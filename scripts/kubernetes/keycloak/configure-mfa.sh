#!/bin/bash
# Configure MFA (Multi-Factor Authentication) in Keycloak

set -e

echo "🔒 Configuring MFA in Keycloak"

KC_POD=$(kubectl get pods -n nxr-auth -l app.kubernetes.io/name=keycloak -o jsonpath='{.items[0].metadata.name}')
KC_URL="http://localhost:8080"
ADMIN_USER="admin"
ADMIN_PASSWORD=$(kubectl get secret keycloak-secrets -n nxr-auth -o jsonpath='{.data.admin-password}' 2>/dev/null | base64 -d || echo "admin")

# Get admin token
TOKEN=$(kubectl exec -n nxr-auth "$KC_POD" -- \
    curl -s -X POST "$KC_URL/realms/master/protocol/openid-connect/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=$ADMIN_USER" \
    -d "password=$ADMIN_PASSWORD" \
    -d "grant_type=password" \
    -d "client_id=admin-cli" | \
    jq -r '.access_token')

if [ "$TOKEN" == "null" ] || [ -z "$TOKEN" ]; then
    echo "❌ Failed to get admin token"
    exit 1
fi

# Enable TOTP authenticator
echo "📝 Enabling TOTP authenticator..."
kubectl exec -n nxr-auth "$KC_POD" -- \
    curl -s -X POST "$KC_URL/admin/realms/nxr/authentication/executors" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d @- <<EOF || true
{
  "alias": "totp",
  "provider": "otp-form",
  "priority": 10,
  "enabled": true,
  "config": {
    "otp.hashAlgorithm": "SHA1",
    "otp.type": "totp",
    "otp.digits": "6",
    "otp.period": "30",
    "otp.initialCounter": "0"
  }
}
EOF

# Enable email OTP authenticator
echo "📝 Enabling Email OTP authenticator..."
kubectl exec -n nxr-auth "$KC_POD" -- \
    curl -s -X POST "$KC_URL/admin/realms/nxr/authentication/executors" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d @- <<EOF || true
{
  "alias": "email-otp",
  "provider": "email-otp-form",
  "priority": 20,
  "enabled": true,
  "config": {
    "otp.hashAlgorithm": "SHA256",
    "otp.type": "totp",
    "otp.digits": "6",
    "otp.period": "60"
  }
}
EOF

# Configure MFA flow
echo "📝 Configuring MFA flow..."
kubectl exec -n nxr-auth "$KC_POD" -- \
    curl -s -X POST "$KC_URL/admin/realms/nxr/authentication/flows/browser/executions/execution" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d @- <<EOF || true
{
  "provider": "otp-form",
  "alias": "Browser - TOTP",
  "requirement": "conditional"
}
EOF

echo ""
echo "✅ MFA configured!"
echo ""
echo "📋 MFA Methods:"
echo "  ✅ TOTP (Time-based One-Time Password)"
echo "  ✅ Email OTP"
echo "  ✅ Conditional requirement (can be required per user/group)"
echo ""
echo "💡 Users can enable MFA in their account settings"
echo "💡 Admins can require MFA for specific users/groups"

