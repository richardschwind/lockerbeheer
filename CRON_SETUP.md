# Cron Setup - Pi Monitoring

##  Doel
Zorg dat `python manage.py monitor_pis` automatisch draait om Pi connectivity status bij te werken.

## Setup op Raspberry Pi (auto-update Pi status)

### Optie 1: Via crontab

1. **Open crontab editor:**
```bash
crontab -e
```

2. **Voeg toe (elke 10 minuten run monitor):**
```cron
*/10 * * * * /bin/bash -c 'cd /var/www/lockerbeheer/backend && python manage.py monitor_pis'
```

3. **Of met verbose logging:**
```cron
*/10 * * * * /bin/bash -c 'cd /var/www/lockerbeheer/backend && python manage.py monitor_pis --verbose >> /var/log/pi_monitor.log 2>&1'
```

4. **Check crontab:**
```bash
crontab -l
```

### Optie 2: Via systemd timer (meer robuust)

**File: `/etc/systemd/system/pi-monitor.service`**
```ini
[Unit]
Description=Lockerbeheer Pi Monitor
After=network.target

[Service]
Type=oneshot
User=django  # Of je deployment user
WorkingDirectory=/var/www/lockerbeheer/backend
ExecStart=/usr/bin/python manage.py monitor_pis --verbose
StandardOutput=journal
StandardError=journal
Environment="PYTHONUNBUFFERED=1"
```

**File: `/etc/systemd/system/pi-monitor.timer`**
```ini
[Unit]
Description=Run Pi Monitor every 10 minutes
Requires=pi-monitor.service

[Timer]
OnBootSec=2min
OnUnitActiveSec=10min
Persistent=true

[Install]
WantedBy=timers.target
```

**Activate:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now pi-monitor.timer
sudo systemctl status pi-monitor.timer
```

**Check logs:**
```bash
journalctl -u pi-monitor.service -f
```

## Setup op Django Server (auto-update Pi monitoring)

### Optie 1: Django Cron (APScheduler)

**Install:**
```bash
pip install django-apscheduler
```

**File: `backend/config/settings.py` — append:**
```python
INSTALLED_APPS = [
    # ... existing apps
    'django_apscheduler',
]

# APScheduler configuration
APSCHEDULER_DATETIME_TIMEOUT = 60 * 60  # 1 hour max task duration
```

**File: `backend/apps/devices/apps.py`**
```python
from django.apps import AppConfig

class DevicesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.devices'
    
    def ready(self):
        """Schedule Pi monitoring on app startup"""
        from django_apscheduler.apscheduler import DjangoJobExecution
        from apscheduler.schedulers.background import BackgroundScheduler
        from django.core.management import call_command
        import logging
        
        scheduler = BackgroundScheduler()
        
        def monitor_pis_task():
            try:
                call_command('monitor_pis', '--verbose')
            except Exception as e:
                logging.error(f"Pi monitor error: {e}")
        
        # Run every 10 minutes
        scheduler.add_job(
            monitor_pis_task,
            'interval',
            minutes=10,
            id='monitor_pis',
            name='Monitor Raspberry Pi status',
            replace_existing=True
        )
        
        if not scheduler.running:
            scheduler.start()
```

### Optie 2: Celery (async task queue)

**Install:**
```bash
pip install celery redis
```

**File: `backend/config/celery.py`** (create)
```python
import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('lockerbeheer')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Scheduled tasks
app.conf.beat_schedule = {
    'monitor-pis': {
        'task': 'apps.devices.tasks.monitor_pis',
        'schedule': crontab(minute='*/10'),  # Every 10 minutes
    },
}
```

**File: `backend/apps/devices/tasks.py`** (create)
```python
from celery import shared_task
from django.core.management import call_command
import logging

logger = logging.getLogger(__name__)

@shared_task
def monitor_pis():
    """Periodically check Pi status"""
    try:
        call_command('monitor_pis', '--verbose')
        logger.info("Pi monitoring task completed")
    except Exception as e:
        logger.error(f"Pi monitoring task failed: {e}")
```

**Start Celery worker:**
```bash
celery -A config worker --loglevel=info
```

**Start Celery beat (scheduler):**
```bash
celery -A config beat --loglevel=info
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Cron niet uitgevoerd | Check `sudo service cron status` atau `systemctl status cron` |
| "No such file" error | Gebruik absolute paths; test pwd in cronjob |
| Django imports fail | Set venv activation: `source /path/venv/bin/activate` |
| No output in logs | Redirect stderr: `command >> log.txt 2>&1` |

## Monitoring

Check if tasks run:
```bash
# View cron logs
sudo tail -f /var/log/syslog | grep CRON

# View Django monitor log (if systemd)
journalctl -u pi-monitor.service -f

# Check last runs
sudo grep CRON /var/log/auth.log | tail -20
```

## Recommended Settings

- **Pi Timeout**: 600 seconds (10 minutes) — if no sync in 10 min, mark OFFLINE
- **Monitor Frequency**: Every 10 minutes — balances responsiveness vs load
- **Log Retention**: Keep 30 days of logs (logrotate)

