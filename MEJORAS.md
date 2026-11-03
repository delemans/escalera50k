# 100 mejoras de la v2

Cada mejora dice en qué archivo está, para que puedas revisarla.

## A. Estilo y experiencia (50)

| # | Mejora | Dónde |
|---|---|---|
| 1 | Íconos fijos por concepto (🟢🟡⚪, 🎯🪜📈🔗🚀, ✅❌➖) en todos los mensajes | `bot/mensajes.py` |
| 2 | Cada tarjeta empieza por lo que debes HACER y el monto | `mensajes.tarjeta` |
| 3 | Mensaje nuevo «📋 QUÉ HACER HOY»: una línea por jugada | `mensajes.plan` |
| 4 | Una tarjeta por jugada en vez de un bloque largo | `app.enviar_dia` |
| 5 | Botones ✅ La hice · ❌ No la hice · 💬 ¿Cuánto paga BetPlay? | `mensajes.botones_tarjeta` |
| 6 | El botón cambia a «✅ Registrada · cambiar» al responder | `app._refrescar_tarjeta` |
| 7 | Botón rápido «Usé mínima · monto sugerido» | `app.boton` |
| 8 | Ejemplo de respuesta en código: `1,42 3000` | `mensajes.pedir_detalle` |
| 9 | Pesos con punto de miles ($12.000) | `nucleo/formato.py` |
| 10 | Coma decimal en cuotas y porcentajes | `formato.cuota/pct` |
| 11 | Signo «−» tipográfico en negativos | `formato` |
| 12 | Fecha corta «Sábado 7 nov» en títulos | `formato.fecha_corta` |
| 13 | Fecha larga en el sitio y el panel | `formato.fecha_larga` |
| 14 | Separador visual fijo en todos los mensajes | `mensajes.LINEA` |
| 15 | Barras ▰▱ para la progresión y el tope diario | `formato.barra` |
| 16 | Las alertas rojas salen arriba del resumen | `mensajes.resumen` |
| 17 | Cuatro niveles de alerta con color propio | `bot/alertas.py` |
| 18 | Cada alerta trae «👉 qué hacer» | `mensajes.alerta` |
| 19 | Un solo recordatorio por partido (antes podían llegar 3) | `alertas.pendientes` |
| 20 | El recordatorio dice cada jugada que usa ese partido y su monto | `mensajes.recordatorio` |
| 21 | Pregunta «❓ ¿Hiciste esta?» con botones cuando empieza el partido | `mensajes.preguntar` |
| 22 | «🧾 Esto entendí» antes de guardar cualquier registro | `mensajes.confirmar_registro` |
| 23 | Avisos ⚠️ dentro de la confirmación (cuota baja, tope, stake) | `alertas.avisos_de_registro` |
| 24 | Mensaje «✅ Registrada» con la cuota y el valor | `mensajes.registrado` |
| 25 | Respuesta final con la cuota de BetPlay: «🟢 APUESTA $x» o «⚪ NO APUESTES» | `mensajes.decision_betplay` |
| 26 | Escalera con el monto de cada peldaño | `mensajes._cuerpo_escalera` |
| 27 | Aviso cuando los montos son solo de la simulación | `_cuerpo_escalera` |
| 28 | La súper siempre lleva el aviso de alto riesgo | `_cuerpo_multi` |
| 29 | Progresión con reto, paso, barra y probabilidad de llegar a la meta | `_cuerpo_progresion` |
| 30 | Transparencia: número de casas, StatArea frente al mercado | `_cuerpo_sencilla` |
| 31 | Noticia en cursiva y con su fuente | `_cuerpo_sencilla` |
| 32 | La razón de cada decisión en una línea | `staking.Instruccion.razon` |
| 33 | /stats: aciertos frente a lo esperado, beneficio y ROI | `mensajes.estadisticas` |
| 34 | El p-valor explicado en palabras («aún no se distingue del azar») | `mensajes.estadisticas` |
| 35 | Tabla de calibración por tramos de probabilidad | `mensajes.estadisticas` |
| 36 | /riesgo: la simulación del día en lenguaje sencillo | `mensajes.simulacion` |
| 37 | La actualización de la tarde/noche solo trae lo nuevo | `mensajes.actualizacion` |
| 38 | Cierre del día a las 22:30 con lo pendiente | `alertas.pendientes` |
| 39 | /ayuda reorganizada por formas de uso | `mensajes.ayuda` |
| 40 | /metodo en 7 pasos | `mensajes.metodo` |
| 41 | Menú de comandos de Telegram con descripciones | `app.main` |
| 42 | Las tarjetas llegan sin sonido para no saturar | `app.enviar_dia` |
| 43 | Los mensajes largos se parten por párrafos, nunca a mitad de línea | `bot/telegram.partir` |
| 44 | Si el HTML falla, se reenvía en texto plano | `telegram.llamar` |
| 45 | Todo texto externo se escapa (equipos, noticias, IA) | `formato.e` |
| 46 | Panel web adaptable al celular y con modo oscuro | `bot/panel.py` |
| 47 | El panel muestra el plan de hoy y lo que confirmaste | `panel.generar` |
| 48 | Curva de la banca dibujada en SVG, sin JavaScript | `panel._curva_svg` |
| 49 | KPIs en el panel: banca, sistema, apostado y tope | `panel.generar` |
| 50 | Vista previa de los mensajes sin Telegram | `ejemplos/vista_previa.py` |

## B. Flujo, cuentas y estadística (50)

| # | Mejora | Dónde |
|---|---|---|
| 51 | Las cuentas las hace código con pruebas, no el modelo de lenguaje | `escalera/analisis.py`, `cli.py` |
| 52 | Tres métodos para quitar el margen: multiplicativo, potencia y Shin | `nucleo/probabilidad.py` |
| 53 | Consenso entre casas, con su dispersión | `probabilidad.consenso` |
| 54 | Se descarta el partido si las casas difieren más de 4 pts | `analisis.evaluar` |
| 55 | Se ignoran las casas con cuotas inválidas | `probabilidad.validar_cuotas` |
| 56 | El método de potencia está probado contra scipy | `tests/test_nucleo.py` |
| 57 | El CSV de StatArea tolera filas rotas y duplicadas | `nucleo/validacion.leer_csv` |
| 58 | El ajuste de hora es un parámetro, no una regla fija | `validacion.ajustar_hora` |
| 59 | La validación de StatArea admite ±1 de redondeo | `validacion.validar` |
| 60 | Filtro automático de ligas principales (excluye reservas, femenino, Challenge Cup…) | `analisis.liga_principal` |
| 61 | Selección de jugadas determinista: mismos datos, mismas jugadas | `nucleo/jugadas.py` |
| 62 | Escalera: prueba todos los tríos con 2 h de separación y avisa si no hay | `jugadas.escalera` |
| 63 | Combinada y súper: búsqueda completa que maximiza P·cuota con partidos distintos | `jugadas._mejor_multi` |
| 64 | La unidad es el 2 % de tu banca real ($2.000 con $100.000) | `nucleo/staking.py` |
| 65 | Stake de sencillas con ¼ de Kelly, máximo 1,5 unidades | `staking.stake_sencilla` |
| 66 | Montos redondeados a $500, con el mínimo de BetPlay | `PoliticaStake.redondear` |
| 67 | Tope diario del 12 % con reducción proporcional | `staking.plan_del_dia` |
| 68 | Freno suave: bajo el 70 %, los stakes bajan a la mitad | `PoliticaStake.freno` |
| 69 | Límite de dinero que depende de un mismo partido (2,5 u) | `plan_del_dia` |
| 70 | Tres acciones claras: APOSTAR, VIGILAR o NO | `staking._accion` |
| 71 | Decisión y monto recalculados con la cuota real de BetPlay | `staking.decidir_con_cuota_betplay` |
| 72 | La progresión es un fondo aparte, fuera del tope diario | `plan_del_dia` |
| 73 | Banca real separada de la simulada (`inicialReal`) | `nucleo/liquidacion.bancas` |
| 74 | /saldo para cuadrar con lo que ves en BetPlay | `app.cmd` |
| 75 | Liquidación automática desde el marcador (local o visitante) | `analisis.resultado_seleccion` |
| 76 | Un peldaño nulo de la escalera cuenta como cuota 1 | `liquidacion.liquidar` |
| 77 | Neto real de la escalera proporcional a tu stake | `analisis.liquidar_filas` |
| 78 | Progresión: meta, pérdida y reinicio guardados en el historial | `liquidacion.avanzar_progresion` |
| 79 | Prueba de regresión con tu historial real (banca $102.199) | `tests/test_historial_real.py` |
| 80 | Brier score, comparado con el de referencia | `nucleo/estadisticas.py` |
| 81 | Log-loss | `estadisticas.resumen` |
| 82 | Prueba exacta de Poisson-binomial: ¿aciertos por encima del azar? | `estadisticas.poisson_binomial_cola` |
| 83 | Intervalo de confianza del 90 % del ROI (bootstrap) | `estadisticas.bootstrap_roi` |
| 84 | Máxima caída (drawdown) y curva de banca | `estadisticas.drawdown` |
| 85 | Rachas: actual, peor y mejor | `estadisticas.rachas` |
| 86 | Calibración: probabilidad dicha frente a la real | `estadisticas.calibracion` |
| 87 | CLV (cuota tomada frente a la de cierre), si existe | `estadisticas.resumen` |
| 88 | Desglose por tipo de jugada y por liga | `estadisticas.resumen` |
| 89 | Semáforo de 7 días: aciertos frente a lo esperado | `estadisticas.semaforo` |
| 90 | Monte Carlo del día que respeta las piernas compartidas | `nucleo/simulacion.dia` |
| 91 | Riesgo de ruina a 60 días con tu política de stakes | `simulacion.largo_plazo` |
| 92 | Estado de cada jugada guardado en SQLite (pendiente, sí o no) | `bot/db.py` |
| 93 | Pregunta automática 5 min después del inicio si no contestaste | `alertas.pendientes` |
| 94 | Atajo «hice 1 y 3» sin IA: instantáneo y gratis | `app.atajo` |
| 95 | Respuestas de cuota y detalle sin IA | `app.resolver_espera` |
| 96 | /deshacer borra el último registro aún no sincronizado | `app.cmd` |
| 97 | La IA usa herramientas: evaluar_cuota y simular_riesgo hacen las cuentas en código | `bot/ia.py` |
| 98 | Pantallazos PNG, JPG y WEBP detectados solos | `ia._media_type` |
| 99 | Telegram: reintentos con espera, límite 429 y control de velocidad | `bot/telegram.py` |
| 100 | Producción: SQLite en modo WAL con 14 respaldos diarios, Docker con healthcheck, HTTPS con Caddy, pruebas en GitHub y despliegue automático | `db.respaldar`, `Dockerfile`, `docker-compose.yml`, `.github/workflows/` |

**También incluido:** silencio nocturno con /silencio · avisos que nunca se repiten · bot privado (mensajes y botones) · latido de vida · escritura atómica del día · registros marcados como aplicados por la mesa · tareas programadas v2 que clonan el repositorio y usan el CLI.
