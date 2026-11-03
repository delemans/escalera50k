# Escalera 50K en Render gratis (sin tarjeta, sin PC)

Render corre el bot gratis y lo actualiza solo cada vez que cambias algo en GitHub.
Límites del plan gratis y cómo los resolvemos:

| Límite | Solución |
|---|---|
| Se duerme tras 15 min sin visitas | Un «ping» gratis cada 10 min (cron-job.org) lo mantiene despierto; además Telegram lo despierta con cada mensaje (webhook) |
| El disco se borra al reiniciar | El bot guarda su estado en los mensajes fijados de Telegram y lo recupera solo al arrancar |
| 750 h al mes | Alcanza para 1 servicio encendido todo el mes (744 h) |
| 512 MB de RAM | Suficiente; las notas de voz se transcriben con Groq o Gemini (gratis) |
| IA de pago | No hace falta: Gemini gratis → Groq gratis → OpenRouter gratis, en ese orden |

## 1. Sube los archivos nuevos a GitHub
En `github.com/Delemans/escalera50k` → **Add file → Upload files** → arrastra desde la carpeta `escalera50k-v3`:
- la carpeta **`escalera`** completa (reemplaza la anterior),
- la carpeta **`tests`**,
- los archivos **`render.yaml`**, **`INSTALAR_RENDER.md`** y **`README.md`**.
→ **Commit changes**.

## 2. Crea el servicio en Render
1. Entra a **render.com → Get Started → GitHub** (inicia sesión con tu cuenta de GitHub).
2. **New → Blueprint** → autoriza el repositorio **escalera50k** → **Connect**.
3. Render lee `render.yaml` y te pide 5 valores:
   - `TOKEN_BOT`: el token de tu bot
   - `GEMINI_API_KEY`: clave **gratis** de Google (aistudio.google.com → **Get API key → Create API key**)
   - `GROQ_API_KEY` (opcional): clave **gratis** de console.groq.com → API Keys (respaldo si Gemini se queda sin cuota y transcribe notas de voz)
   - `PANEL_CLAVE`: una clave que inventes para el panel
   - `CHAT_ID` y `CANAL_DATOS`: **déjalos vacíos por ahora**
4. **Apply**. En 3–5 minutos aparece **Live** y una dirección tipo `https://escalera50k-xxxx.onrender.com`.
5. Abre `https://escalera50k-xxxx.onrender.com/salud`: debe decir `"ok": true`.

## 3. Conecta Telegram
1. Escríbele **/start** al bot → copia tu **CHAT_ID**.
2. Crea un **canal privado** «Escalera 50K · datos», agrega el bot como **administrador** y publica «hola» → el bot responde con **CANAL_DATOS**.
3. En Render → tu servicio → **Environment**: llena **CHAT_ID** y **CANAL_DATOS** → **Save changes** (se reinicia solo).
4. Escribe **/saldo 100000**.

## 4. Tu dominio (Hostinger)
1. Render → tu servicio → **Settings → Custom Domains → Add**: `escalera.dctecnology.xyz`.
2. hPanel de Hostinger → **Dominios → dctecnology.xyz → DNS / Nameservers → Agregar registro**:
   Tipo **CNAME** · Nombre **escalera** · Apunta a **escalera50k-xxxx.onrender.com** → Agregar.
3. Vuelve a Render y toca **Verify**. El certificado HTTPS se crea solo (minutos a pocas horas).
4. Panel: `https://escalera.dctecnology.xyz` (usuario `admin`, tu `PANEL_CLAVE`).

## 5. Mantenerlo despierto (gratis)
1. **cron-job.org → Sign up** (gratis, sin tarjeta).
2. **Create cronjob**: URL `https://escalera.dctecnology.xyz/salud` · cada **10 minutos** → Create.
   (Mientras el dominio no esté verificado, usa la dirección `onrender.com`).

## 6. Tareas programadas (app de Claude)
Pega `tarea/prompt_manana.md` y `tarea/prompt_revision.md` en las 2 tareas y llena:
`REPO = https://github.com/Delemans/escalera50k.git`, `TOKEN_BOT`, `CHAT_ID`, `CANAL_DATOS`.

## Si algo falla
Render → tu servicio → **Logs**. Copia las últimas líneas y pégalas en el chat.
