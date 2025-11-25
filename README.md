# Pkmn Event Archiver/Pipeline-Converter

This project **automates the processing of event files** (such as `.pcd`, `.pgf`, `.wc4`, `.wc5`, and similar) for the **Nintendo DS/Wii generation Pokémon games (Gen IV & Gen V)**.

The pipeline uses a central **CSV database (`events.csv`)** to automatically assign events to the correct **GameCodes** and **Regions** and generate the ready-to-use game files.

## Table of Contents

- [Quick Start](#quick-start)
- [Structure](#structure)
    - [File Components](#file-components)
    - [Structure of `events.csv`](#detail-structure-of-eventscsv)
- [How It Works](#how-it-works)
    - [CSV Check (Primary)](#1-csv-check-primary)
    - [Fallback (YAML) – Secondary](#2-fallback-yaml--secondary)
- [Usage](#usage)
    - [Command Execution](#command-execution)
    - [I/O Types](#io-types)
    - [Assignment Examples](#assignment-examples)
- [Docker Configuration](#docker-configuration)
    - [Services](#services)
    - [Volumes](#volumes)
    - [Environment Variables](#environment-variables)
    - [Web Interface](#web-interface)
- [Data Sources](#data-sources--credits)
- [Contributing](#contributing)
- [License](#license)

---

## Quick Start

The fastest way to get started is using Docker Compose:

```bash
# Clone the repository
git clone <repository-url>
cd Pkmn-Event-Archiver-Pipeline

# Start all services
docker-compose up -d

# Access the web interface
open http://localhost:8080
```

This will:
- Start the **mg-pipeline** service to process event files
- Start the **mg-web** service for the web interface
- Create a shared volume `mg-dlc` for processed files
- Make the web interface available at `http://localhost:8080`

---

## Structure

### File Components

| File | Purpose | Details |
| :--- | :--- | :--- |
| `events.csv` | **Central Event Database** | Contains all known Gen IV & Gen V Pokémon events. |
| `mapping.yml` | **Fallback Rules** | Stores **Regex patterns** for events not found in the CSV (to ensure robustness). |
| `mg_pipeline.py` | **Main Script** | Processes input files and generates the final `.myg` outputs. |

### Detail: Structure of `events.csv`

The CSV database defines the mapping using the following key columns:

* **`EventName`**: The clear name of the event (e.g., `Movie Darkrai 2007`).
* **`GameCodes`**: The target games for which the event is valid (e.g., `ADAE, CPUE`).
* **`Regions`**: The regions where the event was distributed (e.g., `JPN, USA, EUR`).
* **`Year`**: The year of distribution.

---

## How It Works

The processing follows a **two-stage process** to ensure maximum reliability in mapping event files.

### 1. CSV Check (Primary)

1.  The pipeline loads `events.csv`.
2.  **Tokens** are extracted from the input file's name.
3.  If an **`EventName`** is found in the CSV, it is assigned to all listed **`GameCodes`**.

#### Multi-Target Events

**Example:**

```csv
Movie Darkrai 2007,"ADAE,CPUE","JPN,USA,EUR",2007
```
Result: A .myg file is generated in both DLC/ADAE/ and DLC/CPUE/.

### 2. Fallback (YAML) – Secondary

If no CSV match is found, Regex rules from mapping.yml are applied to enforce a GameCode assignment.
This ensures robustness for new or unknown events.

---

## Usage

The main script is executed via the command line and requires the paths to the configuration files and the converter binary.

### Command Execution
```bash
python mg_pipeline.py \
    --events-csv config/events.csv \
    --mapping config/mapping.yml \
    --bin-mgc bin/mgc_converter
```

### I/O Types

| I/O Type | Description |
| :--- | :--- |
| **Input** | Event files (`.pcd`, `.pgf`, `.wc4`, `.wc5`) |
| **Output** | `.myg` files, stored in the respective `DLC/<GameCode>/` folders |

### Assignment Examples

| Input Filename | CSV Match (Example) | Output Path |
| :--- | :--- | :--- |
| `059 GameStop Raikou ENG [PPorg].pcd` | `GameStop Raikou, "IPGE", "USA, EUR", 2011` | `DLC/IPGE/059 GameStop Raikou ENG [PPorg].myg` |
| `028 McDonald's Pikachu JPN [PPorg].pcd` | `McDonald's Pikachu, "IPGE", "JPN", 2010` | `DLC/IPGE/028 McDonald's Pikachu JPN [PPorg].myg` |

---

## Docker Configuration

### Services

#### mg-pipeline
The main processing service that converts event files to `.myg` format.

#### mg-web
Web interface for browsing and managing processed event files.

### Volumes

#### mg-dlc (Shared Volume)
A Docker named volume that stores all processed `.myg` files. This volume is shared between both services:
- **mg-pipeline** writes processed files to this volume
- **mg-web** reads from this volume (read-only access)

### Environment Variables

#### Common Variables
| Variable | Default | Description |
| :--- | :--- | :--- |
| `OUTPUT_DIR` | `/work/DLC` | Directory where processed files are stored |

#### mg-pipeline Specific
| Variable | Default | Description |
| :--- | :--- | :--- |
| `ARCHIVE_URL` | Project Pokémon URL | Source URL for event files |
| `ENABLE_MAPPING_OVERRIDE` | `"true"` | Enable YAML fallback mapping |
| `INPUT_EXTS` | `".pcd,.pgt,.pgf,.wc4,.wc5"` | Accepted file extensions |
| `WORKERS` | `"4"` | Number of parallel processing workers |

### Web Interface

The web interface provides:
- **Browse** processed event files by game code
- **Download** individual `.myg` files

**Access:** `http://localhost:8080`

**Port Configuration:** The service maps port `8080` from the container to the host.

---

## Data Sources & Credits

**Event Data Sources**
* [Project Pokémon – Gen IV Event Collection](https://projectpokemon.org) - Community-driven event file archive
* [Bulbapedia – Event Pokémon Distributions](https://bulbapedia.bulbagarden.net) - Comprehensive Pokémon encyclopedia with event documentation
* [PokéWiki – Events 4th & 5th Generation](https://pokewiki.de) - German Pokémon wiki with event information

**Tool & Converter**
* [MysteryGiftConverter](https://github.com/AdmiralCurtiss/MysteryGiftConvert) - Core conversion tool for processing event files

### Community Contributions
This project builds upon the work of the Pokémon community event archiving efforts. Special thanks to:
- Event file collectors and preservers
- Documentation contributors across various Pokémon wikis
- Tool developers who make event file processing possible

---

## Contributing

* Always add new events first to **`events.csv`**.
* Use **consistent naming conventions**: `Movie <Pokémon> <Year>` or `Pokémon Center <Pokémon>`.
* Each entry should have only **one year** (e.g., `2010`) and **no year ranges** (e.g., `2010-2013`).
* Pull Requests are welcome!

---

## License

Community project for archiving and processing Pokémon events. All event files come from publicly documented sources (Bulbapedia, Project Pokémon, PokéWiki).