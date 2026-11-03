"""
PROBABILIDAD · de cuotas a probabilidades limpias
================================================
Métodos estándar para quitar el margen de la casa (los mismos que usan
librerías abiertas como penaltyblog o implied de R):

  multiplicativo  q_i / Σq                     (simple, sesga a los favoritos)
  potencia        q_i^k con Σ q_i^k = 1        (método del sistema)
  shin            modelo de Shin con insiders  (el más usado en la literatura)

consenso() promedia varias casas y devuelve también la dispersión: si las
casas no se ponen de acuerdo, el dato es menos confiable.
"""
from __future__ import annotations

import math
import statistics as st
from dataclasses import dataclass


def _biseccion(f, lo, hi, it=100):
    flo = f(lo)
    for _ in range(it):
        mid = (lo + hi) / 2
        fm = f(mid)
        if (fm > 0) == (flo > 0):
            lo, flo = mid, fm
        else:
            hi = mid
    return (lo + hi) / 2


def validar_cuotas(cuotas: list[float]) -> None:
    if len(cuotas) < 2 or any((o is None) or o <= 1.0 for o in cuotas):
        raise ValueError(f"Cuotas inválidas: {cuotas}")


def margen(cuotas: list[float]) -> float:
    """Margen de la casa (overround). 0,05 = 5 %."""
    validar_cuotas(cuotas)
    return sum(1 / o for o in cuotas) - 1


def multiplicativo(cuotas: list[float]) -> list[float]:
    validar_cuotas(cuotas)
    q = [1 / o for o in cuotas]
    s = sum(q)
    return [x / s for x in q]


def potencia(cuotas: list[float]) -> list[float]:
    validar_cuotas(cuotas)
    q = [1 / o for o in cuotas]
    if abs(sum(q) - 1) < 1e-12:
        return q
    k = _biseccion(lambda k: sum(x ** k for x in q) - 1, 0.2, 5.0)
    return [x ** k for x in q]


def shin(cuotas: list[float]) -> list[float]:
    validar_cuotas(cuotas)
    q = [1 / o for o in cuotas]
    S = sum(q)
    if S <= 1:
        return [x / S for x in q]

    def probs(z):
        return [(math.sqrt(z * z + 4 * (1 - z) * x * x / S) - z) / (2 * (1 - z)) for x in q]

    z = _biseccion(lambda z: sum(probs(z)) - 1, 0.0, 0.4)
    p = probs(z)
    s = sum(p)
    return [x / s for x in p]


METODOS = {"multiplicativo": multiplicativo, "potencia": potencia, "shin": shin}


@dataclass
class Consenso:
    prob: float            # promedio entre casas (método elegido)
    dispersion: float      # desviación estándar entre casas
    mejor_cuota: float
    mejor_casa: str
    n_casas: int
    margen_medio: float
    por_metodo: dict       # el mismo cálculo con los 3 métodos (control)


def consenso(casas: list[dict], indice: int, metodo: str = "potencia") -> Consenso:
    """casas = [{"bk": "Pinnacle", "o": [o1, oX, o2]}, …]; indice 0=local, 2=visitante."""
    validas = []
    for c in casas:
        try:
            validar_cuotas(c["o"])
            validas.append(c)
        except (ValueError, KeyError, TypeError):
            continue
    if not validas:
        raise ValueError("Ninguna casa con cuotas válidas")
    f = METODOS[metodo]
    ps = [f(c["o"])[indice] for c in validas]
    mejor = max(validas, key=lambda c: c["o"][indice])
    por_metodo = {m: st.fmean(METODOS[m](c["o"])[indice] for c in validas) for m in METODOS}
    return Consenso(prob=st.fmean(ps),
                    dispersion=st.pstdev(ps) if len(ps) > 1 else 0.0,
                    mejor_cuota=mejor["o"][indice], mejor_casa=mejor.get("bk", ""),
                    n_casas=len(validas),
                    margen_medio=st.fmean(margen(c["o"]) for c in validas),
                    por_metodo=por_metodo)


def mezcla(mk: float, sa: float, peso_mercado: float = 0.85) -> float:
    return peso_mercado * mk + (1 - peso_mercado) * sa
