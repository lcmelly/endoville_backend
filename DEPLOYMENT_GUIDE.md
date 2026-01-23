# Endoville Backend - Complete Deployment Guide

Complete guide for deploying the Endoville Backend Django application on Ubuntu 22.04 LTS with Nginx, Gunicorn, and SSL.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Initial Server Setup](#initial-server-setup)
3. [Clone Repository](#clone-repository)
4. [Python Environment Setup](#python-environment-setup)
5. [Django Configuration](#django-configuration)
6. [Database Setup](#database-setup)
7. [Gunicorn Setup with Systemd](#gunicorn-setup-with-systemd)
8. [Nginx Configuration](#nginx-configuration)
9. [SSL/HTTPS Setup](#sslhttps-setup)
10. [Final Verification](#final-verification)
11. [Troubleshooting](#troubleshooting)

---

## Prerequisites

- Ubuntu 22.04 LTS server
- Root or sudo access
- Domain name pointing to your server IP (for SSL)
- Git installed (usually pre-installed)

---

## Initial Server Setup

### Update System

```bash
sudo apt update
sudo apt upgrade -y
```

### Install Required Packages

```bash
sudo apt install -y python3 python3-pip python3-venv nginx git ufw
```

### Configure Firewall

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status
```

---

## Clone Repository

### Create User (if needed)

If the `endoville` user doesn't exist:

```bash
sudo adduser endoville
sudo usermod -aG sudo endoville
```

### Clone Repository

```bash
# Switch to endoville user
su - endoville

# Navigate to home directory
cd ~

# Clone your repository (replace with your actual repository URL)
git clone <your-repository-url> endoville_backend

# Navigate to project directory
cd endoville_backend
```

---

## Python Environment Setup

### Create Virtual Environment

```bash
cd ~/endoville_backend
python3 -m venv venv
source venv/bin/activate
```

### Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Install Gunicorn (if not in requirements.txt)

```bash
pip install gunicorn
```

---

## Django Configuration

### Create Environment File

```bash
cd ~/endoville_backend/src
nano .env
```

Add your environment variables:

```env
SECRET_KEY=your-secret-key-here
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com,your-server-ip
DEFAULT_FROM_EMAIL=your-email@example.com
ZOHO_ZEPTOMAIL_API_KEY_TOKEN=your-api-key
ZOHO_ZEPTOMAIL_HOSTED_REGION=zeptomail.zoho.com
ZEPTOMAIL_OTP_TEMPLATE_KEY=your-template-key
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
```

### Run Migrations

```bash
python manage.py migrate
```

### Create Superuser

```bash
python manage.py createsuperuser
```

### Collect Static Files

```bash
python manage.py collectstatic --noinput
```

### Deactivate Virtual Environment

```bash
deactivate
```

---

## Database Setup

For production, consider using PostgreSQL. For SQLite (development/testing):

```bash
# SQLite is already configured in settings.py
# Just ensure the database file has correct permissions
sudo chown -R endoville:endoville ~/endoville_backend/src/db.sqlite3
sudo chmod 644 ~/endoville_backend/src/db.sqlite3
```

---

## Gunicorn Setup with Systemd

### Create Systemd Socket File

```bash
sudo nano /etc/systemd/system/gunicorn.socket
```

Add:

```ini
[Unit]
Description=gunicorn socket

[Socket]
ListenStream=/run/gunicorn.sock
SocketMode=0660

[Install]
WantedBy=sockets.target
```

### Create Systemd Service File

```bash
sudo nano /etc/systemd/system/gunicorn.service
```

Add (replace `endoville` with your username if different):

```ini
[Unit]
Description=gunicorn daemon
Requires=gunicorn.socket
After=network.target

[Service]
User=endoville
Group=www-data
WorkingDirectory=/home/endoville/endoville_backend/src
Environment="PATH=/home/endoville/endoville_backend/venv/bin"
ExecStart=/home/endoville/endoville_backend/venv/bin/python3 -m gunicorn \
          --access-logfile - \
          --workers 3 \
          --threads 2 \
          --worker-class gthread \
          --timeout 120 \
          --bind unix:/run/gunicorn.sock \
          core.wsgi:application

Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

### Start and Enable Services

```bash
sudo systemctl daemon-reload
sudo systemctl start gunicorn.socket
sudo systemctl enable gunicorn.socket
sudo systemctl start gunicorn
sudo systemctl enable gunicorn
```

### Verify Gunicorn is Running

```bash
sudo systemctl status gunicorn
```

### Test Socket

```bash
curl --unix-socket /run/gunicorn.sock http://localhost/
```

---

## Nginx Configuration

### Remove Default Site

```bash
sudo rm /etc/nginx/sites-enabled/default
```

### Create Nginx Configuration

```bash
sudo nano /etc/nginx/sites-available/endoville_backend
```

Add (replace `yourdomain.com` and `your-server-ip` with your actual values):

```nginx
# HTTP Server - Redirect to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name yourdomain.com www.yourdomain.com your-server-ip;

    # Redirect all HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

# HTTPS Server
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    # SSL Certificate Configuration (will be added by Certbot)
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # SSL Configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305:DHE-RSA-AES128-GCM-SHA256:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Favicon
    location = /favicon.ico {
        access_log off;
        log_not_found off;
    }

    # Static Files
    location /static/ {
        alias /home/endoville/endoville_backend/src/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Media Files
    location /media/ {
        alias /home/endoville/endoville_backend/src/media/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Proxy to Gunicorn
    location / {
        proxy_pass http://unix:/run/gunicorn.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $server_name;
        proxy_redirect off;

        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

### Enable Site

```bash
sudo ln -s /etc/nginx/sites-available/endoville_backend /etc/nginx/sites-enabled/
```

### Test Configuration

```bash
sudo nginx -t
```

### Start Nginx

```bash
sudo systemctl start nginx
sudo systemctl enable nginx
sudo systemctl status nginx
```

---

## SSL/HTTPS Setup

### Install Certbot

```bash
sudo apt install certbot python3-certbot-nginx -y
```

### Obtain SSL Certificate

```bash
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

Certbot will:
- Obtain the certificate
- Update your Nginx configuration
- Set up auto-renewal

### Verify Certificate

```bash
sudo certbot certificates
```

### Test Auto-Renewal

```bash
sudo certbot renew --dry-run
```

---

## Final Verification

### Check Services Status

```bash
sudo systemctl status gunicorn
sudo systemctl status nginx
sudo systemctl status certbot.timer
```

### Test HTTP Redirect

```bash
curl -I http://yourdomain.com
```

Should return `301 Moved Permanently` redirecting to HTTPS.

### Test HTTPS

```bash
curl -I https://yourdomain.com/admin/
```

Should return `200 OK` or `302 Found`.

### Test in Browser

Visit `https://yourdomain.com/admin/` in your browser:
- Should show padlock icon
- Admin login page should load with styling
- No security warnings

### Verify Static Files

```bash
curl -I https://yourdomain.com/static/admin/css/base.css
```

Should return `200 OK`.

---

## Troubleshooting

### Gunicorn Won't Start

1. **Check status:**
   ```bash
   sudo systemctl status gunicorn
   sudo journalctl -u gunicorn -n 50
   ```

2. **Verify paths in service file:**
   ```bash
   sudo cat /etc/systemd/system/gunicorn.service
   ls -la /home/endoville/endoville_backend/venv/bin/python3
   ```

3. **Check permissions:**
   ```bash
   ls -la /home/endoville/endoville_backend/src
   ```

### Nginx 502 Bad Gateway

1. **Check Gunicorn is running:**
   ```bash
   sudo systemctl status gunicorn
   ```

2. **Test socket:**
   ```bash
   curl --unix-socket /run/gunicorn.sock http://localhost/
   ```

3. **Check socket permissions:**
   ```bash
   ls -la /run/gunicorn.sock
   sudo -u www-data test -r /run/gunicorn.sock && echo "Readable" || echo "Not readable"
   ```

4. **Check Nginx error logs:**
   ```bash
   sudo tail -f /var/log/nginx/error.log
   ```

### Nginx 404 Not Found

1. **Verify Nginx configuration:**
   ```bash
   sudo nginx -t
   sudo cat /etc/nginx/sites-available/endoville_backend
   ```

2. **Check default site is disabled:**
   ```bash
   ls -la /etc/nginx/sites-enabled/
   ```

3. **Verify Gunicorn is responding:**
   ```bash
   curl --unix-socket /run/gunicorn.sock http://localhost/admin/
   ```

### Static Files Not Loading (404)

1. **Verify static files were collected:**
   ```bash
   ls -la /home/endoville/endoville_backend/src/static/admin/css/base.css
   ```

2. **Re-collect static files:**
   ```bash
   cd ~/endoville_backend/src
   source ../venv/bin/activate
   python manage.py collectstatic --noinput
   deactivate
   ```

3. **Check Nginx static location:**
   ```bash
   sudo cat /etc/nginx/sites-available/endoville_backend | grep -A 5 "location /static"
   ```

4. **Check permissions:**
   ```bash
   sudo chown -R endoville:www-data /home/endoville/endoville_backend/src/static
   sudo chmod -R 755 /home/endoville/endoville_backend/src/static
   ```

### SSL Certificate Issues

1. **Check certificate:**
   ```bash
   sudo certbot certificates
   ```

2. **Test renewal:**
   ```bash
   sudo certbot renew --dry-run
   ```

3. **Check Nginx SSL configuration:**
   ```bash
   sudo nginx -t
   ```

### Permission Denied Errors

1. **Fix project directory permissions:**
   ```bash
   sudo chown -R endoville:endoville ~/endoville_backend
   ```

2. **Fix static files permissions:**
   ```bash
   sudo chown -R endoville:www-data ~/endoville_backend/src/static
   sudo chmod -R 755 ~/endoville_backend/src/static
   ```

---

## Useful Commands

### Gunicorn Management

```bash
# Restart Gunicorn
sudo systemctl restart gunicorn

# Reload Gunicorn (graceful)
sudo systemctl reload gunicorn

# View logs
sudo journalctl -u gunicorn -f

# Check status
sudo systemctl status gunicorn
```

### Nginx Management

```bash
# Reload Nginx
sudo systemctl reload nginx

# Restart Nginx
sudo systemctl restart nginx

# Test configuration
sudo nginx -t

# View error logs
sudo tail -f /var/log/nginx/error.log

# View access logs
sudo tail -f /var/log/nginx/access.log
```

### Django Management

```bash
# Activate virtual environment
cd ~/endoville_backend
source venv/bin/activate
cd src

# Run migrations
python manage.py migrate

# Collect static files
python manage.py collectstatic --noinput

# Create superuser
python manage.py createsuperuser

# Django shell
python manage.py shell
```

---

## Maintenance

### Update Code

```bash
cd ~/endoville_backend
git pull
source venv/bin/activate
pip install -r requirements.txt
cd src
python manage.py migrate
python manage.py collectstatic --noinput
deactivate
sudo systemctl restart gunicorn
```

### Backup Database

For SQLite:
```bash
cp ~/endoville_backend/src/db.sqlite3 ~/backups/db-$(date +%Y%m%d-%H%M%S).sqlite3
```

### Monitor Logs

```bash
# Gunicorn logs
sudo journalctl -u gunicorn -f

# Nginx error logs
sudo tail -f /var/log/nginx/error.log

# Nginx access logs
sudo tail -f /var/log/nginx/access.log
```

### Certificate Renewal

Certificates auto-renew, but you can manually renew:

```bash
sudo certbot renew
sudo systemctl reload nginx
```

---

## Security Checklist

- [ ] Firewall configured (UFW)
- [ ] SSL/TLS enabled (Let's Encrypt)
- [ ] DEBUG=False in production
- [ ] Strong SECRET_KEY in .env
- [ ] ALLOWED_HOSTS configured
- [ ] Static files permissions set correctly
- [ ] Database permissions secured
- [ ] Regular backups configured
- [ ] System updates enabled
- [ ] Gunicorn running as non-root user

---

## Notes

- Replace `yourdomain.com`, `your-server-ip`, and `endoville` with your actual values
- This guide assumes deployment in `/home/endoville/endoville_backend/`
- For production, consider using PostgreSQL instead of SQLite
- Ensure your domain's DNS points to your server IP before setting up SSL
- Keep your `.env` file secure and never commit it to version control

---

## Additional Resources

- [Django Deployment Checklist](https://docs.djangoproject.com/en/stable/howto/deployment/checklist/)
- [Gunicorn Documentation](https://docs.gunicorn.org/)
- [Nginx Documentation](https://nginx.org/en/docs/)
- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)

