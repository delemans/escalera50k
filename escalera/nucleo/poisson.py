"""
POISSON · «el analista de verdad» (prompt 3) y «modelo vs mercado» (prompt 4)
=============================================================================
Goles esperados (λ) de cada equipo → matriz de marcadores (Poisson
independiente, hasta 10 goles) → probabilidad de cada mercado: 1X2, doble
oportunidad, empate no apuesta, ambos marcan, más/menos goles, goles de un
equipo y los 3 marcadores más probables.

λ sale de datos reales cuando la tarea los trae (xG/xGA o goles a favor y
en contra de los últimos 10 partidos, local en casa y visitante fuera):
    λ_local     = (xG_local_casa + xGA_visitante_fuera) / 2
    λ_visitante = (xG_visitante_fuera + xGA_local_casa) / 2
Si no hay datos, λ se ajusta al mercado (1X2 + más/menos 2,5) solo para
describir el partido (marcadores probables, escenarios): ese ajuste NO cuenta
como opinión independiente y no se mezcla en la probabilidad.
"""
from __future__ import annotations

import math

MAX_GOLES = 10


def _pmf(k: int, lam: float) -> float:
    return math.exp(-lam) * lam ** k / math.factorial(k)


def matriz(lh: float, la: float) -> list[list[float]]:
    ph = [_pmf(i, lh) for i in range(MAX_GOLES + 1)]
    pa = [_pmf(j, la) for j in range(MAX_GOLES + 1)]
    return [[ph[i] * pa[j] for j in range(MAX_GOLES + 1)] for i in range(MAX_GOLES + 1)]


def mercados(lh: float, la: float) -> dict:
    m = matriz(lh, la)
    r = range(MAX_GOLES + 1)
    p1 = sum(m[i][j] for i in r for j in r if i > j)
    px = sum(m[i][i] for i in r)
    p2 = sum(m[i][j] for i in r for j in r if i < j)
    tot = lambda f: sum(m[i][j] for i in r for j in r if f(i, j))
    out = {"lh": round(lh, 3), "la": round(la, 3), "1": p1, "X": px, "2": p2,
           "1X": p1 + px, "X2": px + p2, "12": p1 + p2,
           "DNB1": p1 / (p1 + p2), "DNB2": p2 / (p1 + p2),
           "BTTS": tot(lambda i, j: i > 0 and j > 0)}
    for linea in (0.5, 1.5, 2.5, 3.5, 4.5):
        out[f"O{linea}"] = tot(lambda i, j, l=linea: i + j > l)
        out[f"H{linea}"] = tot(lambda i, j, l=linea: i > l)
        out[f"A{linea}"] = tot(lambda i, j, l=linea: j > l)
    marcadores = sorted(((m[i][j], f"{i}-{j}") for i in r for j in r), reverse=True)[:3]
    out["marcadores"] = [{"m": s, "p": round(p, 4)} for p, s in marcadores]
    return out


def lambdas_de_datos(d: dict) -> tuple[float, float] | None:
    """d = {"xg_h", "xga_h", "xg_a", "xga_a"} o {"gf_h", "gc_h", "gf_a", "gc_a"} (promedios por partido)."""
    for a, b, c, e in (("xg_h", "xga_h", "xg_a", "xga_a"), ("gf_h", "gc_h", "gf_a", "gc_a")):
        if all(isinstance(d.get(k), (int, float)) and d[k] >= 0 for k in (a, b, c, e)):
            lh = (d[a] + d[e]) / 2
            la = (d[c] + d[b]) / 2
            if lh > 0 and la > 0:
                return lh, la
    return None


def ajustar_a_mercado(p1: float, px: float, p2: float, p_over25: float | None = None) -> tuple[float, float]:
    """λ local y visitante que mejor reproducen el 1X2 (y el más de 2,5 si lo hay). Búsqueda en rejilla."""
    mejor, err_min = (1.3, 1.1), 9e9
    rejilla = [(i / 5, j / 5) for i in range(2, 23) for j in range(2, 23)]        # 0,4 … 4,4 cada 0,2
    for paso in (0, 1):
        if paso:                                                                 # afinar alrededor del mejor
            b0, b1 = mejor
            rejilla = [(round(b0 + di / 20, 3), round(b1 + dj / 20, 3)) for di in range(-4, 5) for dj in range(-4, 5)
                       if b0 + di / 20 > 0.1 and b1 + dj / 20 > 0.1]
        for lh, la in rejilla:
            m = matriz(lh, la)
            rr = range(MAX_GOLES + 1)
            q1 = sum(m[a][b] for a in rr for b in rr if a > b)
            qx = sum(m[a][a] for a in rr)
            q2 = 1 - q1 - qx
            err = (q1 - p1) ** 2 + (qx - px) ** 2 + (q2 - p2) ** 2
            if p_over25 is not None:
                qo = sum(m[a][b] for a in rr for b in rr if a + b > 2.5)
                err += (qo - p_over25) ** 2
            else:                                    # sin línea de goles: total cerca del promedio del fútbol (≈2,6)
                err += 0.0008 * (lh + la - 2.6) ** 2
            if err < err_min:
                mejor, err_min = (lh, la), err
    return mejor


def prob_seleccion(pm: dict, mercado: str, lado: str, linea=None, equipo=None) -> float | None:
    """Probabilidad Poisson de la selección del candidato (None si el mercado no aplica)."""
    lado = str(lado)
    if mercado == "1X2":
        return pm.get(lado)
    if mercado == "DC":
        return pm.get(lado)
    if mercado == "DNB":
        return pm.get(f"DNB{lado}")
    if mercado == "BTTS":
        return pm["BTTS"] if lado == "si" else 1 - pm["BTTS"]
    if mercado == "GOLES" and linea is not None:
        o = pm.get(f"O{float(linea)}")
        return None if o is None else (o if lado == "over" else 1 - o)
    if mercado == "EQUIPO" and linea is not None and equipo in ("1", "2"):
        o = pm.get(f"{'H' if equipo == '1' else 'A'}{float(linea)}")
        return None if o is None else (o if lado == "over" else 1 - o)
    return None
