#!/usr/bin/env bash
# ═══ Escalera 50K · instalación en un servidor Ubuntu (Oracle Cloud Always Free u otro VPS) ═══
# Uso (en el servidor):
#   curl -fsSL https://raw.githubusercontent.com/<TU_USUARIO>/escalera50k/main/scripts/instalar_servidor.sh | bash -s -- https://github.com/<TU_USUARIO>/escalera50k.git
set -euo pipefail
REPO="${1:-}"
DESTINO=/opt/escalera50k
[ -z "$REPO" ] && { echo "Uso: instalar_servidor.sh <url-del-repo-git>"; exit 1; }

echo "▶ 1/6 Paquetes del sistema"
sudo apt-get update -y
sudo apt-get install -y ca-certificates curl git ufw

echo "▶ 2/6 Docker"
if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
fi

echo "▶ 3/6 Código"
sudo mkdir -p "$DESTINO" && sudo chown "$USER" "$DESTINO"
if [ -d "$DESTINO/.git" ]; then git -C "$DESTINO" pull --ff-only; else git clone "$REPO" "$DESTINO"; fi
cd "$DESTINO"

echo "▶ 4/6 Configuración (.env)"
if [ ! -f .env ]; then
  cp .env.example .env
  read -rp "Token del bot de Telegram: " TOKEN; sed -i "s|^TOKEN_BOT=.*|TOKEN_BOT=$TOKEN|" .env
  read -rp "Clave API de Claude (sk-ant-...): " KEY; sed -i "s|^ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=$KEY|" .env
  read -rp "Dominio del panel (ej. escalera.dctecnology.xyz): " DOM; sed -i "s|^DOMINIO=.*|DOMINIO=$DOM|" .env
  read -rp "Saldo actual en BetPlay (ej. 100000): " BAN; sed -i "s|^BANCA_INICIAL=.*|BANCA_INICIAL=${BAN:-100000}|" .env
  read -rsp "Clave para entrar al panel web: " PW; echo
  HASH=$(sudo docker run --rm caddy:2.8 caddy hash-password --plaintext "$PW")
  sed -i "s|^PANEL_HASH=.*|PANEL_HASH='$HASH'|" .env
  chmod 600 .env
fi
mkdir -p datos/panel datos/respaldos && sudo chown -R 1000:1000 datos

echo "▶ 5/6 Firewall (SSH, HTTP, HTTPS)"
sudo ufw allow OpenSSH && sudo ufw allow 80/tcp && sudo ufw allow 443/tcp && sudo ufw --force enable
# Las imágenes Ubuntu de Oracle traen reglas iptables propias: se abren 80 y 443
if sudo iptables -L INPUT -n | grep -q "REJECT"; then
  sudo iptables -I INPUT 5 -p tcp --dport 80 -j ACCEPT
  sudo iptables -I INPUT 5 -p tcp --dport 443 -j ACCEPT
  sudo sh -c 'command -v netfilter-persistent >/dev/null && netfilter-persistent save || true'
fi

echo "▶ 6/6 Arranque"
sudo docker compose up -d --build
sleep 15
sudo docker compose ps
echo
echo "✅ Listo. Escríbele /start a tu bot en Telegram."
echo "   Panel: https://$(grep ^DOMINIO= .env | cut -d= -f2)   (registro A del dominio → IP de este servidor)"
echo "   Logs:  cd $DESTINO && sudo docker compose logs -f bot"
