"""
TELEGRAM · cliente HTTP con reintentos, límite de velocidad y partición de textos
"""
from __future__ import annotations

import json
import logging
import time

import requests

from .. import config

log = logging.getLogger("telegram")
_sesion = requests.Session()
_ultimo_envio = [0.0]
espejo = None          # función (chat_id, texto) que replica a observadores lo que se envía al dueño


def _api():
    return f"https://api.telegram.org/bot{config.TOKEN_BOT}"


def llamar(metodo: str, timeout: float = 35, files=None, reintentos: int = 3, **params):
    for intento in range(reintentos):
        try:
            if files:
                r = _sesion.post(f"{_api()}/{metodo}", data=params, files=files, timeout=timeout)
            else:
                r = _sesion.post(f"{_api()}/{metodo}", json=params, timeout=timeout)
            d = r.json()
        except (requests.RequestException, ValueError) as ex:
            log.warning("%s falló (%s), intento %d", metodo, type(ex).__name__, intento + 1)
            time.sleep(2 ** intento)
            continue
        if d.get("ok"):
            return d["result"]
        espera = (d.get("parameters") or {}).get("retry_after")
        if espera:                                    # 429: demasiados mensajes
            time.sleep(espera + 0.5)
            continue
        desc = d.get("description", "")
        if "can't parse entities" in desc and params.get("parse_mode"):
            params.pop("parse_mode")                  # HTML roto → se envía en texto plano
            continue
        if "message is not modified" in desc:
            return True
        log.warning("%s: %s", metodo, desc)
        return None
    return None


def _ritmo():
    falta = 0.35 - (time.time() - _ultimo_envio[0])
    if falta > 0:
        time.sleep(falta)
    _ultimo_envio[0] = time.time()


def partir(texto: str, limite: int = 4000) -> list[str]:
    partes, actual = [], ""
    for bloque in texto.split("\n\n"):
        while len(bloque) > limite:
            partes.append(bloque[:limite])
            bloque = bloque[limite:]
        if actual and len(actual) + len(bloque) + 2 > limite:
            partes.append(actual)
            actual = ""
        actual += ("\n\n" if actual else "") + bloque
    if actual:
        partes.append(actual)
    return partes or [""]


def enviar(chat_id, texto: str, botones=None, silencioso=False):
    res = None
    partes = partir(texto)
    for i, p in enumerate(partes):
        _ritmo()
        extra = {"reply_markup": {"inline_keyboard": botones}} if botones and i == len(partes) - 1 else {}
        res = llamar("sendMessage", chat_id=chat_id, text=p, parse_mode="HTML",
                     disable_web_page_preview=True, disable_notification=silencioso, **extra)
    if espejo:
        try:
            espejo(chat_id, texto)
        except Exception as ex:
            log.warning("espejo: %s", ex)
    return res


def editar(chat_id, message_id, texto, botones=None):
    if espejo:
        try:
            espejo(chat_id, "✏️ " + texto)
        except Exception as ex:
            log.warning("espejo: %s", ex)
    return llamar("editMessageText", chat_id=chat_id, message_id=message_id, text=texto[:4000],
                  parse_mode="HTML", disable_web_page_preview=True,
                  reply_markup={"inline_keyboard": botones or []})


def responder_boton(callback_id, texto=""):
    return llamar("answerCallbackQuery", callback_query_id=callback_id, text=texto[:190], reintentos=1)


def escribiendo(chat_id):
    llamar("sendChatAction", chat_id=chat_id, action="typing", timeout=5, reintentos=1)


def descargar(file_id: str) -> bytes | None:
    f = llamar("getFile", file_id=file_id)
    if not f:
        return None
    try:
        r = _sesion.get(f"https://api.telegram.org/file/bot{config.TOKEN_BOT}/{f['file_path']}", timeout=60)
        return r.content if r.ok else None
    except requests.RequestException:
        return None


def enviar_json_fijado(chat_id, nombre: str, datos: dict, caption: str = "", borrar_anterior=None):
    cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
    msg = llamar("sendDocument", files={"document": (nombre, cuerpo, "application/json")},
                 chat_id=chat_id, caption=caption[:1000], disable_notification="true")
    if not msg:
        return None
    llamar("pinChatMessage", chat_id=chat_id, message_id=msg["message_id"], disable_notification=True)
    if borrar_anterior and borrar_anterior != msg["message_id"]:
        llamar("deleteMessage", chat_id=chat_id, message_id=borrar_anterior, reintentos=1)
    return msg


def leer_json_fijado(chat_id) -> tuple[dict | None, int | None]:
    chat = llamar("getChat", chat_id=chat_id)
    pin = (chat or {}).get("pinned_message") or {}
    doc = pin.get("document")
    if not doc or not doc.get("file_name", "").endswith(".json"):
        return None, None
    crudo = descargar(doc["file_id"])
    try:
        return json.loads(crudo.decode("utf-8")), pin["message_id"]
    except Exception:
        return None, None
