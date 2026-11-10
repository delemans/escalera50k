"""
CHARLA · conversación sin IA (siempre responde)
===============================================
Si no hay clave de IA, o la IA está saturada, el bot igual conversa: entiende
las preguntas más comunes en lenguaje natural y responde con los datos reales
del día y del registro. Nunca inventa: lo que no sabe, lo dice.

Intenciones: saludo · gracias · despedida · qué apuesto / plan · escalera ·
resultados / cómo voy · banca / saldo · "me pagan 1,58 por Envigado" (cuota) ·
por qué · ayuda. Todo lo demás: respuesta amable con lo que sí puede hacer.
"""
from __future__ import annotations

import re
import unicodedata

from ..nucleo.formato import cuota, e, pesos
from . import mensajes as M


def _n(t: str) -> str:
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", t).strip()


INTENCIONES = [
    ("cuota", r"(me (la )?pagan|paga|esta (a|en)|cuota|@)\s*\d+[.,]\d+|\b\d[.,]\d{1,2}\b"),
    ("resultados", r"resultad|como voy|como vamos|gane|perdi|ayer|que paso|balance|historial|record|racha"),
    ("escalera", r"escalera|peldan|soñadora|sonadora|respaldo|reserva"),
    ("plan", r"que (apuesto|juego|hago|monto)|plan|jugadas?|hoy|pick|recomienda|que hay"),
    ("banca", r"banca|saldo|plata|dinero|cuanto (tengo|llevo)|tope|unidad"),
    ("porque", r"por ?que|razon|explica"),
    ("ayuda", r"ayuda|comandos|como (funciona|uso)|que (puedes|sabes)"),
    ("gracias", r"gracias|bacano|chevere|listo|perfecto|ok\b|vale\b"),
    ("despedida", r"chao|adios|hasta (luego|manana)|buenas noches"),
    ("saludo", r"^(hola|buenas|buenos|hey|que mas|quiubo|ey)\b"),
]


def intencion(texto: str) -> str:
    t = _n(texto)
    for nombre, patron in INTENCIONES:
        if re.search(patron, t):
            return nombre
    return "otro"


def _plan_items(dia: dict) -> list[dict]:
    return [x for x in (dia.get("plan") or []) if x.get("accion") != "NO"]


def _primera_jugada(dia: dict) -> str:
    items = _plan_items(dia)
    if not items:
        return "Hoy no hay jugadas en el plan."
    x = items[0]
    return (f"{M.ICONO_ACCION.get(x['accion'], '•')} <b>{e(x['titulo'])}</b> · {x.get('hora', '')} · "
            f"mín <b>{cuota(x.get('cuota_min'))}</b>")


def _buscar_item(dia: dict, texto: str) -> dict | None:
    """Encuentra la jugada del plan o el pick que el usuario nombra (por equipo)."""
    t = _n(texto)
    candidatos = []
    jug = dia.get("jugadas") or {}
    for x in dia.get("plan") or []:
        nombres = [_n(x.get("titulo", ""))]
        clave = x.get("tipo")
        j = jug.get(clave) if clave in ("escalera", "super", "combinada", "progresion") else None
        if j:
            nombres += [_n(p.get("partido", "") + " " + p.get("sel", "")) for p in j.get("patas", [])]
        candidatos.append((x, nombres))
    for pl in jug.get("reserva") or []:
        nombres = [_n(p.get("partido", "") + " " + p.get("sel", "")) for p in pl.get("patas", [])]
        candidatos.append(({"titulo": f"Respaldo {pl['n']}", "cuota_min": pl.get("omin"), "cuota_ref": pl.get("cuota"),
                            "accion": "VIGILAR", "tipo": pl.get("tipo")}, nombres))
    palabras = [w for w in re.findall(r"[a-z]{4,}", t) if w not in {"pagan", "paga", "cuota", "esta", "betplay", "para"}]
    for x, nombres in candidatos:
        if any(w in n for w in palabras for n in nombres):
            return x
    items = _plan_items(dia)
    return items[0] if len(items) == 1 else None


def _cuota(dia: dict, texto: str) -> str:
    m = re.search(r"(\d+[.,]\d{1,3})", texto)
    o = float(m.group(1).replace(",", ".")) if m else None
    x = _buscar_item(dia, texto)
    if not o or not x:
        return ("Dime la cuota y el partido, por ejemplo: <i>«me pagan 1,62 por Envigado»</i>, "
                "y te digo si sirve.")
    cmin = x.get("cuota_min")
    if not cmin:
        return f"No tengo cuota mínima para <b>{e(x['titulo'])}</b>; mejor no la tomes."
    if o >= cmin:
        monto = f" con <b>{pesos(x['monto'])}</b>" if x.get("monto") else ""
        return (f"🟢 <b>Sí sirve.</b> {e(x['titulo'])} a {cuota(o)} ≥ mínima {cuota(cmin)}: apuesta{monto}.\n"
                "Cuando la montes, mándame el pantallazo y la registro.")
    falta = cmin - o
    return (f"⚪ <b>No sirve.</b> {e(x['titulo'])} a {cuota(o)} está {cuota(falta)} por debajo de la mínima "
            f"{cuota(cmin)}. Con esa cuota pierdes a la larga: espera o pasa al siguiente respaldo.")


def _escalera(dia: dict) -> str:
    jug = dia.get("jugadas") or {}
    esc = jug.get("escalera")
    out = []
    if esc:
        out.append(f"🪜 <b>Escalera de {esc['peldanos']} peldaño{'s' if esc['peldanos'] != 1 else ''}</b> · "
                   f"{pesos(esc['stake'])} → {pesos(esc.get('final'))} si completa")
        for i, (p, monto) in enumerate(zip(esc["patas"], esc.get("montos") or []), 1):
            out.append(f"{i}) {p['t']} {e(p['sel'])} @{cuota(p['o'])} · {pesos(monto)}")
        out.append(f"Probabilidad de completarla: <b>{round(esc['P'] * 100)} %</b>")
    else:
        out.append("🪜 Hoy no hay escalera.")
    res = jug.get("reserva") or []
    if res:
        out.append(f"\n🔁 <b>{len(res)} planes de respaldo</b> (si uno no paga la mínima, pasa al siguiente):")
        for pl in res[:5]:
            patas = " + ".join(f"{p['t']} {p['sel']}" for p in pl["patas"])
            out.append(f"{pl['n']}. {e(patas)} @{cuota(pl['cuota'])} · mín {cuota(pl.get('omin'))}")
        if len(res) > 5:
            out.append(f"… y {len(res) - 5} más en /escalera.")
    return "\n".join(out)


def _porque(dia: dict, texto: str) -> str:
    jug = dia.get("jugadas") or {}
    esc = jug.get("escalera")
    if esc and esc.get("detalle"):
        d = esc["detalle"][0]
        razones = "\n".join(f"• {e(r)}" for r in (d.get("razones") or [])[:3])
        contra = "\n".join(f"• {e(r)}" for r in (d.get("enContra") or [])[:2])
        return f"🧠 <b>{e(d['sel'])}</b>\n{razones}" + (f"\n<b>En contra:</b>\n{contra}" if contra else "")
    return "Hoy no hay jugada con análisis para explicar."


def responder(texto: str, dia: dict, registro: list[dict] | None = None, banca: float | None = None) -> str:
    """Respuesta en HTML de Telegram. Nunca lanza excepción."""
    try:
        it = intencion(texto)
        if it == "saludo":
            return (f"¡Hola! 👋 {M.saludo_hora()}.\n" + _primera_jugada(dia)
                    + "\n\nPregúntame <i>«¿qué apuesto?»</i>, <i>«¿cómo voy?»</i> o <i>«me pagan 1,62 por Envigado»</i>.")
        if it == "gracias":
            return "Con gusto 🙌. Recuerda: solo si BetPlay paga la mínima. Aquí sigo."
        if it == "despedida":
            return "¡Hasta luego! 🌙 Si algo cambia en tus partidos te aviso por aquí."
        if it == "cuota":
            return _cuota(dia, texto)
        if it == "resultados":
            return M.resultados(registro or [], dia)
        if it == "escalera":
            return _escalera(dia)
        if it == "plan":
            return M.plan(dia) or "Hoy no hay plan publicado todavía."
        if it == "banca":
            b = dia.get("bancas") or {}
            return (f"💰 <b>Banca</b>\nReal: {pesos(b.get('real'))} · Sistema: {pesos(b.get('sistema'))}"
                    + (f"\nSaldo reportado: {pesos(banca)}" if banca else "")
                    + "\nPara actualizarla: <i>/saldo 25000</i>.")
        if it == "porque":
            return _porque(dia, texto)
        if it == "ayuda":
            return M.ayuda()
        return ("Te leo 👀. Todavía no entiendo eso sin la IA, pero puedo ayudarte con:\n"
                "• <i>«¿qué apuesto hoy?»</i>\n• <i>«¿cómo voy?»</i> (resultados ordenados)\n"
                "• <i>«me pagan 1,55 por Mansfield»</i>\n• <i>«la escalera»</i> y sus respaldos\n"
                "• un pantallazo o <i>«hice la escalera por 5000»</i> para registrar")
    except Exception:                                  # nunca tumbar la charla
        return "Se me enredó la respuesta 😅. Prueba con /hoy, /plan o /resultados."
