# Fase 2 · Canal gratis, VIP y crecimiento

> **Regla de oro: no se vende nada hasta que los números lo prueben.** El bot lo mide solo con `/fase2`.

## 0. Criterios para abrir el VIP (todos a la vez)

| Criterio | Meta | Por qué |
|---|---|---|
| Picks liquidados | ≥ 300 | Con menos, una buena racha parece talento |
| Historial | ≥ 8 semanas | Cubre rachas malas normales |
| IC 90 % del ROI | piso > 0 % | Que incluso en el escenario prudente gane |
| p-valor | < 0,05 | Los aciertos no se explican por azar |

Mientras no se cumplan, el sistema sigue en prueba y el canal gratis construye el historial público.

## 1. Canal gratis (empieza ya, sin vender)

1. Crea un canal público, por ejemplo «Escalera 50K · Picks con datos». Agrega el bot como administrador.
2. Activa los comentarios: Canal → Editar → **Discusión** → crea un grupo enlazado.
3. En Render agrega `FASE2=1` y `CANAL_PUBLICO=@tu_canal` (o el id `-100…`).
4. Cada mañana el bot publica **1 pick gratis**: el de más confianza con valor. Va con hora de publicación (antes del partido), su análisis y el aviso +18.
5. Al liquidar, el bot publica el **resultado** y el **historial público** acumulado (aciertos, unidades y ROI). Publica todo, también las pérdidas: eso es lo que da credibilidad.

Contenido extra, a mano:
- Pantallazos de tus boletos reales, tapando datos personales.
- Explicaciones cortas de un pick: por qué tiene valor.

## 2. Canal VIP (solo con `/fase2` en ✅)

1. Crea un canal **privado** «Escalera 50K · VIP» y agrega el bot como administrador.
2. En Render: `CANAL_VIP=-100…` y `VIP_PRECIO_STARS=500`. El precio es en estrellas de Telegram; ajústalo.
3. En el bot escribe `/vip`. Crea un **enlace de suscripción de 30 días** pagado con Telegram Stars: Telegram cobra, renueva y saca al que no paga.
4. El bot publica en el VIP todo el plan: individuales, combinadas, soñadora, escalera, avisos en vivo y cobro anticipado.

Precio orientativo para validar: el equivalente a 1–2 unidades al mes. Súbelo solo con más historial.

## 3. Crecimiento y publicidad: lo que sí y lo que no

**TikTok prohíbe facilitar o promocionar apuestas.** Los videos que muestran apuestas quedan para +18 y fuera del «Para ti», y los anuncios de apuestas necesitan permiso expreso. Un canal de picks promocionado allí corre riesgo de que le bajen los videos o le cierren la cuenta.

Lo más seguro en TikTok, Reels y Shorts es contenido **educativo**, sin llamados a apostar ni enlaces a casas:

- «Qué es el valor esperado».
- «Por qué el 70 % falla 3 de cada 10».
- «Cómo leer una cuota».
- «Mi historial público, ganadas y perdidas».

El enlace va al canal gratis, que es donde el usuario decide.

**En Colombia** solo los operadores autorizados por Coljuegos pueden hacer publicidad de apuestas. Esa publicidad no puede prometer ganancias, debe advertir el riesgo de adicción e indicar +18. Vender pronósticos no es lo mismo que operar juego, pero igual aplica la protección al consumidor: nada de «ganancias seguras». Antes de cobrar, consulta con un abogado. Esto no es asesoría legal.

**Frases prohibidas en todo el material:** «fija», «100 % seguro», «gana dinero fácil», «recupera lo perdido».

## 4. Estrategias tipo sharp (lo que hace serio el canal)

- **CLV (closing line value):** registra la cuota de cierre de cada pick. Si en promedio tomas mejor cuota que el cierre, hay ventaja real, aunque el mes salga negativo.
- **Publicar antes del partido**, con hora, sin borrar ni editar.
- **Unidades fijas**, no montos: «1 u = 2 % de la banca».
- **Informe semanal** (el bot lo manda los domingos a las 21:00) con aciertos frente a lo esperado, ROI, intervalo de confianza y drawdown.

## 5. Comandos del bot para la fase 2

| Comando | Qué hace |
|---|---|
| `/fase2` | Avance frente a los criterios y el historial público |
| `/vip` | Crea el enlace de suscripción mensual (cuando esté listo) |
| `/informe` | Métricas completas |
| `/app` | Abre la app en el celular |
