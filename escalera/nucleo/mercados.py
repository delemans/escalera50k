"""
MERCADOS · probabilidad, EV y liquidación para cada tipo de apuesta
==================================================================
Mercados soportados (campo "mercado" del candidato):

  1X2        lado "1" | "X" | "2"                      casas: [o1, oX, o2]
  DNB        empate no apuesta, lado "1" | "2"         casas: [o1, o2]  (+ casas1x2 para el empate)
  DC         doble oportunidad, lado "1X" | "12" | "X2" (se deriva de casas1x2)
  GOLES      más/menos goles, linea 1.5/2.5/3.5…, lado "over" | "under"   casas: [over, under]
  BTTS       ambos marcan, lado "si" | "no"            casas: [si, no]
  TARJETAS   más/menos tarjetas, linea, lado "over" | "under"
  CORNERS    más/menos tiros de esquina, linea, lado "over" | "under"

Probabilidad final:
  • mercado (mk): consenso sin margen entre casas, con DOBLE peso a las casas
    "afiladas" (Pinnacle, Betfair, Smarkets, Matchbook, SBOBet), que son las más precisas.
  • StatArea (sa): solo donde aplica (1X2, DNB, DC, GOLES 1.5/2.5/3.5, BTTS).
  • p = 0,85·mk + 0,15·sa ; sin StatArea, p = mk (se marca "solo mercado").
  • DNB devuelve la plata si hay empate: EV = p_gana·o + p_empate − 1.
"""
from __future__ import annotations

import statistics as st

from . import probabilidad as PR

AFILADAS = ("pinnacle", "betfair", "smarkets", "matchbook", "sbobet", "circa")
NOMBRES = {"1X2": "Resultado", "DNB": "Empate no apuesta", "DC": "Doble oportunidad", "GOLES": "Goles",
           "BTTS": "Ambos marcan", "TARJETAS": "Tarjetas", "CORNERS": "Córners"}
LADOS2 = {"over": 0, "under": 1, "si": 0, "no": 1}


def es_afilada(bk: str) -> bool:
    return any(a in (bk or "").lower() for a in AFILADAS)


def _consenso_ponderado(casas: list[dict], indice: int, metodo="potencia"):
    vals, pesos, cuotas = [], [], []
    for c in casas:
        try:
            PR.validar_cuotas(c["o"])
            p = PR.METODOS[metodo](c["o"])[indice]
        except (ValueError, KeyError, TypeError, IndexError):
            continue
        w = 2.0 if es_afilada(c.get("bk")) else 1.0
        vals.append(p)
        pesos.append(w)
        cuotas.append((c["o"][indice], c.get("bk", "")))
    if not vals:
        raise ValueError("sin cuotas válidas")
    media = sum(v * w for v, w in zip(vals, pesos)) / sum(pesos)
    disp = st.pstdev(vals) if len(vals) > 1 else 0.0
    mejor = max(cuotas)
    return {"p": media, "dispersion": disp, "o": mejor[0], "bk": mejor[1], "n": len(vals),
            "afilada": any(es_afilada(c.get("bk")) for c in casas)}


def _p1x2(casas1x2):
    """Probabilidades 1, X, 2 sin margen (consenso ponderado)."""
    return [_consenso_ponderado(casas1x2, i)["p"] for i in range(3)]


def prob_mercado(c: dict) -> dict:
    """Devuelve {p_gana, p_push, o, bk, n, dispersion, afilada}."""
    m = c.get("mercado", "1X2")
    lado = str(c.get("lado", "1"))
    casas = c.get("casas") or []
    if m == "1X2":
        r = _consenso_ponderado(casas, {"1": 0, "X": 1, "2": 2}[lado])
        return {**r, "p_gana": r["p"], "p_push": 0.0}
    if m == "DNB":
        r = _consenso_ponderado(casas, 0 if lado == "1" else 1)
        p_push = 0.0
        if c.get("casas1x2"):
            p1, px, p2 = _p1x2(c["casas1x2"])
            p_push = px
            cond = (p1 if lado == "1" else p2) / (p1 + p2)
            r["p"] = 0.5 * r["p"] + 0.5 * cond          # dos lecturas del mismo mercado
        return {**r, "p_gana": r["p"] * (1 - p_push), "p_push": p_push, "p_cond": r["p"]}
    if m == "DC":
        p1, px, p2 = _p1x2(c.get("casas1x2") or casas)
        p = {"1X": p1 + px, "12": p1 + p2, "X2": px + p2}[lado]
        ofertas = [(x["o"], x.get("bk", "")) for x in (c.get("cuotas_dc") or []) if x.get("o")]
        o, bk = max(ofertas) if ofertas else (c.get("o"), c.get("bk", ""))
        if not o:
            raise ValueError("DC sin cuota")
        r = _consenso_ponderado(c.get("casas1x2") or casas, 0)
        return {"p": p, "p_gana": p, "p_push": 0.0, "o": o, "bk": bk, "n": r["n"],
                "dispersion": r["dispersion"], "afilada": r["afilada"]}
    # mercados de dos salidas
    r = _consenso_ponderado(casas, LADOS2.get(lado, 0))
    return {**r, "p_gana": r["p"], "p_push": 0.0}


def prob_statarea(c: dict) -> float | None:
    """Probabilidad de StatArea para el mismo resultado (o None si no aplica)."""
    f = c.get("statarea")
    if not f:
        return None
    m, lado = c.get("mercado", "1X2"), str(c.get("lado", "1"))
    p1, px, p2 = f["p1"] / 100, f["pX"] / 100, f["p2"] / 100
    if m == "1X2":
        return {"1": p1, "X": px, "2": p2}[lado]
    if m == "DNB":
        return (p1 if lado == "1" else p2) / (p1 + p2) * (1 - px)
    if m == "DC":
        return {"1X": p1 + px, "12": p1 + p2, "X2": px + p2}[lado]
    if m == "GOLES":
        col = {1.5: "o15", 2.5: "o25", 3.5: "o35"}.get(float(c.get("linea", 0)))
        if not col:
            return None
        over = f[col] / 100
        return over if lado == "over" else 1 - over
    if m == "BTTS":
        return f["bts"] / 100 if lado == "si" else f["ots"] / 100
    return None


def ev(p_gana, p_push, o):
    return p_gana * o + p_push - 1


def cuota_minima(p_gana, p_push, margen=0.02):
    return (1 + margen - p_push) / p_gana if p_gana else None


def kelly(p_gana, p_push, o):
    p_pierde = 1 - p_gana - p_push
    if o <= 1:
        return 0.0
    return max(0.0, (p_gana * (o - 1) - p_pierde) / (o - 1))


def describir(c: dict) -> str:
    m, lado, linea = c.get("mercado", "1X2"), str(c.get("lado", "1")), c.get("linea")
    eq = {"1": c.get("h"), "2": c.get("a"), "X": "Empate"}
    if m == "1X2":
        return "Empate" if lado == "X" else f"Gana {eq[lado]}"
    if m == "DNB":
        return f"{eq[lado]} (empate no apuesta)"
    if m == "DC":
        return {"1X": f"{c.get('h')} o empate", "X2": f"{c.get('a')} o empate", "12": "No hay empate"}[lado]
    ln = str(linea).replace(".", ",")
    if m == "GOLES":
        return f"{'Más' if lado == 'over' else 'Menos'} de {ln} goles"
    if m == "BTTS":
        return "Ambos marcan: " + ("sí" if lado == "si" else "no")
    if m == "TARJETAS":
        return f"{'Más' if lado == 'over' else 'Menos'} de {ln} tarjetas"
    if m == "CORNERS":
        return f"{'Más' if lado == 'over' else 'Menos'} de {ln} córners"
    return c.get("sel") or m


# ---------------------------------------------------------------------------
# Liquidación por mercado
# ---------------------------------------------------------------------------
def resultado(m: str, lado: str, linea, gl: int, gv: int, extras: dict | None = None) -> str:
    """gl/gv = goles local/visitante a 90'. extras = {"tarjetas": n, "corners": n}."""
    extras = extras or {}
    lado = str(lado)
    if m == "1X2":
        real = "1" if gl > gv else "2" if gv > gl else "X"
        return "ganado" if real == lado else "perdido"
    if m == "DNB":
        if gl == gv:
            return "nulo"
        return "ganado" if (gl > gv) == (lado == "1") else "perdido"
    if m == "DC":
        real = "1" if gl > gv else "2" if gv > gl else "X"
        return "ganado" if real in lado else "perdido"
    if m in ("GOLES", "TARJETAS", "CORNERS"):
        total = gl + gv if m == "GOLES" else extras.get(m.lower())
        if total is None:
            return "pendiente"
        linea = float(linea)
        if total == linea:
            return "nulo"
        return "ganado" if (total > linea) == (lado == "over") else "perdido"
    if m == "BTTS":
        ambos = gl > 0 and gv > 0
        return "ganado" if ambos == (lado == "si") else "perdido"
    return "pendiente"
