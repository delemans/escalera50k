"""
SERVIDOR WEB INTERNO · para Render (o cualquier PaaS) sin Caddy ni Docker
=========================================================================
  POST /telegram/<secreto>   webhook de Telegram (verifica el encabezado secreto)
  GET  /salud                estado del bot (público, para el "ping" que lo mantiene despierto)
  GET  /tipster.json         picks de tipster reenviados (últimos 7 días, solo lectura, para la tarea)
  GET  /                     panel web con usuario y clave (PANEL_USUARIO / PANEL_CLAVE)
Los updates se ponen en una cola; el hilo principal los procesa en orden.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .. import config

log = logging.getLogger("web")
cola: "queue.Queue[dict]" = queue.Queue()


def secreto() -> str:
    return hashlib.sha256(("escalera50k:" + config.TOKEN_BOT).encode()).hexdigest()[:40]


def _autorizado(cabecera: str | None) -> bool:
    if not config.PANEL_CLAVE:
        return False
    if not cabecera or not cabecera.startswith("Basic "):
        return False
    try:
        usuario, _, clave = base64.b64decode(cabecera[6:]).decode().partition(":")
    except Exception:
        return False
    return hmac.compare_digest(usuario, config.PANEL_USUARIO) and hmac.compare_digest(clave, config.PANEL_CLAVE)


class Manejador(BaseHTTPRequestHandler):
    server_version = "Escalera50K"

    def _responder(self, codigo, cuerpo: bytes = b"", tipo="text/plain; charset=utf-8", extra=None):
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(cuerpo)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        ruta = self.path.split("?")[0]
        if ruta in ("/salud", "/salud.json"):
            f = config.PANEL / "salud.json"
            cuerpo = f.read_bytes() if f.exists() else b'{"ok": true, "nota": "arrancando"}'
            return self._responder(200, cuerpo, "application/json")
        if ruta == "/tipster.json":
            import datetime as dt
            from . import db
            desde = (dt.date.today() - dt.timedelta(days=7)).isoformat()
            cuerpo = json.dumps({"picks": db.tipster(desde)}, ensure_ascii=False).encode()
            return self._responder(200, cuerpo, "application/json; charset=utf-8", {"Cache-Control": "no-store"})
        if ruta == "/app":
            from urllib.parse import parse_qs, urlparse
            from .panel import token_valido
            t = (parse_qs(urlparse(self.path).query).get("t") or [None])[0]
            if not token_valido(t):
                return self._responder(403, "Enlace vencido: pide uno nuevo con /app en el bot.".encode())
            try:                                   # sin día cargado → lo busca en el chat del dueño ya mismo
                from . import panel as _p, sync as _s
                if _s.dia().get("fecha") != _s.hoy():
                    nuevo = _s.revisar_dia_nuevo()
                    if nuevo:
                        _p.generar(nuevo)
            except Exception as ex:
                log.warning("app: %s", ex)
            f = config.PANEL / "index.html"
            cuerpo = f.read_bytes() if f.exists() else "La app se está preparando; vuelve en un minuto.".encode()
            return self._responder(200, cuerpo, "text/html; charset=utf-8", {"Cache-Control": "no-store"})
        if ruta in ("/", "/index.html"):
            if not _autorizado(self.headers.get("Authorization")):
                return self._responder(401, "Clave requerida".encode(), extra={
                    "WWW-Authenticate": 'Basic realm="DCBET", charset="UTF-8"'})
            f = config.PANEL / "index.html"
            cuerpo = f.read_bytes() if f.exists() else "Panel aún sin generar.".encode()
            return self._responder(200, cuerpo, "text/html; charset=utf-8", {"Cache-Control": "no-store"})
        return self._responder(404, b"No encontrado")

    def do_POST(self):
        if self.path != f"/telegram/{secreto()}" or \
                self.headers.get("X-Telegram-Bot-Api-Secret-Token") != secreto():
            return self._responder(403, b"")
        try:
            n = min(int(self.headers.get("Content-Length", 0)), 2_000_000)
            cola.put(json.loads(self.rfile.read(n)))
        except Exception:
            log.warning("Webhook con cuerpo inválido")
        self._responder(200, b"ok")

    def log_message(self, *args):          # sin ruido en los logs
        pass


def arrancar(puerto: int) -> ThreadingHTTPServer:
    srv = ThreadingHTTPServer(("0.0.0.0", puerto), Manejador)
    threading.Thread(target=srv.serve_forever, daemon=True, name="web").start()
    log.info("Servidor web en el puerto %s", puerto)
    return srv
