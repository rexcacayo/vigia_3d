"""Perfil del laminado: lee del .3mf de OrcaSlicer los parámetros con los que se imprime.

El vigía busca el fichero que está imprimiendo la máquina (por su nombre) en
DIR_LAMINADOS y extrae las claves que importan para diagnosticar: temperaturas,
velocidades, ventilador, retracción, capa… Así el diagnóstico y el informe pueden
decir «el voladizo se riza y tienes `fan_max_speed` = 25 %» en vez de hablar en general.
"""
from __future__ import annotations

import json
import logging
import re
import zipfile
from pathlib import Path

from . import config as C

log = logging.getLogger("vigia.perfil")

# Claves de OrcaSlicer que se pasan al diagnóstico (agrupadas para leerlas mejor)
CLAVES = {
    "perfiles": ("printer_settings_id", "filament_settings_id", "print_settings_id", "filament_type",
                 "filament_vendor", "nozzle_diameter"),
    "temperaturas": ("nozzle_temperature_initial_layer", "nozzle_temperature",
                     "hot_plate_temp_initial_layer", "hot_plate_temp", "textured_plate_temp",
                     "chamber_temperature"),
    "capas": ("layer_height", "initial_layer_print_height", "wall_loops", "top_shell_layers",
              "bottom_shell_layers", "sparse_infill_density", "sparse_infill_pattern", "seam_position"),
    "velocidades": ("initial_layer_speed", "outer_wall_speed", "inner_wall_speed", "sparse_infill_speed",
                    "top_surface_speed", "travel_speed", "filament_max_volumetric_speed",
                    "default_acceleration", "outer_wall_acceleration"),
    "flujo": ("filament_flow_ratio", "enable_pressure_advance", "pressure_advance"),
    "retraccion": ("retraction_length", "retraction_speed", "deretraction_speed", "z_hop", "z_hop_types",
                   "wipe", "retract_when_changing_layer"),
    "ventilador": ("fan_min_speed", "fan_max_speed", "close_fan_the_first_x_layers", "overhang_fan_speed",
                   "slow_down_layer_time", "additional_cooling_fan_speed", "reduce_fan_stop_start_freq"),
    "soportes_adhesion": ("enable_support", "support_type", "support_threshold_angle", "brim_type",
                          "brim_width", "skirt_loops"),
}


def _valor(v):
    """Orca guarda casi todo como listas de strings ("['240']"): simplifica a un valor."""
    if isinstance(v, list):
        v = v[0] if len(set(map(str, v))) == 1 else v
    return v


def _desde_gcode(texto: str) -> dict:
    """Plan B: el bloque «; key = value» que Orca escribe al final del G-code."""
    datos = {}
    for m in re.finditer(r"^; ([a-z_0-9]+) = (.*)$", texto, re.M):
        datos[m.group(1)] = m.group(2).strip()
    return datos


def leer(ruta: Path) -> dict:
    """Devuelve {grupo: {clave: valor}} con lo que se encuentre en el .3mf."""
    crudo: dict = {}
    with zipfile.ZipFile(ruta) as z:
        nombres = z.namelist()
        if "Metadata/project_settings.config" in nombres:
            try:
                crudo = json.loads(z.read("Metadata/project_settings.config"))
            except ValueError:
                crudo = {}
        if not crudo:
            for n in nombres:
                if n.endswith(".gcode"):
                    texto = z.read(n)[-200_000:].decode("utf-8", "ignore")  # el bloque va al final
                    crudo = _desde_gcode(texto)
                    break
    perfil = {}
    for grupo, claves in CLAVES.items():
        sub = {k: _valor(crudo[k]) for k in claves if k in crudo}
        if sub:
            perfil[grupo] = sub
    return perfil


def buscar(fichero: str | None) -> Path | None:
    """Busca en DIR_LAMINADOS el .3mf que imprime la máquina (por nombre de fichero)."""
    if not (fichero and C.DIR_LAMINADOS and C.DIR_LAMINADOS.exists()):
        return None
    nombre = Path(fichero).name
    candidatos = [p for p in C.DIR_LAMINADOS.rglob("*.3mf") if p.name == nombre]
    if not candidatos:  # p. ej. la máquina quita «.3mf» o el slicer añade «.gcode»
        base = nombre.split(".")[0]
        candidatos = [p for p in C.DIR_LAMINADOS.rglob("*.3mf") if p.name.split(".")[0] == base]
    return max(candidatos, key=lambda p: p.stat().st_mtime) if candidatos else None


def del_trabajo(fichero: str | None) -> dict | None:
    ruta = buscar(fichero)
    if not ruta:
        if C.DIR_LAMINADOS:
            log.info("Sin laminado para %s en %s", fichero, C.DIR_LAMINADOS)
        return None
    try:
        perfil = leer(ruta)
    except (zipfile.BadZipFile, OSError) as ex:
        log.warning("No pude leer el perfil de %s: %s", ruta, ex)
        return None
    log.info("Perfil del laminado leído de %s (%s grupos)", ruta.name, len(perfil))
    return perfil or None


def texto(perfil: dict | None) -> str:
    if not perfil:
        return ""
    return "Perfil del laminado (OrcaSlicer): " + json.dumps(perfil, ensure_ascii=False)
