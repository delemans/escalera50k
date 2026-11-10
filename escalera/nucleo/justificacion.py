"""
JUSTIFICACIÓN · por qué entra (o no) cada pick, en palabras simples
==================================================================
Todo sale de los números calculados (nunca se inventa nada):
  a favor   prob. del sistema vs. la que paga la cuota, consenso de casas,
            casa afilada, coincidencia con StatArea, noticias limpias, Kelly
  en contra cuota baja, dispersión, sin StatArea, varianza alta, noticias
  confianza 1–5 (calidad de los datos, no garantía de acierto)
"""
from __future__ import annotations


def _pct(x, dec=1):
    return f"{x * 100:.{dec}f}".replace(".", ",") + " %"


def _pts(x):
    return f"{x * 100:+.1f}".replace(".", ",").replace("-", "−") + " pts"


def _c(o):
    return f"{o:.2f}".replace(".", ",")


def confianza(c: dict) -> int:
    puntos = 1
    puntos += 1 if (c.get("nCasas") or 0) >= 3 else 0
    puntos += 1 if c.get("afilada") else 0
    puntos += 1 if (c.get("dispersion") or 1) <= 0.02 else 0
    if c.get("sa") is not None and c.get("mk") is not None and abs(c["sa"] - c["mk"]) <= 0.04:
        puntos += 1
    if c.get("alerta"):
        puntos = 1
    return max(1, min(5, puntos))


def justificar(c: dict) -> dict:
    favor, contra = [], []
    p, o, mk = c.get("p"), c.get("o"), c.get("mk")
    if p and c.get("p_push"):                     # DNB: comparar contra la prob. sin empate
        p = p / (1 - c["p_push"])
    if p and o:
        implicita = 1 / o
        dif = p - implicita
        if dif > 0:
            favor.append(f"Prob. del sistema {_pct(p)}; la cuota {_c(o)} paga como si fuera "
                         f"{_pct(implicita)} ({_pts(dif)} a tu favor).")
        else:
            contra.append(f"La cuota {_c(o)} supone {_pct(implicita)} y el sistema ve {_pct(p)}: "
                          "no paga lo suficiente.")
    n = c.get("nCasas") or 0
    if n >= 3:
        favor.append(f"Consenso de {n} casas sin margen ({'incluye casa afilada' if c.get('afilada') else 'sin casa afilada'}).")
    elif n:
        contra.append(f"Solo {n} casa{'s' if n > 1 else ''} con cuota: dato menos sólido.")
    if c.get("dispersion") is not None and c["dispersion"] > 0.025:
        contra.append(f"Las casas difieren {_pts(c['dispersion'])}: hay dudas en el mercado.")
    sa = c.get("sa")
    if sa is not None and mk is not None:
        d = sa - mk
        if abs(d) <= 0.04:
            favor.append(f"StatArea coincide con el mercado ({_pct(sa)} vs {_pct(mk)}).")
        elif d > 0:
            favor.append(f"StatArea es aún más optimista ({_pct(sa)}).")
        else:
            contra.append(f"StatArea es más prudente ({_pct(sa)} vs mercado {_pct(mk)}).")
    elif c.get("mercado") in ("TARJETAS", "CORNERS"):
        contra.append("Mercado sin modelo estadístico propio: el valor sale solo de comparar casas.")
    if c.get("p_push"):
        favor.append(f"Si empatan te devuelven la plata (pasa {_pct(c['p_push'])} de las veces); "
                     "la prob. de arriba es sin contar el empate.")
    if c.get("noticias"):
        (contra if c.get("alerta") else favor).append(f"Noticias: {c['noticias']}")
    if o and o >= 2.2:
        contra.append("Cuota alta: más varianza, se pierde más seguido aunque tenga valor.")
    if c.get("ev") is not None:
        if c["ev"] >= 0.05:
            favor.append(f"EV {_pct(c['ev'])}: valor claro.")
        elif c["ev"] >= 0.02:
            favor.append(f"EV {_pct(c['ev'])}: valor moderado.")
    conf = confianza(c)
    etiqueta = ("VALOR ALTO" if (c.get("ev") or 0) >= 0.05 and conf >= 3 else
                "VALOR" if (c.get("ev") or 0) >= 0.02 else "VIGILAR" if (c.get("ev") or 0) >= -0.04 else "NO")
    resumen = favor[0] if favor else (contra[0] if contra else "")
    extra = analisis_extra(c)
    return {"aFavor": favor[:5], "enContra": contra[:4], "confianza": conf, "etiqueta": etiqueta, "resumen": resumen,
            **extra}


COMO_PIERDE = {
    "1X2": "si empatan o gana el rival",
    "DNB": "solo si gana el rival (el empate devuelve)",
    "DC": "solo si gana el equipo que no cubres",
    "GOLES": {"over": "si el partido sale cerrado, con pocos goles", "under": "si se abre el partido y llueven goles"},
    "BTTS": {"si": "si uno de los dos no marca", "no": "si marcan los dos"},
    "EQUIPO": {"over": "si ese equipo no llega a la línea de goles", "under": "si ese equipo marca más de la cuenta"},
    "TARJETAS": {"over": "si el partido sale limpio", "under": "si se calienta el partido"},
    "CORNERS": {"over": "si hay pocos córners", "under": "si hay muchos córners"},
}


def analisis_extra(c: dict) -> dict:
    """Escenarios (gana / devuelve / pierde), cuota justa, «pierde 1 de cada N»,
    cómo se pierde según el mercado y un veredicto de una línea. Solo usa números ya calculados."""
    p, o, push = c.get("p"), c.get("o"), c.get("p_push") or 0.0
    if not p:
        return {}
    pierde = max(0.0, 1 - p - push)
    m = c.get("mercado", "1X2")
    cp = COMO_PIERDE.get(m, "si no se cumple la selección")
    if isinstance(cp, dict):
        cp = cp.get(str(c.get("lado")), "si no se cumple la selección")
    justa = (1 - push) / p if p else None                  # cuota con EV 0 (con DNB descuenta el empate)
    n = round(1 / pierde) if pierde > 0 else None
    escenarios = [{"t": "gana", "p": round(p, 4)}]
    if push:
        escenarios.append({"t": "devuelve", "p": round(push, 4)})
    escenarios.append({"t": "pierde", "p": round(pierde, 4)})
    ev, omin = c.get("ev"), c.get("omin")
    if ev is None or not o:
        veredicto = "Sin cuota confiable: no apostar."
    elif c.get("descartado") or c.get("motivo"):
        veredicto = f"Descartado: {c.get('motivo') or 'no pasa los filtros'}."
    elif ev >= 0.02:
        veredicto = f"Apostar: a {_c(o)} tiene valor; aguanta hasta {_c(omin) if omin else _c(justa)}."
    elif omin:
        veredicto = f"Solo si BetPlay paga {_c(omin)} o más; a {_c(o)} pierde a la larga."
    else:
        veredicto = "No apostar: la cuota no paga el riesgo."
    return {"escenarios": escenarios, "cuotaJusta": round(justa, 3) if justa else None,
            "pierde1de": n, "comoPierde": cp, "veredicto": veredicto,
            "lectura": (f"Gana {_pct(p, 0)}" + (f", devuelve {_pct(push, 0)}" if push else "")
                        + f", pierde {_pct(pierde, 0)}" + (f" (1 de cada {n})" if n else "") + f": pierde {cp}.")}


def por_que_jugada(tipo: str, j: dict) -> list[str]:
    """Motivo de cada jugada multi."""
    if not j:
        return []
    P = j.get("P", 0)
    if tipo == "escalera":
        n = len(j.get("patas", []))
        r = j.get("retiro", 2)
        pmin = min(j.get("probs") or [P])
        intro = (f"{n} peldaño{'s' if n != 1 else ''} con p ≥ {_pct(pmin, 0)} y al menos 2 h entre partidos, para crecer la banca."
                 if not j.get("respaldo") else
                 f"Día flojo: {n} peldaño{'s' if n != 1 else ''} (p ≥ {_pct(pmin, 0)}), los más probables aunque no pasen todos los filtros.")
        if n < 3:
            return [intro, f"Gana {_pct(P)} de las veces. Los días flojos salen menos peldaños, pero siempre hay al menos uno."]
        return [intro,
                f"Peldaños 1–{r}: todo lo cobrado pasa al siguiente. Antes del peldaño {r + 1} se aparta la base "
                f"(queda a salvo {_pct(j.get('Pbase') or 0)} de las veces) y se sigue solo con la ganancia.",
                f"Completa {_pct(P)} de las veces."]
    if tipo == "combinada":
        intro = (f"Combinada de valor: cada pierna tiene EV ≥ 0 y el boleto suma EV {_pct(j.get('ev') or 0)}."
                 if j.get("valor", True) else
                 f"Hoy no hay combinada con valor claro: esta es la mejor posible (EV {_pct(j.get('ev') or 0)}); solo con la mínima.")
        return [intro,
                f"Paga {_c(j.get('cuota') or 0)} y gana {_pct(P)} de las veces."]
    if tipo == "super":
        return [f"Soñadora: {len(j.get('patas', []))} piernas con p ≥ 65 %, la combinación más probable del día para cuota 5–8 "
                f"(hoy {_c(j.get('cuota') or 0)}).",
                f"Prob. {_pct(P, 1)}: entra más o menos 1 de cada {max(1, round(1 / P)) if P else '—'} veces; va con la apuesta mínima.",
                f"EV del boleto {_pct(j.get('ev') or 0)}."]
    if tipo == "progresion":
        return ["Escalera de crecimiento: el pick más seguro del día (cuota 1,25–1,60) para reinvertir todo lo ganado.",
                "Si pierde, la serie termina y empieza otra con la base."]
    return []
