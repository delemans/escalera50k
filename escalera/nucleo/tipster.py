"""
TIPSTER · picks de canales externos (Sharpods u otros) como un dato más
=====================================================================
Los picks llegan reenviados al bot (GET /tipster.json). La mesa:
  evaluar(dia, picks)       → sección dia["tipster"]: cruza cada pick con los picks
                              del día (probabilidad propia) y da veredicto
                              valor | sin_valor | descartado | sin_modelo
  filas_nuevas(...)         → filas de seguimiento para la colección "apuestas"
                              (tipster: <nombre>, simulada: False, real: False:
                              no tocan bancas ni estadísticas del sistema)
  liquidar(filas, marcadores) → resultado de cada pick pendiente
  record(filas)             → aciertos y ROI a 1 unidad por pick
"""
from __future__ import annotations

import math
import re
import unicodedata

from . import valor as V


def normalizar(s: str | None) -> str:
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]+", " ", s).strip()


def _palabras(s: str) -> set[str]:
    return {w for w in normalizar(s).split() if len(w) > 2 and w not in {"vs", "fc", "cf", "club", "the"}}


def _mismo_equipo(a: str, b: str) -> bool:
    pa, pb = _palabras(a), _palabras(b)
    return bool(pa and pb and (pa & pb))


def _equipos(partido: str | None) -> tuple[str, str] | None:
    if not partido:
        return None
    partes = re.split(r"\s+(?:vs\.?|v|-|–)\s+", partido, maxsplit=1, flags=re.I)
    return (partes[0].strip(), partes[1].strip()) if len(partes) == 2 else None


def buscar_pick(dia: dict, partido: str | None, sel: str | None) -> dict | None:
    """Pick del día con el mismo partido y la misma selección (comparación tolerante)."""
    eq = _equipos(partido)
    if not eq:
        return None
    for p in dia.get("picks") or []:
        if not ((_mismo_equipo(eq[0], p.get("h", "")) or _mismo_equipo(eq[1], p.get("h", ""))) and
                (_mismo_equipo(eq[0], p.get("a", "")) or _mismo_equipo(eq[1], p.get("a", "")))):
            continue
        if normalizar(sel) == normalizar(p.get("sel")):
            return p
        ganador = re.match(r"(?:gana|victoria de|triunfo de)\s+(.+)", normalizar(sel)) or \
            re.match(r"(.+?)\s+gana$", normalizar(sel))
        if ganador and normalizar(p.get("sel", "")).startswith("gana") and \
                _mismo_equipo(ganador.group(1), p["sel"][5:]) and (p.get("mercado") in (None, "1X2")):
            return p
    return None


def _evaluar_uno(dia: dict, partido, sel, o) -> dict:
    p = buscar_pick(dia, partido, sel)
    if not p or not p.get("p"):
        return {"veredicto": "sin_modelo", "nota": "Sin probabilidad propia: solo seguimiento."}
    if p.get("alerta"):
        return {"veredicto": "descartado", "p": p["p"], "nota": (p.get("noticias") or "Alerta de noticias")[:120]}
    if not o:
        return {"veredicto": "sin_modelo", "p": p["p"], "omin": round(V.evaluar(p["p"], 2.0).omin, 2),
                "nota": "Falta la cuota del tipster."}
    ev = V.evaluar(p["p"], o)
    return {"veredicto": "valor" if ev.valor else "sin_valor", "p": round(p["p"], 4),
            "ev": round(ev.ev, 4), "omin": round(ev.omin, 2), "nota": ev.texto}


def evaluar(dia: dict, picks: list[dict], fecha: str | None = None) -> dict:
    fecha = fecha or dia.get("fecha")
    out = []
    for t in picks:
        if fecha and t.get("fecha") != fecha:
            continue
        base = {k: t.get(k) for k in ("id", "tipster", "hora", "partido", "sel", "mercado", "cuota", "tipo", "piernas")}
        if t.get("tipo") == "combinada" and t.get("piernas"):
            evs = [_evaluar_uno(dia, x.get("partido"), x.get("sel"), x.get("o")) for x in t["piernas"]]
            if all(e.get("p") for e in evs) and not any(e["veredicto"] == "descartado" for e in evs) and t.get("cuota"):
                P = math.prod(e["p"] for e in evs)
                ev = V.evaluar(P, t["cuota"])
                r = {"veredicto": "valor" if ev.valor else "sin_valor", "p": round(P, 4),
                     "ev": round(ev.ev, 4), "omin": round(ev.omin, 2),
                     "nota": f"{len(evs)} piernas · prob. conjunta {P:.0%}"}
            else:
                malas = sum(1 for e in evs if not e.get("p"))
                r = {"veredicto": "descartado" if any(e["veredicto"] == "descartado" for e in evs) else "sin_modelo",
                     "nota": f"Combinada de {len(evs)} piernas; {malas} sin probabilidad propia."}
        else:
            r = _evaluar_uno(dia, t.get("partido"), t.get("sel"), t.get("cuota"))
        out.append({**base, **r})
    fuentes = sorted({x.get("tipster") or "Tipster" for x in out})
    return {"fuente": " · ".join(fuentes) if fuentes else None, "picks": out}


# ---------------------------------------------------------------------------
# Liquidación (selecciones en lenguaje natural de los tipsters)
# ---------------------------------------------------------------------------
def resultado(sel: str, partido: str, marcador) -> str:
    if isinstance(marcador, dict):
        marcador = marcador.get("marcador")
    if not marcador:
        return "pendiente"
    if str(marcador).lower() in ("aplazado", "suspendido", "nulo", "cancelado"):
        return "nulo"
    m = re.match(r"\s*(\d+)\s*[-–:]\s*(\d+)", str(marcador))
    eq = _equipos(partido)
    if not m or not eq:
        return "pendiente"
    gl, gv = int(m.group(1)), int(m.group(2))
    s = normalizar(sel).replace(",", ".")
    s = re.sub(r"(\d) (\d)", r"\1.\2", s)                   # "2 5" (de "2,5") → "2.5"

    def lado(nombre):
        if _mismo_equipo(nombre, eq[0]):
            return "L"
        if _mismo_equipo(nombre, eq[1]):
            return "V"
        return None

    g = re.search(r"(mas|menos) de (\d+(?:\.\d+)?) goles", s)
    if g:
        total, linea = gl + gv, float(g.group(2))
        if total == linea:
            return "nulo"
        return "ganado" if (total > linea) == (g.group(1) == "mas") else "perdido"
    if "ambos marcan" in s:
        si = not re.search(r"ambos marcan\s*(no|:\s*no)", s)
        return "ganado" if ((gl > 0 and gv > 0) == si) else "perdido"
    mm = re.match(r"(.+?) marca(?: (\d+) o mas)?", s)
    if mm:
        ld, n = lado(mm.group(1)), int(mm.group(2) or 1)
        if ld:
            goles = gl if ld == "L" else gv
            return "ganado" if goles >= n else "perdido"
    oe = re.match(r"(.+?) o empate", s)
    if oe and lado(oe.group(1)):
        ld = lado(oe.group(1))
        return "ganado" if (gl >= gv if ld == "L" else gv >= gl) else "perdido"
    if s.startswith("empate"):
        return "ganado" if gl == gv else "perdido"
    gg = re.match(r"(?:gana|victoria de)\s+(.+)", s)
    if gg and lado(gg.group(1)):
        ld = lado(gg.group(1))
        return "ganado" if (gl > gv if ld == "L" else gv > gl) else "perdido"
    return "pendiente"            # no se entiende: lo liquida la mesa a mano


def liquidar(filas: list[dict], marcadores: dict) -> list[dict]:
    """Filas de seguimiento (con "tipster") pendientes → filas liquidadas."""
    def marc(partido):
        if partido in marcadores:
            return marcadores[partido]
        eq = _equipos(partido)
        for k, v in marcadores.items():
            ek = _equipos(k)
            if eq and ek and _mismo_equipo(eq[0], ek[0]) and _mismo_equipo(eq[1], ek[1]):
                return v
        return None

    out = []
    for f in filas:
        if not f.get("tipster") or f.get("resultado") != "pendiente":
            continue
        piernas = f.get("piernas") or [{"partido": f.get("partido"), "sel": f.get("seleccion")}]
        res = [resultado(p.get("sel") or "", p.get("partido") or "", marc(p.get("partido"))) for p in piernas]
        if "perdido" in res:
            r = "perdido"
        elif "pendiente" in res:
            continue
        elif all(x == "nulo" for x in res):
            r = "nulo"
        else:
            r = "ganado"
        textos = []
        for p in piernas:
            v = marc(p.get("partido"))
            textos.append(str(v.get("marcador") if isinstance(v, dict) else v))
        out.append({**f, "resultado": r, "marcador": " · ".join(textos)})
    return out


def record(filas: list[dict]) -> dict:
    """Aciertos y ROI a 1 unidad por pick (por tipster y total)."""
    def calc(fs):
        fs = [f for f in fs if f.get("resultado") in ("ganado", "perdido")]
        if not fs:
            return {"n": 0}
        ben = sum(((f.get("cuotaRef") or 1) - 1) if f["resultado"] == "ganado" else -1 for f in fs)
        return {"n": len(fs), "aciertos": sum(f["resultado"] == "ganado" for f in fs), "roi": round(ben / len(fs), 4)}

    ts = [f for f in filas if f.get("tipster")]
    por = {}
    for f in ts:
        por.setdefault(f["tipster"], []).append(f)
    return {**calc(ts), "porTipster": {k: calc(v) for k, v in por.items()}}


def filas_nuevas(evaluados: list[dict], existentes: list[dict], fecha: str) -> list[dict]:
    """Filas de seguimiento para "apuestas": ids AAAA-MM-DD-tN, sin duplicar."""
    ya = {(f.get("tipster"), normalizar(f.get("partido")), normalizar(f.get("seleccion")))
          for f in existentes if f.get("tipster")}
    n = sum(1 for f in existentes if str(f.get("id", "")).startswith(f"{fecha}-t"))
    out = []
    for e in evaluados:
        clave = (e.get("tipster"), normalizar(e.get("partido") or "Combinada"), normalizar(e.get("sel")))
        if clave in ya:
            continue
        ya.add(clave)
        n += 1
        out.append({"id": f"{fecha}-t{n}", "fecha": fecha, "hora": e.get("hora"), "tipo": e.get("tipo") or "sencilla",
                    "tipster": e.get("tipster"), "partido": e.get("partido") or "Combinada",
                    "seleccion": e.get("sel"), "mercado": e.get("mercado"), "cuotaRef": e.get("cuota"),
                    "piernas": e.get("piernas"), "p": e.get("p"), "ev": e.get("ev"), "veredicto": e.get("veredicto"),
                    "resultado": "pendiente", "simulada": False, "real": False, "stake": None, "stakeReal": None,
                    "neto": None, "netoReal": None})
    return out
