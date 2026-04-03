# Pi Sync Systeem - Documentatie

## Overview

Dit systeem stelt Raspberry Pi's in staat om **autonoom access-events lokaal op te slaan** en deze periodiek naar Django te synchroniseren.

## Architecture

```
Raspberry Pi (lokaal autonoom)
  ├─ SQLite database (access_events, lockers)
  └─ Sync process (elke X minuten)
       ↓
Django Central Backend
  ├─ RaspberryPi model (registration + monitoring)
  ├─ AccessEvent model (logged history)
  └─ Pi Sync API endpoint
```

## Setup Pi

### 1. Registreer Pi in Django Admin

Ga naar: `http://<django-server>/admin/devices/raspberrypi/`

- **Name**: Beschrijvende naam (bijv. "Pi Afdeling A")
- **Company**: Selecteer het bedrijf waar de Pi op staat
- **Unique Code**: Unieke identifier (bijv. "pi-001" of MAC-adres)
- **Location**: Fysieke locatie (bijv. "Gang 1e etage")

**Django genereert automatisch:**
- `api_key` — kopieëren voor gebruik op Pi

### 2. Python Script op Pi

```python
import requests
import json
from datetime import datetime

# Configuration
DJANGO_URL = "http://<django-server>:8000"
PI_API_KEY = "<gekopieerd uit Django admin>"

def sync_events(events):
    """
    Stuur batched events naar Django.
    
    events: List van dicts met:
    {
        "locker_number": 1,
        "credential_type": "nfc" | "pin",
        "credential_value": "AABBCCDD",
        "success": true/false,
        "message": "...",
        "timestamp": "2026-03-30T14:30:00Z"
    }
    """
    
    headers = {
        "X-PI-KEY": PI_API_KEY,
        "Content-Type": "application/json"
    }
    
    payload = {
        "events": events
    }
    
    try:
        response = requests.post(
            f"{DJANGO_URL}/api/devices/pi-sync/sync/",
            json=payload,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Sync succesvol: {result['synced_count']} events")
            return result
        else:
            print(f"✗ Sync fout: {response.status_code}")
            print(response.text)
            return None
    except Exception as e:
        print(f"✗ Connection fout: {e}")
        return None


# Voorbeeld: Handmatig sync testen
if __name__ == "__main__":
    test_events = [
        {
            "locker_number": 1,
            "credential_type": "nfc",
            "credential_value": "AABBCCDD",
            "success": True,
            "message": "Locker geopend",
            "timestamp": datetime.now().isoformat() + "Z"
        },
        {
            "locker_number": 2,
            "credential_type": "pin",
            "credential_value": "1234",
            "success": False,
            "message": "Pincode onjuist",
            "timestamp": datetime.now().isoformat() + "Z"
        }
    ]
    
    sync_events(test_events)
```

## Monitoring

### Management Command

```bash
# Check Pi status (offline als > 10 minuten geen sync)
python manage.py monitor_pis --verbose

# Custom timeout (bijv. 5 minuten)
python manage.py monitor_pis --timeout 300
```

### Via Cron (Linux/Pi)

```bash
# Elke 10 minuten Pi-status monitoren
*/10 * * * * cd /pad/naar/django && python manage.py monitor_pis

# Log output (optioneel)
*/10 * * * * cd /pad/naar/django && python manage.py monitor_pis >> /var/log/pi_monitor.log 2>&1
```

## API Endpoints

### POST `/api/devices/pi-sync/sync/`

**Headers:**
```
X-PI-KEY: <pi-api-key>
Content-Type: application/json
```

**Request body:**
```json
{
    "events": [
        {
            "locker_number": 1,
            "credential_type": "nfc",
            "credential_value": "AABBCCDD",
            "success": true,
            "message": "OK",
            "timestamp": "2026-03-30T14:30:00Z"
        }
    ]
}
```

**Response:**
```json
{
    "success": true,
    "synced_count": 1,
    "message": "1 events gesynchroniseerd.",
    "errors": null
}
```

### GET `/api/devices/raspberry-pis/`

Lijst van alle Pi's (geverifieerd via JWT token, company-gefilterd).

### GET `/api/devices/access-events/`

Alle access events (geverifieerd, company-gefilterd).

## Performance Tips

1. **Batch events** — bundel meerdere events (max 1000 per sync)
2. **Timing** — sync elke 5-10 minuten, niet meer
3. **Fallback** — als sync mislukt, bewaar events lokaal (SQLite)
4. **Retry logic** — probeer opnieuw bij netwerk-fout

## Troubleshooting

| Issue | Oorzaak | Oplossing |
|-------|---------|----------|
| "Ongeldige Pi API sleutel" | API key typo | Controleer in Django admin |
| "Pi authenticatie vereist" | X-PI-KEY header ontbreekt | Voeg header toe |
| 401 Unauthorized | Pi is inactief | Zet `is_active=True` in admin |
| Geen events zichtbaar | Verkeerde company | Zorg dat Pi & Locker bij zelfde company horen |
