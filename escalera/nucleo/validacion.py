"""
VALIDACIÓN · ¿los datos de StatArea vienen sanos hoy?
====================================================
"""
from __future__ import annotations

import csv
import io
import statistics as st

CAMPOS = ["league", "time", "tip", "home", "away", "p1", "pX", "p2", "h1", "hX", "h2",
          "o15", "o25", "o35", "bts", "ots"]
NUM = CAMPOS[5:]


def leer_csv(texto: str) -> tuple[list[dict], list[str]]:
    """Lee el CSV de StatArea; devuelve (filas, errores). Tolera filas rotas."""
    filas, errores, vistos = [], [], set()
    for i, r in enumerate(csv.DictReader(io.StringIO(texto.strip())), 2):
        try:
            f = {k: (r[k] or "").strip() for k in CAMPOS}
            for k in NUM:
                f[k] = int(float(f[k]))
            h, m = map(int, f["time"].split(":"))
            assert 0 <= h < 24 and 0 <= m < 60
        except Exception as ex:
            errores.append(f"Fila {i}: {type(ex).__name__}")
            continue
        clave = (f["home"].lower(), f["away"].lower())
        if clave in vistos:
            errores.append(f"Fila {i}: duplicada")
            continue
        vistos.add(clave)
        filas.append(f)
    return filas, errores


def ajustar_hora(filas, horas: int):
    for f in filas:
        h, m = map(int, f["time"].split(":"))
        f["time"] = f"{(h + horas) % 24:02d}:{m:02d}"
    return filas


def _estado(desvio):
    return "good" if abs(desvio) < 3 else "warn" if abs(desvio) < 6 else "bad"


def validar(filas: list[dict]) -> list[dict]:
    n = len(filas)
    if not n:
        return [{"p": "Datos de StatArea", "r": "0 partidos", "e": "Sin datos", "c": "bad"}]

    def cuenta(cond):
        return sum(1 for f in filas if cond(f))

    def fila_regla(nombre, k):
        return {"p": nombre, "r": f"{k} de {n}", "e": "Pasa" if k == n else f"{n - k} con error",
                "c": "good" if k == n else "warn" if k >= 0.95 * n else "bad"}

    def coherente(f):
        m = max((("1", f["p1"]), ("X", f["pX"]), ("2", f["p2"])), key=lambda x: x[1])[0]
        return m in f["tip"]

    out = [fila_regla("1 + X + 2 = 100", cuenta(lambda f: abs(f["p1"] + f["pX"] + f["p2"] - 100) <= 1)),
           fila_regla("BTS + OTS = 100", cuenta(lambda f: abs(f["bts"] + f["ots"] - 100) <= 1)),
           fila_regla("H1 + HX + H2 = 100", cuenta(lambda f: abs(f["h1"] + f["hX"] + f["h2"] - 100) <= 1)),
           fila_regla("O1,5 ≥ O2,5 ≥ O3,5", cuenta(lambda f: f["o15"] >= f["o25"] >= f["o35"]))]
    k = cuenta(coherente)
    out.append({"p": "TIP coherente con el resultado más probable", "r": f"{k} de {n}",
                "e": "Pasa" if k == n else "Aceptable (tips dobles 1X/X2/12)" if k >= .85 * n else "Muchos tips raros",
                "c": "good" if k == n else "warn" if k >= .85 * n else "bad"})
    m1, mx, m2 = (st.fmean(f[c] for f in filas) for c in ("p1", "pX", "p2"))
    d = max(abs(m1 - 45), abs(mx - 26), abs(m2 - 29))
    out.append({"p": "Promedio 1 / X / 2 (ref. 45/26/29)",
                "r": f"{m1:.1f} / {mx:.1f} / {m2:.1f}".replace(".", ","),
                "e": "Dentro del margen" if d < 3 else f"Desvío máx. {d:.1f} pts".replace(".", ","), "c": _estado(d)})
    for campo, nombre, lo, hi in (("o25", "Promedio O2,5 (ref. 50−55 %)", 50, 55),
                                  ("bts", "Promedio BTS (ref. 50−53 %)", 50, 53)):
        v = st.fmean(f[campo] for f in filas)
        d = 0 if lo <= v <= hi else (v - hi if v > hi else v - lo)
        out.append({"p": nombre, "r": f"{v:.1f} %".replace(".", ","),
                    "e": "Dentro del margen" if d == 0 else
                    f"{abs(d):.1f} pts {'por encima' if d > 0 else 'por debajo'}".replace(".", ","),
                    "c": _estado(d)})
    return out


def favoritos_vs_mercado(evaluados: list[dict]) -> dict:
    """Fila final: cuántos candidatos quedaron dentro del ±8 pts."""
    con = [c for c in evaluados if c.get("mk") is not None and c.get("sa") is not None]
    dentro = [c for c in con if abs(c["sa"] - c["mk"]) <= 0.08]
    peores = sorted(con, key=lambda c: -abs(c["sa"] - c["mk"]))[:2]
    detalle = "; ".join(f"{c['sel'].replace('Gana ', '')} {(c['sa'] - c['mk']) * 100:+.1f}".replace(".", ",").replace("-", "−")
                        for c in peores)
    return {"p": "Favoritos frente al mercado",
            "r": f"{len(evaluados)} candidatos · {len(con)} con cuota · {len(dentro)} dentro de ±8 pts",
            "e": detalle or "Sin cuotas", "c": "good" if len(dentro) >= max(1, len(con) // 2) else "warn" if dentro else "bad"}
