#!/bin/bash
# Reset EASM UI admin password to "admin123"

echo "🔑 Resetting admin password for EASM Platform UI..."
echo ""

# Reset password (bcrypt hash for "admin123")
docker-compose exec -T postgres psql -U easm -d easm -c "
UPDATE users
SET hashed_password = '\$2b\$12\$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyKcpZL0m0K6'
WHERE username = 'admin';
" > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo "✅ Password reset successful!"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  EASM Platform - UI Login Credentials"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "  URL:      http://localhost:13000"
    echo "  Email:    admin@example.com"
    echo "  Password: admin123"
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "⚠️  IMPORTANT: Change this password after first login!"
    echo ""
    echo "Opening UI in browser..."
    sleep 2

    # Try to open in browser
    if command -v open > /dev/null 2>&1; then
        open http://localhost:13000
    elif command -v xdg-open > /dev/null 2>&1; then
        xdg-open http://localhost:13000
    else
        echo "✋ Please open http://localhost:13000 in your browser manually"
    fi
else
    echo "❌ Failed to reset password"
    echo "Please ensure PostgreSQL container is running:"
    echo "  docker-compose ps | grep postgres"
    exit 1
fi
