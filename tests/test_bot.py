import datetime as dt
import json
from pathlib import Path

import pytest

from escalera import analisis as A
from escalera.bot import alertas, app, db, mensajes as M, sync, telegram as tg

RAIZ = Path(__file__).resolve().parent.parent


@pytest.fixture()
def entorno(monkeypatch):
    enviados = []

    def falso(metodo, timeout=35, files=None, reintentos=3, **p):
        enviados.append((metodo, p))
        if metodo in ("sendMessage", "sendDocument"):
            return {"message_id": len(enviados), "chat": {"id": 111}}
        return True

    monkeypatch.setattr(tg, "llamar", falso)
    monkeypatch.setattr(tg, "_ritmo", lambda: None)
    entrada = json.loads((RAIZ / "ejemplos/entrada_ejemplo.json").read_text())
    entrada["statarea_csv"] = (RAIZ / "ejemplos/statarea_ejemplo.csv").read_text()
    # BetPlay "paga más" en Bayern para que haya una APOSTAR en el ejemplo
    entrada["candidatos"][0]["casas"].append({"bk": "Mejor", "o": [1.40, 6.0, 9.0]})
    dia = A.construir_dia(entrada)["dia"]
    sync.guardar_dia(dia)
    db.put("chat", 111)
    db.put("canal", -100)
    return enviados, dia


def textos(env):
    return [p.get("text", "") for m, p in env if m == "sendMessage"]


def test_dia_completo_y_tarjetas(entorno):
    env, dia = entorno
    app.enviar_dia(dia)
    t = textos(env)
    assert "ESCALERA 50K" in t[0] and "PLAN DEL DÍA" in t[1]
    assert len(t) == 2 + len(dia["plan"])
    assert any("APOSTAR" in x for x in t)
    for x in t:
        assert len(x) < 4000


def test_flujo_botones(entorno):
    env, dia = entorno
    ref = dia["plan"][0]["id"]
    cb = {"id": "c", "from": {"id": 111}, "message": {"chat": {"id": 111}, "message_id": 5, "text": "x"}}
    app.procesar({"callback_query": {**cb, "data": f"si:{ref}"}})
    assert db.get("espera")["ref"] == ref
    app.procesar({"message": {"message_id": 9, "chat": {"id": 111, "type": "private"}, "text": "1,42 3000"}})
    assert db.get("espera") is None
    assert db.confirmacion(sync.hoy(), ref)["estado"] == "si"
    r = db.registro(sync.hoy())[-1]
    assert r["cuota"] == 1.42 and r["valor"] == 3000
    app.procesar({"callback_query": {**cb, "data": f"cuota:{ref}"}})
    app.procesar({"message": {"message_id": 10, "chat": {"id": 111, "type": "private"}, "text": "1,25"}})
    assert "NO APUESTES" in textos(env)[-1]


def test_atajo_y_confirmar(entorno):
    env, dia = entorno
    app.procesar({"message": {"message_id": 11, "chat": {"id": 111, "type": "private"}, "text": "hice 1 y 2"}})
    assert "Esto entendí" in textos(env)[-1]
    clave = list(app._pendientes)[-1]
    app.procesar({"callback_query": {"id": "c", "from": {"id": 111}, "data": f"ok:{clave}",
                                     "message": {"chat": {"id": 111}, "message_id": 12, "text": "Esto entendí"}}})
    assert len([a for a in db.registro(sync.hoy()) if a.get("fuente") == "texto"]) >= 2
    assert any(m == "sendDocument" for m, _ in env)            # registro publicado al canal


def test_privado_y_comandos(entorno):
    env, dia = entorno
    app.procesar({"message": {"message_id": 1, "chat": {"id": 999, "type": "private"}, "text": "hola"}})
    assert textos(env)[-1] == "Este bot es privado."
    for c in ("/banca", "/stats", "/riesgo", "/metodo", "/plan", "/registro", "/saldo 95.000"):
        app.procesar({"message": {"message_id": 2, "chat": {"id": 111, "type": "private"}, "text": c}})
    assert db.get("saldo") == 95000


def test_alertas_recordatorio_y_pregunta(entorno, monkeypatch):
    env, dia = entorno
    primero = dia["plan"][0]
    h, m = map(int, primero["hora"].split(":"))
    base = dt.datetime.fromisoformat(dia["fecha"]).replace(tzinfo=sync.BOG)
    monkeypatch.setattr(alertas, "ahora", lambda: base.replace(hour=h, minute=m) - dt.timedelta(minutes=58))
    claves = [c for c, _, _ in alertas.pendientes(dia)]
    assert any(c.startswith("rec-") for c in claves)
    monkeypatch.setattr(alertas, "ahora", lambda: base.replace(hour=h, minute=m) + dt.timedelta(minutes=6))
    db.set_confirmacion(dia["fecha"], primero["id"], estado="pendiente")
    claves = [c for c, _, _ in alertas.pendientes(dia)]
    assert any(c.startswith("preg-") for c in claves)


def test_mensajes_html_balanceado(entorno):
    _, dia = entorno
    import re
    for txt in [M.resumen(dia), M.plan(dia), M.metodo(), M.ayuda()] + [M.tarjeta(dia, i) for i in dia["plan"]]:
        for tag in ("b", "i", "code"):
            assert len(re.findall(f"<{tag}>", txt)) == len(re.findall(f"</{tag}>", txt))


def test_herramientas_ia(entorno):
    from escalera.bot import ia
    _, dia = entorno
    pol = alertas.politica(dia)
    ref = dia["plan"][0]["id"]
    r = ia.ejecutar_herramienta("evaluar_cuota", {"ref": ref, "cuota": 1.60}, dia, pol, [])
    assert r["decision"] in ("APOSTAR", "NO") and "ev" in r
    props = []
    ia.ejecutar_herramienta("registrar_apuestas", {"items": [{"accion": "propia", "tipo": "sencilla"}]}, dia, pol, props)
    assert props and props[0]["accion"] == "propia"
    r = ia.ejecutar_herramienta("simular_riesgo", {"ev": 0.02}, dia, pol, [])
    assert 0 <= r["pCaida30"] <= 1
