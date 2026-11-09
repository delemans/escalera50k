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
    assert "DCBET" in t[0] and "PLAN DEL DÍA" in t[1]
    assert len(t) == 3 + len(dia["plan"])          # resumen, plan, boletos + tarjetas
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
    assert textos(env)[-1].startswith("Este bot es privado.")
    for c in ("/banca", "/stats", "/riesgo", "/metodo", "/plan", "/registro", "/saldo 95.000"):
        app.procesar({"message": {"message_id": 2, "chat": {"id": 111, "type": "private"}, "text": c}})
    assert db.get("saldo") == 95000


def test_alertas_recordatorio_y_pregunta(entorno, monkeypatch):
    env, dia = entorno
    primero = dia["plan"][0]
    h, m = map(int, primero["hora"].split(":"))
    base = dt.datetime.fromisoformat(dia["fecha"]).replace(tzinfo=sync.BOG)
    monkeypatch.setattr(alertas, "ahora", lambda: base.replace(hour=h, minute=m) - dt.timedelta(minutes=28))
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


def test_observador_modo_lectura(entorno):
    env, dia = entorno
    codigo = app.codigo_invitacion()
    app.procesar({"message": {"message_id": 50, "from": {"first_name": "Ana"}, "chat": {"id": 777, "type": "private"},
                              "text": f"/start {codigo}"}})
    assert "777" in app.observadores()
    antes = len(env)
    app.al_usuario("Aviso de prueba")
    destinos = [p.get("chat_id") for m, p in env[antes:] if m == "sendMessage"]
    assert 111 in destinos and "777" in destinos
    app.procesar({"message": {"message_id": 51, "chat": {"id": 777, "type": "private"}, "text": "hice 1"}})
    assert "modo lectura" in textos(env)[-1]
    antes = len(env)
    app.procesar({"message": {"message_id": 60, "chat": {"id": 111, "type": "private"}, "text": "/banca"}})
    metodos = [(m, p.get("chat_id")) for m, p in env[antes:]]
    assert ("forwardMessage", "777") in metodos                    # ve lo que escribe el dueño
    assert ("sendMessage", "777") in metodos                       # y lo que el bot le responde
    app.procesar({"message": {"message_id": 52, "chat": {"id": 888, "type": "private"}, "text": "/start malo"}})
    assert textos(env)[-1].startswith("Este bot es privado.")
    app.procesar({"message": {"message_id": 53, "chat": {"id": 111, "type": "private"}, "text": "/quitar 777"}})
    assert "777" not in app.observadores()


def test_observador_no_se_vuelve_dueno_tras_reinicio(entorno, monkeypatch):
    env, _ = entorno
    db.put("chat", None)
    db.put("observadores", {"777": {"nombre": "Ana"}})
    app.procesar({"message": {"message_id": 70, "chat": {"id": 777, "type": "private"}, "text": "hola"}})
    assert not db.get("chat")                                     # el observador no toma el bot
    assert "modo lectura" in textos(env)[-1]
    app.procesar({"message": {"message_id": 71, "chat": {"id": 888, "type": "private"},
                              "text": "/start " + app.codigo_invitacion()}})
    assert not db.get("chat")                                     # el enlace de lectura tampoco
    monkeypatch.setattr(app.config, "CHAT_ID", "111")
    db.put("chat", 777)
    assert sync.ids()["chat"] == 111                              # CHAT_ID manda sobre lo guardado


def test_espejo_completo_con_observador_fijo(entorno, monkeypatch):
    env, dia = entorno
    db.put("observadores", {})
    monkeypatch.setattr(app.config, "OBSERVADORES", ["555"])
    assert "555" in app.observadores()
    antes = len(env)
    app.al_usuario("Plan de hoy")
    tg.editar(111, 5, "Confirmado")
    cb = {"id": "c", "from": {"id": 111}, "data": "no:x",
          "message": {"chat": {"id": 111}, "message_id": 5, "text": "x",
                      "reply_markup": {"inline_keyboard": [[{"text": "❌ No la hice", "callback_data": "no:x"}]]}}}
    app.procesar({"callback_query": cb})
    a555 = [p.get("text", "") for m, p in env[antes:] if m == "sendMessage" and str(p.get("chat_id")) == "555"]
    assert any("Plan de hoy" in t for t in a555)
    assert any("✏️ Confirmado" in t for t in a555)
    assert any("No la hice" in t for t in a555)
    app.procesar({"message": {"message_id": 80, "chat": {"id": 555, "type": "private"}, "text": "hice 1"}})
    assert "modo lectura" in textos(env)[-1]


def test_tipster_reenvio_guarda_y_muestra(entorno, monkeypatch):
    from escalera.bot import ia
    env, dia = entorno
    vistos = {}

    def falso_ia(hist, texto, imagen, dia_, reg, fecha, pol):
        vistos["texto"] = texto
        r = ia.ejecutar_herramienta("registrar_tipster", {"items": [
            {"tipster": "SHARPODS DEPORTIVAS", "partido": "Fenerbahçe vs Liverpool", "sel": "Gana Liverpool",
             "mercado": "1X2", "cuota": 1.44, "hora": "12:45"},
            {"tipster": "SHARPODS DEPORTIVAS", "sel": "La del medio", "tipo": "combinada", "cuota": 5.28,
             "piernas": [{"partido": "Viking vs Sabah", "sel": "Gana Viking", "o": 1.41}]}]}, dia_, pol, [])
        return f"Guardé {r['guardados']}", []

    monkeypatch.setattr(ia, "conversar", falso_ia)
    msg = {"message_id": 50, "chat": {"id": 111, "type": "private"}, "text": "/hoy picks",
           "forward_origin": {"type": "channel", "chat": {"id": -1001, "type": "channel", "title": "SHARPODS DEPORTIVAS"}}}
    app.procesar({"message": msg})
    assert "REENVIADO DESDE EL CANAL «SHARPODS DEPORTIVAS»" in vistos["texto"]   # no se toma como comando
    assert not app._pendientes or all(p.get("accion") != "propia" for v in app._pendientes.values() for p in v)
    hoy = db.tipster(sync.hoy())
    assert len(hoy) == 2 and hoy[1]["tipo"] == "combinada"
    app.procesar({"message": {**msg, "message_id": 51}})                         # repetido: no duplica
    assert len(db.tipster(sync.hoy())) == 2
    app.procesar({"message": {"message_id": 52, "chat": {"id": 111, "type": "private"}, "text": "/tipster"}})
    t = textos(env)[-1]
    assert "TIPSTER" in t and "Gana Liverpool" in t and "1,44" in t
    import re
    for tag in ("b", "i"):
        assert len(re.findall(f"<{tag}>", t)) == len(re.findall(f"</{tag}>", t))


def test_tipster_evaluado_por_la_mesa(entorno):
    _, dia = entorno
    dia = {**dia, "tipster": {"fuente": "Sharpods", "record": {"n": 4, "aciertos": 3, "roi": 0.12},
                              "picks": [{"partido": "A vs B", "sel": "Gana A", "cuota": 1.44, "omin": 1.58,
                                         "veredicto": "sin_valor", "nota": "Bajo la mínima"}]}}
    t = M.tipster(dia, [])
    assert "⚠️" in t and "mín. 1,58" in t and "3/4" in t
    assert M.tipster({**dia, "tipster": None}, []) is None


def test_aviso_sin_dia_no_se_repite(monkeypatch):
    import datetime as dt
    from escalera.bot import alertas as AL
    monkeypatch.setattr(AL, "ahora", lambda: dt.datetime(2026, 11, 9, 8, 30))
    viejo = {"fecha": "2026-11-08"}
    claves = [c for c, _, _ in AL.pendientes(viejo)]
    assert "sin-dia-2026-11-09" in claves
    AL.marcar("sin-dia-2026-11-09")
    monkeypatch.setattr(db, "aviso_enviado", lambda c: False)        # aunque la base "olvide"
    assert "sin-dia-2026-11-09" not in [c for c, _, _ in AL.pendientes(viejo)]
    monkeypatch.setattr(AL, "ahora", lambda: dt.datetime(2026, 11, 10, 13, 0))
    assert not any(c.startswith("sin-dia") for c, _, _ in AL.pendientes(viejo))   # fuera de 8–10 a. m. no sale
