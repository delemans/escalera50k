"""
VALOR · EV, cuota mínima, cuota justa y Kelly
=============================================
EV    = p·o − 1                  ganancia esperada por peso apostado
justa = 1/p                      cuota con EV = 0
omin  = (1 + margen_valor)/p     cuota desde la que hay "valor" (margen 2 %)
Kelly = (p·o − 1)/(o − 1)        fracción óptima de la banca (se usa 1/4)
"""
from __future__ import annotations

from dataclasses import dataclass

MARGEN_VALOR = 0.02


def ev(p: float, o: float) -> float:
    return p * o - 1


def cuota_justa(p: float) -> float:
    return 1 / p


def cuota_minima(p: float, margen: float = MARGEN_VALOR) -> float:
    return (1 + margen) / p


def kelly(p: float, o: float) -> float:
    if o <= 1:
        return 0.0
    return max(0.0, (p * o - 1) / (o - 1))


def prob_multi(ps: list[float]) -> float:
    r = 1.0
    for p in ps:
        r *= p
    return r


@dataclass
class Evaluacion:
    p: float
    cuota: float
    ev: float
    omin: float
    justa: float
    kelly: float
    valor: bool
    nivel: str        # "valor" | "justa" | "negativa"
    texto: str


def evaluar(p: float, o: float, margen: float = MARGEN_VALOR) -> Evaluacion:
    e_ = ev(p, o)
    if e_ >= margen:
        nivel, txt = "valor", "Tiene valor: la cuota paga más de lo que el riesgo exige."
    elif e_ >= 0:
        nivel, txt = "justa", "Justa: casi sin ventaja. No compensa el riesgo."
    else:
        nivel, txt = "negativa", "EV negativo: con esa cuota se pierde dinero a la larga."
    return Evaluacion(p, o, e_, cuota_minima(p, margen), cuota_justa(p), kelly(p, o),
                      e_ >= margen, nivel, txt)
