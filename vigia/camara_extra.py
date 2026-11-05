"""Cámaras extra: una o varias vistas más para el diagnóstico (cenital, frontal, de la cama…).

Pensado para correr en la Raspberry con cámaras USB y/o la cámara de la propia Pi, pero
funciona igual en un PC con webcams.

En el .env:
    CAMARAS_EXTRA=superior=picam, frontal=/dev/v4l/by-id/usb-046d_C920_...-video-index0
Fuentes admitidas:
    picam            cámara CSI de la Raspberry (picam:1 = segunda CSI en Pi 5)
    /dev/video0      webcam USB (mejor la ruta estable /dev/v4l/by-id/…: no cambia al reiniciar)
    http(s)://…      URL que devuelve un JPEG o un stream MJPEG (otra Pi, cámara IP…)
Ajustes por cámara (opcionales; si no, se usan los CAMARA_EXTRA_* generales):
    CAMARA_<NOMBRE>_RESOLUCION=1280x960
    CAMARA_<NOMBRE>_ENFOQUE=3                 picam Module 3: dioptrías (≈ 100 / cm)
    CAMARA_<NOMBRE>_V4L2=focus_automatic_continuous=0,focus_absolute=40
    CAMARA_<NOMBRE>_DESCRIPCION=Encima de la tapa, mirando hacia abajo…
Compatibilidad: CAMARA_EXTRA=<fuente> equivale a CAMARAS_EXTRA=superior=<fuente>.

    python -m vigia.camara_extra            # foto de prueba de cada cámara configurada
    python -m vigia.camara_extra --listar   # qué cámaras ve el sistema
"""
from __future__ import annotations

import glob
import logging
import os
import re
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass, field

import requests

from . import config as C

log = logging.getLogger("vigia.camaras")

DESCRIPCIONES = {
    "superior": "Cámara encima de la tapa, mirando hacia abajo en diagonal a través del plástico: ve la "
                "cara superior de la pieza; reflejos o polvo de la tapa no son defectos.",
    "frontal": "Cámara frontal a la altura de la cama: ve la base, la primera capa y la adhesión.",
    "cama": "Cámara que mira la cama de cerca: ve la primera capa y el despegue de esquinas.",
}
_locks: dict[str, threading.Lock] = {}
_ajustadas: set[str] = set()


@dataclass
class Camara:
    nombre: str
    fuente: str
    resolucion: str = "1280x960"
    enfoque: str = ""
    v4l2: str = ""
    descripcion: str = ""
    errores: int = field(default=0, compare=False)


def _opcion(nombre: str, clave: str, defecto: str) -> str:
    return os.getenv(f"CAMARA_{nombre.upper()}_{clave}", "").strip() or defecto


def camaras() -> list[Camara]:
    """Lee la configuración en cada llamada (se puede cambiar sin reiniciar en las pruebas)."""
    pares = [p.strip() for p in C.CAMARAS_EXTRA.split(",") if p.strip()]
    if not pares and C.CAMARA_EXTRA:
        pares = [f"superior={C.CAMARA_EXTRA}"]
    lista = []
    for par in pares:
        nombre, _, fuente = par.partition("=")
        nombre = re.sub(r"[^a-z0-9_]", "", nombre.strip().lower()) or f"cam{len(lista) + 1}"
        if not fuente.strip():
            log.warning("Cámara «%s» sin fuente: se ignora", nombre)
            continue
        lista.append(Camara(
            nombre=nombre, fuente=fuente.strip(),
            resolucion=_opcion(nombre, "RESOLUCION", C.CAMARA_EXTRA_RESOLUCION),
            enfoque=_opcion(nombre, "ENFOQUE", C.CAMARA_EXTRA_ENFOQUE),
            v4l2=_opcion(nombre, "V4L2", C.CAMARA_EXTRA_V4L2),
            descripcion=_opcion(nombre, "DESCRIPCION", DESCRIPCIONES.get(nombre, C.CAMARA_EXTRA_DESCRIPCION))))
    return lista


def activa() -> bool:
    return bool(camaras())


def _ancho_alto(c: Camara) -> tuple[str, str]:
    a, _, h = c.resolucion.partition("x")
    return a or "1280", h or "960"


def _picam(c: Camara) -> bytes:
    exe = shutil.which("rpicam-still") or shutil.which("libcamera-still")
    if not exe:
        raise RuntimeError("no encuentro rpicam-still ni libcamera-still (¿Raspberry Pi OS?)")
    ancho, alto = _ancho_alto(c)
    orden = [exe, "-n", "-t", "800", "--width", ancho, "--height", alto, "-e", "jpg", "-o", "-"]
    _, _, indice = c.fuente.partition(":")
    if indice:
        orden += ["--camera", indice]
    if c.enfoque:
        orden += ["--autofocus-mode", "manual", "--lens-position", c.enfoque]
    r = subprocess.run(orden, capture_output=True, timeout=20, check=False)
    if r.stdout[:2] != b"\xff\xd8":
        raise RuntimeError(f"la cámara de la Pi no dio imagen: {r.stderr.decode(errors='replace')[-200:]}")
    return r.stdout


def _usb(c: Camara) -> bytes:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("falta ffmpeg (sudo apt install ffmpeg)")
    if c.v4l2 and c.fuente not in _ajustadas and shutil.which("v4l2-ctl"):
        r = subprocess.run(["v4l2-ctl", "-d", c.fuente, "-c", c.v4l2], capture_output=True, timeout=10, check=False)
        if r.returncode:
            log.warning("v4l2-ctl %s: %s", c.nombre, r.stderr.decode(errors="replace")[-200:])
        _ajustadas.add(c.fuente)
    ancho, alto = _ancho_alto(c)
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "v4l2", "-input_format", "mjpeg",
                        "-video_size", f"{ancho}x{alto}", "-i", c.fuente,
                        "-frames:v", "1", "-f", "image2", "-c:v", "mjpeg", "pipe:1"],
                       capture_output=True, timeout=20, check=False)
    if r.stdout[:2] != b"\xff\xd8":
        raise RuntimeError(f"la webcam no dio imagen: {r.stderr.decode(errors='replace')[-200:]}")
    return r.stdout


def _url(c: Camara) -> bytes:
    with requests.get(c.fuente, stream=True, timeout=(5, 10)) as r:
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


def capturar_una(c: Camara) -> bytes | None:
    lock = _locks.setdefault(c.fuente, threading.Lock())
    try:
        with lock:
            if c.fuente.startswith("picam"):
                return _picam(c)
            if c.fuente.startswith("/dev/"):
                return _usb(c)
            if c.fuente.startswith(("http://", "https://")):
                return _url(c)
        raise RuntimeError(f"fuente no reconocida: {c.fuente}")
    except Exception as ex:  # noqa: BLE001 — una cámara caída no para la vigilancia
        log.warning("Cámara «%s» sin imagen: %s", c.nombre, ex)
        return None


def capturar_todas() -> dict[str, bytes]:
    """{nombre: jpeg} de cada cámara extra que haya respondido (en paralelo)."""
    lista = camaras()
    if not lista:
        return {}
    resultado: dict[str, bytes] = {}
    hilos = []
    for c in lista:
        def tomar(cam=c):
            foto = capturar_una(cam)
            if foto:
                resultado[cam.nombre] = foto
        h = threading.Thread(target=tomar, daemon=True)
        h.start()
        hilos.append(h)
    for h in hilos:
        h.join(25)
    return {c.nombre: resultado[c.nombre] for c in lista if c.nombre in resultado}


def descripcion(nombre: str) -> str:
    for c in camaras():
        if c.nombre == nombre:
            return c.descripcion
    return ""


def listar() -> str:
    """Lo que ve el sistema, para saber qué poner en CAMARAS_EXTRA."""
    lineas = []
    for ruta in sorted(glob.glob("/dev/v4l/by-id/*-video-index0")):
        lineas.append(f"USB  {ruta}  →  {os.path.realpath(ruta)}")
    if not lineas:
        lineas += [f"USB  {d}" for d in sorted(glob.glob("/dev/video*"))]
    exe = shutil.which("rpicam-hello") or shutil.which("libcamera-hello")
    if exe:
        r = subprocess.run([exe, "--list-cameras"], capture_output=True, text=True, timeout=20, check=False)
        for linea in (r.stdout + r.stderr).splitlines():
            if re.match(r"^\s*\d+\s*:", linea):
                lineas.append(f"CSI  picam:{linea.strip().split(':')[0]}  {linea.strip()}")
    return "\n".join(lineas) or "No veo ninguna cámara."


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if "--listar" in sys.argv:
        print(listar())
        raise SystemExit(0)
    if not camaras():
        raise SystemExit("No hay cámaras extra configuradas (CAMARAS_EXTRA en el .env).\n" + listar())
    fotos = capturar_todas()
    for c in camaras():
        if c.nombre in fotos:
            destino = C.DIR_CASOS / f"prueba_camara_{c.nombre}.jpg"
            destino.write_bytes(fotos[c.nombre])
            print(f"✅ {c.nombre} ({c.fuente}): {len(fotos[c.nombre]) // 1024} KB → {destino}")
        else:
            print(f"❌ {c.nombre} ({c.fuente}): sin imagen (mira el aviso de arriba)")
