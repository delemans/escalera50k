"""
BOT EN VIVO · Escalera 50K
==========================
Arranque:  python -m escalera.bot.app

Flujo de un día:
  06:59  la tarea fija dia.json → el bot manda: resumen · qué hacer hoy · tarjetas
         (cada tarjeta: ✅ La hice · ❌ No la hice · 💬 ¿Cuánto paga BetPlay?)
  −60/−15 min  recordatorio por partido con el monto de cada jugada
  +5 min       si no contestaste: "¿Hiciste esta?" con los mismos botones
  tarde/noche  la tarea liquida → "🔄 Actualización"
  22:30        cierre del día
En cualquier momento: texto, pantallazo o voz → Claude responde y registra.
"""
from __future__ import annotations

import logging
import re
import signal
import time
import uuid

from .. import config
from ..nucleo import formato as F
from ..nucleo import staking as STK
from . import alertas, db, ia, panel, sync, voz
from . import mensajes as M
from . import telegram as tg

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s · %(message)s")
log = logging.getLogger("bot")
_pendientes: dict[str, list] = {}           # propuestas esperando ✅ Confirmar
_apagar = [False]


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def al_usuario(texto, botones=None, silencioso=False):
    chat = sync.ids()["chat"]
    return tg.enviar(chat, texto, botones, silencioso) if chat else None


def item_plan(ref):
    return next((i for i in sync.dia().get("plan", []) if i["id"] == ref), None)


def ref_por_numero(n: int):
    ids = ((sync.dia().get("jugadas") or {}).get("sencillas") or {}).get("ids", [])
    return ids[n - 1] if 0 < n <= len(ids) else None


def nuevo_tgid(base) -> str:
    return f"tg-{base}-{uuid.uuid4().hex[:6]}"


def guardar_registro(items: list[dict], fuente: str):
    hoy = sync.hoy()
    for a in items:
        a.setdefault("tgId", nuevo_tgid(int(time.time())))
        a.setdefault("fecha", hoy)
        a.setdefault("fuente", fuente)
        a.setdefault("cuando", sync.ahora().strftime("%d/%m %H:%M"))
        a.pop("avisos", None)
        if a.get("ref"):
            db.set_confirmacion(a["fecha"], a["ref"], estado="si" if a["accion"] == "hice" else "no")
    db.registrar(items)
    sync.publicar_registro()


# ---------------------------------------------------------------------------
# Envío del día
# ---------------------------------------------------------------------------
def enviar_dia(dia, solo_tarjetas=False):
    if not dia:
        al_usuario("Todavía no tengo las jugadas de hoy. La mesa las publica hacia las 07:00.")
        return
    if not solo_tarjetas:
        al_usuario(M.resumen(dia, db.get("saldo")))
        p = M.plan(dia)
        if p:
            al_usuario(p)
    for i in dia.get("plan", []):
        estado = (db.confirmacion(dia["fecha"], i["id"]) or {}).get("estado", "pendiente")
        msg = al_usuario(M.tarjeta(dia, i), M.botones_tarjeta(i["id"], estado), silencioso=True)
        if msg:
            db.set_confirmacion(dia["fecha"], i["id"], msg_id=msg["message_id"])


# ---------------------------------------------------------------------------
# Comandos
# ---------------------------------------------------------------------------
def cmd(texto: str, chat_id) -> bool:
    partes = texto.split()
    c = partes[0].split("@")[0].lower()
    dia = sync.dia()
    pol = alertas.politica(dia)
    if c in ("/start", "/ayuda", "/help"):
        tg.enviar(chat_id, M.ayuda())
        if c == "/start":
            i = sync.ids()
            tg.enviar(chat_id, f"🔑 CHAT_ID <code>{chat_id}</code>\nCANAL_DATOS <code>{i.get('canal') or 'sin conectar'}</code>\n"
                               "Cópialos en las instrucciones de las tareas programadas.")
    elif c == "/hoy":
        enviar_dia(dia)
    elif c == "/plan":
        tg.enviar(chat_id, M.plan(dia) or "Hoy no hay plan.")
    elif c == "/tarjetas":
        enviar_dia(dia, solo_tarjetas=True)
    elif c == "/banca":
        tg.enviar(chat_id, M.banca(dia, db.get("saldo"), db.apostado(sync.hoy()), pol.tope_diario, pol.unidad))
    elif c == "/saldo":
        v = F.leer_numero(partes[1]) if len(partes) > 1 else None
        if not v or v < 0:
            tg.enviar(chat_id, "Escríbelo así: <code>/saldo 100000</code> (lo que ves en BetPlay ahora).")
        else:
            db.put("saldo", v)
            pol = alertas.politica(dia)
            sync.publicar_registro()
            tg.enviar(chat_id, f"💰 Saldo guardado: <b>{F.pesos(v)}</b>\nUnidad {F.pesos(pol.unidad)} · "
                               f"tope diario {F.pesos(pol.tope_diario)}" + (" · 🔴 freno activo" if pol.freno else ""))
    elif c == "/stats":
        est = dia.get("estadisticas") or {}
        tg.enviar(chat_id, M.estadisticas(est.get("real"), "TUS APUESTAS REALES"))
        tg.enviar(chat_id, M.estadisticas(est.get("sistema"), "SISTEMA (SIMULADO)"))
    elif c == "/riesgo":
        tg.enviar(chat_id, M.simulacion(dia.get("simulacion")))
    elif c == "/registro":
        items = db.registro(sync.hoy())
        tg.enviar(chat_id, M.confirmar_registro(items).replace("¿Lo guardo así?", "") if items
                  else "Hoy no has registrado apuestas.")
    elif c == "/deshacer":
        items = [a for a in db.registro(sync.hoy()) if not a.get("sincronizado")]
        if not items:
            tg.enviar(chat_id, "No hay registros de hoy sin sincronizar para deshacer.")
        else:
            ult = items[-1]
            db.borrar_registro(ult["tgId"])
            if ult.get("ref"):
                db.set_confirmacion(ult["fecha"], ult["ref"], estado="pendiente")
            sync.publicar_registro()
            tg.enviar(chat_id, f"↩️ Borré: {M.e(ult.get('sel') or ult.get('ref') or 'el último registro')}")
    elif c == "/metodo":
        tg.enviar(chat_id, M.metodo())
    elif c == "/silencio":
        off = not db.get("silencio_off", False)
        db.put("silencio_off", off)
        tg.enviar(chat_id, "🔔 Recordatorios también de noche." if off else f"🔕 Silencio nocturno activo ({config.SILENCIO}).")
    elif c == "/id":
        tg.enviar(chat_id, f"<code>{chat_id}</code>")
    else:
        return False
    return True


# ---------------------------------------------------------------------------
# Botones
# ---------------------------------------------------------------------------
def boton(cb):
    datos = cb.get("data", "")
    accion, _, clave = datos.partition(":")
    msg = cb.get("message") or {}
    chat_id = msg.get("chat", {}).get("id")
    hoy = sync.hoy()

    if accion in ("ok", "descartar"):
        items = _pendientes.pop(clave, None)
        if items is None:
            tg.responder_boton(cb["id"], "Ya no está pendiente")
            return
        if accion == "ok":
            guardar_registro(items, items[0].get("fuente", "chat"))
            tg.responder_boton(cb["id"], "Guardado ✅")
            tg.editar(chat_id, msg["message_id"], M.e(msg.get("text", "").replace("¿Lo guardo así?", ""))
                      + "\n✅ <b>Guardado.</b>")
        else:
            tg.responder_boton(cb["id"], "Descartado")
            tg.editar(chat_id, msg["message_id"], "🗑 Descartado. Mándamelo de nuevo si quieres corregir.")
        return

    item = item_plan(clave)
    if not item:
        tg.responder_boton(cb["id"], "Esa jugada ya no está en el plan de hoy")
        return
    dia = sync.dia()
    if accion == "si":
        db.put("espera", {"tipo": "detalle", "ref": clave, "msg": msg.get("message_id")})
        tg.responder_boton(cb["id"], "Cuéntame cuota y valor")
        botones = None
        if item["monto"]:
            botones = [[{"text": f"Usé mínima {F.cuota(item['cuota_min'])} · {F.pesos(item['monto'])}",
                         "callback_data": f"rapido:{clave}"}]]
        tg.enviar(chat_id, M.pedir_detalle(item), botones)
    elif accion == "rapido":
        guardar_registro([{"accion": "hice", "ref": clave, "tipo": item["tipo"], "sel": item["titulo"],
                           "cuota": item["cuota_min"], "valor": item["monto"], "estado": "abierta"}], "boton")
        db.put("espera", None)
        tg.responder_boton(cb["id"], "Registrada ✅")
        _refrescar_tarjeta(dia, item, "si")
        tg.enviar(chat_id, M.registrado(item["titulo"], item["cuota_min"], item["monto"], []))
    elif accion == "no":
        guardar_registro([{"accion": "no_hice", "ref": clave, "tipo": item["tipo"], "sel": item["titulo"]}], "boton")
        tg.responder_boton(cb["id"], "Anotado: no la hiciste")
        _refrescar_tarjeta(dia, item, "no")
    elif accion == "cuota":
        db.put("espera", {"tipo": "cuota", "ref": clave})
        tg.responder_boton(cb["id"], "Escribe la cuota de BetPlay")
        tg.enviar(chat_id, f"💬 ¿Cuánto paga BetPlay para <b>{M.e(item['titulo'])}</b>?\n"
                           f"Escribe solo la cuota, ej.: <code>{F.cuota(item['cuota_ref'])}</code>")
    elif accion == "cambiar":
        db.set_confirmacion(hoy, clave, estado="pendiente")
        _refrescar_tarjeta(dia, item, "pendiente")
        tg.responder_boton(cb["id"], "Elige de nuevo")


def _refrescar_tarjeta(dia, item, estado):
    conf = db.confirmacion(dia.get("fecha"), item["id"]) or {}
    if conf.get("msg_id"):
        tg.editar(sync.ids()["chat"], conf["msg_id"], M.tarjeta(dia, item), M.botones_tarjeta(item["id"], estado))


# ---------------------------------------------------------------------------
# Respuestas a una espera (cuota de BetPlay o detalle de la apuesta)
# ---------------------------------------------------------------------------
NUM = r"\$?\d+(?:[.,]\d+)*"


def resolver_espera(chat_id, texto) -> bool:
    espera = db.get("espera")
    if not espera or not texto or texto.startswith("/"):
        return False
    item = item_plan(espera["ref"])
    if not item:
        db.put("espera", None)
        return False
    numeros = [F.leer_numero(x) for x in re.findall(NUM, texto)]
    numeros = [n for n in numeros if n]
    if espera["tipo"] == "cuota":
        o = next((n for n in numeros if 1.01 <= n <= 50), None)
        if not o:
            return False                      # no era una cuota: pasa a la conversación
        pol = alertas.politica(sync.dia())
        acc, monto, ev = STK.decidir_con_cuota_betplay(item["p"], o, pol, item["tipo"])
        db.put("espera", None)
        tg.enviar(chat_id, M.decision_betplay(item, o, acc, monto, ev.ev))
        return True
    if espera["tipo"] == "detalle":
        o = next((n for n in numeros if 1.01 <= n <= 1000 and n < 100), None)
        v = next((n for n in numeros if n >= 500), None)
        if not (o and v):
            tg.enviar(chat_id, "No entendí cuota y valor. Escríbelo así: <code>1,42 3000</code> o manda el pantallazo.")
            return True
        dia = sync.dia()
        avisos = alertas.avisos_de_registro({"accion": "hice", "ref": item["id"], "cuota": o, "valor": v},
                                            dia, db.apostado(sync.hoy()))
        guardar_registro([{"accion": "hice", "ref": item["id"], "tipo": item["tipo"], "sel": item["titulo"],
                           "cuota": o, "valor": v, "estado": "abierta"}], "texto")
        db.put("espera", None)
        _refrescar_tarjeta(dia, item, "si")
        tg.enviar(chat_id, M.registrado(item["titulo"], o, v, avisos))
        return True
    return False


# ---------------------------------------------------------------------------
# Atajos sin IA: "hice 1 y 3", "no hice el 2"
# ---------------------------------------------------------------------------
def atajo(texto: str) -> list[dict] | None:
    t = texto.lower().strip()
    m = re.fullmatch(r"(no\s+)?hice\s+(?:la|el|las|los)?\s*([\d\s,y]+)", t)
    if not m:
        return None
    nums = [int(x) for x in re.findall(r"\d+", m.group(2))]
    items = []
    for n in nums:
        ref = ref_por_numero(n)
        if not ref:
            return None
        it = item_plan(ref) or {}
        items.append({"accion": "no_hice" if m.group(1) else "hice", "ref": ref, "tipo": "sencilla",
                      "sel": it.get("titulo"), "cuota": None, "valor": None})
    return items or None


# ---------------------------------------------------------------------------
# Conversación con Claude
# ---------------------------------------------------------------------------
def proponer(chat_id, propuestas, fuente):
    dia = sync.dia()
    acumulado = db.apostado(sync.hoy())
    for p in propuestas:
        p.update(tgId=nuevo_tgid(int(time.time())), fecha=sync.hoy(), fuente=fuente,
                 cuando=sync.ahora().strftime("%d/%m %H:%M"))
        p["avisos"] = alertas.avisos_de_registro(p, dia, acumulado)
        if p.get("dudas"):
            p["avisos"].append(f"No se leyó bien: {p['dudas']}")
        if p.get("accion") == "hice" and not (p.get("cuota") and p.get("valor")):
            p["avisos"].append("Falta cuota o valor: puedes confirmar y corregir luego con /deshacer.")
        acumulado += p.get("valor") or 0
    clave = uuid.uuid4().hex[:8]
    _pendientes[clave] = propuestas
    tg.enviar(chat_id, M.confirmar_registro(propuestas),
              botones=[[{"text": "✅ Confirmar", "callback_data": f"ok:{clave}"},
                        {"text": "🗑 Descartar", "callback_data": f"descartar:{clave}"}]])


def conversar(chat_id, texto, imagen=None, fuente="texto"):
    tg.escribiendo(chat_id)
    dia = sync.dia()
    pol = alertas.politica(dia)
    desde = sync.ahora().date().isoformat()[:8] + "01"
    try:
        respuesta, propuestas = ia.conversar(db.memoria(), texto, imagen, dia, db.registro(desde),
                                             sync.ahora().strftime("%A %d/%m/%Y %H:%M"), pol)
    except Exception as ex:
        log.exception("Claude falló")
        tg.enviar(chat_id, f"⚠️ No pude procesar eso ahora ({type(ex).__name__}). Intenta en un minuto; "
                           "los botones siguen funcionando.")
        return
    db.recordar("user", ("[pantallazo] " if imagen else "") + (texto or ""))
    db.recordar("assistant", respuesta or "…")
    if respuesta:
        tg.enviar(chat_id, M.e(respuesta))
    if propuestas:
        proponer(chat_id, propuestas, fuente)


# ---------------------------------------------------------------------------
# Enrutador
# ---------------------------------------------------------------------------
def procesar(u: dict):
    if "callback_query" in u:
        cb = u["callback_query"]
        if str(cb.get("from", {}).get("id")) != str(sync.ids()["chat"]):
            tg.responder_boton(cb["id"], "Bot privado")
            return
        boton(cb)
        return
    if "channel_post" in u:
        canal = u["channel_post"]["chat"]["id"]
        if not sync.ids()["canal"]:
            db.put("canal", canal)
            al_usuario(f"📡 Canal de datos conectado: <code>{canal}</code>")
            sync.publicar_registro()
        return
    m = u.get("message")
    if not m or m["chat"]["type"] != "private":
        return
    chat_id = m["chat"]["id"]
    if not sync.ids()["chat"]:
        db.put("chat", chat_id)
    elif str(sync.ids()["chat"]) != str(chat_id):
        tg.enviar(chat_id, "Este bot es privado.")
        return
    texto = (m.get("text") or m.get("caption") or "").strip()
    if texto.startswith("/") and cmd(texto, chat_id):
        return
    if "photo" in m or m.get("document", {}).get("mime_type", "").startswith("image/"):
        fid = m["photo"][-1]["file_id"] if "photo" in m else m["document"]["file_id"]
        img = tg.descargar(fid)
        if not img:
            tg.enviar(chat_id, "No pude descargar la imagen. ¿Me la mandas otra vez?")
            return
        db.put("espera", None)
        conversar(chat_id, texto, img, "foto")
        return
    if "voice" in m or "audio" in m:
        a = m.get("voice") or m.get("audio")
        crudo = tg.descargar(a["file_id"]) or b""
        t = voz.transcribir(crudo) if crudo else None
        if t is None:
            tg.enviar(chat_id, "🎙 No pude transcribir la nota de voz (falta faster-whisper en el servidor). Escríbemelo.")
            return
        tg.enviar(chat_id, f"🎙 Entendí: «{M.e(t)}»")
        texto = t
    if not texto:
        return
    if resolver_espera(chat_id, texto):
        return
    rapido = atajo(texto)
    if rapido:
        proponer(chat_id, rapido, "texto")
        return
    conversar(chat_id, texto, None, "voz" if "voice" in m else "texto")


# ---------------------------------------------------------------------------
# Tareas periódicas
# ---------------------------------------------------------------------------
_ultimo = {"dia": 0.0, "alertas": 0.0, "latido": 0.0, "panel": 0.0, "respaldo": ""}


def periodicas():
    t = time.time()
    if t - _ultimo["dia"] > 180:
        _ultimo["dia"] = t
        previo = sync.dia().get("fecha")
        nuevo = sync.revisar_dia_nuevo()
        if nuevo:
            log.info("Publicación nueva %s (%s)", nuevo.get("fecha"), nuevo.get("publicacion"))
            if nuevo.get("publicacion") == "revision" and nuevo.get("fecha") == previo:
                m = M.actualizacion(nuevo)
                if m:
                    al_usuario(m)
            else:
                enviar_dia(nuevo)
            panel.generar(nuevo)
    if t - _ultimo["alertas"] > 60:
        _ultimo["alertas"] = t
        for clave, texto, botones in alertas.pendientes(sync.dia()):
            if al_usuario(texto, botones):
                db.marcar_aviso(clave)
    if t - _ultimo["latido"] > 1800:
        _ultimo["latido"] = t
        sync.publicar_registro()
    if t - _ultimo["panel"] > 600:
        _ultimo["panel"] = t
        try:
            panel.generar(sync.dia())
        except Exception:
            log.exception("Panel")
    hoy = sync.hoy()
    if _ultimo["respaldo"] != hoy and sync.ahora().hour >= 3:
        _ultimo["respaldo"] = hoy
        log.info("Respaldo: %s", db.respaldar())


def main():
    if not config.TOKEN_BOT:
        raise SystemExit("Falta TOKEN_BOT (archivo .env).")
    signal.signal(signal.SIGTERM, lambda *_: _apagar.__setitem__(0, True))
    tg.llamar("deleteWebhook")
    tg.llamar("setMyCommands", commands=[
        {"command": c, "description": d} for c, d in [
            ("hoy", "Resumen y jugadas del día"), ("plan", "Qué hacer con cada jugada"),
            ("tarjetas", "Tarjetas con botones"), ("banca", "Banca, unidad y tope"),
            ("saldo", "Reportar tu saldo de BetPlay"), ("stats", "Estadísticas"),
            ("riesgo", "Simulación del plan"), ("registro", "Lo registrado hoy"),
            ("deshacer", "Borrar el último registro"), ("metodo", "Cómo decide el sistema"),
            ("silencio", "Recordatorios de noche sí/no"), ("ayuda", "Cómo usar el bot")]])
    offset = db.get("offset", 0)
    log.info("Bot encendido.")
    panel.salud(True, "arrancando")
    while not _apagar[0]:
        try:
            ups = tg.llamar("getUpdates", offset=offset, timeout=25, reintentos=1,
                            allowed_updates=["message", "callback_query", "channel_post"]) or []
            for u in ups:
                offset = u["update_id"] + 1
                db.put("offset", offset)
                try:
                    procesar(u)
                except Exception:
                    log.exception("Error procesando update %s", u.get("update_id"))
            periodicas()
        except KeyboardInterrupt:
            break
        except Exception:
            log.exception("Error en el bucle; reintento en 5 s")
            panel.salud(False, "error en el bucle")
            time.sleep(5)
    log.info("Bot apagado.")


if __name__ == "__main__":
    main()
