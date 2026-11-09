"""
JUGADAS · selección determinista (misma entrada → mismas jugadas)
=================================================================
Entrada: candidatos ya evaluados (p, o, ev, omin, valor, alerta, t, lg, id…).
Salida: el bloque "jugadas" del dia.json.
"""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field

from . import valor as V


@dataclass
class Reglas:
    sencillas_max: int = 5
    sencilla_cuota: tuple = (1.30, 2.60)
    max_por_liga: int = 2
    max_misma_hora: int = 2
    escalera_p: float = 0.60           # crecer la banca: cada peldaño con p ≥ 60 % (se prefieren los más altos)
    escalera_cuota: tuple = (1.15, 1.75)    # incluye doble oportunidad y más de 1,5
    escalera_gap_h: float = 2.0
    escalera_peldanos: tuple = (5, 4, 3, 2, 1)   # objetivo: 5; solo baja si el día no da (con aviso)
    escalera_cuota_respaldo: tuple = (1.15, 2.10)   # día flojo: se abre cuota y EV (p ≥ 60 % se mantiene)
    escalera_retiro: int = 2           # antes del peldaño 3 se aparta la base y se sigue solo con la ganancia
    escalera_ev_min: float = -0.05     # no se aceptan peldaños muy mal pagados
    progresion_cuota: tuple = (1.25, 1.60)
    combi_p: float = 0.55
    combi_cuota: tuple = (1.25, 2.20)
    combi_total: tuple = (2.0, 4.5)
    combi_ev_pierna: float = 0.0       # combinada de VALOR: cada pierna con EV ≥ 0
    combi_ev_total: float = 0.02
    super_cuota: tuple = (5.0, 8.0)    # soñadora realista: cuota total 5–8
    super_piernas: tuple = (4, 5)
    super_p: float = 0.65              # cada pierna con p ≥ 65 %
    super_ev_pierna: float = -0.03     # piernas casi justas o con valor
    max_busqueda: int = 14            # candidatos máx. para combinatoria
    mercados_bloqueados: set = field(default_factory=set)   # mercados con mal récord en el registro de picks
    stakes: dict = field(default_factory=lambda: {
        "sencilla": 3000, "escalera": 5000, "progresion": 5000, "combinada": 3000, "super": 1500})


def _min(t: str) -> int:
    h, m = map(int, t.split(":"))
    return h * 60 + m


def _pata(c: dict) -> dict:
    return {"id": c["id"], "sel": c["sel"], "partido": f"{c['h']} vs {c['a']}",
            "t": c["t"], "lg": c["lg"], "o": c["o"], "mercado": c.get("mercado", "1X2"),
            "lado": c.get("lado"), "linea": c.get("linea")}


def _distintos(cs) -> bool:
    claves = [(c["h"], c["a"]) for c in cs]
    return len(set(claves)) == len(claves)


def elegir_sencillas(cands: list[dict], r: Reglas) -> list[dict]:
    pool = [c for c in cands if not c.get("alerta") and r.sencilla_cuota[0] <= c["o"] <= r.sencilla_cuota[1]]
    if len(pool) < 3:                                   # día flojo: se abre el rango para no quedar sin individuales
        pool = [c for c in cands if not c.get("alerta") and 1.20 <= c["o"] <= 3.50]
    pool.sort(key=lambda c: (not c.get("valor"), -c["ev"], -c["p"]))
    elegidas, por_liga, por_hora = [], {}, {}
    for estricto in (True, False):
        for c in pool:
            if len(elegidas) >= r.sencillas_max or c in elegidas:
                continue
            if any((x["h"], x["a"]) == (c["h"], c["a"]) for x in elegidas):
                continue
            if por_liga.get(c["lg"], 0) >= r.max_por_liga:
                continue
            if estricto and por_hora.get(c["t"], 0) >= r.max_misma_hora:
                continue
            elegidas.append(c)
            por_liga[c["lg"]] = por_liga.get(c["lg"], 0) + 1
            por_hora[c["t"]] = por_hora.get(c["t"], 0) + 1
    return sorted(elegidas, key=lambda c: c["t"])


def montos_escalera(S: float, o: list[float], retiro: int = 2) -> dict:
    """Montos de cada peldaño. Hasta el peldaño `retiro` todo lo cobrado pasa al siguiente;
    antes del peldaño retiro+1 se aparta la base S y se sigue solo con la ganancia.
    Devuelve {montos, final (lo que tienes si completa, base incluida), neto}."""
    montos, m = [], S
    for i, x in enumerate(o):
        if i == retiro and i > 0:
            m -= S                       # se aparta la base
        montos.append(m)
        m *= x
    apartado = S if 0 < retiro < len(o) else 0
    return {"montos": montos, "final": m + apartado, "neto": m + apartado - S}


def ev_escalera(p: list[float], o: list[float], retiro: int = 2) -> float:
    """EV por peso apostado: si ganan los primeros `retiro` peldaños la base ya está a salvo."""
    S = 1.0
    r = montos_escalera(S, o, retiro)
    P = math.prod(p)
    if 0 < retiro < len(o):
        Pbase = math.prod(p[:retiro])
        esperado = (Pbase - P) * S + P * r["final"]
    else:
        esperado = P * r["final"]
    return esperado / S - 1


def _mejor_escalera(pool: list[dict], r: Reglas):
    for n in r.escalera_peldanos:
        mejor, mejor_P = None, -1
        for combo in itertools.combinations(pool, n):
            if not _distintos(combo):
                continue
            combo = sorted(combo, key=lambda c: c["t"])
            if n > 1:
                g = min((_min(combo[i + 1]["t"]) - _min(combo[i]["t"])) / 60 for i in range(n - 1))
                if g < r.escalera_gap_h:
                    continue
            P = math.prod(c["p"] for c in combo)
            if P > mejor_P:
                mejor, mejor_P = combo, P
        if mejor:
            return mejor
    return None


def escalera(cands: list[dict], r: Reglas) -> tuple[dict | None, str | None]:
    """Escalera para crecer la banca: hasta 5 peldaños con p ≥ 60 % y ≥ 2 h entre partidos.
    Todos los días sale al menos un peldaño si existe algún pick de 60 %: si con los filtros normales
    no hay, se abre el rango de cuota y se quita el filtro de EV (con aviso)."""
    base = [c for c in cands if not c.get("alerta") and c["p"] >= r.escalera_p
            and c.get("mercado", "1X2") not in r.mercados_bloqueados]
    estricto = [c for c in base if c["ev"] >= r.escalera_ev_min
                and r.escalera_cuota[0] <= c["o"] <= r.escalera_cuota[1]]
    aviso = None
    mejor = _mejor_escalera(sorted(estricto, key=lambda c: -c["p"])[: r.max_busqueda], r)
    if not mejor:
        respaldo = [c for c in base if r.escalera_cuota_respaldo[0] <= c["o"] <= r.escalera_cuota_respaldo[1]]
        mejor = _mejor_escalera(sorted(respaldo, key=lambda c: -c["p"])[: r.max_busqueda], r)
        if mejor:
            aviso = "Escalera de día flojo: ningún pick pasó todos los filtros; es la más probable posible (revisa la cuota mínima)."
    if not mejor:
        return None, "Hoy no hay escalera: ningún pick llega al 60 %."
    if len(mejor) < 5:
        falta = (f"Escalera de {len(mejor)} peldaño{'s' if len(mejor) != 1 else ''}: hoy no hay 5 picks de 60 % "
                 "con cuotas confirmadas y 2 h entre partidos.")
        aviso = f"{aviso} {falta}" if aviso else falta
    S = r.stakes["escalera"]
    o = [c["o"] for c in mejor]
    p = [c["p"] for c in mejor]
    m = montos_escalera(S, o, r.escalera_retiro)
    P = math.prod(p)
    return {"tipo": "escalera", "stake": S, "patas": [_pata(c) for c in mejor],
            "peldanos": len(mejor), "retiro": r.escalera_retiro, "respaldo": bool(aviso),
            "P": round(P, 4), "Pbase": round(math.prod(p[: r.escalera_retiro]), 4),
            "ev": round(ev_escalera(p, o, r.escalera_retiro), 4), "final": round(m["final"]),
            "montos": [round(x) for x in m["montos"]], "probs": [round(x, 4) for x in p]}, aviso


def progresion(cands: list[dict], r: Reglas, cfg: dict) -> dict | None:
    if not cfg.get("activo"):
        return None
    pool = [c for c in cands if not c.get("alerta")
            and r.progresion_cuota[0] <= c["o"] <= r.progresion_cuota[1]]
    if not pool:
        return None
    c = max(pool, key=lambda c: (c["p"], c["ev"]))
    saldo = cfg["saldo"]
    faltan = max(1, math.ceil(math.log(cfg["meta"] / saldo) / math.log(c["o"])))
    return {"tipo": "progresion", "reto": cfg["reto"], "paso": cfg["paso"], "saldo": saldo,
            "base": cfg["base"], "meta": cfg["meta"], "stake": saldo, "patas": [_pata(c)],
            "P": round(c["p"], 4), "ev": round(c["p"] * c["o"] - 1, 4),
            "Pmeta": round(c["p"] ** faltan, 4), "pasosFaltan": faltan}


def _mejor_multi(pool, tamanos, total, stake, tipo):
    mejor, mejor_val = None, -1
    for n in tamanos:
        for combo in itertools.combinations(pool, n):
            if not _distintos(combo):
                continue
            cuota = math.prod(c["o"] for c in combo)
            if not (total[0] <= cuota <= total[1]):
                continue
            P = math.prod(c["p"] for c in combo)
            if P * cuota > mejor_val:
                mejor, mejor_val = combo, P * cuota
    if not mejor:
        return None
    mejor = sorted(mejor, key=lambda c: c["t"])
    cuota = math.prod(c["o"] for c in mejor)
    P = math.prod(c["p"] for c in mejor)
    return {"tipo": tipo, "stake": stake, "patas": [_pata(c) for c in mejor],
            "cuota": round(cuota, 3), "P": round(P, 4), "ev": round(P * cuota - 1, 4),
            "omin": round(V.cuota_minima(P), 3)}


def combinada(cands, r: Reglas):
    """Combinada de VALOR: 2–3 piernas, cada una con EV ≥ 0, y EV total ≥ +2 %.
    Si hoy no existe, sale la MEJOR combinada posible marcada «sin valor» (para vigilar / probar el sistema)."""
    def _buscar(ev_pierna, p_min, cuota_rng, total):
        pool = [c for c in cands if not c.get("alerta") and c["p"] >= p_min and c["ev"] >= ev_pierna
                and cuota_rng[0] <= c["o"] <= cuota_rng[1]]
        pool = sorted(pool, key=lambda c: -(1 + c["ev"]) * c["p"])[: r.max_busqueda]
        return _mejor_multi(pool, (2, 3), total, r.stakes["combinada"], "combinada")
    j = _buscar(r.combi_ev_pierna, r.combi_p, r.combi_cuota, r.combi_total)
    if j and j["ev"] >= r.combi_ev_total:
        j["valor"] = True
        return j
    for evp, pm, rng, tot in ((-0.02, 0.50, (1.20, 2.40), (1.8, 5.0)), (-0.05, 0.45, (1.15, 2.80), (1.6, 6.0))):
        j = _buscar(evp, pm, rng, tot)
        if j:
            j["valor"] = False
            return j
    return None


def super_(cands, r: Reglas):
    """Soñadora para crecer el bank: 4–5 piernas, cada una con p ≥ 65 %, cuota total 5–8.
    Se elige la combinación MÁS PROBABLE dentro de ese rango (una pierna por partido)."""
    for umbral in (r.super_ev_pierna, -0.06):   # si no sale, se abre un poco el filtro de EV
        j = _sonadora(cands, r, umbral)
        if j:
            j["umbralEv"] = umbral
            return j
    return None


def _sonadora(cands, r: Reglas, umbral: float):
    pool = [c for c in cands if not c.get("alerta") and c["p"] >= r.super_p and c["ev"] >= umbral]
    pool = sorted(pool, key=lambda c: (-c["p"], -c["ev"]))[: r.max_busqueda]
    mejor, mejor_P = None, -1
    for n in range(r.super_piernas[0], r.super_piernas[1] + 1):
        for combo in itertools.combinations(pool, n):
            if not _distintos(combo):
                continue
            cuota = math.prod(c["o"] for c in combo)
            if not (r.super_cuota[0] <= cuota <= r.super_cuota[1]):
                continue
            P = math.prod(c["p"] for c in combo)
            if P > mejor_P:
                mejor, mejor_P = combo, P
    if not mejor:
        return None
    elegidas = sorted(mejor, key=lambda c: c["t"])
    cuota = math.prod(c["o"] for c in elegidas)
    P = math.prod(c["p"] for c in elegidas)
    return {"tipo": "super", "stake": r.stakes["super"], "patas": [_pata(c) for c in elegidas],
            "cuota": round(cuota, 2), "P": round(P, 4), "ev": round(P * cuota - 1, 4),
            "omin": round(V.cuota_minima(P), 2), "probs": [round(c["p"], 4) for c in elegidas]}


def armar(cands: list[dict], fecha: str, cfg_prog: dict, r: Reglas | None = None) -> tuple[dict, list[str]]:
    """Devuelve (jugadas, avisos). Asigna ids AAAA-MM-DD-n a las sencillas."""
    r = r or Reglas()
    avisos = []
    senc = elegir_sencillas(cands, r)
    for n, c in enumerate(senc, 1):
        c["id"] = f"{fecha}-{n}"
    # Los candidatos que no son sencilla también necesitan id para las patas
    extra = 1
    for c in cands:
        if not c.get("id"):
            c["id"] = f"{fecha}-c{extra}"
            extra += 1
    esc, aviso = escalera(cands, r)
    if aviso:
        avisos.append(aviso)
    jug = {"sencillas": {"stake": r.stakes["sencilla"], "ids": [c["id"] for c in senc]},
           "escalera": esc, "progresion": progresion(cands, r, cfg_prog),
           "combinada": combinada(cands, r), "super": super_(cands, r)}
    for k, nombre in (("combinada", "combinada"), ("super", "soñadora")):
        if not jug[k]:
            avisos.append(f"Hoy no hay {nombre}: no hay suficientes picks que pasen los filtros.")
    if not senc:
        avisos.append("Hoy no hay individuales: ningún pick pasa los filtros.")
    sufijos = {"escalera": "esc", "progresion": "prog", "combinada": "combi", "super": "super"}
    for k, suf in sufijos.items():
        if jug[k]:
            jug[k]["id"] = f"{fecha}-{suf}"
    return jug, avisos
