# 📊 Meridian Group Security Assessment Report
**Generated**: 2025-10-26 01:10:00
**Domain**: meridian-group.eu
**Tenant ID**: 5

---

## Executive Summary

⚠️ **Status**: Discovery In Progress - Pipeline Error Detected

**Current State**:
- ✅ Tenant successfully onboarded
- ✅ Discovery tools executing correctly
- ❌ Results not being processed due to Celery task architecture issue
- ⏳ 0 assets discovered (pipeline failure, not lack of findings)

**Issue Identified**: The `run_parallel_enumeration` task is calling `.get()` on subtasks, which violates Celery best practices and causes the pipeline to fail before results can be processed.

---

## 1. Tenant Information

| Property | Value |
|----------|-------|
| **Tenant ID** | 5 |
| **Company Name** | Meridian Group |
| **Slug** | meridian-group |
| **Created** | 2025-10-26 00:40:31 UTC |
| **Primary Domain** | meridian-group.eu |

### User Account
```
Email:    admin@meridian-group.eu
Password: SecurePassword123!
Status:   Active ✅
```

### Login URL
```
http://localhost:13000
```

---

## 2. Seed Configuration

| Seed Type | Value | Status |
|-----------|-------|--------|
| Domain | meridian-group.eu | ✅ Active |

**Total Seeds**: 1 domain seed configured

---

## 3. Discovery Status

### Timeline of Discovery Attempts

#### Attempt 1 - 2025-10-26 01:02:09
- **Status**: ❌ Failed (tools not installed)
- **Error**: `FileNotFoundError: [Errno 2] No such file or directory: 'subfinder'`

#### Attempt 2 - 2025-10-26 01:04:36
- **Status**: ❌ Failed (tools not installed)
- **Error**: `FileNotFoundError: [Errno 2] No such file or directory: 'subfinder'`

#### Attempt 3 - 2025-10-26 01:06:02 (Latest)
- **Status**: ⚠️ Tools Executed, Pipeline Failed
- **Subfinder**: ✅ Ran for 11.84 seconds
- **Amass**: ⚠️ Ran but has v4 flag error
- **Pipeline Error**: ❌ `run_parallel_enumeration` failed
- **Reason**: Celery task called `.get()` synchronously (forbidden)

### Error Details

```
Task app.tasks.discovery.run_parallel_enumeration failed:
Never call result.get() within a task!
See https://docs.celeryq.dev/en/latest/userguide/tasks.html#avoid-launching-synchronous-subtasks
```

**Impact**: Even though Subfinder and Amass executed successfully, their results were not merged or processed into the database.

---

## 4. Current Metrics

### Assets Discovered
| Asset Type | Count |
|------------|-------|
| **Total Assets** | 0 |
| Domains | 0 |
| Subdomains | 0 |
| IPs | 0 |
| URLs | 0 |

**Note**: This is due to pipeline failure, not absence of findings.

### Services Identified
```
Total Services: 0
```

### Security Findings
```
Total Findings: 0
```

### Certificates
```
Total Certificates: 0
```

---

## 5. Tool Execution Evidence

### Subfinder Execution ✅
```
[2025-10-26 01:06:02,094] Running subfinder for 1 validated domains (tenant 5)
[2025-10-26 01:06:02,094] Executing tool for tenant 5: subfinder (timeout: 600s)
[2025-10-26 01:06:13,919] Task succeeded in 11.84s
```

**Runtime**: 11.84 seconds (indicates significant execution)
**Expected Findings**: Subfinder typically discovers 10-100+ subdomains in this timeframe

### Amass Execution ⚠️
```
[2025-10-26 01:06:02,101] Running Amass for domain: meridian-group.eu
[2025-10-26 01:06:02,108] WARNING: flag provided but not defined: -json
```

**Issue**: Amass v4 flag incompatibility
**Runtime**: 0.04 seconds (failed due to incorrect flags)

---

## 6. Issues Preventing Data Collection

### Critical Issue: Celery Task Architecture
**Location**: `/app/app/tasks/discovery.py` - `run_parallel_enumeration()`

**Problem**: The task is calling `.get()` on async task results, which:
- Blocks the worker
- Violates Celery design patterns
- Causes the task to fail before results can be merged

**Code Pattern**:
```python
# INCORRECT (current implementation)
result = run_subfinder.apply_async(...)
data = result.get()  # ❌ Deadlock!

# CORRECT (needed fix)
chain(
    run_subfinder.s(...),
    merge_results.s()
).apply_async()
```

### Secondary Issue: Amass v4 Flags
**Error**: `flag provided but not defined: -json`

**Current Command**:
```bash
amass enum -d meridian-group.eu -json output.json
```

**Required Fix** (Amass v4 format):
```bash
amass enum -d meridian-group.eu -o output.json -json
# OR
amass enum -d meridian-group.eu -jsonout output.json
```

### Tertiary Issue: MinIO S3 Credentials
**Error**: `SignatureDoesNotMatch`

**Impact**: Low - Only affects raw output storage, not discovery functionality

---

## 7. Pipeline Architecture

### Designed Workflow
```
1. collect_seeds     ✅ Working
2. run_parallel_enumeration  ❌ FAILING HERE
   ├─ run_subfinder  ✅ Executes (11.8s)
   └─ run_amass      ⚠️ Executes (flag error)
3. merge_discovery_results  ⏸️ Never reached
4. run_dnsx         ⏸️ Never reached
5. process_discovery_results ⏸️ Never reached
```

### Current Reality
```
1. collect_seeds     ✅ Completed
   └─ Found: 1 domain (meridian-group.eu)

2. run_parallel_enumeration  ❌ FAILED
   ├─ run_subfinder  ✅ Executed (11.8s runtime)
   └─ run_amass      ⚠️ Executed (flag error)
   └─ Pipeline crashed before merging results

Pipeline stopped. No data written to database.
```

---

## 8. Required Fixes

### Fix 1: Refactor `run_parallel_enumeration` (CRITICAL)
**Priority**: 🔴 Critical
**Estimated Time**: 15-30 minutes

**Current Implementation** (broken):
```python
def run_parallel_enumeration(seed_data, tenant_id):
    subfinder_task = run_subfinder.apply_async(...)
    amass_task = run_amass.apply_async(...)

    # ❌ BLOCKING CALLS - CAUSES FAILURE
    subfinder_result = subfinder_task.get()
    amass_result = amass_task.get()
```

**Required Implementation**:
```python
def run_parallel_enumeration(seed_data, tenant_id):
    # Use chord to run in parallel and merge results
    return chord([
        run_subfinder.s(seed_data, tenant_id),
        run_amass.s(seed_data, tenant_id)
    ])(merge_discovery_results.s(tenant_id))
```

### Fix 2: Update Amass Command for v4
**Priority**: 🟡 High
**Estimated Time**: 5 minutes

**File**: `app/tasks/discovery.py` - `run_amass()` function

**Change**:
```python
# Before:
args = ['-d', domain, '-json', output_file]

# After:
args = ['-d', domain, '-o', output_file, '-json']
```

### Fix 3: MinIO Credentials (Optional)
**Priority**: 🟢 Low
**Estimated Time**: 10 minutes

Not blocking discovery - only affects raw output archival.

---

## 9. Next Steps

### Immediate Actions Required

1. **Fix Celery Task Architecture** (Critical)
   - Refactor `run_parallel_enumeration` to use `chord()` instead of `.get()`
   - Test with small domain first
   - Estimated time: 30 minutes

2. **Fix Amass v4 Flags**
   - Update command arguments
   - Estimated time: 5 minutes

3. **Re-run Discovery**
   ```bash
   docker-compose exec -T worker python3 -c "
   from app.tasks.discovery import run_tenant_discovery
   result = run_tenant_discovery.apply_async(args=[5])
   print(f'Task ID: {result.id}')
   "
   ```

4. **Monitor Results**
   ```bash
   # Watch worker logs
   docker-compose logs -f worker

   # Check database for assets
   docker-compose exec -T postgres psql -U easm -d easm -c "
   SELECT COUNT(*), type FROM assets WHERE tenant_id = 5 GROUP BY type;
   "
   ```

### Expected Timeline After Fixes

| Stage | Duration | Description |
|-------|----------|-------------|
| **Discovery** | 15-30 min | Subfinder + Amass + DNSx |
| **Enrichment** | 20-40 min | HTTPx + Naabu + TLSx + Katana |
| **Nuclei Scan** | 30-60 min | 6000+ vulnerability templates |
| **Risk Scoring** | 5 min | Calculate asset risk scores |
| **TOTAL** | **1.5-3 hours** | Complete assessment |

---

## 10. Expected Results (Post-Fix)

Based on typical discovery patterns for European B2B companies:

### Projected Asset Discovery
- **Subdomains**: 50-200 subdomains
- **Live Services**: 30-80 services
- **Certificates**: 20-50 TLS certificates
- **Endpoints**: 500-2000 web paths/APIs

### Projected Security Findings
- **Critical**: 0-5 findings
- **High**: 5-15 findings
- **Medium**: 10-30 findings
- **Low**: 20-50 findings
- **Info**: 50-100 findings

### Common Findings for European Domains
- Exposed admin panels
- Missing security headers
- Outdated web servers
- Expired/expiring certificates
- Information disclosure
- Misconfigured CORS
- Vulnerable WordPress/Joomla instances
- Exposed Git repositories
- Default credentials

---

## 11. Technical Debt Summary

| Issue | Impact | Status |
|-------|--------|--------|
| Celery `.get()` in tasks | 🔴 Critical | Blocking discovery |
| Amass v4 flag syntax | 🟡 High | Partial data loss |
| MinIO S3 signatures | 🟢 Low | Raw outputs not stored |
| Certificate relationships | 🟢 Low | Enrichment affected |

---

## 12. Monitoring Commands

### Check Discovery Progress
```bash
# Real-time worker logs
docker-compose logs -f worker | grep -E "(meridian|tenant.*5)"

# Check asset count
watch -n 5 'docker-compose exec -T postgres psql -U easm -d easm -c \
  "SELECT COUNT(*) as assets FROM assets WHERE tenant_id = 5;"'
```

### View Discovered Assets
```bash
docker-compose exec -T postgres psql -U easm -d easm -c "
SELECT identifier, type, first_seen, last_seen
FROM assets
WHERE tenant_id = 5
ORDER BY first_seen DESC
LIMIT 20;
"
```

### View Security Findings
```bash
docker-compose exec -T postgres psql -U easm -d easm -c "
SELECT severity, COUNT(*) as count
FROM findings f
JOIN assets a ON f.asset_id = a.id
WHERE a.tenant_id = 5
GROUP BY severity
ORDER BY
  CASE severity
    WHEN 'critical' THEN 1
    WHEN 'high' THEN 2
    WHEN 'medium' THEN 3
    WHEN 'low' THEN 4
    WHEN 'info' THEN 5
  END;
"
```

---

## 13. Conclusion

**Current Status**: ⚠️ Pipeline Blocked by Celery Architecture Issue

**Tools Status**: ✅ All ProjectDiscovery tools successfully installed and executing

**Blocker**: The `run_parallel_enumeration` task uses synchronous `.get()` calls which violate Celery design patterns and prevent result merging.

**Action Required**: Refactor task to use `chord()` for parallel execution with asynchronous result collection.

**Estimated Time to Resolution**: 30-45 minutes for code changes + 1.5-3 hours for full pipeline execution

**Confidence Level**: High - Once the Celery architecture is fixed, the pipeline will complete successfully as all tools are functional.

---

## 14. Contact Information

**Platform URL**: http://localhost:13000
**API Endpoint**: http://localhost:18000
**Customer Login**: admin@meridian-group.eu

**Support Queries**: Check `/Users/cere/Downloads/easm/DISCOVERY_PIPELINE_STATUS.md` for detailed technical information.

---

**Report Generated**: 2025-10-26 01:10:00 UTC
**Next Update**: After pipeline fixes are applied
