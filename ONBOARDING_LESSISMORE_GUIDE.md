# How to Onboard lessismore.fun Using the UI

**Complete Step-by-Step Guide**

---

## Quick Start (2 Minutes)

### Step 1: Login as Admin

1. Open browser: **http://localhost:13000**
2. Login with admin credentials:
   - Email: `admin@example.com`
   - Password: `admin123`

### Step 2: Navigate to Onboarding Page

Go to: **http://localhost:13000/admin/onboard**

Or manually navigate in the UI (once we add a menu link).

### Step 3: Fill Out the Form

```
Company Name:  Less Is More
Email:         admin@lessismore.fun
Password:      SecurePassword123!  (customer will use this to login)
Domain 1:      lessismore.fun
```

### Step 4: Click "Onboard Customer"

The system will:
- Create tenant "Less Is More"
- Create user account for admin@lessismore.fun
- Add lessismore.fun as a seed domain
- Trigger initial scan (Amass + Subfinder + HTTPx + Naabu + TLSx)
- Show success message

### Step 5: Customer Can Now Login

Send these credentials to the customer:
```
URL:      http://localhost:13000
Email:    admin@lessismore.fun
Password: SecurePassword123!
```

---

## What Happens Automatically

### Immediately:
- ✅ Tenant created in database
- ✅ User account created
- ✅ Domain added to seeds table
- ✅ Celery task triggered for discovery

### Within 1-2 Hours:
- 🔄 Amass discovers subdomains (30-45 min)
- 🔄 Subfinder discovers subdomains (15-20 min)
- 🔄 DNSx resolves all domains (5 min)
- 🔄 HTTPx probes web services (10 min)
- 🔄 Naabu scans ports (15 min)
- 🔄 TLSx analyzes certificates (5 min)
- ✅ Data appears in UI

---

## Customer's First Login Experience

### What They See:

```
1. Login page → Enter credentials
2. Dashboard loads with:
   - "Scan in progress" message
   - Progress bar
   - Estimated completion time
3. After scan completes:
   - Full dashboard with discovered assets
   - Services list
   - Certificates
   - Risk scores
```

---

## Complete Walkthrough with Screenshots

### 1. Admin Login

```
┌─────────────────────────────────────────────────┐
│                                                  │
│            🔒 EASM Platform                     │
│     External Attack Surface Management          │
│                                                  │
│  ┌────────────────────────────────────────┐    │
│  │ Email: admin@example.com               │    │
│  │ Password: admin123                     │    │
│  │                                         │    │
│  │        [ Sign In ]                      │    │
│  └────────────────────────────────────────┘    │
└─────────────────────────────────────────────────┘
```

### 2. Onboarding Page

Navigate to: **http://localhost:13000/admin/onboard**

```
┌─────────────────────────────────────────────────────────────┐
│ Onboard New Customer                                        │
│ Add a new organization to the EASM platform                 │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ Company Name:                                                │
│ ┌────────────────────────────────────────┐                 │
│ │ Less Is More                           │                 │
│ └────────────────────────────────────────┘                 │
│                                                              │
│ Customer Admin Email:                                        │
│ ┌────────────────────────────────────────┐                 │
│ │ admin@lessismore.fun                   │                 │
│ └────────────────────────────────────────┘                 │
│ This will be the customer's login email                     │
│                                                              │
│ Initial Password:                                            │
│ ┌────────────────────────────────────────┐                 │
│ │ SecurePassword123!                     │                 │
│ └────────────────────────────────────────┘                 │
│ Share this with the customer                                 │
│                                                              │
│ Domains to Monitor:                                          │
│ Enter root domains (e.g., example.com)                      │
│                                                              │
│ ┌────────────────────────────────────────┐                 │
│ │ lessismore.fun                         │ [Remove]        │
│ └────────────────────────────────────────┘                 │
│                                                              │
│ [+ Add Another Domain]                                       │
│                                                              │
│                                                              │
│                      [Reset]  [Onboard Customer]            │
│                                                              │
├─────────────────────────────────────────────────────────────┤
│ ℹ️ What happens after onboarding?                           │
│ • Customer account and tenant are created immediately       │
│ • Initial reconnaissance scan starts automatically (1-2 hrs)│
│ • Customer can log in with the email and password provided  │
│ • Send the login credentials to the customer securely       │
└─────────────────────────────────────────────────────────────┘
```

### 3. Success Message

After clicking "Onboard Customer":

```
┌─────────────────────────────────────────────────────────────┐
│ ✅ Customer onboarded successfully!                         │
│                                                              │
│ Successfully registered Less Is More! Your initial scan has │
│ been started and will complete in 1-2 hours.                │
│                                                              │
│ The customer can now log in and their initial scan is       │
│ running.                                                     │
└─────────────────────────────────────────────────────────────┘
```

---

## Send Welcome Email to Customer

**Template:**

```
Subject: Welcome to EASM Platform - Your Account is Ready

Hi Less Is More Team,

Your EASM Platform account has been created! Here are your login credentials:

🔗 URL: http://localhost:13000  (or your production URL)
📧 Email: admin@lessismore.fun
🔑 Password: SecurePassword123!

⚠️ IMPORTANT: Please change your password after first login.

🔍 What's Happening Now:
We've started an initial scan of lessismore.fun. This will discover:
- All subdomains
- Web services and technologies
- Open ports
- TLS certificates
- Potential vulnerabilities

The scan will complete in 1-2 hours. You can log in now to see the progress.

📊 What You'll See:
- Real-time dashboard with attack surface overview
- List of all discovered assets
- Risk scoring for each asset
- Certificate expiration monitoring
- Vulnerability findings

Need help? Reply to this email or contact support@yourcompany.com

Best regards,
EASM Platform Team
```

---

## Verify Onboarding Worked

### Check Database:

```bash
# Check tenant was created
docker-compose exec -T postgres psql -U easm -d easm -c "
SELECT id, name, slug FROM tenants WHERE slug = 'less-is-more';
"

# Check user was created
docker-compose exec -T postgres psql -U easm -d easm -c "
SELECT id, email, username FROM users WHERE email = 'admin@lessismore.fun';
"

# Check domain was added
docker-compose exec -T postgres psql -U easm -d easm -c "
SELECT tenant_id, type, value, enabled FROM seeds WHERE value = 'lessismore.fun';
"

# Check scan task was triggered
docker-compose logs worker --tail 50 | grep lessismore
```

### Check Celery Worker:

```bash
# View active tasks
docker-compose exec -T worker celery -A app.celery_app inspect active

# View worker logs
docker-compose logs -f worker
```

You should see:
```
[timestamp] Starting full discovery for tenant X
[timestamp] Running Amass for lessismore.fun
[timestamp] Running Subfinder for lessismore.fun
```

---

## Troubleshooting

### Problem: "You must be an admin to onboard customers"

**Solution:**
Your user account is not an admin. Update it:

```bash
docker-compose exec -T postgres psql -U easm -d easm -c "
UPDATE users SET is_superuser = true WHERE username = 'admin';
"
```

Then log out and log back in.

### Problem: Form doesn't submit

**Check browser console** (F12 → Console tab):
- Look for errors
- Check if API is running: `curl http://localhost:8000/health`
- Check API logs: `docker-compose logs api --tail 50`

### Problem: "Email address already registered"

**Solution:**
That email is already in use. Either:
1. Use a different email
2. Delete the existing user:
```bash
docker-compose exec -T postgres psql -U easm -d easm -c "
DELETE FROM users WHERE email = 'admin@lessismore.fun';
"
```

### Problem: Scan doesn't start

**Check worker**:
```bash
# Is worker running?
docker-compose ps | grep worker

# Check worker logs
docker-compose logs worker --tail 100

# Restart worker
docker-compose restart worker
```

---

## Add More Domains Later

If customer wants to add more domains after onboarding:

### Option 1: Via Database (Quick)
```bash
TENANT_ID=3  # Use the actual tenant ID

docker-compose exec -T postgres psql -U easm -d easm << EOF
INSERT INTO seeds (tenant_id, type, value, enabled, created_at, updated_at)
VALUES ($TENANT_ID, 'domain', 'lessismore.io', true, NOW(), NOW());
EOF

# Trigger new scan
curl -X POST "http://localhost:8000/api/v1/tenants/${TENANT_ID}/scans/trigger" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -d '{"scan_type": "full_discovery"}'
```

### Option 2: Build Domain Management UI (Future)
Add a "Manage Domains" page where admins can add/remove domains.

---

## Current Limitations

### What's NOT in the UI Yet:
- ❌ Navigation menu link to onboarding page (must manually go to /admin/onboard)
- ❌ List of all onboarded customers
- ❌ Edit customer details
- ❌ View customer's scan status
- ❌ Trigger manual scans from UI
- ❌ Add more domains after onboarding
- ❌ Delete/disable customers

### Workarounds:
- Access onboarding directly: http://localhost:13000/admin/onboard
- View customers via database or API
- Trigger scans via API endpoints
- Manage domains via database

---

## Next Steps for Production

To make this production-ready, you need to build:

1. **Navigation Menu** - Add "Onboard Customer" link in nav bar
2. **Customer List Page** - View all onboarded customers
3. **Customer Detail Page** - View/edit customer details
4. **Scan Status Dashboard** - See which scans are running
5. **Domain Management** - Add/remove domains per customer
6. **Welcome Email Automation** - Send credentials automatically
7. **API Key Generation** - Provide customers with API keys

---

## Summary

**You can now onboard customers through the UI!**

✅ **What Works:**
- Admin-only onboarding form
- Creates tenant + user + domains
- Triggers automatic scan
- Form validation
- Success/error messages

⏱️ **Time to Onboard:** 2 minutes manual work + 1-2 hours automated scanning

🎯 **Result:** Customer gets a fully functional account with all their assets discovered and monitored.

**URL to bookmark:** http://localhost:13000/admin/onboard

---

Ready to onboard lessismore.fun? Just navigate to the onboarding page and fill out the form! 🚀
