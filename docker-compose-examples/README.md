# Docker Compose Examples

This directory contains different Docker Compose configurations for various deployment scenarios.

## Available Configurations

| File | Description | Use Case |
|------|-------------|----------|
| `docker-compose.dev.yml` | Local development with builds | Development, testing changes |
| `docker-compose.ghcr.yml` | Production with GHCR images (SQLite) | Quick production setup |
| `docker-compose.ghcr-mariadb.yml` | Production with GHCR images + MariaDB | Full production with GTS |

## Quick Start

### Development (Local Builds)

```bash
cd docker-compose-examples
cp ../.env.example .env
# Edit .env file with your settings
docker compose -f docker-compose.dev.yml up -d
```

This builds all images locally from the source code.

### Production with SQLite (GHCR Images)

```bash
cd docker-compose-examples
cp ../.env.example .env
# Edit .env file with your settings
docker compose -f docker-compose.ghcr.yml up -d
```

Uses pre-built images from GitHub Container Registry. Faster startup, no build required.

### Production with MariaDB + GTS (GHCR Images)

```bash
cd docker-compose-examples
cp ../.env.example .env
# Edit .env file with your settings
# Make sure to set DATABASE_ENGINE=mariadb and GTS credentials
docker compose -f docker-compose.ghcr-mariadb.yml up -d
```

Full production setup with MariaDB database and Pokemon GTS support.

## Configuration Comparison

| Feature | dev.yml | ghcr.yml | ghcr-mariadb.yml |
|---------|---------|----------|------------------|
| **Image Source** | Local build | GHCR | GHCR |
| **Database** | SQLite | SQLite | MariaDB |
| **GTS Support** | ❌ | ❌ | ✅ |
| **Build Time** | ~10-15 min | ~30 sec | ~30 sec |
| **Disk Space** | High (builds) | Low | Low |
| **Best For** | Development | Simple production | Full production |

## Environment Variables

All configurations use the same `.env` file. Key differences:

### SQLite Configurations (dev.yml, ghcr.yml)

```env
DATABASE_ENGINE=sqlite
DATABASE_NAME=/app/data/dwc_server.db
```

### MariaDB Configuration (ghcr-mariadb.yml)

```env
DATABASE_ENGINE=mariadb
DATABASE_NAME=dwc_server
DATABASE_USER=dwc
DATABASE_PASSWORD=changeme
DATABASE_HOST=mariadb
DATABASE_PORT=3306
DATABASE_ROOT_PASSWORD=rootpassword

# GTS Database
GTS_DB_NAME=gts
GTS_DB_USER=gts
GTS_DB_PASSWORD=gts
```

## Image Tags

By default, all GHCR configurations use the `latest` tag. You can specify a specific version:

```yaml
# Example: Use version 1.0.0 instead of latest
services:
  apache:
    image: ghcr.io/jonathan-priebe/dwc-server-apache:1.0.0
```

Available tags:
- `latest` - Latest stable release
- `v1.2.3` - Specific version (semver)
- `1.2` - Major.minor version
- `1` - Major version only
- `sha-abc1234` - Specific commit

## Switching Between Configurations

To switch from one configuration to another:

```bash
# Stop current setup
docker compose -f docker-compose.dev.yml down

# Start new setup
docker compose -f docker-compose.ghcr.yml up -d
```

**Note:** If switching from SQLite to MariaDB or vice versa, you'll need to migrate your data manually.

## Ports

All configurations expose the same ports:

| Service | Port | Protocol | Description |
|---------|------|----------|-------------|
| Apache | 80 | TCP | HTTP |
| Apache | 443 | TCP | HTTPS |
| DNSMasq | 53 | TCP/UDP | DNS |
| Admin Panel | 7999 | TCP | Django Admin |
| GameSpy GP | 29900 | TCP | GameSpy Login |
| GameSpy QR | 27900 | UDP | GameSpy Query |
| DLS1 | 9003 | TCP | Download Service |
| Storage | 8000 | TCP | Storage Server |
| MariaDB | 3306 | TCP | Database (mariadb only) |

## Data Persistence

All configurations mount the same volumes for data persistence:

- `./data` - SQLite databases, game data
- `./logs` - Application logs
- `mariadb-data` - MariaDB data (mariadb only)
- `static-files` - Django static files

## Troubleshooting

### Images not found (GHCR)

If you get "image not found" errors with GHCR configurations:

1. Check if images are published: https://github.com/jonathan-priebe?tab=packages
2. Try pulling manually: `docker pull ghcr.io/jonathan-priebe/dwc-server-apache:latest`
3. If private, login first: `docker login ghcr.io`

### Build failures (dev.yml)

If builds fail in development mode:

1. Ensure all submodules are checked out: `git submodule update --init --recursive`
2. Check Docker build logs: `docker compose -f docker-compose.dev.yml build --no-cache`
3. Verify Dockerfiles exist in `docker/` directory

### Permission issues

If you get permission errors:

```bash
sudo chown -R $USER:$USER data/ logs/
chmod -R 755 data/ logs/
```

## See Also

- [Main README](../README.md) - Full project documentation
- [GitHub Actions Workflows](../.github/workflows/README.md) - CI/CD documentation
- [.env.example](../.env.example) - Environment variable reference
