import math

import pytest

from escalera import analisis as A
from escalera.nucleo import estadisticas as EST
from escalera.nucleo import formato as F
from escalera.nucleo import jugadas as J
from escalera.nucleo import liquidacion as L
from escalera.nucleo import probabilidad as PR
from escalera.nucleo import simulacion as SIM
from escalera.nucleo import staking as S
from escalera.nucleo import validacion as VAL
from escalera.nucleo import valor as V

CUOTAS = [1.43, 5.55, 7.40]


# --- probabilidad -----------------------------------------------------------
@pytest.mark.parametrize("metodo", ["multiplicativo", "potencia", "shin"])
def test_metodos_suman_uno(metodo):
    p = PR.METODOS[metodo](CUOTAS)
    assert math.isclose(sum(p), 1, abs_tol=1e-6)
    assert p[0] > p[2] > 0


def test_potencia_coincide_con_scipy():
    scipy = pytest.importorskip("scipy.optimize")
    q = [1 / o for o in CUOTAS]
    k = scipy.brentq(lambda k: sum(x ** k for x in q) - 1, 0.5, 3)
    assert math.isclose(PR.potencia(CUOTAS)[0], q[0] ** k, abs_tol=1e-6)


def test_shin_da_menos_al_favorito_que_multiplicativo():
    assert PR.shin(CUOTAS)[0] > PR.multiplicativo(CUOTAS)[0] - 0.02


def test_consenso_y_dispersion():
    c = PR.consenso([{"bk": "A", "o": [1.40, 5.25, 7.0]}, {"bk": "B", "o": [1.43, 5.55, 7.4]},
                     {"bk": "Mala", "o": [0.9, 2, 3]}], 0)
    assert c.n_casas == 2 and c.mejor_casa == "B" and c.mejor_cuota == 1.43
    assert 0.68 < c.prob < 0.71 and c.dispersion < 0.01


def test_cuotas_invalidas():
    with pytest.raises(ValueError):
        PR.potencia([1.0, 3.0, 4.0])


# --- valor y staking --------------------------------------------------------
def test_valor_basico():
    assert math.isclose(V.ev(0.7, 1.5), 0.05)
    assert math.isclose(V.cuota_minima(0.7), 1.02 / 0.7)
    assert V.kelly(0.5, 1.8) == 0
    assert V.evaluar(0.7, 1.40).nivel == "negativa"


def test_stake_sencilla_100k():
    pol = S.PoliticaStake(banca=100_000, banca_inicial=100_000)
    assert pol.unidad == 2000 and pol.tope_diario == 12000
    m = S.stake_sencilla(0.55, 1.95, pol)            # EV +7 %
    assert 1000 <= m <= 3000 and m % 500 == 0


def test_freno_suave():
    pol = S.PoliticaStake(banca=60_000, banca_inicial=100_000)
    assert pol.freno and pol.unidad == 600


def test_decidir_con_betplay():
    pol = S.PoliticaStake()
    acc, monto, _ = S.decidir_con_cuota_betplay(0.70, 1.40, pol)
    assert acc == "NO" and monto == 0
    acc, monto, _ = S.decidir_con_cuota_betplay(0.70, 1.55, pol)
    assert acc == "APOSTAR" and monto >= 1000


# --- jugadas ----------------------------------------------------------------
def _cand(h, t, p, o, lg="L1"):
    return {"h": h, "a": h + " B", "lg": lg, "t": t, "sel": f"Gana {h}", "p": p, "o": o,
            "ev": p * o - 1, "omin": 1.02 / p, "valor": p * o - 1 >= .02, "alerta": False}


def test_armar_jugadas():
    cands = [_cand("A", "08:00", .74, 1.40, "L1"), _cand("B", "10:30", .70, 1.45, "L2"),
             _cand("C", "13:00", .71, 1.48, "L3"), _cand("D", "15:00", .60, 1.75, "L1"),
             _cand("E", "15:00", .55, 1.95, "L4"), _cand("F", "17:00", .62, 1.70, "L5")]
    jug, avisos = J.armar(cands, "2026-11-07", {"activo": True, "reto": 1, "paso": 1, "saldo": 5000,
                                                "base": 5000, "meta": 50000})
    assert len(jug["sencillas"]["ids"]) == 5
    assert jug["escalera"] and [p["t"] for p in jug["escalera"]["patas"]] == ["08:00", "10:30", "13:00"]
    assert jug["progresion"]["patas"][0]["sel"] == "Gana A"
    c = jug["combinada"]
    assert c is None or not c["valor"] or (2.0 <= c["cuota"] <= 4.5 and c["ev"] >= 0.02)
    assert jug["super"] is None or 5.0 <= jug["super"]["cuota"] <= 8.0
    assert all(a.startswith("Hoy no hay") for a in avisos)


# --- liquidación ------------------------------------------------------------
def test_escalera_netos():
    f = {"tipo": "escalera", "stake": 5000, "piernas": [{"o": 1.3}, {"o": 1.39}, {"o": 1.4}]}
    assert L.liquidar(f, ["ganado", "perdido", "pendiente"])["neto"] == -5000
    assert L.liquidar(f, ["ganado", "ganado", "perdido"])["neto"] == 0
    assert L.liquidar(f, ["ganado", "ganado", "ganado"])["neto"] == 5649


def test_combinada_pierna_nula():
    f = {"tipo": "combinada", "stake": 3000, "piernas": [{"o": 1.5}, {"o": 1.6}]}
    r = L.liquidar(f, ["ganado", "nulo"])
    assert r["resultado"] == "ganado" and r["cuotaRef"] == 1.5 and r["neto"] == 1500
    assert L.liquidar(f, ["perdido", "pendiente"])["resultado"] == "perdido"


def test_progresion():
    cfg = {"reto": 1, "paso": 1, "saldo": 5000, "base": 5000, "meta": 50000, "historial": []}
    c2 = L.avanzar_progresion(cfg, "ganado", 5000, 1.5)
    assert c2["saldo"] == 7500 and c2["paso"] == 2
    c3 = L.avanzar_progresion(c2, "perdido", 7500, 1.4)
    assert c3["reto"] == 2 and c3["saldo"] == 5000 and c3["historial"][-1]["resultado"] == "perdido"


def test_resultado_seleccion():
    assert A.resultado_seleccion("Gana Lyon", "Lyon vs Angers", "2-0") == "ganado"
    assert A.resultado_seleccion("Gana Angers", "Lyon vs Angers", "2-0") == "perdido"
    assert A.resultado_seleccion("Gana Lyon", "Lyon vs Angers", "1-1") == "perdido"
    assert A.resultado_seleccion("Gana Lyon", "Lyon vs Angers", "aplazado") == "nulo"
    assert A.resultado_seleccion("Gana Lyon", "Lyon vs Angers", None) == "pendiente"


def test_bancas_reales_del_historial():
    filas = [{"simulada": True, "tipo": "escalera", "resultado": "perdido", "neto": -5000},
             {"simulada": True, "tipo": "sencilla", "resultado": "ganado", "neto": 1500},
             {"simulada": True, "tipo": "escalera", "resultado": "ganado", "neto": 5649}]
    assert L.bancas(filas, 90000, 100000) == {"sistema": 92149, "real": 100000}


# --- estadísticas y simulación ---------------------------------------------
def test_resumen_estadistico():
    filas = [{"simulada": True, "tipo": "sencilla", "fecha": f"2026-11-0{i}", "p": .7, "stake": 3000,
              "cuotaRef": 1.5, "resultado": "ganado" if i % 3 else "perdido"} for i in range(1, 10)]
    r = EST.resumen(filas, 90000)
    assert r["n"] == 9 and r["aciertos"] == 6 and 0 < r["brier"] < 0.3
    assert 0 <= r["pValor"] <= 1 and r["icRoi90"][0] <= r["roi"] <= r["icRoi90"][1]
    assert r["rachas"]["peorPerdidas"] == 1


def test_poisson_binomial():
    assert math.isclose(EST.poisson_binomial_cola(0, [.5, .5]), 1)
    assert math.isclose(EST.poisson_binomial_cola(2, [.5, .5]), .25)


def test_montecarlo_dia():
    r = SIM.dia([{"tipo": "sencilla", "monto": 2000, "patas": [{"id": "a", "o": 1.5}]}], {"a": .7}, n=5000)
    assert abs(r["pGanar"] - .7) < .03 and r["peor"] == -2000


# --- validación y formato --------------------------------------------------
CSV = """league,time,tip,home,away,p1,pX,p2,h1,hX,h2,o15,o25,o35,bts,ots
International - Champions League,15:00,1,Barcelona,Aston Villa,64,18,18,46,28,26,95,83,60,66,34
Scotland - Challenge Cup Playoffs,14:45,1,Ross County,Celtic B,72,16,12,41,35,24,95,85,73,64,36
England - Championship,14:45,1X,QPR,Burnley,49,31,20,39,40,21,85,65,46,66,34
roto,xx,1,A,B,1,2
"""


def test_csv_y_candidatos():
    filas, errores = VAL.leer_csv(CSV)
    assert len(filas) == 3 and errores
    cands = A.candidatos_statarea(filas)
    assert {c["h"] for c in cands} == {"Barcelona", "QPR"}    # Challenge Cup excluida
    assert any(c["mercado"] == "1X2" and c["h"] == "Barcelona" for c in cands)
    assert not any(c["h"] == "QPR" and c["mercado"] == "1X2" for c in cands)       # QPR < 50 %
    assert all(c.get("sa") is not None for c in cands)
    assert VAL.validar(filas)[0]["c"] == "good"


def test_evaluar_descarta_por_desvio():
    c = A.evaluar({"h": "Barcelona", "a": "Aston Villa", "lg": "UCL", "t": "15:00", "lado": "1",
                   "sel": "Gana Barcelona", "sa": .64, "casas": [{"bk": "Betway", "o": [1.25, 7, 8.5]}]})
    assert c["descartado"] and "Desvío" in c["motivo"]


def test_formato():
    assert F.pesos(-5000) == "−$5.000" and F.pesos(1500, True) == "+$1.500"
    assert F.cuota(1.456) == "1,46" and F.pct(0.031, True, 1) == "+3,1 %"
    assert F.leer_numero("3.000") == 3000 and F.leer_numero("1,45") == 1.45 and F.leer_numero("$2.500") == 2500
    assert F.fecha_larga("2026-11-03") == "Martes 3 de noviembre de 2026"
