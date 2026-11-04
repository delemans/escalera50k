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
    return {"aFavor": favor[:5], "enContra": contra[:4], "confianza": conf, "etiqueta": etiqueta, "resumen": resumen}


def por_que_jugada(tipo: str, j: dict) -> list[str]:
    """Motivo de cada jugada multi."""
    if not j:
        return []
    P = j.get("P", 0)
    if tipo == "escalera":
        return ["Tres favoritos con p ≥ 65 % y al menos 2 h entre partidos, para reinvertir con calma.",
                f"Cada peldaño que gana pasa TODO al siguiente; completa {_pct(P)} de las veces."]
    if tipo == "combinada":
        intro = (f"Combinada de valor: cada pierna tiene EV ≥ 0 y el boleto suma EV {_pct(j.get('ev') or 0)}."
                 if j.get("valor", True) else
                 f"Hoy no hay combinada con valor claro: esta es la mejor posible (EV {_pct(j.get('ev') or 0)}); solo con la mínima.")
        return [intro,
                f"Paga {_c(j.get('cuota') or 0)} y gana {_pct(P)} de las veces."]
    if tipo == "super":
        return [f"Soñadora: {len(j.get('patas', []))} piernas, las más probables del día, para una cuota de {_c(j.get('cuota') or 0)}.",
                f"Prob. {_pct(P, 2)}: se acierta muy pocas veces; por eso va siempre con la apuesta mínima.",
                f"EV del boleto {_pct(j.get('ev') or 0)} (ojo: con tantas piernas un error pequeño en cada una cambia mucho)."]
    if tipo == "progresion":
        return ["Escalera de crecimiento: el pick más seguro del día (cuota 1,25–1,60) para reinvertir todo lo ganado.",
                "Si pierde, la serie termina y empieza otra con la base."]
    return []
