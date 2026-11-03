# Escalera 50K · imagen del bot (multi-arquitectura: funciona en ARM de Oracle Free y en x86)
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TZ=America/Bogota DATOS_DIR=/datos
RUN apt-get update && apt-get install -y --no-install-recommends tzdata ca-certificates \
    && rm -rf /var/lib/apt/lists/* && useradd -m -u 1000 bot
WORKDIR /app
COPY pyproject.toml README.md ./
COPY escalera ./escalera
ARG VOZ=0
RUN pip install --no-cache-dir . && if [ "$VOZ" = "1" ]; then pip install --no-cache-dir faster-whisper; fi
USER bot
VOLUME ["/datos"]
HEALTHCHECK --interval=2m --timeout=10s --start-period=1m \
  CMD python -c "import json,time;d=json.load(open('/datos/panel/salud.json'));exit(0 if time.time()-d['ts']<900 else 1)"
CMD ["python", "-m", "escalera.bot.app"]
