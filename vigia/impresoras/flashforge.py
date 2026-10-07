"""Adaptador: Flashforge Adventurer 5M / 5M Pro (firmware de serie) por su API local.

- Estado y control: HTTP en el puerto 8898 (requiere nº de serie + código de acceso).
- Vídeo: MJPEG en el 8080. Solo admite UN espectador a la vez y no tiene snapshot.
- Pausa de respaldo: protocolo TCP clásico en el 8899 (~M25 / ~M24).
"""
import logging
import os
import socket

import requests

from .. import config as C
from . import material_de

log = logging.getLogger("vigia.impresora.flashforge")

# ---------------------------------------------------------------- contrato
NOMBRE = "Flashforge Adventurer 5M Pro (firmware de serie)"

CAPACIDADES = {"velocidad", "temp_boquilla", "temp_cama", "z_offset", "ventilador",
               "pausar", "reanudar", "luz"}
SOLO_CON_PERMISO = {"ventilador"}  # escala del ventilador sin confirmar en este firmware

DESCRIPCION = """\
## Máquina: Flashforge Adventurer 5M Pro
- CoreXY cerrada, cama 220×220 mm, boquilla 0,4 mm, firmware de serie.
- Cámara interna fija, gran angular, ~640×480, mira **de frente y algo desde abajo**.
- Ves la pieza **de lado**: la cara superior de piezas pequeñas apenas se ve.
- Detalles de 1–3 mm son pocos píxeles; el cabezal tapa a menudo la zona que imprime.
- No se puede tocar en marcha: flujo, retracción ni pressure advance."""

# ---------------------------------------------------------------- conexión
IP = C.PRINTER_IP
SN = os.getenv("PRINTER_SN", "")
CODIGO = os.getenv("PRINTER_CHECK_CODE", "")
if not (IP and SN and CODIGO):
    raise RuntimeError("Flashforge: faltan PRINTER_IP, PRINTER_SN o PRINTER_CHECK_CODE en el .env")

API = f"http://{IP}:8898"
CAMARA = f"http://{IP}:8080/?action=stream"


def _auth() -> dict:
    return {"serialNumber": SN, "checkCode": CODIGO}


def detalle() -> dict:
    r = requests.post(f"{API}/detail", json=_auth(), timeout=8)
    r.raise_for_status()
    j = r.json()
    if j.get("code") != 0:
        raise RuntimeError(f"API /detail: {j.get('message')}")
    return j["detail"]


def control(cmd: str, args: dict) -> None:
    body = {**_auth(), "payload": {"cmd": cmd, "args": args}}
    r = requests.post(f"{API}/control", json=body, timeout=8)
    r.raise_for_status()
    j = r.json()
    if j.get("code") != 0:
        raise RuntimeError(f"API /control {cmd}: {j.get('message')}")


def estado() -> dict:
    d = detalle()
    fichero = d.get("printFileName")
    return {
        "maquina": d.get("status"),
        "imprimiendo": d.get("status") == "printing",
        "pausada": d.get("status") == "paused",
        "fichero": fichero,
        "material": material_de(fichero),
        "capa": {"actual": d.get("printLayer"), "total": d.get("targetPrintLayer")},
        "progreso_pct": round(100 * (d.get("printProgress") or 0), 1),
        "boquilla": {"actual": d.get("rightTemp"), "objetivo": d.get("rightTargetTemp")},
        "cama": {"actual": d.get("platTemp"), "objetivo": d.get("platTargetTemp")},
        "velocidad_mm_s": d.get("currentPrintSpeed"),
        "ajuste_velocidad_pct": d.get("printSpeedAdjust"),
        "ventilador_capa": d.get("coolingFanSpeed"),
        "z_offset": d.get("zAxisCompensation"),
        "puerta": d.get("doorStatus"),
        "luz": d.get("lightStatus"),
        "error": d.get("errorCode") or None,
        "tiempo_impresion_s": d.get("printDuration"),
    }


# ---------------------------------------------------------------- cámara / luz
def encender_camara() -> None:
    control("streamCtrl_cmd", {"action": "open"})


def encender_luz() -> None:
    control("lightControl_cmd", {"status": "open"})


def capturar() -> bytes:
    """Saca un JPEG del stream y suelta la cámara al momento."""
    try:
        encender_camara()
    except Exception as e:  # noqa: BLE001
        log.debug("No se pudo pedir el stream: %s", e)
    with requests.get(CAMARA, stream=True, timeout=(5, 10)) as r:
        r.raise_for_status()
        buf = b""
        for trozo in r.iter_content(8192):
            buf += trozo
            ini = buf.find(b"\xff\xd8")
            if ini != -1:
                fin = buf.find(b"\xff\xd9", ini + 2)
                if fin != -1:
                    return buf[ini:fin + 2]
            if len(buf) > 3_000_000:
                break
    raise RuntimeError("No se pudo extraer un fotograma del stream")


# ---------------------------------------------------------------- ajustes
def poner_velocidad(pct: int) -> None:
    control("printerCtl_cmd", {"speed": int(pct)})


def poner_temp_boquilla(c: int) -> None:
    control("temperatureCtl_cmd", {"rightNozzle": int(c)})


def poner_temp_cama(c: int) -> None:
    control("temperatureCtl_cmd", {"platform": int(c)})


def poner_z_offset(mm: float) -> None:
    control("printerCtl_cmd", {"zAxisCompensation": round(float(mm), 3)})


def poner_ventilador(valor: int) -> None:
    """Experimental: la escala (0-100 o 0-255) no está confirmada para este firmware."""
    control("printerCtl_cmd", {"coolingFan": int(valor)})


# ---------------------------------------------------------------- trabajo
def _tcp(cmd: str) -> str:
    with socket.create_connection((IP, 8899), timeout=5) as sk:
        def enviar(c: str) -> str:
            sk.sendall(f"~{c}\r\n".encode())
            buf = b""
            while not buf.rstrip().endswith(b"ok"):
                trozo = sk.recv(4096)
                if not trozo:
                    break
                buf += trozo
            return buf.decode(errors="ignore")
        enviar("M601 S1")
        resp = enviar(cmd)
        try:
            enviar("M602")
        except OSError:
            pass
        return resp


def _trabajo(accion: str, gcode_respaldo: str) -> None:
    try:
        control("jobCtl_cmd", {"jobID": "", "action": accion})
    except Exception as e:  # noqa: BLE001
        log.warning("jobCtl %s falló (%s); uso TCP %s", accion, e, gcode_respaldo)
        _tcp(gcode_respaldo)


def pausar() -> None:
    _trabajo("pause", "M25")


def reanudar() -> None:
    _trabajo("continue", "M24")
