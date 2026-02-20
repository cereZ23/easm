# ✅ Onboarding Is Ready!

## What I Fixed:

1. ✅ Port issue (8000 → 18000)
2. ✅ Username conflict (auto-increments: admin1, admin2, etc.)
3. ✅ Certificate model error (fixed imports and restart)

## 🚀 Onboard lessismore.fun NOW:

### Step 1: Go to Onboarding Page
http://localhost:13000/admin/onboard

### Step 2: Fill the Form
```
Company Name:  Less Is More
Email:         admin@lessismore.fun
Password:      SecurePassword123!
Domain:        lessismore.fun
```

### Step 3: Click "Onboard Customer"

### Step 4: Wait for Success Message
You'll see:
```
✅ Customer onboarded successfully!

Successfully registered Less Is More! Your initial scan has
been started and will complete in 1-2 hours.
```

---

## What Happens Next (Automatically):

### Stage 1: Discovery (30-60 min)
```
🔄 Amass + Subfinder discovering subdomains...
🔄 DNSx resolving domains...
✅ ~50-500 subdomains discovered
```

### Stage 2: Enrichment (20-40 min)
```
🔄 HTTPx probing web services...
🔄 Naabu scanning ports...
🔄 TLSx analyzing certificates...
🔄 Katana crawling websites...
✅ ~100-200 services, ~50-100 certs, ~500-2000 endpoints
```

### Stage 3: Nuclei Scanning (30-60 min)
```
🔄 Nuclei scanning with 6000+ templates...
🔄 Checking for CVEs, misconfigurations, exposed panels...
✅ ~30-100 findings discovered
```

### Stage 4: Risk Scoring (5 min)
```
🔄 Calculating risk scores...
✅ All assets scored (0-100 scale)
```

**Total Time: 1.5-3 hours**

---

## Monitor Progress:

### Check Worker Logs:
```bash
docker-compose logs -f worker
```

### Check Database:
```bash
# Check assets discovered
docker-compose exec -T postgres psql -U easm -d easm -c "
SELECT COUNT(*) as total_assets
FROM assets a
JOIN tenants t ON a.tenant_id = t.id
WHERE t.name = 'Less Is More';
"

# Check findings
docker-compose exec -T postgres psql -U easm -d easm -c "
SELECT severity, COUNT(*) as count
FROM findings f
JOIN assets a ON f.asset_id = a.id
JOIN tenants t ON a.tenant_id = t.id
WHERE t.name = 'Less Is More'
GROUP BY severity;
"
```

---

## Customer Login (After Onboarding):

Send these credentials to customer:

```
URL:      http://localhost:13000
Email:    admin@lessismore.fun
Password: SecurePassword123!

Please change your password after first login.
```

They'll see:
- 🔄 "Scan in progress..." message initially
- ⏳ Progress updates as stages complete
- ✅ Full dashboard with all discoveries after 1.5-3 hours

---

## ✅ Everything Is Fixed and Ready!

Just go to http://localhost:13000/admin/onboard and fill out the form!

The complete 4-stage pipeline will run automatically:
1. Discovery (Amass + Subfinder + DNSx)
2. Enrichment (HTTPx + Naabu + TLSx + Katana)
3. **Nuclei vulnerability scanning** (6000+ templates)
4. Risk scoring (0-100 scale)

🎯 **Try it now!**
