"""Genera ejemplos/vista_previa.html: los mensajes del bot como burbujas de chat.
Uso: python ejemplos/vista_previa.py"""
import json
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
os.environ.setdefault("DATOS_DIR", tempfile.mkdtemp())
os.environ.setdefault("ENV_FILE", "/nonexistent")
from escalera import analisis as A  # noqa: E402
from escalera.bot import mensajes as M  # noqa: E402

entrada = json.loads((RAIZ / "ejemplos/entrada_ejemplo.json").read_text(encoding="utf-8"))
entrada["statarea_csv"] = (RAIZ / "ejemplos/statarea_ejemplo.csv").read_text(encoding="utf-8")
entrada["candidatos"][0]["casas"].append({"bk": "Mejor", "o": [1.40, 6.0, 9.0]})
entrada["candidatos"][1]["casas"].append({"bk": "Mejor", "o": [2.05, 3.4, 4.0]})
dia = A.construir_dia(entrada)["dia"]
dia["bancas"].update(varReal=0, varSistema=2500)

burbujas = [("bot", M.resumen(dia), None), ("bot", M.plan(dia), None)]
for i in dia["plan"][:4]:
    burbujas.append(("bot", M.tarjeta(dia, i), M.botones_tarjeta(i["id"])))
p0 = dia["plan"][0]
burbujas += [
    ("yo", "BetPlay paga 1,38 la 1", None),
    ("bot", M.decision_betplay(p0, 1.38, "APOSTAR", 2000, 0.045), None),
    ("bot", M.recordatorio({"t": p0["hora"], "partido": "Bayern Múnich vs Mainz", "sel": "Gana Bayern Múnich",
                            "omin": p0["cuota_min"]}, 15, [("APOSTAR", "1 · Gana Bayern Múnich", 2000),
                                                            ("VIGILAR", "Escalera · pierna 1", None)]), None),
    ("bot", M.preguntar(p0), M.botones_tarjeta(p0["id"])),
    ("yo", "✅ La hice", None),
    ("bot", M.pedir_detalle(p0), [[{"text": f"Usé mínima {M.cuota(p0['cuota_min'])} · {M.pesos(p0['monto'])}"}]]),
    ("yo", "1,38 2000", None),
    ("bot", M.registrado(p0["titulo"], 1.38, 2000, []), None),
    ("yo", "📸 [pantallazo de una apuesta propia]", None),
    ("bot", M.confirmar_registro([{"accion": "propia", "partido": "Junior vs Millonarios", "sel": "Gana Junior",
                                   "cuota": 2.10, "valor": 5000, "estado": "abierta",
                                   "avisos": ["Stake de $5.000: más de 2 unidades ($4.000)."]}]),
     [[{"text": "✅ Confirmar"}, {"text": "🗑 Descartar"}]]),
    ("bot", M.alerta("rojo", "Tope diario superado", "Llevas $13.000 apostados hoy; el tope es $12.000.",
                     "Lo sano es parar por hoy."), None),
    ("bot", M.simulacion(dia["simulacion"]), None),
]
css = """body{margin:0;background:#cfd9c6;font:15px/1.38 -apple-system,Segoe UI,Roboto,sans-serif}
.h{background:#517da2;color:#fff;padding:12px 16px;font-weight:600}.c{max-width:420px;margin:0 auto;padding:12px 10px}
.b{background:#fff;border-radius:14px 14px 14px 4px;padding:9px 12px;margin:0 36px 8px 0;white-space:pre-wrap;box-shadow:0 1px 1px #0002}
.y{background:#e1fec6;border-radius:14px 14px 4px 14px;margin:0 0 8px 70px}
.k{display:grid;gap:5px;margin:-3px 36px 12px 0}.r{display:flex;gap:5px}.r span{flex:1;text-align:center;background:#0004;color:#fff;border-radius:8px;padding:7px;font-size:13.5px}
a{color:#168acd;text-decoration:none}code{background:#eef;padding:0 3px;border-radius:3px}"""
html = [f"<!doctype html><meta charset='utf-8'><style>{css}</style><div class='h'>🪜 Escalera 50K · bot</div><div class='c'>"]
for quien, txt, bot in burbujas:
    html.append(f"<div class='b{' y' if quien == 'yo' else ''}'>{txt}</div>")
    if bot:
        html.append("<div class='k'>" + "".join("<div class='r'>" + "".join(f"<span>{b['text']}</span>" for b in fila)
                                                + "</div>" for fila in bot) + "</div>")
html.append("</div>")
(RAIZ / "ejemplos/vista_previa.html").write_text("".join(html), encoding="utf-8")
print("Listo: ejemplos/vista_previa.html")
