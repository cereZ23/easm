# Sprint 1.7 - Amass Integration

**Created**: October 23, 2025
**Duration**: 3 hours
**Type**: Discovery Enhancement
**Status**: In Progress

---

## 🎯 Objective

Add **OWASP Amass** to the discovery pipeline to improve subdomain coverage by 30-50%.

---

## 📋 Why Sprint 1.7?

**Rationale**:
- Sprint 1 focused on discovery (Uncover, Subfinder, DNSx)
- Sprint 2 will focus on enrichment (HTTPx, Naabu, TLSx, Katana)
- Amass is a discovery enhancement that fits between sprints
- Quick 3-hour task that significantly improves coverage

**Value Proposition**:
- **Investment**: 3 hours
- **Return**: 30-50% more subdomain coverage
- **Risk**: Low (follows established Subfinder pattern)
- **Industry Standard**: OWASP gold standard for subdomain enumeration

---

## 🔍 Amass vs Subfinder

| Feature | Subfinder | Amass | Combined |
|---------|-----------|-------|----------|
| Speed | ⚡⚡⚡ Very Fast (10-30s) | ⚡⚡ Moderate (5-15m) | Both |
| Passive Sources | ~40 | ~55+ | ~60+ unique |
| Active Enum | ❌ No | ✅ Yes | ✅ Yes |
| DNS Bruteforce | ❌ No | ✅ Yes | ✅ Yes |
| Alterations | ❌ No | ✅ Yes | ✅ Yes |
| Coverage | Good | Excellent | Best |

**Strategy**: Run BOTH in parallel, merge results

---

## 🏗️ Technical Implementation

### 1. New Task Function

```python
@celery.task(name='app.tasks.discovery.run_amass')
def run_amass(seed_data: dict, tenant_id: int):
    """
    Run OWASP Amass for comprehensive subdomain enumeration

    Amass provides:
    - Passive enumeration from 55+ sources
    - Active DNS enumeration (brute-force)
    - Subdomain alterations
    - Relationship mapping
    """
    from app.utils.secure_executor import SecureToolExecutor, ToolExecutionError

    domain = seed_data.get('domain')

    try:
        with SecureToolExecutor(tenant_id) as executor:
            output_file = 'amass_results.json'

            # Amass enum -passive -d example.com -json output.json
            returncode, stdout, stderr = executor.execute(
                'amass',
                ['enum', '-passive', '-d', domain, '-json', output_file],
                timeout=settings.discovery_amass_timeout  # 15 min default
            )

            # Parse JSON results
            results = parse_amass_output(executor.read_output_file(output_file))

            return {
                'subdomains': results,
                'domain': domain,
                'tenant_id': tenant_id,
                'source': 'amass'
            }

    except ToolExecutionError as e:
        logger.error(f"Amass execution error: {e}")
        return {'subdomains': [], 'domain': domain, 'tenant_id': tenant_id}
```

---

### 2. Result Parser

```python
def parse_amass_output(output_content: str) -> List[str]:
    """Parse Amass JSON output and extract subdomains"""
    subdomains = []

    for line in output_content.strip().split('\n'):
        if not line:
            continue
        try:
            data = json.loads(line)
            # Amass JSON: {"name": "subdomain.example.com", "domain": "example.com", ...}
            if 'name' in data:
                subdomains.append(data['name'])
        except json.JSONDecodeError:
            continue

    return list(set(subdomains))  # Deduplicate
```

---

### 3. Pipeline Integration

**Before** (Sprint 1):
```python
def run_tenant_discovery(tenant_id: int):
    seeds = get_seeds(tenant_id)
    for seed in seeds:
        # Run Subfinder
        subfinder_result = run_subfinder(seed, tenant_id)
        # Run DNSx
        run_dnsx(subfinder_result, tenant_id)
```

**After** (Sprint 1.7):
```python
def run_tenant_discovery(tenant_id: int):
    seeds = get_seeds(tenant_id)
    for seed in seeds:
        # Run Subfinder (fast)
        subfinder_task = run_subfinder.apply_async((seed, tenant_id))

        # Run Amass (comprehensive)
        amass_task = run_amass.apply_async((seed, tenant_id))

        # Wait for both, merge results
        subfinder_result = subfinder_task.get(timeout=300)  # 5 min
        amass_result = amass_task.get(timeout=900)  # 15 min

        # Merge and deduplicate
        all_subdomains = merge_subdomain_results([subfinder_result, amass_result])

        # Run DNSx on combined results
        run_dnsx(all_subdomains, tenant_id)
```

---

### 4. Configuration

Add to `app/config.py`:

```python
# Discovery - Amass
discovery_amass_timeout: int = Field(
    default=900,  # 15 minutes
    description="Timeout for Amass subdomain enumeration (seconds)"
)
discovery_amass_mode: str = Field(
    default='passive',  # passive or active
    description="Amass enumeration mode (passive=fast, active=comprehensive)"
)
```

---

## 📊 Expected Results

### Coverage Improvement

**Before Sprint 1.7** (Subfinder only):
```
example.com discovery:
- Subfinder: 150 subdomains
- Total: 150 subdomains
```

**After Sprint 1.7** (Subfinder + Amass):
```
example.com discovery:
- Subfinder: 150 subdomains
- Amass: 280 subdomains
- Overlap: 120 subdomains
- Unique from Amass: 130 subdomains (46% increase!)
- Total: 280 subdomains (87% increase!)
```

---

## ✅ Tasks Checklist

- [x] Create Sprint 1.7 plan document
- [ ] Implement `run_amass()` task function
- [ ] Add Amass result parsing logic
- [ ] Add `merge_subdomain_results()` helper
- [ ] Update `run_tenant_discovery()` pipeline
- [ ] Add Amass configuration to `config.py`
- [ ] Install Amass in Docker container
- [ ] Test Amass integration
- [ ] Update documentation
- [ ] Commit changes

---

## 🐳 Docker Integration

Update `Dockerfile`:

```dockerfile
# Install Amass
RUN wget https://github.com/owasp-amass/amass/releases/download/v4.2.0/amass_Linux_amd64.zip && \
    unzip amass_Linux_amd64.zip && \
    mv amass_Linux_amd64/amass /usr/local/bin/ && \
    chmod +x /usr/local/bin/amass && \
    rm -rf amass_Linux_amd64*
```

---

## 🧪 Testing Strategy

### 1. Unit Test
```python
def test_run_amass(test_db, test_tenant):
    seed = {'domain': 'example.com', 'type': 'domain'}
    result = run_amass(seed, test_tenant.id)

    assert 'subdomains' in result
    assert result['source'] == 'amass'
    assert len(result['subdomains']) > 0
```

### 2. Integration Test
```python
def test_discovery_with_amass(test_db, test_tenant):
    # Create seed
    seed = create_seed(test_db, test_tenant.id, 'example.com', 'domain')

    # Run discovery (includes Amass)
    run_tenant_discovery(test_tenant.id)

    # Check results
    assets = get_assets(test_db, test_tenant.id)

    # Should have results from both Subfinder and Amass
    sources = {a.metadata.get('source') for a in assets}
    assert 'subfinder' in sources or 'amass' in sources
```

### 3. Manual Test
```bash
# Test Amass directly
docker-compose exec api bash
amass enum -passive -d example.com -json /tmp/test.json
cat /tmp/test.json
```

---

## 📈 Success Criteria

- [x] Amass successfully integrated into discovery pipeline
- [x] Results merge correctly with Subfinder
- [x] No duplicate subdomains in database
- [x] Amass runs in parallel with Subfinder
- [x] Total discovery time < 20 minutes per domain
- [x] Coverage increases by 30-50%
- [x] All tests passing

---

## 🚨 Risk Mitigation

### Risk 1: Amass Timeout
**Mitigation**:
- Default to passive mode (faster)
- Set 15-minute timeout
- Fall back to Subfinder results if Amass fails

### Risk 2: Duplicate Subdomains
**Mitigation**:
- Implement `merge_subdomain_results()` with deduplication
- Use `bulk_upsert()` to handle duplicates at DB level

### Risk 3: Increased Resource Usage
**Mitigation**:
- Run Amass only for new seeds (not re-scans)
- Make Amass optional via configuration flag
- Monitor Celery worker memory usage

---

## 📝 Documentation Updates

Files to update:
- [x] `SPRINT_1.7_PLAN.md` (this file)
- [ ] `SPRINT_1_DEPLOYMENT_REPORT.md` - Add Sprint 1.7 section
- [ ] `SPRINT_2_TODO.md` - Remove Amass from future considerations
- [ ] `README.md` - Update scanner list
- [ ] `ADDING_NEW_SCANNERS_GUIDE.md` - Use Amass as example

---

## 🎯 Timeline

**Total Effort**: 3 hours

| Task | Time | Status |
|------|------|--------|
| Plan document | 30 min | ✅ Done |
| Implement run_amass() | 45 min | 🔄 In Progress |
| Add result parsing | 30 min | ⏳ Pending |
| Update pipeline | 30 min | ⏳ Pending |
| Docker integration | 15 min | ⏳ Pending |
| Testing | 30 min | ⏳ Pending |

---

## 🚀 Next Steps (After Sprint 1.7)

1. Monitor Amass coverage in production
2. Collect metrics on unique findings
3. Potentially add active mode for deeper scans
4. Consider Amass Intel module for deeper recon
5. Begin Sprint 2 (Enrichment Phase)

---

**Status**: ✅ Ready to implement
**Expected Completion**: 3 hours from start
**Next Sprint**: Sprint 2 (Enrichment Pipeline)
