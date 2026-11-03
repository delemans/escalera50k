"""
SINCRONIZACIÓN con la mesa de análisis (tarea programada en la nube)
===================================================================
  Tarea ──► dia.json fijado en tu chat privado ──► bot
  Bot   ──► registro.json fijado en el canal de datos ──► tarea
El registro se vuelve a publicar cada 30 min con un "latido": si la tarea ve
un latido de menos de 3 h sabe que el bot está vivo (y nunca usa getUpdates).
"""
from __future__ import annotations

import datetime as dt
import json
import logging
from zoneinfo import ZoneInfo

from .. import config
from . import db
from . import telegram as tg

log = logging.getLogger("sync")
BOG = ZoneInfo(config.TZ)
F_DIA = config.DATOS / "dia.json"


def ahora() -> dt.datetime:
    return dt.datetime.now(BOG)


def hoy() -> str:
    return ahora().date().isoformat()


def ids() -> dict:
    return {"chat": db.get("chat") or (int(config.CHAT_ID) if config.CHAT_ID else None),
            "canal": db.get("canal") or (int(config.CANAL_DATOS) if config.CANAL_DATOS else None)}


def dia() -> dict:
    try:
        return json.loads(F_DIA.read_text(encoding="utf-8"))
    except Exception:
        return {}


def guardar_dia(d: dict):
    tmp = F_DIA.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    tmp.replace(F_DIA)                       # escritura atómica


def revisar_dia_nuevo() -> dict | None:
    chat = ids()["chat"]
    if not chat:
        return None
    datos, mid = tg.leer_json_fijado(chat)
    if not datos or not isinstance(datos, dict) or "fecha" not in datos:
        return None
    if dia().get("_mid") == mid:
        return None
    datos["_mid"] = mid
    guardar_dia(datos)
    hechos = set(datos.get("registrados") or [])
    if hechos:
        db.marcar_sincronizados(hechos)
    return datos


def publicar_registro():
    canal = ids()["canal"]
    if not canal:
        return None
    desde = (ahora() - dt.timedelta(days=7)).date().isoformat()
    cuerpo = {"version": 2, "latido": ahora().isoformat(timespec="minutes"), "chatId": ids()["chat"],
              "saldoReportado": db.get("saldo"), "apuestas": db.registro(desde, solo_pendientes=True)}
    msg = tg.enviar_json_fijado(canal, "registro.json", cuerpo, caption=f"💓 {cuerpo['latido']}",
                                borrar_anterior=db.get("registro_mid"))
    if msg:
        db.put("registro_mid", msg["message_id"])
    return msg
