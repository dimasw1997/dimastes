#!/usr/bin/env bash
# Skrip bantu macOS/Linux: siapkan .venv, pasang dependensi, lalu jalankan CLI.
# Contoh: ./jalankan.sh run
#         ./jalankan.sh config
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -x ".venv/bin/python" ]; then
    echo "[1/3] Membuat virtual environment..."
    python3 -m venv .venv
fi

echo "[2/3] Memasang dependensi..."
".venv/bin/python" -m pip install --quiet --upgrade pip
".venv/bin/python" -m pip install --quiet -r requirements.txt

if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    cp .env.example .env
    echo "File .env dibuat dari .env.example. Sesuaikan dulu bila perlu."
fi

echo "[3/3] Menjalankan program..."
echo
exec ".venv/bin/python" cli.py "$@"
