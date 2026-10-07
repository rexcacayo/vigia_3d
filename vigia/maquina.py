"""Carga el adaptador de impresora elegido en PRINTER_TIPO (por defecto, flashforge)."""
from . import config as C
from .impresoras import cargar

P = cargar(C.PRINTER_TIPO)
