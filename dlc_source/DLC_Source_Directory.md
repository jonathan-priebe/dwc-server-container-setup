# DLC Source Directory

This directory contains Nintendo DS/Wii DLC files (.myg) for Mystery Gift distribution from the [Pokémon Event Archiver Pipeline](https://github.com/jonathan-priebe/pkmn-event-archiver-pipeline), which aggregates and processes event data from Project Pokémon, Bulbapedia, and PokéWiki.

**Mystery Gifts are fully functional!** The DLS1 server automatically distributes gifts to Pokemon games (Diamond, Pearl, Platinum, HeartGold, SoulSilver, Black, White, etc.) with cross-region support.

## Setup

The DLC files are included in this repository via Git Subtree from the [Pokémon Event Archiver Pipeline](https://github.com/jonathan-priebe/pkmn-event-archiver-pipeline).

When you clone this repository, the DLC files are automatically included in `dlc_source/dlc/`.

## Structure

```
dlc_source/
└── dlc/
    ├── CPUE/          # Pokemon Platinum (USA)
    │   └── *.myg      # Mystery Gift files
    ├── IRBE/          # Pokemon Black (USA)
    ├── IPGE/          # Pokemon SoulSilver (USA)
    └── ...            # Other game IDs (20+ games)
```

## Importing to Django

To import all .myg files into the Django admin panel:

```bash
# From project root
docker compose exec admin python manage.py import_mystery_gifts

# Or from within the container
docker compose exec admin bash
cd /app
python manage.py import_mystery_gifts
```

### Import Options

```bash
# Dry run - see what would be imported
python manage.py import_mystery_gifts --dry-run

# Import only specific game
python manage.py import_mystery_gifts --game-id CPUE

# Overwrite existing gifts
python manage.py import_mystery_gifts --overwrite
```

## Updating DLC Files

To update the DLC files from the Event Archiver Pipeline:

```bash
# From repository root
git subtree pull --prefix=dlc_source \
  https://github.com/jonathan-priebe/pkmn-event-archiver-pipeline.git main \
  --squash
```

Then re-run the import command with `--overwrite` to update existing gifts in Django:

```bash
docker compose exec admin python manage.py import_mystery_gifts --overwrite
```

## Game IDs

See the [Wiki](https://github.com/barronwaffles/dwc_network_server_emulator/wiki/Nintendo-DS-Download-Content) for full list of game IDs.

Common game IDs:
- `CPUE` - Pokemon Platinum (USA)
- `CPUJ` - Pokemon Platinum (Japan)
- `IPKE` - Pokemon HeartGold (USA)
- `IPGE` - Pokemon SoulSilver (USA)
- `IRBE` - Pokemon Black (USA)
- `IRAE` - Pokemon White (USA)
- `RMCE` - Mario Kart Wii (USA)

## Distribution Features

### Cross-Region Gift Sharing

Games from the same family share ALL gifts across ALL regions:

- **Diamond/Pearl**: All regions (USA, EUR, JPN, etc.) share the same gift pool
- **Platinum**: All regions share gifts
- **HeartGold/SoulSilver**: All regions share gifts
- **Black/White**: All regions share gifts

Example: If you import gifts for Platinum USA (CPUE) and Platinum Japan (CPUJ), both regions will have access to all gifts from both regions.

### Distribution Modes

Configure how gifts are distributed per game in the Django admin:

1. **Random** (Default for Pokemon): Pick one random gift from available pool
2. **Priority**: Show highest priority gift first
3. **All**: Show all available gifts (for non-Pokemon games)

### Download Tracking

- Tracks which gifts each user has already received
- Prevents duplicate downloads (configurable per game)
- Optional reset when user has received all gifts

### Managing Gifts

In the Django Admin Panel (`http://your-server:7999/admin/dwc_admin/mysterygift/`):

- **Enable/Disable** gifts directly in the table (checkbox column)
- **Bulk Actions**:
  - "✓ Enable selected gifts" - Enable only selected gifts
  - "✗ Disable selected gifts" - Disable only selected gifts
  - "✓✓ ENABLE ALL GIFTS" - Enable ALL gifts at once
  - "✗✗ DISABLE ALL GIFTS" - Disable ALL gifts at once
- **Edit Priority** directly in the table
- **Set Date Ranges** for timed events (start_date/end_date)

## Notes

- DLC files are included in the repository via Git Subtree (no separate setup needed)
- Files are imported into Django's media directory via the `import_mystery_gifts` command
- Original files remain in `dlc_source/dlc/` for reference
- Mystery Gifts are served via DLS1 server on port 9003 (proxied through Apache)
- Downloads work with original Nintendo DS/DSi hardware
- To update DLC files, use `git subtree pull` (see Updating section above)
