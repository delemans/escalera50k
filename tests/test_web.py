import base64
import json
import urllib.error
import urllib.request

from escalera import config
from escalera.bot import db, sync, telegram as tg, web


def _get(url, headers=None, data=None):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def test_servidor_web(monkeypatch):
    monkeypatch.setattr(config, "PANEL_CLAVE", "secreta")
    srv = web.arrancar(0)
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    assert _get(base + "/salud")[0] == 200
    assert _get(base + "/")[0] == 401
    ok = base64.b64encode(b"admin:secreta").decode()
    assert _get(base + "/", {"Authorization": "Basic " + ok})[0] == 200
    malo = base64.b64encode(b"admin:otra").decode()
    assert _get(base + "/", {"Authorization": "Basic " + malo})[0] == 401
    cuerpo = json.dumps({"update_id": 1}).encode()
    assert _get(base + "/telegram/x", {"X-Telegram-Bot-Api-Secret-Token": "x"}, cuerpo)[0] == 403
    assert _get(base + f"/telegram/{web.secreto()}", {"X-Telegram-Bot-Api-Secret-Token": web.secreto()}, cuerpo)[0] == 200
    assert web.cola.get(timeout=2)["update_id"] == 1
    srv.shutdown()


def test_restaurar_desde_telegram(monkeypatch):
    reg = {"saldoReportado": 98000, "apuestas": [{"tgId": "tg-r1", "fecha": sync.hoy(), "accion": "hice",
                                                 "ref": "x-1", "valor": 2000, "cuota": 1.5}],
           "estado": {"fecha": sync.hoy(), "confirmaciones": {"x-1": "si"}, "avisos": ["rec-a"], "silencioOff": True}}
    monkeypatch.setattr(tg, "leer_json_fijado", lambda chat: (reg, 77) if chat == -500 else (None, None))
    monkeypatch.setattr(db, "vacia", lambda: True)
    monkeypatch.setattr(sync, "ids", lambda: {"chat": 111, "canal": -500})
    assert sync.restaurar()
    assert db.get("saldo") == 98000 and db.get("registro_mid") == 77
    assert db.confirmacion(sync.hoy(), "x-1")["estado"] == "si"
    assert db.aviso_enviado("rec-a") and db.apostado(sync.hoy()) >= 2000


def test_enlace_app_firmado(monkeypatch):
    from escalera.bot import panel
    t = panel.token_app(111)
    assert panel.token_valido(t) and not panel.token_valido(t[:-2] + "xx") and not panel.token_valido(None)
    srv = web.arrancar(0)
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    assert _get(base + f"/app?t={t}")[0] == 200
    assert _get(base + "/app?t=malo")[0] == 403
    srv.shutdown()


def test_fase2_criterios():
    from escalera.bot import canal
    c = canal.criterios({"estadisticas": {"sistema": {"n": 40, "icRoi90": [-0.1, 0.2], "pValor": 0.4}}}, "2026-11-03")
    assert not c["listo"] and len(c["checks"]) == 4
    assert "Aún no" in canal.mensaje_fase2({}, "2026-11-03")


def test_escaneo_pedido_y_atendido(monkeypatch):
    from escalera.bot import app
    db.put("escaneo", None)
    txt = app.pedir_escaneo()
    assert "Escaneo pedido" in txt or "mañana" in txt
    assert db.get("escaneo")["pedido"] and db.get("escaneo")["atendido"] is None
    assert "Ya hay" in app.pedir_escaneo()                       # no duplica
    assert len(app.firma_escaneo()) == 16
