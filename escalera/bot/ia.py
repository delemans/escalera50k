"""
IA · conversación 24/7 con balanceo entre proveedores (gratis primero)
=====================================================================
Proveedores (se usa el primero que tenga clave; si falla o se acaba la cuota,
pasa al siguiente). Orden por defecto: IA_ORDEN=gemini,groq,openrouter,anthropic
  gemini      Google AI Studio · plan gratis · lee pantallazos · herramientas
  groq        plan gratis · muy rápido · solo texto (y transcribe voz)
  openrouter  modelos ":free" · solo texto por defecto
  anthropic   Claude · de pago
El modelo recibe el día publicado, tu registro y tus estadísticas, y puede usar:
  registrar_apuestas   propone lo que reportaste (tú confirmas con botón)
  evaluar_cuota        EV, mínima y decisión con una cuota de BetPlay
  simular_riesgo       Monte Carlo de largo plazo con la política de stakes
Las cuentas las hace el código (nucleo/), nunca el modelo de memoria.
"""
from __future__ import annotations

import base64
import json
import logging
import time

import requests

from .. import config
from ..nucleo import simulacion as SIM
from ..nucleo import staking as STK

log = logging.getLogger("ia")
SISTEMA = """Eres el asistente de Telegram de "Escalera 50K" (DC Tecnology). Hablas en español de Colombia, cálido, claro y breve (máximo ~12 líneas), para leer en el celular.

QUÉ HACES
- Explicas el sistema y las jugadas del día, dices QUÉ HACER con cada una según el plan (APOSTAR / VIGILAR / NO), lees pantallazos de BetPlay y registras lo que el usuario apostó.
- El usuario decide y apuesta él mismo. Tú nunca apuestas, nunca prometes resultados y no existen "fijas".
- Todo se basa en probabilidad (p) y valor esperado (EV). Si algo tiene EV negativo, lo dices sin rodeos.
- No inventes cuotas, marcadores, lesiones ni noticias: usa solo los datos de abajo. Si no sabes, dilo.
- No hagas cuentas de memoria: para EV, montos o "¿me sirve esta cuota?" usa evaluar_cuota; para riesgo usa simular_riesgo.
- Si notas señales de juego problemático (perseguir pérdidas, apostar más del tope, angustia), dilo con cariño y sugiere pausar; no sermonees.

EL PLAN (en dia.plan): cada jugada trae accion, monto sugerido, cuota_min y razón.
- APOSTAR: EV ≥ +2 % con la cuota de referencia → apostar el monto SOLO si BetPlay paga ≥ cuota_min.
- VIGILAR: casi justa → solo si BetPlay paga ≥ cuota_min (pide la cuota y usa evaluar_cuota).
- NO: EV negativo o alerta → no apostar; solo se simula.
Numeración: "la 1", "la 3" = sencillas 1 y 3 del día (ids AAAA-MM-DD-1…). Escalera -esc, progresión -prog, combinada -combi, súper -super.

REGISTRO
- Si el usuario dice que hizo / no hizo jugadas, o manda pantallazo de boleto o historial, usa registrar_apuestas.
- Apuesta que no está en el sistema = accion "propia" (ref null).
- Si algo del pantallazo no se lee con seguridad (cuota, valor, equipos), déjalo en null, ponlo en "dudas" y pide un pantallazo más nítido.
- Después de registrar, resume en una línea; el bot muestra el detalle con botones para confirmar.

FORMATO: texto plano, emojis sobrios (🟢 🟡 ⚪ ✅ ❌ ⚠️ 📈). Sin Markdown, sin asteriscos, sin tablas. Coma decimal ($7.500, 1,45, 72 %)."""

HERRAMIENTAS = [
    {"name": "registrar_apuestas",
     "description": "Propone registrar apuestas reportadas (texto, voz o pantallazo). Quedan pendientes hasta que el usuario confirme.",
     "input_schema": {"type": "object", "required": ["items"], "properties": {"items": {"type": "array", "items": {
         "type": "object", "required": ["accion", "tipo"], "properties": {
             "accion": {"type": "string", "enum": ["hice", "no_hice", "propia"]},
             "ref": {"type": ["string", "null"]},
             "tipo": {"type": "string", "enum": ["sencilla", "escalera", "progresion", "combinada", "super"]},
             "partido": {"type": ["string", "null"]}, "sel": {"type": ["string", "null"]},
             "cuota": {"type": ["number", "null"]}, "valor": {"type": ["number", "null"]},
             "estado": {"type": ["string", "null"], "enum": ["abierta", "ganada", "perdida", "nula", None]},
             "piernas": {"type": "array", "items": {"type": "object", "properties": {
                 "partido": {"type": "string"}, "sel": {"type": "string"}, "o": {"type": ["number", "null"]}}}},
             "dudas": {"type": ["string", "null"]}}}}}}},
    {"name": "evaluar_cuota",
     "description": "Con la cuota que paga BetPlay para una jugada del plan (ref) o una probabilidad p, devuelve EV, cuota mínima, decisión y monto.",
     "input_schema": {"type": "object", "required": ["cuota"], "properties": {
         "ref": {"type": ["string", "null"]}, "p": {"type": ["number", "null"]}, "cuota": {"type": "number"}}}},
    {"name": "simular_riesgo",
     "description": "Monte Carlo de largo plazo: probabilidad de caer 30 % / 50 % con la política de stakes.",
     "input_schema": {"type": "object", "properties": {
         "ev": {"type": "number"}, "apuestas_dia": {"type": "integer"}, "cuota_media": {"type": "number"},
         "dias": {"type": "integer"}}}},
]


def ejecutar_herramienta(nombre: str, args: dict, dia: dict, pol: STK.PoliticaStake, propuestas: list):
    if nombre == "registrar_apuestas":
        propuestas.extend(args.get("items", []))
        return {"ok": True, "nota": "Pendiente de confirmación con botón."}
    if nombre == "evaluar_cuota":
        item = next((i for i in dia.get("plan", []) if i["id"] == args.get("ref")), None)
        p = args.get("p") or (item or {}).get("p")
        if not p:
            return {"error": "No encuentro esa jugada; dime cuál es (número o tipo)."}
        acc, monto, ev = STK.decidir_con_cuota_betplay(p, args["cuota"], pol, (item or {}).get("tipo", "sencilla"))
        return {"decision": acc, "monto": monto, "ev": round(ev.ev, 4), "cuotaMinima": round(ev.omin, 2),
                "veredicto": ev.texto, "jugada": (item or {}).get("titulo")}
    if nombre == "simular_riesgo":
        return SIM.largo_plazo(args.get("ev", 0.0), args.get("apuestas_dia", 2), pol.unidad_pct,
                               args.get("cuota_media", 1.6), args.get("dias", 60), caminos=1500)
    return {"error": "herramienta desconocida"}


def _contexto(dia: dict, registro: list, fecha: str, pol: STK.PoliticaStake) -> str:
    limpio = {k: v for k, v in dia.items() if not k.startswith("_") and k not in ("validacion",)}
    return (f"\n\nAHORA (Bogotá): {fecha}\nPOLÍTICA: banca {pol.banca:.0f}, unidad {pol.unidad:.0f}, "
            f"tope diario {pol.tope_diario:.0f}, freno {'sí' if pol.freno else 'no'}"
            f"\n\nDÍA (dia.json):\n{json.dumps(limpio, ensure_ascii=False)[:40000]}"
            f"\n\nREGISTRO DEL USUARIO (7 días):\n{json.dumps(registro, ensure_ascii=False)[:8000]}")


def _media_type(img: bytes) -> str:
    if img[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if img[:4] == b"RIFF" and img[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


class SinCuota(Exception):
    """El proveedor no respondió (cuota, red, error): se prueba el siguiente."""


_ultimo_ok = {"proveedor": None, "cuando": None}
_modelo_gemini = {"id": None}


def proveedores(con_imagen: bool = False) -> list[str]:
    claves = {"gemini": config.GEMINI_API_KEY, "groq": config.GROQ_API_KEY,
              "openrouter": config.OPENROUTER_API_KEY, "anthropic": config.ANTHROPIC_API_KEY}
    vision = {"gemini": True, "anthropic": True, "groq": bool(config.GROQ_MODELO_VISION),
              "openrouter": config.OPENROUTER_VISION}
    orden = [p.strip() for p in config.IA_ORDEN.split(",") if p.strip() in claves]
    return [p for p in orden if claves[p] and (vision[p] or not con_imagen)]


def estado() -> str:
    activos = proveedores()
    if not activos:
        return "Sin IA configurada (pon GEMINI_API_KEY gratis en Render → Environment)."
    txt = "IA disponible: " + " → ".join(activos)
    if _ultimo_ok["proveedor"]:
        txt += f" · última respuesta: {_ultimo_ok['proveedor']} ({_ultimo_ok['cuando']})"
    return txt


# ---------------------------------------------------------------------------
# Esquemas: el de las herramientas se adapta a cada proveedor
# ---------------------------------------------------------------------------
def _esquema_gemini(s):
    """JSON Schema → subconjunto OpenAPI que acepta Gemini (sin listas de tipos ni null)."""
    if isinstance(s, list):
        return [_esquema_gemini(x) for x in s]
    if not isinstance(s, dict):
        return s
    out = {}
    for k, v in s.items():
        if k == "type" and isinstance(v, list):
            tipos = [t for t in v if t != "null"]
            out["type"] = tipos[0] if tipos else "string"
            if "null" in v:
                out["nullable"] = True
        elif k == "enum":
            out["enum"] = [x for x in v if x is not None]
        elif k in ("properties",):
            out[k] = {nombre: _esquema_gemini(sub) for nombre, sub in v.items()}
        elif k in ("items",):
            out[k] = _esquema_gemini(v)
        elif k in ("type", "description", "required", "format"):
            out[k] = v
    return out


def _http(url, cuerpo, cabeceras, timeout=60):
    try:
        r = requests.post(url, json=cuerpo, headers=cabeceras, timeout=timeout)
    except requests.RequestException as ex:
        raise SinCuota(f"red: {type(ex).__name__}") from ex
    if r.status_code in (401, 403):
        raise SinCuota(f"clave rechazada ({r.status_code})")
    if r.status_code == 429:
        raise SinCuota("cuota agotada (429)")
    if r.status_code >= 400:
        raise SinCuota(f"HTTP {r.status_code}: {r.text[:200]}")
    return r.json()


# ---------------------------------------------------------------------------
# Gemini (Google AI Studio)
# ---------------------------------------------------------------------------
GEMINI = "https://generativelanguage.googleapis.com/v1beta"


def modelo_gemini() -> str:
    """Usa GEMINI_MODEL si está; si no, busca el mejor 'flash' disponible para tu clave."""
    if config.GEMINI_MODELO:
        return config.GEMINI_MODELO
    if _modelo_gemini["id"]:
        return _modelo_gemini["id"]
    preferidos = ["gemini-flash-latest", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-lite-latest"]
    try:
        r = requests.get(f"{GEMINI}/models", headers={"x-goog-api-key": config.GEMINI_API_KEY},
                         params={"pageSize": 200}, timeout=20)
        nombres = [m["name"].split("/")[-1] for m in r.json().get("models", [])
                   if "generateContent" in m.get("supportedGenerationMethods", [])]
    except Exception:
        nombres = []
    elegido = next((p for p in preferidos if p in nombres), None) or \
        next((n for n in sorted(nombres, reverse=True) if "flash" in n and "image" not in n
              and "tts" not in n and "live" not in n), None) or "gemini-2.5-flash"
    _modelo_gemini["id"] = elegido
    log.info("Modelo Gemini: %s", elegido)
    return elegido


def _gemini(historial, texto, imagen, sistema, dia, pol, propuestas):
    contenidos = [{"role": "model" if m["role"] == "assistant" else "user",
                   "parts": [{"text": m["content"] if isinstance(m["content"], str) else str(m["content"])}]}
                  for m in historial]
    partes = []
    if imagen:
        partes.append({"inline_data": {"mime_type": _media_type(imagen),
                                       "data": base64.b64encode(imagen).decode()}})
    partes.append({"text": texto or "Te mando un pantallazo de BetPlay."})
    contenidos.append({"role": "user", "parts": partes})
    herramientas = [{"functionDeclarations": [
        {"name": h["name"], "description": h["description"], "parameters": _esquema_gemini(h["input_schema"])}
        for h in HERRAMIENTAS]}]
    url = f"{GEMINI}/models/{modelo_gemini()}:generateContent"
    for _ in range(5):
        d = _http(url, {"systemInstruction": {"parts": [{"text": sistema}]}, "contents": contenidos,
                        "tools": herramientas, "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1500}},
                  {"x-goog-api-key": config.GEMINI_API_KEY})
        cand = (d.get("candidates") or [{}])[0]
        contenido = cand.get("content") or {}
        partes = contenido.get("parts") or []
        llamadas = [p["functionCall"] for p in partes if "functionCall" in p]
        if not llamadas:
            txt = "".join(p.get("text", "") for p in partes if not p.get("thought")).strip()
            if not txt and cand.get("finishReason") not in (None, "STOP"):
                raise SinCuota(f"respuesta vacía ({cand.get('finishReason')})")
            return txt, propuestas
        contenidos.append(contenido)
        contenidos.append({"role": "user", "parts": [
            {"functionResponse": {"name": c["name"], "response": {"resultado":
                ejecutar_herramienta(c["name"], c.get("args") or {}, dia, pol, propuestas)}}}
            for c in llamadas]})
    return "Listo.", propuestas


# ---------------------------------------------------------------------------
# Groq y OpenRouter (API compatible con OpenAI)
# ---------------------------------------------------------------------------
def _compatible(base, clave, modelo, historial, texto, imagen, sistema, dia, pol, propuestas, extra=None):
    mensajes = [{"role": "system", "content": sistema}] + \
        [{"role": m["role"], "content": m["content"] if isinstance(m["content"], str) else str(m["content"])}
         for m in historial]
    if imagen:
        url_img = f"data:{_media_type(imagen)};base64,{base64.b64encode(imagen).decode()}"
        mensajes.append({"role": "user", "content": [
            {"type": "text", "text": texto or "Te mando un pantallazo de BetPlay."},
            {"type": "image_url", "image_url": {"url": url_img}}]})
    else:
        mensajes.append({"role": "user", "content": texto})
    herramientas = [{"type": "function", "function": {"name": h["name"], "description": h["description"],
                                                      "parameters": h["input_schema"]}} for h in HERRAMIENTAS]
    cab = {"Authorization": f"Bearer {clave}", **(extra or {})}
    for _ in range(5):
        d = _http(f"{base}/chat/completions", {"model": modelo, "messages": mensajes, "tools": herramientas,
                                                "temperature": 0.3, "max_tokens": 1500}, cab)
        msg = ((d.get("choices") or [{}])[0]).get("message") or {}
        llamadas = msg.get("tool_calls") or []
        if not llamadas:
            return (msg.get("content") or "").strip(), propuestas
        mensajes.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": llamadas})
        for c in llamadas:
            try:
                args = json.loads(c["function"].get("arguments") or "{}")
            except ValueError:
                args = {}
            res = ejecutar_herramienta(c["function"]["name"], args, dia, pol, propuestas)
            mensajes.append({"role": "tool", "tool_call_id": c["id"], "content": json.dumps(res, ensure_ascii=False)})
    return "Listo.", propuestas


def _groq(historial, texto, imagen, sistema, dia, pol, propuestas):
    modelo = config.GROQ_MODELO_VISION if imagen else config.GROQ_MODELO
    return _compatible("https://api.groq.com/openai/v1", config.GROQ_API_KEY, modelo,
                       historial, texto, imagen, sistema, dia, pol, propuestas)


def _openrouter(historial, texto, imagen, sistema, dia, pol, propuestas):
    return _compatible("https://openrouter.ai/api/v1", config.OPENROUTER_API_KEY, config.OPENROUTER_MODELO,
                       historial, texto, imagen, sistema, dia, pol, propuestas,
                       {"HTTP-Referer": config.SITIO, "X-Title": "Escalera 50K"})


# ---------------------------------------------------------------------------
# Anthropic (Claude, de pago)
# ---------------------------------------------------------------------------
def _anthropic(historial, texto, imagen, sistema, dia, pol, propuestas):
    contenido = []
    if imagen:
        contenido.append({"type": "image", "source": {"type": "base64", "media_type": _media_type(imagen),
                                                      "data": base64.b64encode(imagen).decode()}})
    contenido.append({"type": "text", "text": texto or "Te mando un pantallazo de BetPlay."})
    mensajes = historial + [{"role": "user", "content": contenido}]
    cab = {"x-api-key": config.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01"}
    for _ in range(5):
        d = _http("https://api.anthropic.com/v1/messages",
                  {"model": config.MODELO, "max_tokens": 1200, "system": sistema,
                   "tools": HERRAMIENTAS, "messages": mensajes}, cab)
        bloques = d.get("content") or []
        usos = [b for b in bloques if b.get("type") == "tool_use"]
        if not usos:
            return "".join(b.get("text", "") for b in bloques if b.get("type") == "text").strip(), propuestas
        mensajes.append({"role": "assistant", "content": bloques})
        mensajes.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": u["id"],
             "content": json.dumps(ejecutar_herramienta(u["name"], u.get("input") or {}, dia, pol, propuestas),
                                   ensure_ascii=False)} for u in usos]})
    return "Listo.", propuestas


ADAPTADORES = {"gemini": _gemini, "groq": _groq, "openrouter": _openrouter, "anthropic": _anthropic}


def conversar(historial: list[dict], texto: str, imagen: bytes | None, dia: dict, registro: list,
              fecha: str, pol: STK.PoliticaStake) -> tuple[str, list[dict]]:
    lista = proveedores(con_imagen=bool(imagen))
    if not lista:
        if imagen and proveedores():
            return ("📸 Para leer pantallazos necesito Gemini (gratis): agrega GEMINI_API_KEY en Render. "
                    "Mientras, escríbeme la apuesta: «hice la 2 a 1,45 por 3000»."), []
        return ("⚠️ No hay IA configurada. Crea una clave GRATIS en aistudio.google.com → Get API key "
                "y ponla como GEMINI_API_KEY en Render → Environment. Los botones y comandos sí funcionan."), []
    sistema = SISTEMA + _contexto(dia, registro, fecha, pol)
    errores = []
    for nombre in lista:
        propuestas: list[dict] = []
        try:
            txt, props = ADAPTADORES[nombre](historial, texto, imagen, sistema, dia, pol, propuestas)
            _ultimo_ok.update(proveedor=nombre, cuando=time.strftime("%H:%M"))
            return txt or "Listo.", props
        except SinCuota as ex:
            log.warning("IA %s no disponible: %s", nombre, ex)
            errores.append(f"{nombre}: {ex}")
        except Exception as ex:                     # nunca tumbar el bot por la IA
            log.exception("IA %s falló", nombre)
            errores.append(f"{nombre}: {type(ex).__name__}")
    return ("⚠️ Ninguna IA respondió ahora (" + "; ".join(errores)[:300] + "). "
            "Intenta en un minuto; los botones y comandos siguen funcionando."), []
