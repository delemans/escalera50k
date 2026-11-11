import datetime as dt

from escalera import analisis as A
from escalera.fuentes import odds_api as OA

AHORA = dt.datetime(2026, 11, 11, 14, 0, tzinfo=dt.timezone.utc)      # 09:00 Bogotá


def _ev(h, a, hora_utc, h2h, totales):
    bks = []
    for (bk, o), tot in zip(h2h, totales):
        mk = [{"key": "h2h", "outcomes": [{"name": h, "price": o[0]}, {"name": "Draw", "price": o[1]}, {"name": a, "price": o[2]}]}]
        mk.append({"key": "totals", "outcomes": [{"name": "Over", "price": tot[0], "point": 2.5}, {"name": "Under", "price": tot[1], "point": 2.5}]})
        bks.append({"key": bk.lower(), "title": bk, "markets": mk})
    return {"home_team": h, "away_team": a, "commence_time": hora_utc, "bookmakers": bks, "liga": "Liga X"}


DATOS = {"eventos": [
    _ev("Flamengo", "Bahia", "2026-11-11T23:30:00Z", [("Pinnacle", [1.45, 4.6, 7.5]), ("Betfair", [1.47, 4.5, 7.0]), ("Unibet", [1.44, 4.4, 7.2])],
        [(1.80, 2.05), (1.83, 2.02), (1.78, 2.05)]),
    _ev("Ya empezó", "Otro", "2026-11-11T13:00:00Z", [("Pinnacle", [1.5, 4, 6]), ("Betfair", [1.5, 4, 6])], [(1.9, 1.9), (1.9, 1.9)]),
]}


def test_convertir_crea_candidatos_verificados_con_hora_bogota():
    cs = OA.convertir(DATOS, ahora=AHORA)
    assert cs and all(c["verificado"] and c["h"] != "Ya empezó" for c in cs)
    f = [c for c in cs if c["mercado"] == "1X2"][0]
    assert f["lado"] == "1" and f["t"] == "18:30" and len(f["casas"]) == 3
    assert any(c["mercado"] == "GOLES" and c["linea"] == 2.5 and c["lado"] == "over" for c in cs)


def test_candidato_api_se_evalua_y_mercado_afilado_no_se_descarta_por_statarea():
    c = [c for c in OA.convertir(DATOS, ahora=AHORA) if c["mercado"] == "1X2"][0]
    c["statarea"] = {"p1": 45, "pX": 30, "p2": 25, "h1": 30, "hX": 40, "h2": 30, "o15": 70, "o25": 50, "o35": 30, "bts": 50, "ots": 50}
    r = A.evaluar(c, exigir_verificado=True)
    assert not r["descartado"] and r["soloMercado"] and r["afilada"]
