"""
PANEL WEB · página estática con el estado del sistema (la sirve Caddy en tu dominio)
===================================================================================
Se regenera cada 10 min en datos/panel/index.html y datos/panel/salud.json.
Protegido con usuario y clave (Caddy basic_auth). Sin JavaScript externo.
"""
from __future__ import annotations

import json
import time

from .. import config
from ..nucleo.formato import cuota, e, fecha_larga, pct, pesos
from . import db
from .sync import ahora

COLOR = {"APOSTAR": "#1f9d55", "VIGILAR": "#c99a06", "NO": "#8a8f98"}


def _curva_svg(curva: list[float], w=640, h=160) -> str:
    if len(curva) < 2:
        return "<p class='m'>Aún sin historial suficiente.</p>"
    lo, hi = min(curva), max(curva)
    rng = (hi - lo) or 1
    pts = " ".join(f"{i * w / (len(curva) - 1):.1f},{h - (v - lo) / rng * (h - 10) - 5:.1f}"
                   for i, v in enumerate(curva))
    base = h - (curva[0] - lo) / rng * (h - 10) - 5
    return (f"<svg viewBox='0 0 {w} {h}' role='img' aria-label='Evolución de la banca'>"
            f"<line x1='0' y1='{base:.1f}' x2='{w}' y2='{base:.1f}' class='b'/>"
            f"<polyline points='{pts}' class='l'/></svg>"
            f"<div class='m'>{pesos(curva[0])} → <b>{pesos(curva[-1])}</b></div>")


def _tarjeta_est(nombre, est):
    if not est or not est.get("n"):
        return f"<div class='c'><h3>{nombre}</h3><p class='m'>Sin jugadas liquidadas.</p></div>"
    ic = est.get("icRoi90")
    filas = "".join(f"<tr><td>{e(k)}</td><td>{d['aciertos']}/{d['n']}</td><td>{pct(d['roi'], True, 1)}</td></tr>"
                    for k, d in (est.get("porTipo") or {}).items())
    cal = "".join(f"<tr><td>{e(t['tramo'])}</td><td>{pct(t['esperado'])}</td><td>{pct(t['real'])}</td><td>{t['n']}</td></tr>"
                  for t in est.get("calibracion") or [])
    return f"""<div class='c'><h3>{nombre}</h3>
<div class='k'><div><b>{est['aciertos']}/{est['n']}</b><span>aciertos (esp. {pct(est['tasaEsperada'])})</span></div>
<div><b>{pct(est['roi'], True, 1)}</b><span>ROI</span></div>
<div><b>{pesos(est['beneficio'], True)}</b><span>beneficio</span></div>
<div><b>{pct(est['maxDrawdown'], dec=1)}</b><span>máx. caída</span></div></div>
<p class='m'>IC 90 % ROI: {pct(ic[0], True, 1) + ' a ' + pct(ic[1], True, 1) if ic else 'faltan datos'} ·
Brier {est['brier']} · p-valor {est['pValor']}</p>
{_curva_svg(est.get('curva') or [])}
<table><tr><th>Tipo</th><th>Aciertos</th><th>ROI</th></tr>{filas}</table>
<table><tr><th>Tramo</th><th>Dicho</th><th>Real</th><th>n</th></tr>{cal}</table></div>"""


def generar(dia: dict) -> None:
    plan = dia.get("plan") or []
    filas_plan = "".join(
        f"<tr><td>{e(i['hora'])}</td><td>{e(i['titulo'])}</td>"
        f"<td><span class='t' style='background:{COLOR[i['accion']]}'>{i['accion']}</span></td>"
        f"<td>{pesos(i['monto']) if i['monto'] else '—'}</td><td>{cuota(i['cuota_min'])}</td>"
        f"<td>{pct(i['ev'], True, 1)}</td><td>{e((db.confirmacion(dia.get('fecha'), i['id']) or {}).get('estado', 'pendiente'))}</td></tr>"
        for i in plan)
    est = dia.get("estadisticas") or {}
    b = dia.get("bancas") or {}
    saldo = db.get("saldo")
    html = f"""<!doctype html><html lang="es"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="300">
<title>Escalera 50K</title><style>
:root{{--bg:#f6f7f9;--fg:#15181d;--m:#5d6470;--c:#fff;--ln:#e3e6ea;--ac:#2563eb}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0f1115;--fg:#e8eaed;--m:#9aa1ab;--c:#181b21;--ln:#2a2f37;--ac:#60a5fa}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}}
main{{max-width:980px;margin:0 auto;padding:16px}}h1{{font-size:22px;margin:4px 0}}h3{{margin:0 0 8px}}
.m{{color:var(--m);font-size:13px}}.g{{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(300px,1fr))}}
.c{{background:var(--c);border:1px solid var(--ln);border-radius:12px;padding:14px;overflow-x:auto}}
.k{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin:8px 0}}.k div{{display:flex;flex-direction:column}}
.k b{{font-size:18px}}.k span{{color:var(--m);font-size:12px}}
table{{width:100%;border-collapse:collapse;margin-top:8px;font-size:13px}}td,th{{text-align:left;padding:6px;border-bottom:1px solid var(--ln)}}
.t{{color:#fff;border-radius:6px;padding:2px 6px;font-size:12px;font-weight:600}}
svg{{width:100%;height:auto}}.l{{fill:none;stroke:var(--ac);stroke-width:2}}.b{{stroke:var(--ln);stroke-dasharray:4}}
</style><main>
<h1>🪜 Escalera 50K</h1><div class="m">{e(fecha_larga(dia['fecha'])) if dia.get('fecha') else 'Sin día publicado'} ·
actualizado {ahora().strftime('%d/%m %H:%M')}</div>
<div class="g" style="margin-top:12px">
<div class="c"><h3>{e((dia.get('veredicto') or {}).get('titulo', ''))}</h3><p>{e((dia.get('veredicto') or {}).get('texto', ''))}</p>
<div class="k"><div><b>{pesos(saldo or b.get('real'))}</b><span>tu banca</span></div>
<div><b>{pesos(b.get('sistema'))}</b><span>sistema</span></div>
<div><b>{pesos(db.apostado(dia.get('fecha', '')))}</b><span>apostado hoy</span></div>
<div><b>{pesos((dia.get('politica') or {}).get('tope'))}</b><span>tope</span></div></div></div>
<div class="c"><h3>Qué hacer hoy</h3><table><tr><th>Hora</th><th>Jugada</th><th>Acción</th><th>Monto</th><th>Mín.</th><th>EV</th><th>Tú</th></tr>{filas_plan}</table></div>
</div><div class="g" style="margin-top:12px">{_tarjeta_est('Sistema (simulado)', est.get('sistema'))}{_tarjeta_est('Tus apuestas reales', est.get('real'))}</div>
<p class="m">Probabilidad no es certeza. Este panel no apuesta ni recomienda más allá del valor esperado.</p></main></html>"""
    (config.PANEL / "index.html").write_text(html, encoding="utf-8")
    salud(ok=True)


def salud(ok=True, nota=""):
    (config.PANEL / "salud.json").write_text(json.dumps({
        "ok": ok, "nota": nota, "latido": ahora().isoformat(timespec="seconds"), "ts": time.time()}), encoding="utf-8")
