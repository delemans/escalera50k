#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════
#  Escalera 50K · instalación automática SIN PC (Oracle Cloud → "Initialization script")
#  1) Llena los 6 datos de abajo.  2) Pega TODO este texto al crear la instancia.
#  3) Espera ~10 minutos. El progreso queda en /var/log/escalera-instalacion.log
#  Nota: este texto queda guardado en la consola de Oracle (solo tú lo ves). Cuando
#  termine, puedes cambiar la clave de Claude si quieres más seguridad.
# ═══════════════════════════════════════════════════════════════════════
REPO="https://github.com/Delemans/escalera50k.git"
TOKEN_BOT="PEGA_AQUI_EL_TOKEN_DEL_BOT"
ANTHROPIC_API_KEY="PEGA_AQUI_LA_CLAVE_DE_CLAUDE"
DOMINIO="escalera.dctecnology.xyz"
BANCA_INICIAL="100000"
PANEL_CLAVE="ELIGE_UNA_CLAVE_PARA_EL_PANEL"
# ═══════════════════════ no cambies nada debajo ═══════════════════════
set -euo pipefail
exec > /var/log/escalera-instalacion.log 2>&1
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y git curl ca-certificates iptables-persistent
curl -fsSL https://get.docker.com | sh
usermod -aG docker ubuntu || true

DEST=/opt/escalera50k
[ -d "$DEST/.git" ] || git clone "$REPO" "$DEST"
cd "$DEST"
HASH=$(docker run --rm caddy:2.8 caddy hash-password --plaintext "$PANEL_CLAVE")
cat > .env <<ENV
TOKEN_BOT=$TOKEN_BOT
ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY
CLAUDE_MODEL=claude-sonnet-4-5
CHAT_ID=
CANAL_DATOS=
BANCA_INICIAL=$BANCA_INICIAL
UNIDAD_PCT=0.02
TOPE_DIARIO_PCT=0.12
APUESTA_MINIMA=1000
BANCA_ALERTA_PCT=0.70
AVISO_MIN_ANTES=60,15
PREGUNTAR_MIN_DESPUES=5
RACHA_ALERTA=3
SILENCIO=23:00-06:30
DOMINIO=$DOMINIO
PANEL_USUARIO=admin
PANEL_HASH='$HASH'
VOZ=0
ENV
chmod 600 .env
mkdir -p datos/panel datos/respaldos && chown -R 1000:1000 datos
git config --system --add safe.directory "$DEST"

# Firewall de las imágenes Ubuntu de Oracle: abrir 80 y 443
iptables -I INPUT 5 -p tcp --dport 80 -m state --state NEW -j ACCEPT
iptables -I INPUT 5 -p tcp --dport 443 -m state --state NEW -j ACCEPT
netfilter-persistent save

docker compose up -d --build

# Actualización automática desde GitHub cada 10 minutos (no depende de ningún archivo del repo)
cat > /usr/local/bin/escalera-actualizar <<'UPD'
#!/usr/bin/env bash
set -euo pipefail
cd /opt/escalera50k
git fetch -q origin main
if [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]; then
  echo "$(date -Is) actualizando a $(git rev-parse --short origin/main)" >> datos/actualizaciones.log
  git pull -q --ff-only origin main
  docker compose up -d --build >> datos/actualizaciones.log 2>&1
  docker image prune -f >> datos/actualizaciones.log 2>&1
fi
UPD
chmod +x /usr/local/bin/escalera-actualizar
echo "*/10 * * * * root /usr/local/bin/escalera-actualizar" > /etc/cron.d/escalera50k
echo "✅ INSTALACIÓN TERMINADA $(date -Is)"
