"""Cámara extra (p. ej. cenital, encima de la tapa): una segunda vista para el diagnóstico.

CAMARA_EXTRA en el .env:
- vacío          → sin cámara extra
- picam          → cámara de la Raspberry (CSI) con rpicam-still / libcamera-still
- /dev/video0    → webcam USB (UVC) con ffmpeg; ajustes fijos con CAMARA_EXTRA_V4L2
- http(s)://…    → URL que devuelve un JPEG (snapshot) o un stream MJPEG

    python -m vigia.camara_extra      # saca una foto de prueba en DIR_CASOS
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import threading

import requests

from . import config as C

log = logging.getLogger("vigia.camara_extra")
_lock = threading.Lock()   # una cámara CSI o USB no admite dos capturas a la vez
_ajustada = False


def activa() -> bool:
    return bool(C.CAMARA_EXTRA)


def _ancho_alto() -> tuple[str, str]:
    a, _, h = C.CAMARA_EXTRA_RESOLUCION.partition("x")
    return a or "1280", h or "960"


def _picam() -> bytes:
    exe = shutil.which("rpicam-still") or shutil.which("libcamera-still")
    if not exe:
        raise RuntimeError("no encuentro rpicam-still ni libcamera-still (¿Raspberry Pi OS?)")
    ancho, alto = _ancho_alto()
    orden = [exe, "-n", "-t", "800", "--width", ancho, "--height", alto, "-e", "jpg", "-o", "-"]
    if C.CAMARA_EXTRA_ENFOQUE:  # Camera Module 3: enfoque fijo (dioptrías; 3 ≈ 33 cm)
        orden += ["--autofocus-mode", "manual", "--lens-position", C.CAMARA_EXTRA_ENFOQUE]
    r = subprocess.run(orden, capture_output=True, timeout=20, check=False)
    if r.stdout[:2] != b"\xff\xd8":
        raise RuntimeError(f"la cámara de la Pi no dio imagen: {r.stderr.decode()[-200:]}")
    return r.stdout


def _ajustar_v4l2(dispositivo: str) -> None:
    """Apaga autoenfoque/autoexposición si se pide (CAMARA_EXTRA_V4L2=clave=valor,…)."""
    global _ajustada
    if _ajustada or not C.CAMARA_EXTRA_V4L2 or not shutil.which("v4l2-ctl"):
        return
    r = subprocess.run(["v4l2-ctl", "-d", dispositivo, "-c", C.CAMARA_EXTRA_V4L2],
                       capture_output=True, timeout=10, check=False)
    if r.returncode:
        log.warning("v4l2-ctl: %s", r.stderr.decode()[-200:])
    _ajustada = True


def _usb(dispositivo: str) -> bytes:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("falta ffmpeg (sudo apt install ffmpeg)")
    _ajustar_v4l2(dispositivo)
    ancho, alto = _ancho_alto()
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "v4l2", "-input_format", "mjpeg",
                        "-video_size", f"{ancho}x{alto}", "-i", dispositivo,
                        "-frames:v", "1", "-f", "image2", "-c:v", "mjpeg", "pipe:1"],
                       capture_output=True, timeout=20, check=False)
    if r.stdout[:2] != b"\xff\xd8":
        raise RuntimeError(f"la webcam no dio imagen: {r.stderr.decode()[-200:]}")
    return r.stdout


def _url(url: str) -> bytes:
    with requests.get(url, stream=True, timeout=(5, 10)) as r:
        r.raise_for_status()
        buf = b""
        for trozo in r.iter_content(8192):
            buf += trozo
            ini = buf.find(b"\xff\xd8")
            fin = buf.find(b"\xff\xd9", ini + 2) if ini != -1 else -1
            if fin != -1:
                return buf[ini:fin + 2]
            if len(buf) > 3_000_000:
                break
    raise RuntimeError("la URL no devolvió un JPEG")


def capturar() -> bytes | None:
    """Foto de la cámara extra, o None si no hay. Nunca rompe el ciclo del vigía."""
    fuente = C.CAMARA_EXTRA
    if not fuente:
        return None
    try:
        with _lock:
            if fuente == "picam":
                return _picam()
            if fuente.startswith("/dev/"):
                return _usb(fuente)
            if fuente.startswith(("http://", "https://")):
                return _url(fuente)
        raise RuntimeError(f"CAMARA_EXTRA no reconocida: {fuente}")
    except Exception as ex:  # noqa: BLE001
        log.warning("Cámara extra sin imagen: %s", ex)
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    foto = capturar()
    if not foto:
        raise SystemExit(f"Sin imagen (CAMARA_EXTRA={C.CAMARA_EXTRA or 'vacío'}); mira el aviso de arriba")
    destino = C.DIR_CASOS / "prueba_camara_extra.jpg"
    destino.write_bytes(foto)
    print(f"✅ {len(foto) // 1024} KB guardados en {destino}")
