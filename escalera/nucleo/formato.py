"""Formatos colombianos: $ con punto de miles, coma decimal y signo "−"."""
from __future__ import annotations

import datetime as dt
import html

DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
MESES_LARGO = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
               "septiembre", "octubre", "noviembre", "diciembre"]
MENOS = "−"


def e(t) -> str:
    """Escapa & < > para el HTML de Telegram."""
    return html.escape("" if t is None else str(t), quote=False)


def pesos(v, signo: bool = False) -> str:
    if v is None:
        return "—"
    v = round(v)
    s = f"{abs(v):,}".replace(",", ".")
    if signo:
        return ("+" if v > 0 else MENOS if v < 0 else "±") + "$" + s
    return (MENOS if v < 0 else "") + "$" + s


def cuota(v) -> str:
    return "—" if v is None else f"{v:.2f}".replace(".", ",")


def pct(v, signo: bool = False, dec: int = 0) -> str:
    if v is None:
        return "—"
    n = v * 100
    s = f"{abs(n):.{dec}f}".replace(".", ",")
    if signo:
        return ("+" if n > 0.0 else MENOS if n < 0.0 else "") + s + " %"
    return (MENOS if n < 0 else "") + s + " %"


def num(v, dec: int = 2) -> str:
    return f"{v:.{dec}f}".replace(".", ",").replace("-", MENOS)


def fecha_corta(iso: str) -> str:
    d = dt.date.fromisoformat(iso)
    return f"{DIAS[d.weekday()]} {d.day} {MESES[d.month - 1]}"


def fecha_larga(iso: str) -> str:
    d = dt.date.fromisoformat(iso)
    return f"{DIAS[d.weekday()]} {d.day} de {MESES_LARGO[d.month - 1]} de {d.year}"


def barra(actual, total, n: int = 10) -> str:
    if not total:
        return "▱" * n
    llenos = max(0, min(n, round(n * actual / total)))
    return "▰" * llenos + "▱" * (n - llenos)


def leer_numero(txt: str) -> float | None:
    """'1,45' → 1.45 · '3.000' → 3000 · '$3.000' → 3000 · '2.5' → 2.5"""
    t = txt.strip().replace("$", "").replace(" ", "")
    if not t:
        return None
    if "," in t and "." in t:                 # 1.234,56
        t = t.replace(".", "").replace(",", ".")
    elif "," in t:
        t = t.replace(",", ".")
    elif t.count(".") == 1 and len(t.split(".")[1]) == 3:   # 3.000 = miles
        t = t.replace(".", "")
    elif t.count(".") > 1:
        t = t.replace(".", "")
    try:
        return float(t)
    except ValueError:
        return None
