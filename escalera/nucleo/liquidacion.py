"""
LIQUIDACIÓN · resultados, netos, bancas y progresión
====================================================
resultado de cada pierna: "ganado" | "perdido" | "nulo" | "pendiente"
"""
from __future__ import annotations

import math


def liquidar(fila: dict, piernas: list[str]) -> dict:
    """Devuelve {resultado, neto, cuotaRef?} para una fila según sus piernas."""
    tipo = fila["tipo"]
    S = fila.get("stake") or 0

    if tipo in ("sencilla", "progresion"):
        r = piernas[0]
        if r == "pendiente":
            return {"resultado": "pendiente"}
        if r == "nulo":
            return {"resultado": "nulo", "neto": 0}
        o = fila["cuotaRef"]
        return {"resultado": r, "neto": round(S * (o - 1)) if r == "ganado" else -S}

    if tipo == "escalera":
        o = [p["o"] for p in fila["piernas"]]
        for i, r in enumerate(piernas):
            if r == "perdido":
                return {"resultado": "perdido", "neto": -S if i < 2 else 0}
            if r == "pendiente":
                return {"resultado": "pendiente"}
        # nulos: el peldaño nulo cuenta como cuota 1
        o = [1.0 if r == "nulo" else x for x, r in zip(o, piernas)]
        return {"resultado": "ganado", "neto": round((S * o[0] * o[1] - S) * o[2])}

    # combinada / super
    if "perdido" in piernas:
        return {"resultado": "perdido", "neto": -S}
    if "pendiente" in piernas:
        return {"resultado": "pendiente"}
    vivas = [p["o"] for p, r in zip(fila["piernas"], piernas) if r != "nulo"]
    if not vivas:
        return {"resultado": "nulo", "neto": 0}
    cuota = math.prod(vivas)
    return {"resultado": "ganado", "neto": round(S * (cuota - 1)), "cuotaRef": round(cuota, 3)}


def neto(fila: dict, real: bool = False) -> float:
    if fila.get("resultado") not in ("ganado", "perdido"):
        return 0.0
    if real:
        if fila.get("netoReal") is not None:
            return fila["netoReal"]
        S = fila.get("stakeReal") or 0
        o = fila.get("cuotaReal") or fila.get("cuotaRef") or 1
        if fila["tipo"] == "escalera" and fila.get("neto") is not None and fila.get("stake"):
            return fila["neto"] * S / fila["stake"]
    else:
        if fila.get("neto") is not None:
            return fila["neto"]
        S, o = fila.get("stake") or 0, fila.get("cuotaRef") or 1
    return S * (o - 1) if fila["resultado"] == "ganado" else -S


def bancas(filas: list[dict], inicial_sistema: float, inicial_real: float) -> dict:
    sis = inicial_sistema + sum(neto(f) for f in filas if f.get("simulada"))
    real = inicial_real + sum(neto(f, True) for f in filas if f.get("real"))
    return {"sistema": round(sis), "real": round(real)}


def avanzar_progresion(cfg: dict, resultado: str, stake: float, cuota: float) -> dict:
    cfg = {**cfg, "historial": list(cfg.get("historial", []))}
    if resultado == "ganado":
        cfg["saldo"] = round(stake * cuota)
        cfg["paso"] += 1
        if cfg["saldo"] >= cfg["meta"]:
            cfg["historial"].append({"reto": cfg["reto"], "pasos": cfg["paso"] - 1,
                                     "final": cfg["saldo"], "resultado": "meta"})
            cfg.update(reto=cfg["reto"] + 1, paso=1, saldo=cfg["base"])
    elif resultado == "perdido":
        cfg["historial"].append({"reto": cfg["reto"], "pasos": cfg["paso"],
                                 "final": 0, "resultado": "perdido"})
        cfg.update(reto=cfg["reto"] + 1, paso=1, saldo=cfg["base"])
    return cfg
