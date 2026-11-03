"""Regresión con el historial real del sistema (1–2 nov 2026): los netos deben coincidir con la base."""
from escalera import analisis as A
from escalera.nucleo import liquidacion as L

FILAS = [
    {"id": "2026-10-17-1", "tipo": "escalera", "simulada": True, "resultado": "perdido", "neto": -5000, "stake": 5000},
    {"id": "2026-11-01-1", "tipo": "sencilla", "simulada": True, "stake": 5000, "cuotaRef": 1.30,
     "partido": "Djurgården vs Degerfors", "seleccion": "Gana Djurgården"},
    {"id": "2026-11-01-2", "tipo": "sencilla", "simulada": True, "stake": 5000, "cuotaRef": 1.42,
     "partido": "Lazio vs Cagliari", "seleccion": "Gana Lazio"},
    {"id": "2026-11-01-3", "tipo": "sencilla", "simulada": True, "stake": 5000, "cuotaRef": 1.39,
     "partido": "Elfsborg vs Örgryte", "seleccion": "Gana Elfsborg"},
    {"id": "2026-11-01-4", "tipo": "sencilla", "simulada": True, "stake": 5000, "cuotaRef": 1.40,
     "partido": "Lyon vs Angers", "seleccion": "Gana Lyon"},
    {"id": "2026-11-01-esc", "tipo": "escalera", "simulada": True, "stake": 5000, "cuotaRef": 2.53,
     "piernas": [{"sel": "Gana Djurgården", "partido": "Djurgården vs Degerfors", "o": 1.30},
                 {"sel": "Gana Elfsborg", "partido": "Elfsborg vs Örgryte", "o": 1.39},
                 {"sel": "Gana Lyon", "partido": "Lyon vs Angers", "o": 1.40}]},
    {"id": "2026-11-02-1", "tipo": "sencilla", "simulada": True, "stake": 3000, "cuotaRef": 1.50,
     "partido": "Mallorca vs Cádiz", "seleccion": "Gana Mallorca"},
    {"id": "2026-11-02-prog", "tipo": "progresion", "simulada": True, "stake": 5000, "cuotaRef": 1.50,
     "piernas": [{"sel": "Gana Mallorca", "partido": "Mallorca vs Cádiz", "o": 1.50}]},
]
MARCADORES = {"Djurgården vs Degerfors": "2-1", "Lazio vs Cagliari": "2-1", "Elfsborg vs Örgryte": "2-1",
              "Lyon vs Angers": "2-0", "Mallorca vs Cádiz": "2-1"}


def test_historial_coincide_con_la_base():
    pend = [dict(f, resultado="pendiente") for f in FILAS[1:]]
    r = A.liquidar_filas(pend, MARCADORES, {"reto": 1, "paso": 1, "saldo": 5000, "base": 5000, "meta": 50000})
    netos = {f["id"]: f["neto"] for f in r["filas"]}
    assert netos == {"2026-11-01-1": 1500, "2026-11-01-2": 2100, "2026-11-01-3": 1950, "2026-11-01-4": 2000,
                     "2026-11-01-esc": 5649, "2026-11-02-1": 1500, "2026-11-02-prog": 2500}
    assert r["progresion"]["saldo"] == 7500 and r["progresion"]["paso"] == 2
    todas = [FILAS[0]] + r["filas"]
    assert L.bancas(todas, 90000, 100000) == {"sistema": 102199, "real": 100000}
