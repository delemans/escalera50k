"""
IA · conversación 24/7 con Claude (texto, pantallazos y voz transcrita)
======================================================================
Claude recibe el día publicado, tu registro y tus estadísticas, y puede usar:
  registrar_apuestas   propone lo que reportaste (tú confirmas con botón)
  evaluar_cuota        EV, mínima y decisión con una cuota de BetPlay
  simular_riesgo       Monte Carlo de largo plazo con la política de stakes
Las cuentas las hace el código (nucleo/), nunca el modelo de memoria.
"""
from __future__ import annotations

import base64
import json
import logging

from .. import config
from ..nucleo import simulacion as SIM
from ..nucleo import staking as STK

log = logging.getLogger("ia")
_cliente = None


def cliente():
    global _cliente
    if _cliente is None and config.ANTHROPIC_API_KEY:
        import anthropic
        _cliente = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, max_retries=3, timeout=60)
    return _cliente


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


def conversar(historial: list[dict], texto: str, imagen: bytes | None, dia: dict, registro: list,
              fecha: str, pol: STK.PoliticaStake) -> tuple[str, list[dict]]:
    c = cliente()
    if not c:
        return ("⚠️ Falta ANTHROPIC_API_KEY: sin ella no puedo conversar ni leer pantallazos. "
                "Los botones y comandos sí funcionan."), []
    contenido = []
    if imagen:
        contenido.append({"type": "image", "source": {"type": "base64", "media_type": _media_type(imagen),
                                                      "data": base64.b64encode(imagen).decode()}})
    contenido.append({"type": "text", "text": texto or "Te mando un pantallazo de BetPlay."})
    mensajes = historial + [{"role": "user", "content": contenido}]
    propuestas: list[dict] = []
    sistema = SISTEMA + _contexto(dia, registro, fecha, pol)
    for _ in range(5):
        r = c.messages.create(model=config.MODELO, max_tokens=1200, system=sistema,
                              tools=HERRAMIENTAS, messages=mensajes)
        usos = [b for b in r.content if b.type == "tool_use"]
        if not usos:
            return "".join(b.text for b in r.content if b.type == "text").strip(), propuestas
        mensajes.append({"role": "assistant", "content": r.content})
        mensajes.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": u.id,
             "content": json.dumps(ejecutar_herramienta(u.name, u.input, dia, pol, propuestas), ensure_ascii=False)}
            for u in usos]})
    return "Listo.", propuestas
