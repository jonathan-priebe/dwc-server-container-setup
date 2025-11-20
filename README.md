# DWC Server Python3

A Docker-based setup for hosting a custom Nintendo Wi-Fi Connection (WFC) server, enabling online functionality for various Nintendo DS and Wii titles with Django Admin Panel and Pokemon GTS support.

## Table of Contents

- [Features](#features)
- [System Overview](#system-overview)
  - [Architecture Diagram](#architecture-diagram)
  - [Container Services](#container-services)
  - [Network Ports](#network-ports)
- [Data Flow](#data-flow)
  - [DS Connection Flow](#ds-connection-flow)
  - [GTS Trading Flow](#gts-trading-flow)
  - [Friend Code Generation](#friend-code-generation)
- [Installation](#installation)
  - [Prerequisites](#prerequisites)
  - [Quick Start](#quick-start)
  - [DNS Configuration](#dns-configuration)
- [Configuration](#configuration)
  - [Environment Variables](#environment-variables)
  - [Database Options](#database-options)
  - [Security Keys](#security-keys)
- [Usage](#usage)
  - [Nintendo DS Setup](#nintendo-ds-setup)
  - [Admin Panel](#admin-panel)
  - [Managing Services](#managing-services)
  - [API Access](#api-access)
- [GTS (Pokemon Trading)](#gts-pokemon-trading)
  - [Enable GTS](#enable-gts)
  - [Supported Pokemon Games](#supported-pokemon-games)
  - [How GTS Works](#how-gts-works)
- [Troubleshooting](#troubleshooting)
- [Supported Games](#supported-games)
- [Project Structure](#project-structure)
- [Documentation](#documentation)
- [Legal Notice / Disclaimer](#legal-notice--disclaimer)
   - [Important Legal Information](#important-legal-information)
   - [Warranty Disclaimer](#warranty-disclaimer)
   - [Takedown Policy](#takedown-policy)
   - [License](#license)
- [Acknowledgments](#acknowledgments)

## Features

- **GameSpy Protocol**: Full implementation of GP, QR2, GPCM protocols
- **NAS Emulation**: Nintendo Authentication Server with challenge-response
- **GTS Support**: Pokemon Global Trade Station for Gen 4/5 games
- **Django Admin**: Web-based management interface
- **REST API**: Programmatic access to all data
- **Friend Codes**: Automatic generation and validation
- **Dual Database**: SQLite (simple) or MariaDB (full features)
- **Docker Deploy**: Complete containerized setup
- **DNS Server**: Built-in dnsmasq for DS redirection

## System Overview

### Architecture Diagram

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────────────────────┐
│  Nintendo DS    │     │   dnsmasq    │     │        Docker Network           │
│                 │     │              │     │                                 │
│ - Pokemon D/P   │────>│ DNS :53      │────>│  ┌─────────────────────────┐    │
│ - Mario Kart    │     │              │     │  │   Apache (dwc-apache)   │    │
│ - Animal Cross  │     │ Redirects:   │     │  │   :80 / :443 (SSLv3)    │    │
└─────────────────┘     │ *.nintendo   │     │  └───────────┬─────────────┘    │
                        │   wifi.net   │     │              │                  │
                        │ *.gamespy    │     │     ┌────────┼─────────────┐    │
                        │   .com       │     │     ▼        ▼             ▼    │
                        └──────────────┘     │  ┌───────────────────┐ ┌──────┐ │
                                             │  │ NAS    QR     GP  │ │ GTS  │ │
                                             │  │:8080 :27900 :29900│ │:9002 │ │
                                             │  └──┬────────┬───────┘ └────┬─┘ │
                                             │     │        │              │   │
                                             │     ▼        ▼              │   │
                                             │  ┌───────────────────────┐  │   │
                                             │  │   Django Admin Panel  │  │   │
                                             │  │   (dwc-admin) :7999   │  │   │
                                             │  └───────────┬───────────┘  │   │
                                             │              │              │   │
                                             │              ▼              ▼   │
                                             │  ┌────────────────────────────┐ │
                                             │  │   MariaDB / SQLite         │ │
                                             │  │   (dwc-mariadb) :3306      │ │
                                             │  └────────────────────────────┘ │
                                             └─────────────────────────────────┘
```

### Container Services

| Container | Service | Description | Database |
|-----------|---------|-------------|----------|
| `dwc-apache` | Apache 2.4 | Reverse proxy with SSLv3/Nintendo certs | - |
| `dwc-gamespy` | Python 3.11 | NAS, GP, QR servers | Via API |
| `dwc-admin` | Django 4.2 | Admin panel & REST API | SQLite/MariaDB |
| `dwc-gts` | Mono/.NET | Pokemon GTS (pkmn-classic-framework) | MariaDB only |
| `dwc-mariadb` | MariaDB 10.5 | Database server (optional) | - |
| `dnsmasq` | dnsmasq | DNS server for Nintendo domains | - |

### Network Ports

| Port | Protocol | Service | Description |
|------|----------|---------|-------------|
| 53 | TCP/UDP | dnsmasq | DNS server |
| 80 | HTTP | Apache | NAS, GTS proxy |
| 443 | HTTPS | Apache | NAS (SSLv3 for DS) |
| 3306 | TCP | MariaDB | Database (optional) |
| 7999 | HTTP | Django | Admin panel & API |
| 8080 | HTTP | NAS | Internal - Nintendo auth |
| 9002 | HTTP | GTS | Internal - Pokemon trading |
| 27900 | UDP | QR | Server browser |
| 29900 | TCP | GP | GameSpy presence |

## Data Flow

### DS Connection Flow

```
Step 1: DNS Resolution
┌──────┐                    ┌─────────┐
│  DS  │ ──── DNS Query ───>│ dnsmasq │
│      │ <── Server IP ─────│  :53    │
└──────┘                    └─────────┘

Step 2: NAS Authentication
┌──────┐                    ┌─────────┐                    ┌──────────┐
│  DS  │ ── POST /ac ──────>│ Apache  │ ── Proxy ─────────>│   NAS    │
│      │ <─ token+challenge─│  :443   │ <──────────────────│  :8080   │
└──────┘                    └─────────┘                    └──────────┘

Step 3: GameSpy Login
┌──────┐                    ┌──────────┐                   ┌──────────┐
│  DS  │ ── TCP Connect ───>│    GP    │ ── API Call ─────>│  Django  │
│      │ <─ Profile Data ───│  :29900  │ <─ Profile ───────│  :7999   │
└──────┘                    └──────────┘                   └──────────┘

Step 4: Server Registration
┌──────┐                    ┌──────────┐
│  DS  │ ── UDP Heartbeat ─>│    QR    │
│      │ <─ Challenge ──────│  :27900  │
└──────┘                    └──────────┘
```

### GTS Trading Flow

```
┌──────┐     ┌─────────┐     ┌──────────┐     ┌──────────┐
│  DS  │────>│ Apache  │────>│   GTS    │────>│ MariaDB  │
│      │     │  :80    │     │  :9002   │     │  :3306   │
└──────┘     └─────────┘     └──────────┘     └──────────┘
   │              │               │                │
   │   gamestats2.gs.            Mono/.NET        gts
   │   nintendowifi.net          Application     database
   │                                              │
   └──────────────────────────────────────────────┘
              Pokemon Data (upload/download)
```

### Friend Code Generation

Friend Codes are calculated from:
- **Profile ID**: Assigned by server on first connection
- **Game ID**: 4-character game code (e.g., ADAJ for Pokemon Diamond JP)

Algorithm: CRC8 checksum over `profile_id (LE) + game_id (BE->LE)` with polynomial 0x07

Example: Profile 88 + ADAJ = `3693-6718-7544`

## Installation

### Prerequisites

- Docker and Docker Compose v2+
- Open ports: 53, 80, 443, 29900, 27900
- DNS control (router or dnsmasq)

### Quick Start

**Clone the repository**
```bash
git clone --recurse-submodules https://github.com/jonathan-priebe/dwc-server-container-setup.git
cd dwc-server-container-setup
```

**Configure environment**
```bash
# Copy and configure environment
cp .env.example .env

# Generate required keys
SECRET_KEY=$(openssl rand -base64 50)
NAS_API_TOKEN=$(openssl rand -hex 20)

# Edit .env with your values (set SECRET_KEY and NAS_API_TOKEN)
nano .env
```

**Choose your deployment method:**

#### Simple Start (Root docker-compose.yml)

Fastest way to get started - uses the root `docker-compose.yml`:

```bash
# SQLite (basic Wi-Fi functionality):
docker compose up -d

# OR MariaDB + GTS (full features including Pokemon trading):
docker compose --profile mariadb up -d
```

#### Advanced Deployment (docker-compose-examples/)

For production with pre-built GHCR images or custom configurations:

| Configuration | Description | Best For |
|--------------|-------------|----------|
| **docker-compose.ghcr.yml** | Production with GHCR images (SQLite) | Quick production deployment |
| **docker-compose.ghcr-mariadb.yml** | Production with GHCR + MariaDB + GTS | Full production with Pokemon GTS |
| **docker-compose.dev.yml** | Local development builds | Development & testing |

```bash
cd docker-compose-examples
cp .env.example .env  # Configure if different from root .env
nano .env

# Production with pre-built images (SQLite):
docker compose -f docker-compose.ghcr.yml up -d

# Production with pre-built images (MariaDB + GTS):
docker compose -f docker-compose.ghcr-mariadb.yml up -d
```

> **For detailed configuration options and examples, see [docker-compose-examples/README.md](docker-compose-examples/README.md)**

> **Note**:
> - Root `docker-compose.yml` builds locally - best for getting started quickly
> - GHCR images (`docker-compose-examples/*.ghcr.yml`) are pre-built - faster for production
> - MariaDB 10.5 is required for GTS compatibility with Mono/.NET

### DNS Configuration

Point Nintendo domains to your server IP:

**Option 1: dnsmasq (included)**

The built-in dnsmasq container handles DNS automatically:

1. Edit `dnsmasq/wfc.conf` and replace `192.168.1.100` with your server's IP
2. Configure your Nintendo DS to use your server's IP as DNS server (in DS Wi-Fi settings)

The dnsmasq container is already configured in all docker-compose files.

**Option 2: Router/Custom DNS**

Add these DNS entries in your router pointing to your server:

```
*.nintendowifi.net → YOUR_SERVER_IP
*.gamespy.com → YOUR_SERVER_IP
```

Example router DNS override:
```
address=/nintendowifi.net/192.168.1.100
address=/gamespy.com/192.168.1.100
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| **Django Settings** | | |
| `SECRET_KEY` | Django secret key | (required) |
| `DEBUG` | Debug mode | `False` |
| `ALLOWED_HOSTS` | Allowed hostnames | `*` |
| **Database** | | |
| `DATABASE_ENGINE` | `sqlite` or `mariadb` | `sqlite` |
| `DATABASE_NAME` | Database name | `dwc_server.db` |
| `DATABASE_USER` | MariaDB user | `dwc` |
| `DATABASE_PASSWORD` | MariaDB password | `changeme` |
| `DATABASE_ROOT_PASSWORD` | MariaDB root (for GTS) | `rootpassword` |
| **API Authentication** | | |
| `NAS_API_TOKEN` | GameSpy ↔ Django token | (required) |
| **Admin Auto-Creation** | | |
| `DJANGO_SUPERUSER_USERNAME` | Admin username | (optional) |
| `DJANGO_SUPERUSER_PASSWORD` | Admin password | (optional) |
| `DJANGO_SUPERUSER_EMAIL` | Admin email | (optional) |
| **GTS Settings** | | |
| `GTS_DB_NAME` | GTS database | `gts` |
| `GTS_DB_USER` | GTS user | `gts` |
| `GTS_DB_PASSWORD` | GTS password | `gts` |

### Database Options

**SQLite (Default)**

Simple setup, good for testing or small deployments:

```env
DATABASE_ENGINE=sqlite
DATABASE_NAME=dwc_server.db
```

**MariaDB (Recommended for GTS)**

Required for Pokemon GTS functionality:

```env
DATABASE_ENGINE=mariadb
DATABASE_NAME=dwc_server
DATABASE_USER=dwc
DATABASE_PASSWORD=changeme
DATABASE_HOST=mariadb
DATABASE_PORT=3306
DATABASE_ROOT_PASSWORD=rootpassword
```

### Security Keys

**Generate SECRET_KEY**

```bash
# Using Python
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# Using openssl
openssl rand -base64 50
```

**Generate NAS_API_TOKEN**

```bash
# Using Python
python -c "import secrets; print(secrets.token_hex(20))"

# Using openssl
openssl rand -hex 20
```

The NAS_API_TOKEN is automatically registered in Django when the admin container starts.

## Usage

### Nintendo DS Setup

1. **Configure DNS on Nintendo DS/Wii:**
   - Primary DNS: `YOUR_SERVER_IP`
   - Secondary DNS: `8.8.8.8` (optional)

2. **Supported Features:**
   - ⚠️ Mystery Gifts / Wonder Cards - Coming soon
   - ✅ GTS (Global Trade Station)
   - ✅ Battle Tower
   - ⚠️ Wi-Fi Plaza - Coming soon
   - ⚠️ Wi-Fi Club (Player vs Player) - Coming soon
   - & many more ...

### Admin Panel

**Access URL**: `http://your-server:7999/admin/`

**Features**:
- View and manage player profiles
- Monitor active connections
- Ban management (IP, MAC, Profile)
- View friend codes and game sessions
- Server statistics

**First-time Setup**:

1. Set admin credentials in `.env`:
   ```env
   DJANGO_SUPERUSER_USERNAME=admin
   DJANGO_SUPERUSER_PASSWORD=your-secure-password
   DJANGO_SUPERUSER_EMAIL=admin@example.com
   ```

2. Or create manually:
   ```bash
   # Using root docker-compose.yml:
   docker compose exec admin python manage.py createsuperuser

   # Using docker-compose-examples:
   docker compose -f docker-compose.ghcr.yml exec admin python manage.py createsuperuser
   ```

### Managing Services

**Using root docker-compose.yml:**

```bash
# View all containers
docker compose ps

# View logs (all services)
docker compose logs -f

# View specific service logs
docker compose logs -f gamespy
docker compose --profile mariadb logs -f gts

# Restart a service
docker compose restart admin

# Stop all services
docker compose down

# Stop and remove volumes (full reset)
docker compose down -v
```

**Using docker-compose-examples:**

```bash
cd docker-compose-examples

# View all containers
docker compose -f docker-compose.ghcr.yml ps

# View logs (all services)
docker compose -f docker-compose.ghcr.yml logs -f

# View specific service logs
docker compose -f docker-compose.ghcr.yml logs -f gamespy
docker compose -f docker-compose.ghcr-mariadb.yml logs -f gts

# Restart a service
docker compose -f docker-compose.ghcr.yml restart admin

# Stop all services
docker compose -f docker-compose.ghcr.yml down
```

> **Tip**: Replace `docker-compose.ghcr.yml` with your chosen configuration file

### API Access

The REST API is available at `http://your-server:7999/api/`

**Endpoints**:

| Endpoint | Description |
|----------|-------------|
| `/api/profiles/` | Player profiles and friend codes |
| `/api/consoles/` | Registered DS consoles |
| `/api/game-servers/` | Active game servers |
| `/api/sessions/` | Active GP sessions |
| `/api/stats/` | Server statistics |

**Example: Get Profile**

```bash
curl http://localhost:7999/api/profiles/89/
```

Response:
```json
{
  "profile_id": 89,
  "user_id": "...",
  "game_id": "ADAJ",
  "friend_code": "2963-5274-3513",
  "enabled": true
}
```

See [API Documentation](docs/API_DOCUMENTATION.md) for full details.

## GTS (Pokemon Trading)

The Global Trade Station allows Pokemon trading between players.

**Important**: GTS requires MariaDB and cannot run with SQLite.

### Enable GTS

**Using root docker-compose.yml:**

```bash
docker compose --profile mariadb up -d
```

**Using docker-compose-examples (GHCR Images - Production):**

```bash
cd docker-compose-examples
docker compose -f docker-compose.ghcr-mariadb.yml up -d
```

**Using docker-compose-examples (Local Builds - Development):**

```bash
cd docker-compose-examples
docker compose -f docker-compose.dev.yml --profile mariadb up -d
```

The GTS server will automatically:
1. Create the GTS database and user
2. Import the Pokemon database schema (721 Pokemon, 639 moves)
3. Start the Mono/.NET GTS application

> See [docker-compose-examples/README.md](docker-compose-examples/README.md) for detailed GTS configuration options.

### Supported Pokemon Games

#### Generation 4 (Nintendo DS)

| Game | Region | Game ID | Status |
|------|--------|---------|--------|
| Pokémon Diamond | ALL | ADA | ✅ Supported |
| Pokémon Diamond | USA | ADAE | ✅ Supported |
| Pokémon Diamond | EUR | ADAP | ✅ Supported |
| Pokémon Diamond | JPN | ADAJ | ✅ Supported |
| Pokémon Pearl | ALL | APA | ✅ Supported |
| Pokémon Pearl | USA | APAE | ✅ Supported |
| Pokémon Pearl | EUR | APAP | ✅ Supported |
| Pokémon Pearl | JPN | APAJ | ✅ Supported |
| Pokémon Platinum | ALL | CPU | ✅ Supported |
| Pokémon Platinum | USA | CPUE | ✅ Supported |
| Pokémon Platinum | EUR | CPUP | ✅ Supported |
| Pokémon Platinum | JPN | CPUJ | ✅ Supported |
| Pokémon HeartGold | ALL | IPK | ✅ Supported |
| Pokémon HeartGold | USA | IPKE | ✅ Supported |
| Pokémon HeartGold | EUR | IPKP | ✅ Supported |
| Pokémon HeartGold | JPN | IPKJ | ✅ Supported |
| Pokémon SoulSilver | ALL | IPG | ✅ Supported |
| Pokémon SoulSilver | USA | IPGE | ✅ Supported |
| Pokémon SoulSilver | EUR | IPGP | ✅ Supported |
| Pokémon SoulSilver | JPN | IPGJ | ✅ Supported |

#### Generation 5 (Nintendo DS)

| Game | Region | Game ID | Status |
|------|--------|---------|--------|
| Pokémon Black | ALL | IRB | ✅ Supported |
| Pokémon Black | USA | IRBO | ✅ Supported |
| Pokémon Black | EUR | IRBP | ✅ Supported |
| Pokémon Black | JPN | IRBJ | ✅ Supported |
| Pokémon White | ALL | IRA | ✅ Supported |
| Pokémon White | USA | IRAO | ✅ Supported |
| Pokémon White | EUR | IRAP | ✅ Supported |
| Pokémon White | JPN | IRAJ | ✅ Supported |
| Pokémon Black 2 | ALL | IRE | ✅ Supported |
| Pokémon Black 2 | USA | IREO | ✅ Supported |
| Pokémon Black 2 | EUR | IREP | ✅ Supported |
| Pokémon Black 2 | JPN | IREJ | ✅ Supported |
| Pokémon White 2 | ALL | IRD | ✅ Supported |
| Pokémon White 2 | USA | IRDO | ✅ Supported |
| Pokémon White 2 | EUR | IRDP | ✅ Supported |
| Pokémon White 2 | JPN | IRDJ | ✅ Supported |

*also supported with other game IDs.*

### How GTS Works

The GTS uses [pkmn-classic-framework](https://github.com/mm201/pkmn-classic-framework) running on Mono/.NET:

1. DS connects to `gamestats2.gs.nintendowifi.net`
2. Apache proxies request to GTS container (:9002)
3. GTS processes request using MariaDB
4. Pokemon data stored/retrieved from `gts` database

## Troubleshooting

### Error Code 52200 - Connection Failed

**Problem**: DS shows error 52200 after configuring Wi-Fi.

**Solution**: Restart the DS after initial Wi-Fi configuration. This is required for the DS to properly connect to the server.

### Error Code 20110 - Server Unavailable

**Problem**: DS can't connect to server.

**Debug**:
```bash
# Check services
docker compose ps

# Check DNS resolution
nslookup nas.nintendowifi.net YOUR_SERVER_IP
```

**Solutions**:
- Verify DNS points to your server
- Ensure ports 80, 443, 29900, 27900 are open
- Check Apache logs: `docker compose logs dwc-apache`

### Error Code 61010 - Authentication Failed

**Problem**: Login fails with error 61010.

**Debug**:
```bash
docker compose logs dwc-admin | grep -i token
docker compose logs dwc-gamespy | grep -i 401
```

**Solutions**:
- Verify `NAS_API_TOKEN` is set in `.env`
- Restart admin container: `docker compose restart dwc-admin`
- Check token in Django admin → Tokens

### GTS Connection Aborted

**Problem**: "Failed to Connect to the GTS"

**Debug**:
```bash
docker compose ps dwc-gts
docker compose logs dwc-gts | grep -i error
```

**Solutions**:
- Use MariaDB profile: `docker compose --profile mariadb up -d`
- Check GTS initialization: `docker compose logs dwc-gts | grep -i success`
- Verify MariaDB is healthy: `docker compose ps dwc-mariadb`

### Further Troubleshooting

See the [DWC Network Server Emulator Wiki](https://github.com/barronwaffles/dwc_network_server_emulator/wiki/Troubleshooting) for additional help.

## Supported Games

Any Nintendo DS or Wii game using Nintendo Wi-Fi Connection:

- **Pokemon**: Diamond, Pearl, Platinum, HeartGold, SoulSilver, Black, White, B2, W2
- **Mario Kart**: DS, Wii
- **Animal Crossing**: Wild World, City Folk
- **Metroid Prime**: Hunters
- **Tetris DS**
- **And many more...**

## Project Structure

```
dwc-server-python3/
├── admin_panel/           # Django Admin Panel
│   ├── dwc_admin/         # Models, admin interface
│   └── dwc_api/           # REST API endpoints
├── dwc_server/            # GameSpy Server (Python)
│   ├── servers/           # NAS, GP, QR implementations
│   └── utils/             # Friend code, crypto utilities
├── gts/                   # GTS SQL dump
├── docker/                # Dockerfiles and entrypoints
│   ├── Dockerfile.*       # Container definitions
│   └── entrypoints/       # Startup scripts
├── apache-configs/        # Virtual host configurations
├── dnsmasq/               # DNS configuration
├── docs/                  # Additional documentation
├── requirements/          # Python dependencies
└── tests/                 # Test suites
```

## Documentation

- **[Docker Compose Examples](docker-compose-examples/README.md)** - Deployment configurations (GHCR, MariaDB, Development)
- **[GitHub Actions Workflows](.github/workflows/README.md)** - CI/CD, GHCR deployment, PR testing
- [Docker Setup Guide](docs/DOCKER_GUIDE.md) - Detailed Docker configuration
- [GameSpy Protocol Reference](docs/GAMESPY_RESOURCES_AND_GOAL_TRACKER.md) - Protocol implementation details
- [API Documentation](docs/API_DOCUMENTATION.md) - REST API reference

## Legal Notice / Disclaimer

This project is an independent, non-commercial fan project for game preservation and educational purposes. It is not affiliated with, endorsed by, or connected to Nintendo Co., Ltd., The Pokémon Company, Game Freak, or any of their subsidiaries.

### Important Legal Information

- **No Commercial Use**: This server is provided free of charge for personal, non-commercial use only
- **Educational Purpose**: Created for learning about network protocols and game preservation
- **No Official Content**: Does not distribute, host, or provide any Nintendo proprietary software, ROMs, or game files
- **Legitimate Ownership**: Users must own legitimate copies of the games they wish to use with this server
- **Trademark Notice**: All trademarks, service marks, trade names, and logos referenced are the property of their respective owners

### Warranty Disclaimer

This software is provided "as is" without warranty of any kind, express or implied. Use at your own risk.

### Takedown Policy

If you represent Nintendo, The Pokémon Company, or any related entity and have concerns about this project, please contact [me](#made-with-️-for-pokémon-preservation) before taking legal action. I will cooperate fully with any legitimate requests.

### License

This project is licensed under the GPL-3.0 License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [pkmn-classic-framework](https://github.com/mm201/pkmn-classic-framework) - Pokemon GTS implementation
- [dwc_network_server_emulator](https://github.com/barronwaffles/dwc_network_server_emulator) - Original DWC research
- Nintendo DS homebrew community for protocol documentation

---

## **Made with ❤️ for Pokémon preservation**

**Mission**: Preserve Nintendo Wi-Fi Connection functionality for retro gaming enthusiasts.

For issues and contributions, please visit: [GitHub Repository](https://github.com/jonathan-priebe/pkmn-wfc-server-docker-setup)

- 📫 Reach me via GitHub or [LinkedIn](https://www.linkedin.com/in/jonathan-p-34471b1a5/)
