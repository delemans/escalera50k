"""
RIESGO · cuándo seguir, cuándo bajar y cuándo parar (solo informa, no bloquea)
=============================================================================
Reglas sobre tus apuestas REALES ya liquidadas:

  🛑 STOP del día        pérdida del día ≥ 5 % de la banca → no más apuestas hoy
  🟠 MODO REDUCIDO       pérdida de 7 días ≥ 12 % → stakes al 50 % (hasta recuperar la mitad)
  🧊 ENFRIAMIENTO        3 pérdidas seguidas → mañana stakes al 50 %
  🔴 FRENO               banca < 70 % de la inicial → stakes al 50 % (ya existía)
  🟢 ASEGURAR            día ≥ +8 % → no subas stakes; retira parte de la ganancia
  🚫 NUNCA RECUPERAR     subir el stake después de perder (martingala) multiplica el riesgo de ruina

Escalera de crecimiento (reinvertir lo ganado):
  • modo seguro: desde el peldaño 2 se aparta la base y se reinvierte solo la ganancia
  • máximo 5 peldaños o la meta; luego se cobra y empieza otra serie
  • 2 series perdidas seguidas → la próxima base baja a la mitad
"""
from __future__ import annotations

import datetime as dt

STOP_DIA = 0.05
REDUCIDO_7D = 0.12
RACHA = 3
ASEGURAR_DIA = 0.08
MAX_PELDANOS = 5


def _neto_real(f):
    from .liquidacion import neto
    return neto(f, real=True)


def evaluar(filas: list[dict], banca: float, hoy: str, banca_inicial: float | None = None) -> dict:
    reales = sorted([f for f in filas if f.get("real") and f.get("resultado") in ("ganado", "perdido", "nulo")],
                    key=lambda f: (f.get("fecha", ""), f.get("hora", ""), f.get("creado", 0)))
    d_hoy = dt.date.fromisoformat(hoy)
    desde7 = (d_hoy - dt.timedelta(days=7)).isoformat()
    ayer = (d_hoy - dt.timedelta(days=1)).isoformat()
    neto_hoy = sum(_neto_real(f) for f in reales if f.get("fecha") == hoy)
    neto_ayer = sum(_neto_real(f) for f in reales if f.get("fecha") == ayer)
    neto_7 = sum(_neto_real(f) for f in reales if f.get("fecha", "") >= desde7)
    racha = 0
    for f in reversed(reales):
        if f["resultado"] == "perdido":
            racha += 1
        elif f["resultado"] == "ganado":
            break
    factor, estado, alertas = 1.0, "normal", []
    if banca and neto_hoy <= -STOP_DIA * banca:
        estado = "stop"
        factor = 0.0
        alertas.append({"nivel": "rojo", "t": f"STOP del día: llevas {neto_hoy:,.0f} hoy (≥ 5 % de la banca). "
                                                "Para por hoy; mañana se sigue con el plan normal.".replace(",", ".")})
    if banca and neto_7 <= -REDUCIDO_7D * banca:
        estado = "reducido" if estado == "normal" else estado
        factor = min(factor, 0.5) if factor else 0.0
        alertas.append({"nivel": "naranja", "t": "Modo reducido: −12 % o más en 7 días. Stakes al 50 % hasta recuperar la mitad."})
    if racha >= RACHA:
        factor = min(factor, 0.5) if factor else 0.0
        alertas.append({"nivel": "naranja", "t": f"Enfriamiento: {racha} pérdidas seguidas. Stakes al 50 % hoy; "
                                                 "no intentes recuperar subiendo montos."})
    if banca and neto_ayer >= ASEGURAR_DIA * banca:
        alertas.append({"nivel": "verde", "t": "Ayer fue un gran día (+8 % o más): asegura, no subas stakes y "
                                               "retira parte de lo ganado de la escalera."})
    return {"estado": estado, "factor": factor, "netoHoy": round(neto_hoy), "neto7d": round(neto_7),
            "racha": racha, "alertas": alertas}


def escalera_crecimiento(cfg: dict, modo: str = "seguro") -> dict:
    """Cuánto va en el próximo peldaño. Seguro: desde el peldaño 2 se aparta la base."""
    saldo, base, paso = cfg.get("saldo", 0), cfg.get("base", 0), cfg.get("paso", 1)
    if modo == "seguro" and paso >= 2 and saldo > base:
        stake, asegurado = saldo - base, base
    else:
        stake, asegurado = saldo, 0
    avisos = []
    if paso > MAX_PELDANOS:
        avisos.append(f"Ya van {paso - 1} peldaños: cobra y empieza una serie nueva.")
    perdidas = 0
    for h in reversed(cfg.get("historial") or []):
        if h.get("resultado") == "perdido":
            perdidas += 1
        else:
            break
    if perdidas >= 2:
        avisos.append("2 series perdidas seguidas: la próxima base debería bajar a la mitad.")
    return {"stake": round(stake), "asegurado": round(asegurado), "agresivo": round(saldo), "avisos": avisos}
