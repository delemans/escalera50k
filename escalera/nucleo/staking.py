"""
STAKING · cuánto apostar con dinero real y qué hacer con cada jugada
===================================================================
Reglas (todas configurables en PoliticaStake):
  • Unidad = 2 % de la banca real.               ($100.000 → $2.000)
  • Sencilla: 1/4 de Kelly, entre la apuesta mínima y 1,5 unidades.
  • Escalera 2 u · combinada 1 u · súper 0,5 u · progresión = su saldo propio.
  • Una jugada se recomienda con dinero real SOLO si EV ≥ +2 %.
  • Tope diario: 12 % de la banca. Si la suma pasa, todo se reduce en proporción.
  • Banca bajo el 70 % de la inicial → stakes a la mitad (freno suave, avisado).
  • Montos redondeados a $500 (BetPlay acepta montos cerrados).

Acciones:
  APOSTAR  → EV ≥ +2 % con la cuota de referencia: apuesta el monto si BetPlay
             paga al menos la mínima.
  VIGILAR  → EV entre −4 % y +2 %: solo si BetPlay paga la mínima (dime la cuota).
  NO       → EV < −4 %, alerta de noticias o falta de datos: solo se simula.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from . import valor as V


def _pct(x):
    return f"{'+' if x >= 0 else '−'}{abs(x) * 100:.1f} %".replace(".", ",")


@dataclass
class PoliticaStake:
    banca: float = 100_000
    banca_inicial: float = 100_000
    unidad_pct: float = 0.02
    kelly_frac: float = 0.25
    max_unidades_sencilla: float = 1.5
    unidades: dict = field(default_factory=lambda: {
        "escalera": 2.0, "combinada": 1.0, "super": 0.0})   # soñadora = apuesta mínima
    apuesta_minima: float = 1_000
    redondeo: float = 500
    tope_diario_pct: float = 0.12
    freno_pct: float = 0.70
    max_exposicion_partido: float = 2.5     # unidades que pueden depender de un mismo partido
    margen_valor: float = V.MARGEN_VALOR
    umbral_vigilar: float = -0.04
    escalera_fija: float = 0               # > 0: la escalera usa este monto fijo (fondo aparte elegido por el usuario)
    escalera_ev_min: float = -0.06         # con fondo fijo se apuesta si el EV no es peor que esto

    @property
    def freno(self) -> bool:
        return self.banca < self.freno_pct * self.banca_inicial

    @property
    def unidad(self) -> float:
        u = self.banca * self.unidad_pct
        return u * (0.5 if self.freno else 1.0)

    @property
    def tope_diario(self) -> float:
        return self.banca * self.tope_diario_pct

    def redondear(self, x: float) -> float:
        if x <= 0:
            return 0
        r = round(x / self.redondeo) * self.redondeo
        return max(self.apuesta_minima, r)


@dataclass
class Instruccion:
    id: str
    tipo: str
    titulo: str
    accion: str          # APOSTAR | VIGILAR | NO
    monto: float         # pesos reales sugeridos (0 si NO)
    cuota_ref: float
    cuota_min: float
    p: float
    ev: float
    razon: str
    hora: str = ""
    p_push: float = 0.0

    def dict(self):
        return asdict(self)


def _accion(ev: float, pol: PoliticaStake, alerta: bool = False) -> str:
    if alerta:
        return "NO"
    if ev >= pol.margen_valor:
        return "APOSTAR"
    if ev >= pol.umbral_vigilar:
        return "VIGILAR"
    return "NO"


def stake_sencilla(p: float, o: float, pol: PoliticaStake, k_total: float | None = None) -> float:
    k = (V.kelly(p, o) if k_total is None else k_total) * pol.kelly_frac
    bruto = min(k * pol.banca, pol.max_unidades_sencilla * pol.unidad)
    if bruto <= 0:
        return 0
    return pol.redondear(max(bruto, pol.apuesta_minima))


def decidir_con_cuota_betplay(p: float, o_betplay: float, pol: PoliticaStake,
                              tipo: str = "sencilla", p_push: float = 0.0) -> tuple[str, float, V.Evaluacion]:
    """Cuando el usuario dice cuánto paga BetPlay: decisión final y monto (p_push = empate devuelto)."""
    ev_ = V.evaluar(p, o_betplay, pol.margen_valor)
    if p_push:
        from . import mercados as MK
        e = MK.ev(p, p_push, o_betplay)
        ev_ = V.Evaluacion(p, o_betplay, e, MK.cuota_minima(p, p_push, pol.margen_valor), (1 - p_push) / p,
                           MK.kelly(p, p_push, o_betplay), e >= pol.margen_valor,
                           "valor" if e >= pol.margen_valor else "justa" if e >= 0 else "negativa",
                           "Tiene valor (contando que el empate devuelve)." if e >= pol.margen_valor
                           else "EV negativo con esa cuota.")
    if not ev_.valor:
        return "NO", 0, ev_
    if tipo == "sencilla":
        return "APOSTAR", stake_sencilla(p, o_betplay, pol, ev_.kelly if p_push else None), ev_
    return "APOSTAR", pol.redondear(pol.unidades.get(tipo, 1) * pol.unidad), ev_


def plan_del_dia(dia: dict, pol: PoliticaStake) -> list[Instruccion]:
    """Lista ordenada por hora de qué hacer con cada jugada del día."""
    picks = {p["id"]: p for p in dia.get("picks", []) if p.get("id")}
    jug = dia.get("jugadas") or {}
    out: list[Instruccion] = []

    for n, pid in enumerate((jug.get("sencillas") or {}).get("ids", []), 1):
        p = picks.get(pid)
        if not p:
            continue
        acc = _accion(p["ev"], pol, p.get("alerta"))
        monto = stake_sencilla(p["p"], p["o"], pol, p.get("kelly")) if acc == "APOSTAR" else 0
        razon = {"APOSTAR": f"EV {_pct(p['ev'])} con la cuota de referencia.",
                 "VIGILAR": "Casi justa: solo si BetPlay paga la mínima.",
                 "NO": "EV negativo o alerta: se sigue en simulación."}[acc]
        out.append(Instruccion(pid, "sencilla", f"{n} · {p['sel']}", acc, monto, p["o"],
                               p.get("omin") or V.cuota_minima(p["p"]), p["p"], p["ev"],
                               razon, p.get("t", ""), p.get("p_push") or 0.0))

    for clave, nombre in (("escalera", "Escalera"), ("combinada", "Combinada"), ("super", "Soñadora")):
        j = jug.get(clave)
        if not j:
            continue
        acc = _accion(j["ev"], pol)
        razon = "Multi: todas las piernas deben ganar." if acc != "NO" else "EV negativo: solo simulación."
        fija = clave == "escalera" and pol.escalera_fija > 0
        if clave == "super" and j["ev"] >= -0.10:
            acc = "APOSTAR"                                 # prueba diaria del sistema: siempre la mínima
            razon = ("Prueba diaria de la soñadora: solo la apuesta mínima. "
                     + ("Tiene valor." if j["ev"] >= 0 else "EV ligeramente negativo: es un boleto de lotería."))
        if clave == "combinada" and j.get("valor") is False and acc == "NO":
            acc = "VIGILAR"
            razon = "Hoy no hay combinada con valor: esta es la mejor posible; solo si BetPlay paga la mínima."
        if fija:
            acc = "APOSTAR" if j["ev"] >= pol.escalera_ev_min else "VIGILAR"
            razon = (f"Escalera con el fondo fijo que elegiste (${pol.escalera_fija:,.0f}".replace(",", ".")
                     + "): va aparte, no cuenta en el tope diario."
                     + ("" if acc == "APOSTAR" else " Hoy el EV es muy bajo: solo si BetPlay paga la mínima."))
        if acc != "APOSTAR":
            monto = 0
        elif fija:
            monto = pol.escalera_fija
        elif clave == "super":
            monto = pol.apuesta_minima                      # gasto fijo y mínimo
        else:
            monto = pol.redondear(pol.unidades[clave] * pol.unidad)
        if clave == "escalera":
            cref = 1.0
            for x in j["patas"]:
                cref *= x["o"]
        else:
            cref = j["cuota"]
        cmin = V.cuota_minima(j["P"], pol.margen_valor)
        if clave == "escalera" and j.get("conSeguro") and j["ev"] > -1:
            cmin = cref * (1 + pol.margen_valor) / (1 + j["ev"])   # con DNB: P es "no perder", no "ganar"
        if clave == "super":
            cmin = min(cmin, cref * 0.9)                     # soñadora: acepta hasta un 10 % menos que la referencia
        out.append(Instruccion(j["id"], clave, nombre, acc, monto, round(cref, 3), round(cmin, 3), j["P"], j["ev"],
                               razon, j["patas"][0].get("t", "")))

    pr = jug.get("progresion")
    if pr:
        acc = _accion(pr["ev"], pol)
        out.append(Instruccion(pr["id"], "progresion", f"Escalera de crecimiento · peldaño {pr['paso']} de 5", acc,
                               pr["stake"] if acc == "APOSTAR" else 0, pr["patas"][0]["o"],
                               round(V.cuota_minima(pr["P"], pol.margen_valor), 3), pr["P"], pr["ev"],
                               "Reto aparte con su propio fondo: no cuenta en el tope ni en el plan diario.",
                               pr["patas"][0].get("t", "")))

    # Exposición por partido: si un mismo partido sostiene demasiadas jugadas, se recortan las multi
    patas_de = {}
    for i in out:
        if i.tipo == "sencilla":
            patas_de[i.id] = [i.id]
        elif i.tipo == "escalera" and pol.escalera_fija > 0:
            continue                                        # fondo aparte: no cuenta en la exposición
        elif i.tipo in jug and jug[i.tipo] and i.tipo != "progresion":
            patas_de[i.id] = [x["id"] for x in jug[i.tipo]["patas"]]
    limite = pol.max_exposicion_partido * pol.unidad
    for _ in range(3):
        expo = {}
        for i in out:
            for pid in patas_de.get(i.id, []):
                expo[pid] = expo.get(pid, 0) + i.monto
        excedidos = {pid for pid, v in expo.items() if v > limite}
        if not excedidos:
            break
        for i in sorted(out, key=lambda i: i.ev):          # primero la de peor EV
            if i.monto and i.tipo not in ("sencilla", "progresion") and excedidos & set(patas_de.get(i.id, [])):
                i.monto = 0
                i.accion = "VIGILAR"
                i.razon = "Se omite para no cargar demasiado dinero en un mismo partido."
                break

    # Tope diario: reducir en proporción si se pasa
    aparte = {"progresion"} | ({"escalera"} if pol.escalera_fija > 0 else set())
    total = sum(i.monto for i in out if i.tipo not in aparte)
    if total > pol.tope_diario > 0:
        f = pol.tope_diario / total
        for i in out:
            if i.monto and i.tipo not in aparte:
                i.monto = pol.redondear(i.monto * f)
                i.razon += " (ajustado al tope diario)"
    out.sort(key=lambda i: i.hora or "99")
    return out
