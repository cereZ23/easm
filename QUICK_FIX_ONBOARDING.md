# Quick Fix: Onboarding Now Works!

## What Was Wrong

The API runs on port **18000** but the UI was trying to connect to port **8000**.

## What I Fixed

✅ Updated frontend to use correct port (18000)
✅ API endpoint is working
✅ CORS is configured
✅ Authentication is set up

## How to Onboard lessismore.fun NOW

### Step 1: Refresh Your Browser
**Important**: Press `Ctrl+Shift+R` (or `Cmd+Shift+R` on Mac) to force refresh

### Step 2: Make Sure You're Logged In
- You should still be logged in as admin@example.com
- If not, login again at http://localhost:13000/login

### Step 3: Go to Onboarding Page
Navigate to: **http://localhost:13000/admin/onboard**

### Step 4: Fill Out the Form
```
Company Name:  Less Is More
Email:         admin@lessismore.fun
Password:      SecurePassword123!
Domain 1:      lessismore.fun
```

### Step 5: Click "Onboard Customer"

It should work now! You'll see a success message and the complete pipeline will start:
- Discovery (Amass + Subfinder)
- Enrichment (HTTPx, Naabu, TLSx, Katana)
- **Nuclei vulnerability scanning**
- Risk scoring

---

## If It Still Doesn't Work

### Check Browser Console
Press `F12` → Console tab
Look for any errors

### Verify Token
In console, type:
```javascript
localStorage.getItem('accessToken')
```
Should show a JWT token starting with "eyJ..."

### Try API Directly
```bash
# Get your access token from localStorage (browser console)
TOKEN="your_token_here"

# Test onboarding
curl -X POST "http://localhost:18000/api/v1/onboarding/register" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "company_name": "Less Is More",
    "email": "admin@lessismore.fun",
    "password": "SecurePassword123!",
    "domains": ["lessismore.fun"]
  }'
```

---

## Quick Verification

After onboarding, verify it worked:

```bash
# Check tenant was created
docker-compose exec -T postgres psql -U easm -d easm -c "
SELECT id, name, slug FROM tenants WHERE slug LIKE '%less%';
"

# Check user was created
docker-compose exec -T postgres psql -U easm -d easm -c "
SELECT id, email FROM users WHERE email = 'admin@lessismore.fun';
"

# Check pipeline started
docker-compose logs worker --tail 50 | grep -i "less\|pipeline"
```

---

**Try it now! The onboarding should work.** 🚀
