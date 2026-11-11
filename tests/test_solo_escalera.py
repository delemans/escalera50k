from escalera.nucleo import jugadas as J


def _c(i, t, o, p=0.65):
    return {"h": f"L{i}", "a": f"V{i}", "lg": f"Liga{i}", "t": t, "o": o, "p": p, "ev": p * o - 1,
            "mercado": "1X2", "lado": "1", "sel": f"Gana L{i}", "valor": True}


def test_rango_cuota_y_solo_escalera():
    r = J.reglas_desde_config({"escaleraCfg": {"cuota": [1.40, 1.60], "soloEscalera": True, "stake": 5000}})
    assert r.escalera_cuota == (1.40, 1.60) and r.escalera_cuota_respaldo == (1.40, 1.60)
    cands = [_c(1, "09:00", 1.45), _c(2, "11:00", 1.30, 0.8), _c(3, "13:00", 1.55), _c(4, "15:00", 1.90),
             _c(5, "17:00", 1.50), _c(6, "19:00", 1.42), _c(7, "21:00", 1.58)]
    jug, _ = J.armar(cands, "2026-11-10", {"activo": True, "saldo": 9000, "meta": 50000, "reto": 1, "paso": 1, "base": 9000}, r)
    esc = jug["escalera"]
    assert esc and esc["stake"] == 5000
    assert all(1.40 <= p["o"] <= 1.60 for p in esc["patas"])
    assert jug["combinada"] is None and jug["super"] is None
    pr = jug["progresion"]                      # serie activa: sale el siguiente escalón, en el mismo rango
    assert pr and 1.40 <= pr["patas"][0]["o"] <= 1.60 and pr["stake"] == 9000
    assert jug["sencillas"]["ids"] == []


def test_sin_config_igual_que_antes():
    r = J.reglas_desde_config({})
    assert r.escalera_cuota == (1.15, 1.75) and not r.solo_escalera


def test_dnb_cuenta_empate_como_seguro_en_escalera():
    r = J.reglas_desde_config({"escaleraCfg": {"cuota": [1.40, 1.60], "soloEscalera": True}})
    dnb = {**_c(1, "09:00", 1.45, p=0.50), "p_push": 0.28, "mercado": "DNB"}
    gana = _c(2, "09:00", 1.50, p=0.62)
    jug, _ = J.armar([dnb, gana], "2026-11-10", {}, r)
    assert jug["escalera"]["patas"][0]["mercado"] == "DNB"      # 78 % de no perder > 62 %
    assert jug["escalera"]["conSeguro"] == 1


def test_sonadora_piernas_130_140_con_comodin():
    r = J.reglas_desde_config({"escaleraCfg": {"soloEscalera": True, "sonadora": {
        "pierna": [1.30, 1.40], "piernas": [3, 5], "total": [2.0, 8.0], "seguro": True, "pMin": 0.65}}})
    cands = [_c(i, f"{10 + i}:00", 1.30 + 0.02 * i, p=0.74) for i in range(5)] + [_c(9, "20:00", 1.60, 0.9)]
    jug, _ = J.armar(cands, "2026-11-10", {}, r)
    s = jug["super"]
    assert s and all(1.30 <= p["o"] <= 1.40 for p in s["patas"])
    assert s["Pcomodin"] >= s["Pnoperder"]


def test_reserva_hasta_20_planes_balanceados():
    r = J.reglas_desde_config({"escaleraCfg": {"cuota": [1.30, 1.60], "soloEscalera": True}})
    cands = [_c(i, f"{8 + i}:00", 1.32 + 0.02 * i, p=0.72) for i in range(12)]
    jug, _ = J.armar(cands, "2026-11-10", {}, r)
    res = jug["reserva"]
    assert 0 < len(res) <= 20
    uso = {}
    for pl in res:
        for p in pl["patas"]:
            uso[p["partido"]] = uso.get(p["partido"], 0) + 1
    assert max(uso.values()) <= 4
    assert [pl["n"] for pl in res] == list(range(1, len(res) + 1))
