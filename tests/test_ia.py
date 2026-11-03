import json

from escalera import config
from escalera.bot import alertas, ia, sync
from escalera import analisis as A
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


class Resp:
    def __init__(self, codigo, datos):
        self.status_code, self._d, self.text = codigo, datos, json.dumps(datos)

    def json(self):
        return self._d


def _dia():
    e = json.loads((RAIZ / "ejemplos/entrada_ejemplo.json").read_text())
    e["statarea_csv"] = (RAIZ / "ejemplos/statarea_ejemplo.csv").read_text()
    return A.construir_dia(e)["dia"]


def _sin_listas_de_tipos(s):
    if isinstance(s, dict):
        assert not isinstance(s.get("type"), list)
        assert None not in (s.get("enum") or [])
        return all(_sin_listas_de_tipos(v) for v in s.values())
    if isinstance(s, list):
        return all(_sin_listas_de_tipos(v) for v in s)
    return True


def test_esquema_gemini_valido():
    for h in ia.HERRAMIENTAS:
        assert _sin_listas_de_tipos(ia._esquema_gemini(h["input_schema"]))


def test_gemini_con_herramienta(monkeypatch):
    dia = _dia()
    ref = dia["plan"][0]["id"]
    respuestas = [
        Resp(200, {"candidates": [{"content": {"role": "model", "parts": [
            {"functionCall": {"name": "evaluar_cuota", "args": {"ref": ref, "cuota": 1.6}}}]}}]}),
        Resp(200, {"candidates": [{"content": {"role": "model", "parts": [{"text": "🟢 Con 1,60 sí."}]},
                                   "finishReason": "STOP"}]}),
    ]
    enviados = []
    monkeypatch.setattr(ia.requests, "post", lambda url, json=None, headers=None, timeout=0:
                        (enviados.append(json), respuestas.pop(0))[1])
    monkeypatch.setattr(config, "GEMINI_API_KEY", "x")
    monkeypatch.setattr(config, "GEMINI_MODELO", "gemini-test")
    monkeypatch.setattr(config, "IA_ORDEN", "gemini")
    txt, props = ia.conversar([], "¿me sirve a 1,60?", None, dia, [], "hoy", alertas.politica(dia))
    assert txt == "🟢 Con 1,60 sí." and props == []
    assert "functionResponse" in enviados[1]["contents"][-1]["parts"][0]


def test_balanceo_si_gemini_sin_cuota(monkeypatch):
    dia = _dia()

    def post(url, json=None, headers=None, timeout=0):
        if "googleapis" in url:
            return Resp(429, {"error": "quota"})
        return Resp(200, {"choices": [{"message": {"content": "Respuesta de Groq"}}]})

    monkeypatch.setattr(ia.requests, "post", post)
    monkeypatch.setattr(config, "GEMINI_API_KEY", "x")
    monkeypatch.setattr(config, "GEMINI_MODELO", "gemini-test")
    monkeypatch.setattr(config, "GROQ_API_KEY", "y")
    monkeypatch.setattr(config, "IA_ORDEN", "gemini,groq")
    txt, _ = ia.conversar([], "hola", None, dia, [], "hoy", alertas.politica(dia))
    assert txt == "Respuesta de Groq" and ia._ultimo_ok["proveedor"] == "groq"


def test_sin_claves(monkeypatch):
    for k in ("GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.setattr(config, k, "")
    txt, _ = ia.conversar([], "hola", None, {}, [], "hoy", alertas.politica({}))
    assert "GEMINI_API_KEY" in txt
    assert sync  # módulo importable
