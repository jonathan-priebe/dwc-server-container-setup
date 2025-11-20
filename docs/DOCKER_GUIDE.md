# 🐳 Docker Deployment Guide

## Quick Start

### 1. With SQLite (Simple, Recommended for Testing)

```bash
# Copy environment file
cp .env.docker .env

# Build and start
docker-compose up -d

# View logs
docker-compose logs -f

# Access
# Admin: http://localhost:7999/admin
# API: http://localhost:7999/api
```

### 2. With MariaDB (Production)

```bash
# Edit .env and set:
# DATABASE_ENGINE=mariadb
# DATABASE_NAME=dwc_server
# DATABASE_USER=dwc
# DATABASE_PASSWORD=your-secure-password

# Start with MariaDB
docker-compose --profile with-mariadb up -d

# View logs
docker-compose logs -f
```

## Services

### Admin Panel (Django)
- **Port:** 8000
- **Container:** `dwc-admin`
- **Health:** http://localhost:7999/api/

### GameSpy Servers
- **Container:** `dwc-gamespy`
- **Ports:**
  - 8080 - NAS (HTTP)
  - 29900 - GP (TCP)
  - 27900 - QR (UDP)

### MariaDB (Optional)
- **Port:** 3306
- **Container:** `dwc-mariadb`

## Commands

### Start
```bash
# Start all (SQLite)
docker-compose up -d

# Start with MariaDB
docker-compose --profile with-mariadb up -d

# Start and view logs
docker-compose up
```

### Stop
```bash
# Stop all
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

### Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f admin
docker-compose logs -f gamespy
```

### Rebuild
```bash
# Rebuild after code changes
docker-compose build

# Rebuild without cache
docker-compose build --no-cache
```

### Database Management
```bash
# Run migrations
docker-compose exec admin python manage.py migrate

# Create superuser
docker-compose exec admin python manage.py createsuperuser

# Create test data
docker-compose exec admin python manage.py create_testdata
```

## Development vs Production

### Development Setup
```bash
# .env
DEBUG=True
DATABASE_ENGINE=sqlite
LOG_LEVEL=DEBUG
```

### Production Setup
```bash
# .env
DEBUG=False
DATABASE_ENGINE=mariadb
DATABASE_PASSWORD=very-secure-password
SECRET_KEY=random-long-key-here
ALLOWED_HOSTS=your-domain.com,your-ip
LOG_LEVEL=INFO
```

## Port Mapping

You can change external ports in docker-compose.yml:

```yaml
services:
  admin:
    ports:
      - "7999:7999"  # Change 7999 to your desired port
  
  gamespy:
    ports:
      - "80:8080"    # Use port 80 for NAS
      - "29900:29900"
      - "27900:27900/udp"
```

## Volumes

- `mariadb-data` - Database files
- `static-files` - Django static files
- `./data` - Shared data (SQLite, uploads)
- `./logs` - Application logs

## Health Checks

All containers have health checks:

```bash
# Check status
docker-compose ps

# Should show "healthy" for all services
```

## Troubleshooting

### Admin panel not accessible
```bash
# Check logs
docker-compose logs admin

# Restart admin
docker-compose restart admin
```

### GameSpy servers not responding
```bash
# Check if ports are open
docker-compose ps
docker-compose logs gamespy

# Test connectivity
nc -zv localhost 29900  # GP
nc -zu localhost 27900  # QR (UDP)
```

### Database connection issues
```bash
# If using MariaDB, check it's healthy
docker-compose ps mariadb

# View MariaDB logs
docker-compose logs mariadb

# Restart MariaDB
docker-compose restart mariadb
```

### Clear all data and start fresh
```bash
# Stop and remove everything
docker-compose down -v

# Remove data
rm -rf data/*

# Start again
docker-compose up -d
```

## Backup

### SQLite
```bash
# Backup database
cp data/dwc_server.db data/dwc_server.db.backup

# Or use docker cp
docker cp dwc-admin:/app/data/dwc_server.db ./backup.db
```

### MariaDB
```bash
# Backup
docker-compose exec mariadb mysqldump -u dwc -p dwc_server > backup.sql

# Restore
docker-compose exec -T mariadb mysql -u dwc -p dwc_server < backup.sql
```

## Performance Tuning

### For Production

Edit docker-compose.yml:

```yaml
services:
  admin:
    command: >
      gunicorn config.wsgi:application 
      --bind 0.0.0.0:7999 
      --workers 4        # Increase workers
      --threads 2
      --timeout 60
      --max-requests 1000
```

## Security

### Production Checklist

- [ ] Change SECRET_KEY
- [ ] Set DEBUG=False
- [ ] Use strong DATABASE_PASSWORD
- [ ] Set specific ALLOWED_HOSTS
- [ ] Use HTTPS (reverse proxy recommended)
- [ ] Regular backups
- [ ] Update dependencies regularly

### Reverse Proxy (Nginx)

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Monitoring

```bash
# Resource usage
docker stats

# Specific container
docker stats dwc-admin dwc-gamespy
```

## Updates

```bash
# Pull latest code
git pull

# Rebuild containers
docker-compose build

# Restart with new images
docker-compose up -d
```