"""
ALERTAS · reglas de aviso (solo informan, nunca bloquean)
========================================================
🔴 rojo      banca bajo el 70 % · tope diario superado · cuota bajo la mínima
🟠 naranja   racha de pérdidas · apuesta propia tras perder · stake > 2 unidades
🟡 amarillo  recordatorios 60/15 min · pregunta "¿la hiciste?" · día sin publicar
🟢 verde     escalera completa · meta de progresión · día positivo
Cada alerta tiene una clave única y se envía una sola vez.
Durante el horario de SILENCIO no se mandan recordatorios (las rojas sí).
"""
from __future__ import annotations

import datetime as dt

from .. import config
from ..nucleo import staking as STK
from . import db
from . import mensajes as M
from .sync import BOG, ahora


def politica(dia: dict) -> STK.PoliticaStake:
    saldo = db.get("saldo")
    real = saldo or (dia.get("bancas") or {}).get("real") or config.BANCA_INICIAL
    return STK.PoliticaStake(banca=real, banca_inicial=config.BANCA_INICIAL, unidad_pct=config.UNIDAD_PCT,
                             tope_diario_pct=config.TOPE_DIARIO_PCT, apuesta_minima=config.APUESTA_MINIMA,
                             freno_pct=config.BANCA_ALERTA_PCT)


def en_silencio(t: dt.datetime) -> bool:
    if db.get("silencio_off"):
        return False
    try:
        a, b = config.SILENCIO.split("-")
        ini, fin = (dt.time.fromisoformat(a), dt.time.fromisoformat(b))
    except ValueError:
        return False
    h = t.time()
    return (h >= ini or h < fin) if ini > fin else (ini <= h < fin)


def _hora(hhmm: str, fecha: str) -> dt.datetime | None:
    try:
        h, m = map(int, hhmm.split(":"))
        d = dt.date.fromisoformat(fecha)
        return dt.datetime(d.year, d.month, d.day, h, m, tzinfo=BOG)
    except (ValueError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# Al registrar una apuesta
# ---------------------------------------------------------------------------
def avisos_de_registro(item: dict, dia: dict, apostado_hoy: float) -> list[str]:
    pol = politica(dia)
    avisos = []
    plan = next((i for i in dia.get("plan", []) if i["id"] == item.get("ref")), None)
    if plan and item.get("cuota") and item["cuota"] < plan["cuota_min"] and item.get("accion") == "hice":
        ev = plan["p"] * item["cuota"] - 1
        avisos.append(f"Cuota {M.cuota(item['cuota'])} bajo la mínima {M.cuota(plan['cuota_min'])}: "
                      f"EV {M.pct(ev, True, 1)}.")
    if plan and plan["accion"] == "NO" and item.get("accion") == "hice":
        avisos.append("El sistema la tenía en NO APOSTAR (EV negativo).")
    valor = item.get("valor") or 0
    if valor > 2 * pol.unidad:
        avisos.append(f"Stake de {M.pesos(valor)}: más de 2 unidades ({M.pesos(2 * pol.unidad)}).")
    if item.get("accion") in ("hice", "propia") and apostado_hoy + valor > pol.tope_diario:
        avisos.append(f"Con esta llevas {M.pesos(apostado_hoy + valor)} hoy: pasas el tope de {M.pesos(pol.tope_diario)}.")
    if item.get("accion") == "propia":
        perdio = any((x.get("netoReal") or 0) < 0 for x in dia.get("liquidado") or [])
        if perdio:
            avisos.append("Apuesta fuera del sistema después de una pérdida: ojo con querer recuperar.")
    return avisos


# ---------------------------------------------------------------------------
# Revisión periódica → [(clave, texto, botones)]
# ---------------------------------------------------------------------------
_ENVIADOS: set[str] = set()      # respaldo en memoria: si la base falla o se reinicia, no se repite en este proceso


def marcar(clave: str):
    _ENVIADOS.add(clave)
    try:
        db.marcar_aviso(clave)
    except Exception:
        pass


def pendientes(dia: dict) -> list[tuple[str, str, list | None]]:
    t = ahora()
    hoy = t.date().isoformat()
    pol = politica(dia)
    out: list[tuple[str, str, list | None]] = []

    def add(clave, texto, botones=None):
        if clave in _ENVIADOS or db.aviso_enviado(clave):
            return
        out.append((clave, texto, botones))

    real = db.get("saldo") or (dia.get("bancas") or {}).get("real")
    if real is not None and real < config.BANCA_ALERTA_PCT * config.BANCA_INICIAL:
        add(f"banca-{hoy}", M.alerta("rojo", "Banca bajo el 70 %",
            f"Tu banca está en {M.pesos(real)} (inicial {M.pesos(config.BANCA_INICIAL)}).",
            "Los stakes sugeridos ya bajaron a la mitad. Considera hacer solo las 🟢."))
    ap = db.apostado(hoy)
    if ap > pol.tope_diario:
        add(f"tope-{hoy}", M.alerta("rojo", "Tope diario superado",
            f"Llevas {M.pesos(ap)} apostados hoy; el tope es {M.pesos(pol.tope_diario)}.",
            "Lo sano es parar por hoy."))
    racha = ((dia.get("estadisticas") or {}).get("real") or {}).get("rachas") or {}
    if racha.get("actualTipo") == "perdido" and racha.get("actual", 0) >= config.RACHA_ALERTA:
        add(f"racha-{dia.get('fecha')}", M.alerta("naranja", f"{racha['actual']} pérdidas seguidas",
            "Las rachas son normales con estas probabilidades, pero es cuando más se sube el stake por impulso.",
            "Mantén el stake sugerido o tómate el día."))
    if 8 <= t.hour < 10 and dia.get("fecha") != hoy:      # solo en esa ventana: un reinicio más tarde no lo repite
        add(f"sin-dia-{hoy}", M.alerta("amarillo", "Aún no llegan las jugadas de hoy",
            "La mesa de análisis no ha publicado el día. Puede ir tarde.", "Escribe /hoy más tarde."))
    for x in dia.get("liquidado") or []:
        if x.get("tipo") == "escalera" and x.get("resultado") == "ganado":
            add(f"esc-ok-{x['id']}", M.alerta("verde", "¡Escalera completa!", f"{x.get('titulo')}: {M.pesos(x.get('neto'), True)}."))
    if dia.get("fecha") != hoy:
        return out

    silencio = en_silencio(t)
    plan = dia.get("plan") or []
    jug = dia.get("jugadas") or {}
    picks = {p["id"]: p for p in dia.get("picks", []) if p.get("id")}

    # Recordatorios: un mensaje por partido con todas las jugadas que lo usan
    por_partido: dict[str, dict] = {}
    for i in plan:
        if i["accion"] == "NO":
            continue
        patas = [{"id": i["id"], **picks.get(i["id"], {})}] if i["tipo"] == "sencilla" else \
            (jug.get(i["tipo"]) or {}).get("patas", [])
        for n, x in enumerate(patas):
            pk = picks.get(x["id"], x)
            g = por_partido.setdefault(x["id"], {"p": {**pk, "partido": x.get("partido") or f"{pk.get('h')} vs {pk.get('a')}"},
                                                 "roles": []})
            nombre = i["titulo"] if i["tipo"] == "sencilla" else f"{i['titulo']} · pierna {n + 1}"
            monto = i["monto"]
            if i["tipo"] == "escalera" and jug.get("escalera", {}).get("montos") and i["monto"]:
                monto = jug["escalera"]["montos"][n] * i["monto"] / jug["escalera"]["stake"]
            g["roles"].append((i["accion"], nombre, monto))
    if not silencio:
        for pid, g in por_partido.items():
            inicio = _hora(g["p"].get("t", ""), hoy)
            if not inicio:
                continue
            faltan = (inicio - t).total_seconds() / 60
            for m in config.AVISO_MIN_ANTES:
                if m - 6 < faltan <= m:
                    add(f"rec-{hoy}-{pid}-{m}", M.recordatorio(g["p"], m, g["roles"]))

    # Recordatorio de TUS apuestas ya hechas (30 y 10 min antes)
    if not silencio:
        for m in dia.get("misApuestas") or []:
            inicio = _hora(m.get("hora") or "", hoy)
            if m.get("resultado") != "pendiente" or not inicio:
                continue
            faltan = (inicio - t).total_seconds() / 60
            for mm in config.AVISO_MIN_ANTES:
                if mm - 6 < faltan <= mm:
                    add(f"rec-mia-{hoy}-{m.get('id')}-{mm}",
                        f"⏰ <b>Faltan {mm} min</b> · {M.e(m.get('hora'))}\n{M.e(m.get('partido'))}\n"
                        f"▸ Tu apuesta: <b>{M.e(m.get('seleccion'))}</b> @ {M.cuota(m.get('cuotaReal'))} · "
                        f"{M.pesos(m.get('stakeReal'))}\n📡 Te aviso cada gol y tarjeta en vivo.")

    # Pregunta "¿la hiciste?" poco después del inicio de la primera pierna
    for i in plan:
        if i["accion"] == "NO":
            continue
        inicio = _hora(i.get("hora", ""), hoy)
        conf = db.confirmacion(hoy, i["id"]) or {}
        if inicio and conf.get("estado", "pendiente") == "pendiente" and \
                t >= inicio + dt.timedelta(minutes=config.PREGUNTAR_MIN_DESPUES):
            add(f"preg-{hoy}-{i['id']}", M.preguntar(i), M.botones_tarjeta(i["id"]))

    # Cierre del día
    if t.hour == 22 and t.minute >= 30:
        sin = [i for i in plan if i["accion"] != "NO" and
               (db.confirmacion(hoy, i["id"]) or {}).get("estado", "pendiente") == "pendiente"]
        texto = (f"🌙 <b>Cierre del día</b>\nApostaste {M.pesos(ap)} de {M.pesos(pol.tope_diario)}.\n"
                 + (f"Te faltan por confirmar {len(sin)} jugadas: usa /tarjetas." if sin else "Todo confirmado. ¡Buen trabajo!"))
        add(f"cierre-{hoy}", texto)
    return out
