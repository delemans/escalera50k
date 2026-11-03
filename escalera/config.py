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
CHAT_ID = os.environ.get("CHAT_ID", "8695188020")    # dueño del bot (manda sobre lo guardado)
CANAL_DATOS = os.environ.get("CANAL_DATOS", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODELO = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-5")
# IA gratis y balanceo (se usa el primero con clave; si falla, el siguiente)
IA_ORDEN = os.environ.get("IA_ORDEN", "gemini,groq,openrouter,anthropic")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")
GEMINI_MODELO = os.environ.get("GEMINI_MODEL", "")           # vacío = se elige solo
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODELO = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
GROQ_MODELO_VISION = os.environ.get("GROQ_VISION_MODEL", "")
GROQ_RESPALDOS = [m for m in os.environ.get("GROQ_FALLBACKS", "openai/gpt-oss-20b,qwen/qwen3.8-27b").split(",") if m]
GEMINI_RESPALDOS = [m for m in os.environ.get(
    "GEMINI_FALLBACKS", "gemini-3-flash-preview,gemini-flash-latest,gemini-3.1-flash-lite,gemini-flash-lite-latest").split(",") if m]
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODELO = os.environ.get("OPENROUTER_MODEL", "google/gemma-4-31b-it:free")
OPENROUTER_VISION = os.environ.get("OPENROUTER_VISION", "0") == "1"
SITIO = os.environ.get("SITIO", "https://script.google.com/macros/s/AKfycbzAte1NoObySREqwPgx8RcYeXTcz161l0gXV63wRJ5ouMaQJMVRb9ID8NDgYUsHMdCT/exec")
BOT_NOMBRE = os.environ.get("BOT_NOMBRE", "DCBET")
DOMINIO = os.environ.get("DOMINIO", "")
TZ = os.environ.get("TZ_BOT", "America/Bogota")

BANCA_INICIAL = _float("BANCA_INICIAL", 100_000)
UNIDAD_PCT = _float("UNIDAD_PCT", 0.02)
TOPE_DIARIO_PCT = _float("TOPE_DIARIO_PCT", 0.12)
APUESTA_MINIMA = _float("APUESTA_MINIMA", 1_000)
BANCA_ALERTA_PCT = _float("BANCA_ALERTA_PCT", 0.70)
AVISO_MIN_ANTES = [int(x) for x in os.environ.get("AVISO_MIN_ANTES", "30,10").split(",") if x.strip()]
PREGUNTAR_MIN_DESPUES = _int("PREGUNTAR_MIN_DESPUES", 5)
RACHA_ALERTA = _int("RACHA_ALERTA", 3)
SILENCIO = os.environ.get("SILENCIO", "23:00-06:30")   # sin recordatorios en ese horario

# Servidor web propio (Render u otro PaaS): webhook de Telegram + panel + salud
PUERTO = _int("PORT", 0)                                   # Render define PORT
URL_PUBLICA = os.environ.get("URL_PUBLICA") or os.environ.get("RENDER_EXTERNAL_URL", "")
MODO = os.environ.get("MODO", "webhook" if URL_PUBLICA else "polling")
EFIMERO = bool(os.environ.get("RENDER")) or os.environ.get("DISCO_EFIMERO") == "1"
PANEL_USUARIO = os.environ.get("PANEL_USUARIO", "admin")
PANEL_CLAVE = os.environ.get("PANEL_CLAVE", "")
CODIGO_OBSERVADOR = os.environ.get("CODIGO_OBSERVADOR", "")
OBSERVADORES = [x.strip() for x in os.environ.get("OBSERVADORES", "").split(",") if x.strip()]   # ids fijos en modo lectura

DATOS = Path(os.environ.get("DATOS_DIR", RAIZ / "datos"))
PANEL = Path(os.environ.get("PANEL_DIR", DATOS / "panel"))
for d in (DATOS, PANEL, DATOS / "respaldos"):
    d.mkdir(parents=True, exist_ok=True)
