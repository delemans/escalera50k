from escalera import analisis as A
from escalera.nucleo import tipster as T

DIA = {"fecha": "2026-11-04", "picks": [
    {"h": "Fenerbahçe", "a": "Liverpool", "sel": "Gana Liverpool", "mercado": "1X2", "p": 0.6461, "alerta": False},
    {"h": "AEK Atenas", "a": "Real Madrid", "sel": "Gana Real Madrid", "p": 0.79, "alerta": True,
     "noticias": "Descartado por desvío"}]}


def test_evaluar_cruza_con_picks_del_dia():
    picks = [
        {"fecha": "2026-11-04", "tipster": "SHARPODS", "partido": "Fenerbahce vs Liverpool", "sel": "Liverpool gana", "cuota": 1.44},
        {"fecha": "2026-11-04", "tipster": "SHARPODS", "partido": "Fenerbahce vs Liverpool", "sel": "Gana Liverpool", "cuota": 1.44},
        {"fecha": "2026-11-04", "tipster": "SHARPODS", "partido": "AEK vs Real Madrid", "sel": "Gana Real Madrid", "cuota": 1.20},
        {"fecha": "2026-11-04", "tipster": "SHARPODS", "partido": "Viking vs Sabah", "sel": "Gana Viking", "cuota": 1.41},
        {"fecha": "2026-11-03", "tipster": "SHARPODS", "partido": "X vs Y", "sel": "Gana X", "cuota": 2.0}]
    r = T.evaluar(DIA, picks)
    v = [p["veredicto"] for p in r["picks"]]
    assert len(v) == 4 and v[0] == "sin_valor"          # el de ayer no entra; "Liverpool gana" también cruza
    assert v[1] == "sin_valor" and r["picks"][1]["omin"] > 1.5      # 1,44 < mínima ~1,58
    assert v[2] == "descartado" and v[3] == "sin_modelo"


def test_combinada_y_valor():
    dia = {"fecha": "2026-11-04", "picks": [{"h": "Ajax", "a": "Benfica", "sel": "Gana Ajax", "p": 0.8},
                                            {"h": "Celtic", "a": "Porto", "sel": "Gana Porto", "p": 0.7}]}
    t = [{"fecha": "2026-11-04", "tipster": "S", "tipo": "combinada", "cuota": 2.2, "sel": "Doble",
          "piernas": [{"partido": "Ajax vs Benfica", "sel": "Gana Ajax"}, {"partido": "Celtic vs Porto", "sel": "Gana Porto"}]}]
    r = T.evaluar(dia, t)["picks"][0]
    assert r["veredicto"] == "valor" and abs(r["p"] - 0.56) < 1e-9


def test_resultado_lenguaje_natural():
    assert T.resultado("Leipzig marca", "Leipzig vs Man City", "1-3") == "ganado"
    assert T.resultado("Real Madrid marca 2 o más", "AEK vs Real Madrid", "0-1") == "perdido"
    assert T.resultado("Más de 2,5 goles", "PSV vs Brujas", "2-1") == "ganado"
    assert T.resultado("Ambos marcan", "Dortmund vs Betis", "2-0") == "perdido"
    assert T.resultado("Gana Liverpool", "Fenerbahçe vs Liverpool", {"marcador": "0-2"}) == "ganado"
    assert T.resultado("Como o empate", "Lens vs Como", "1-1") == "ganado"
    assert T.resultado("Algo raro", "A vs B", "1-0") == "pendiente"
    assert T.resultado("Gana A", "A vs B", "aplazado") == "nulo"


def test_filas_liquidar_y_record():
    ev = T.evaluar(DIA, [{"fecha": "2026-11-04", "tipster": "S", "partido": "Fenerbahce vs Liverpool",
                          "sel": "Gana Liverpool", "cuota": 1.44},
                         {"fecha": "2026-11-04", "tipster": "S", "tipo": "combinada", "sel": "La del medio",
                          "cuota": 2.0, "piernas": [{"partido": "Viking vs Sabah", "sel": "Gana Viking"},
                                                    {"partido": "PSV vs Brujas", "sel": "Más de 2,5 goles"}]}])
    filas = T.filas_nuevas(ev["picks"], [], "2026-11-04")
    assert [f["id"] for f in filas] == ["2026-11-04-t1", "2026-11-04-t2"]
    assert T.filas_nuevas(ev["picks"], filas, "2026-11-04") == []          # no duplica
    assert not any(f["real"] or f["simulada"] for f in filas)                # no tocan bancas
    liq = A.liquidar_filas(filas, {"Fenerbahçe vs Liverpool": "0-2", "Viking vs Sabah": "3-0", "PSV vs Brujas": "1-1"})
    res = {f["id"]: f["resultado"] for f in liq["filas"]}
    assert res == {"2026-11-04-t1": "ganado", "2026-11-04-t2": "perdido"}
    rec = T.record(liq["filas"])
    assert rec["n"] == 2 and rec["aciertos"] == 1 and abs(rec["roi"] - (0.44 - 1) / 2) < 1e-9
    from escalera.nucleo import liquidacion as LIQ
    assert LIQ.bancas(liq["filas"], 100, 100) == {"sistema": 100, "real": 100}
