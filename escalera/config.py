"""
CONFIGURACIÓN · variables de entorno (archivo .env o Docker)
"""
from __future__ import annotations

import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _cargar_env():
    f = Path(os.environ.get("ENV_FILE", RAIZ / ".env"))
    if f.exists():
        for linea in f.read_text(encoding="utf-8").splitlines():
            linea = linea.strip()
            if linea and not linea.startswith("#") and "=" in linea:
                k, v = linea.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_cargar_env()


def _int(k, d):
    try:
        return int(os.environ.get(k, d))
    except ValueError:
        return d


def _float(k, d):
    try:
        return float(os.environ.get(k, d))
    except ValueError:
        return d


TOKEN_BOT = os.environ.get("TOKEN_BOT", "")
CHAT_ID = os.environ.get("CHAT_ID", "")
CANAL_DATOS = os.environ.get("CANAL_DATOS", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODELO = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-5")
SITIO = os.environ.get("SITIO", "https://claude.ai/artifact/9iFSG3bVbk7GZZCJKfxMoa")
DOMINIO = os.environ.get("DOMINIO", "")
TZ = os.environ.get("TZ_BOT", "America/Bogota")

BANCA_INICIAL = _float("BANCA_INICIAL", 100_000)
UNIDAD_PCT = _float("UNIDAD_PCT", 0.02)
TOPE_DIARIO_PCT = _float("TOPE_DIARIO_PCT", 0.12)
APUESTA_MINIMA = _float("APUESTA_MINIMA", 1_000)
BANCA_ALERTA_PCT = _float("BANCA_ALERTA_PCT", 0.70)
AVISO_MIN_ANTES = [int(x) for x in os.environ.get("AVISO_MIN_ANTES", "60,15").split(",") if x.strip()]
PREGUNTAR_MIN_DESPUES = _int("PREGUNTAR_MIN_DESPUES", 5)
RACHA_ALERTA = _int("RACHA_ALERTA", 3)
SILENCIO = os.environ.get("SILENCIO", "23:00-06:30")   # sin recordatorios en ese horario

DATOS = Path(os.environ.get("DATOS_DIR", RAIZ / "datos"))
PANEL = Path(os.environ.get("PANEL_DIR", DATOS / "panel"))
for d in (DATOS, PANEL, DATOS / "respaldos"):
    d.mkdir(parents=True, exist_ok=True)
