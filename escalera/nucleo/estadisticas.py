"""
ESTADÍSTICAS · ¿el sistema funciona o es suerte?
================================================
Todo en Python puro (sin dependencias), con las métricas que usan las
herramientas abiertas de evaluación de pronósticos:

  rendimiento   n, aciertos, esperado (Σp), ROI, yield, beneficio
  calibración   Brier, log-loss, tabla por tramos de probabilidad
  significancia prueba binomial (¿aciertos por encima de lo esperado?)
                intervalo de confianza del ROI por bootstrap
  riesgo        máximo drawdown, racha actual, peor racha
  mercado       CLV (cuota tomada vs. cuota de cierre), si existe
  desglose      por tipo de jugada y por liga
"""
from __future__ import annotations

import math
import random
import statistics as st


def _filas_validas(filas, real=False):
    out = []
    for f in filas:
        if f.get("resultado") not in ("ganado", "perdido"):
            continue
        if real and not f.get("real"):
            continue
        if not real and not f.get("simulada"):
            continue
        out.append(f)
    return sorted(out, key=lambda f: (f.get("fecha", ""), f.get("hora", ""), f.get("creado", 0)))


def _stake_neto(f, real):
    from .liquidacion import neto
    S = (f.get("stakeReal") if real else f.get("stake")) or 0
    return S, neto(f, real)


def binomial_cola_superior(k: int, n: int, p: float) -> float:
    """P(X ≥ k) con X ~ Binomial(n, p)."""
    if n == 0:
        return 1.0
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1))


def poisson_binomial_cola(k: int, ps: list[float]) -> float:
    """P(aciertos ≥ k) cuando cada apuesta tiene su propia p (exacto, DP)."""
    dist = [1.0]
    for p in ps:
        nueva = [0.0] * (len(dist) + 1)
        for i, v in enumerate(dist):
            nueva[i] += v * (1 - p)
            nueva[i + 1] += v * p
        dist = nueva
    return sum(dist[k:])


def bootstrap_roi(stakes, netos, n=2000, semilla=7):
    if len(stakes) < 5:
        return None
    rnd = random.Random(semilla)
    idx = range(len(stakes))
    rois = []
    for _ in range(n):
        m = [rnd.choice(idx) for _ in idx]
        s = sum(stakes[i] for i in m)
        if s:
            rois.append(sum(netos[i] for i in m) / s)
    rois.sort()
    return rois[int(0.05 * len(rois))], rois[int(0.95 * len(rois))]


def drawdown(netos, inicial):
    pico, banca, peor = inicial, inicial, 0.0
    curva = [inicial]
    for x in netos:
        banca += x
        curva.append(banca)
        pico = max(pico, banca)
        peor = max(peor, (pico - banca) / pico if pico else 0)
    return peor, curva


def rachas(resultados):
    actual_tipo, actual, peor_perd, mejor_gan, run = None, 0, 0, 0, 0
    prev = None
    for r in resultados:
        run = run + 1 if r == prev else 1
        prev = r
        if r == "perdido":
            peor_perd = max(peor_perd, run)
        else:
            mejor_gan = max(mejor_gan, run)
    if resultados:
        actual_tipo, actual = resultados[-1], run
    return {"actual": actual, "actualTipo": actual_tipo, "peorPerdidas": peor_perd, "mejorGanadas": mejor_gan}


def calibracion(ps, ys, tramos=((0, .5), (.5, .6), (.6, .7), (.7, .8), (.8, 1.01))):
    tabla = []
    for lo, hi in tramos:
        sel = [(p, y) for p, y in zip(ps, ys) if lo <= p < hi]
        if sel:
            tabla.append({"tramo": f"{int(lo*100)}–{min(100, int(hi*100))} %", "n": len(sel),
                          "esperado": st.fmean(p for p, _ in sel), "real": st.fmean(y for _, y in sel)})
    return tabla


def resumen(filas: list[dict], inicial: float, real: bool = False) -> dict:
    fs = _filas_validas(filas, real)
    n = len(fs)
    if n == 0:
        return {"n": 0}
    ps = [f.get("p") or (1 / f["cuotaRef"] if f.get("cuotaRef") else 0.5) for f in fs]
    ys = [1 if f["resultado"] == "ganado" else 0 for f in fs]
    stakes, netos = zip(*(_stake_neto(f, real) for f in fs))
    apostado = sum(stakes)
    benef = sum(netos)
    aciertos = sum(ys)
    esperado = sum(ps)
    brier = st.fmean((p - y) ** 2 for p, y in zip(ps, ys))
    logloss = -st.fmean(math.log(max(1e-9, p if y else 1 - p)) for p, y in zip(ps, ys))
    dd, curva = drawdown(netos, inicial)
    clv = [f["cuotaRef"] / f["cuotaCierre"] - 1 for f in fs if f.get("cuotaCierre") and f.get("cuotaRef")]
    por_tipo, por_liga = {}, {}
    for f, s, x, y in zip(fs, stakes, netos, ys):
        for dic, k in ((por_tipo, f.get("tipo", "?")), (por_liga, f.get("liga") or "Multi")):
            d = dic.setdefault(k, {"n": 0, "aciertos": 0, "apostado": 0, "beneficio": 0})
            d["n"] += 1
            d["aciertos"] += y
            d["apostado"] += s
            d["beneficio"] += x
    for dic in (por_tipo, por_liga):
        for d in dic.values():
            d["roi"] = d["beneficio"] / d["apostado"] if d["apostado"] else 0
    return {
        "n": n, "aciertos": aciertos, "esperado": round(esperado, 2),
        "tasa": aciertos / n, "tasaEsperada": esperado / n,
        "apostado": apostado, "beneficio": round(benef), "roi": benef / apostado if apostado else 0,
        "brier": round(brier, 4), "brierBase": round(st.fmean(p * (1 - p) for p in ps), 4),
        "logloss": round(logloss, 4),
        "pValor": round(poisson_binomial_cola(aciertos, ps), 4),
        "icRoi90": bootstrap_roi(list(stakes), list(netos)),
        "maxDrawdown": round(dd, 4), "curva": [round(c) for c in curva],
        "rachas": rachas([f["resultado"] for f in fs]),
        "clv": st.fmean(clv) if clv else None,
        "calibracion": calibracion(ps, ys), "porTipo": por_tipo, "porLiga": por_liga,
    }


def semaforo(filas: list[dict], dias: int = 7, hoy: str | None = None) -> dict:
    import datetime as dt
    hoy_d = dt.date.fromisoformat(hoy) if hoy else dt.date.today()
    corte = (hoy_d - dt.timedelta(days=dias)).isoformat()
    fs = [f for f in _filas_validas(filas) if f.get("fecha", "") >= corte]
    if not fs:
        return {"c": "warn", "t": "Aún sin jugadas liquidadas en los últimos 7 días."}
    ps = [f.get("p") or 0.5 for f in fs]
    a = sum(1 for f in fs if f["resultado"] == "ganado")
    esp = sum(ps)
    stakes, netos = zip(*(_stake_neto(f, False) for f in fs))
    roi = sum(netos) / sum(stakes) if sum(stakes) else 0
    dif = a - esp
    c = "good" if dif >= -1 else "warn" if dif >= -2.5 else "bad"
    roi_txt = f"{abs(roi) * 100:.1f}".replace(".", ",")
    t = (f"Sistema {'+' if roi >= 0 else '−'}{roi_txt} % en {dias} días; "
         f"{a} de {len(fs)} aciertos ({a / len(fs) * 100:.0f} %, esperado {esp / len(fs) * 100:.0f} %).")
    return {"c": c, "t": t}
