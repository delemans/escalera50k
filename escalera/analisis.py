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

import re

from .nucleo import estadisticas as EST
from .nucleo import jugadas as JUG
from .nucleo import liquidacion as LIQ
from .nucleo import probabilidad as PR
from .nucleo import simulacion as SIM
from .nucleo import staking as STK
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
                        maximo: int = 15) -> list[dict]:
    out = []
    for f in filas:
        if f["time"] < hora_min or not liga_principal(f["league"]):
            continue
        for lado, prob, equipo in (("1", f["p1"], f["home"]), ("2", f["p2"], f["away"])):
            if prob >= umbral:
                out.append({"h": f["home"], "a": f["away"], "lg": f["league"], "t": f["time"],
                            "lado": lado, "sel": f"Gana {equipo}", "sa": prob / 100})
    out.sort(key=lambda c: -c["sa"])
    return out[:maximo]


def evaluar(c: dict) -> dict:
    """c = candidato + casas [{bk, o:[1, X, 2]}] (+ noticias, alerta). Agrega cálculo y motivo."""
    c = dict(c)
    idx = 0 if c.get("lado", "1") == "1" else 2
    try:
        cs = PR.consenso(c.get("casas") or [], idx)
    except ValueError:
        c.update(mk=None, p=None, motivo="Sin cuotas confiables", descartado=True)
        return c
    mk = cs.prob
    p = PR.mezcla(mk, c["sa"], PESO_MERCADO)
    o = cs.mejor_cuota
    c.update(mk=round(mk, 4), p=round(p, 4), o=o, bk=cs.mejor_casa, nCasas=cs.n_casas,
             dispersion=round(cs.dispersion, 4), margen=round(cs.margen_medio, 4),
             mkShin=round(cs.por_metodo["shin"], 4),
             ev=round(V.ev(p, o), 4), omin=round(V.cuota_minima(p), 3),
             valor=V.ev(p, o) >= V.MARGEN_VALOR, alerta=bool(c.get("alerta")))
    motivo = None
    if abs(c["sa"] - mk) > DESVIO_MAX:
        motivo = f"Desvío StatArea−mercado {(c['sa'] - mk) * 100:+.1f} pts".replace(".", ",").replace("-", "−")
    elif cs.dispersion > DISPERSION_MAX:
        motivo = "Las casas no coinciden (dispersión alta)"
    elif c["alerta"]:
        motivo = "Vetado por noticias"
    c["motivo"] = motivo
    c["descartado"] = motivo is not None
    return c


def _pick_publico(c: dict) -> dict:
    claves = ["id", "h", "a", "lg", "t", "sel", "o", "bk", "sa", "mk", "p", "ev", "omin",
              "valor", "noticias", "alerta", "motivo", "nCasas", "dispersion"]
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
            cref = round(j["patas"][0]["o"] * j["patas"][1]["o"] * j["patas"][2]["o"], 3)
        elif k == "progresion":
            cref = j["patas"][0]["o"]
        else:
            cref = j["cuota"]
        nombre = " + ".join(p["sel"].replace("Gana ", "") for p in j["patas"])
        nuevas.append(_fila_apuesta({"id": j["id"], "tipo": k, "fecha": fecha, "hora": j["patas"][0]["t"],
                                     "partido": f"{k.capitalize()}: {nombre}", "seleccion": nombre,
                                     "piernas": [{"id": p["id"], "sel": p["sel"], "partido": p["partido"],
                                                  "t": p["t"], "o": p["o"]} for p in j["patas"]],
                                     "cuotaRef": cref, "p": j["P"], "ev": j["ev"], "stake": j["stake"]},
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
                sim_in.append({"tipo": i.tipo, "monto": i.monto,
                               "patas": [{"id": p["id"], "o": p["o"]} for p in j["patas"]]})
    dia["simulacion"] = SIM.dia(sim_in, probs) if sim_in else {"n": 0}
    dia["estadisticas"] = {"sistema": EST.resumen(filas_previas, ini_sis),
                           "real": EST.resumen(filas_previas, ini_real, real=True)}
    for k in ("sistema", "real"):                       # curva compacta (máx. 120 puntos)
        cur = dia["estadisticas"][k].get("curva") or []
        if len(cur) > 120:
            dia["estadisticas"][k]["curva"] = cur[:: max(1, len(cur) // 120)] + [cur[-1]]

    dia["veredicto"] = veredicto(dia, avisos, bool(sa_filas))
    dia["alertas"] = [{"nivel": "amarillo", "t": a} for a in avisos]
    if pol.freno:
        dia["alertas"].insert(0, {"nivel": "rojo", "t": "Banca real bajo el 70 %: stakes reales a la mitad."})
    return {"dia": dia, "apuestasNuevas": [f for f in nuevas if f["id"] not in {x.get("id") for x in filas_previas}]}


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


def liquidar_filas(filas: list[dict], marcadores: dict, progresion: dict | None = None) -> dict:
    """marcadores = {"Local vs Visitante": "2-1" | "aplazado"}. Devuelve filas cambiadas."""
    cambios, prog = [], progresion
    for f in filas:
        if f.get("resultado") != "pendiente":
            continue
        piernas = f.get("piernas") or [{"sel": f["seleccion"], "partido": f["partido"]}]
        res = [resultado_seleccion(p["sel"], p["partido"], marcadores.get(p["partido"])) for p in piernas]
        r = LIQ.liquidar({**f, "piernas": f.get("piernas") or [{"o": f["cuotaRef"]}]}, res)
        if r["resultado"] == "pendiente":
            continue
        marc = " · ".join(marcadores.get(p["partido"], "?") for p in piernas)
        nf = {**f, **r, "marcador": marc}
        if f.get("real") and f.get("stakeReal"):
            if f["tipo"] == "escalera":
                nf["netoReal"] = round(r["neto"] * f["stakeReal"] / f["stake"]) if f.get("stake") else None
            elif r["resultado"] in ("ganado", "perdido"):
                o = f.get("cuotaReal") or r.get("cuotaRef") or f["cuotaRef"]
                nf["netoReal"] = round(f["stakeReal"] * (o - 1)) if r["resultado"] == "ganado" else -f["stakeReal"]
        cambios.append(nf)
        if f["tipo"] == "progresion" and prog:
            prog = LIQ.avanzar_progresion(prog, r["resultado"], f["stake"], f["cuotaRef"])
    return {"filas": cambios, "progresion": prog}
