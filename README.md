# 🪜 Escalera 50K

Mesa de análisis de fútbol por **valor esperado** + **bot de Telegram 24/7**. Software libre (MIT).

- Cada mañana te dice **qué hacer con cada jugada**: 🟢 apostar (con monto), 🟡 vigilar (solo si BetPlay paga la mínima) o ⚪ no.
- Una tarjeta por jugada con botones **✅ La hice · ❌ No la hice · 💬 ¿Cuánto paga BetPlay?**
- Lee **pantallazos** de BetPlay, **notas de voz** y texto («hice 1 y 3»), y siempre pide confirmación.
- Puedes **conversar** con él a cualquier hora sobre el sistema y los picks.
- Recordatorios 60 y 15 min antes, pregunta «¿la hiciste?» cuando empieza el partido, alertas de tope, banca y rachas.
- Estadística seria: calibración, Brier, p-valor, ROI con intervalo de confianza, drawdown, Monte Carlo.
- Panel web privado en tu dominio, con HTTPS automático.

> ⚠️ Esto no es un sistema para ganar seguro. En la mayoría de los días el mercado está bien calibrado y la respuesta honesta es «no apostar». Apuesta solo lo que puedas perder.

## Arquitectura

```
 ┌──────────────────────────┐   dia.json fijado    ┌──────────────────────────┐
 │ Tarea programada (Claude)│ ───────────────────▶ │ Bot 24/7 (tu servidor)   │──▶ Telegram
 │ 06:59 · 13:47 · 21:47    │                      │  SQLite · panel · alertas │──▶ https://tu-dominio
 │ recolecta web → CLI      │ ◀─────────────────── │                          │
 └──────────────────────────┘ registro.json fijado └──────────────────────────┘
          │ clona este repo y corre `escalera analizar` (las cuentas las hace el código)
          ▼
   Sitio (artifact) con la base de datos de apuestas
```

## Estructura

```
escalera/
├── nucleo/              ← lógica pura, 100 % probada
│   ├── probabilidad.py    margen: multiplicativo, potencia, Shin · consenso entre casas
│   ├── valor.py           EV, cuota mínima, Kelly
│   ├── staking.py         cuánto apostar y qué hacer (APOSTAR / VIGILAR / NO)
│   ├── jugadas.py         sencillas, escalera, progresión, combinada, súper
│   ├── liquidacion.py     resultados, netos, bancas, progresión
│   ├── estadisticas.py    Brier, calibración, p-valor, bootstrap, drawdown, CLV
│   ├── simulacion.py      Monte Carlo del día y riesgo de ruina
│   ├── validacion.py      control de calidad de StatArea
│   └── formato.py         $ 12.000 · 1,45 · −3,1 %
├── analisis.py          ← tubería del día (la usa la tarea)
├── cli.py               ← `escalera candidatos | analizar | liquidar | informe | evaluar | riesgo`
└── bot/                 ← Telegram
    ├── app.py             flujo, comandos, botones
    ├── mensajes.py        diseño de cada mensaje
    ├── alertas.py         recordatorios y alertas 🔴🟠🟡🟢
    ├── ia.py              Claude con herramientas
    ├── db.py              SQLite + respaldos
    ├── sync.py            intercambio con la tarea
    ├── panel.py           panel web estático
    ├── telegram.py        cliente con reintentos
    └── voz.py             notas de voz (opcional)
tarea/                   ← instrucciones de las 2 tareas programadas
scripts/                 ← instalar servidor · publicar en GitHub · correr local
despliegue/Caddyfile     ← HTTPS y clave del panel
tests/                   ← 31 pruebas
```

## Puesta en producción (unos 30 minutos)

### 1. Publica el repositorio en GitHub
```bash
bash scripts/publicar_github.sh escalera50k      # necesita gh (cli.github.com)
```
El `.env` nunca se sube: está en `.gitignore`.

### 2. Crea el servidor gratis (Oracle Cloud Always Free)
1. Crea una cuenta en cloud.oracle.com (puede pedir tarjeta para verificar identidad; los recursos Always Free no se cobran).
2. Compute → Instances → Create: **Ubuntu 22.04**, forma **VM.Standard.A1.Flex** (ARM, 1 OCPU y 6 GB alcanzan). Descarga la llave SSH.
3. En la VCN, en Security List, agrega reglas de entrada para TCP **80** y **443**.
4. En tu dominio, crea un registro **A**: `escalera.tudominio.com → IP pública del servidor`.

> Otras opciones gratis o casi gratis: Google Cloud e2-micro (free tier), o cualquier VPS de unos 5 USD/mes.

### 3. Instala con un solo comando (dentro del servidor)
```bash
ssh -i llave.key ubuntu@IP
curl -fsSL https://raw.githubusercontent.com/TU_USUARIO/escalera50k/main/scripts/instalar_servidor.sh \
  | bash -s -- https://github.com/TU_USUARIO/escalera50k.git
```
Te pide el token del bot, la clave de Claude, el dominio, tu saldo y una clave para el panel. Queda corriendo con Docker y se reinicia solo.

### 4. Conecta Telegram
1. Escríbele `/start` a tu bot: te da tu **CHAT_ID**.
2. Crea un **canal privado** «Escalera 50K · datos», agrega el bot como **administrador** y publica cualquier mensaje: el bot responde «📡 Canal de datos conectado».
3. Escribe `/saldo 100000`.

### 5. Despliegue automático
En GitHub → Settings → Secrets → Actions: `SERVIDOR_IP`, `SERVIDOR_USUARIO` (ubuntu) y `SERVIDOR_LLAVE_SSH` (el contenido de la llave). Cada push a `main` pasa las pruebas y actualiza el servidor solo.

### 6. Actualiza las 2 tareas programadas
En la app de Claude, abre cada tarea y pega `tarea/prompt_manana.md` (06:59) y `tarea/prompt_revision.md` (13:47 y 21:47). Llena `REPO`, `TOKEN_BOT`, `CHAT_ID` y `CANAL_DATOS`.

### 7. Monitoreo (opcional, gratis)
UptimeRobot → monitor HTTP a `https://tu-dominio/salud.json`. Si el bot se cae, te llega un correo.

## Uso diario

| Momento | Qué pasa | Qué haces tú |
|---|---|---|
| ~07:05 | Llegan el resumen, «Qué hacer hoy» y las tarjetas | Abres BetPlay y miras las cuotas |
| Antes de apostar | 💬 ¿Cuánto paga BetPlay? → escribes `1,40` | El bot responde 🟢 APUESTA $x o ⚪ NO |
| Apostaste | ✅ La hice → `1,40 2000` o pantallazo | Queda registrado |
| −60/−15 min | Recordatorio por partido | — |
| +5 min | «¿Hiciste esta?» si no respondiste | Toca ✅ o ❌ |
| Tarde y noche | 🔄 Actualización con resultados | — |
| Cuando quieras | /stats · /riesgo · /banca · o pregúntale | — |

## Desarrollo

```bash
pip install -e ".[dev]"
pytest -q                                   # 31 pruebas
python -m escalera.cli analizar ejemplos/entrada_ejemplo.json
python -m escalera.cli evaluar 0.70 1.45
python ejemplos/vista_previa.py             # así se ven los mensajes
```

## Costos

| Pieza | Costo |
|---|---|
| Servidor Oracle Always Free | $0 |
| Telegram, GitHub, Caddy, SQLite | $0 |
| Dominio | el que ya tienes |
| API de Claude (chat y pantallazos) | por uso; depende de cuánto converses (revisa la tarifa en console.anthropic.com) |

## Juego responsable

El bot informa y nunca bloquea. Si sientes que necesitas recuperar pérdidas o apostar más de lo planeado, para. En Colombia, Coljuegos publica información sobre juego responsable.
