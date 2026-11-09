"""
ANÁLISIS DEL DÍA · tubería completa y determinista
=================================================
La tarea de la mañana (Claude en la nube) solo RECOLECTA datos de la web:
el CSV de StatArea, las cuotas por casa y las noticias. Todo el cálculo lo
hace este módulo, con pruebas automáticas, para que los números no dependan
de que un modelo de lenguaje haga bien las cuentas.

  candidatos_statarea()  → qué partidos buscar en el mercado
  evaluar()              → mk, p, EV, cuota mínima, descartes con motivo
  construir_dia()        → dia.json completo + filas nuevas para "apuestas"
"""
from __future__ import annotations

import math
import re

from .nucleo import estadisticas as EST
from .nucleo import jugadas as JUG
from .nucleo import justificacion as JUS
from .nucleo import liquidacion as LIQ
from .nucleo import mercados as MK
from .nucleo import probabilidad as PR
from .nucleo import riesgo as RIESGO
from .nucleo import simulacion as SIM
from .nucleo import staking as STK
from .nucleo import tipster as TIP
from .nucleo import validacion as VAL
from .nucleo import valor as V
from .nucleo.formato import fecha_corta, fecha_larga, pesos

DESVIO_MAX = 0.08
DISPERSION_MAX = 0.04
PESO_MERCADO = 0.85

# (país, palabras del nombre) — StatArea escribe "País - Liga"
LIGAS = [
    ("england", ["premier league", "championship", "fa cup", "league cup", "efl cup"]),
    ("spain", ["laliga", "la liga", "primera division", "segunda", "laliga2", "copa del rey"]),
    ("italy", ["serie a", "coppa italia"]),
    ("germany", ["bundesliga", "dfb pokal"]),
    ("france", ["ligue 1", "coupe de france"]),
    ("netherlands", ["eredivisie", "knvb"]),
    ("portugal", ["primeira", "liga portugal", "taca de portugal"]),
    ("turkey", ["super lig", "süper lig"]),
    ("mexico", ["liga mx"]),
    ("colombia", ["primera a", "liga betplay", "copa colombia"]),
    ("argentina", ["liga profesional", "primera division", "copa argentina"]),
    ("brazil", ["serie a", "brasileirao", "copa do brasil"]),
    ("usa", ["mls"]),
    ("czech", ["chance liga", "1. liga", "first league"]),
    ("sweden", ["allsvenskan"]),
    ("denmark", ["superliga", "superligaen"]),
    ("greece", ["super league"]),
    ("austria", ["bundesliga"]),
    ("belgium", ["pro league", "first division a", "jupiler"]),
    ("scotland", ["premiership", "scottish cup", "league cup"]),
    ("international", ["champions league", "europa league", "conference league",
                       "libertadores", "sudamericana"]),
]
EXCLUIR = ["2. bundesliga", "women", "femen", "u19", "u21", "u23", "reserve", "youth",
           "challenge cup", "playoff", "regional", "amateur"]


def liga_principal(liga: str) -> bool:
    t = liga.lower()
    if any(x in t for x in EXCLUIR):
        return False
    pais, _, nombre = t.partition(" - ")
    for p, nombres in LIGAS:
        if pais.strip().startswith(p) and any(n in nombre for n in nombres):
            return True
    return False


def candidatos_statarea(filas: list[dict], umbral: int = 50, hora_min: str = "07:30",
                        maximo: int = 30) -> list[dict]:
    """Qué buscar en el mercado, por partido y por mercado (1X2, DNB, goles, ambos marcan).
    La tarea busca cuotas solo de estos; tarjetas y córners los agrega ella si encuentra líneas."""
    out = []
    for f in filas:
        if f["time"] < hora_min or not liga_principal(f["league"]):
            continue
        base = {"h": f["home"], "a": f["away"], "lg": f["league"], "t": f["time"], "statarea": f}
        p1, px, p2 = f["p1"], f["pX"], f["p2"]
        for lado, prob in (("1", p1), ("2", p2)):
            if prob >= umbral:
                out.append({**base, "mercado": "1X2", "lado": lado, "fuerza": prob / 100})
            cond = prob / max(1, p1 + p2)
            if 42 <= prob < umbral and cond >= 0.62:
                out.append({**base, "mercado": "DNB", "lado": lado, "fuerza": cond * (1 - px / 100)})
        if f["o25"] >= 62:
            out.append({**base, "mercado": "GOLES", "linea": 2.5, "lado": "over", "fuerza": f["o25"] / 100})
        elif f["o25"] <= 38:
            out.append({**base, "mercado": "GOLES", "linea": 2.5, "lado": "under", "fuerza": 1 - f["o25"] / 100})
        if f["bts"] >= 62:
            out.append({**base, "mercado": "BTTS", "lado": "si", "fuerza": f["bts"] / 100})
        elif f["bts"] <= 38:
            out.append({**base, "mercado": "BTTS", "lado": "no", "fuerza": f["ots"] / 100})
    for c in out:
        c["sel"] = MK.describir(c)
        c["sa"] = MK.prob_statarea(c)
    out.sort(key=lambda c: -c["fuerza"])
    return out[:maximo]


def evaluar(c: dict) -> dict:
    """c = candidato con "mercado", "lado", "linea", "casas" [{bk, o:[…]}] (+ casas1x2, noticias, alerta)."""
    c = dict(c)
    c.setdefault("mercado", "1X2")
    c.setdefault("sel", MK.describir(c))
    try:
        r = MK.prob_mercado(c)
    except (ValueError, KeyError, TypeError, IndexError):
        c.update(mk=None, p=None, ev=None, motivo="Sin cuotas confiables", descartado=True, valor=False)
        c["justificacion"] = {"aFavor": [], "enContra": ["No se encontraron cuotas confiables."],
                              "confianza": 1, "etiqueta": "NO", "resumen": "Sin cuotas confiables."}
        return c
    mk = r["p_gana"]
    sa = MK.prob_statarea(c) if c.get("statarea") else c.get("sa")
    p = PR.mezcla(mk, sa, PESO_MERCADO) if sa is not None else mk
    p_push, o = r["p_push"], r["o"]
    e = MK.ev(p, p_push, o)
    c.update(mk=round(mk, 4), sa=None if sa is None else round(sa, 4), p=round(p, 4), p_push=round(p_push, 4),
             o=o, bk=r["bk"], nCasas=r["n"], dispersion=round(r["dispersion"], 4), afilada=r["afilada"],
             ev=round(e, 4), omin=round(MK.cuota_minima(p, p_push), 3), kelly=round(MK.kelly(p, p_push, o), 4),
             valor=e >= V.MARGEN_VALOR, alerta=bool(c.get("alerta")), soloMercado=sa is None)
    motivo = None
    if sa is not None and abs(sa - mk) > DESVIO_MAX:
        motivo = f"Desvío StatArea−mercado {(sa - mk) * 100:+.1f} pts".replace(".", ",").replace("-", "−")
    elif r["dispersion"] > DISPERSION_MAX:
        motivo = "Las casas no coinciden (dispersión alta)"
    elif c["alerta"]:
        motivo = "Vetado por noticias"
    c["motivo"] = motivo
    c["descartado"] = motivo is not None
    c["justificacion"] = JUS.justificar(c)
    c["confianza"] = c["justificacion"]["confianza"]
    if motivo:
        c["justificacion"]["etiqueta"] = "DESCARTADO"
        c["justificacion"]["enContra"].insert(0, motivo + ".")
    c.pop("statarea", None)
    return c


def _pick_publico(c: dict) -> dict:
    claves = ["id", "h", "a", "lg", "t", "mercado", "lado", "linea", "sel", "o", "bk", "sa", "mk", "p", "p_push",
              "ev", "omin", "kelly", "valor", "noticias", "alerta", "motivo", "nCasas", "dispersion", "afilada",
              "soloMercado", "confianza", "justificacion"]
    return {k: c.get(k) for k in claves}


def _fila_apuesta(base: dict, creado: int) -> dict:
    return {"simulada": True, "real": False, "resultado": "pendiente", "cuotaReal": None,
            "stakeReal": None, "fuenteReal": None, "netoReal": None, "marcador": "",
            "creado": creado, **base}


def construir_dia(entrada: dict) -> dict:
    fecha = entrada["fecha"]
    banca_cfg = entrada.get("banca", {})
    prog_cfg = entrada.get("progresion", {"activo": False})
    filas_previas = entrada.get("apuestas", [])
    creado = int(entrada.get("creadoMs", 0))

    sa_filas, errores = VAL.leer_csv(entrada.get("statarea_csv", ""))
    if entrada.get("ajuste_hora"):
        VAL.ajustar_hora(sa_filas, int(entrada["ajuste_hora"]))
    validacion = VAL.validar(sa_filas)

    evaluados = [evaluar(c) for c in entrada.get("candidatos", [])]
    validacion.append(VAL.favoritos_vs_mercado(evaluados))
    validos = [c for c in evaluados if not c["descartado"]]

    stakes = banca_cfg.get("stakes") or JUG.Reglas().stakes
    reglas = JUG.Reglas(stakes=stakes)
    jug, avisos = JUG.armar(validos, fecha, prog_cfg, reglas)

    usados = set(jug["sencillas"]["ids"])
    for k in ("escalera", "progresion", "combinada", "super"):
        if jug[k]:
            usados |= {p["id"] for p in jug[k]["patas"]}
    picks = [_pick_publico(c) for c in validos if c["id"] in usados]
    picks += [_pick_publico({**c, "id": None}) for c in evaluados if c["descartado"]]
    picks.sort(key=lambda p: (p["id"] is None, p["t"]))

    # Filas nuevas para la base del sitio
    nuevas = []
    por_id = {c["id"]: c for c in validos}
    for n, pid in enumerate(jug["sencillas"]["ids"]):
        c = por_id[pid]
        nuevas.append(_fila_apuesta({"id": pid, "tipo": "sencilla", "fecha": fecha, "hora": c["t"],
                                     "partido": f"{c['h']} vs {c['a']}", "seleccion": c["sel"],
                                     "liga": c["lg"], "cuotaRef": c["o"], "bk": c["bk"], "p": c["p"],
                                     "mk": c["mk"], "sa": c["sa"], "ev": c["ev"],
                                     "stake": stakes["sencilla"]}, creado + n))
    for k, j in ((k, jug[k]) for k in ("escalera", "progresion", "combinada", "super")):
        if not j:
            continue
        if k == "escalera":
            cref = round(math.prod(p["o"] for p in j["patas"]), 3)
        elif k == "progresion":
            cref = j["patas"][0]["o"]
        else:
            cref = j["cuota"]
        nombre = " + ".join(p["sel"].replace("Gana ", "") for p in j["patas"])
        nuevas.append(_fila_apuesta({"id": j["id"], "tipo": k, "fecha": fecha, "hora": j["patas"][0]["t"],
                                     "partido": f"{k.capitalize()}: {nombre}", "seleccion": nombre,
                                     "piernas": [{"id": p["id"], "sel": p["sel"], "partido": p["partido"],
                                                  "t": p["t"], "o": p["o"]} for p in j["patas"]],
                                     "cuotaRef": cref, "p": j["P"], "ev": j["ev"], "stake": j["stake"],
                                     **({"retiro": j["retiro"]} if j.get("retiro") is not None else {})},
                                    creado + 10 + len(nuevas)))

    # Bancas, semáforo y estadísticas
    ini_sis = banca_cfg.get("inicial", 90000)
    ini_real = banca_cfg.get("inicialReal", ini_sis)
    bancas = LIQ.bancas(filas_previas, ini_sis, ini_real)
    pol = STK.PoliticaStake(banca=entrada.get("saldoReal") or bancas["real"], banca_inicial=ini_real)
    dia = {"fecha": fecha, "fechaTexto": fecha_larga(fecha), "actualizado": entrada.get("actualizado", ""),
           "partidos": len(sa_filas), "erroresCsv": errores[:10], "validacion": validacion,
           "picks": picks, "jugadas": jug, "bancas": {**bancas, **entrada.get("variacion", {})},
           "semaforo": EST.semaforo(filas_previas, hoy=fecha),
           "progresionCfg": prog_cfg, "sitio": entrada.get("sitio"), "publicacion": "manana"}
    plan = STK.plan_del_dia(dia, pol)
    # Gestión de riesgo (stop-loss, enfriamiento, modo reducido) sobre tus apuestas reales
    rg = RIESGO.evaluar(filas_previas, pol.banca, fecha, ini_real)
    ec = RIESGO.escalera_crecimiento(prog_cfg) if prog_cfg.get("activo") else None
    if ec:
        pj = jug.get("progresion")
        ec["tabla"] = RIESGO.plan_peldanos(prog_cfg, pj["patas"][0]["o"] if pj else None)
    for i in plan:
        if i.tipo == "progresion" and ec and i.monto:
            i.monto = ec["stake"]
            if ec["asegurado"]:
                i.razon = f"Modo seguro: apartas la base ({pesos(ec['asegurado'])}) y reinviertes solo lo ganado."
            else:
                i.razon = (f"Peldaño {prog_cfg.get('paso', 1)} de {ec['peldanos']}: va TODO lo acumulado. "
                           "Si gana, todo pasa al siguiente; si pierde, la serie reinicia con la base.")
        if rg["factor"] < 1 and i.monto:
            if rg["factor"] == 0:
                i.monto, i.accion, i.razon = 0, "NO", "STOP del día por pérdidas: hoy no se apuesta más."
            else:
                i.monto = pol.redondear(i.monto * rg["factor"])
                i.razon += " (stake al 50 % por gestión de riesgo)"
    dia["riesgo"] = {k: v for k, v in rg.items() if k != "alertas"}
    dia["escaleraCrec"] = ec
    dia["plan"] = [i.dict() for i in plan]
    dia["politica"] = {"banca": pol.banca, "unidad": pol.unidad, "tope": pol.tope_diario, "freno": pol.freno}

    # Monte Carlo del plan real recomendado
    probs = {c["id"]: c["p"] for c in validos}
    sim_in = []
    for i in plan:
        if not i.monto or i.tipo == "progresion":      # la progresión es un fondo aparte
            continue
        if i.tipo == "sencilla":
            sim_in.append({"tipo": "sencilla", "monto": i.monto, "patas": [{"id": i.id, "o": i.cuota_ref}]})
        else:
            j = jug[i.tipo] if i.tipo in jug else None
            if j:
                sim_in.append({"tipo": i.tipo, "monto": i.monto, "retiro": j.get("retiro", 2),
                               "patas": [{"id": p["id"], "o": p["o"]} for p in j["patas"]]})
    dia["simulacion"] = SIM.dia(sim_in, probs) if sim_in else {"n": 0}
    dia["estadisticas"] = {"sistema": EST.resumen(filas_previas, ini_sis),
                           "real": EST.resumen(filas_previas, ini_real, real=True)}
    for k in ("sistema", "real"):                       # curva compacta (máx. 120 puntos)
        cur = dia["estadisticas"][k].get("curva") or []
        if len(cur) > 120:
            dia["estadisticas"][k]["curva"] = cur[:: max(1, len(cur) // 120)] + [cur[-1]]

    dia["porQue"] = {k: JUS.por_que_jugada(k, jug.get(k)) for k in ("escalera", "combinada", "super", "progresion")}
    dia["misApuestas"] = [
        {k: f.get(k) for k in ("id", "fecha", "hora", "partido", "seleccion", "mercado", "lado", "linea", "piernas",
                               "cuotaReal", "stakeReal", "resultado", "marcador", "netoReal", "cupon", "tipo")}
        for f in filas_previas if f.get("real") and (f.get("resultado") == "pendiente" or f.get("fecha") == fecha)]
    dia["veredicto"] = veredicto(dia, avisos, bool(sa_filas))
    dia["alertas"] = rg["alertas"] + [{"nivel": "amarillo", "t": a} for a in avisos] + \
        [{"nivel": "amarillo", "t": a} for a in ((ec or {}).get("avisos") or [])]
    if pol.freno:
        dia["alertas"].insert(0, {"nivel": "rojo", "t": "Banca real bajo el 70 %: stakes reales a la mitad."})
    tip_nuevas = []
    if entrada.get("tipster") or any(f.get("tipster") for f in filas_previas):
        ev_tip = TIP.evaluar(dia, entrada.get("tipster") or [], fecha)
        tip_nuevas = TIP.filas_nuevas(ev_tip["picks"], filas_previas, fecha)
        dia["tipster"] = {**ev_tip, "record": TIP.record(filas_previas)}
    return {"dia": dia, "apuestasNuevas": [f for f in nuevas if f["id"] not in {x.get("id") for x in filas_previas}]
            + tip_nuevas}


def veredicto(dia: dict, avisos: list[str], hay_datos: bool) -> dict:
    nombre_dia = fecha_corta(dia["fecha"]).split()[0]
    if not hay_datos:
        return {"titulo": "Sin datos de StatArea hoy", "texto": "No se pudo leer la fuente; no hay jugadas.",
                "chips": [{"t": "Sin datos", "c": "bad"}]}
    plan = dia["plan"]
    apostar = [i for i in plan if i["accion"] == "APOSTAR" and i["tipo"] != "progresion"]
    vigilar = [i for i in plan if i["accion"] == "VIGILAR"]
    if not plan:
        titulo = f"{nombre_dia} sin jugadas"
        texto = "Ningún candidato pasó los filtros (desvío, dispersión o noticias). Hoy no se apuesta."
    elif not apostar:
        titulo = f"{nombre_dia} en modo papel"
        texto = (f"Ninguna jugada tiene EV positivo con la cuota de referencia. {len(vigilar)} quedan en "
                 "vigilancia: apuesta solo si BetPlay paga la cuota mínima (mándame la cuota y te confirmo).")
    else:
        total = sum(i["monto"] for i in apostar)
        titulo = f"{nombre_dia}: {len(apostar)} jugada{'s' if len(apostar) > 1 else ''} con valor"
        texto = (f"Plan real: {pesos(total)} en {len(apostar)} jugada{'s' if len(apostar) > 1 else ''}, "
                 f"solo si BetPlay paga al menos la mínima de cada una. {len(vigilar)} más en vigilancia.")
    chips = [{"t": f"{len(apostar)} apostar", "c": "good" if apostar else "bad"},
             {"t": f"{len(vigilar)} vigilar", "c": "warn"}]
    chips += [{"t": a[:40], "c": "warn"} for a in avisos]
    return {"titulo": titulo, "texto": texto, "chips": chips}


# ---------------------------------------------------------------------------
# Liquidación desde marcadores
# ---------------------------------------------------------------------------
def resultado_seleccion(sel: str, partido: str, marcador: str | None) -> str:
    """'Gana Bayern' + 'Bayern vs Mainz' + '2-1' → 'ganado'."""
    if not marcador:
        return "pendiente"
    if marcador.lower() in ("aplazado", "suspendido", "nulo", "cancelado"):
        return "nulo"
    m = re.match(r"\s*(\d+)\s*[-–:]\s*(\d+)", marcador)
    if not m:
        return "pendiente"
    gl, gv = int(m.group(1)), int(m.group(2))
    local, _, visit = partido.partition(" vs ")
    equipo = sel.replace("Gana ", "").strip()
    if equipo == local.strip():
        return "ganado" if gl > gv else "perdido"
    if equipo == visit.strip():
        return "ganado" if gv > gl else "perdido"
    raise ValueError(f"No sé si '{sel}' es local o visitante en '{partido}'")


def _marcador(valor) -> tuple[str | None, dict]:
    """'2-1' o {"marcador": "2-1", "tarjetas": 5, "corners": 9} → (texto, extras)."""
    if isinstance(valor, dict):
        return valor.get("marcador"), {k: valor[k] for k in ("tarjetas", "corners") if valor.get(k) is not None}
    return valor, {}


def resultado_pierna(p: dict, valor) -> str:
    marcador, extras = _marcador(valor)
    if not marcador:
        return "pendiente"
    if str(marcador).lower() in ("aplazado", "suspendido", "nulo", "cancelado"):
        return "nulo"
    if not p.get("mercado") or (p["mercado"] == "1X2" and not p.get("lado")):
        return resultado_seleccion(p["sel"], p["partido"], marcador)
    m = re.match(r"\s*(\d+)\s*[-–:]\s*(\d+)", str(marcador))
    if not m:
        return "pendiente"
    return MK.resultado(p["mercado"], p.get("lado"), p.get("linea"), int(m.group(1)), int(m.group(2)), extras)


def liquidar_filas(filas: list[dict], marcadores: dict, progresion: dict | None = None) -> dict:
    """marcadores = {"Local vs Visitante": "2-1" | "aplazado" | {"marcador": "2-1", "tarjetas": 5, "corners": 9}}."""
    cambios, prog = [], progresion
    for f in filas:
        if f.get("resultado") != "pendiente" or f.get("tipster"):     # los de tipster van aparte (TIP.liquidar)
            continue
        piernas = f.get("piernas") or [{"sel": f["seleccion"], "partido": f["partido"], "mercado": f.get("mercado"),
                                        "lado": f.get("lado"), "linea": f.get("linea")}]
        res = [resultado_pierna(p, marcadores.get(p["partido"])) for p in piernas]
        solo_real = not f.get("simulada")
        base = {**f, "stake": f.get("stakeReal") if solo_real else f.get("stake"),
                "cuotaRef": (f.get("cuotaReal") or f.get("cuotaRef")) if solo_real else f.get("cuotaRef"),
                "piernas": f.get("piernas") or [{"o": f.get("cuotaReal") if solo_real else f["cuotaRef"]}]}
        r = LIQ.liquidar(base, res)
        if r["resultado"] == "pendiente":
            continue
        marc = " · ".join(str(_marcador(marcadores.get(p["partido"], "?"))[0]) for p in piernas)
        nf = {**f, **r, "marcador": marc}
        if solo_real:
            nf["netoReal"] = r.get("neto", 0)
            nf["neto"] = None
        elif f.get("real") and f.get("stakeReal"):
            if f["tipo"] == "escalera":
                nf["netoReal"] = round(r["neto"] * f["stakeReal"] / f["stake"]) if f.get("stake") else None
            elif r["resultado"] in ("ganado", "perdido"):
                o = f.get("cuotaReal") or r.get("cuotaRef") or f["cuotaRef"]
                nf["netoReal"] = round(f["stakeReal"] * (o - 1)) if r["resultado"] == "ganado" else -f["stakeReal"]
        cambios.append(nf)
        if f["tipo"] == "progresion" and prog:
            prog = LIQ.avanzar_progresion(prog, r["resultado"], base["stake"], base["cuotaRef"])
    return {"filas": cambios + TIP.liquidar(filas, marcadores), "progresion": prog}
