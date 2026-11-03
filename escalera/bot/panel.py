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
from ..nucleo.formato import cuota, e, pct, pesos
from . import db
from .logo import LOGO
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
    return f"{base}/app?t={token_app(chat)}&v={int(time.time()) // 3600}" if base else None


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
    color = {"sencilla": "var(--c-v2)", "escalera": "var(--c-esc)", "combinada": "var(--c-comb)",
             "super": "var(--c-sue)", "progresion": "var(--accent)"}.get(i["tipo"], "var(--accent)")
    return f"""<div class='c' style='--tipo:{color}'>
<div class='row'><span class='t' style='background:{COLOR[i["accion"]]}'>{TXT[i["accion"]]}</span>
<span class='m' style='color:{color};font-weight:700'>{ICONO.get(i['tipo'], '')} {e(NOMBRE.get(i['tipo'], '')).upper()} · #{n}</span><span class='m'>{marca}</span></div>
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
    picks_ok = [p for p in dia.get("picks", []) if p.get("id")]
    con_valor = sum(1 for i in plan if i["accion"] == "APOSTAR")
    import datetime as _dt
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
             "noviembre", "diciembre"]
    if dia.get("fecha"):
        d = _dt.date.fromisoformat(dia["fecha"])
        ceja = f"Picks del {dias[d.weekday()]}, {d.day} de {meses[d.month - 1]}"
    else:
        ceja = "Esperando el análisis de la mañana"
    mensaje = v.get("texto") or "Ahora no hay apuestas con valor. No apostar también cuida tu bank. El próximo análisis llega hacia las 07:00."
    html = f"""<!doctype html><html lang="es"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta http-equiv="refresh" content="300">
<title>DCBET · DC Tecnology</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Montserrat:wght@700;800;900&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;700&display=swap">
<style>
:root{{--bg:#F5F4F4;--surface:#FFFFFF;--surface-2:#F0EEEE;--ink:#121214;--muted:#5C5C66;--line:#E3E0E0;
--c-esc:#D90000;--c-v2:#0A8F5F;--c-sue:#1F6FD6;--c-comb:#7A3FD9;--accent:#E00000;--accent-soft:rgba(224,0,0,.08);
--ok:#0A8F5F;--ok-soft:rgba(10,143,95,.1);--warn:#B37A00;--warn-soft:rgba(255,190,60,.18);--risk:#FF6B6B;--info:#9AA4B8;
--glow:radial-gradient(60% 90% at 100% 0%,rgba(255,0,0,.10),transparent 60%);--shadow:0 18px 40px -28px rgba(0,0,0,.35);
--f-display:"Montserrat","Segoe UI",system-ui,sans-serif;--f-body:"Inter","Segoe UI",system-ui,sans-serif;
--f-mono:"JetBrains Mono",ui-monospace,Consolas,monospace;--radius:16px;color-scheme:light}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 var(--f-body);-webkit-font-smoothing:antialiased}}
h1,h2,h3{{font-family:var(--f-display);margin:0;line-height:1.12}}h1{{font-size:clamp(1.7rem,7vw,2.4rem);font-weight:900;letter-spacing:-.02em}}
h1 span{{color:var(--accent)}}h2{{font-size:1.05rem;font-weight:800;letter-spacing:-.01em}}h3{{font-size:1rem;font-weight:800}}
.wrap{{max-width:680px;margin:0 auto;padding:0 14px 40px}}.top{{position:sticky;top:0;z-index:5;background:var(--bg);padding:12px 0 6px}}
.bar{{display:flex;align-items:center;gap:11px}}.logo{{width:42px;height:42px;border-radius:11px;background:#FF0000;overflow:hidden;box-shadow:0 8px 22px -10px var(--accent)}}.logo img{{width:100%;height:100%;object-fit:cover;display:block}}.marca{{font:800 1.15rem var(--f-display)}}
.estado{{margin-left:auto;display:inline-flex;align-items:center;gap:7px;font:600 .72rem/1 var(--f-body);padding:7px 10px;border-radius:99px;
border:1px solid var(--line);background:var(--surface);color:var(--ok);white-space:nowrap}}.estado i{{width:8px;height:8px;border-radius:99px;background:var(--ok)}}
.tabs{{display:flex;gap:4px;overflow-x:auto;padding:10px 0 4px;scrollbar-width:none}}.tabs::-webkit-scrollbar{{display:none}}
.tabs a{{color:var(--muted);text-decoration:none;font:600 .84rem/1 var(--f-body);padding:9px 13px;border-radius:10px;white-space:nowrap;border:1px solid transparent}}
.tabs a.on{{background:var(--accent);color:#fff;box-shadow:0 8px 20px -12px var(--accent)}}
.mod{{background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow);padding:18px;margin:14px 0}}
.hero{{background-image:var(--glow)}}.ceja{{font:800 .7rem/1.2 var(--f-display);letter-spacing:.12em;text-transform:uppercase;color:var(--accent);margin-bottom:6px}}
.msg{{margin:14px 0;padding:12px 14px;border-radius:12px;background:var(--warn-soft);border:1px solid color-mix(in srgb,var(--warn) 35%,transparent);font-size:1.02rem}}
.kpis{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}}.kh{{display:grid;gap:2px;padding:10px 12px;border-radius:12px;
background:var(--surface-2);border:1px solid var(--line)}}.kh b{{font:700 1.35rem/1 var(--f-mono)}}.kh span{{font-size:.72rem;color:var(--muted)}}.kh.si b{{color:var(--ok)}}
.sec{{font:800 .78rem var(--f-display);letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin:24px 2px 0}}
.m{{color:var(--muted);font-size:.82rem}}.t{{color:#fff;border-radius:8px;padding:4px 9px;font:700 .7rem var(--f-body);letter-spacing:.04em}}
.row{{display:flex;gap:8px;align-items:center;justify-content:space-between;flex-wrap:wrap}}
.rowb{{display:flex;justify-content:space-between;gap:10px;padding:10px 0;border-bottom:1px solid var(--line)}}.rowb:last-child{{border:0}}
.pat{{margin:6px 0 0;padding-left:20px}}.pat li{{margin:0 0 10px}}.sel{{font:800 1.05rem/1.2 var(--f-display)}}
.c{{background:var(--surface);border:1px solid var(--line);border-left:4px solid var(--tipo,var(--accent));border-radius:var(--radius);box-shadow:var(--shadow);padding:16px;margin:12px 0}}
.g3{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:10px 0}}.k{{display:grid;gap:2px;padding:8px 10px;border-radius:10px;background:var(--surface-2)}}
.k b{{font:700 1.05rem/1 var(--f-mono)}}.k span{{color:var(--muted);font-size:.7rem}}
svg{{width:100%;height:auto}}.l{{fill:none;stroke:var(--accent);stroke-width:2.5}}.b{{stroke:var(--line);stroke-dasharray:4}}
.pie{{text-align:center;color:var(--muted);font-size:.75rem;margin-top:24px}}
</style><div class="wrap">
<div class="top"><div class="bar"><div class="logo"><img src="{LOGO}" alt="DC Tecnology"></div><div class="marca">DCBET</div>
<span class="estado"><i></i>Conectado · {ahora().strftime('%I:%M %p').lower().lstrip('0')}</span></div>
<nav class="tabs"><a class="on" href="#hoy">🏠 Hoy</a><a href="#boletos">🎟 Boletos</a><a href="#mias">🧾 Mis apuestas</a>
<a href="#escalera">📈 Escalera</a><a href="#sistemas">🧪 Laboratorio</a><a href="#metricas">📊 Rendimiento</a></nav></div>
<section id="hoy" class="mod hero"><div class="ceja">{e(ceja)}</div><h1>Tus picks de <span>hoy</span></h1>
<div class="msg">{e(mensaje)}</div>
<div class="kpis"><div class="kh"><b>{dia.get('partidos', 0)}</b><span>partidos revisados</span></div>
<div class="kh"><b>{len(dia.get('picks') or [])}</b><span>con cuotas</span></div>
<div class="kh si"><b>{con_valor}</b><span>con valor</span></div>
<div class="kh"><b>{pr.get('paso', 0) if pr else 0}</b><span>peldaño actual</span></div></div>
<div class="g3">{_kpi(pesos(db.get('saldo') or b.get('real')), 'tu banca')}{_kpi(pesos((dia.get('politica') or {}).get('unidad')), 'unidad')}{_kpi(pesos((dia.get('politica') or {}).get('tope')), 'tope del día')}</div>
<p class="m">Riesgo {e((rg.get('estado') or 'normal').upper())} · hoy {pesos(rg.get('netoHoy'), True)} · 7 días {pesos(rg.get('neto7d'), True)} · {len(picks_ok)} picks en el plan</p></section>
<div class="sec" id="boletos">🎟 Boletos para BetPlay</div><p class="m">Búscalos tal cual: partido → mercado → selección. Apuesta solo si la cuota es ≥ la mínima.</p>{boletos}
<div class="sec" id="mias">🧾 Tus apuestas</div><div class="mod">{mias}</div>
<div class="sec" id="escalera">📈 Escalera de crecimiento</div><div class="mod">{escalera}</div>
<div class="sec" id="sistemas">🧪 Laboratorio · prueba de sistemas</div><div class="mod">{_sistemas(est.get('sistema'))}</div>
<div class="sec" id="metricas">📊 Rendimiento</div><div class="mod"><h3>Tus apuestas reales</h3>{_metricas(est.get('real'))}</div>
<div class="mod"><h3>Sistema (simulado)</h3>{_metricas(est.get('sistema'))}</div>
<p class="pie">DCBET · DC Tecnology · <a href="{e(config.SITIO)}" style="color:inherit">sitio</a> · Probabilidad no es certeza · +18</p></div></html>"""
    (config.PANEL / "index.html").write_text(html, encoding="utf-8")
    salud(ok=True)


def salud(ok=True, nota=""):
    (config.PANEL / "salud.json").write_text(json.dumps({
        "ok": ok, "nota": nota, "latido": ahora().isoformat(timespec="seconds"), "ts": time.time()}), encoding="utf-8")
