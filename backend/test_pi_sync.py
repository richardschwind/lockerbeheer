#!/usr/bin/env python3
"""
Test script voor Pi Sync endpoint.
Gebruik: python test_pi_sync.py
"""

import os
import django
import requests
import json
from datetime import datetime, timedelta

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.devices.models import RaspberryPi, AccessEvent
from apps.users.models import Company
from apps.lockers.models import LockerLocation

# Color output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'


def create_test_pi():
    """Creëer test Pi in database."""
    company = Company.objects.first()
    if not company:
        print(f"{Colors.RED}✗ Geen company gevonden. Creëer eerst een Company.{Colors.END}")
        return None
    
    pi, created = RaspberryPi.objects.get_or_create(
        unique_code="test-pi-001",
        defaults={
            "name": "Test Pi #001",
            "company": company,
            "location": LockerLocation.objects.get_or_create(company=company, name="Lab")[0],
        }
    )
    
    if created:
        print(f"{Colors.GREEN}✓ Test Pi aangemaakt:{Colors.END}")
    else:
        print(f"{Colors.YELLOW}! Test Pi bestaat al:{Colors.END}")
    
    print(f"  - Name: {pi.name}")
    print(f"  - Company: {pi.company.name}")
    print(f"  - API Key: {pi.api_key}")
    print()
    
    return pi


def test_sync_endpoint(pi):
    """Test POST /api/devices/pi-sync/sync/"""
    
    print(f"{Colors.BLUE}═══ TEST: Pi Sync Endpoint ═══{Colors.END}")
    print()
    
    # Endpoint
    url = "http://localhost:8000/api/devices/pi-sync/sync/"
    
    # Headers met Pi API Key
    headers = {
        "X-PI-KEY": pi.api_key,
        "Content-Type": "application/json"
    }
    
    # Test payload
    now = datetime.now()
    payload = {
        "events": [
            {
                "locker_number": 1,
                "credential_type": "nfc",
                "credential_value": "AABBCCDD1111",
                "success": True,
                "message": "Locker #1 geopend met NFC",
                "timestamp": now.isoformat() + "Z",
                "locker_state": "occupied_nfc"
            },
            {
                "locker_number": 2,
                "credential_type": "pin",
                "credential_value": "1234",
                "success": False,
                "message": "Pincode onjuist",
                "timestamp": (now - timedelta(seconds=30)).isoformat() + "Z",
                "locker_state": "unknown"
            },
            {
                "locker_number": 3,
                "credential_type": "nfc",
                "credential_value": "EEFF00112222",
                "success": True,
                "message": "Locker #3 geopend met NFC",
                "timestamp": (now - timedelta(minutes=1)).isoformat() + "Z",
                "locker_state": "opened_and_released"
            }
        ]
    }
    
    print(f"POST {url}")
    print(f"Headers: {headers}")
    print(f"Payload: {json.dumps(payload, indent=2)}")
    print()
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=5)
        
        print(f"Status: {response.status_code}")
        result = response.json()
        print(f"Response: {json.dumps(result, indent=2)}")
        print()
        
        if response.status_code == 200:
            print(f"{Colors.GREEN}✓ Sync succesvol!{Colors.END}")
            return result
        else:
            print(f"{Colors.RED}✗ Sync gefaald{Colors.END}")
            return None
            
    except Exception as e:
        print(f"{Colors.RED}✗ Connection error: {e}{Colors.END}")
        return None


def check_database_events(pi):
    """Check ingecreëerde AccessEvents in database."""
    
    print(f"{Colors.BLUE}═══ CHECK: AccessEvents in Database ═══{Colors.END}")
    print()
    
    events = AccessEvent.objects.filter(raspberry_pi=pi).order_by('-pi_timestamp')
    
    print(f"AccessEvents voor Pi '{pi.name}':")
    print()
    
    if events.count() == 0:
        print(f"{Colors.YELLOW}! Geen events gevonden{Colors.END}")
        return
    
    for i, event in enumerate(events[:10], 1):
        status_icon = f"{Colors.GREEN}✓{Colors.END}" if event.status == "success" else f"{Colors.RED}✗{Colors.END}"
        print(f"{i}. {status_icon} Locker #{event.locker_number} | {event.credential_type}")
        print(f"   - Status: {event.status}")
        print(f"   - Message: {event.message}")
        print(f"   - Pi Time: {event.pi_timestamp}")
        print()
    
    print(f"{Colors.GREEN}Total: {events.count()} events{Colors.END}")
    print()


def check_pi_status(pi):
    """Check Pi connectivity status."""
    
    print(f"{Colors.BLUE}═══ CHECK: Pi Status ═══{Colors.END}")
    print()
    
    # Refresh from DB
    pi.refresh_from_db()
    
    print(f"Name: {pi.name}")
    print(f"Status: {pi.get_status_display()}")
    print(f"Last Sync: {pi.last_sync}")
    print(f"Last IP: {pi.last_ip}")
    print(f"Is Active: {pi.is_active}")
    print()


def main():
    """Run all tests."""
    
    print()
    print(f"{Colors.BLUE}╔═══════════════════════════════════════╗{Colors.END}")
    print(f"{Colors.BLUE}║  Pi Sync Endpoint Test Suite          ║{Colors.END}")
    print(f"{Colors.BLUE}╚═══════════════════════════════════════╝{Colors.END}")
    print()
    
    # 1. Create test Pi
    pi = create_test_pi()
    if not pi:
        return
    
    # 2. Test sync endpoint
    test_sync_endpoint(pi)
    
    # 3. Check database
    check_database_events(pi)
    
    # 4. Check Pi status
    check_pi_status(pi)
    
    print(f"{Colors.GREEN}═══ Test Complete ═══{Colors.END}")
    print()
    print("Next steps:")
    print("1. Controleer Django admin: http://localhost:8000/admin/devices/accessevent/")
    print("2. Controleer Pi status: http://localhost:8000/admin/devices/raspberrypi/")
    print("3. Test API endpoint: curl -H 'X-PI-KEY: <key>' http://localhost:8000/api/devices/access-events/")


if __name__ == "__main__":
    main()
