"""
SIMULACIÓN · Monte Carlo del plan del día y del riesgo a largo plazo
====================================================================
dia(): reparte 20.000 escenarios del día (cada pick gana con su p; las multi
comparten piernas, así que se simulan partido por partido, no jugada por jugada).
largo_plazo(): repite un día típico N días y estima la probabilidad de perder
el 30 % o el 50 % de la banca (riesgo de ruina) con la política de stakes.
"""
from __future__ import annotations

import random
import statistics as st


def _resultado_jugada(j: dict, gana: dict) -> float:
    S = j["monto"]
    if not S:
        return 0.0
    patas = j["patas"]
    if j["tipo"] == "escalera":
        retiro = j.get("retiro", 2)
        for i, p in enumerate(patas):
            if not gana[p["id"]]:
                return -S if i < retiro else 0.0
        m = S
        for i, p in enumerate(patas):
            if i == retiro and i > 0:
                m -= S
            m *= p["o"]
        return m + (S if 0 < retiro < len(patas) else 0) - S
    if all(gana[p["id"]] for p in patas):
        c = 1.0
        for p in patas:
            c *= p["o"]
        return S * (c - 1)
    return -S


def dia(jugadas: list[dict], probs: dict, n: int = 20_000, semilla: int = 11) -> dict:
    """jugadas = [{"tipo", "monto", "patas": [{"id", "o"}]}], probs = {id: p}."""
    rnd = random.Random(semilla)
    activos = [j for j in jugadas if j.get("monto")]
    if not activos:
        return {"n": 0}
    ids = sorted({p["id"] for j in activos for p in j["patas"]})
    res = []
    for _ in range(n):
        gana = {i: rnd.random() < probs[i] for i in ids}
        res.append(sum(_resultado_jugada(j, gana) for j in activos))
    res.sort()
    apostado = sum(j["monto"] for j in activos)
    return {"n": n, "apostado": apostado, "esperado": round(st.fmean(res)),
            "pGanar": sum(1 for x in res if x > 0) / n,
            "pPerderTodo": sum(1 for x in res if x <= -apostado + 1) / n,
            "p10": round(res[int(.10 * n)]), "p50": round(res[n // 2]), "p90": round(res[int(.90 * n)]),
            "peor": round(res[0]), "mejor": round(res[-1])}


def largo_plazo(ev_medio: float, apuestas_dia: int, stake_pct: float, cuota_media: float,
                dias: int = 60, caminos: int = 3000, semilla: int = 5) -> dict:
    """Riesgo de ruina con apuestas sencillas típicas (aproximación)."""
    rnd = random.Random(semilla)
    p = (1 + ev_medio) / cuota_media
    finales, caida30, caida50 = [], 0, 0
    for _ in range(caminos):
        b, minimo = 1.0, 1.0
        for _ in range(dias * apuestas_dia):
            s = b * stake_pct
            b += s * (cuota_media - 1) if rnd.random() < p else -s
            minimo = min(minimo, b)
        finales.append(b)
        caida30 += minimo <= 0.70
        caida50 += minimo <= 0.50
    finales.sort()
    return {"pCaida30": caida30 / caminos, "pCaida50": caida50 / caminos,
            "mediana": finales[caminos // 2], "p10": finales[int(.1 * caminos)],
            "p90": finales[int(.9 * caminos)], "pTerminarArriba": sum(f > 1 for f in finales) / caminos}
