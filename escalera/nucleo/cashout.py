"""
COBRO ANTICIPADO (cash out) · ¿cobrar ya o aguantar?
===================================================
valor justo = stake × cuota total × Π p(piernas que faltan)
  (lo que "vale" el boleto hoy según las probabilidades del sistema)

Decisión:
  COBRAR            la oferta es ≥ 95 % del valor justo (te pagan lo que vale)
  COBRAR · ASEGURA  la oferta es ≥ 20 % de tu banca y ≥ 60 % del valor justo:
                    cambia tu banca de verdad; asegurar vale más que el EV que regalas
  PARCIAL           oferta ≥ 80 % del justo y ≥ 20 veces el stake: cobra una parte si BetPlay lo permite
  AGUANTAR          la oferta regala demasiado valor
"""
from __future__ import annotations

import math


def valor_justo(stake: float, cuota_total: float, p_restantes: list[float]) -> float:
    return stake * cuota_total * math.prod(p_restantes) if p_restantes else stake * cuota_total


def decidir(oferta: float, justo: float, banca: float, stake: float) -> tuple[str, str]:
    if justo <= 0:
        return "COBRAR", "El boleto ya no tiene valor esperado: cobra lo que ofrezcan."
    r = oferta / justo
    pct = f"{r * 100:.0f} %"
    if r >= 0.95:
        return "COBRAR", f"Te ofrecen el {pct} de lo que vale: cobrar es justo."
    if banca and oferta >= 0.20 * banca and r >= 0.60:
        return "COBRAR · ASEGURA", (f"La oferta es {oferta / banca * 100:.0f} % de tu banca ({pct} del valor justo). "
                                    "Asegurar crece tu bank aunque regales algo de valor.")
    if r >= 0.80 and oferta >= 20 * stake:
        return "PARCIAL", f"Te ofrecen el {pct} del valor justo: cobra una parte y deja correr el resto."
    return "AGUANTAR", f"Solo te ofrecen el {pct} de lo que vale: regalarías mucho valor."


def umbral_cobro(justo: float, banca: float) -> float:
    """Oferta mínima que conviene aceptar (para avisarlo antes de que la consultes)."""
    return min(0.95 * justo, max(0.60 * justo, 0.20 * banca)) if banca else 0.95 * justo
