"""
MENSAJES · diseño visual de todo lo que envía el bot (HTML de Telegram)
======================================================================
Principios: una idea por mensaje · lo que debes HACER va primero y en
negrita · números con formato colombiano · un ícono por concepto, siempre
el mismo · ninguna línea pasa de ~40 caracteres útiles en el celular.

Íconos fijos
  🟢 APOSTAR   🟡 VIGILAR   ⚪ NO APOSTAR   ✅ ganada   ❌ perdida   ➖ nula
  🎯 sencilla  🪜 escalera  📈 progresión  🔗 combinada  🚀 súper
  🔴🟠🟡🟢 niveles de alerta  ⏰ recordatorio  🧾 registro  💰 banca  📊 estadísticas
"""
from __future__ import annotations

from ..nucleo.formato import barra, cuota, e, fecha_corta, pct, pesos

LINEA = "━━━━━━━━━━━━━━━━"
ICONO_TIPO = {"sencilla": "🎯", "escalera": "🪜", "progresion": "📈", "combinada": "🔗", "super": "🌙"}
ICONO_ACCION = {"APOSTAR": "🟢", "VIGILAR": "🟡", "NO": "⚪"}
TEXTO_ACCION = {"APOSTAR": "APOSTAR", "VIGILAR": "VIGILAR", "NO": "NO APOSTAR"}
ICONO_NIVEL = {"rojo": "🔴", "naranja": "🟠", "amarillo": "🟡", "verde": "🟢", "info": "ℹ️"}
ICONO_RES = {"ganado": "✅", "perdido": "❌", "nulo": "➖", "pendiente": "⏳"}
SEMAFORO = {"good": "🟢", "warn": "🟡", "bad": "🔴"}


def _titulo(icono, texto, sub=""):
    return f"{icono} <b>{e(texto)}</b>" + (f" · {e(sub)}" if sub else "")


def _pick(dia, pid):
    return next((p for p in dia.get("picks", []) if p.get("id") == pid), None)


def _plan(dia, ref):
    return next((i for i in dia.get("plan", []) if i["id"] == ref), None)


def _alertas(dia, niveles=("rojo", "naranja", "amarillo", "verde")):
    return [f"{ICONO_NIVEL[a['nivel']]} {e(a['t'])}" for a in dia.get("alertas") or []
            if a.get("nivel") in niveles]


# ---------------------------------------------------------------------------
# 1. Resumen de la mañana
# ---------------------------------------------------------------------------
def resumen(dia: dict, banca_real: float | None = None) -> str:
    v = dia.get("veredicto", {})
    b = dia.get("bancas", {})
    pol = dia.get("politica", {})
    out = ["🪜 <b>ESCALERA 50K · DC TECNOLOGY</b>",
           f"📅 {e(fecha_corta(dia['fecha']))} · <i>{e(dia.get('actualizado', ''))}</i>", LINEA]
    out += _alertas(dia, ("rojo",))
    out += [f"<b>{e(v.get('titulo', ''))}</b>", e(v.get("texto", "")), ""]
    plan = dia.get("plan", [])
    n = {k: sum(1 for i in plan if i["accion"] == k) for k in ("APOSTAR", "VIGILAR", "NO")}
    total = sum(i["monto"] for i in plan if i["accion"] == "APOSTAR" and i["tipo"] != "progresion")
    picks = [p for p in dia.get("picks", []) if p.get("id")]
    descartados = [p for p in dia.get("picks", []) if not p.get("id")]
    por_tipo = {t: sum(1 for i in plan if i["tipo"] == t) for t in ("sencilla", "escalera", "combinada", "super")}
    out += ["📊 <b>Resumen del análisis</b>",
            f"• {dia.get('partidos', 0)} partidos revisados · {len(picks) + len(descartados)} con cuotas",
            f"• {len(picks)} picks pasan los filtros · {len(descartados)} descartados",
            f"• 🎯 {por_tipo['sencilla']} individuales · 🪜 {por_tipo['escalera']} escalera · "
            f"🔗 {por_tipo['combinada']} combinada · 🌙 {por_tipo['super']} soñadora",
            f"• 🟢 {n['APOSTAR']} apostar · 🟡 {n['VIGILAR']} vigilar · ⚪ {n['NO']} no",
            f"💵 Dinero real del plan: <b>{pesos(total)}</b> (tope {pesos(pol.get('tope'))})", ""]
    if b:
        real = banca_real if banca_real is not None else b.get("real")
        out += ["💰 <b>Bancas</b>",
                f"• Tuya: <b>{pesos(real)}</b>" + (f" ({pesos(b['varReal'], True)} ayer)" if "varReal" in b else ""),
                f"• Sistema (simulado): {pesos(b.get('sistema'))}"
                + (f" ({pesos(b['varSistema'], True)} ayer)" if "varSistema" in b else ""), ""]
    liq = dia.get("liquidado") or []
    if liq:
        out.append("🧾 <b>Liquidado</b>")
        out += [_linea_liquidado(x) for x in liq]
        out.append("")
    rg = dia.get("riesgo") or {}
    if rg:
        icono = {"normal": "🟢", "reducido": "🟠", "stop": "🛑"}.get(rg.get("estado"), "⚪")
        out += [f"🛡 <b>Riesgo</b> {icono} {e(rg.get('estado', '').upper())} · hoy {pesos(rg.get('netoHoy'), True)} · "
                f"7 días {pesos(rg.get('neto7d'), True)}"
                + (f" · {rg['racha']} pérdidas seguidas" if rg.get("racha") else ""), ""]
    pt = ((dia.get("estadisticas") or {}).get("sistema") or {}).get("porTipo") or {}
    if pt:
        out.append("🧪 <b>Prueba de sistemas</b> (simulado)")
        for t in ("sencilla", "combinada", "super", "progresion", "escalera"):
            d = pt.get(t)
            if d:
                out.append(f"• {NOMBRE_TIPO.get(t, t)}: {d['aciertos']}/{d['n']} · ROI {pct(d['roi'], True, 1)}")
        out.append("")
    s = dia.get("semaforo")
    if s:
        out += [f"🚦 <b>¿Se está dando?</b> {SEMAFORO.get(s.get('c'), '⚪')}", e(s.get("t")), ""]
    otras = _alertas(dia, ("naranja", "amarillo", "verde"))
    if otras:
        out += otras + [""]
    mias = [m for m in dia.get("misApuestas") or [] if m.get("resultado") == "pendiente"]
    if mias:
        out += [f"🧾 Tienes <b>{len(mias)}</b> apuestas abiertas por {pesos(sum(m.get('stakeReal') or 0 for m in mias))} (detalle abajo).", ""]
    out += [LINEA, "Abajo: el plan, tus apuestas y una tarjeta por jugada con su análisis.",
            "📸 Pantallazo · 🎙 voz · ✍️ «hice 1 y 3» · 💬 pregúntame"]
    if dia.get("sitio"):
        out.append(f"🌐 <a href=\"{e(dia['sitio'])}\">Ver el sitio</a>")
    return "\n".join(out)


def _linea_liquidado(x):
    tu = f" · tú {pesos(x['netoReal'], True)}" if x.get("netoReal") is not None else ""
    return (f"{ICONO_RES.get(x.get('resultado'), '•')} {e(x.get('titulo'))} "
            f"<i>{e(x.get('marcador', ''))}</i> · {pesos(x.get('neto'), True)}{tu}")


# ---------------------------------------------------------------------------
# 2. Plan del día (qué hacer con cada una)
# ---------------------------------------------------------------------------
GRUPOS = [("sencilla", "🎯 INDIVIDUALES CON VALOR"), ("escalera", "🪜 ESCALERA"), ("combinada", "🔗 COMBINADA"),
          ("super", "🌙 SOÑADORA (cuota 100+)"), ("progresion", "📈 ESCALERA DE CRECIMIENTO")]
NOMBRE_TIPO = {"sencilla": "Individual", "escalera": "Escalera", "combinada": "Combinada",
               "super": "Soñadora", "progresion": "Escalera de crecimiento"}


def estrellas(n) -> str:
    n = max(0, min(5, int(n or 0)))
    return "●" * n + "○" * (5 - n)


def plan(dia: dict) -> str | None:
    items = dia.get("plan") or []
    if not items:
        return None
    out = [_titulo("📋", "PLAN DEL DÍA", fecha_corta(dia["fecha"])), LINEA]
    for tipo, nombre in GRUPOS:
        grupo = [i for i in items if i["tipo"] == tipo]
        if not grupo:
            continue
        out.append(f"<b>{nombre}</b>")
        for i in grupo:
            ic = ICONO_ACCION[i["accion"]]
            pk = _pick(dia, i["id"]) or {}
            conf = f" · {estrellas(pk.get('confianza'))}" if tipo == "sencilla" and pk else ""
            out.append(f"{ic} <b>{e(i['hora'])}</b> · {e(i['titulo'])}{conf}")
            if i["accion"] == "APOSTAR":
                out.append(f"     <b>{pesos(i['monto'])}</b> · mínima BetPlay <b>{cuota(i['cuota_min'])}</b> · EV {pct(i['ev'], True, 1)}")
            elif i["accion"] == "VIGILAR":
                out.append(f"     solo si BetPlay paga ≥ <b>{cuota(i['cuota_min'])}</b> (ref {cuota(i['cuota_ref'])})")
            else:
                out.append("     no apostar · solo simulación")
        out.append("")
    total = sum(i["monto"] for i in items if i["accion"] == "APOSTAR" and i["tipo"] != "progresion")
    tope = (dia.get("politica") or {}).get("tope")
    out += [LINEA, f"💵 Dinero real del plan: <b>{pesos(total)}</b>" + (f" de {pesos(tope)} de tope" if tope else ""),
            "🟢 apostar · 🟡 vigilar · ⚪ no  ·  ●●●○○ confianza en los datos",
            "<i>Confirma siempre la cuota en BetPlay antes de apostar.</i>"]
    return "\n".join(out)


def mis_apuestas(dia: dict) -> str | None:
    mias = dia.get("misApuestas") or []
    if not mias:
        return None
    abiertas = [m for m in mias if m.get("resultado") == "pendiente"]
    en_juego = sum(m.get("stakeReal") or 0 for m in abiertas)
    pot = sum((m.get("stakeReal") or 0) * (m.get("cuotaReal") or 1) for m in abiertas)
    out = [_titulo("🧾", "TUS APUESTAS", f"{len(abiertas)} abiertas"), LINEA]
    for m in mias:
        ic = ICONO_RES.get(m.get("resultado"), "•")
        linea = f"{ic} {e(m.get('hora') or '')} · {e(m.get('partido'))}"
        det = f"     ▸ {e(m.get('seleccion'))} @ {cuota(m.get('cuotaReal'))} · {pesos(m.get('stakeReal'))}"
        if m.get("resultado") != "pendiente" and m.get("netoReal") is not None:
            det += f" → <b>{pesos(m['netoReal'], True)}</b>"
        out += [linea, det]
    out += ["", f"En juego <b>{pesos(en_juego)}</b> · pago potencial {pesos(pot)}"]
    grande = [m for m in abiertas if (m.get("stakeReal") or 0) > 2 * ((dia.get("politica") or {}).get("unidad") or 2000)]
    for m in grande:
        out.append(f"⚠️ {e(m.get('partido'))}: {pesos(m['stakeReal'])} es más de 2 unidades.")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# 3. Tarjetas por jugada (cada una con botones)
# ---------------------------------------------------------------------------
def tarjeta(dia: dict, item: dict) -> str:
    tipo = item["tipo"]
    acc = item["accion"]
    pk = _pick(dia, item["id"]) if tipo == "sencilla" else None
    etiqueta = ((pk or {}).get("justificacion") or {}).get("etiqueta")
    cab = [f"{ICONO_TIPO.get(tipo, '•')} <b>{NOMBRE_TIPO.get(tipo, '').upper()}</b> · {e(item['titulo'])}"
           + (f" · <i>{e(etiqueta)}</i>" if etiqueta and tipo == "sencilla" else ""),
           f"{ICONO_ACCION[acc]} <b>{TEXTO_ACCION[acc]}</b>"
           + (f" · <b>{pesos(item['monto'])}</b>" if item["monto"] else "")
           + (f" si BetPlay paga ≥ <b>{cuota(item['cuota_min'])}</b>" if acc != "NO" else "")]
    cuerpo = {"sencilla": _cuerpo_sencilla, "escalera": _cuerpo_escalera, "progresion": _cuerpo_progresion,
              "combinada": _cuerpo_multi, "super": _cuerpo_multi}[tipo](dia, item)
    prob = f"Prob. {pct(item['p'], dec=1)}"
    if pk and pk.get("p_push"):
        prob = f"Gana {pct(item['p'], dec=1)} · empate (devuelve) {pct(pk['p_push'], dec=1)}"
    pie = [LINEA, f"{prob} · EV {pct(item['ev'], True, 1)} · mínima {cuota(item['cuota_min'])}",
           f"<i>{e(item['razon'])}</i>"]
    return "\n".join(cab + [LINEA] + cuerpo + pie)


def _cuerpo_sencilla(dia, item):
    p = _pick(dia, item["id"]) or {}
    j = p.get("justificacion") or {}
    out = [f"⚽ <b>{e(p.get('h'))} vs {e(p.get('a'))}</b>",
           f"🏆 {e(p.get('lg'))} · ⏱ {e(p.get('t'))}",
           f"▸ <b>{e(p.get('sel'))}</b> · ref {cuota(p.get('o'))} ({e(p.get('bk'))})",
           f"Confianza en los datos {estrellas(p.get('confianza'))}", ""]
    if j.get("aFavor"):
        out.append("📌 <b>Por qué</b>")
        out += [f"• {e(x)}" for x in j["aFavor"][:4]]
    if j.get("enContra"):
        out.append("⚖️ <b>En contra</b>")
        out += [f"• {e(x)}" for x in j["enContra"][:3]]
    return out


def _cuerpo_escalera(dia, item):
    j = dia["jugadas"]["escalera"]
    montos = j.get("montos") or [j["stake"], None, None]
    factor = (item["monto"] / j["stake"]) if item["monto"] else 1
    out = []
    for n, (x, m) in enumerate(zip(j["patas"], montos), 1):
        monto = pesos(m * factor) if m else "—"
        nota = " (ya retiraste la base)" if n == 3 else ""
        out += [f"<b>{n}.</b> {e(x['t'])} · {e(x['partido'])}",
                f"    ▸ {e(x['sel'])} @ {cuota(x['o'])} · apuestas <b>{monto}</b>{nota}"]
    if not item["monto"]:
        out.append("<i>Montos de la simulación del sistema (no es dinero real hoy).</i>")
    out += ["", f"🏁 Si completa: <b>{pesos(j['final'] * factor)}</b> · prob. {pct(j['P'], dec=1)}",
            "Falla 1.º o 2.º: pierdes la base · falla 3.º: quedas en $0"]
    out += _por_que(dia, "escalera")
    return out


def _por_que(dia, tipo):
    razones = (dia.get("porQue") or {}).get(tipo) or []
    return (["", "📌 <b>Por qué</b>"] + [f"• {e(r)}" for r in razones]) if razones else []


def _cuerpo_progresion(dia, item):
    j = dia["jugadas"]["progresion"]
    x = j["patas"][0]
    ec = dia.get("escaleraCrec") or {}
    stake = ec.get("stake") or j["saldo"]
    lineas = [f"Serie #{j['reto']} · Peldaño {j['paso']}",
              f"{barra(j['saldo'], j['meta'])} <b>{pesos(j['saldo'])}</b> / {pesos(j['meta'])}",
              f"{e(x['t'])} · {e(x['partido'])}", f"▸ <b>{e(x['sel'])}</b> @ {cuota(x['o'])}"]
    if ec.get("asegurado"):
        lineas += [f"🛡 Modo seguro: apuestas <b>{pesos(stake)}</b> y apartas {pesos(ec['asegurado'])} (tu base)",
                   f"   si gana: {pesos(stake * x['o'] + ec['asegurado'])} · si pierde: conservas {pesos(ec['asegurado'])}",
                   f"   modo agresivo (todo): {pesos(ec['agresivo'])} → {pesos(ec['agresivo'] * x['o'])}"]
    else:
        lineas.append(f"Apuestas <b>{pesos(stake)}</b> → si gana {pesos(stake * x['o'])}")
    return lineas + [
            f"🎲 Este paso {pct(j['P'])} · 🏁 llegar a la meta {pct(j['Pmeta'], dec=1)}"] + _por_que(dia, "progresion")


def _cuerpo_multi(dia, item):
    j = dia["jugadas"][item["tipo"]]
    out = [f"<b>{n}.</b> {e(x['t'])} · {e(x['partido'])}\n    ▸ {e(x['sel'])} @ {cuota(x['o'])}"
           for n, x in enumerate(j["patas"], 1)]
    monto = item["monto"] or j["stake"]
    out += ["", f"Cuota total <b>{cuota(j['cuota'])}</b> · prob. {pct(j['P'], dec=1)}",
            f"Con {pesos(monto)} cobras {pesos(monto * j['cuota'])}"]
    if item["tipo"] == "super":
        out.append(f"🎟 {len(j['patas'])} piernas, todas con valor. Prob. de acertar ≈ 1 en {max(1, round(1 / j['P'])) if j.get('P') else '—'}.")
        out.append("⚠️ <i>Boleto de lotería con valor: se juega la apuesta mínima y lo normal es perderla.</i>")
    return out + _por_que(dia, item["tipo"])


def botones_tarjeta(ref: str, estado: str = "pendiente"):
    if estado == "si":
        return [[{"text": "✅ Registrada · cambiar", "callback_data": f"cambiar:{ref}"}]]
    if estado == "no":
        return [[{"text": "❌ No la hiciste · cambiar", "callback_data": f"cambiar:{ref}"}]]
    return [[{"text": "✅ La hice", "callback_data": f"si:{ref}"},
             {"text": "❌ No la hice", "callback_data": f"no:{ref}"}],
            [{"text": "💬 ¿Cuánto paga BetPlay?", "callback_data": f"cuota:{ref}"}]]


# ---------------------------------------------------------------------------
# Durante el día
# ---------------------------------------------------------------------------
def decision_betplay(item: dict, o: float, accion: str, monto: float, ev: float) -> str:
    if accion == "APOSTAR":
        return (f"🟢 <b>APUESTA {pesos(monto)}</b> a {cuota(o)}\n"
                f"{e(item['titulo'])}\nEV {pct(ev, True, 1)} con la cuota de BetPlay.\n"
                "Cuando la hagas toca ✅ La hice en la tarjeta.")
    return (f"⚪ <b>NO APUESTES</b> a {cuota(o)}\n{e(item['titulo'])}\n"
            f"EV {pct(ev, True, 1)}: necesitas al menos <b>{cuota(item['cuota_min'])}</b>.")


def pedir_detalle(item: dict) -> str:
    sug = f" (sugerido {pesos(item['monto'])})" if item.get("monto") else ""
    return (f"🧾 <b>{e(item['titulo'])}</b>\n¿A qué cuota y por cuánto la hiciste?{sug}\n"
            "Escríbelo así: <code>1,42 3000</code> — o mándame el pantallazo del boleto.")


def registrado(item_titulo: str, o, valor, avisos: list[str]) -> str:
    out = [f"✅ <b>Registrada</b> · {e(item_titulo)}",
           f"Cuota {cuota(o)} · valor {pesos(valor)}" if o or valor else ""]
    out += [f"⚠️ {e(a)}" for a in avisos]
    out.append("<i>La mesa la aplica al sitio en la próxima revisión.</i>")
    return "\n".join(x for x in out if x)


def alerta(nivel: str, titulo: str, texto: str, accion: str | None = None) -> str:
    out = [f"{ICONO_NIVEL.get(nivel, '•')} <b>{e(titulo)}</b>", e(texto)]
    if accion:
        out.append(f"👉 {e(accion)}")
    return "\n".join(out)


def recordatorio(p: dict, minutos: int, roles: list[tuple[str, str, float | None]]) -> str:
    """roles = [(acción, nombre, monto), …] para el mismo partido."""
    out = [f"⏰ <b>Faltan {minutos} min</b> · {e(p.get('t'))}",
           e(p.get("partido") or f"{p.get('h')} vs {p.get('a')}"), f"▸ <b>{e(p.get('sel'))}</b>"]
    for acc, nombre, monto in roles:
        txt = f"{ICONO_ACCION.get(acc, '•')} {e(nombre)}"
        if acc == "APOSTAR" and monto:
            txt += f": <b>{pesos(monto)}</b>"
        elif acc == "VIGILAR":
            txt += ": solo si paga la mínima"
        out.append(txt)
    if p.get("omin"):
        out.append(f"Mínima BetPlay <b>{cuota(p['omin'])}</b>")
    return "\n".join(out)


def preguntar(item: dict) -> str:
    return (f"❓ <b>¿Hiciste esta?</b>\n{ICONO_TIPO.get(item['tipo'], '')} {e(item['titulo'])}\n"
            f"Ya empezó ({e(item['hora'])}). Toca un botón para que lleve bien tus cuentas.")


def confirmar_registro(items: list[dict]) -> str:
    out = [_titulo("🧾", "Esto entendí"), LINEA]
    for n, a in enumerate(items, 1):
        accion = {"hice": "✅ La hiciste", "no_hice": "❌ No la hiciste",
                  "propia": "🆕 Apuesta tuya (fuera del sistema)"}.get(a.get("accion"), "•")
        out.append(f"<b>{n}. {accion}</b>")
        if a.get("ref"):
            out.append(f"Jugada: <code>{e(a['ref'])}</code>")
        for k in ("partido", "sel"):
            if a.get(k):
                out.append(("▸ " if k == "sel" else "") + e(a[k]))
        datos = [x for x in (a.get("cuota") and f"cuota {cuota(a['cuota'])}",
                             a.get("valor") and f"valor {pesos(a['valor'])}", e(a.get("estado") or "")) if x]
        if datos:
            out.append(" · ".join(datos))
        out += [f"⚠️ {e(w)}" for w in a.get("avisos", [])]
        out.append("")
    out.append("¿Lo guardo así?")
    return "\n".join(out)


def banca(dia: dict, saldo: float | None, apostado: float, tope: float, unidad: float) -> str:
    b = dia.get("bancas", {})
    pr = dia.get("progresionCfg") or {}
    out = [_titulo("💰", "BANCA Y CONTROL"), LINEA,
           f"Saldo BetPlay (tú lo reportas): <b>{pesos(saldo)}</b>" if saldo else
           "Saldo BetPlay: <i>sin reportar · usa /saldo 100000</i>",
           f"Banca real según registro: {pesos(b.get('real'))}",
           f"Sistema (simulado): {pesos(b.get('sistema'))}", "",
           f"Unidad de hoy: <b>{pesos(unidad)}</b>",
           f"Apostado hoy: <b>{pesos(apostado)}</b> de {pesos(tope)}", barra(apostado, tope)]
    if pr:
        out += ["", f"📈 Progresión: reto #{pr.get('reto')} · paso {pr.get('paso')}",
                f"{barra(pr.get('saldo', 0), pr.get('meta', 50000))} {pesos(pr.get('saldo'))} / {pesos(pr.get('meta'))}"]
    return "\n".join(out)


def estadisticas(est: dict, titulo: str) -> str:
    if not est or not est.get("n"):
        return f"📊 <b>{e(titulo)}</b>\nAún no hay jugadas liquidadas."
    ic = est.get("icRoi90")
    out = [_titulo("📊", titulo, f"{est['n']} jugadas"), LINEA,
           f"Aciertos <b>{est['aciertos']}</b> de {est['n']} ({pct(est['tasa'])}) · esperado {pct(est['tasaEsperada'])}",
           f"Beneficio <b>{pesos(est['beneficio'], True)}</b> · ROI <b>{pct(est['roi'], True, 1)}</b>",
           f"IC 90 % del ROI: {pct(ic[0], True, 1)} a {pct(ic[1], True, 1)}" if ic else "IC del ROI: faltan datos",
           f"Brier {str(est['brier']).replace('.', ',')} (azar informado {str(est['brierBase']).replace('.', ',')})",
           f"¿Suerte? p = {str(est['pValor']).replace('.', ',')} " + ("(señal)" if est["pValor"] < 0.1 else "(aún no se distingue del azar)"),
           f"Máx. caída {pct(est['maxDrawdown'], dec=1)} · peor racha {est['rachas']['peorPerdidas']} perdidas"]
    if est.get("clv") is not None:
        out.append(f"CLV medio {pct(est['clv'], True, 1)}")
    if est.get("porTipo"):
        out += ["", "<b>Por tipo</b>"]
        for k, d in est["porTipo"].items():
            out.append(f"{ICONO_TIPO.get(k, '•')} {e(k)}: {d['aciertos']}/{d['n']} · ROI {pct(d['roi'], True, 1)}")
    if est.get("calibracion"):
        out += ["", "<b>Calibración</b> (prob. dicha → real)"]
        for t in est["calibracion"]:
            out.append(f"{e(t['tramo'])}: {pct(t['esperado'])} → {pct(t['real'])} ({t['n']})")
    return "\n".join(out)


def simulacion(sim: dict) -> str:
    if not sim or not sim.get("n"):
        return "🎲 Hoy no hay plan real que simular (todo está en vigilancia o papel)."
    return "\n".join([_titulo("🎲", "SIMULACIÓN DEL PLAN", f"{sim['n']:,} escenarios".replace(",", ".")), LINEA,
                      f"Apuestas {pesos(sim['apostado'])} · resultado esperado {pesos(sim['esperado'], True)}",
                      f"Prob. de terminar el día ganando: <b>{pct(sim['pGanar'])}</b>",
                      f"Prob. de perder todo lo apostado: {pct(sim['pPerderTodo'])}",
                      f"Rango típico (10–90 %): {pesos(sim['p10'], True)} a {pesos(sim['p90'], True)}",
                      f"Peor caso {pesos(sim['peor'], True)} · mejor {pesos(sim['mejor'], True)}"])


def actualizacion(dia: dict) -> str | None:
    liq = dia.get("liquidado") or []
    if not liq and not dia.get("registrados"):
        return None
    b = dia.get("bancas", {})
    out = [_titulo("🔄", "ACTUALIZACIÓN", dia.get("actualizado", "")), LINEA]
    out += [_linea_liquidado(x) for x in liq]
    if dia.get("registrados"):
        out.append(f"🧾 {len(dia['registrados'])} apuestas tuyas aplicadas al sitio.")
    out += ["", f"💰 Tuya <b>{pesos(b.get('real'))}</b> · Sistema {pesos(b.get('sistema'))}"]
    out += _alertas(dia)
    return "\n".join(out)


def metodo() -> str:
    return "\n".join([
        _titulo("📐", "CÓMO DECIDE EL SISTEMA"), LINEA,
        "<b>1.</b> StatArea da probabilidades de todos los partidos.",
        "<b>2.</b> Se juntan cuotas de varias casas y se les quita el margen (métodos potencia y Shin).",
        "<b>3.</b> Fuera si StatArea y mercado difieren &gt; 8 pts o las casas no coinciden.",
        "<b>4.</b> p = 85 % mercado + 15 % StatArea. Noticias solo vetan.",
        "<b>5.</b> EV = p × cuota − 1. Mínima BetPlay = 1,02 ÷ p.",
        "<b>6.</b> Stake real = ¼ de Kelly, máx. 1,5 unidades (unidad = 2 % de tu banca).",
        "<b>7.</b> Tope diario 12 % de la banca. Bajo el 70 % → stakes a la mitad.", "",
        "🟢 <b>APOSTAR</b>: EV ≥ +2 % con la cuota de referencia",
        "🟡 <b>VIGILAR</b>: solo si BetPlay paga la mínima",
        "⚪ <b>NO</b>: EV negativo o alerta → solo simulación", "",
        "<i>Probabilidad no es certeza: un 70 % falla 3 de cada 10 veces.</i>"])


MERCADO_BETPLAY = {"1X2": "Resultado final", "DNB": "Apuesta sin empate", "DC": "Doble oportunidad",
                   "GOLES": "Total de goles", "BTTS": "Ambos equipos marcarán", "TARJETAS": "Total de tarjetas",
                   "CORNERS": "Total de tiros de esquina"}


def boletos(dia: dict) -> str | None:
    """Lista lista-para-copiar de lo que hay que montar en BetPlay, con monto y mínima."""
    items = [i for i in dia.get("plan") or [] if i["accion"] in ("APOSTAR", "VIGILAR")]
    if not items:
        return None
    picks = {p["id"]: p for p in dia.get("picks", []) if p.get("id")}
    jug = dia.get("jugadas") or {}
    out = [_titulo("🎟", "BOLETOS PARA BETPLAY", f"{len(items)}"), LINEA,
           "En BetPlay: <b>Fútbol → liga → partido → mercado → selección</b>. Pon el monto y apuesta solo si la cuota es ≥ la mínima.", ""]
    for n, i in enumerate(items, 1):
        if i["tipo"] == "sencilla":
            p = picks.get(i["id"], {})
            patas = [{"partido": f"{p.get('h')} vs {p.get('a')}", "sel": p.get("sel"), "t": p.get("t"),
                      "lg": p.get("lg"), "mercado": p.get("mercado"), "o": p.get("o")}]
        else:
            patas = (jug.get(i["tipo"]) or {}).get("patas", [])
        monto = pesos(i["monto"]) if i["monto"] else "solo si paga la mínima"
        out.append(f"<b>#{n} {ICONO_ACCION[i['accion']]} {e(NOMBRE_TIPO.get(i['tipo'], ''))}</b> · <b>{monto}</b> · mínima <b>{cuota(i['cuota_min'])}</b>")
        for x in patas:
            out.append(f"   {e(x.get('t'))} · {e(x.get('partido'))}\n   🔎 {e(MERCADO_BETPLAY.get(x.get('mercado') or '1X2', 'Resultado final'))} → <b>{e(x.get('sel'))}</b>")
        if i["tipo"] == "escalera":
            out.append("   ⚠️ <i>Son 3 sencillas en orden (no una combinada): la siguiente solo si ganó la anterior.</i>")
        elif len(patas) > 1:
            out.append(f"   🧩 <i>Todas en el mismo boleto (combinada) · cuota total ≈ {cuota(i['cuota_ref'])}</i>")
        out.append("")
    out.append("Cuando apuestes, toca ✅ La hice en su tarjeta o mándame el pantallazo.")
    return "\n".join(out)


def informe(dia: dict) -> str:
    est = dia.get("estadisticas") or {}
    out = [_titulo("📑", "INFORME", fecha_corta(dia["fecha"]) if dia.get("fecha") else ""), LINEA]
    for clave, nombre in (("real", "Tus apuestas reales"), ("sistema", "Sistema (simulado)")):
        d = est.get(clave) or {}
        if not d.get("n"):
            out += [f"<b>{nombre}</b>: aún sin jugadas liquidadas.", ""]
            continue
        ic = d.get("icRoi90")
        out += [f"<b>{nombre}</b> · {d['n']} jugadas",
                f"Aciertos {d['aciertos']} ({pct(d['tasa'])}, esperado {pct(d['tasaEsperada'])}) · beneficio <b>{pesos(d['beneficio'], True)}</b>",
                f"ROI <b>{pct(d['roi'], True, 1)}</b>" + (f" (IC 90 %: {pct(ic[0], True, 1)} a {pct(ic[1], True, 1)})" if ic else ""),
                f"Máx. caída {pct(d['maxDrawdown'], dec=1)} · p-valor {str(d['pValor']).replace('.', ',')}"]
        for t, x in (d.get("porTipo") or {}).items():
            out.append(f"   {ICONO_TIPO.get(t, '•')} {e(NOMBRE_TIPO.get(t, t))}: {x['aciertos']}/{x['n']} · ROI {pct(x['roi'], True, 1)}")
        out.append("")
    rg = dia.get("riesgo") or {}
    if rg:
        out.append(f"🛡 Riesgo: {e((rg.get('estado') or '').upper())} · 7 días {pesos(rg.get('neto7d'), True)}")
    return "\n".join(out)


def escalera_estado(dia: dict) -> str:
    """Respuesta a «¿cuál es el peldaño 2?» / /escalera."""
    cfg = dia.get("progresionCfg") or {}
    if not cfg:
        return "📈 Aún no tengo los datos de tu escalera. Llegan con el análisis de la mañana (/hoy)."
    ec = dia.get("escaleraCrec") or {}
    saldo, base, paso = cfg.get("saldo", 0), cfg.get("base", 0), cfg.get("paso", 1)
    seguro = ec.get("stake") or (saldo - base if paso >= 2 and saldo > base else saldo)
    out = [_titulo("📈", "ESCALERA DE CRECIMIENTO", f"serie #{cfg.get('reto', 1)}"), LINEA,
           f"{barra(saldo, cfg.get('meta', 50000))} <b>{pesos(saldo)}</b> / {pesos(cfg.get('meta', 50000))}",
           f"Próximo: <b>peldaño {paso}</b>", ""]
    if paso >= 2 and saldo > base:
        out += [f"🛡 Modo seguro: apuestas <b>{pesos(seguro)}</b> y apartas tu base de {pesos(base)}",
                f"🔥 Modo agresivo: apuestas los <b>{pesos(saldo)}</b>"]
    else:
        out.append(f"Apuestas <b>{pesos(saldo)}</b> (la base de la serie)")
    j = (dia.get("jugadas") or {}).get("progresion")
    plan = next((i for i in dia.get("plan") or [] if i["tipo"] == "progresion"), None)
    if j and plan and dia.get("fecha"):
        x = j["patas"][0]
        out += ["", f"🎯 <b>Pick del peldaño {paso}</b> · {e(x['t'])}", e(x["partido"]),
                f"▸ <b>{e(x['sel'])}</b> @ {cuota(x['o'])} · mínima BetPlay <b>{cuota(plan['cuota_min'])}</b>",
                f"{ICONO_ACCION[plan['accion']]} {TEXTO_ACCION[plan['accion']]} · prob. {pct(plan['p'])} · EV {pct(plan['ev'], True, 1)}"]
        for a in (dia.get("porQue") or {}).get("progresion") or []:
            out.append(f"• {e(a)}")
    else:
        out += ["", "🎯 El pick de este peldaño sale con el análisis de la mañana (hacia las 07:00).",
                "Solo entran picks muy probables (cuota 1,25–1,60) que no tengan EV negativo."]
    out += ["", "<i>Si pierde, la serie termina y empieza otra con la base. Nunca subas el monto para recuperar.</i>"]
    return "\n".join(out)


def ayuda() -> str:
    return "\n".join([
        _titulo("🤖", "Cómo usarme"), LINEA,
        "Cada mañana te llega el resumen, <b>qué hacer hoy</b> y una tarjeta por jugada.",
        "En cada tarjeta: ✅ La hice · ❌ No la hice · 💬 ¿Cuánto paga BetPlay?", "",
        "📸 Pantallazo del boleto → lo leo y te pido confirmar.",
        "🎙 Nota de voz → la transcribo.",
        "✍️ «hice 1 y 3», «la combinada a 2,80 por 3000», «BetPlay paga 1,40 el 2».",
        "💬 Cualquier pregunta sobre el sistema o los picks.", "",
        "<b>Comandos</b>",
        "/hoy resumen · /plan qué hacer · /tarjetas botones",
        "/banca control · /saldo 100000 tu saldo real",
        "/stats estadísticas · /riesgo simulación",
        "/registro lo de hoy · /deshacer último registro",
        "/escalera tu escalera y el próximo peldaño · /mis tus apuestas · /cobro 45000",
        "/metodo cómo decide · /silencio recordatorios de noche · /ia qué IA está activa", "",
        "<i>No apuesto ni prometo resultados: te doy probabilidad y valor esperado.</i>"])
