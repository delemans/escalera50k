from escalera.bot import charla, mensajes as M

DIA = {"plan": [{"id": "x-esc", "tipo": "escalera", "titulo": "Escalera", "accion": "APOSTAR", "monto": 5000,
                 "cuota_ref": 1.53, "cuota_min": 1.62, "hora": "15:30"}],
       "jugadas": {"escalera": {"peldanos": 1, "stake": 5000, "final": 7650, "P": 0.63, "montos": [5000],
                                "patas": [{"t": "15:30", "sel": "Gana Envigado", "partido": "Envigado vs Boca Juniors de Cali", "o": 1.53}],
                                "detalle": [{"sel": "Gana Envigado", "razones": ["Probabilidad 62,9 %."], "enContra": []}]},
                   "reserva": [{"n": 1, "tipo": "escalera", "cuota": 1.36, "omin": 1.41, "P": 0.72,
                                "patas": [{"t": "15:00", "sel": "Gana Manchester City W", "partido": "Inter W vs Manchester City W"}]}]},
       "bancas": {"real": 114255, "sistema": 109395}}


def test_intenciones():
    assert charla.intencion("hola parce") == "saludo"
    assert charla.intencion("me pagan 1,65 por envigado") == "cuota"
    assert charla.intencion("¿cómo voy?") == "resultados"
    assert charla.intencion("qué apuesto hoy") == "plan"


def test_cuota_sirve_y_no_sirve():
    assert "Sí sirve" in charla.responder("me pagan 1,65 por Envigado", DIA)
    assert "No sirve" in charla.responder("está a 1.55 envigado", DIA)
    assert "Respaldo 1" in charla.responder("y el city a 1,30?", DIA)


def test_resultados_ordenados():
    reg = [{"fecha": "2026-11-09", "sel": "Gana A", "cuota": 1.5, "valor": 2000, "estado": "perdida"},
           {"fecha": "2026-11-10", "sel": "Gana B", "cuota": 1.5, "valor": 2000, "estado": "ganada"},
           {"fecha": "2026-11-10", "sel": "Gana C", "cuota": 1.4, "valor": 1000, "estado": "pendiente"}]
    txt = M.resultados(reg)
    assert "✅ 1" in txt and "❌ 1" in txt and "⏳ 1" in txt
    assert txt.index("10 nov") < txt.index("9 nov")          # lo más reciente primero
    assert "Neto" in txt


def test_nunca_falla():
    assert charla.responder("asdf qwer", {})
    assert charla.responder("hola", {})
