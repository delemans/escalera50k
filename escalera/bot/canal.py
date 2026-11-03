"""
FASE 2 · canal gratis, canal VIP y prueba de rentabilidad pública
================================================================
Nada de esto se activa solo: requiere FASE2=1 y los ids de los canales.

  Canal GRATIS (CANAL_PUBLICO)  1 pick al día (el de más confianza con valor), publicado
                                ANTES del partido con hora, y su resultado después.
                                Así se arma un historial público verificable.
  Canal VIP (CANAL_VIP)         todos los picks y jugadas del día. Suscripción mensual con
                                Telegram Stars (enlace de suscripción de 30 días).
  /fase2                        ¿ya está comprobado que es rentable? (criterios abajo)

Criterios para vender (todos):
  • ≥ 300 picks liquidados   • ≥ 8 semanas   • IC 90 % del ROI por encima de 0
  • p-valor < 0,05 (los aciertos no se explican por azar)
"""
from __future__ import annotations

import datetime as dt
import os

from ..nucleo.formato import cuota, e, pct
from . import db
from . import telegram as tg
from .sync import ahora

ACTIVA = os.environ.get("FASE2") == "1"
CANAL_PUBLICO = os.environ.get("CANAL_PUBLICO", "")
CANAL_VIP = os.environ.get("CANAL_VIP", "")
PRECIO_STARS = int(os.environ.get("VIP_PRECIO_STARS", "500") or 500)
CRITERIOS = {"n": 300, "semanas": 8, "pValor": 0.05}
AVISO_LEGAL = ("+18 · Probabilidad no es certeza: no hay ganancias garantizadas. "
               "Apuesta solo lo que puedas perder y solo en casas autorizadas por Coljuegos.")


def criterios(dia: dict, fecha_inicio: str | None) -> dict:
    est = (dia.get("estadisticas") or {}).get("sistema") or {}
    n = est.get("n") or 0
    ic = est.get("icRoi90") or [None, None]
    semanas = 0
    if fecha_inicio:
        semanas = (ahora().date() - dt.date.fromisoformat(fecha_inicio)).days / 7
    checks = [("Picks liquidados", n, CRITERIOS["n"], n >= CRITERIOS["n"]),
              ("Semanas de historial", round(semanas, 1), CRITERIOS["semanas"], semanas >= CRITERIOS["semanas"]),
              ("IC 90 % del ROI (piso)", ic[0], "> 0", bool(ic[0] is not None and ic[0] > 0)),
              ("p-valor (azar)", est.get("pValor"), "< 0,05", bool(est.get("pValor") is not None and est["pValor"] < CRITERIOS["pValor"]))]
    return {"checks": checks, "listo": all(c[3] for c in checks), "roi": est.get("roi"), "n": n}


def mensaje_fase2(dia: dict, fecha_inicio: str | None) -> str:
    c = criterios(dia, fecha_inicio)
    out = ["🚀 <b>FASE 2 · ¿YA SE PUEDE VENDER?</b>", "━━━━━━━━━━━━━━━━"]
    for nombre, valor, meta, ok in c["checks"]:
        v = "—" if valor is None else (pct(valor, True, 1) if "ROI" in nombre else str(valor).replace(".", ","))
        out.append(f"{'✅' if ok else '⏳'} {e(nombre)}: <b>{e(v)}</b> (meta {e(meta)})")
    out += ["", "🟢 <b>Listo</b>: ya hay pruebas para abrir el VIP." if c["listo"] else
            "⏳ <b>Aún no</b>. Mientras tanto publica 1 pick gratis al día para construir el historial público.",
            "", f"<i>{AVISO_LEGAL}</i>"]
    return "\n".join(out)


def _pick_gratis(dia):
    picks = {p["id"]: p for p in dia.get("picks", []) if p.get("id")}
    candidatos = [i for i in dia.get("plan") or [] if i["tipo"] == "sencilla" and i["accion"] == "APOSTAR"]
    candidatos.sort(key=lambda i: (-(picks.get(i["id"], {}).get("confianza") or 0), -i["ev"]))
    return (candidatos[0], picks.get(candidatos[0]["id"], {})) if candidatos else (None, None)


def publicar_dia(dia: dict) -> list[str]:
    """Publica el pick gratis (y el VIP completo). Devuelve qué hizo."""
    hecho = []
    if not ACTIVA or not dia.get("fecha"):
        return hecho
    libro = db.get("publicos") or []
    if any(x["fecha"] == dia["fecha"] for x in libro):
        return hecho
    item, p = _pick_gratis(dia)
    if CANAL_PUBLICO and item:
        j = p.get("justificacion") or {}
        txt = "\n".join([
            "🆓 <b>PICK GRATIS DEL DÍA</b> · Escalera 50K", "━━━━━━━━━━━━━━━━",
            f"⚽ <b>{e(p.get('h'))} vs {e(p.get('a'))}</b>", f"🏆 {e(p.get('lg'))} · ⏱ {e(p.get('t'))} (hora Colombia)",
            f"▸ <b>{e(p.get('sel'))}</b> · cuota ref {cuota(p.get('o'))}",
            f"Prob. {pct(p.get('p'))} · EV {pct(p.get('ev'), True, 1)} · confianza {'●' * (p.get('confianza') or 0)}", "",
            "📌 <b>Por qué</b>"] + [f"• {e(x)}" for x in (j.get("aFavor") or [])[:3]] + [
            "", f"🕒 Publicado {ahora().strftime('%d/%m %H:%M')} (antes del partido)",
            "💎 Todos los picks, escaleras y soñadoras en el VIP.", f"<i>{AVISO_LEGAL}</i>"])
        msg = tg.enviar(CANAL_PUBLICO, txt)
        if msg:
            libro.append({"fecha": dia["fecha"], "id": item["id"], "sel": p.get("sel"), "partido": f"{p.get('h')} vs {p.get('a')}",
                          "cuota": p.get("o"), "publicado": ahora().isoformat(timespec="minutes"), "msg": msg.get("message_id"),
                          "resultado": "pendiente"})
            hecho.append("pick gratis publicado")
    if CANAL_VIP:
        from . import mensajes as M
        for m in [M.resumen(dia), M.plan(dia)] + [M.tarjeta(dia, i) for i in dia.get("plan") or [] if i["accion"] != "NO"]:
            if m:
                tg.enviar(CANAL_VIP, m, silencioso=True)
        hecho.append("VIP publicado")
    db.put("publicos", libro[-400:])
    return hecho


def publicar_resultados(dia: dict) -> None:
    if not ACTIVA or not CANAL_PUBLICO:
        return
    libro = db.get("publicos") or []
    liq = {x["id"]: x for x in dia.get("liquidado") or []}
    cambio = False
    for x in libro:
        r = liq.get(x["id"])
        if x["resultado"] == "pendiente" and r and r.get("resultado") in ("ganado", "perdido", "nulo"):
            x["resultado"] = r["resultado"]
            cambio = True
            ic = {"ganado": "✅", "perdido": "❌", "nulo": "➖"}[r["resultado"]]
            hechos = [y for y in libro if y["resultado"] in ("ganado", "perdido")]
            gan = sum(1 for y in hechos if y["resultado"] == "ganado")
            unidades = sum((y["cuota"] - 1) if y["resultado"] == "ganado" else -1 for y in hechos)
            tg.enviar(CANAL_PUBLICO, f"{ic} <b>RESULTADO</b> · {e(x['partido'])}\n▸ {e(x['sel'])} @ {cuota(x['cuota'])} "
                                     f"· {e(r.get('marcador', ''))}\n\n📊 Historial público: {gan}/{len(hechos)} · "
                                     f"{unidades:+.2f} unidades".replace(".", ","))
    if cambio:
        db.put("publicos", libro)


def enlace_vip() -> str:
    if not CANAL_VIP:
        return "Falta CANAL_VIP en Render (id del canal privado VIP, con el bot como administrador)."
    r = tg.llamar("createChatSubscriptionInviteLink", chat_id=CANAL_VIP, name="VIP mensual",
                  subscription_period=2592000, subscription_price=PRECIO_STARS)
    if not r:
        return "Telegram no creó el enlace (revisa que el bot sea admin del canal VIP y que el precio esté permitido)."
    return f"💎 Enlace de suscripción VIP (30 días, {PRECIO_STARS} ⭐):\n{e(r.get('invite_link'))}"


def resumen_libro() -> str:
    libro = db.get("publicos") or []
    hechos = [y for y in libro if y["resultado"] in ("ganado", "perdido")]
    if not hechos:
        return "📒 Historial público: aún sin picks liquidados."
    gan = sum(1 for y in hechos if y["resultado"] == "ganado")
    unidades = sum((y["cuota"] - 1) if y["resultado"] == "ganado" else -1 for y in hechos)
    return f"📒 Historial público: {gan}/{len(hechos)} aciertos · {unidades:+.2f} u · ROI {unidades / len(hechos) * 100:+.1f} %".replace(".", ",")
