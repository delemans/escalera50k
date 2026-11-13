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


# ---------------------------------------------------------------------------
# Más ligas sin gastar más créditos
# ---------------------------------------------------------------------------
def _api_falsa(monkeypatch, ligas, creditos=100):
    """ligas = {clave: partidos}. Devuelve la lista de llamadas a /odds y descuenta créditos."""
    estado = {"restante": creditos, "odds": []}

    def get(url, timeout=30):
        if "/events?" in url:
            k = url.split("/sports/")[1].split("/")[0]
            return [{"id": i} for i in range(ligas[k])], None
        if "/odds?" in url:
            k = url.split("/sports/")[1].split("/")[0]
            costo = OA.costo_por_liga(*[__import__("urllib.parse").parse.parse_qs(url.split("?")[1])[x][0] for x in ("markets", "regions")])
            estado["restante"] -= costo
            estado["odds"].append(k)
            return [{"home_team": "A", "away_team": "B"}], str(estado["restante"])
        return [{"key": k, "active": True, "title": k.upper()} for k in ligas] + \
               [{"key": "soccer_copa_ganador", "active": True, "has_outrights": True}, {"key": "basketball_nba", "active": True}], None

    monkeypatch.setattr(OA, "_get", get)
    return estado


def test_costo_por_liga():
    assert OA.costo_por_liga("h2h,totals", "eu") == 2 and OA.costo_por_liga("h2h", "eu") == 1
    assert OA.costo_por_liga("h2h,totals", "eu,uk") == 4


def test_solo_h2h_trae_el_doble_de_ligas_con_los_mismos_creditos(monkeypatch):
    ligas = {f"soccer_l{i}": 10 - i for i in range(8)}
    d0, d1 = AHORA, AHORA + dt.timedelta(hours=20)
    _api_falsa(monkeypatch, ligas)
    con_goles = OA.descargar("k", d0, d1, max_ligas=4, mercados="h2h,totals")
    _api_falsa(monkeypatch, ligas)
    solo_1x2 = OA.descargar("k", d0, d1, max_ligas=8, mercados="h2h")
    assert con_goles["creditos"] == solo_1x2["creditos"] == 8
    assert len(con_goles["ligas"]) == 4 and len(solo_1x2["ligas"]) == 8
    assert len(con_goles["omitidas"]) == 4 and solo_1x2["omitidas"] == []


def test_prioridad_exclusion_y_reserva(monkeypatch):
    ligas = {"soccer_grande": 9, "soccer_media": 5, "soccer_chica": 1, "soccer_fuera": 8}
    d0, d1 = AHORA, AHORA + dt.timedelta(hours=20)
    est = _api_falsa(monkeypatch, ligas)
    OA.descargar("k", d0, d1, max_ligas=2, primero=["soccer_chica"], excluir=["soccer_fuera"])
    assert est["odds"] == ["soccer_chica", "soccer_grande"]          # la pedida va primero; la excluida nunca
    est = _api_falsa(monkeypatch, ligas, creditos=25)
    r = OA.descargar("k", d0, d1, max_ligas=4, reserva=20)
    assert r["creditos"] == 4 and int(r["restante"]) >= 20           # se detiene antes de bajar de la reserva


def test_sin_cuotas_de_goles_igual_arma_el_1x2():
    ev = _ev("Flamengo", "Bahia", "2026-11-11T23:30:00Z", [("Pinnacle", [1.45, 4.6, 7.5]), ("Betfair", [1.47, 4.5, 7.0])], [(1.8, 2.0), (1.8, 2.0)])
    for b in ev["bookmakers"]:
        b["markets"] = [m for m in b["markets"] if m["key"] == "h2h"]
    cs = OA.convertir({"eventos": [ev]}, ahora=AHORA)
    assert [c["mercado"] for c in cs] == ["1X2"]
