#!/usr/bin/env bash
set -euo pipefail

ARCHIVE_URL="${ARCHIVE_URL:-}"
OUTPUT_DIR="${OUTPUT_DIR:-/work/DLC}"

mkdir -p /work/tmp /work/input "$OUTPUT_DIR"

echo "[mg] Downloading archive: ${ARCHIVE_URL}"
curl -L --fail "$ARCHIVE_URL" -o /work/tmp/archive.zip

echo "[mg] Extracting..."
unzip -oq /work/tmp/archive.zip -d /work/input

echo "[mg] Converting & organizing..."
python3 /work/mg_pipeline.py \
  --input-root /work/input \
  --output-root "$OUTPUT_DIR" \
  --bin-mgc /work/bin/MysteryGiftConvert \
  --exts "${INPUT_EXTS:-.pcd,.pgt,.pgf,.wc4,.wc5}" \
  --workers "${WORKERS:-4}" \
  --mapping "/work/config/mapping.yml" \
  ${ENABLE_MAPPING_OVERRIDE:+--enable-mapping-override}

echo "[mg] Done."
