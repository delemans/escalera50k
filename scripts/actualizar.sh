#!/usr/bin/env bash
# Actualización automática (la corre cron cada 10 min en el servidor):
# si hay cambios en GitHub, los baja, reconstruye y reinicia el bot. No necesita PC ni llaves SSH.
set -euo pipefail
cd /opt/escalera50k
LOG=datos/actualizaciones.log
git fetch -q origin main
if [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]; then
  echo "$(date -Is) actualizando a $(git rev-parse --short origin/main)" >> "$LOG"
  git pull -q --ff-only origin main
  docker compose up -d --build >> "$LOG" 2>&1
  docker image prune -f >> "$LOG" 2>&1
fi
