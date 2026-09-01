#!/usr/bin/env bash
# Telecharge et extrait les 32 roulements Paderborn (KAt-DataCenter).
# ~5.4 Go au total. Necessite `unar` (brew install unar).
set -euo pipefail

BASE_URL="https://groups.uni-paderborn.de/kat/BearingDataCenter"
RAW_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/data/raw/paderborn"

CODES=(
  K001 K002 K003 K004 K005 K006
  KA01 KA03 KA04 KA05 KA06 KA07 KA08 KA09 KA15 KA16 KA22 KA30
  KB23 KB24 KB27
  KI01 KI03 KI04 KI05 KI07 KI08 KI14 KI16 KI17 KI18 KI21
)

mkdir -p "$RAW_DIR"

for code in "${CODES[@]}"; do
  archive="$RAW_DIR/${code}.rar"
  if [ -d "$RAW_DIR/${code}" ]; then
    echo "[skip] ${code} deja extrait"
    continue
  fi
  echo "[download] ${code}"
  curl -sS --fail --retry 3 -o "$archive" "${BASE_URL}/${code}.rar"
  echo "[extract] ${code}"
  unar -quiet -output-directory "$RAW_DIR" "$archive"
  rm -f "$archive"
done

echo "Termine. Roulements dans: $RAW_DIR"
