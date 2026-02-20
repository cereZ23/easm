# Nuclei Integration - Quick Start Guide

## Overview

Nuclei vulnerability scanner is fully integrated into the EASM platform as **Phase 3** of the enrichment pipeline. It automatically scans live web services discovered by HTTPx for known vulnerabilities.

## Quick Start

### 1. Enable Nuclei Scanning

```python
# In .env or environment variables
FEATURE_NUCLEI_ENABLED=true
```

### 2. Run Enrichment Pipeline (includes Nuclei)

```bash
# Via Celery task
from app.tasks.enrichment import run_enrichment_pipeline

result = run_enrichment_pipeline.delay(
    tenant_id=1,
    asset_ids=None,  # All assets
    priority='critical',  # Optional: only critical assets
    force_refresh=False
)
```

The pipeline automatically executes:
1. **Phase 1**: HTTPx + Naabu + TLSx (parallel)
2. **Phase 2**: Katana (web crawling)
3. **Phase 3**: Nuclei (vulnerability scanning) ✅

### 3. Trigger Nuclei Scan Manually

```python
from app.tasks.scanning import run_nuclei_scan

result = run_nuclei_scan.delay(
    tenant_id=1,
    asset_ids=[123, 456],  # Optional: specific assets
    severity=['critical', 'high', 'medium'],
    templates=['cves/', 'exposed-panels/'],
    rate_limit=300
)
```

### 4. Query Findings

```python
from app.database import SessionLocal
from app.repositories.finding_repository import FindingRepository

db = SessionLocal()
repo = FindingRepository(db)

# Get critical findings
findings = repo.get_findings(
    tenant_id=1,
    severity=['critical', 'high'],
    status=['open']
)

for finding in findings:
    print(f"{finding.severity.value}: {finding.name}")
    print(f"  Asset: {finding.asset.identifier}")
    print(f"  CVE: {finding.cve_id}")
    print(f"  CVSS: {finding.cvss_score}")
    print(f"  Matched: {finding.matched_at}")
```

## Common Operations

### Scan Single Asset

```python
from app.tasks.scanning import scan_single_asset

result = scan_single_asset.delay(
    tenant_id=1,
    asset_id=123,
    severity=['critical', 'high']
)
```

### Scan Critical Assets Only

```python
from app.tasks.scanning import scan_critical_assets

result = scan_critical_assets.delay(tenant_id=1)
```

### Update Nuclei Templates

```python
from app.tasks.scanning import update_nuclei_templates

result = update_nuclei_templates.delay()
# Returns: {'success': True, 'timestamp': '...'}
```

### Create Suppression Rule

```python
from app.database import SessionLocal
from app.services.scanning.suppression_service import SuppressionService

db = SessionLocal()
service = SuppressionService(db, tenant_id=1)

# Suppress findings on test domains
service.create_suppression(
    name="Suppress test environments",
    pattern_type="url",
    pattern=r"(test|staging|dev)\.",
    reason="Test environments have intentional vulnerabilities",
    is_global=False  # Tenant-specific
)

# Suppress specific template
service.create_suppression(
    name="Suppress old Log4j CVEs",
    pattern_type="template_id",
    pattern=r"CVE-2021-44228",
    reason="Already patched in our environment",
    expires_at=datetime(2025, 12, 31)  # Temporary suppression
)
```

### List Suppressions

```python
suppressions = service.list_suppressions(
    include_global=True,
    include_expired=False
)

for supp in suppressions:
    print(f"{supp['name']}: {supp['pattern']}")
```

### Get Finding Statistics

```python
stats = repo.get_finding_stats(
    tenant_id=1,
    days=30  # Last 30 days
)

print(f"Total findings: {stats['total']}")
print(f"By severity: {stats['by_severity']}")
print(f"By status: {stats['by_status']}")
print(f"Top CVEs: {stats['top_cves']}")
```

### Get New Findings

```python
# Get findings discovered in last 24 hours
new_findings = repo.get_new_findings(
    tenant_id=1,
    since_hours=24
)

for finding in new_findings:
    print(f"NEW: {finding.severity.value} - {finding.name}")
```

## Configuration

### Environment Variables

```bash
# Feature flag
FEATURE_NUCLEI_ENABLED=true

# Timeouts
DISCOVERY_NUCLEI_TIMEOUT=1800  # 30 minutes

# Tool whitelist
TOOL_ALLOWED_TOOLS=nuclei,subfinder,httpx,naabu,tlsx,katana
```

### Scan Configuration

```python
# app/services/scanning/nuclei_service.py

# Default severity levels
DEFAULT_SEVERITIES = ['critical', 'high', 'medium']

# Template categories
TEMPLATE_CATEGORIES = {
    'cves': 'CVE-based vulnerabilities',
    'exposed-panels': 'Exposed admin/login panels',
    'misconfigurations': 'Common misconfigurations',
    'default-logins': 'Default credentials',
    'takeovers': 'Subdomain takeovers',
    'exposures': 'Information disclosure',
    'technologies': 'Technology detection',
    'vulnerabilities': 'Generic vulnerabilities',
}
```

### Nuclei Command Arguments

```bash
# Default arguments (in NucleiService)
nuclei \
  -l urls.txt \
  -json \
  -silent \
  -severity critical,high,medium \
  -rl 300 \          # Rate limit: 300 req/s
  -c 50 \            # Concurrency: 50 templates
  -timeout 10 \      # Request timeout: 10s
  -retries 1 \       # Retry once
  -t cves/ \
  -t exposed-panels/ \
  -t misconfigurations/ \
  -exclude-tags dos,fuzz,intrusive
```

## Template Management

### List Available Templates

```python
from app.services.scanning.template_manager import template_manager

# List all templates
templates = template_manager.list_templates()

# Filter by category
cve_templates = template_manager.list_templates(
    categories=['cves']
)

# Filter by severity
critical_templates = template_manager.list_templates(
    severity=['critical', 'high']
)
```

### Get Template Categories

```python
categories = template_manager.get_categories()

for name, info in categories.items():
    print(f"{name}: {info['description']}")
```

### Get Recommended Templates

```python
# Get recommended templates by asset type
web_templates = template_manager.get_recommended_templates('web')
# Returns: ['cves/', 'exposed-panels/', 'misconfigurations/', ...]

api_templates = template_manager.get_recommended_templates('api')
# Returns: ['cves/', 'misconfigurations/', 'exposures/']
```

## Risk Scoring

### How Risk Scores Are Calculated

```python
# Severity weights
severity_weights = {
    'critical': 3.0,
    'high': 2.0,
    'medium': 1.0,
    'low': 0.5,
    'info': 0.1
}

# Score = sum of weights (capped at 10.0)
```

### Priority Assignment

```python
# Auto-calculated based on risk score
if risk_score >= 7.0:
    priority = 'critical'
elif risk_score >= 5.0:
    priority = 'high'
elif risk_score >= 2.0:
    priority = 'normal'
else:
    priority = 'low'
```

### Manual Risk Score Calculation

```python
from app.services.scanning.nuclei_service import calculate_risk_score_from_findings

findings = [
    {'severity': 'critical'},
    {'severity': 'high'},
    {'severity': 'medium'}
]

score = calculate_risk_score_from_findings(findings)
# Returns: 6.0 (3.0 + 2.0 + 1.0)
```

## Suppression Patterns

### Common Suppression Rules

```python
# 1. Suppress localhost findings
{
    'pattern_type': 'host',
    'pattern': r'^(localhost|127\.0\.0\.1)$',
    'reason': 'Localhost not relevant'
}

# 2. Suppress test/staging environments
{
    'pattern_type': 'url',
    'pattern': r'(test|staging|dev)\.',
    'reason': 'Test environments may have intentional vulnerabilities'
}

# 3. Suppress specific CVE
{
    'pattern_type': 'template_id',
    'pattern': r'CVE-2020-.*',
    'reason': 'Old CVEs not relevant'
}

# 4. Suppress by severity
{
    'pattern_type': 'severity',
    'pattern': r'^info$',
    'reason': 'Info findings are noise'
}

# 5. Suppress by name
{
    'pattern_type': 'name',
    'pattern': r'.*DNS CAA.*',
    'reason': 'CAA records not required'
}
```

## Monitoring

### Check Scan Status

```python
from celery.result import AsyncResult

task_id = 'abc-123-def-456'
result = AsyncResult(task_id)

print(f"Status: {result.status}")
print(f"Result: {result.result}")
```

### Get Scan Statistics

```python
result = run_nuclei_scan.delay(tenant_id=1)
result_data = result.get()

print(f"Assets scanned: {result_data['assets_scanned']}")
print(f"URLs scanned: {result_data['urls_scanned']}")
print(f"Findings discovered: {result_data['findings_discovered']}")
print(f"Findings suppressed: {result_data['findings_suppressed']}")
print(f"Findings created: {result_data['findings_created']}")
print(f"Findings updated: {result_data['findings_updated']}")
```

### Monitor Finding Trends

```python
from datetime import datetime, timedelta

# Get findings over time
today = repo.get_finding_stats(tenant_id=1, days=1)
week = repo.get_finding_stats(tenant_id=1, days=7)
month = repo.get_finding_stats(tenant_id=1, days=30)

print(f"Today: {today['total']} findings")
print(f"This week: {week['total']} findings")
print(f"This month: {month['total']} findings")
```

## Troubleshooting

### No Findings Returned

**Problem**: Scan completes but no findings are created

**Solutions**:
1. Check if HTTPx enrichment has run (Nuclei needs live web services)
   ```python
   service_repo = ServiceRepository(db)
   web_services = service_repo.get_web_services(asset_id, only_live=True)
   ```

2. Check suppression rules
   ```python
   suppressions = service.list_suppressions()
   # Review patterns that might be too broad
   ```

3. Check severity filters
   ```python
   # Try scanning with all severities
   run_nuclei_scan.delay(
       tenant_id=1,
       severity=['critical', 'high', 'medium', 'low', 'info']
   )
   ```

### Scan Times Out

**Problem**: Nuclei scan exceeds timeout

**Solutions**:
1. Reduce template scope
   ```python
   run_nuclei_scan.delay(
       tenant_id=1,
       templates=['cves/']  # Only CVEs
   )
   ```

2. Increase timeout
   ```python
   # In app/config.py
   discovery_nuclei_timeout = 3600  # 1 hour
   ```

3. Scan in batches
   ```python
   # Split assets into smaller batches
   for batch in asset_batches:
       run_nuclei_scan.delay(tenant_id=1, asset_ids=batch)
   ```

### Template Update Fails

**Problem**: Template update returns error

**Solutions**:
1. Check network connectivity
   ```bash
   docker exec easm-worker curl -I https://github.com
   ```

2. Manual update
   ```bash
   docker exec easm-worker nuclei -update-templates
   ```

3. Check disk space
   ```bash
   docker exec easm-worker df -h
   ```

## Best Practices

### 1. Regular Template Updates

```python
# Schedule daily template updates
from celery.schedules import crontab

app.conf.beat_schedule = {
    'update-nuclei-templates': {
        'task': 'app.tasks.scanning.update_nuclei_templates',
        'schedule': crontab(hour=2, minute=0),  # 2 AM daily
    }
}
```

### 2. Progressive Scanning

```python
# Start with critical assets
scan_critical_assets.delay(tenant_id=1)

# Then high priority
run_nuclei_scan.delay(
    tenant_id=1,
    severity=['critical', 'high']
)

# Finally comprehensive scan
run_enrichment_pipeline.delay(tenant_id=1)
```

### 3. Use Suppressions Wisely

```python
# Create tenant-specific suppressions
service.create_suppression(
    name="Suppress internal tools",
    pattern_type="url",
    pattern=r"internal\.company\.com",
    reason="Internal tools not in scope",
    is_global=False  # Tenant-specific
)

# Use global suppressions for known false positives
service.create_suppression(
    name="Suppress development servers",
    pattern_type="host",
    pattern=r"\.local$",
    reason="Development servers not relevant",
    is_global=True  # All tenants
)
```

### 4. Monitor Critical Findings

```python
# Alert on new critical findings
new_critical = repo.get_new_findings(
    tenant_id=1,
    since_hours=24
)

critical = [f for f in new_critical if f.severity.value == 'critical']

if critical:
    # Send alert
    notify_security_team(critical)
```

### 5. Cleanup Old Findings

```python
# Archive fixed findings older than 90 days
from datetime import datetime, timedelta

cutoff = datetime.utcnow() - timedelta(days=90)

old_fixed = db.query(Finding).filter(
    Finding.status == FindingStatus.FIXED,
    Finding.last_seen < cutoff
).all()

# Archive or delete
for finding in old_fixed:
    # archive_finding(finding)
    db.delete(finding)

db.commit()
```

## API Integration (Future)

### REST API Endpoints (To Be Implemented)

```bash
# Trigger scan
POST /api/tenants/{tenant_id}/scan
{
    "severity": ["critical", "high"],
    "templates": ["cves/", "exposed-panels/"]
}

# Get findings
GET /api/tenants/{tenant_id}/findings?severity=critical&status=open

# Create suppression
POST /api/tenants/{tenant_id}/suppressions
{
    "name": "Suppress test env",
    "pattern_type": "url",
    "pattern": "test\\.",
    "reason": "Test environment"
}

# Update templates
POST /api/system/nuclei/update-templates

# Get scan status
GET /api/tenants/{tenant_id}/scan/{task_id}
```

## Summary

The Nuclei integration is **production-ready** and provides:

✅ Automated vulnerability scanning
✅ Smart template selection
✅ False positive suppression
✅ Automatic risk scoring
✅ Multi-tenant isolation
✅ Comprehensive security controls

**Start scanning vulnerabilities today!**

---

For complete documentation, see:
- `/Users/cere/Downloads/easm/NUCLEI_INTEGRATION_COMPLETE.md`
- `/Users/cere/Downloads/easm/IMPLEMENTATION_SUMMARY.md`
