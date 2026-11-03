"""
BASE LOCAL · SQLite (un archivo, sin servidor, con respaldo diario)
==================================================================
Tablas:
  registro       lo que reportaste (hice / no hice / propia) y si ya se sincronizó
  confirmacion   estado de cada jugada del día: pendiente | si | no
  avisos         alertas ya enviadas (para no repetir)
  memoria        últimos mensajes de la conversación con Claude
  kv             valores sueltos (ids, saldo reportado, offset, estado de espera)
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from contextlib import contextmanager

from .. import config

_ARCHIVO = config.DATOS / "escalera.db"
_lock = threading.RLock()
_con: sqlite3.Connection | None = None

ESQUEMA = """
CREATE TABLE IF NOT EXISTS registro (
  tgId TEXT PRIMARY KEY, fecha TEXT, cuando TEXT, accion TEXT, ref TEXT, tipo TEXT,
  partido TEXT, sel TEXT, cuota REAL, valor REAL, estado TEXT, fuente TEXT,
  datos TEXT, sincronizado INTEGER DEFAULT 0, creado REAL);
CREATE TABLE IF NOT EXISTS confirmacion (
  fecha TEXT, ref TEXT, estado TEXT DEFAULT 'pendiente', preguntado INTEGER DEFAULT 0,
  msg_id INTEGER, PRIMARY KEY (fecha, ref));
CREATE TABLE IF NOT EXISTS avisos (clave TEXT PRIMARY KEY, cuando REAL);
CREATE TABLE IF NOT EXISTS memoria (id INTEGER PRIMARY KEY AUTOINCREMENT, rol TEXT, texto TEXT, cuando REAL);
CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT);
"""


def con() -> sqlite3.Connection:
    global _con
    if _con is None:
        _con = sqlite3.connect(_ARCHIVO, check_same_thread=False, isolation_level=None)
        _con.row_factory = sqlite3.Row
        _con.execute("PRAGMA journal_mode=WAL")
        _con.executescript(ESQUEMA)
    return _con


@contextmanager
def tx():
    with _lock:
        c = con()
        c.execute("BEGIN")
        try:
            yield c
            c.execute("COMMIT")
        except Exception:
            c.execute("ROLLBACK")
            raise


# ---- kv ---------------------------------------------------------------------
def get(k, defecto=None):
    with _lock:
        r = con().execute("SELECT v FROM kv WHERE k=?", (k,)).fetchone()
    return json.loads(r["v"]) if r else defecto


def put(k, v):
    with _lock:
        con().execute("INSERT INTO kv(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
                      (k, json.dumps(v, ensure_ascii=False)))


# ---- registro ---------------------------------------------------------------
CAMPOS = ["tgId", "fecha", "cuando", "accion", "ref", "tipo", "partido", "sel", "cuota", "valor", "estado", "fuente"]


def registrar(items: list[dict]):
    with tx() as c:
        for a in items:
            c.execute(f"INSERT OR REPLACE INTO registro({','.join(CAMPOS)},datos,sincronizado,creado) "
                      f"VALUES({','.join('?' * len(CAMPOS))},?,0,?)",
                      [a.get(k) for k in CAMPOS] + [json.dumps(a, ensure_ascii=False), time.time()])


def registro(desde: str | None = None, solo_pendientes=False) -> list[dict]:
    q = "SELECT datos, sincronizado FROM registro WHERE 1=1"
    args = []
    if desde:
        q += " AND fecha >= ?"
        args.append(desde)
    if solo_pendientes:
        q += " AND sincronizado = 0"
    with _lock:
        filas = con().execute(q + " ORDER BY creado", args).fetchall()
    out = []
    for f in filas:
        d = json.loads(f["datos"])
        d["sincronizado"] = bool(f["sincronizado"])
        out.append(d)
    return out


def marcar_sincronizados(tg_ids):
    with tx() as c:
        c.executemany("UPDATE registro SET sincronizado=1 WHERE tgId=?", [(t,) for t in tg_ids])


def borrar_registro(tg_id):
    with _lock:
        con().execute("DELETE FROM registro WHERE tgId=? AND sincronizado=0", (tg_id,))


def apostado(fecha: str) -> float:
    with _lock:
        r = con().execute("SELECT COALESCE(SUM(valor),0) s FROM registro WHERE fecha=? "
                          "AND accion IN ('hice','propia')", (fecha,)).fetchone()
    return r["s"]


# ---- confirmaciones ---------------------------------------------------------
def confirmacion(fecha, ref):
    with _lock:
        r = con().execute("SELECT * FROM confirmacion WHERE fecha=? AND ref=?", (fecha, ref)).fetchone()
    return dict(r) if r else None


def set_confirmacion(fecha, ref, **campos):
    actual = confirmacion(fecha, ref) or {"fecha": fecha, "ref": ref, "estado": "pendiente",
                                           "preguntado": 0, "msg_id": None}
    actual.update(campos)
    with _lock:
        con().execute("INSERT OR REPLACE INTO confirmacion(fecha,ref,estado,preguntado,msg_id) VALUES(?,?,?,?,?)",
                      (fecha, ref, actual["estado"], actual["preguntado"], actual["msg_id"]))


# ---- avisos y memoria -------------------------------------------------------
def aviso_enviado(clave) -> bool:
    with _lock:
        return con().execute("SELECT 1 FROM avisos WHERE clave=?", (clave,)).fetchone() is not None


def marcar_aviso(clave):
    with _lock:
        con().execute("INSERT OR IGNORE INTO avisos VALUES(?,?)", (clave, time.time()))


def memoria(n=16) -> list[dict]:
    with _lock:
        filas = con().execute("SELECT rol, texto FROM memoria ORDER BY id DESC LIMIT ?", (n,)).fetchall()
    msgs = [{"role": f["rol"], "content": f["texto"]} for f in reversed(filas)]
    while msgs and msgs[0]["role"] != "user":       # la API exige empezar con el usuario
        msgs.pop(0)
    return msgs


def recordar(rol, texto):
    with _lock:
        con().execute("INSERT INTO memoria(rol,texto,cuando) VALUES(?,?,?)", (rol, texto, time.time()))
        con().execute("DELETE FROM memoria WHERE id NOT IN (SELECT id FROM memoria ORDER BY id DESC LIMIT 200)")


def respaldar() -> str:
    import datetime as dt
    destino = config.DATOS / "respaldos" / f"escalera-{dt.date.today().isoformat()}.db"
    with _lock:
        b = sqlite3.connect(destino)
        con().backup(b)
        b.close()
    viejos = sorted((config.DATOS / "respaldos").glob("escalera-*.db"))[:-14]
    for v in viejos:
        v.unlink()
    return str(destino)
