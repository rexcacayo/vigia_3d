"""Adaptador: Anycubic Kobra 3 / 3 Max / 3 V2 / S1 / S1 Max (firmware de serie) por LAN.

Protocolo local (el mismo que usa Anycubic Slicer Next en «modo LAN»), sin nube:
1. Apretón de manos HTTP en el puerto 18910 → credenciales MQTT de sesión (cifradas AES).
2. Broker MQTT con TLS **en la propia impresora**, puerto 9883.
3. Vídeo HTTP-FLV en el 18088 (solo da imagen tras la orden `video/startCapture`).

Notas del protocolo, por ingeniería inversa de la comunidad:
https://github.com/sebmueller/kobra3-lan-bridge/blob/main/docs/mqtt-protocol.md

Pruebas desde la terminal (no hace falta arrancar el vigía):
    ./venv/bin/python -m vigia.impresoras.anycubic estado
    ./venv/bin/python -m vigia.impresoras.anycubic pausa | reanudar | luz | foto
    ./venv/bin/python -m vigia.impresoras.anycubic escuchar   # vuelca todos los mensajes
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import random
import ssl
import string
import subprocess
import threading
import time
import uuid

import requests

from .. import config as C
from . import material_de

log = logging.getLogger("vigia.impresora.anycubic")

# ---------------------------------------------------------------- contrato
NOMBRE = "Anycubic Kobra 3 / 3 Max (firmware de serie, modo LAN)"

# Solo lo verificable con seguridad. Temperaturas y ventilador están implementados
# (poner_*) pero se activan cuando se prueben en la máquina: añádelos aquí entonces.
CAPACIDADES = {"pausar", "reanudar", "luz"}
SOLO_CON_PERMISO: set[str] = set()

DESCRIPCION = """\
## Máquina: Anycubic Kobra 3 Max
- Cartesiana de cama móvil (bedslinger), volumen 420×420×500 mm, extrusión directa.
- La cama se mueve en Y: entre fotogramas la pieza cambia de posición, eso es normal.
- Cámara (accesorio) fija; calidad modesta. Piezas grandes y largas: típicamente PLA/PETG.
- Riesgo propio: impresiones muy largas → **quedarse sin filamento** a mitad. Señales:
  el cabezal se mueve pero no deposita material nuevo, la parte de arriba de la pieza
  no crece aunque la capa avance, o la boquilla «dibuja» en el aire.
- No se puede cambiar en marcha: flujo, retracción, Z offset ni % de velocidad fino
  (solo modos silencioso/estándar/deportivo)."""

# ---------------------------------------------------------------- conexión
IP = C.PRINTER_IP
if not IP:
    raise RuntimeError("Anycubic: falta PRINTER_IP en el .env")

PUERTO_HTTP, PUERTO_MQTT, PUERTO_VIDEO = 18910, 9883, 18088
VIDEO = f"http://{IP}:{PUERTO_VIDEO}/flv"
# Estados de proyecto que significan que ya no hay impresión en curso
TERMINADOS = {"finish", "finished", "complete", "completed", "stop", "stoped", "stopped",
              "cancel", "canceled", "cancelled", "failed", "free", "idle"}
PAUSADOS = {"pause", "paused", "pausing"}
# Palabras que, en cualquier mensaje de la impresora, delatan falta de filamento
PALABRAS_FILAMENTO = ("runout", "run_out", "lack", "no_filament", "filament_out",
                      "out_of_filament", "material_out", "feed_fail")


def _rand(n: int) -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=n))


def _md5(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()  # noqa: S324 — lo exige el protocolo


def _descifrar(clave: bytes, iv: bytes, datos: bytes) -> bytes:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    d = Cipher(algorithms.AES(clave), modes.CBC(iv)).decryptor()
    plano = d.update(datos) + d.finalize()
    return plano[:-plano[-1]]  # quitar relleno PKCS7


def credenciales() -> dict:
    """Apretón de manos local: devuelve {username, password, deviceId, modeId, ...}."""
    info = requests.get(f"http://{IP}:{PUERTO_HTTP}/info", timeout=8).json()
    token = info["token"]
    ts, nonce = str(int(time.time() * 1000)), _rand(6)
    firma = _md5(_md5(token[:16]) + ts + nonce)
    url = info.get("ctrlInfoUrl") or f"http://{IP}:{PUERTO_HTTP}/ctrl"
    r = requests.post(url, params={"ts": ts, "nonce": nonce, "sign": firma, "did": "vigia3d-" + _rand(8)},
                      timeout=8).json()
    if r.get("code") != 200:
        raise RuntimeError(f"Anycubic: el apretón de manos falló (code {r.get('code')}). "
                           "¿Está activado el modo LAN en la impresora?")
    plano = _descifrar(token[16:32].encode(), r["data"]["token"].encode(),
                       base64.b64decode(r["data"]["info"]))
    return json.loads(plano)


class _Conexion:
    """Una conexión MQTT persistente; guarda el último mensaje de cada tipo."""

    def __init__(self) -> None:
        self.cli = None
        self.modelo = self.dispositivo = None
        self.lista = threading.Event()
        self.lock = threading.Lock()
        self.ultimo: dict[str, dict] = {}       # tipo → data
        self.recibido: dict[str, float] = {}    # tipo → instante
        self.aviso_filamento: str | None = None
        self.escuchar_todo = False
        self.video_ts = 0.0

    # -------------------------------------------------- conexión
    def asegurar(self) -> None:
        if self.cli is not None and self.lista.is_set():
            return
        with self.lock:
            if self.cli is not None and self.lista.is_set():
                return
            self._conectar()

    def _conectar(self) -> None:
        import paho.mqtt.client as mqtt
        if self.cli is not None:
            try:
                self.cli.loop_stop()
                self.cli.disconnect()
            except Exception:  # noqa: BLE001
                pass
        cred = credenciales()  # siempre una sesión nueva: las viejas caducan
        self.modelo, self.dispositivo = str(cred.get("modeId")), cred.get("deviceId")
        cid = "vigia3d_" + _rand(6)
        cli = (mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, cid)
               if hasattr(mqtt, "CallbackAPIVersion") else mqtt.Client(cid))
        cli.username_pw_set(cred["username"], cred["password"])
        cli.tls_set(cert_reqs=ssl.CERT_NONE)  # certificado propio de la impresora
        cli.tls_insecure_set(True)
        cli.on_connect = self._al_conectar
        cli.on_message = self._al_recibir
        cli.on_disconnect = lambda *_: self.lista.clear()
        self.lista.clear()
        cli.connect(IP, PUERTO_MQTT, keepalive=60)
        cli.loop_start()
        self.cli = cli
        if not self.lista.wait(10):
            raise RuntimeError("Anycubic: no conecta con el MQTT de la impresora (puerto 9883)")
        log.info("Conectado a la Anycubic (modelo %s)", self.modelo)

    def _al_conectar(self, cli, _u, _f, rc) -> None:
        if rc == 0:
            cli.subscribe(f"anycubic/anycubicCloud/v1/printer/public/{self.modelo}/{self.dispositivo}/#", 1)
            self.lista.set()
        else:
            log.error("MQTT rechazó la conexión (rc=%s)", rc)

    def _al_recibir(self, _cli, _u, m) -> None:
        try:
            d = json.loads(m.payload)
        except ValueError:
            return
        tipo = d.get("type") or m.topic.rsplit("/", 2)[-2]
        if isinstance(d.get("data"), dict):
            self.ultimo[tipo] = d["data"]
        self.recibido[tipo] = time.time()
        texto = m.payload.decode("utf-8", "replace").lower()
        if any(p in texto for p in PALABRAS_FILAMENTO):
            self.aviso_filamento = f"{tipo}/{d.get('action')}"
            log.warning("La impresora informa de filamento: %s", texto[:300])
        if self.escuchar_todo:
            print(m.topic, json.dumps(d, ensure_ascii=False)[:2000], flush=True)
        self._registrar(m.topic, d)

    @staticmethod
    def _registrar(topic: str, d: dict) -> None:
        """Guarda los mensajes (últimos ~2 MB) para descubrir campos nuevos, p. ej. de filamento."""
        try:
            f = C.DIR_CASOS / "anycubic_mensajes.jsonl"
            if f.exists() and f.stat().st_size > 2_000_000:
                f.replace(f.with_suffix(".jsonl.1"))
            with f.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"t": time.strftime("%H:%M:%S"), "topic": topic, "msg": d},
                                    ensure_ascii=False) + "\n")
        except OSError:
            pass

    # -------------------------------------------------- órdenes
    def enviar(self, tipo: str, accion: str, datos: dict | None = None, ruta: str = "web") -> None:
        self.asegurar()
        msg = {"type": tipo, "action": accion, "timestamp": int(time.time() * 1000),
               "msgid": str(uuid.uuid4()), "data": datos}
        topic = f"anycubic/anycubicCloud/v1/{ruta}/printer/{self.modelo}/{self.dispositivo}/{tipo}"
        self.cli.publish(topic, json.dumps(msg), 1).wait_for_publish(5)

    def consultar(self, tipo: str = "info", espera: float = 4.0) -> dict:
        antes = self.recibido.get(tipo, 0)
        self.enviar(tipo, "query", None, ruta="slicer")
        limite = time.time() + espera
        while time.time() < limite and self.recibido.get(tipo, 0) <= antes:
            time.sleep(0.1)
        if self.recibido.get(tipo, 0) <= antes:
            if tipo in self.ultimo and time.time() - self.recibido.get(tipo, 0) < 120:
                return self.ultimo[tipo]  # respuesta reciente en caché
            self.lista.clear()  # forzar reconexión la próxima vez
            raise RuntimeError("Anycubic: la impresora no responde a la consulta")
        return self.ultimo[tipo]


_c = _Conexion()


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- obligatorias
def estado() -> dict:
    d = _c.consultar("info")
    p = d.get("project") or {}
    t = d.get("temp") or {}
    est = str(p.get("state") or "").lower()
    pausada = est in PAUSADOS or p.get("pause") in (1, True, "1")
    activa = bool(p) and est not in TERMINADOS
    fichero = p.get("filename")
    error = d.get("error") or p.get("error") or None
    if _c.aviso_filamento and activa:
        error = f"posible falta de filamento ({_c.aviso_filamento})"
    if not activa:
        _c.aviso_filamento = None
    return {
        "maquina": est or d.get("state"),
        "imprimiendo": activa and not pausada,
        "pausada": activa and pausada,
        "fichero": fichero,
        "material": material_de(fichero),
        "capa": {"actual": p.get("curr_layer"), "total": p.get("total_layers")},
        "progreso_pct": _num(p.get("progress")),
        "boquilla": {"actual": _num(t.get("curr_nozzle_temp")), "objetivo": _num(t.get("target_nozzle_temp"))},
        "cama": {"actual": _num(t.get("curr_hotbed_temp")), "objetivo": _num(t.get("target_hotbed_temp"))},
        "ajuste_velocidad_pct": None,
        "modo_velocidad": {1: "silencioso", 2: "estándar", 3: "deportivo"}.get(d.get("print_speed_mode")),
        "ventilador_capa": _num(d.get("fan_speed_pct")),
        "z_offset": None,
        "error": error,
        "tiempo_impresion_s": (_num(p.get("print_time")) or 0) * 60,  # llega en minutos
    }


def capturar() -> bytes:
    """Un fotograma del vídeo FLV con ffmpeg (hay que instalarlo: sudo apt install ffmpeg)."""
    if time.time() - _c.video_ts > 60:
        _c.enviar("video", "startCapture")  # sin esto el stream no da imagen
        _c.video_ts = time.time()
        time.sleep(2)
    try:
        r = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", VIDEO, "-frames:v", "1",
                            "-f", "image2", "-c:v", "mjpeg", "pipe:1"],
                           capture_output=True, timeout=20, check=False)
    except FileNotFoundError:
        raise RuntimeError("Anycubic: falta ffmpeg (sudo apt install ffmpeg)") from None
    if r.stdout[:2] != b"\xff\xd8":
        raise RuntimeError(f"Anycubic: sin imagen de la cámara ({r.stderr.decode()[:200]})")
    return r.stdout


# ---------------------------------------------------------------- acciones
def pausar() -> None:
    _c.enviar("print", "pause", {"taskid": "-1"})


def reanudar() -> None:
    _c.enviar("print", "resume", {"taskid": "-1"})  # «resume», no «continue»


def encender_luz() -> None:
    _c.enviar("light", "control", {"type": 1, "status": 1, "brightness": 100})


def _ajustes(**cambios) -> None:
    t = (_c.ultimo.get("info") or {}).get("temp") or {}
    base = {"target_nozzle_temp": t.get("target_nozzle_temp"), "target_hotbed_temp": t.get("target_hotbed_temp")}
    ajustes = {k: v for k, v in {**base, **cambios}.items() if v is not None}
    _c.enviar("print", "update", {"taskid": "-1", "settings": ajustes})


# Implementadas, pendientes de probar en la máquina (ver CAPACIDADES)
def poner_temp_boquilla(c: float) -> None:
    _ajustes(target_nozzle_temp=int(c))


def poner_temp_cama(c: float) -> None:
    _ajustes(target_hotbed_temp=int(c))


def poner_ventilador(pct: float) -> None:
    _ajustes(fan_speed_pct=int(pct))


# ---------------------------------------------------------------- pruebas a mano
def _main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    orden = argv[0] if argv else "estado"
    if orden == "estado":
        print(json.dumps(estado(), ensure_ascii=False, indent=2))
    elif orden in ("pausa", "pausar"):
        pausar()
        time.sleep(5)
        print("pausada:", estado()["pausada"])
    elif orden == "reanudar":
        reanudar()
        time.sleep(5)
        print("imprimiendo:", estado()["imprimiendo"])
    elif orden == "luz":
        encender_luz()
    elif orden == "foto":
        (C.DIR_CASOS / "prueba_anycubic.jpg").write_bytes(capturar())
        print("Foto en", C.DIR_CASOS / "prueba_anycubic.jpg")
    elif orden == "escuchar":
        _c.escuchar_todo = True
        _c.asegurar()
        print("Escuchando (Ctrl+C para salir)…")
        while True:
            time.sleep(30)
            _c.enviar("info", "query", None, ruta="slicer")
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_main(sys.argv[1:]))
