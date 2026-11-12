from escalera import analisis as A
from escalera.nucleo import poisson as PO


def test_mercados_suman_y_marcadores():
    pm = PO.mercados(1.5, 1.0)
    assert abs(pm["1"] + pm["X"] + pm["2"] - 1) < 1e-6
    assert pm["1"] > pm["2"] and 0.4 < pm["O2.5"] < 0.5 and len(pm["marcadores"]) == 3
    assert {x["m"] for x in pm["marcadores"][:2]} <= {"1-0", "1-1"}


def test_lambdas_de_datos_y_ajuste_a_mercado():
    lh0, la0 = PO.lambdas_de_datos({"xg_h": 1.8, "xga_h": 0.9, "xg_a": 1.0, "xga_a": 1.6})
    assert abs(lh0 - 1.7) < 1e-9 and abs(la0 - 0.95) < 1e-9
    lh, la = PO.ajustar_a_mercado(0.55, 0.25, 0.20)
    pm = PO.mercados(lh, la)
    assert abs(pm["1"] - 0.55) < 0.02 and abs(pm["X"] - 0.25) < 0.02


def _cand(**extra):
    return {"h": "A", "a": "B", "lg": "L", "t": "15:00", "verificado": True, "mercado": "1X2", "lado": "1",
            "casas": [{"bk": "Pinnacle", "o": [1.6, 4.0, 5.5]}, {"bk": "Betfair", "o": [1.62, 3.9, 5.6]}], **extra}


def test_con_datos_poisson_entra_en_la_probabilidad_y_hay_abogado():
    sin = A.evaluar(_cand(), True)
    con = A.evaluar(_cand(stats={"xg_h": 2.4, "xga_h": 0.7, "xg_a": 0.8, "xga_a": 2.0}), True)
    assert sin["poisson"]["fuente"] == "mercado" and con["poisson"]["fuente"] == "datos"
    assert con["p"] > sin["p"]                         # los datos ven al local más fuerte que el mercado
    j = con["justificacion"]
    assert len(j["abogado"]) == 3 and j["lecturaPopular"] and j["marcadores"]
    assert "difModelo" in j
