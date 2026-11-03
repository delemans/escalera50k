"""
VOZ · transcribe notas de voz en español, con respaldo gratis
=============================================================
Orden: faster-whisper local (si está instalado) → Groq Whisper (gratis) → Gemini (gratis).
En Render gratis no hay memoria para el modelo local, así que usa Groq o Gemini.
"""
from __future__ import annotations

import base64
import logging
import os
import tempfile

import requests

from .. import config

log = logging.getLogger("voz")
_modelo = None


def _local(audio: bytes) -> str | None:
    global _modelo
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None
    if _modelo is None:
        _modelo = WhisperModel("small", device="cpu", compute_type="int8")
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as f:
        f.write(audio)
        ruta = f.name
    try:
        segmentos, _ = _modelo.transcribe(ruta, language="es", vad_filter=True)
        return " ".join(s.text.strip() for s in segmentos).strip()
    finally:
        os.unlink(ruta)


def _groq(audio: bytes) -> str | None:
    if not config.GROQ_API_KEY:
        return None
    r = requests.post("https://api.groq.com/openai/v1/audio/transcriptions",
                      headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"},
                      files={"file": ("nota.ogg", audio, "audio/ogg")},
                      data={"model": os.environ.get("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo"),
                            "language": "es", "response_format": "json"}, timeout=60)
    r.raise_for_status()
    return (r.json().get("text") or "").strip()


def _gemini(audio: bytes) -> str | None:
    if not config.GEMINI_API_KEY:
        return None
    from .ia import GEMINI, modelo_gemini
    r = requests.post(f"{GEMINI}/models/{modelo_gemini()}:generateContent",
                      headers={"x-goog-api-key": config.GEMINI_API_KEY}, timeout=60,
                      json={"contents": [{"role": "user", "parts": [
                          {"inline_data": {"mime_type": "audio/ogg", "data": base64.b64encode(audio).decode()}},
                          {"text": "Transcribe literalmente este audio en español. Responde solo con la transcripción."}]}]})
    r.raise_for_status()
    partes = (((r.json().get("candidates") or [{}])[0].get("content") or {}).get("parts") or [])
    return "".join(p.get("text", "") for p in partes).strip()


def transcribir(audio: bytes) -> str | None:
    for metodo in (_local, _groq, _gemini):
        try:
            t = metodo(audio)
            if t:
                return t
        except Exception as ex:
            log.warning("Transcripción %s falló: %s", metodo.__name__, ex)
    return None
