# Instalar sin PC (solo con el celular)

Todo se hace desde el navegador del celular. Nada depende de tu computador: el bot vive en un servidor y se actualiza solo desde GitHub.

| # | Dónde | Qué haces | Tiempo |
|---|---|---|---|
| 1 | github.com | Crear el repositorio vacío `escalera50k` (público) y un token temporal | 5 min |
| 2 | Chat con Claude | Pegar el token: Claude sube el código; luego borras el token | 2 min |
| 3 | cloud.oracle.com | Crear la instancia gratis y pegar `despliegue/oracle-cloud-init.sh` | 10 min |
| 4 | hPanel de Hostinger | Registro A `escalera` → IP del servidor | 3 min |
| 5 | Telegram | /start, canal de datos, /saldo 100000 | 3 min |
| 6 | App de Claude | Pegar las instrucciones nuevas en las 2 tareas programadas | 5 min |

## 1. GitHub (navegador del celular)
1. github.com → **+ → New repository** → nombre `escalera50k` → **Public** → **sin** README → Create.
2. Foto de perfil → **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**
   - Expiration: **1 día**
   - Repository access: **Only select repositories → escalera50k**
   - Permissions → Repository: **Contents: Read and write** y **Workflows: Read and write**
3. Copia el token (`github_pat_…`) y pégalo en el chat con tu usuario de GitHub.
4. Cuando Claude confirme que subió el código: **borra el token** (Settings → Fine-grained tokens → Delete).

## 2. Oracle Cloud (navegador del celular; usa «Ver como escritorio» si se ve mal)
1. **Compute → Instances → Create instance**
2. Image: **Canonical Ubuntu 22.04** · Shape: **Ampere VM.Standard.A1.Flex, 1 OCPU, 6 GB** (gratis).
3. Networking: deja la VCN nueva con **IP pública** asignada.
4. SSH keys: **Generate a key pair** y descarga la privada (por si algún día la necesitas; guárdala en Drive).
5. **Show advanced options → Management → Initialization script → Paste cloud-init script**: pega el contenido de `despliegue/oracle-cloud-init.sh` con tus 6 datos llenos.
6. **Create**. Anota la **IP pública**.
7. Abre los puertos: Networking → Virtual cloud networks → tu VCN → Security Lists → Default → **Add Ingress Rules**: Source `0.0.0.0/0`, TCP, puerto **80**; repite con **443**.
8. Espera unos 10 minutos.

Si dice *Out of capacity*: cambia el *Availability domain* o usa la forma **VM.Standard.E2.1.Micro** (también gratis).

## 3. Hostinger (hPanel en el celular)
**Dominios → dctecnology.xyz → DNS / Nameservers → Agregar registro**: Tipo **A** · Nombre **escalera** · Apunta a **IP de Oracle** · TTL por defecto → Agregar.
No toques `www` ni `@`. En unos minutos `https://escalera.dctecnology.xyz/salud.json` debe responder (el HTTPS se activa solo).

## 4. Telegram
1. Escríbele **/start** al bot → te muestra el CHAT_ID.
2. Crea un **canal privado** «Escalera 50K · datos», agrega el bot como **administrador** y publica «hola» → «📡 Canal de datos conectado».
3. **/start** otra vez → anota CHAT_ID y CANAL_DATOS.
4. **/saldo 100000**.

## 5. Tareas programadas (app de Claude)
Pega `tarea/prompt_manana.md` en «Escalera 50K · picks diarios» y `tarea/prompt_revision.md` en «Escalera 50K · revisión del día». Llena REPO, TOKEN_BOT, CHAT_ID y CANAL_DATOS.

## Cómo se actualiza solo
El servidor revisa GitHub cada 10 minutos (`scripts/actualizar.sh`). Para cambiar algo del código basta con editar el archivo en github.com desde el celular: en 10 minutos el bot ya corre la versión nueva. No hace falta llave SSH ni PC.

## Si algo falla
- `https://escalera.dctecnology.xyz/salud.json` no abre → revisa el registro A y los puertos 80/443 en Oracle.
- El bot no responde → en Oracle: la instancia → **Console connection → Launch Cloud Shell connection**, y escribe `sudo tail -50 /var/log/escalera-instalacion.log` y `cd /opt/escalera50k && sudo docker compose logs --tail 50 bot`. Copia lo que salga y pégalo en el chat.
