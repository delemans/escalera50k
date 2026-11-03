#!/usr/bin/env bash
# Corre el bot en tu PC (Linux/Mac) sin Docker. En Windows usa correr_local.bat
set -e
cd "$(dirname "$0")/.."
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q -e .
[ -f .env ] || { cp .env.example .env; echo "Llena el archivo .env y vuelve a correr."; exit 1; }
python -m escalera.bot.app
