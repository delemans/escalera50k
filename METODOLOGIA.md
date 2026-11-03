# Metodología · Escalera 50K v2

El sistema no busca «fijas». Busca apuestas en las que la cuota paga **más** de lo que el riesgo exige, y dice con claridad cuando no hay ninguna (que es lo normal en mercados eficientes).

## 1. De los datos a la probabilidad

| Paso | Qué se hace | Código |
|---|---|---|
| Fuente estadística | StatArea: 1X2 de todos los partidos del día | `validacion.leer_csv` |
| Control de calidad | Sumas = 100 (±1), tips coherentes, promedios frente a la referencia | `validacion.validar` |
| Candidatos | Ligas principales, StatArea ≥ 50 %, desde 07:30 (Bogotá) | `analisis.candidatos_statarea` |
| Mercado | Cuotas de 2 o más casas; margen quitado con el método de potencia (y Shin como control) | `probabilidad.consenso` |
| Filtros | Fuera si StatArea y mercado difieren más de 8 pts, si las casas difieren más de 4 pts o si hay alerta por noticias | `analisis.evaluar` |
| Probabilidad final | **p = 0,85·mercado + 0,15·StatArea** | `probabilidad.mezcla` |

## 2. Valor

- **EV = p·cuota − 1**: +3 % significa ganar 3 pesos por cada 100 apostados, a la larga.
- **Cuota mínima = 1,02/p**: por debajo de ella, no hay valor.
- **Kelly = (p·o − 1)/(o − 1)**: la fracción teórica de la banca. Se usa **¼** porque las probabilidades tienen error.

## 3. Qué hacer con cada jugada (dinero real)

| Acción | Cuándo | Qué haces |
|---|---|---|
| 🟢 APOSTAR | EV ≥ +2 % con la cuota de referencia | Apuestas el monto **solo si BetPlay paga ≥ la mínima** |
| 🟡 VIGILAR | EV entre −4 % y +2 % | Le dices al bot cuánto paga BetPlay y él decide |
| ⚪ NO | EV < −4 % o alerta | No apuestas; solo se simula |

Con una banca de **$100.000**:

- Unidad: $2.000 (2 %).
- Sencilla: ¼ de Kelly, de $1.000 a $3.000.
- Escalera: 2 unidades. Combinada: 1 unidad. Súper: 0,5 unidades.
- Tope diario: $12.000 (12 %). Si el plan lo pasa, todo se reduce en proporción.
- Exposición: como máximo 2,5 unidades pueden depender de un mismo partido.
- Freno suave: si la banca baja de $70.000, los stakes bajan a la mitad (el bot te avisa).
- Progresión: es un reto aparte con fondo propio y no entra en el tope.

## 4. Jugadas

| Jugada | Reglas |
|---|---|
| 🎯 Sencillas | Hasta 5, cuota 1,30–2,60, máx. 2 por liga y 2 a la misma hora |
| 🪜 Escalera | 3 picks con p ≥ 65 %, cuota 1,30–1,50 y ≥ 2 h entre sí. Se reinvierte, se retira la base tras el 2.º y se juega el resto en el 3.º |
| 📈 Progresión | El pick de mayor p con cuota 1,25–1,50. Todo el saldo, de $5.000 a $50.000 |
| 🔗 Combinada | 2–3 piernas con p ≥ 62 %, cuota total 2–3,5 |
| 🚀 Súper | 4–6 piernas con p ≥ 58 %, cuota total 6–20. Gasto pequeño de alto riesgo |

## 5. ¿Funciona o es suerte?

| Métrica | Qué dice |
|---|---|
| Aciertos frente a lo esperado (Σp) | Si el sistema acierta lo que promete |
| p-valor (Poisson-binomial exacto) | Probabilidad de acertar tanto solo por azar; < 0,10 empieza a ser señal |
| Brier y log-loss | Calidad de las probabilidades (menor es mejor) |
| Calibración por tramos | Cuando dice 70 %, ¿acierta cerca del 70 %? |
| ROI con IC 90 % (bootstrap) | Rango creíble del rendimiento |
| Máxima caída y rachas | Cuánto duele el camino |
| CLV | Si tomaste mejor cuota que la de cierre (el mejor indicador a largo plazo) |
| Monte Carlo | Probabilidad de terminar el día ganando y riesgo de caer 30 % o 50 % |

Con menos de unas 200 jugadas, ningún resultado prueba nada: ni una buena racha ni una mala.

> Probabilidad no es certeza: un pick de 70 % falla 3 de cada 10 veces.
