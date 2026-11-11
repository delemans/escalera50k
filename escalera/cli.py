"""
CLI · comandos que usa la tarea programada (y tú, para probar)
=============================================================
  python -m escalera.cli candidatos statarea.csv [--ajuste -1] [--desde 12:00] [--max 45] [--sin-api]   → candidatos.json
      (suma solos los candidatos con cuotas reales de The Odds API: ODDS_API_KEY o el bot en Render /cuotas.json)
  python -m escalera.cli analizar entrada.json  [--out salida.json]
  python -m escalera.cli liquidar entrada.json  [--out salida.json]
  python -m escalera.cli informe apuestas.json  [--inicial 90000] [--real]
  python -m escalera.cli tipster dia.json tipster.json apuestas.json [--out t.json]  → sección dia.tipster + filas
  python -m escalera.cli evaluar 0.70 1.45
  python -m escalera.cli riesgo --ev 0.03 --apuestas 2 --stake 0.02 --cuota 1.6
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import analisis as A
from .nucleo import estadisticas as EST
from .nucleo import simulacion as SIM
from .nucleo import tipster as TIP
from .nucleo import validacion as VAL
from .nucleo import valor as V


def _cuotas_api(filas, desde=None):
    """Candidatos con cuotas reales de muchas ligas: The Odds API directo (ODDS_API_KEY) o vía el bot
    en Render (/cuotas.json). Ya traen "casas" y "verificado": no hace falta buscarles cuotas a mano."""
    import os
    import urllib.request
    from .fuentes import odds_api
    datos, nota = None, ""
    clave = os.environ.get("ODDS_API_KEY", "")
    try:
        if clave:
            d0, d1 = odds_api.ventana_hoy()
            datos, nota = odds_api.descargar(clave, d0, d1), "directo"
        else:
            url = os.environ.get("CUOTAS_URL", "https://escalera50k.onrender.com/cuotas.json")
            with urllib.request.urlopen(url, timeout=90) as r:
                datos, nota = json.loads(r.read().decode()), "vía bot"
    except Exception as ex:
        return [], f"no disponibles ({type(ex).__name__})"
    if datos.get("error"):
        return [], datos["error"]
    cands = odds_api.convertir(datos, filas)
    if desde:
        cands = [c for c in cands if c["t"] >= desde or c.get("fecha", "") > odds_api.dt.datetime.now(odds_api.BOG).date().isoformat()]
    return cands, f"{nota} · {len(datos.get('ligas', []))} ligas · créditos restantes {datos.get('restante')}"


def _leer(ruta):
    return json.loads(Path(ruta).read_text(encoding="utf-8"))


def _salida(datos, out):
    txt = json.dumps(datos, ensure_ascii=False, indent=1)
    if out:
        Path(out).write_text(txt, encoding="utf-8")
        print(f"OK → {out}")
    else:
        print(txt)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="escalera")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("candidatos")
    c.add_argument("csv")
    c.add_argument("--ajuste", type=int, default=0, help="horas a sumar a la hora de StatArea")
    c.add_argument("--desde", default="07:30", help="solo partidos desde esta hora (Bogotá), p. ej. 12:00 en un escaneo manual")
    c.add_argument("--max", type=int, default=45)
    c.add_argument("--solo-principales", action="store_true")
    c.add_argument("--sin-api", action="store_true", help="no sumar cuotas automáticas (The Odds API)")
    c.add_argument("--out")
    for nombre in ("analizar", "liquidar"):
        s = sub.add_parser(nombre)
        s.add_argument("entrada")
        s.add_argument("--out")
    i = sub.add_parser("informe")
    i.add_argument("apuestas")
    i.add_argument("--inicial", type=float, default=90000)
    i.add_argument("--real", action="store_true")
    t = sub.add_parser("tipster")
    t.add_argument("dia")
    t.add_argument("picks")
    t.add_argument("apuestas")
    t.add_argument("--out")
    e = sub.add_parser("evaluar")
    e.add_argument("p", type=float)
    e.add_argument("cuota", type=float)
    r = sub.add_parser("riesgo")
    r.add_argument("--ev", type=float, default=0.03)
    r.add_argument("--apuestas", type=int, default=2)
    r.add_argument("--stake", type=float, default=0.02)
    r.add_argument("--cuota", type=float, default=1.6)
    r.add_argument("--dias", type=int, default=60)
    a = ap.parse_args(argv)

    if a.cmd == "candidatos":
        filas, errores = VAL.leer_csv(Path(a.csv).read_text(encoding="utf-8"))
        if a.ajuste:
            VAL.ajustar_hora(filas, a.ajuste)
        cands = A.candidatos_statarea(filas, hora_min=a.desde, maximo=a.max, amplia=not a.solo_principales)
        extra, nota = ([], "sin cuotas automáticas (--sin-api)") if a.sin_api else _cuotas_api(filas, a.desde)
        vistos = {(c["h"], c["a"], c.get("mercado"), str(c.get("lado")), c.get("linea")) for c in cands}
        extra = [c for c in extra if (c["h"], c["a"], c.get("mercado"), str(c.get("lado")), c.get("linea")) not in vistos]
        print(f"Cuotas automáticas: {len(extra)} candidatos con casas y hora verificada · {nota}", file=sys.stderr)
        _salida({"partidos": len(filas), "errores": errores, "validacion": VAL.validar(filas),
                 "cuotasAutomaticas": {"n": len(extra), "nota": nota},
                 "candidatos": cands + extra}, a.out)
    elif a.cmd == "analizar":
        entrada = _leer(a.entrada)
        if entrada.get("statarea_csv", "").endswith(".csv"):
            entrada["statarea_csv"] = Path(entrada["statarea_csv"]).read_text(encoding="utf-8")
        _salida(A.construir_dia(entrada), a.out)
    elif a.cmd == "liquidar":
        entrada = _leer(a.entrada)
        _salida(A.liquidar_filas(entrada["apuestas"], entrada["marcadores"], entrada.get("progresion")), a.out)
    elif a.cmd == "informe":
        datos = _leer(a.apuestas)
        _salida(EST.resumen(datos if isinstance(datos, list) else datos["apuestas"], a.inicial, a.real), None)
    elif a.cmd == "tipster":
        dia, picks, filas = _leer(a.dia), _leer(a.picks), _leer(a.apuestas)
        picks = picks.get("picks", []) if isinstance(picks, dict) else picks
        filas = filas if isinstance(filas, list) else filas.get("apuestas", [])
        ev = TIP.evaluar(dia, picks)
        _salida({"tipster": {**ev, "record": TIP.record(filas)},
                 "filasNuevas": TIP.filas_nuevas(ev["picks"], filas, dia["fecha"])}, a.out)
    elif a.cmd == "evaluar":
        ev = V.evaluar(a.p, a.cuota)
        print(f"EV {ev.ev:+.2%} · mínima {ev.omin:.2f} · justa {ev.justa:.2f} · Kelly {ev.kelly:.2%} · {ev.texto}")
    elif a.cmd == "riesgo":
        _salida(SIM.largo_plazo(a.ev, a.apuestas, a.stake, a.cuota, a.dias), None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
