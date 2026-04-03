#!/usr/bin/env python3
"""
Raspberry Pi Client Simulator

Simulate a real Raspberry Pi sending access events to Django backend.
Use this for testing without actual hardware.

Usage:
    python pi_client_simulator.py --pi-key <api-key> --count 10 --interval 5
"""

import argparse
import requests
import time
import random
from datetime import datetime
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class PiClient:
    """Simulates a Raspberry Pi sending events to Django"""
    
    def __init__(self, django_url, pi_key, pi_name="Simulator-Pi-001"):
        self.django_url = django_url
        self.pi_key = pi_key
        self.pi_name = pi_name
        self.credentials = [
            {"type": "nfc", "value": f"NFC{i:06d}"} 
            for i in range(1, 20)
        ] + [
            {"type": "pin", "value": f"{i:04d}"} 
            for i in range(1000, 1010)
        ]
        self.lockers = list(range(1, 11))
        self.local_event_queue = []
    
    def generate_event(self, force_fail=False):
        """Generate random access event"""
        
        if force_fail or random.random() < 0.15:  # 15% failure rate
            success = False
            message = random.choice([
                "Pincode onjuist",
                "NFC tag onbekend",
                "Locker niet bereikbaar",
                "Timeout"
            ])
            locker_state = "unknown"
        else:
            success = True
            message = "OK"
            locker_state = random.choice([
                "occupied_pin",
                "occupied_nfc",
                "opened_and_released",
                "free",
            ])
        
        cred = random.choice(self.credentials)
        
        event = {
            "locker_number": random.choice(self.lockers),
            "credential_type": cred["type"],
            "credential_value": cred["value"],
            "success": success,
            "message": message,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "locker_state": locker_state,
        }
        
        return event
    
    def add_to_queue(self, event):
        """Add event to local queue (simulating Pi local storage)"""
        self.local_event_queue.append(event)
        logger.info(
            f"[Local] Locker #{event['locker_number']} | "
            f"{event['credential_type'].upper()} | "
            f"{'✓' if event['success'] else '✗'}"
        )
    
    def sync(self):
        """Sync queued events to Django"""
        
        if not self.local_event_queue:
            logger.info("No events to sync")
            return False
        
        headers = {
            "X-PI-KEY": self.pi_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "events": self.local_event_queue
        }
        
        try:
            logger.info(f"Syncing {len(self.local_event_queue)} events...")
            
            response = requests.post(
                f"{self.django_url}/api/devices/pi-sync/sync/",
                json=payload,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                return self._apply_sync_result(result)
            else:
                logger.error(f"✗ Sync failed: {response.status_code}")
                logger.error(response.text)
                return False
                
        except Exception as e:
            logger.error(f"✗ Sync error: {e}")
            return False

    def _apply_sync_result(self, result):
        """Apply backend sync result and keep failed events in queue for retry."""

        synced_count = int(result.get("synced_count", 0))
        failed_count = int(result.get("failed_count", 0))
        failed_indices = result.get("failed_indices") or []
        errors = result.get("errors") or []

        if failed_count == 0 and synced_count >= len(self.local_event_queue):
            logger.info(f"✓ Sync successful: {synced_count} events")
            self.local_event_queue = []
            return True

        if failed_indices:
            failed_index_set = {idx for idx in failed_indices if isinstance(idx, int) and idx >= 0}
            kept_events = [
                event
                for idx, event in enumerate(self.local_event_queue)
                if idx in failed_index_set
            ]
            dropped = len(self.local_event_queue) - len(kept_events)
            self.local_event_queue = kept_events

            logger.warning(
                "Partial sync: %s opgeslagen, %s gefaald, %s in retry-queue",
                dropped,
                len(kept_events),
                len(self.local_event_queue),
            )
            if errors:
                logger.warning("Backend errors: %s", errors)
            return dropped > 0

        if failed_count > 0:
            logger.warning(
                "Backend meldde %s failures zonder failed_indices; queue blijft volledig staan (%s events)",
                failed_count,
                len(self.local_event_queue),
            )
            if errors:
                logger.warning("Backend errors: %s", errors)
            return False

        # Fallback for older responses where only synced_count is returned.
        if synced_count > 0:
            remove_count = min(synced_count, len(self.local_event_queue))
            self.local_event_queue = self.local_event_queue[remove_count:]
            logger.info(
                "✓ Sync verwerkt met oudere response: %s verwijderd, %s in queue",
                remove_count,
                len(self.local_event_queue),
            )
            return True

        logger.warning("Geen events bevestigd door backend; queue blijft staan.")
        return False
    
    def get_status(self):
        """Check Pi status in Django"""
        
        headers = {
            "X-PI-KEY": self.pi_key,
        }
        
        try:
            response = requests.get(
                f"{self.django_url}/api/devices/raspberry-pis/",
                headers=headers,
                timeout=5
            )
            
            if response.status_code == 200:
                pis = response.json()
                if isinstance(pis, list) and pis:
                    pi = pis[0]
                    logger.info(f"π Status: {pi.get('status', 'unknown')} | Last sync: {pi.get('last_sync_ago', '?')}")
                    return pi
            return None
            
        except Exception as e:
            logger.error(f"Status check error: {e}")
            return None


def main():
    parser = argparse.ArgumentParser(
        description="Simulate Raspberry Pi sending events to Django"
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Django URL (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--pi-key",
        required=True,
        help="Pi API Key (from Django admin)"
    )
    parser.add_argument(
        "--name",
        default="Simulator-Pi-001",
        help="Pi name (default: Simulator-Pi-001)"
    )
    parser.add_argument(
        "--events",
        type=int,
        default=10,
        help="Number of events to generate (default: 10)"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=2,
        help="Seconds between events (default: 2)"
    )
    parser.add_argument(
        "--sync-interval",
        type=int,
        default=5,
        help="Sync every N events (default: 5)"
    )
    
    args = parser.parse_args()
    
    logger.info(f"═══ Pi Client Simulator ═══")
    logger.info(f"Django URL: {args.url}")
    logger.info(f"Pi Name: {args.name}")
    logger.info(f"Events: {args.events}")
    logger.info("")
    
    client = PiClient(args.url, args.pi_key, args.name)
    
    # Generate and sync events
    event_count = 0
    for i in range(args.events):
        event = client.generate_event()
        client.add_to_queue(event)
        event_count += 1
        
        # Sync every N events
        if event_count % args.sync_interval == 0:
            logger.info("")
            client.sync()
            logger.info("")
        
        # Wait before next event
        if i < args.events - 1:
            time.sleep(args.interval)
    
    # Final sync
    if client.local_event_queue:
        logger.info("")
        logger.info("Final sync...")
        client.sync()
    
    # Get final status
    logger.info("")
    client.get_status()
    
    logger.info("")
    logger.info("═══ Simulation Complete ═══")


if __name__ == "__main__":
    main()
