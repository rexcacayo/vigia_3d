"""PLANTILLA de adaptador de impresora.

Copia este fichero como `vigia/impresoras/<tu_tipo>.py`, rellena las funciones y pon
`PRINTER_TIPO=<tu_tipo>` en el .env. Comprueba que cumple el contrato con:

    ./venv/bin/python -m vigia.probar

Guía completa: docs/ADAPTADORES.md
"""
import logging
import os

import requests

from .. import config as C
from . import material_de

log = logging.getLogger("vigia.impresora.plantilla")

# ================================================================ 1. Contrato
# Nombre legible (sale en el log y en Telegram)
NOMBRE = "Mi impresora (firmware X)"

# Qué sabe hacer. Cada capacidad exige su función (ver POR_CAPACIDAD en __init__.py):
#   velocidad → poner_velocidad(pct)        flujo → poner_flujo(pct)
#   temp_boquilla → poner_temp_boquilla(c)  temp_cama → poner_temp_cama(c)
#   z_offset → poner_z_offset(mm)           ventilador → poner_ventilador(valor)
#   pausar → pausar()   reanudar → reanudar()   luz → encender_luz()
# Declara SOLO lo que hayas probado en tu máquina.
CAPACIDADES: set[str] = {"pausar", "reanudar"}

# Capacidades que nunca se aplican en modo "auto" (siempre piden permiso por Telegram)
SOLO_CON_PERMISO: set[str] = set()

# Se añade al prompt de Claude: describe la máquina y, sobre todo, su CÁMARA
DESCRIPCION = """\
## Máquina: Mi impresora
- Tipo (bedslinger / CoreXY), volumen, boquilla.
- Cámara: posición, ángulo, resolución, qué partes de la pieza se ven y cuáles no.
- Qué NO se puede cambiar en marcha."""

# ================================================================ 2. Conexión
IP = C.PRINTER_IP
TOKEN = os.getenv("MI_IMPRESORA_TOKEN", "")  # credenciales propias de tu adaptador
if not IP:
    raise RuntimeError("Plantilla: falta PRINTER_IP en el .env")


# ================================================================ 3. Obligatorias
def estado() -> dict:
    """Devuelve el estado normalizado. TODAS estas claves deben existir (usa None si no lo sabes)."""
    # d = requests.get(f"http://{IP}/api/status", timeout=8).json()
    d: dict = {}
    fichero = d.get("filename")
    return {
        "maquina": d.get("state"),                       # texto libre del firmware
        "imprimiendo": d.get("state") == "printing",     # bool: hay una impresión activa
        "pausada": d.get("state") == "paused",           # bool
        "fichero": fichero,
        "material": material_de(fichero),                # o el material que te dé la máquina
        "capa": {"actual": d.get("layer"), "total": d.get("layers")},
        "progreso_pct": d.get("progress"),               # 0-100
        "boquilla": {"actual": d.get("nozzle"), "objetivo": d.get("nozzle_target")},
        "cama": {"actual": d.get("bed"), "objetivo": d.get("bed_target")},
        "ajuste_velocidad_pct": d.get("speed_factor"),   # 100 = normal
        "ventilador_capa": d.get("fan"),                 # 0-100
        "z_offset": d.get("z_offset"),                   # mm
        "error": d.get("error") or None,
        "tiempo_impresion_s": d.get("elapsed"),
        # Opcional: "flujo_pct", "puerta", "luz", "velocidad_mm_s"
    }


def capturar() -> bytes:
    """Devuelve UN fotograma JPEG. Corto de tiempo y liberando la cámara al terminar."""
    r = requests.get(f"http://{IP}/webcam/?action=snapshot", timeout=(5, 10))
    r.raise_for_status()
    if r.content[:2] != b"\xff\xd8":
        raise RuntimeError("La cámara no devolvió un JPEG")
    return r.content


# ================================================================ 4. Opcionales (según CAPACIDADES)
def pausar() -> None:
    raise NotImplementedError


def reanudar() -> None:
    raise NotImplementedError


# def poner_velocidad(pct: int) -> None: ...
# def poner_flujo(pct: int) -> None: ...
# def poner_temp_boquilla(c: int) -> None: ...
# def poner_temp_cama(c: int) -> None: ...
# def poner_z_offset(mm: float) -> None: ...   # valor ABSOLUTO, no incremento
# def poner_ventilador(valor: int) -> None: ...
# def encender_luz() -> None: ...
