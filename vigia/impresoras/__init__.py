"""Adaptadores de impresora.

Cada fichero de esta carpeta (salvo los que empiezan por "_" y `plantilla.py`) es un
adaptador que traduce el "idioma" de una familia de impresoras al contrato común del
vigía. El adaptador activo se elige con PRINTER_TIPO en el .env.

Contrato mínimo de un adaptador → ver CONTRIBUIR.md y plantilla.py.
"""
import importlib
import re
from types import ModuleType

MATERIALES = ("PETG", "PCTG", "PLA", "ASA", "ABS", "TPU", "PC", "PA", "PVA", "HIPS")

# Funciones obligatorias y la capacidad que activa cada función opcional
OBLIGATORIAS = ("estado", "capturar")
POR_CAPACIDAD = {
    "velocidad": "poner_velocidad",
    "temp_boquilla": "poner_temp_boquilla",
    "temp_cama": "poner_temp_cama",
    "z_offset": "poner_z_offset",
    "ventilador": "poner_ventilador",
    "flujo": "poner_flujo",
    "pausar": "pausar",
    "reanudar": "reanudar",
    "luz": "encender_luz",
}

# Claves que debe devolver estado()
CLAVES_ESTADO = ("maquina", "imprimiendo", "pausada", "fichero", "material", "capa",
                 "progreso_pct", "boquilla", "cama", "ajuste_velocidad_pct",
                 "ventilador_capa", "z_offset", "error", "tiempo_impresion_s")


def material_de(fichero: str | None) -> str | None:
    """Deduce el material del nombre del fichero (p. ej. 'pieza_PETG_2h.gcode' → 'PETG')."""
    if not fichero:
        return None
    tokens = re.split(r"[^A-Za-z0-9]+", fichero.upper())
    for m in MATERIALES:
        if m in tokens:
            return m
    return None


def validar(mod: ModuleType) -> list[str]:
    """Devuelve la lista de problemas del adaptador (vacía si cumple el contrato)."""
    problemas = []
    for attr in ("NOMBRE", "CAPACIDADES", "DESCRIPCION"):
        if not hasattr(mod, attr):
            problemas.append(f"falta la constante {attr}")
    for f in OBLIGATORIAS:
        if not callable(getattr(mod, f, None)):
            problemas.append(f"falta la función {f}()")
    for cap in getattr(mod, "CAPACIDADES", set()):
        f = POR_CAPACIDAD.get(cap)
        if f and not callable(getattr(mod, f, None)):
            problemas.append(f"declara '{cap}' pero no define {f}()")
    return problemas


def cargar(tipo: str) -> ModuleType:
    if tipo.startswith("_") or tipo == "plantilla" or not re.fullmatch(r"[a-z0-9_]+", tipo):
        raise ValueError(f"PRINTER_TIPO no válido: {tipo!r}")
    mod = importlib.import_module(f"{__name__}.{tipo}")
    if not hasattr(mod, "SOLO_CON_PERMISO"):
        mod.SOLO_CON_PERMISO = set()
    problemas = validar(mod)
    if problemas:
        raise RuntimeError(f"Adaptador '{tipo}' incompleto: " + "; ".join(problemas))
    return mod
