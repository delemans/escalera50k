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
    escalera_p: float = 0.65
    escalera_cuota: tuple = (1.30, 1.50)
    escalera_gap_h: float = 2.0
    progresion_cuota: tuple = (1.25, 1.50)
    combi_p: float = 0.62
    combi_cuota: tuple = (1.25, 1.75)
    combi_total: tuple = (2.0, 3.5)
    super_p: float = 0.58
    super_total: tuple = (6.0, 20.0)
    super_piernas: tuple = (4, 6)
    max_busqueda: int = 14            # candidatos máx. para combinatoria
    stakes: dict = field(default_factory=lambda: {
        "sencilla": 3000, "escalera": 5000, "progresion": 5000, "combinada": 3000, "super": 1500})


def _min(t: str) -> int:
    h, m = map(int, t.split(":"))
    return h * 60 + m


def _pata(c: dict) -> dict:
    return {"id": c["id"], "sel": c["sel"], "partido": f"{c['h']} vs {c['a']}",
            "t": c["t"], "lg": c["lg"], "o": c["o"]}


def _distintos(cs) -> bool:
    claves = [(c["h"], c["a"]) for c in cs]
    return len(set(claves)) == len(claves)


def elegir_sencillas(cands: list[dict], r: Reglas) -> list[dict]:
    pool = [c for c in cands if not c.get("alerta") and r.sencilla_cuota[0] <= c["o"] <= r.sencilla_cuota[1]]
    pool.sort(key=lambda c: (not c.get("valor"), -c["ev"], -c["p"]))
    elegidas, por_liga, por_hora = [], {}, {}
    for estricto in (True, False):
        for c in pool:
            if len(elegidas) >= r.sencillas_max or c in elegidas:
                continue
            if por_liga.get(c["lg"], 0) >= r.max_por_liga:
                continue
            if estricto and por_hora.get(c["t"], 0) >= r.max_misma_hora:
                continue
            elegidas.append(c)
            por_liga[c["lg"]] = por_liga.get(c["lg"], 0) + 1
            por_hora[c["t"]] = por_hora.get(c["t"], 0) + 1
    return sorted(elegidas, key=lambda c: c["t"])


def escalera(cands: list[dict], r: Reglas) -> tuple[dict | None, str | None]:
    pool = [c for c in cands if not c.get("alerta") and c["p"] >= r.escalera_p
            and r.escalera_cuota[0] <= c["o"] <= r.escalera_cuota[1]]
    pool = sorted(pool, key=lambda c: -c["p"])[: r.max_busqueda]
    mejor, mejor_gap, aviso = None, -1e9, None
    for trio in itertools.combinations(pool, 3):
        if not _distintos(trio):
            continue
        trio = sorted(trio, key=lambda c: c["t"])
        gaps = [(_min(trio[i + 1]["t"]) - _min(trio[i]["t"])) / 60 for i in range(2)]
        g = min(gaps)
        P = math.prod(c["p"] for c in trio)
        ok = g >= r.escalera_gap_h
        clave = (ok, P if ok else g)
        if mejor is None or clave > mejor_gap:
            mejor, mejor_gap = trio, clave
    if not mejor:
        return None, None
    if not mejor_gap[0]:
        aviso = "Escalera sin 2 h entre peldaños: es la más cercana posible."
    S = r.stakes["escalera"]
    o = [c["o"] for c in mejor]
    p = [c["p"] for c in mejor]
    s2 = S * o[0]
    s3 = s2 * o[1] - S
    final = s3 * o[2] + S
    P = math.prod(p)
    ev = (-S * (1 - p[0] * p[1]) + P * (final - S)) / S
    return {"tipo": "escalera", "stake": S, "patas": [_pata(c) for c in mejor],
            "P": round(P, 4), "ev": round(ev, 4), "final": round(final),
            "montos": [S, round(s2), round(s3)]}, aviso


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
    pool = [c for c in cands if not c.get("alerta") and c["p"] >= r.combi_p
            and r.combi_cuota[0] <= c["o"] <= r.combi_cuota[1]]
    pool = sorted(pool, key=lambda c: -c["p"] * c["o"])[: r.max_busqueda]
    return _mejor_multi(pool, (2, 3), r.combi_total, r.stakes["combinada"], "combinada")


def super_(cands, r: Reglas):
    pool = [c for c in cands if not c.get("alerta") and c["p"] >= r.super_p]
    pool = sorted(pool, key=lambda c: -c["p"] * c["o"])[: min(r.max_busqueda, 12)]
    return _mejor_multi(pool, range(r.super_piernas[0], r.super_piernas[1] + 1),
                        r.super_total, r.stakes["super"], "super")


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
    sufijos = {"escalera": "esc", "progresion": "prog", "combinada": "combi", "super": "super"}
    for k, suf in sufijos.items():
        if jug[k]:
            jug[k]["id"] = f"{fecha}-{suf}"
    return jug, avisos
