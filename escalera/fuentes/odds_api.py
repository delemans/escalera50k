"""
CUOTAS AUTOMÁTICAS · The Odds API (the-odds-api.com)
====================================================
Por qué: los comparadores web (BetExplorer, Oddspedia…) bloquean la lectura
automática y casi todos los días quedaban 5 candidatos con cuotas. Esta API
entrega, con hora oficial de inicio, las cuotas de muchas casas (Pinnacle,
Betfair, Unibet, William Hill, 1xBet, Marathon…) de cientos de ligas.

Plan gratis: 500 créditos/mes. /sports y /events no gastan; cada llamada a
/odds gasta (mercados × regiones). Por defecto: solo las ligas con partidos
en la ventana, mercados h2h,totals, región eu → 2 créditos por liga.

Salida: candidatos en el formato de analisis.evaluar (1X2 del favorito y
goles más/menos 1,5 / 2,5 / 3,5), con "verificado": True porque la hora
viene de la API (y se descartan los que ya empezaron).
"""
from __future__ import annotations

import datetime as dt
import json
import re
import unicodedata
import urllib.parse
import urllib.request

BASE = "https://api.the-odds-api.com/v4"
BOG = dt.timezone(dt.timedelta(hours=-5))


def _get(url: str, timeout=30):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        restante = r.headers.get("x-requests-remaining")
        return json.loads(r.read().decode()), restante


def _iso(t: dt.datetime) -> str:
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def descargar(clave: str, desde: dt.datetime, hasta: dt.datetime, max_ligas: int = 15,
              mercados: str = "h2h,totals", regiones: str = "eu") -> dict:
    """Devuelve {"eventos": [...], "restante": créditos, "ligas": [...]}. Solo fútbol."""
    q = lambda **k: urllib.parse.urlencode({"apiKey": clave, **k})
    deportes, _ = _get(f"{BASE}/sports?{q()}")
    futbol = [d for d in deportes if d.get("key", "").startswith("soccer_") and d.get("active")
              and not d.get("has_outrights")]
    ventana = {"commenceTimeFrom": _iso(desde), "commenceTimeTo": _iso(hasta)}
    con_partidos = []
    for d in futbol:                                     # /events no gasta créditos
        try:
            evs, _ = _get(f"{BASE}/sports/{d['key']}/events?{q(**ventana)}")
        except Exception:
            continue
        if evs:
            con_partidos.append((len(evs), d))
    con_partidos.sort(key=lambda x: -x[0])
    eventos, restante, ligas = [], None, []
    for _, d in con_partidos[:max_ligas]:
        try:
            evs, restante = _get(f"{BASE}/sports/{d['key']}/odds?{q(regions=regiones, markets=mercados, oddsFormat='decimal', **ventana)}")
        except Exception:
            continue
        for e in evs:
            e["liga"] = d.get("title") or d["key"]
        eventos += evs
        ligas.append(d.get("title") or d["key"])
    return {"eventos": eventos, "restante": restante, "ligas": ligas,
            "generado": _iso(dt.datetime.now(dt.timezone.utc))}


def _n(t: str) -> list[str]:
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    t = re.sub(r"\(.*?\)", " ", t)
    t = re.sub(r"[^a-z ]", " ", t)
    return [w for w in t.split() if w not in {"fc", "cf", "cd", "ud", "sc", "ac", "club", "de", "city", "united", "town", "w"}]


def _statarea_de(h: str, a: str, filas: list[dict]) -> dict | None:
    for f in filas or []:
        if set(_n(h)) & set(_n(f.get("home", ""))) and set(_n(a)) & set(_n(f.get("away", ""))):
            return f
    return None


def convertir(datos: dict, statarea: list[dict] | None = None, ahora: dt.datetime | None = None,
              margen_min: int = 20, cuota: tuple = (1.15, 2.10), maximo: int = 80) -> list[dict]:
    """Eventos de la API → candidatos. Solo partidos que empiezan en ≥ margen_min minutos."""
    ahora = ahora or dt.datetime.now(dt.timezone.utc)
    cands = []
    for e in datos.get("eventos", []):
        try:
            ini = dt.datetime.strptime(e["commence_time"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
        except (KeyError, ValueError):
            continue
        if ini < ahora + dt.timedelta(minutes=margen_min):
            continue                                     # ya empezó o está por empezar
        h, a = e.get("home_team", ""), e.get("away_team", "")
        base = {"h": h, "a": a, "lg": e.get("liga", ""), "t": ini.astimezone(BOG).strftime("%H:%M"),
                "fecha": ini.astimezone(BOG).date().isoformat(), "verificado": True,
                "fuente": "the-odds-api", "noticias": "", "alerta": False}
        sa = _statarea_de(h, a, statarea)
        if sa:
            base["statarea"] = sa
        h2h, totales = [], {}
        for b in e.get("bookmakers", []):
            bk = b.get("title") or b.get("key")
            for m in b.get("markets", []):
                if m.get("key") == "h2h":
                    o = {x["name"]: x["price"] for x in m.get("outcomes", [])}
                    if h in o and a in o and "Draw" in o:
                        h2h.append({"bk": bk, "o": [o[h], o["Draw"], o[a]]})
                elif m.get("key") == "totals":
                    por = {}
                    for x in m.get("outcomes", []):
                        por.setdefault(x.get("point"), {})[x["name"]] = x["price"]
                    for pt, o in por.items():
                        if pt in (1.5, 2.5, 3.5) and "Over" in o and "Under" in o:
                            totales.setdefault(pt, []).append({"bk": bk, "o": [o["Over"], o["Under"]]})
        if len(h2h) >= 2:
            prom = [sum(c["o"][i] for c in h2h) / len(h2h) for i in range(3)]
            fav = "1" if prom[0] <= prom[2] else "2"
            o_fav = prom[0] if fav == "1" else prom[2]
            if cuota[0] <= o_fav <= cuota[1]:
                cands.append({**base, "mercado": "1X2", "lado": fav, "casas": h2h})
        for pt, casas in totales.items():
            if len(casas) < 2:
                continue
            for i, lado in enumerate(("over", "under")):
                o_med = sum(c["o"][i] for c in casas) / len(casas)
                if cuota[0] <= o_med <= cuota[1]:
                    cands.append({**base, "mercado": "GOLES", "linea": pt, "lado": lado, "casas": casas})
    # Los de cuota más baja (más probables) primero, con tope para no inflar el registro
    def media(c):
        i = {"1": 0, "2": 2}.get(str(c.get("lado")), 0) if c["mercado"] == "1X2" else (0 if c["lado"] == "over" else 1)
        return sum(x["o"][i] for x in c["casas"]) / len(c["casas"])
    cands.sort(key=media)
    return cands[:maximo]


def ventana_hoy(ahora: dt.datetime | None = None, horas_extra: int = 6) -> tuple[dt.datetime, dt.datetime]:
    """Desde ahora hasta mañana a media mañana (Bogotá): cubre la noche y Asia/Europa temprano."""
    ahora = ahora or dt.datetime.now(dt.timezone.utc)
    fin = ahora.astimezone(BOG).replace(hour=23, minute=59, second=0, microsecond=0) + dt.timedelta(hours=horas_extra)
    return ahora, fin
