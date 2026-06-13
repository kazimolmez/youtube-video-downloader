#!/usr/bin/env bash
# YouTube İndirici'yi başlatır. Sanal ortamı yoksa kurar.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "Sanal ortam kuruluyor…"
  python3 -m venv .venv
  ./.venv/bin/python -m pip install --upgrade pip
  ./.venv/bin/python -m pip install -r requirements.txt
fi

exec ./.venv/bin/python -m youtube_downloader.app
