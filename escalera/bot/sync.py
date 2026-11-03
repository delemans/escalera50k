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
import time
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
              "saldoReportado": db.get("saldo"), "apuestas": db.registro(desde, solo_pendientes=True),
              "estado": {"fecha": hoy(), "confirmaciones": db.confirmaciones(hoy()), "diaMid": db.get("dia_mid_enviado"),
                         "avisos": db.avisos_desde(time.time() - 36 * 3600),
                         "silencioOff": bool(db.get("silencio_off"))}}
    msg = tg.enviar_json_fijado(canal, "registro.json", cuerpo, caption=f"💓 {cuerpo['latido']}",
                                borrar_anterior=db.get("registro_mid"))
    if msg:
        db.put("registro_mid", msg["message_id"])
    return msg


def restaurar() -> bool:
    """Con disco efímero (Render gratis): al arrancar, recupera el estado desde
    los mensajes fijados de Telegram. No reenvía el día."""
    if not db.vacia():
        return False
    i = ids()
    if i["chat"]:
        db.put("chat", i["chat"])
    if i["canal"]:
        db.put("canal", i["canal"])
        reg, mid = tg.leer_json_fijado(i["canal"])
        if reg:
            db.put("registro_mid", mid)
            if reg.get("saldoReportado"):
                db.put("saldo", reg["saldoReportado"])
            if reg.get("apuestas"):
                db.registrar(reg["apuestas"])
            est = reg.get("estado") or {}
            db.put("silencio_off", bool(est.get("silencioOff")))
            for ref, estado in (est.get("confirmaciones") or {}).items():
                db.set_confirmacion(est.get("fecha"), ref, estado=estado)
            for clave in est.get("avisos") or []:
                db.marcar_aviso(clave)
            if est.get("diaMid"):
                db.put("dia_mid_enviado", est["diaMid"])
    revisar_dia_nuevo()            # deja el día en disco sin mandarlo
    db.put("restaurado", ahora().isoformat(timespec="minutes"))
    log.info("Estado restaurado desde Telegram")
    return True
