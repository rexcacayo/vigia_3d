"""Carga el adaptador de impresora elegido en PRINTER_TIPO (por defecto, flashforge).

Además envuelve capturar() con un candado: muchas cámaras (p. ej. la de Flashforge)
solo admiten un espectador, y el bucle y las órdenes de Telegram (/foto, preguntas)
podrían pedir foto a la vez.
"""
import threading

from . import config as C
from .impresoras import cargar

P = cargar(C.PRINTER_TIPO)

_candado_camara = threading.Lock()
_capturar_original = P.capturar


def _capturar_con_candado() -> bytes:
    with _candado_camara:
        return _capturar_original()


P.capturar = _capturar_con_candado
