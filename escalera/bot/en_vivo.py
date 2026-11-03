"""
EN VIVO · avisos minuto a minuto de tus apuestas (goles, tarjetas, córners, final)
=================================================================================
Fuente: marcador público de ESPN (site.api.espn.com, gratis y sin clave).
Cada minuto, solo mientras haya partidos tuyos en juego:
  ⚽ gol · 🟨 tarjeta · 🟥 roja (con minuto, equipo y jugador)
  y cómo va cada apuesta: «Más de 4,5 tarjetas: van 3, faltan 2» · «✅ ya ganada»
  🌙 soñadora / combinadas: piernas acertadas, pago potencial y cuánto aceptar de cobro anticipado
Si ESPN no tiene el partido, el bot lo dice una vez y sigue con los demás.
"""
from __future__ import annotations

import datetime as dt
import logging
import re
import time
import unicodedata

import requests

from ..nucleo import cashout as CO
from ..nucleo import mercados as MK
from ..nucleo.formato import cuota, e, pesos
from . import db
from .sync import ahora

log = logging.getLogger("vivo")
ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer"
LIGAS = [("champions", "uefa.champions"), ("europa league", "uefa.europa"), ("conference", "uefa.europa.conf"),
         ("england - premier", "eng.1"), ("championship", "eng.2"), ("fa cup", "eng.fa"), ("league cup", "eng.league_cup"),
         ("spain - laliga2", "esp.2"), ("segunda", "esp.2"), ("spain", "esp.1"), ("copa del rey", "esp.copa_del_rey"),
         ("italy", "ita.1"), ("germany - bundesliga", "ger.1"), ("france", "fra.1"), ("netherlands", "ned.1"),
         ("portugal", "por.1"), ("turkey", "tur.1"), ("mexico", "mex.1"), ("colombia", "col.1"), ("argentina", "arg.1"),
         ("brazil", "bra.1"), ("usa", "usa.1"), ("scotland", "sco.1"), ("belgium", "bel.1"), ("austria", "aut.1"),
         ("denmark", "den.1"), ("sweden", "swe.1"), ("greece", "gre.1"), ("libertadores", "conmebol.libertadores"),
         ("sudamericana", "conmebol.sudamericana")]
POR_DEFECTO = ["uefa.champions", "uefa.europa", "eng.1", "esp.1", "ita.1", "ger.1", "fra.1", "col.1"]
_cache: dict = {}


# ---------------------------------------------------------------------------
# Utilidades puras (con pruebas)
# ---------------------------------------------------------------------------
def normalizar(nombre: str) -> set[str]:
    t = unicodedata.normalize("NFKD", nombre or "").encode("ascii", "ignore").decode().lower()
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    ruido = {"fc", "cf", "ac", "sc", "cd", "club", "de", "the", "afc", "sk", "fk", "as", "vfb", "ssc", "1"}
    return {w for w in t.split() if w not in ruido and len(w) > 1}


def parecido(a: str, b: str) -> float:
    x, y = normalizar(a), normalizar(b)
    return len(x & y) / max(1, min(len(x), len(y))) if x and y else 0.0


def slugs_para(liga: str | None) -> list[str]:
    t = (liga or "").lower()
    for clave, slug in LIGAS:
        if clave in t:
            return [slug] + [s for s in POR_DEFECTO if s != slug]
    return POR_DEFECTO


def estado_pierna(p: dict, gl: int, gv: int, tarjetas: int, corners: int, terminado: bool) -> tuple[str, str]:
    """→ (estado, texto) con estado en ganada | perdida | nula | en_juego."""
    m, lado, linea = p.get("mercado") or "1X2", str(p.get("lado") or ""), p.get("linea")
    if m in ("TARJETAS", "CORNERS", "GOLES"):
        total = {"TARJETAS": tarjetas, "CORNERS": corners, "GOLES": gl + gv}[m]
        nombre = {"TARJETAS": "tarjetas", "CORNERS": "córners", "GOLES": "goles"}[m]
        linea = float(linea)
        if lado == "over":
            if total > linea:
                return "ganada", f"✅ ya ganada ({total} {nombre})"
            falta = int(linea - total) + 1
            return ("perdida", f"❌ terminó con {total} {nombre}") if terminado else \
                ("en_juego", f"van {total}, faltan {falta}")
        if total > linea:
            return "perdida", f"❌ se pasó ({total} {nombre})"
        margen = int(linea - total)
        return ("ganada", f"✅ ganada ({total} {nombre})") if terminado else \
            ("en_juego", f"van {total}, aguanta {margen} más")
    if m == "BTTS":
        ambos = gl > 0 and gv > 0
        if lado == "si":
            return ("ganada", "✅ ya marcaron los dos") if ambos else \
                (("perdida", "❌ no marcaron los dos") if terminado else ("en_juego", f"va {gl}-{gv}"))
        return ("perdida", "❌ marcaron los dos") if ambos else \
            (("ganada", "✅ no marcaron los dos") if terminado else ("en_juego", f"va {gl}-{gv}"))
    if terminado:
        r = MK.resultado(m, lado, linea, gl, gv)
        return {"ganado": "ganada", "perdido": "perdida", "nulo": "nula"}.get(r, "en_juego"), f"final {gl}-{gv}"
    real = "1" if gl > gv else "2" if gv > gl else "X"
    if m == "DNB" and real == "X":
        return "en_juego", f"va {gl}-{gv} (empate devuelve)"
    va = real in lado if m in ("DC", "1X2", "DNB") else False
    return "en_juego", f"va {gl}-{gv} · {'👍 a favor' if va else '👎 en contra'}"


def leer_resumen(d: dict) -> dict:
    """Resumen de ESPN → marcador, reloj, tarjetas, córners y eventos clave."""
    comp = d["header"]["competitions"][0]
    eqs = comp["competitors"]
    local = next(x for x in eqs if x.get("homeAway") == "home")
    visit = next(x for x in eqs if x.get("homeAway") == "away")
    st = comp["status"]["type"]
    eventos, tarjetas = [], 0
    for k in d.get("keyEvents") or []:
        tipo = (k.get("type") or {}).get("text", "")
        es_tarjeta = "Card" in tipo
        es_gol = "Goal" in tipo or "Penalty - Scored" in tipo
        if es_tarjeta:
            tarjetas += 1
        if es_tarjeta or es_gol:
            eventos.append({"id": k.get("id") or f"{tipo}-{(k.get('clock') or {}).get('displayValue')}-{k.get('text', '')[:20]}",
                            "tipo": "roja" if "Red" in tipo else "tarjeta" if es_tarjeta else "gol",
                            "min": (k.get("clock") or {}).get("displayValue", ""),
                            "equipo": (k.get("team") or {}).get("displayName", ""), "texto": k.get("text", "")})
    corners = 0
    for t in (d.get("boxscore") or {}).get("teams", []):
        for s in t.get("statistics", []):
            if s.get("name") == "wonCorners":
                try:
                    corners += int(float(s.get("displayValue") or 0))
                except ValueError:
                    pass
    return {"local": local["team"]["displayName"], "visitante": visit["team"]["displayName"],
            "gl": int(local.get("score") or 0), "gv": int(visit.get("score") or 0),
            "reloj": comp["status"].get("displayClock", ""), "estado": st.get("description", ""),
            "terminado": bool(st.get("completed")), "en_juego": st.get("state") == "in",
            "tarjetas": tarjetas, "corners": corners, "eventos": eventos}


# ---------------------------------------------------------------------------
# Red
# ---------------------------------------------------------------------------
def _get(url, params=None, ttl=50):
    clave = url + str(params)
    if clave in _cache and time.time() - _cache[clave][0] < ttl:
        return _cache[clave][1]
    try:
        r = requests.get(url, params=params, timeout=15)
        d = r.json() if r.ok else None
    except Exception as ex:
        log.warning("ESPN: %s", ex)
        d = None
    _cache[clave] = (time.time(), d)
    return d


def buscar_evento(partido: str, fecha: str, liga: str | None = None) -> tuple[str, str] | None:
    local, _, visit = partido.partition(" vs ")
    dia = fecha.replace("-", "")
    for slug in slugs_para(liga):
        d = _get(f"{ESPN}/{slug}/scoreboard", {"dates": dia}, ttl=600)
        for ev in (d or {}).get("events", []):
            c = ev["competitions"][0]["competitors"]
            h = next((x["team"]["displayName"] for x in c if x.get("homeAway") == "home"), "")
            a = next((x["team"]["displayName"] for x in c if x.get("homeAway") == "away"), "")
            if parecido(local, h) >= 0.5 and parecido(visit, a) >= 0.5:
                return slug, ev["id"]
    return None


def resumen_evento(slug: str, ev_id: str) -> dict | None:
    d = _get(f"{ESPN}/{slug}/summary", {"event": ev_id}, ttl=45)
    try:
        return leer_resumen(d) if d else None
    except (KeyError, StopIteration, TypeError):
        return None


# ---------------------------------------------------------------------------
# Qué seguir hoy
# ---------------------------------------------------------------------------
def apuestas_a_seguir(dia: dict) -> list[dict]:
    """Cada apuesta con sus piernas: [{id, titulo, tipo, stake, cuota, piernas:[{partido, mercado, lado, linea, sel, t, lg, p}]}]."""
    out, picks = [], {p["id"]: p for p in dia.get("picks", []) if p.get("id")}
    for m in dia.get("misApuestas") or []:
        if m.get("resultado") != "pendiente":
            continue
        piernas = m.get("piernas") or [{"partido": m.get("partido"), "mercado": m.get("mercado"), "lado": m.get("lado"),
                                         "linea": m.get("linea"), "sel": m.get("seleccion"), "t": m.get("hora")}]
        out.append({"id": m["id"], "titulo": m.get("seleccion") or m.get("partido"), "tipo": m.get("tipo", "sencilla"),
                    "stake": m.get("stakeReal") or 0, "cuota": m.get("cuotaReal") or 0, "piernas": piernas})
    hoy = dia.get("fecha")
    for i in dia.get("plan") or []:
        if (db.confirmacion(hoy, i["id"]) or {}).get("estado") != "si":
            continue
        if i["tipo"] == "sencilla":
            p = picks.get(i["id"], {})
            piernas = [{"partido": f"{p.get('h')} vs {p.get('a')}", "mercado": p.get("mercado"), "lado": p.get("lado"),
                        "linea": p.get("linea"), "sel": p.get("sel"), "t": p.get("t"), "lg": p.get("lg"), "p": p.get("p")}]
        else:
            j = (dia.get("jugadas") or {}).get(i["tipo"]) or {}
            probs = j.get("probs") or [picks.get(x["id"], {}).get("p") for x in j.get("patas", [])]
            piernas = [{**x, "p": pr} for x, pr in zip(j.get("patas", []), probs)]
        reg = next((a for a in db.registro(hoy) if a.get("ref") == i["id"] and a.get("accion") == "hice"), {})
        out.append({"id": i["id"], "titulo": i["titulo"], "tipo": i["tipo"],
                    "stake": reg.get("valor") or i["monto"], "cuota": reg.get("cuota") or i["cuota_ref"], "piernas": piernas})
    return out


def _hora(t: str | None) -> dt.datetime | None:
    try:
        h, m = map(int, (t or "").split(":"))
        n = ahora()
        return n.replace(hour=h, minute=m, second=0, microsecond=0)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Ciclo: llamarlo cada minuto → lista de mensajes para enviar
# ---------------------------------------------------------------------------
def revisar(dia: dict, banca: float) -> list[str]:
    if not dia or dia.get("fecha") != ahora().date().isoformat():
        return []
    estado = db.get("vivo") or {}
    mensajes = []
    apuestas = apuestas_a_seguir(dia)
    partidos = {}
    for a in apuestas:
        for p in a["piernas"]:
            if p.get("partido"):
                partidos.setdefault(p["partido"], p)
    vivos = {}
    for partido, p in partidos.items():
        inicio = _hora(p.get("t"))
        if inicio and not (inicio - dt.timedelta(minutes=10) <= ahora() <= inicio + dt.timedelta(minutes=140)):
            continue
        st = estado.setdefault(partido, {"vistos": [], "fin": False})
        if st.get("fin"):
            continue
        if not st.get("ev"):
            enc = buscar_evento(partido, dia["fecha"], p.get("lg"))
            if not enc:
                if not st.get("sin_dato"):
                    st["sin_dato"] = True
                    mensajes.append(f"📡 No encuentro <b>{e(partido)}</b> en el marcador en vivo; te aviso solo el final.")
                continue
            st["ev"] = list(enc)
        r = resumen_evento(*st["ev"])
        if not r:
            continue
        vivos[partido] = r
        nuevos = [x for x in r["eventos"] if x["id"] not in st["vistos"]]
        primera = not st["vistos"] and not st.get("anunciado")
        st["vistos"] = [x["id"] for x in r["eventos"]]
        mios = [(a, pi) for a in apuestas for pi in a["piernas"] if pi.get("partido") == partido]
        if primera:
            st["anunciado"] = True
            lineas = [f"📡 <b>EN VIVO</b> · {e(r['local'])} {r['gl']}-{r['gv']} {e(r['visitante'])} · {e(r['reloj'])}"]
            for a, pi in mios:
                lineas.append(f"• {e(pi.get('sel'))}: {e(estado_pierna(pi, r['gl'], r['gv'], r['tarjetas'], r['corners'], r['terminado'])[1])}")
            mensajes.append("\n".join(lineas))
            nuevos = []
        sigue_tarjetas = any((pi.get("mercado") == "TARJETAS") for _, pi in mios)
        for x in nuevos:
            if x["tipo"] in ("tarjeta", "roja") and not sigue_tarjetas:
                continue
            ic = {"gol": "⚽", "tarjeta": "🟨", "roja": "🟥"}[x["tipo"]]
            cab = f"{ic} <b>{e(x['min'])}</b> {e(x['tipo'].upper())} · {e(x['equipo'])}"
            lineas = [cab, f"{e(r['local'])} {r['gl']}-{r['gv']} {e(r['visitante'])}"
                      + (f" · 🟨 {r['tarjetas']} en total" if sigue_tarjetas else "")]
            for a, pi in mios:
                est, txt = estado_pierna(pi, r["gl"], r["gv"], r["tarjetas"], r["corners"], False)
                lineas.append(f"▸ {e(pi.get('sel'))}: {e(txt)}")
            mensajes.append("\n".join(lineas))
        if r["terminado"]:
            st["fin"] = True
            lineas = [f"🏁 <b>FINAL</b> · {e(r['local'])} {r['gl']}-{r['gv']} {e(r['visitante'])}"
                      + (f" · 🟨 {r['tarjetas']} · córners {r['corners']}" if mios else "")]
            for a, pi in mios:
                lineas.append(f"▸ {e(pi.get('sel'))}: {e(estado_pierna(pi, r['gl'], r['gv'], r['tarjetas'], r['corners'], True)[1])}")
            mensajes.append("\n".join(lineas))
    # Multis: piernas acertadas, pago y cobro anticipado
    for a in apuestas:
        if len(a["piernas"]) < 2 or not a.get("stake"):
            continue
        ests = []
        for pi in a["piernas"]:
            r = vivos.get(pi.get("partido"))
            if r:
                ests.append(estado_pierna(pi, r["gl"], r["gv"], r["tarjetas"], r["corners"], r["terminado"])[0])
            else:
                ests.append("pendiente")
        if "perdida" in ests:
            clave = f"multi-perdida-{a['id']}"
            if clave not in estado:
                estado[clave] = True
                mensajes.append(f"❌ <b>{e(a['titulo'])}</b>: se cayó una pierna. Así es este juego; mañana hay otra.")
            continue
        ganadas = ests.count("ganada")
        clave = f"multi-{a['id']}-{ganadas}"
        if ganadas and clave not in estado:
            estado[clave] = True
            pago = a["stake"] * (a["cuota"] or 0)
            restantes = [pi.get("p") for pi, s in zip(a["piernas"], ests) if s != "ganada"]
            linea = [f"🌙 <b>{e(a['titulo'])}</b> · {ganadas}/{len(ests)} ✅",
                     f"Pago si acierta todo: <b>{pesos(pago)}</b> (cuota {cuota(a['cuota'])})"]
            if restantes and all(restantes):
                justo = CO.valor_justo(a["stake"], a["cuota"], restantes)
                umbral = CO.umbral_cobro(justo, banca)
                linea += [f"Valor justo ahora ≈ {pesos(justo)}",
                          f"💸 Si BetPlay te ofrece <b>{pesos(umbral)}</b> o más de cobro anticipado, cóbralo.",
                          "Escríbeme «cobro 45000» con la oferta y te digo si conviene."]
            mensajes.append("\n".join(linea))
    db.put("vivo", estado)
    return mensajes


def evaluar_cobro(dia: dict, oferta: float, banca: float, ref: str | None = None) -> str:
    """Respuesta a «cobro 45000»: compara la oferta con el valor justo de la multi activa."""
    apuestas = [a for a in apuestas_a_seguir(dia) if len(a["piernas"]) >= 2 and (not ref or a["id"] == ref)]
    if not apuestas:
        return "No veo combinadas o soñadoras abiertas tuyas hoy. Dime cuál es o regístrala primero."
    a = max(apuestas, key=lambda x: x["cuota"] or 0)
    estado = db.get("vivo") or {}
    restantes = []
    for pi in a["piernas"]:
        st = estado.get(pi.get("partido"), {})
        r = resumen_evento(*st["ev"]) if st.get("ev") else None
        s = estado_pierna(pi, r["gl"], r["gv"], r["tarjetas"], r["corners"], r["terminado"])[0] if r else "pendiente"
        if s == "perdida":
            return f"❌ {e(a['titulo'])} ya perdió una pierna: si aún te ofrecen algo, cóbralo."
        if s != "ganada":
            restantes.append(pi.get("p") or 0.6)
    justo = CO.valor_justo(a["stake"], a["cuota"], restantes)
    accion, txt = CO.decidir(oferta, justo, banca, a["stake"])
    icono = {"COBRAR": "🟢", "COBRAR · ASEGURA": "🟢", "PARCIAL": "🟡", "AGUANTAR": "⚪"}[accion]
    return (f"{icono} <b>{accion}</b> · {e(a['titulo'])}\nOferta {pesos(oferta)} · valor justo ≈ {pesos(justo)}\n"
            f"Faltan {len(restantes)} piernas · pago total {pesos(a['stake'] * a['cuota'])}\n<i>{e(txt)}</i>")
