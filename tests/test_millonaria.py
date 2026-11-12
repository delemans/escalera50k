from escalera.nucleo import millonaria as MI


def test_plan_por_hitos_hasta_la_meta():
    pl = MI.plan(36100, saldo_serie=6100, cuota=1.5, p=0.65)
    assert pl["tramos"][-1]["hasta"] == 3_000_000
    assert pl["pMeta"] < 0.01 and 0 < pl["tramos"][0]["pTramo"] <= 1
    assert all(t["pAcumulada"] <= t["pTramo"] + 1e-4 for t in pl["tramos"])
    assert pl["tramos"][0]["aseguras"] > 0 and pl["tramos"][-1]["aseguras"] == 0
    assert MI.peldanos_para(6100, 3_000_000, 1.5) == 16
