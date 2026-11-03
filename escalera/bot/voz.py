"""
VOZ · transcribe notas de voz en español (opcional: pip install faster-whisper).
El modelo "small" se descarga la primera vez (~500 MB) y luego funciona sin internet.
"""
import logging
import os
import tempfile

log = logging.getLogger("voz")
_modelo = None


def transcribir(audio: bytes) -> str | None:
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
