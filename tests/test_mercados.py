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


def test_sonadora_realista_cuota_5_a_8():
    from escalera.nucleo import jugadas as J
    cands = [_c(f"E{i}", f"{8 + i:02d}:00", 0.70, 1.45) for i in range(6)] + [_c("Flojo", "20:00", 0.55, 1.90)]
    j = J.super_(cands, J.Reglas())
    assert j and 5.0 <= j["cuota"] <= 8.0 and 4 <= len(j["patas"]) <= 5
    assert all(x["sel"] != "Gana Flojo" for x in j["patas"])          # p < 65 % no entra
    assert all(p >= 0.65 for p in j["probs"])
    assert J.super_([_c(f"B{i}", f"{8 + i:02d}:00", 0.55, 1.95) for i in range(6)], J.Reglas()) is None


def test_escalera_cinco_peldanos_70():
    from escalera.nucleo import jugadas as J
    cands = [_c(f"E{i}", f"{8 + 2 * i:02d}:00", 0.72, 1.40) for i in range(6)] + [_c("Medio", "09:00", 0.60, 1.45)]
    j, aviso = J.escalera(cands, J.Reglas(stakes={**J.Reglas().stakes, "escalera": 4000}))
    assert j and aviso is None and len(j["patas"]) == 5 and j["peldanos"] == 5
    assert all(x["sel"] != "Gana Medio" for x in j["patas"])
    # 4000 → 5600 → 7840; se aparta la base 4000 → 3840 sigue → 5376 → 7526,4 → final 10536 + 4000
    assert j["montos"] == [4000, 5600, 3840, 5376, 7526]
    assert j["final"] == 14537
    # con pocos picks de 70 % baja a 3 peldaños
    j3, _ = J.escalera(cands[:3], J.Reglas())
    assert j3 and len(j3["patas"]) == 3


def test_escalera_sale_todos_los_dias():
    from escalera.nucleo import jugadas as J
    # un solo pick de 60 %+ con buena cuota → escalera de 1 peldaño, con aviso de que faltan peldaños
    j, aviso = J.escalera([_c("A", "10:00", 0.62, 1.62), _c("B", "12:00", 0.50, 2.10)], J.Reglas())
    assert j and len(j["patas"]) == 1 and j["patas"][0]["sel"] == "Gana A" and "1 peldaño" in aviso
    # con 5 picks bien espaciados (incluida doble oportunidad a 1,20) no hay aviso
    cinco = [_c(f"E{i}", f"{7 + 3 * i:02d}:00", 0.80, 1.20) for i in range(5)]
    j, aviso = J.escalera(cinco, J.Reglas())
    assert j and len(j["patas"]) == 5 and aviso is None
    # día flojo: el único pick de 60 %+ está mal pagado → sale igual, marcado como respaldo
    j, aviso = J.escalera([_c("A", "10:00", 0.66, 1.30)], J.Reglas())
    assert j and j["respaldo"] and aviso and aviso.startswith("Escalera de día flojo")
    # sin ningún pick de 60 % no hay escalera
    j, aviso = J.escalera([_c("A", "10:00", 0.55, 1.80)], J.Reglas())
    assert j is None and "60 %" in aviso


def test_escalera_fondo_fijo_fuera_del_tope():
    from escalera.nucleo import staking as S
    dia = {"picks": [], "jugadas": {"escalera": {"id": "e", "tipo": "escalera", "P": 0.4, "ev": -0.02, "stake": 5000,
                                                 "patas": [{"id": "a", "o": 1.5, "t": "10:00"}, {"id": "b", "o": 1.6, "t": "13:00"}]}}}
    pol = S.PoliticaStake(banca=20000, banca_inicial=20000, escalera_fija=5000)
    i = [x for x in S.plan_del_dia(dia, pol) if x.tipo == "escalera"][0]
    assert i.accion == "APOSTAR" and i.monto == 5000          # 25 % de la banca: no lo recorta el tope diario


def test_liquidar_escalera_cinco():
    from escalera.nucleo import liquidacion as L
    fila = {"tipo": "escalera", "stake": 4000, "retiro": 2, "piernas": [{"o": 1.40}] * 5}
    assert L.liquidar(fila, ["ganado", "perdido"] + ["pendiente"] * 3) == {"resultado": "perdido", "neto": -4000}
    assert L.liquidar(fila, ["ganado", "ganado", "ganado", "perdido", "pendiente"])["neto"] == 0
    assert L.liquidar(fila, ["ganado"] * 5) == {"resultado": "ganado", "neto": 10537}
    vieja = {"tipo": "escalera", "stake": 5000, "piernas": [{"o": 1.4}, {"o": 1.4}, {"o": 1.3}]}   # filas de 3 sin "retiro"
    assert L.liquidar(vieja, ["ganado"] * 3)["neto"] == round((5000 * 1.4 * 1.4 - 5000) * 1.3)


def test_combinada_solo_con_valor():
    from escalera.nucleo import jugadas as J
    buenas = [_c("A", "08:00", .70, 1.50), _c("B", "10:00", .66, 1.60)]
    malas = [_c("C", "12:00", .70, 1.38), _c("D", "14:00", .68, 1.40)]
    j = J.combinada(buenas + malas, J.Reglas())
    assert j and {x["sel"] for x in j["patas"]} <= {"Gana A", "Gana B"} and j["ev"] >= 0.02
    assert j["valor"] is True
    respaldo = J.combinada(malas, J.Reglas())                # sin valor: sale la mejor posible, marcada
    assert respaldo is None or respaldo["valor"] is False


def test_escalera_crecimiento_real_avanza():
    fila = {"id": "x1", "tipo": "progresion", "simulada": False, "real": True, "resultado": "pendiente",
            "partido": "Shakhtar Donetsk vs Sporting CP", "seleccion": "Menos de 5,5 tarjetas", "mercado": "TARJETAS",
            "linea": 5.5, "lado": "under", "cuotaReal": 1.54, "cuotaRef": 1.54, "stakeReal": 9000}
    prog = {"reto": 1, "paso": 1, "saldo": 9000, "base": 9000, "meta": 50000, "historial": []}
    r = A.liquidar_filas([fila], {"Shakhtar Donetsk vs Sporting CP": {"marcador": "0-1", "tarjetas": 3}}, prog)
    assert r["filas"][0]["netoReal"] == 4860 and r["progresion"]["saldo"] == 13860 and r["progresion"]["paso"] == 2


def test_candidatos_escalera_y_franjas():
    filas = []
    for i, h in enumerate(["07:30", "09:45", "12:00", "14:15", "16:30", "19:00"]):
        filas.append({"league": "Bulgaria - Second Professional League", "time": h, "tip": "1",
                      "home": f"L{i}", "away": f"V{i}", "p1": 55, "pX": 25, "p2": 20, "h1": 40, "hX": 40, "h2": 20,
                      "o15": 80, "o25": 55, "o35": 30, "bts": 50, "ots": 50})
    filas.append({"league": "U19 - Youth League", "time": "10:00", "tip": "1", "home": "J", "away": "K",
                  "p1": 70, "pX": 20, "p2": 10, "h1": 50, "hX": 30, "h2": 20, "o15": 90, "o25": 70, "o35": 50,
                  "bts": 60, "ots": 40})
    cands = A.candidatos_statarea(filas)
    assert {c["t"] for c in cands} == {"07:30", "09:45", "12:00", "14:15", "16:30", "19:00"}   # todas las franjas
    assert any(c["mercado"] == "DC" and c["lado"] == "1X" for c in cands)
    assert any(c["mercado"] == "GOLES" and c["linea"] == 1.5 for c in cands)
    assert not any(c["h"] == "J" for c in cands)                                                # juveniles fuera
    assert not A.candidatos_statarea(filas, amplia=False)                                         # solo principales
    assert all(c["t"] >= "12:00" for c in A.candidatos_statarea(filas, hora_min="12:00"))


def test_partido_no_verificado_se_descarta():
    base = {"h": "A", "a": "B", "lg": "L", "t": "15:00", "mercado": "1X2", "lado": "1",
            "casas": [{"bk": "Pinnacle", "o": [1.5, 4.0, 6.0]}, {"bk": "Bet365", "o": [1.5, 4.2, 6.5]}]}
    assert A.evaluar({**base, "verificado": False})["descartado"]
    assert "no confirmado" in A.evaluar(base, exigir_verificado=True)["motivo"]
    assert not A.evaluar({**base, "verificado": True}, exigir_verificado=True)["descartado"]


def test_registro_de_picks_y_rendimiento():
    from escalera.nucleo import estadisticas as EST
    filas = [{"tipo": "pick", "mercado": "DC", "p": 0.8, "cuotaRef": 1.25, "resultado": "ganado", "usado": True}] * 24 + \
            [{"tipo": "pick", "mercado": "DC", "p": 0.8, "cuotaRef": 1.25, "resultado": "perdido"}] * 6 + \
            [{"tipo": "pick", "mercado": "BTTS", "p": 0.65, "cuotaRef": 1.6, "resultado": "ganado"}] * 12 + \
            [{"tipo": "pick", "mercado": "BTTS", "p": 0.65, "cuotaRef": 1.6, "resultado": "perdido"}] * 18
    r = EST.rendimiento_picks(filas)
    assert r["total"]["n"] == 60
    assert r["porMercado"]["DC"]["real"] == 0.8 and not r["porMercado"]["DC"]["bloqueado"]
    assert r["porMercado"]["BTTS"]["bloqueado"]                 # 40 % real vs 65 % esperado
    assert r["usados"]["n"] == 24
    from escalera.nucleo import jugadas as J
    c = {**_c("A", "10:00", 0.7, 1.4), "mercado": "BTTS"}
    j, _ = J.escalera([c], J.Reglas(mercados_bloqueados={"BTTS"}))
    assert j is None


def test_racha_escaleras():
    from escalera.nucleo import estadisticas as EST
    f = lambda d, r, n: {"tipo": "escalera", "fecha": d, "id": d, "resultado": r, "neto": n}
    assert EST.racha_escaleras([f("2026-11-01", "ganado", 900), f("2026-11-02", "perdido", -5000),
                                f("2026-11-03", "perdido", -5000), f("2026-11-04", "perdido", -5000)]) == 3
    assert EST.racha_escaleras([f("2026-11-03", "perdido", -5000), f("2026-11-04", "perdido", 0)]) == 0


def test_mercado_goles_de_equipo():
    assert MK.resultado("EQUIPO", "over", 0.5, 1, 0, {"equipo": "1"}) == "ganado"
    assert MK.resultado("EQUIPO", "over", 0.5, 1, 0, {"equipo": "2"}) == "perdido"
    assert MK.describir({"mercado": "EQUIPO", "equipo": "1", "lado": "over", "linea": 0.5, "h": "Bayern", "a": "X"}) \
        == "Bayern: más de 0,5 goles"
    assert A.resultado_pierna({"mercado": "EQUIPO", "equipo": "2", "lado": "under", "linea": 1.5,
                               "sel": "x", "partido": "A vs B"}, "3-1") == "ganado"


def test_analisis_registra_todos_los_picks_y_detalle():
    import json
    from pathlib import Path
    raiz = Path(__file__).resolve().parent.parent
    e = json.loads((raiz / "ejemplos/entrada_ejemplo.json").read_text())
    e["statarea_csv"] = (raiz / "ejemplos/statarea_ejemplo.csv").read_text()
    out = A.construir_dia(e)
    picks = [f for f in out["apuestasNuevas"] if f["tipo"] == "pick"]
    assert len(picks) == sum(1 for c in e["candidatos"]) and all(f["stake"] == 0 and not f["simulada"] for f in picks)
    assert all(f["piernas"][0]["mercado"] for f in picks)
    assert "rendimientoPicks" in out["dia"]
    for k in ("escalera", "super", "combinada"):
        j = out["dia"]["jugadas"].get(k)
        if j:
            assert len(j["detalle"]) == len(j["patas"]) and j["detalle"][0]["razones"]
