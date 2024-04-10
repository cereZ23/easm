EEASM (External Attack Surface Management) costruito attorno allo stack ProjectDiscovery (Subfinder, HTTPX, Naabu, Katana, DNSX, TLSX, Uncover, Nuclei, Notify). È pensato per multi-tenant, continuo, con UI e API.

# Obiettivi

-   **Discovery continuo** di domini, sottodomini, IP esposti e tecnologie.
    
-   **Enrichment e prioritizzazione** (TLS, porte, tecnologie HTTP, esposizioni note).
    
-   **Scanning mirato e sicuro** con Nuclei (template curati).
    
-   **Alerting** su nuove superfici o vulnerabilità critiche.
    
-   **Storico e trend** per cliente/tenant, asset e CVE.
    

* * *

# Architettura (high-level)

1.  **Ingestion & Seeds**
    
    -   Input: domini radice, ASN, IP ranges, wordlist (permutazioni).
        
    -   Fonti OSINT: `uncover` (Shodan/Censys/FOFA ecc., con chiavi per tenant).
        
2.  **Discovery**
    
    -   Passivo: `subfinder` (+ provider keys).
        
    -   DNS: `dnsx` (risoluzione + record A/AAAA/CNAME/NS/TXT/MX).
        
    -   Permutazioni opz.: `dnsx -w permutations.txt`.
        
3.  **Web/Network Enrichment**
    
    -   HTTP: `httpx` (titolo, status, tech, favicon hash, WAF, HTTP2, TLS info base).
        
    -   Porte: `naabu` (top-ports → full-ports su target ad alta priorità).
        
    -   TLS profondo: `tlsx` (issuer, scadenza, chain, vuln note, JA3).
        
    -   Crawling: `katana` (URL surface, JS endpoints, sensitive paths).
        
4.  **Vulnerability Scanning**
    
    -   `nuclei` su risultati `httpx/naabu/katana/tlsx`, con **severity gates** e **rate-limit**.
        
5.  **Storage & API**
    
    -   DB: PostgreSQL (metadata, tenants, findings), + MinIO/S3 (artefatti/JSON grezzi).
        
    -   Coda: Redis + Celery (scheduler/worker).
        
    -   API Backend: **FastAPI** (o Flask se preferisci), autenticazione JWT (multi-tenant).
        
    -   UI: **Vue.js** (dashboard, timeline, diff tra run).
        
6.  **Alerting**
    
    -   `notify` → Slack/Email/Webhook. Policy per severity/time-window/suppressioni.
        
7.  **Scheduler**
    
    -   Celery Beat (o Argo Workflows/K8s CronJobs). Run giornalieri e “watcher” ogni 15–30 min su asset critici.
        
8.  **Compliance & Sicurezza**
    
    -   Scope per tenant, esclusioni, throttle globale, logging e audit trail.
        

* * *

# Flusso dati (pipeline per tenant)

`Seeds → uncover → subfinder → dnsx(resolved) →    ├─ httpx (web attrs) ─┐   ├─ naabu (open ports) ├─→ merge assets → katana (crawl) → nuclei (templates filtrati)    └─ tlsx (cert intel) ─┘ → normalizzazione JSON → DB (assets, exposures, findings) → scoring → notify`

* * *

# Comandi chiave (idempotenti e componibili)

**1) Discovery**

`uncover -q 'org:"ACME Corp"' -e shodan,censys -silent | tee seeds.txt subfinder -dL roots.txt -all -recursive -silent -o subdomains.txt dnsx -l subdomains.txt -a -aaaa -cname -mx -resp -silent -o resolved.txt`

**2) Enrichment**

`httpx -l resolved.txt -mc 200,301,302,403 -server -tech-detect -title -follow-redirects \   -json -o httpx.json naabu -l resolved.txt -top-ports 1000 -rate 8000 -json -o naabu.json tlsx -l resolved.txt -cn -sans -issuer -exp -alpn -ja3 -json -o tlsx.json katana -uL <(jq -r '.[].url' httpx.json) -js-crawl -silent -json -o katana.json`

**3) Vulnerability scanning**

`nuclei -l <(jq -r '.[].url' httpx.json) \   -t cves/ -t exposed-panels/ -t misconfiguration/ \   -severity critical,high,medium -rl 300 -bs 50 -c 50 \   -json -o nuclei.json`

**4) Alerting**

`cat nuclei.json | jq -cr '. | select(.severity=="critical")' | notify -provider-config notify.conf`

* * *

# Data model (PostgreSQL, minimale)

-   `tenants(id, name, slug, contact_policy)`
    
-   `assets(id, tenant_id, type('domain','subdomain','ip','url','service'), identifier, first_seen, last_seen, risk_score)`
    
-   `services(id, asset_id, port, proto, product, version, tls_fingerprint, last_seen)`
    
-   `findings(id, asset_id, source('nuclei','manual'), template_id, name, severity, cvss, evidence, first_seen, last_seen, status('open','suppressed','fixed'))`
    
-   `events(id, asset_id, kind('new_asset','open_port','new_cert','new_path'), payload, created_at)`
    

**Risk score (esempio):**

`score = max_severity_weight + (is_new_asset? 10:0) + (exp_tls? 8:0) + (internet_exposed_login? 6:0)`

* * *

# API (FastAPI – esempi)

-   `POST /tenants/{t}/seeds` (roots, ASNs)
    
-   `GET /tenants/{t}/assets?changed_since=...`
    
-   `GET /tenants/{t}/findings?severity>=high&status=open`
    
-   `POST /tenants/{t}/suppressions` (pattern per falsi positivi)
    
-   `GET /tenants/{t}/risk/scorecard`
    

* * *

# UI (Vue.js – widget essenziali)

-   **Attack Surface Map**: cards per domini → sottodomini → servizi.
    
-   **Delta view**: “nuovi asset/porte” ultimi 24h/7gg.
    
-   **Findings board**: filtri per severity, service, template, tenant.
    
-   **TLS Hygiene**: cert in scadenza, weak ciphers, mismatch.
    
-   **Tech radar**: Wappalyzer/`httpx` per tecnologia (priorità patch).
    

* * *

# Deployment

-   **PoC veloce**: Docker Compose
    
    -   `api` (FastAPI), `worker` (Celery), `beat`, `db` (Postgres), `redis`, `minio`, `ui`.
        
    -   Container “runner” con tool PD + volume `templates/` per nuclei.
