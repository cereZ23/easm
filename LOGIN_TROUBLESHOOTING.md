# EASM Platform Login Troubleshooting

## ✅ Credentials

**URL:** http://localhost:13000
**Email:** `admin@example.com`
**Password:** `easm2024`

## 🔍 If Login Fails - Try These Steps:

### Step 1: Check Browser Console
1. Open the browser console (F12 or right-click → Inspect)
2. Go to the **Console** tab
3. Try to login
4. Look for any error messages (red text)
5. Common errors:
   - `Network Error` - Can't reach API
   - `CORS error` - Cross-origin issue
   - `401 Unauthorized` - Wrong credentials

### Step 2: Verify API is Accessible
Open this URL in your browser: http://localhost:18000/health

**Expected response:**
```json
{
  "status": "healthy",
  "services": {
    "database": {"status": "connected"},
    "redis": {"status": "connected"},
    "minio": {"status": "connected"}
  }
}
```

If you **can't** access this URL:
- The API container might not be running
- Port 18000 might be blocked
- Run: `docker-compose ps` to check containers

### Step 3: Check All Containers Are Running
```bash
docker-compose ps
```

**Expected output:**
```
easm-ui         Up    localhost:13000
easm-api        Up    localhost:18000
easm-postgres   Up    (healthy)
easm-redis      Up    (healthy)
easm-minio      Up    (healthy)
```

If any container is not running:
```bash
docker-compose up -d
```

### Step 4: Test Login from Command Line
```bash
curl -X POST http://localhost:18000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"easm2024"}'
```

**Expected:** You should see a JSON response with `access_token` and `user` data.

If this works but UI doesn't:
- It's a frontend issue
- Check browser console for errors
- The UI might be trying to connect to the wrong URL

### Step 5: Restart All Services
```bash
docker-compose down
docker-compose up -d
```

Wait 30 seconds, then try again at http://localhost:13000

### Step 6: Check UI Logs
```bash
docker-compose logs ui --tail 50
```

Look for any errors related to:
- Vite errors
- Network connection errors
- API endpoint errors

### Step 7: Check API Logs
```bash
docker-compose logs api --tail 50
```

Look for:
- Login attempts (should show `POST /api/v1/auth/login`)
- Any 4xx or 5xx errors

## 🐛 Common Issues

### Issue: "Login failed" message with no details
**Cause:** Frontend can't reach the API
**Fix:**
1. Verify http://localhost:18000/health works in browser
2. Check browser console for network errors
3. Ensure you're not behind a firewall blocking port 18000

### Issue: CORS error in browser console
**Cause:** Browser blocking cross-origin requests
**Fix:** This should already be configured, but if you see this:
```bash
docker-compose restart api
```

### Issue: "Invalid email or password"
**Cause:** Credentials are incorrect
**Try:**
- Email: `admin@example.com` (no typos!)
- Password: `easm2024` (lowercase, no spaces)

### Issue: Blank page after login
**Cause:** Dashboard route not loading
**Fix:** Refresh the page (Ctrl+R or Cmd+R)

## 🔄 Nuclear Option - Full Reset

If nothing works, reset everything:

```bash
# Stop all containers
docker-compose down

# Remove the user (we'll recreate)
docker-compose up -d postgres
sleep 5

# Recreate user
docker-compose exec postgres psql -U easm -d easm -c "
DELETE FROM users;
INSERT INTO users (email, username, hashed_password, full_name, is_active, is_superuser, created_at)
VALUES ('admin@example.com', 'admin', '\$2b\$12\$v4pAOydjSL2Msfz4wxE9LuCUV8Vpz1PIevvxSqk/AJZBV/538pUuO', 'EASM Admin', true, true, NOW());
"

# Start all services
docker-compose up -d

# Wait for everything to be ready
sleep 20

# Try login
```

## 📞 Quick Test Commands

Test if API is reachable:
```bash
curl http://localhost:18000/health
```

Test login:
```bash
curl -X POST http://localhost:18000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"easm2024"}' | jq
```

Check user exists:
```bash
docker-compose exec postgres psql -U easm -d easm -c "SELECT email FROM users;"
```

## ✅ Success Indicators

Login is successful if:
1. No error message appears on login form
2. Page redirects to dashboard (http://localhost:13000/)
3. You see the navigation bar with "Dashboard", "Assets", "Findings", "Certificates"
4. Top-right shows "admin@example.com" with logout button

## 🎯 What Should Happen

1. Enter email and password
2. Click "Sign in" button
3. Brief loading state (button says "Signing in...")
4. Redirect to dashboard
5. See stats cards and navigation

If this doesn't happen, follow the troubleshooting steps above!
