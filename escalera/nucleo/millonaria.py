"""
ESCALERA MILLONARIA · plan por hitos con la plata protegida
===========================================================
Idea: la banca NO se arriesga entera. Solo un fondo fijo sube peldaño a
peldaño (todo lo cobrado al siguiente), un peldaño por franja horaria
(07–09, 09–12, 12–15, 15–18, 18–21, 21+), con picks de 1,40–1,60 y 60 %+
de no perder (empate no apuesta primero). Al cruzar cada hito se aparta
una parte de lo ganado: si un peldaño falla, se pierde solo lo que seguía
subiendo, nunca lo asegurado ni el resto de la banca.

Las probabilidades son exactas para una serie «todo a todo» con cuota y
probabilidad medias (p^n). Sirven para dimensionar, no son promesas.
"""
from __future__ import annotations

import math

FRANJAS = [("07:00", "09:00"), ("09:00", "12:00"), ("12:00", "15:00"), ("15:00", "18:00"),
           ("18:00", "21:00"), ("21:00", "23:59")]


def peldanos_para(desde: float, hasta: float, cuota: float) -> int:
    return max(0, math.ceil(math.log(hasta / desde) / math.log(cuota))) if hasta > desde else 0


def plan(banca: float, meta: float = 3_000_000, fondo: float | None = None, saldo_serie: float | None = None,
         cuota: float = 1.50, p: float = 0.65, hitos: list[float] | None = None, asegurar: float = 0.5) -> dict:
    """Tabla de tramos hasta la meta. En cada hito se aparta `asegurar` de lo que sube y sigue el resto.
    Devuelve tramos con peldaños, probabilidad del tramo y acumulada, y cuánto queda asegurado."""
    fondo = fondo or min(banca, max(5000.0, round(banca * 0.15, -2)))
    sube = saldo_serie or fondo
    hitos = sorted(h for h in (hitos or [50_000, 150_000, 500_000, 1_500_000, meta]) if h > sube) or [meta]
    tramos, acum, asegurado, total_pel = [], 1.0, 0.0, 0
    for h in hitos:
        n = peldanos_para(sube, h, cuota)
        p_tramo = p ** n
        acum *= p_tramo
        total_pel += n
        llega = sube * cuota ** n
        guarda = 0.0 if h == hitos[-1] else llega * asegurar
        asegurado += guarda
        tramos.append({"hasta": h, "desde": round(sube), "peldanos": n, "pTramo": round(p_tramo, 4),
                       "pAcumulada": round(acum, 5), "llega": round(llega), "aseguras": round(guarda),
                       "aseguradoTotal": round(asegurado), "dias": math.ceil(n / 3)})
        sube = llega - guarda
    ev_peldano = p * cuota - 1
    return {"banca": round(banca), "fondo": round(fondo), "saldoSerie": round(saldo_serie or fondo), "meta": meta,
            "cuota": cuota, "p": p, "evPeldano": round(ev_peldano, 4), "tramos": tramos,
            "peldanosTotales": total_pel, "pMeta": round(acum, 6),
            "pTodoATodo": round(p ** peldanos_para(saldo_serie or fondo, meta, cuota), 6),
            "franjas": FRANJAS,
            "reglas": [
                f"Solo sube el fondo de la serie (${round(fondo):,}); el resto de la banca no se toca.".replace(",", "."),
                "Un peldaño por franja horaria y 2 h entre partidos; si una franja no tiene pick apto, se espera.",
                "Cada peldaño: cuota 1,40–1,60, 60 %+ de no perder, empate no apuesta primero, y BetPlay debe pagar la mínima.",
                f"Al cruzar cada hito apartas el {int(asegurar * 100)} % de lo que llevas; lo apartado no vuelve a subir.",
                "Si un peldaño falla, la serie arranca otra vez con el fondo; nunca se sube el monto para recuperar.",
            ]}
