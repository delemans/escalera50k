import math

from escalera import analisis as A
from escalera.nucleo import mercados as MK

FILA = {"p1": 32, "pX": 33, "p2": 35, "o15": 87, "o25": 68, "o35": 45, "bts": 68, "ots": 32}


def test_dnb_con_empate_devuelto():
    c = {"mercado": "DNB", "lado": "2", "h": "Man United", "a": "Roma",
         "casas": [{"bk": "Pinnacle", "o": [1.95, 1.90]}, {"bk": "Bet365", "o": [1.90, 1.90]}],
         "casas1x2": [{"bk": "Pinnacle", "o": [2.90, 3.40, 2.70]}]}
    r = MK.prob_mercado(c)
    assert 0.2 < r["p_push"] < 0.35 and r["p_gana"] < r["p_cond"]
    e = MK.ev(r["p_gana"], r["p_push"], 1.92)
    assert math.isclose(e, r["p_gana"] * 1.92 + r["p_push"] - 1)
    assert MK.describir(c) == "Roma (empate no apuesta)"


def test_evaluar_multimercado():
    for c in [
        {"mercado": "GOLES", "linea": 2.5, "lado": "over", "h": "A", "a": "B", "statarea": FILA,
         "casas": [{"bk": "Pinnacle", "o": [1.70, 2.20]}, {"bk": "X", "o": [1.72, 2.10]}]},
        {"mercado": "BTTS", "lado": "si", "h": "A", "a": "B", "statarea": FILA,
         "casas": [{"bk": "Pinnacle", "o": [1.65, 2.25]}]},
        {"mercado": "TARJETAS", "linea": 5.5, "lado": "under", "h": "A", "a": "B",
         "casas": [{"bk": "Pinnacle", "o": [2.30, 1.62]}, {"bk": "Y", "o": [2.40, 1.55]}]},
    ]:
        r = A.evaluar(c)
        assert r["p"] and r["o"] and r["justificacion"]["aFavor"] + r["justificacion"]["enContra"]
        assert 1 <= r["confianza"] <= 5
        if c["mercado"] == "TARJETAS":
            assert r["soloMercado"] and r["sa"] is None


def test_casa_afilada_pesa_doble():
    casas = [{"bk": "Pinnacle", "o": [1.50, 2.70]}, {"bk": "Otra", "o": [1.70, 2.20]}]
    r = MK.prob_mercado({"mercado": "GOLES", "linea": 2.5, "lado": "over", "casas": casas})
    p_pin = 1 / 1.5 / (1 / 1.5 + 1 / 2.7)
    assert abs(r["p"] - p_pin) < abs(r["p"] - 0.5)          # más cerca de Pinnacle


def test_resultados_por_mercado():
    assert MK.resultado("DNB", "2", None, 1, 1) == "nulo"
    assert MK.resultado("DNB", "2", None, 0, 1) == "ganado"
    assert MK.resultado("DC", "X2", None, 2, 2) == "ganado"
    assert MK.resultado("GOLES", "over", 2.5, 2, 1) == "ganado"
    assert MK.resultado("BTTS", "no", None, 2, 0) == "ganado"
    assert MK.resultado("TARJETAS", "under", 5.5, 0, 0, {"tarjetas": 4}) == "ganado"
    assert MK.resultado("TARJETAS", "over", 4.5, 0, 0, {}) == "pendiente"


def test_liquidar_apuestas_reales_de_hoy():
    filas = [
        {"id": "x1", "tipo": "sencilla", "simulada": False, "real": True, "resultado": "pendiente",
         "partido": "Shakhtar Donetsk vs Sporting CP", "seleccion": "Menos de 5,5 tarjetas", "mercado": "TARJETAS",
         "linea": 5.5, "lado": "under", "cuotaReal": 1.54, "cuotaRef": 1.54, "stakeReal": 9000},
        {"id": "x2", "tipo": "sencilla", "simulada": False, "real": True, "resultado": "pendiente",
         "partido": "Galatasaray vs VfB Stuttgart", "seleccion": "Más de 4,5 tarjetas", "mercado": "TARJETAS",
         "linea": 4.5, "lado": "over", "cuotaReal": 2.0, "cuotaRef": 2.0, "stakeReal": 1000},
        {"id": "x3", "tipo": "sencilla", "simulada": False, "real": True, "resultado": "pendiente",
         "partido": "Manchester United vs AS Roma", "seleccion": "Roma (empate no apuesta)", "mercado": "DNB",
         "lado": "2", "cuotaReal": 2.14, "cuotaRef": 2.14, "stakeReal": 1000},
    ]
    marc = {"Shakhtar Donetsk vs Sporting CP": {"marcador": "1-2", "tarjetas": 4},
            "Galatasaray vs VfB Stuttgart": {"marcador": "2-2"},             # falta el dato de tarjetas
            "Manchester United vs AS Roma": "1-1"}
    r = {f["id"]: f for f in A.liquidar_filas(filas, marc)["filas"]}
    assert r["x1"]["resultado"] == "ganado" and r["x1"]["netoReal"] == 4860
    assert "x2" not in r                                                      # sigue pendiente
    assert r["x3"]["resultado"] == "nulo" and r["x3"]["netoReal"] == 0


def _c(h, t, p, o):
    return {"id": h, "h": h, "a": h + " B", "lg": "L", "t": t, "sel": f"Gana {h}", "p": p, "o": o, "ev": p * o - 1, "alerta": False}


def test_sonadora_cuota_100_con_valor():
    from escalera.nucleo import jugadas as J
    cands = [_c(f"E{i}", f"{8 + i:02d}:00", 0.55, 1.95) for i in range(8)] + [_c("Malo", "20:00", 0.30, 2.5)]
    j = J.super_(cands, J.Reglas())
    assert j and j["cuota"] >= 100 and all(x["sel"] != "Gana Malo" for x in j["patas"])
    assert J.super_([_c("A", "08:00", .5, 1.9)], J.Reglas()) is None


def test_combinada_solo_con_valor():
    from escalera.nucleo import jugadas as J
    buenas = [_c("A", "08:00", .70, 1.50), _c("B", "10:00", .66, 1.60)]
    malas = [_c("C", "12:00", .70, 1.38), _c("D", "14:00", .68, 1.40)]
    j = J.combinada(buenas + malas, J.Reglas())
    assert j and {x["sel"] for x in j["patas"]} <= {"Gana A", "Gana B"} and j["ev"] >= 0.02
    assert J.combinada(malas, J.Reglas()) is None


def test_escalera_crecimiento_real_avanza():
    fila = {"id": "x1", "tipo": "progresion", "simulada": False, "real": True, "resultado": "pendiente",
            "partido": "Shakhtar Donetsk vs Sporting CP", "seleccion": "Menos de 5,5 tarjetas", "mercado": "TARJETAS",
            "linea": 5.5, "lado": "under", "cuotaReal": 1.54, "cuotaRef": 1.54, "stakeReal": 9000}
    prog = {"reto": 1, "paso": 1, "saldo": 9000, "base": 9000, "meta": 50000, "historial": []}
    r = A.liquidar_filas([fila], {"Shakhtar Donetsk vs Sporting CP": {"marcador": "0-1", "tarjetas": 3}}, prog)
    assert r["filas"][0]["netoReal"] == 4860 and r["progresion"]["saldo"] == 13860 and r["progresion"]["paso"] == 2
