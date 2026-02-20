#!/usr/bin/env python3
"""
Quick reconnaissance scan using Subfinder + Amass + HTTPX
Inserts results directly into the EASM database
"""
import subprocess
import json
import sys
from datetime import datetime
import psycopg2
from psycopg2.extras import execute_values

# Database connection
DB_CONFIG = {
    'host': 'localhost',
    'port': 15432,
    'database': 'easm',
    'user': 'easm',
    'password': 'easm_password'
}

def run_subfinder(domain):
    """Run Subfinder for subdomain discovery"""
    print(f"\n🔍 Running Subfinder on {domain}...")
    cmd = ['docker-compose', 'exec', '-T', 'worker', 'subfinder', '-d', domain, '-silent']
    result = subprocess.run(cmd, capture_output=True, text=True)
    subdomains = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    print(f"✅ Subfinder found {len(subdomains)} subdomains")
    return subdomains

def run_amass(domain):
    """Run Amass for subdomain enumeration"""
    print(f"\n🔍 Running Amass passive scan on {domain}...")
    cmd = ['docker-compose', 'exec', '-T', 'worker', 'amass', 'enum', '-passive', '-d', domain, '-timeout', '2']
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    subdomains = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    print(f"✅ Amass found {len(subdomains)} subdomains")
    return subdomains

def run_httpx(subdomains):
    """Run HTTPX to probe web services"""
    print(f"\n🌐 Running HTTPX on {len(subdomains)} subdomains...")

    # Write subdomains to temp file
    with open('/tmp/scan_targets.txt', 'w') as f:
        f.write('\n'.join(subdomains))

    # Copy to worker container
    subprocess.run(['docker', 'cp', '/tmp/scan_targets.txt', 'easm-worker:/tmp/targets.txt'], check=True)

    # Run HTTPX
    cmd = [
        'docker-compose', 'exec', '-T', 'worker', 'httpx',
        '-l', '/tmp/targets.txt',
        '-silent', '-json',
        '-title', '-tech-detect', '-status-code', '-web-server',
        '-timeout', '10', '-retries', '1'
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)

    # Parse JSON output
    http_results = []
    for line in result.stdout.splitlines():
        if line.strip():
            try:
                data = json.loads(line)
                http_results.append(data)
            except json.JSONDecodeError:
                continue

    print(f"✅ HTTPX probed {len(http_results)} web services")
    return http_results

def insert_assets(conn, tenant_id, domain, subdomains, http_results):
    """Insert discovered assets into database"""
    cursor = conn.cursor()

    # Insert root domain
    print(f"\n💾 Inserting assets into database...")
    cursor.execute("""
        INSERT INTO assets (tenant_id, type, identifier, priority, is_active, first_seen, last_seen)
        VALUES (%s, 'DOMAIN', %s, 'high', true, NOW(), NOW())
        ON CONFLICT (tenant_id, identifier) DO UPDATE
        SET last_seen = NOW(), is_active = true
        RETURNING id
    """, (tenant_id, domain))

    domain_id = cursor.fetchone()[0]

    # Prepare subdomain data
    subdomain_data = []
    for subdomain in subdomains:
        if subdomain != domain and subdomain.endswith('.' + domain):
            subdomain_data.append((
                tenant_id,
                'SUBDOMAIN',
                subdomain,
                'medium',
                True,
                datetime.now(),
                datetime.now()
            ))

    # Bulk insert subdomains
    if subdomain_data:
        execute_values(cursor, """
            INSERT INTO assets (tenant_id, type, identifier, priority, is_active, first_seen, last_seen)
            VALUES %s
            ON CONFLICT (tenant_id, identifier) DO UPDATE
            SET last_seen = EXCLUDED.last_seen, is_active = true
        """, subdomain_data)

    conn.commit()
    print(f"✅ Inserted {len(subdomain_data)} subdomains")

    # Insert HTTP/service data
    if http_results:
        service_count = 0
        for http_data in http_results:
            try:
                host = http_data.get('host', http_data.get('url', '')).replace('http://', '').replace('https://', '').split('/')[0].split(':')[0]

                # Find asset
                cursor.execute("SELECT id FROM assets WHERE tenant_id = %s AND identifier = %s", (tenant_id, host))
                row = cursor.fetchone()
                if not row:
                    continue

                asset_id = row[0]
                port = http_data.get('port', 443 if 'https' in http_data.get('url', '') else 80)

                # Insert service
                cursor.execute("""
                    INSERT INTO services (
                        asset_id, port, protocol, product, version,
                        http_title, http_status, web_server, has_tls,
                        first_seen, last_seen
                    )
                    VALUES (%s, %s, 'tcp', %s, %s, %s, %s, %s, %s, NOW(), NOW())
                    ON CONFLICT DO NOTHING
                """, (
                    asset_id,
                    port,
                    http_data.get('webserver', 'http'),
                    None,
                    http_data.get('title', ''),
                    http_data.get('status_code'),
                    http_data.get('webserver'),
                    'https' in http_data.get('url', '')
                ))
                service_count += 1

            except Exception as e:
                print(f"⚠️  Error processing {http_data.get('url')}: {e}")
                continue

        conn.commit()
        print(f"✅ Inserted {service_count} services")

    return domain_id

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 quick_scan.py <domain>")
        print("Example: python3 quick_scan.py tesla.com")
        sys.exit(1)

    domain = sys.argv[1]
    tenant_id = 2  # Demo Organization

    print(f"\n🚀 Starting reconnaissance scan for: {domain}")
    print(f"   Tenant ID: {tenant_id}")
    print("="*60)

    try:
        # Run subdomain discovery
        subfinder_results = run_subfinder(domain)
        amass_results = run_amass(domain)

        # Combine and deduplicate
        all_subdomains = list(set(subfinder_results + amass_results + [domain]))
        print(f"\n📊 Total unique subdomains found: {len(all_subdomains)}")

        # Run HTTPX
        http_results = run_httpx(all_subdomains[:50])  # Limit to first 50 for quick test

        # Connect to database
        print(f"\n🔌 Connecting to database...")
        conn = psycopg2.connect(**DB_CONFIG)

        # Insert results
        insert_assets(conn, tenant_id, domain, all_subdomains, http_results)

        conn.close()

        print("\n" + "="*60)
        print("✅ Scan complete! Check the UI at http://localhost:13000")
        print(f"   - Total subdomains: {len(all_subdomains)}")
        print(f"   - Web services: {len(http_results)}")
        print("="*60 + "\n")

    except subprocess.TimeoutExpired:
        print("⚠️  Scan timed out - partial results may be available")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
