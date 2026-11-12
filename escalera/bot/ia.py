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
  registrar_tipster    guarda picks de un tipster (Sharpods…) para evaluarlos y llevarles récord
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
SISTEMA = """Eres el asistente de Telegram de "DCBET" (DC Tecnology). Hablas en español de Colombia, cálido, claro y breve (máximo ~12 líneas), para leer en el celular.

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
Categorías: individuales con valor (sencillas), escalera, combinada, soñadora (= "super", cuota alta y stake mínimo) y progresión.
Mercados: 1X2, DNB (empate no apuesta: si empatan devuelven la plata), doble oportunidad, goles más/menos, ambos marcan, tarjetas y córners. Para tarjetas y córners no hay modelo estadístico: el valor sale solo de comparar casas; dilo.
Cuando pregunten "¿por qué?", usa porQue / enContra del pick (no inventes otras razones).
Cobro anticipado: si te dicen cuánto ofrece BetPlay, usa evaluar_cobro. Gestión de riesgo: respeta dia.riesgo (stop, reducido) y nunca sugieras subir el monto para recuperar pérdidas.
misApuestas = lo que el usuario YA apostó en BetPlay; si una supera 2 unidades, recuérdaselo con tacto.
Numeración: "la 1", "la 3" = sencillas 1 y 3 del día (ids AAAA-MM-DD-1…). Escalera -esc, progresión -prog, combinada -combi, súper -super.

REGISTRO
- Si el usuario dice que hizo / no hizo jugadas, o manda pantallazo de boleto o historial, usa registrar_apuestas.
- Apuesta que no está en el sistema = accion "propia" (ref null).
- Si algo del pantallazo no se lee con seguridad (cuota, valor, equipos), déjalo en null, ponlo en "dudas" y pide un pantallazo más nítido.
- Después de registrar, resume en una línea; el bot muestra el detalle con botones para confirmar.

TIPSTERS (Sharpods u otros canales)
- Si el mensaje viene marcado [REENVIADO DESDE EL CANAL …] o el usuario dice que son picks de un tipster/canal, NO son apuestas del usuario: nunca uses registrar_apuestas con ellos.
- Usa registrar_tipster con cada pick: tipster (nombre del canal), partido "Local vs Visitante", sel, mercado (1X2, DNB, GOLES, BTTS, MARCA, TARJETAS, CORNERS u OTRO), cuota y hora (hora de Colombia). Una combinada va como UN item con tipo "combinada", sus piernas y la cuota total.
- Si un pick coincide con una jugada del plan o un pick del día (mismo partido y selección), pon su id en ref y evalúalo con evaluar_cuota usando la cuota del tipster. Si no coincide, di que el sistema no tiene probabilidad propia para ese pick y que solo queda en seguimiento.
- Responde corto: cuántos picks guardaste y, por cada uno, ✅ con valor / ⚠️ sin valor / ⚪ sin modelo. Recuerda que las combinadas largas tienen muy baja probabilidad.

MONEDA: todo es en pesos colombianos ($3.000 = tres mil pesos), nunca USD ni dólares.

FORMATO: texto plano (prohibido usar ** o #), emojis sobrios (🟢 🟡 ⚪ ✅ ❌ ⚠️ 📈). Sin Markdown, sin asteriscos, sin tablas. Coma decimal ($7.500, 1,45, 72 %)."""

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
    {"name": "registrar_tipster",
     "description": "Guarda picks publicados por un tipster o canal (Sharpods, etc.). NO son apuestas del usuario: quedan en seguimiento para evaluarlos y llevar su récord.",
     "input_schema": {"type": "object", "required": ["items"], "properties": {"items": {"type": "array", "items": {
         "type": "object", "required": ["tipster", "sel"], "properties": {
             "tipster": {"type": "string"}, "partido": {"type": ["string", "null"]},
             "sel": {"type": "string"}, "mercado": {"type": ["string", "null"]},
             "cuota": {"type": ["number", "null"]}, "hora": {"type": ["string", "null"]},
             "tipo": {"type": ["string", "null"], "enum": ["sencilla", "combinada", None]},
             "ref": {"type": ["string", "null"]},
             "piernas": {"type": "array", "items": {"type": "object", "properties": {
                 "partido": {"type": "string"}, "sel": {"type": "string"}, "o": {"type": ["number", "null"]},
                 "hora": {"type": ["string", "null"]}}}},
             "dudas": {"type": ["string", "null"]}}}}}}},
    {"name": "evaluar_cuota",
     "description": "Con la cuota que paga BetPlay para una jugada del plan (ref) o una probabilidad p, devuelve EV, cuota mínima, decisión y monto.",
     "input_schema": {"type": "object", "required": ["cuota"], "properties": {
         "ref": {"type": ["string", "null"]}, "p": {"type": ["number", "null"]}, "cuota": {"type": "number"}}}},
    {"name": "evaluar_cobro",
     "description": "Cuando el usuario dice cuánto le ofrece BetPlay de cobro anticipado (cash out) por una combinada o soñadora abierta: compara con el valor justo y dice COBRAR / PARCIAL / AGUANTAR.",
     "input_schema": {"type": "object", "required": ["oferta"], "properties": {
         "oferta": {"type": "number"}, "ref": {"type": ["string", "null"]}}}},
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
    if nombre == "registrar_tipster":
        return guardar_tipster(args.get("items") or [])
    if nombre == "evaluar_cuota":
        item = next((i for i in dia.get("plan", []) if i["id"] == args.get("ref")), None)
        p = args.get("p") or (item or {}).get("p")
        if not p:
            return {"error": "No encuentro esa jugada; dime cuál es (número o tipo)."}
        acc, monto, ev = STK.decidir_con_cuota_betplay(p, args["cuota"], pol, (item or {}).get("tipo", "sencilla"),
                                                       (item or {}).get("p_push") or 0.0)
        return {"decision": acc, "monto": monto, "ev": round(ev.ev, 4), "cuotaMinima": round(ev.omin, 2),
                "veredicto": ev.texto, "jugada": (item or {}).get("titulo")}
    if nombre == "evaluar_cobro":
        from . import en_vivo
        return {"respuesta": en_vivo.evaluar_cobro(dia, args.get("oferta") or 0, pol.banca, args.get("ref"))}
    if nombre == "simular_riesgo":
        return SIM.largo_plazo(args.get("ev", 0.0), args.get("apuestas_dia", 2), pol.unidad_pct,
                               args.get("cuota_media", 1.6), args.get("dias", 60), caminos=1500)
    return {"error": "herramienta desconocida"}


def guardar_tipster(items: list[dict]) -> dict:
    import datetime as dt
    from zoneinfo import ZoneInfo
    from . import db
    ahora = dt.datetime.now(ZoneInfo(config.TZ))
    limpios = []
    for i, it in enumerate(items):
        if not it.get("sel"):
            continue
        limpios.append({"id": f"T{ahora:%Y%m%d%H%M%S}{i}", "fecha": ahora.date().isoformat(),
                        "recibido": ahora.strftime("%d/%m %H:%M"), "tipster": (it.get("tipster") or "Tipster")[:60],
                        "tipo": it.get("tipo") or ("combinada" if it.get("piernas") else "sencilla"),
                        **{k: it.get(k) for k in ("partido", "sel", "mercado", "cuota", "hora", "ref", "piernas", "dudas")}})
    nuevos = db.tipster_guardar(limpios)
    return {"ok": True, "guardados": len(nuevos), "repetidos": len(limpios) - len(nuevos),
            "nota": "Quedan en seguimiento (no son apuestas del usuario). La mesa los evalúa y liquida."}


def _compacto_dia(dia: dict) -> dict:
    """Resumen corto del día (los planes gratis tienen pocos tokens por minuto)."""
    if not isinstance(dia, dict) or not dia:
        return {}
    _d = lambda x: x if isinstance(x, dict) else {}          # los datos del sitio a veces llegan con otra forma
    _l = lambda x: [i for i in x if isinstance(i, dict)] if isinstance(x, list) else []
    picks = [{**{k: p.get(k) for k in ("id", "h", "a", "lg", "t", "mercado", "sel", "o", "bk", "p", "p_push", "ev",
                                        "omin", "valor", "confianza", "noticias", "alerta", "motivo")},
              "porQue": (_d(p.get("justificacion")).get("aFavor") or [])[:3],
              "enContra": (_d(p.get("justificacion")).get("enContra") or [])[:2]} for p in _l(dia.get("picks"))]
    jug = {}
    for k, j in _d(dia.get("jugadas")).items():
        if not isinstance(j, dict) or not j:
            continue
        if k == "sencillas":
            jug[k] = j.get("ids")
        else:
            jug[k] = {x: j.get(x) for x in ("id", "cuota", "P", "ev", "final", "montos", "reto", "paso",
                                             "saldo", "meta", "Pmeta") if j.get(x) is not None}
            jug[k]["patas"] = [f"{p.get('t')} {p.get('sel')} @{p.get('o')} ({p.get('id')})" for p in _l(j.get("patas"))]
    est = {}
    for k, e in _d(dia.get("estadisticas")).items():
        if isinstance(e, dict) and e.get("n"):
            est[k] = {x: e.get(x) for x in ("n", "aciertos", "esperado", "roi", "beneficio", "pValor",
                                             "brier", "maxDrawdown")}
    return {"fecha": dia.get("fecha"), "veredicto": _d(dia.get("veredicto")).get("texto") or (dia.get("veredicto") if isinstance(dia.get("veredicto"), str) else None),
            "plan": [{k: i.get(k) for k in ("id", "titulo", "tipo", "hora", "accion", "monto", "cuota_ref",
                                             "cuota_min", "p", "p_push", "ev", "razon")} for i in _l(dia.get("plan"))],
            "misApuestas": dia.get("misApuestas"), "porQueJugadas": dia.get("porQue"),
            "escalera": {"config": dia.get("progresionCfg"), "proximo": dia.get("escaleraCrec")},
            "riesgo": dia.get("riesgo"),
            "picks": picks, "jugadas": jug, "bancas": dia.get("bancas"), "politica": dia.get("politica"),
            "tipster": dia.get("tipster"),
            "liquidado": dia.get("liquidado"), "alertas": dia.get("alertas"), "semaforo": dia.get("semaforo"),
            "simulacion": {k: (dia.get("simulacion") or {}).get(k) for k in ("apostado", "esperado", "pGanar")},
            "estadisticas": est}


def _contexto(dia: dict, registro: list, fecha: str, pol: STK.PoliticaStake) -> str:
    reg = [{k: a.get(k) for k in ("fecha", "accion", "ref", "sel", "cuota", "valor", "estado")}
           for a in (registro or [])[-15:] if isinstance(a, dict)]
    try:
        compacto = _compacto_dia(dia)
    except Exception:                                   # un dato raro del día no puede dejar al bot sin IA
        log.exception("No se pudo resumir el día para la IA")
        compacto = {"fecha": dia.get("fecha") if isinstance(dia, dict) else None,
                    "aviso": "El resumen del día no está disponible; responde con el registro y el mensaje."}
    try:
        from . import db
        recibidos = [{k: t.get(k) for k in ("tipster", "partido", "sel", "cuota", "hora", "tipo")}
                     for t in db.tipster((dia or {}).get("fecha"))][-20:]
    except Exception:
        recibidos = []
    return (f"\n\nAHORA (Bogotá): {fecha}\nPOLÍTICA: banca {pol.banca:.0f}, unidad {pol.unidad:.0f}, "
            f"tope diario {pol.tope_diario:.0f}, freno {'sí' if pol.freno else 'no'}"
            f"\n\nDÍA:\n{json.dumps(compacto, ensure_ascii=False, separators=(',', ':'), default=str)[:12000]}"
            f"\n\nREGISTRO DEL USUARIO:\n{json.dumps(reg, ensure_ascii=False, separators=(',', ':'), default=str)}"
            f"\n\nPICKS DE TIPSTER RECIBIDOS HOY:\n{json.dumps(recibidos, ensure_ascii=False, separators=(',', ':'))}")


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
    for intento in range(2):
        try:
            r = requests.post(url, json=cuerpo, headers=cabeceras, timeout=timeout)
        except requests.RequestException as ex:
            raise SinCuota(f"red: {type(ex).__name__}") from ex
        if r.status_code in (500, 502, 503) and intento == 0:
            time.sleep(2)                       # saturación pasajera: un reintento rápido
            continue
        break
    if r.status_code in (401, 403):
        raise SinCuota(f"clave rechazada ({r.status_code}): revisa la clave en Render")
    if r.status_code == 429:
        raise SinCuota("cuota agotada (429)")
    if r.status_code == 503:
        raise SinCuota("modelo saturado (503)")
    if r.status_code >= 400:
        raise SinCuota(f"error {r.status_code}")
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
    preferidos = ["gemini-3-flash-preview", "gemini-flash-latest", "gemini-3.1-flash-lite", "gemini-flash-lite-latest"]
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
    principal = modelo_gemini()
    candidatos = [principal] + [m for m in config.GEMINI_RESPALDOS if m != principal]
    ultimo = None
    for modelo in candidatos:
        try:
            return _gemini_modelo(modelo, list(contenidos), herramientas, sistema, dia, pol, propuestas)
        except SinCuota as ex:                      # 503 saturado / 429 cuota de ese modelo
            log.warning("Gemini %s: %s", modelo, ex)
            ultimo = ex
            propuestas.clear()
    raise ultimo or SinCuota("Gemini sin modelos")


def _gemini_modelo(modelo, contenidos, herramientas, sistema, dia, pol, propuestas):
    url = f"{GEMINI}/models/{modelo}:generateContent"
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
    modelos = [config.GROQ_MODELO_VISION] if imagen else [config.GROQ_MODELO] + config.GROQ_RESPALDOS
    ultimo = None
    for modelo in dict.fromkeys(m for m in modelos if m):
        try:
            return _compatible("https://api.groq.com/openai/v1", config.GROQ_API_KEY, modelo,
                               historial, texto, imagen, sistema, dia, pol, propuestas)
        except SinCuota as ex:
            log.warning("Groq %s: %s", modelo, ex)
            ultimo = ex
            propuestas.clear()
    raise ultimo or SinCuota("Groq sin modelos")


def _openrouter(historial, texto, imagen, sistema, dia, pol, propuestas):
    return _compatible("https://openrouter.ai/api/v1", config.OPENROUTER_API_KEY, config.OPENROUTER_MODELO,
                       historial, texto, imagen, sistema, dia, pol, propuestas,
                       {"HTTP-Referer": config.SITIO, "X-Title": "DCBET"})


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
    try:
        sistema = SISTEMA + _contexto(dia, registro, fecha, pol)
    except Exception:
        log.exception("Falló el contexto de la IA; sigo solo con las instrucciones")
        sistema = SISTEMA + f"\n\nAHORA (Bogotá): {fecha}"
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
    return ("⚠️ La IA está saturada ahora mismo (" + "; ".join(errores)[:200] + ").\n"
            "Mientras tanto puedes usar /hoy, /plan, /escalera, /mis o /cobro 45000, que no dependen de la IA."), []
