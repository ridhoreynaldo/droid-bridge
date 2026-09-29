#!/usr/bin/env bash
# Cara gampang jalanin droid-bridge: ./start.sh
# (Windows: klik dua kali start.bat)
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f .env ]; then
  cp .env.example .env
  echo ">> .env dibuat dari .env.example — isi BRIDGE_TOKEN dulu kalau mau di-expose ke internet"
fi

# python3 atau python, mana yang ada
if command -v python3 >/dev/null; then PY=python3; else PY=python; fi

echo ">> buka http://localhost:${PORT:-3000} (lihat PORT di .env)"
$PY bridge.py
