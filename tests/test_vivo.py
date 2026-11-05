import datetime as dt
import json
from pathlib import Path

from escalera.bot import db, en_vivo as V, sync
from escalera.nucleo import cashout as CO
from escalera.nucleo import riesgo as R

FIX = json.loads((Path(__file__).parent / "espn_galatasaray_stuttgart.json").read_text())


def test_resumen_real_espn():
    r = V.leer_resumen(FIX)
    assert r["local"] == "Galatasaray" and r["gl"] >= 2
    assert r["tarjetas"] >= 8 and any(x["tipo"] == "tarjeta" for x in r["eventos"])
    est, txt = V.estado_pierna({"mercado": "TARJETAS", "lado": "over", "linea": 4.5}, r["gl"], r["gv"],
                               r["tarjetas"], r["corners"], False)
    assert est == "ganada" and "ya ganada" in txt


def test_estado_piernas():
    assert V.estado_pierna({"mercado": "TARJETAS", "lado": "under", "linea": 5.5}, 0, 1, 2, 0, False)[1] == "van 2, aguanta 3 más"
    assert V.estado_pierna({"mercado": "TARJETAS", "lado": "under", "linea": 5.5}, 0, 1, 6, 0, False)[0] == "perdida"
    assert V.estado_pierna({"mercado": "DNB", "lado": "2"}, 1, 1, 0, 0, True)[0] == "nula"
    assert V.estado_pierna({"mercado": "GOLES", "lado": "over", "linea": 2.5}, 1, 0, 0, 0, False)[1] == "van 1, faltan 2"
    assert V.parecido("Manchester United", "Manchester United") == 1 and V.parecido("Sporting CP", "Sporting Lisbon") >= 0.5


def test_ciclo_en_vivo(monkeypatch):
    hoy = sync.hoy()
    dia = {"fecha": hoy, "misApuestas": [{"id": "x2", "resultado": "pendiente", "partido": "Galatasaray vs VfB Stuttgart",
                                          "seleccion": "Más de 4,5 tarjetas", "mercado": "TARJETAS", "lado": "over",
                                          "linea": 4.5, "hora": sync.ahora().strftime("%H:%M"), "stakeReal": 1000,
                                          "cuotaReal": 2.0}]}
    db.put("vivo", {})
    r = V.leer_resumen(FIX)
    r["eventos"] = r["eventos"][:-1]
    estado = {"r": r}
    monkeypatch.setattr(V, "buscar_evento", lambda *a, **k: ("uefa.champions", "1"))
    monkeypatch.setattr(V, "resumen_evento", lambda *a: estado["r"])
    m1 = V.revisar(dia, 100000)
    assert m1 and "EN VIVO" in m1[0] and "ya ganada" in m1[0]
    estado["r"] = V.leer_resumen(FIX)                       # llega un evento nuevo
    m2 = V.revisar(dia, 100000)
    assert any("🟨" in m or "⚽" in m for m in m2)


def test_cobro_anticipado():
    justo = CO.valor_justo(1000, 120, [0.7, 0.6])
    assert round(justo) == 50400
    assert CO.decidir(49000, justo, 100000, 1000)[0] == "COBRAR"
    assert CO.decidir(32000, justo, 100000, 1000)[0] == "COBRAR · ASEGURA"
    assert CO.decidir(10000, justo, 100000, 1000)[0] == "AGUANTAR"


def test_riesgo_stop_y_escalera():
    hoy = "2026-11-05"
    filas = [{"real": True, "resultado": "perdido", "fecha": hoy, "stakeReal": 3000, "cuotaReal": 1.5, "tipo": "sencilla"},
             {"real": True, "resultado": "perdido", "fecha": hoy, "stakeReal": 3000, "cuotaReal": 1.5, "tipo": "sencilla"}]
    r = R.evaluar(filas, 100000, hoy)
    assert r["estado"] == "stop" and r["factor"] == 0
    ec = R.escalera_crecimiento({"saldo": 13860, "base": 9000, "paso": 2})
    assert ec["stake"] == 13860 and ec["asegurado"] == 0            # todo lo ganado al siguiente peldaño
    ec = R.escalera_crecimiento({"saldo": 13860, "base": 9000, "paso": 2}, modo="seguro")
    assert ec["stake"] == 4860 and ec["asegurado"] == 9000
    t = R.plan_peldanos({"saldo": 13860, "base": 9000, "paso": 2, "meta": 50000}, 1.36)
    assert t[0]["estado"] == "ganado" and t[1]["apuesta"] == 13860 and t[1]["cobro"] == round(13860 * 1.36)
    assert t[2]["apuesta"] == t[1]["cobro"]
    assert dt  # importado


def test_bot_liquida_pendiente_de_ayer(monkeypatch):
    from escalera.bot import db
    db.put("liquidados_bot", {})
    r = V.leer_resumen(FIX)
    monkeypatch.setattr(V, "buscar_evento", lambda *a, **k: ("uefa.champions", "1"))
    monkeypatch.setattr(V, "resumen_evento", lambda *a: {**r, "terminado": True})
    dia = {"fecha": sync.hoy(), "misApuestas": [
        {"id": "x2", "fecha": "2026-11-03", "hora": "12:45", "resultado": "pendiente", "partido": "Galatasaray vs VfB Stuttgart",
         "seleccion": "Más de 4,5 tarjetas", "mercado": "TARJETAS", "lado": "over", "linea": 4.5,
         "stakeReal": 1000, "cuotaReal": 2.0},
        {"id": "x3", "fecha": "2026-11-03", "hora": "15:00", "resultado": "pendiente", "partido": "Galatasaray vs VfB Stuttgart",
         "seleccion": "Stuttgart (empate no apuesta)", "mercado": "DNB", "lado": "2", "stakeReal": 1000, "cuotaReal": 2.14}]}
    msgs, cambio = V.liquidar_pendientes(dia)
    assert cambio and len(msgs) == 2
    a, b = dia["misApuestas"]
    assert a["resultado"] == "ganado" and a["netoReal"] == 1000
    assert b["resultado"] == "perdido" and b["netoReal"] == -1000      # ganó el local
    assert "LIQUIDADA" in msgs[0]
    assert V.liquidar_pendientes(dia) == ([], False)                    # no repite
