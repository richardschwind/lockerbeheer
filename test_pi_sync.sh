#!/bin/bash
# Pi Sync - Curl Test Examples

# Variabelen
DJANGO_URL="http://localhost:8000"
PI_API_KEY="pi_1_dJgxeoSrIYe5ZuMOd8q6Y_oCeZO2pTerpsqaOKMYjqY"  # Vervang met je eigen Pi API key

echo "═══════════════════════════════════════"
echo "Pi Sync - Curl Test Examples"
echo "═══════════════════════════════════════"
echo ""

# Test 1: List alle Pi's
echo "[1] GET /api/devices/raspberry-pis/"
echo "    (Pas JWT token aan of gebruik Pi API key)"
echo ""
curl -s -H "X-PI-KEY: $PI_API_KEY" \
  "$DJANGO_URL/api/devices/raspberry-pis/" | python -m json.tool
echo ""
echo ""

# Test 2: List access events
echo "[2] GET /api/devices/access-events/"
echo ""
curl -s -H "X-PI-KEY: $PI_API_KEY" \
  "$DJANGO_URL/api/devices/access-events/" | python -m json.tool
echo ""
echo ""

# Test 3: POST single event
echo "[3] POST /api/devices/pi-sync/sync/ (single event)"
echo ""
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
curl -s -X POST \
  -H "X-PI-KEY: $PI_API_KEY" \
  -H "Content-Type: application/json" \
  -d @- "$DJANGO_URL/api/devices/pi-sync/sync/" <<EOF
{
  "events": [
    {
      "locker_number": 5,
      "credential_type": "nfc",
      "credential_value": "DEADBEEF5555",
      "success": true,
      "message": "NFC geldig",
      "timestamp": "$TIMESTAMP"
    }
  ]
}
EOF
echo ""
echo ""

# Test 4: POST multiple events (batch)
echo "[4] POST /api/devices/pi-sync/sync/ (batch)"
echo ""
TIMESTAMP1=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
TIMESTAMP2=$(date -u -d "-1 minute" +"%Y-%m-%dT%H:%M:%SZ")
TIMESTAMP3=$(date -u -d "-2 minutes" +"%Y-%m-%dT%H:%M:%SZ")
curl -s -X POST \
  -H "X-PI-KEY: $PI_API_KEY" \
  -H "Content-Type: application/json" \
  -d @- "$DJANGO_URL/api/devices/pi-sync/sync/" <<EOF
{
  "events": [
    {
      "locker_number": 1,
      "credential_type": "nfc",
      "credential_value": "AAAA0001",
      "success": true,
      "message": "OK",
      "timestamp": "$TIMESTAMP1"
    },
    {
      "locker_number": 2,
      "credential_type": "pin",
      "credential_value": "9999",
      "success": false,
      "message": "Pincode onjuist",
      "timestamp": "$TIMESTAMP2"
    },
    {
      "locker_number": 3,
      "credential_type": "nfc",
      "credential_value": "CCCC0003",
      "success": true,
      "message": "OK",
      "timestamp": "$TIMESTAMP3"
    }
  ]
}
EOF
echo ""
echo ""

echo "═══════════════════════════════════════"
echo "Tests complete!"
echo ""
