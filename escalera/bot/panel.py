"""
APP WEB · panel para el celular (se abre desde el bot como mini app de Telegram)
===============================================================================
Se regenera cada 10 min y con cada día nuevo en datos/panel/index.html.
Acceso: con el botón 📱 del bot (enlace firmado, sin clave) o con usuario/clave
(PANEL_USUARIO / PANEL_CLAVE). Una sola columna, botones grandes, modo oscuro,
sin JavaScript externo.

Secciones: Hoy · Boletos para BetPlay · Tus apuestas · Escalera · Prueba de
sistemas · Métricas · Curva de banca
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from .. import config
from ..nucleo.formato import cuota, e, fecha_larga, pct, pesos
from . import db
from .sync import ahora

COLOR = {"APOSTAR": "#1f9d55", "VIGILAR": "#c99a06", "NO": "#8a8f98"}
TXT = {"APOSTAR": "APOSTAR", "VIGILAR": "VIGILAR", "NO": "NO APOSTAR"}
NOMBRE = {"sencilla": "Individual", "escalera": "Escalera 3 peldaños", "combinada": "Combinada de valor",
          "super": "Soñadora 100+", "progresion": "Escalera de crecimiento"}
ICONO = {"sencilla": "🎯", "escalera": "🪜", "combinada": "🔗", "super": "🌙", "progresion": "📈"}


# ---------------------------------------------------------------------------
# Enlace firmado para abrir la app desde Telegram sin escribir clave
# ---------------------------------------------------------------------------
def _firma(chat, exp) -> str:
    return hmac.new(("app:" + config.TOKEN_BOT).encode(), f"{chat}:{exp}".encode(), hashlib.sha256).hexdigest()[:32]


def token_app(chat, dias: int = 30) -> str:
    exp = int(time.time()) + dias * 86400
    return base64.urlsafe_b64encode(f"{chat}:{exp}:{_firma(chat, exp)}".encode()).decode().rstrip("=")


def token_valido(t: str | None) -> bool:
    if not t:
        return False
    try:
        crudo = base64.urlsafe_b64decode(t + "=" * (-len(t) % 4)).decode()
        chat, exp, firma = crudo.split(":")
        return int(exp) > time.time() and hmac.compare_digest(firma, _firma(chat, int(exp)))
    except Exception:
        return False


def url_app(chat) -> str | None:
    base = (config.URL_PUBLICA or (f"https://{config.DOMINIO}" if config.DOMINIO else "")).rstrip("/")
    return f"{base}/app?t={token_app(chat)}" if base else None


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------
def _curva_svg(curva: list[float], w=640, h=150) -> str:
    if len(curva) < 2:
        return "<p class='m'>La curva aparece cuando haya jugadas liquidadas.</p>"
    lo, hi = min(curva), max(curva)
    rng = (hi - lo) or 1
    pts = " ".join(f"{i * w / (len(curva) - 1):.1f},{h - (v - lo) / rng * (h - 10) - 5:.1f}" for i, v in enumerate(curva))
    base = h - (curva[0] - lo) / rng * (h - 10) - 5
    return (f"<svg viewBox='0 0 {w} {h}' role='img' aria-label='Evolución de la banca'>"
            f"<line x1='0' y1='{base:.1f}' x2='{w}' y2='{base:.1f}' class='b'/><polyline points='{pts}' class='l'/></svg>"
            f"<div class='m'>{pesos(curva[0])} → <b>{pesos(curva[-1])}</b></div>")


def _kpi(valor, etiqueta):
    return f"<div class='k'><b>{valor}</b><span>{e(etiqueta)}</span></div>"


def _boleto(dia, i, n):
    picks = {p["id"]: p for p in dia.get("picks", []) if p.get("id")}
    jug = dia.get("jugadas") or {}
    if i["tipo"] == "sencilla":
        p = picks.get(i["id"], {})
        patas = [{"partido": f"{p.get('h')} vs {p.get('a')}", "sel": p.get("sel"), "o": p.get("o"),
                  "t": p.get("t"), "lg": p.get("lg"), "mercado": p.get("mercado")}]
    else:
        patas = (jug.get(i["tipo"]) or {}).get("patas", [])
    estado = (db.confirmacion(dia.get("fecha"), i["id"]) or {}).get("estado", "pendiente")
    marca = {"si": "✅ hecha", "no": "❌ no la hiciste"}.get(estado, "")
    filas = "".join(
        f"<li><b>{e(x.get('t'))}</b> · {e(x.get('partido'))}<br><span class='m'>{e(x.get('lg') or '')}</span>"
        f"<div class='sel'>{e(x.get('sel'))} <span class='m'>@ {cuota(x.get('o'))}</span></div></li>" for x in patas)
    monto = f"{pesos(i['monto'])}" if i["monto"] else "—"
    return f"""<div class='c'>
<div class='row'><span class='t' style='background:{COLOR[i["accion"]]}'>{TXT[i["accion"]]}</span>
<span class='m'>{ICONO.get(i['tipo'], '')} {e(NOMBRE.get(i['tipo'], ''))} · #{n}</span><span class='m'>{marca}</span></div>
<h3>{e(i['titulo'])}</h3>
<ol class='pat'>{filas}</ol>
<div class='g3'>{_kpi(monto, 'monto')}{_kpi(cuota(i['cuota_min']), 'mínima BetPlay')}{_kpi(pct(i['ev'], True, 1), 'EV')}</div>
<p class='m'>{e(i['razon'])}</p></div>"""


def _sistemas(est):
    pt = (est or {}).get("porTipo") or {}
    if not pt:
        return "<p class='m'>Aún sin jugadas liquidadas.</p>"
    return "".join(f"<div class='rowb'><span>{ICONO.get(k, '•')} {e(NOMBRE.get(k, k))}</span>"
                   f"<span>{d['aciertos']}/{d['n']} · <b>{pct(d['roi'], True, 1)}</b></span></div>" for k, d in pt.items())


def _metricas(est):
    if not est or not est.get("n"):
        return "<p class='m'>Aún sin jugadas liquidadas.</p>"
    ic = est.get("icRoi90")
    aciertos = f"{est['aciertos']}/{est['n']}"
    return (f"<div class='g3'>{_kpi(aciertos, 'aciertos')}"
            f"{_kpi(pct(est['roi'], True, 1), 'ROI')}{_kpi(pesos(est['beneficio'], True), 'beneficio')}</div>"
            f"<p class='m'>Esperado {pct(est['tasaEsperada'])} · real {pct(est['tasa'])} · p-valor {est['pValor']} · "
            f"Brier {est['brier']} · máx. caída {pct(est['maxDrawdown'], dec=1)}"
            + (f" · IC 90 % ROI {pct(ic[0], True, 1)} a {pct(ic[1], True, 1)}" if ic else "") + "</p>"
            + _curva_svg(est.get("curva") or []))


def generar(dia: dict) -> None:
    b = dia.get("bancas") or {}
    v = dia.get("veredicto") or {}
    est = dia.get("estadisticas") or {}
    pr = dia.get("progresionCfg") or {}
    ec = dia.get("escaleraCrec") or {}
    rg = dia.get("riesgo") or {}
    plan = dia.get("plan") or []
    orden = {"sencilla": 0, "combinada": 1, "super": 2, "progresion": 3, "escalera": 4}
    boletos = "".join(_boleto(dia, i, n) for n, i in enumerate(sorted(plan, key=lambda i: (orden.get(i["tipo"], 9), i["hora"])), 1)) \
        or "<p class='m'>Hoy no hay boletos. El plan llega hacia las 07:00.</p>"
    mias = "".join(
        f"<div class='rowb'><span>{ {'ganado': '✅', 'perdido': '❌', 'nulo': '➖'}.get(m.get('resultado'), '⏳') } "
        f"{e(m.get('hora') or '')} · {e(m.get('partido'))}<br><span class='m'>{e(m.get('seleccion'))} @ {cuota(m.get('cuotaReal'))}</span></span>"
        f"<span><b>{pesos(m.get('netoReal'), True) if m.get('netoReal') is not None else pesos(m.get('stakeReal'))}</b></span></div>"
        for m in dia.get("misApuestas") or []) or "<p class='m'>Sin apuestas registradas hoy.</p>"
    escalera = (f"<div class='g3'>{_kpi(pesos(pr.get('saldo')), 'saldo')}{_kpi(pr.get('paso', 1), 'peldaño')}"
                f"{_kpi(pesos(pr.get('meta')), 'meta')}</div>"
                + (f"<p>🛡 Modo seguro: apuesta <b>{pesos(ec.get('stake'))}</b> y aparta {pesos(ec.get('asegurado'))}.</p>"
                   if ec.get("asegurado") else "")) if pr else "<p class='m'>Sin escalera activa.</p>"
    html = f"""<!doctype html><html lang="es"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta http-equiv="refresh" content="300">
<meta name="theme-color" content="#0f1115"><title>Escalera 50K</title><style>
:root{{--bg:#f4f5f7;--fg:#14171c;--m:#5d6470;--c:#fff;--ln:#e3e6ea;--ac:#2563eb}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0f1115;--fg:#e8eaed;--m:#9aa1ab;--c:#181b21;--ln:#2a2f37;--ac:#60a5fa}}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.45 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}}
main{{max-width:640px;margin:0 auto;padding:12px 14px 40px}}header{{position:sticky;top:0;background:var(--bg);padding:10px 0 8px;z-index:2}}
h1{{font-size:20px;margin:0}}h2{{font-size:15px;text-transform:uppercase;letter-spacing:.04em;color:var(--m);margin:22px 2px 8px}}
h3{{margin:6px 0 8px;font-size:17px}}.m{{color:var(--m);font-size:13px}}
.c{{background:var(--c);border:1px solid var(--ln);border-radius:14px;padding:14px;margin:0 0 10px}}
.g3{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:8px 0}}.k{{display:flex;flex-direction:column}}
.k b{{font-size:17px}}.k span{{color:var(--m);font-size:12px}}.t{{color:#fff;border-radius:8px;padding:3px 8px;font-size:12px;font-weight:700}}
.row{{display:flex;gap:8px;align-items:center;justify-content:space-between;flex-wrap:wrap}}
.rowb{{display:flex;justify-content:space-between;gap:10px;padding:9px 0;border-bottom:1px solid var(--ln)}}
.pat{{margin:0;padding-left:20px}}.pat li{{margin:0 0 8px}}.sel{{font-weight:600}}
nav{{display:flex;gap:6px;overflow-x:auto;padding:4px 0}}nav a{{flex:none;color:var(--fg);text-decoration:none;border:1px solid var(--ln);
border-radius:999px;padding:6px 12px;font-size:13px;background:var(--c)}}svg{{width:100%;height:auto}}
.l{{fill:none;stroke:var(--ac);stroke-width:2.5}}.b{{stroke:var(--ln);stroke-dasharray:4}}
</style><main>
<header><h1>🪜 Escalera 50K</h1><div class="m">{e(fecha_larga(dia['fecha'])) if dia.get('fecha') else 'Sin día publicado'} · {ahora().strftime('%H:%M')}</div>
<nav><a href="#hoy">Hoy</a><a href="#boletos">Boletos</a><a href="#mias">Mis apuestas</a><a href="#escalera">Escalera</a><a href="#sistemas">Sistemas</a><a href="#metricas">Métricas</a></nav></header>
<h2 id="hoy">Hoy</h2><div class="c"><h3>{e(v.get('titulo', ''))}</h3><p>{e(v.get('texto', ''))}</p>
<div class="g3">{_kpi(pesos(db.get('saldo') or b.get('real')), 'tu banca')}{_kpi(pesos((dia.get('politica') or {}).get('unidad')), 'unidad')}{_kpi(pesos((dia.get('politica') or {}).get('tope')), 'tope del día')}</div>
<p class="m">Riesgo: {e((rg.get('estado') or 'normal').upper())} · hoy {pesos(rg.get('netoHoy'), True)} · 7 días {pesos(rg.get('neto7d'), True)}</p></div>
<h2 id="boletos">Boletos para BetPlay</h2><p class="m">Búscalos en BetPlay tal cual: partido → mercado → selección. Pon el monto y apuesta solo si la cuota es ≥ la mínima.</p>{boletos}
<h2 id="mias">Tus apuestas</h2><div class="c">{mias}</div>
<h2 id="escalera">Escalera de crecimiento</h2><div class="c">{escalera}</div>
<h2 id="sistemas">Prueba de sistemas (simulado)</h2><div class="c">{_sistemas(est.get('sistema'))}</div>
<h2 id="metricas">Métricas</h2><div class="c"><h3>Tus apuestas reales</h3>{_metricas(est.get('real'))}</div>
<div class="c"><h3>Sistema (simulado)</h3>{_metricas(est.get('sistema'))}</div>
<p class="m">Probabilidad no es certeza. Juega solo lo que puedas perder · +18.</p></main></html>"""
    (config.PANEL / "index.html").write_text(html, encoding="utf-8")
    salud(ok=True)


def salud(ok=True, nota=""):
    (config.PANEL / "salud.json").write_text(json.dumps({
        "ok": ok, "nota": nota, "latido": ahora().isoformat(timespec="seconds"), "ts": time.time()}), encoding="utf-8")
