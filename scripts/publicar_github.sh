#!/usr/bin/env bash
# Publica este proyecto como repositorio PÚBLICO en tu GitHub (requiere gh: https://cli.github.com)
# Uso:  bash scripts/publicar_github.sh escalera50k
set -euo pipefail
NOMBRE="${1:-escalera50k}"
cd "$(dirname "$0")/.."
[ -f .env ] && grep -q "^TOKEN_BOT=." .env && echo "ℹ️  .env existe pero está en .gitignore: NO se sube."
gh auth status >/dev/null 2>&1 || gh auth login
[ -d .git ] || git init -b main
git add -A
git commit -m "Escalera 50K v2" || true
gh repo create "$NOMBRE" --public --source . --remote origin --push \
  --description "Mesa de análisis por valor esperado + bot de Telegram. Sin fijas, con estadística."
echo "✅ Publicado: $(gh repo view --json url -q .url)"
echo "Siguiente: Settings → Secrets → Actions → SERVIDOR_IP, SERVIDOR_USUARIO, SERVIDOR_LLAVE_SSH"
