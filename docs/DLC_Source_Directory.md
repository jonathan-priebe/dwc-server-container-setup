# DLC Source Directory

This directory contains Nintendo DS/Wii DLC files (.myg) for Mystery Gift distribution from the original dwc_network_server_emulator repository, using Git sparse checkout to only include the `/dlc` directory.

**Mystery Gifts are fully functional!** The DLS1 server automatically distributes gifts to Pokemon games (Diamond, Pearl, Platinum, HeartGold, SoulSilver, Black, White, etc.) with cross-region support.

## Setup

This directory should be created automatically using:

```bash
# Create sparse checkout of only the /dlc directory
mkdir -p dlc_source
cd dlc_source
git init
git remote add origin https://github.com/jonathan-priebe/dwc_network_server_emulator.git
git config core.sparseCheckout true
echo "dlc/*" > .git/info/sparse-checkout
git pull origin master
```

## Structure

```
dlc_source/
└── dlc/
    ├── CPUE/          # Pokemon Platinum (USA)
    │   ├── *.myg      # Mystery Gift files
    │   └── _list.txt  # File listing
    ├── IRBE/          # Pokemon Black (USA)
    └── ...            # Other game IDs
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

## Updating

To update the DLC files from upstream:

```bash
cd dlc_source
git pull origin master
```

Then re-run the import command with `--overwrite` to update existing gifts.

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

- This directory is in `.gitignore` - each developer/deployment needs to set it up locally
- Files are stored in Django's media directory after import
- Original files remain in `dlc_source/dlc/` for reference
- Mystery Gifts are served via DLS1 server on port 9003 (proxied through Apache)
- Downloads work with original Nintendo DS/DSi hardware
