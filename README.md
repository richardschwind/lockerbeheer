# Lockerbeheer

Locker management systeem gebouwd met React + Django + PostgreSQL.

## Snelstart (lokaal zonder Docker)

### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Met Docker
```bash
docker-compose up --build
```

Migraties uitvoeren na eerste start:
```bash
docker-compose exec backend python manage.py migrate
docker-compose exec backend python manage.py createsuperuser
```

## Api Endpoints

### Authenticatie & Gebruikers
| Methode | URL | Beschrijving |
|---------|-----|--------------|
| POST | `/api/auth/token/` | Inloggen (JWT) |
| POST | `/api/auth/token/refresh/` | Token vernieuwen |
| POST | `/api/users/register/` | Registreren |
| GET | `/api/users/me/` | Eigen profiel |

### Lockersbeheer
| Methode | URL | Beschrijving |
|---------|-----|--------------|
| GET/POST | `/api/lockers/` | Lockers |
| GET/POST | `/api/lockers/locations/` | Locaties |

### Huurovereenkomsten
| Methode | URL | Beschrijving |
|---------|-----|--------------|
| GET/POST | `/api/rentals/` | Huurovereenkomsten |

### Raspberry Pi Sync (✨ Nieuw!)
| Methode | URL | Beschrijving |
|---------|-----|--------------|
| POST | `/api/devices/pi-sync/sync/` | Pi event sync (X-PI-KEY header) |
| GET | `/api/devices/raspberry-pis/` | Lijst Pi's |
| GET | `/api/devices/access-events/` | Access event log |

## Projectstructuur

```
lockerbeheer/
├── backend/
│   ├── apps/
│   │   ├── users/      # Authenticatie & gebruikers
│   │   ├── lockers/    # Locker beheer
│   │   ├── rentals/    # Huurovereenkomsten
│   │   └── devices/    # Raspberry Pi & AccessEvents (✨ Nieuw!)
│   ├── config/         # Django instellingen & URLs
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── api/        # Axios API calls
│       ├── context/    # Auth context
│       ├── components/ # Herbruikbare componenten
│       └── pages/      # Pagina's per feature
├── PI_QUICKSTART.md    # ⚡ Pi integration gids
├── PI_SYNC_DOCS.md     # 📚 Gedetailleerde documentatie
├── CRON_SETUP.md       # 🔄 Monitoring scheduling
└── docker-compose.yml
```

## 🎯 Raspberry Pi Sync Integration (✨ Nieuw!)

### Overview
Raspberry Pi's kunnen **autonoom** access-events lokaal opslaan en deze periodiek synchroniseren met de centrale Django backend.

### Quickstart
```bash
# 1. Register Pi in Django admin
http://localhost:8000/admin/devices/raspberrypi/

# 2. Copieer de auto-generated API key

# 3. Test sync met simulator
.venv/bin/python pi_client_simulator.py --pi-key <your-api-key> --events 10

# 4. Controleer events in admin
http://localhost:8000/admin/devices/accessevent/
```

### Documentatie
- **[PI_QUICKSTART.md](PI_QUICKSTART.md)** — 3-stap quick start gids
- **[PI_SYNC_DOCS.md](PI_SYNC_DOCS.md)** — Complete technische gids
- **[CRON_SETUP.md](CRON_SETUP.md)** — Background monitoring configuratie

### Features
- ✅ Multi-device support (ongelimiteerde Pi's per company)
- ✅ Batch event syncing (max 1000 events per sync)
- ✅ API-key authentication (X-PI-KEY header)
- ✅ Automatic status tracking (Online/Offline/Error)
- ✅ Event logging with timestamps
- ✅ Django admin integration
- ✅ Simulator tool for testing

