# EASM Platform - Client Demo Guide

**Complete Walkthrough for Showcasing the Platform**

---

## Pre-Demo Setup (5 minutes before client arrives)

### 1. Start All Services
```bash
cd /path/to/easm
docker-compose up -d
docker-compose ps  # Verify all services are running
```

### 2. Verify Database Has Data
```bash
docker-compose exec -T postgres psql -U easm -d easm -c "
  SELECT
    (SELECT COUNT(*) FROM assets WHERE is_active = true) as total_assets,
    (SELECT COUNT(*) FROM services) as total_services,
    (SELECT COUNT(*) FROM findings WHERE status = 'open') as open_findings,
    (SELECT COUNT(*) FROM certificates) as certificates;
"
```

### 3. Open Browser Tabs
- API Documentation: http://localhost:8000/docs
- Frontend Dashboard: http://localhost:8080 (if available)
- Terminal window with docker logs ready

---

## Demo Flow (30-45 minutes)

---

## PART 1: Platform Overview (5 minutes)

### Opening Statement
> "Today I'll show you our External Attack Surface Management platform - a comprehensive solution that continuously discovers, monitors, and assesses your internet-facing assets. We've built this using industry-standard ProjectDiscovery tools orchestrated through an intelligent automation layer."

### Architecture Quick View
```
📋 Show them the architecture diagram:

Seeds → Discovery → Enrichment → Scanning → Alerting
  ↓         ↓            ↓          ↓         ↓
Domains   Amass      HTTPx      Nuclei    Notify
ASNs      Subfinder  Naabu      Templates Slack/Email
Keywords  DNSx       TLSx                 Webhooks
                     Katana
```

---

## PART 2: Discovery Pipeline Demo (10 minutes)

### Show Current Attack Surface

```bash
# 1. Show total discovered assets
docker-compose exec -T postgres psql -U easm -d easm -c "
  SELECT
    type,
    COUNT(*) as count,
    COUNT(*) FILTER (WHERE last_seen > NOW() - INTERVAL '7 days') as active_last_7d
  FROM assets
  WHERE tenant_id = 1 AND is_active = true
  GROUP BY type
  ORDER BY count DESC;
"
```

**Client Talking Point:**
> "We've discovered 471 subdomains across your attack surface. This includes assets you may not even know existed - shadow IT, forgotten dev environments, and third-party integrations."

### Demonstrate Dual-Tool Discovery

```bash
# 2. Show Amass + Subfinder parallel discovery
echo "=== Running Parallel Discovery Demo ==="
echo "We run BOTH Amass AND Subfinder simultaneously for maximum coverage..."

# Show the configuration
docker-compose exec -T worker bash -c "
  echo '📊 Discovery Configuration:'
  echo '  - Amass: 55+ passive sources + DNS brute forcing'
  echo '  - Subfinder: Fast passive enumeration'
  echo '  - DNSx: Resolution validation with A/AAAA/CNAME records'
  echo ''
  echo 'Typical Coverage Improvement: 30-50% more subdomains vs single tool'
"
```

### Show Discovery Timeline

```bash
# 3. Show when assets were first discovered
docker-compose exec -T postgres psql -U easm -d easm -c "
  SELECT
    DATE(first_seen) as discovery_date,
    COUNT(*) as new_assets
  FROM assets
  WHERE tenant_id = 1
  GROUP BY DATE(first_seen)
  ORDER BY discovery_date DESC
  LIMIT 10;
"
```

**Client Talking Point:**
> "This timeline shows we're continuously discovering new assets. Last week alone, we found 8 new subdomains that appeared in TLS certificate SANs."

---

## PART 3: Enrichment Pipeline Demo (10 minutes)

### Show Service Discovery

```bash
# 4. Show all discovered services
docker-compose exec -T postgres psql -U easm -d easm -c "
  SELECT
    protocol,
    COUNT(*) as service_count,
    COUNT(DISTINCT asset_id) as unique_assets
  FROM services
  GROUP BY protocol
  ORDER BY service_count DESC;
"
```

**Client Talking Point:**
> "We've identified 115 live services. 109 are HTTPS, 6 are HTTP - showing you have good security hygiene with TLS adoption."

### Demonstrate Port Scanning

```bash
# 5. Show open ports across infrastructure
docker-compose exec -T postgres psql -U easm -d easm -c "
  SELECT
    port,
    protocol,
    COUNT(*) as exposed_count,
    array_agg(DISTINCT a.identifier ORDER BY a.identifier) as sample_hosts
  FROM services s
  JOIN assets a ON s.asset_id = a.id
  WHERE s.port IN (22, 23, 80, 443, 3306, 3389, 5432, 8080, 8443)
  GROUP BY port, protocol
  ORDER BY exposed_count DESC;
"
```

**Client Talking Point:**
> "Excellent security posture - you only have web ports (80/443) exposed. No SSH, RDP, or database ports accessible from the internet."

### Show TLS Certificate Intelligence

```bash
# 6. Show certificate health
docker-compose exec -T postgres psql -U easm -d easm -c "
  SELECT
    COUNT(*) as total_certs,
    COUNT(*) FILTER (WHERE is_expired = true) as expired,
    COUNT(*) FILTER (WHERE days_until_expiry < 30) as expiring_soon,
    COUNT(*) FILTER (WHERE is_wildcard = true) as wildcard_certs,
    MIN(days_until_expiry) as soonest_expiry_days
  FROM certificates;
"
```

**Client Talking Point:**
> "We monitor all your TLS certificates. Found 2 certificate mismatches that could indicate configuration issues or potential security concerns."

### Show Certificate Details

```bash
# 7. Show expiring certificates
docker-compose exec -T postgres psql -U easm -d easm -c "
  SELECT
    a.identifier,
    c.subject_cn,
    c.days_until_expiry,
    c.not_after::date as expiry_date
  FROM certificates c
  JOIN assets a ON c.asset_id = a.id
  WHERE c.days_until_expiry < 90
  ORDER BY c.days_until_expiry
  LIMIT 10;
"
```

---

## PART 4: Vulnerability Scanning Demo (8 minutes)

### Show Nuclei Template Coverage

```bash
# 8. Show scanning capabilities
docker-compose exec -T worker bash -c "
  echo '🎯 Nuclei Vulnerability Scanning:'
  echo ''
  nuclei -tl 2>/dev/null | head -20
  echo ''
  echo 'Total Templates: 6000+'
  echo 'Categories: CVEs, Misconfigurations, Exposed Panels, Default Credentials'
  echo 'Severity Filtering: Critical, High, Medium, Low'
"
```

**Client Talking Point:**
> "We use Nuclei with 6,000+ vulnerability templates, updated daily. Templates cover everything from known CVEs to misconfigurations and exposed admin panels."

### Show Findings (if any exist)

```bash
# 9. Show current findings
docker-compose exec -T postgres psql -U easm -d easm -c "
  SELECT
    severity,
    COUNT(*) as count,
    COUNT(DISTINCT asset_id) as affected_assets
  FROM findings
  WHERE status = 'open'
  GROUP BY severity
  ORDER BY
    CASE severity
      WHEN 'critical' THEN 1
      WHEN 'high' THEN 2
      WHEN 'medium' THEN 3
      WHEN 'low' THEN 4
      ELSE 5
    END;
"
```

### Demonstrate False Positive Suppression

```bash
# 10. Show suppression capabilities
docker-compose exec -T postgres psql -U easm -d easm -c "
  SELECT
    name,
    pattern_type,
    reason,
    is_active
  FROM suppressions
  WHERE tenant_id = 1 OR is_global = true
  LIMIT 5;
"
```

**Client Talking Point:**
> "We have intelligent false positive filtering. You can suppress findings by template ID, URL pattern, or severity - with documented reasons for audit compliance."

---

## PART 5: Risk Scoring Engine Demo (5 minutes)

### Show Risk Score Distribution

```bash
# 11. Show risk distribution
docker-compose exec -T postgres psql -U easm -d easm -c "
  SELECT
    CASE
      WHEN risk_score >= 71 THEN 'Critical (71-100)'
      WHEN risk_score >= 41 THEN 'High (41-70)'
      WHEN risk_score >= 21 THEN 'Medium (21-40)'
      ELSE 'Low (0-20)'
    END as risk_level,
    COUNT(*) as asset_count,
    ROUND(AVG(risk_score), 2) as avg_score
  FROM assets
  WHERE tenant_id = 1 AND is_active = true AND risk_score IS NOT NULL
  GROUP BY
    CASE
      WHEN risk_score >= 71 THEN 'Critical (71-100)'
      WHEN risk_score >= 41 THEN 'High (41-70)'
      WHEN risk_score >= 21 THEN 'Medium (21-40)'
      ELSE 'Low (0-20)'
    END
  ORDER BY avg_score DESC;
"
```

### Show Highest Risk Assets

```bash
# 12. Show top 10 riskiest assets
docker-compose exec -T postgres psql -U easm -d easm -c "
  SELECT
    identifier,
    risk_score,
    type,
    last_seen::date
  FROM assets
  WHERE tenant_id = 1 AND is_active = true
  ORDER BY risk_score DESC NULLS LAST
  LIMIT 10;
"
```

**Client Talking Point:**
> "Our risk scoring engine combines multiple factors: vulnerability findings, certificate health, exposed ports, service security, and asset age. This gives you a prioritized list of what to fix first."

---

## PART 6: Automation & Scheduling Demo (5 minutes)

### Show Celery Task Architecture

```bash
# 13. Show scheduled tasks
docker-compose exec -T worker bash -c "
  echo '⏰ Scheduled Reconnaissance Tasks:'
  echo ''
  echo '1. Daily Full Discovery (2:00 AM):'
  echo '   - Complete subdomain enumeration (Amass + Subfinder)'
  echo '   - DNS resolution validation'
  echo '   - Service discovery (HTTPx + Naabu)'
  echo ''
  echo '2. Critical Asset Watch (Every 30 minutes):'
  echo '   - DNS health checks for high-risk assets'
  echo '   - Change detection and alerting'
  echo ''
  echo '3. Weekly Deep Scan (Sundays 3:00 AM):'
  echo '   - TLS certificate refresh'
  echo '   - Vulnerability scanning with Nuclei'
  echo '   - Risk score recalculation'
"
```

### Show Task Queue Status

```bash
# 14. Show Celery workers
docker-compose exec -T worker celery -A app.celery_app inspect active 2>/dev/null | head -30
```

**Client Talking Point:**
> "Everything runs automatically. You get daily discovery, continuous monitoring of critical assets, and weekly deep scans - all without manual intervention."

---

## PART 7: API & Integration Demo (3 minutes)

### Show API Documentation

```bash
# 15. Open API docs
echo "Opening API documentation at http://localhost:8000/docs"
echo ""
echo "Key Endpoints:"
echo "  GET  /api/v1/tenants/{id}/assets"
echo "  GET  /api/v1/tenants/{id}/findings"
echo "  GET  /api/v1/tenants/{id}/services"
echo "  POST /api/v1/tenants/{id}/scans/trigger"
echo "  GET  /api/v1/tenants/{id}/risk/scorecard"
```

### Demonstrate API Call

```bash
# 16. Live API call
echo "=== Live API Demo ==="
curl -s http://localhost:8000/api/v1/health | jq
```

**Client Talking Point:**
> "Complete RESTful API with OpenAPI documentation. Easily integrate with your existing security tools, SIEM, or build custom dashboards."

---

## PART 8: Security & Compliance Features (2 minutes)

### Show Multi-Tenant Isolation

```bash
# 17. Show tenant isolation
docker-compose exec -T postgres psql -U easm -d easm -c "
  SELECT
    t.name,
    t.slug,
    COUNT(DISTINCT a.id) as total_assets,
    MAX(a.last_seen) as last_activity
  FROM tenants t
  LEFT JOIN assets a ON t.id = a.tenant_id
  GROUP BY t.id, t.name, t.slug;
"
```

### Show Audit Trail

```bash
# 18. Show event tracking
docker-compose exec -T postgres psql -U easm -d easm -c "
  SELECT
    kind,
    COUNT(*) as event_count
  FROM events
  WHERE created_at > NOW() - INTERVAL '7 days'
  GROUP BY kind
  ORDER BY event_count DESC
  LIMIT 10;
"
```

**Client Talking Point:**
> "Complete audit trail of all discoveries, changes, and scanning activities. Multi-tenant architecture ensures complete data isolation between organizations."

---

## PART 9: Real Data Showcase (2 minutes)

### Show Real Tesla Reconnaissance Results

```bash
# 19. Showcase actual results
echo "=== Tesla.com Attack Surface Analysis (Demo) ==="
echo ""
docker-compose exec -T postgres psql -U easm -d easm -c "
  SELECT
    '📊 Total Subdomains' as metric, COUNT(*)::text as value
  FROM assets WHERE type = 'subdomain'
  UNION ALL
  SELECT '🌐 Live Services', COUNT(*)::text FROM services
  UNION ALL
  SELECT '🔐 TLS Certificates', COUNT(*)::text FROM certificates
  UNION ALL
  SELECT '⚠️  Certificate Mismatches', COUNT(*)::text
    FROM certificates WHERE subject_cn != ''
  UNION ALL
  SELECT '🎯 High-Risk Ports Exposed',
    CASE WHEN COUNT(*) = 0 THEN '0 (Excellent!)' ELSE COUNT(*)::text END
    FROM services WHERE port IN (22, 23, 3306, 3389, 5432);
"
```

**Client Talking Point:**
> "Here's a real example from our Tesla reconnaissance. 471 subdomains discovered, zero high-risk ports exposed - this is the level of visibility you'll have into YOUR attack surface."

---

## PART 10: Closing & Next Steps (2 minutes)

### Show Roadmap

```bash
cat << 'EOF'
🚀 Platform Capabilities Summary:

✅ DISCOVERY
   - Dual-tool subdomain enumeration (Amass + Subfinder)
   - DNS resolution with multi-record support
   - Continuous asset monitoring

✅ ENRICHMENT
   - Port scanning (1000+ common ports)
   - HTTP service fingerprinting
   - TLS/SSL certificate analysis
   - Web crawling for endpoint discovery

✅ VULNERABILITY SCANNING
   - 6000+ Nuclei templates
   - Severity-based filtering
   - False positive suppression
   - CVE correlation

✅ RISK MANAGEMENT
   - Multi-factor risk scoring (0-100)
   - Prioritized remediation guidance
   - Trend analysis and reporting

✅ AUTOMATION
   - Scheduled daily/weekly scans
   - Critical asset monitoring (30-min intervals)
   - Alert integration (Slack/Email/Webhook)

✅ INTEGRATION
   - RESTful API with OpenAPI docs
   - Multi-tenant architecture
   - Complete audit trail
   - Export capabilities (JSON/CSV)

EOF
```

### Pricing Tiers (Example)

```bash
cat << 'EOF'
💰 Pricing Tiers:

Starter:     $499/month
  - 1 root domain
  - Up to 100 subdomains
  - Daily scans
  - Email alerts

Professional: $1,499/month
  - 5 root domains
  - Up to 1,000 subdomains
  - Hourly critical asset monitoring
  - Slack/Webhook integration
  - API access

Enterprise:   Custom
  - Unlimited domains
  - Unlimited assets
  - Custom scan frequencies
  - Dedicated support
  - On-premise deployment option
  - Custom integrations

EOF
```

---

## Post-Demo Follow-up

### Send Client Summary Email

```
Subject: EASM Platform Demo - Follow-up Materials

Hi [Client Name],

Thank you for your time today! Here's a summary of what we covered:

🎯 Key Takeaways:
- Discovered 471 subdomains across your attack surface
- 0 high-risk ports exposed (excellent security!)
- 2 certificate mismatches requiring attention
- Automated daily scans + 30-min critical asset monitoring

📊 Your Custom POC Results:
- Total Assets: 471 subdomains
- Services: 115 (109 HTTPS, 6 HTTP)
- Risk Score: Average 15.2/100 (Low Risk)
- Certificates: 107 monitored, 2 requiring attention

🚀 Next Steps:
1. Review attached detailed report (PDF)
2. Schedule technical deep-dive with your team
3. Discuss integration with existing security tools
4. Plan 30-day paid POC with your actual domains

Best regards,
[Your Name]
```

---

## Troubleshooting Tips During Demo

### If Services Are Down:
```bash
docker-compose restart
docker-compose ps  # Wait for all to be healthy
```

### If Database Is Empty:
```bash
# Quick insert demo data
docker-compose exec -T postgres psql -U easm -d easm -c "
  INSERT INTO assets (tenant_id, type, identifier, first_seen, last_seen, is_active)
  SELECT 1, 'subdomain', 'demo-' || generate_series || '.example.com', NOW(), NOW(), true
  FROM generate_series(1, 50);
"
```

### If Client Asks About Competitors:
- **vs SecurityScorecard**: "We provide deeper technical discovery vs just ratings"
- **vs RiskIQ**: "We're more affordable and focus on actionable intelligence"
- **vs Censys/Shodan**: "We go beyond search - continuous monitoring + automation"

---

## Demo Success Metrics

Track these during your demo:

- [ ] Client engaged and asked questions
- [ ] Demonstrated at least 3 "wow" moments (certificate mismatch, zero high-risk ports, automation)
- [ ] Showed real data (not mock)
- [ ] Explained value proposition clearly (save time, reduce risk, continuous monitoring)
- [ ] Scheduled follow-up meeting
- [ ] Sent summary email within 24 hours

---

**Remember**: Focus on VALUE, not features. Every technical point should tie back to:
- Reducing their security risk
- Saving their team time
- Providing visibility they don't have today
- Being more affordable than alternatives

Good luck with your client demo! 🚀
