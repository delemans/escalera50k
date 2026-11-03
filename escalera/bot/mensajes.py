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
ICONO_TIPO = {"sencilla": "🎯", "escalera": "🪜", "progresion": "📈", "combinada": "🔗", "super": "🚀"}
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
    out = [_titulo("🪜", "ESCALERA 50K", fecha_corta(dia["fecha"])),
           f"<i>Actualizado {e(dia.get('actualizado', ''))}</i>", LINEA]
    out += _alertas(dia, ("rojo",))
    out += [f"<b>{e(v.get('titulo', ''))}</b>", e(v.get("texto", "")), ""]
    plan = dia.get("plan", [])
    n = {k: sum(1 for i in plan if i["accion"] == k) for k in ("APOSTAR", "VIGILAR", "NO")}
    total = sum(i["monto"] for i in plan if i["accion"] == "APOSTAR" and i["tipo"] != "progresion")
    out += [f"📊 {dia.get('partidos', 0)} partidos analizados",
            f"🟢 {n['APOSTAR']} apostar · 🟡 {n['VIGILAR']} vigilar · ⚪ {n['NO']} no",
            f"💵 Plan real de hoy: <b>{pesos(total)}</b> (tope {pesos(pol.get('tope'))})", ""]
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
    s = dia.get("semaforo")
    if s:
        out += [f"🚦 <b>¿Se está dando?</b> {SEMAFORO.get(s.get('c'), '⚪')}", e(s.get("t")), ""]
    otras = _alertas(dia, ("naranja", "amarillo", "verde"))
    if otras:
        out += otras + [""]
    out += [LINEA, "Abajo va una tarjeta por jugada con botones.",
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
def plan(dia: dict) -> str | None:
    items = dia.get("plan") or []
    if not items:
        return None
    out = [_titulo("📋", "QUÉ HACER HOY", f"{len(items)} jugadas"), LINEA]
    for i in items:
        ic = ICONO_ACCION[i["accion"]]
        linea = f"{ic} <b>{e(i['hora'])}</b> {ICONO_TIPO.get(i['tipo'], '')} {e(i['titulo'])}"
        if i["accion"] == "APOSTAR":
            det = f"   → <b>{pesos(i['monto'])}</b> si BetPlay paga ≥ <b>{cuota(i['cuota_min'])}</b>"
        elif i["accion"] == "VIGILAR":
            det = f"   → solo si BetPlay paga ≥ <b>{cuota(i['cuota_min'])}</b> (ref {cuota(i['cuota_ref'])})"
        else:
            det = "   → no apostar · solo simulación"
        out += [linea, det]
    out += ["", LINEA, "🟢 apostar · 🟡 vigilar (dime la cuota de BetPlay) · ⚪ no",
            "<i>Confirma siempre la cuota en BetPlay antes de apostar.</i>"]
    return "\n".join(out)


# ---------------------------------------------------------------------------
# 3. Tarjetas por jugada (cada una con botones)
# ---------------------------------------------------------------------------
def tarjeta(dia: dict, item: dict) -> str:
    tipo = item["tipo"]
    acc = item["accion"]
    cab = (f"{ICONO_TIPO.get(tipo, '•')} <b>{e(item['titulo'])}</b>\n"
           f"{ICONO_ACCION[acc]} <b>{TEXTO_ACCION[acc]}</b>"
           + (f" · <b>{pesos(item['monto'])}</b>" if item["monto"] else ""))
    cuerpo = {"sencilla": _cuerpo_sencilla, "escalera": _cuerpo_escalera, "progresion": _cuerpo_progresion,
              "combinada": _cuerpo_multi, "super": _cuerpo_multi}[tipo](dia, item)
    pie = [LINEA, f"Mínima BetPlay <b>{cuota(item['cuota_min'])}</b> · EV {pct(item['ev'], True, 1)}",
           f"<i>{e(item['razon'])}</i>"]
    return "\n".join([cab, LINEA] + cuerpo + pie)


def _cuerpo_sencilla(dia, item):
    p = _pick(dia, item["id"]) or {}
    out = [f"⏱ {e(p.get('t'))} · {e(p.get('lg'))}", f"{e(p.get('h'))} vs {e(p.get('a'))}",
           f"▸ <b>{e(p.get('sel'))}</b>",
           f"Prob. {pct(p.get('p'))} · Ref {cuota(p.get('o'))} ({e(p.get('bk'))})"]
    if p.get("nCasas"):
        out.append(f"<i>{p['nCasas']} casas · StatArea {pct(p.get('sa'))} · mercado {pct(p.get('mk'))}</i>")
    if p.get("noticias"):
        out.append(f"📰 <i>{e(p['noticias'])}</i>")
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
    return out


def _cuerpo_progresion(dia, item):
    j = dia["jugadas"]["progresion"]
    x = j["patas"][0]
    return [f"Reto #{j['reto']} · Paso {j['paso']}",
            f"{barra(j['saldo'], j['meta'])} <b>{pesos(j['saldo'])}</b> / {pesos(j['meta'])}",
            f"{e(x['t'])} · {e(x['partido'])}", f"▸ <b>{e(x['sel'])}</b> @ {cuota(x['o'])}",
            f"Todo el saldo → si gana {pesos(j['saldo'] * x['o'])}",
            f"🎲 Este paso {pct(j['P'])} · 🏁 llegar a la meta {pct(j['Pmeta'], dec=1)}"]


def _cuerpo_multi(dia, item):
    j = dia["jugadas"][item["tipo"]]
    out = [f"<b>{n}.</b> {e(x['t'])} · {e(x['partido'])}\n    ▸ {e(x['sel'])} @ {cuota(x['o'])}"
           for n, x in enumerate(j["patas"], 1)]
    monto = item["monto"] or j["stake"]
    out += ["", f"Cuota total <b>{cuota(j['cuota'])}</b> · prob. {pct(j['P'], dec=1)}",
            f"Con {pesos(monto)} cobras {pesos(monto * j['cuota'])}"]
    if item["tipo"] == "super":
        out.append("⚠️ <i>Gasto pequeño de alto riesgo: lo normal es perderla.</i>")
    return out


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
        "/metodo cómo decide · /silencio activa o quita recordatorios", "",
        "<i>No apuesto ni prometo resultados: te doy probabilidad y valor esperado.</i>"])
