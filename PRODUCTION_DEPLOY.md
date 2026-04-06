# Production Deploy

Deze guide gaat uit van de stack die je hier al gebruikt:

- server IP: `95.111.250.181`
- backend onder `/lockerbeheer/`
- frontend onder `/lockerbeheer-frontend/`
- websocket proxy onder `/lockerbeheer/ws/`
- Gunicorn voor Django HTTP
- Daphne voor Channels websocket verkeer
- Nginx als reverse proxy
- PostgreSQL en Redis lokaal op de server

## 1. Vereisten op de server

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx redis-server postgresql postgresql-contrib
```

Controleer Redis:

```bash
sudo systemctl enable --now redis-server
sudo systemctl status redis-server
```

## 2. Applicatie ophalen

```bash
sudo mkdir -p /var/www/lockerbeheer
sudo chown -R $USER:$USER /var/www/lockerbeheer
cd /var/www/lockerbeheer
git clone <jouw-repo-url> .
```

Als de repo er al staat:

```bash
cd /var/www/lockerbeheer
git pull
```

## 3. Backend virtualenv en dependencies

```bash
cd /var/www/lockerbeheer
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt
```

## 4. PostgreSQL database

```bash
sudo -u postgres psql
```

Voer uit:

```sql
CREATE DATABASE lockerbeheer;
CREATE USER locker_user WITH PASSWORD 'kies-een-sterk-wachtwoord';
GRANT ALL PRIVILEGES ON DATABASE lockerbeheer TO locker_user;
\q
```

## 5. Backend environment file

Maak `/var/www/lockerbeheer/backend/.env.production`:

```env
DEBUG=False
SECRET_KEY=kies-hier-een-lange-unieke-secret
DATABASE_URL=postgresql://locker_user:kies-een-sterk-wachtwoord@127.0.0.1:5432/lockerbeheer
ALLOWED_HOSTS=95.111.250.181,localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://95.111.250.181
CSRF_TRUSTED_ORIGINS=http://95.111.250.181
CHANNEL_LAYER=redis
REDIS_URL=redis://127.0.0.1:6379/0
```

## 6. Django migraties en static files

```bash
cd /var/www/lockerbeheer/backend
source ../.venv/bin/activate
export $(grep -v '^#' .env.production | xargs)
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

## 7. Frontend build

De huidige productievariabelen in `frontend/.env.production` zijn al afgestemd op:

- `/lockerbeheer-frontend/`
- API via `/lockerbeheer/api`
- websocket via `/lockerbeheer/ws`

Build de frontend:

```bash
cd /var/www/lockerbeheer/frontend
npm install
npm run build
```

De build-output staat daarna in:

```bash
/var/www/lockerbeheer/frontend/dist
```

## 8. Systemd service voor Gunicorn

Maak `/etc/systemd/system/lockerbeheer-gunicorn.service`:

```ini
[Unit]
Description=Lockerbeheer Gunicorn
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/lockerbeheer/backend
EnvironmentFile=/var/www/lockerbeheer/backend/.env.production
ExecStart=/var/www/lockerbeheer/.venv/bin/gunicorn config.wsgi:application \
  --bind unix:/run/lockerbeheer-gunicorn.sock \
  --workers 3
Restart=always

[Install]
WantedBy=multi-user.target
```

## 9. Systemd service voor Daphne

Maak `/etc/systemd/system/lockerbeheer-daphne.service`:

```ini
[Unit]
Description=Lockerbeheer Daphne
After=network.target redis-server.service

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/lockerbeheer/backend
EnvironmentFile=/var/www/lockerbeheer/backend/.env.production
ExecStart=/var/www/lockerbeheer/.venv/bin/daphne \
  -u /run/lockerbeheer-daphne.sock \
  config.asgi:application
Restart=always

[Install]
WantedBy=multi-user.target
```

Zorg dat `www-data` toegang heeft:

```bash
sudo chown -R www-data:www-data /var/www/lockerbeheer
sudo systemctl daemon-reload
sudo systemctl enable --now lockerbeheer-gunicorn
sudo systemctl enable --now lockerbeheer-daphne
```

## 10. Nginx configuratie

Maak `/etc/nginx/sites-available/lockerbeheer`:

```nginx
server {
    listen 80;
    server_name 95.111.250.181;

    client_max_body_size 20M;

    location /lockerbeheer/static/ {
        alias /var/www/lockerbeheer/backend/staticfiles/;
    }

    location /lockerbeheer/media/ {
        alias /var/www/lockerbeheer/backend/media/;
    }

    location /lockerbeheer/ws/ {
        proxy_pass http://unix:/run/lockerbeheer-daphne.sock;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /lockerbeheer/ {
        proxy_pass http://unix:/run/lockerbeheer-gunicorn.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /lockerbeheer-frontend/ {
        alias /var/www/lockerbeheer/frontend/dist/;
        try_files $uri $uri/ /lockerbeheer-frontend/index.html;
    }
}
```

Activeer de site:

```bash
sudo ln -sf /etc/nginx/sites-available/lockerbeheer /etc/nginx/sites-enabled/lockerbeheer
sudo nginx -t
sudo systemctl reload nginx
```

## 11. Deploy update

Voor een volgende deploy:

```bash
cd /var/www/lockerbeheer
git pull
source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend
export $(grep -v '^#' .env.production | xargs)
python manage.py migrate
python manage.py collectstatic --noinput
cd ../frontend
npm install
npm run build
sudo systemctl restart lockerbeheer-gunicorn
sudo systemctl restart lockerbeheer-daphne
sudo systemctl reload nginx
```

## 12. Checks na deploy

Backend:

```bash
curl http://95.111.250.181/lockerbeheer/api/lockers/
```

Frontend:

```bash
http://95.111.250.181/lockerbeheer-frontend/
```

Services:

```bash
sudo systemctl status lockerbeheer-gunicorn
sudo systemctl status lockerbeheer-daphne
sudo systemctl status nginx
sudo systemctl status redis-server
```

Logs:

```bash
sudo journalctl -u lockerbeheer-gunicorn -f
sudo journalctl -u lockerbeheer-daphne -f
sudo tail -f /var/log/nginx/error.log
```