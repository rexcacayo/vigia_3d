"""Motor de correcciones: Claude PROPONE, este código DECIDE con reglas fijas.

Ninguna acción sale de aquí sin pasar por:
- lista blanca de tipos y límites por material,
- confianza mínima y persistencia (misma propuesta en 2 diagnósticos seguidos),
- máximo de cambios por impresión y espera entre cambios,
- reversión automática de velocidad/ventilador cuando todo vuelve a ir bien.
"""
import itertools
import logging
import time
from dataclasses import dataclass, field

from . import config as C
from .impresoras import POR_CAPACIDAD
from .maquina import P

log = logging.getLogger("vigia.correcciones")

TEMP_BOQUILLA = {"PLA": (190, 230), "PETG": (220, 260), "PCTG": (230, 265),
                 "ASA": (235, 265), "ABS": (230, 265), "TPU": (200, 240)}
TEMP_CAMA = {"PLA": (45, 70), "PETG": (60, 90), "PCTG": (60, 90),
             "ASA": (80, 110), "ABS": (80, 110), "TPU": (30, 60)}
SIN_VENTILADOR = {"ASA", "ABS", "PC"}
REVERSIBLES = {"velocidad", "ventilador", "flujo"}

_ids = itertools.count(1)


@dataclass
class Propuesta:
    tipo: str
    actual: float
    objetivo: float
    motivo: str
    id: str = field(default_factory=lambda: f"c{next(_ids)}")
    ts: float = field(default_factory=time.time)

    def texto(self) -> str:
        unidades = {"velocidad": " %", "flujo": " %", "temp_boquilla": " °C", "temp_cama": " °C",
                    "z_offset": " mm", "ventilador": ""}
        u = unidades.get(self.tipo, "")
        nombre = {"velocidad": "Velocidad", "flujo": "Flujo", "temp_boquilla": "Temperatura boquilla",
                  "temp_cama": "Temperatura cama", "z_offset": "Z offset",
                  "ventilador": "Ventilador de capa"}.get(self.tipo, self.tipo)
        return f"{nombre}: {self.actual:g}{u} → {self.objetivo:g}{u}"


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


class Motor:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.cambios: list[Propuesta] = []
        self.base: dict[str, float] = {}       # valor original de cada parámetro tocado
        self.ultima_tipo: tuple | None = None  # (tipo, signo) del diagnóstico anterior
        self.ultimo_cambio = 0.0
        self.ok_seguidos = 0
        self.pendientes: dict[str, Propuesta] = {}

    # ------------------------------------------------------------ decidir
    def evaluar(self, diag: dict, estado: dict) -> Propuesta | None:
        if C.CORRECCION_MODO == "off":
            return None
        acc = diag.get("accion") or {}
        tipo, delta = acc.get("tipo"), acc.get("delta")

        if tipo in (None, "ninguna", "pausar") or delta in (None, 0):
            self.ultima_tipo = None
            return None
        if tipo not in P.CAPACIDADES:
            log.info("La impresora no permite '%s'", tipo)
            return None
        try:
            delta = float(delta)
        except (TypeError, ValueError):
            return None

        firma = (tipo, delta > 0)
        persistente = firma == self.ultima_tipo
        self.ultima_tipo = firma

        if diag.get("confianza", 0) < C.CORRECCION_CONFIANZA:
            log.info("Propuesta %s descartada: confianza baja", tipo)
            return None
        if not persistente:
            log.info("Propuesta %s anotada; espero a que se repita", tipo)
            return None
        if len(self.cambios) >= C.CORRECCION_MAX:
            log.info("Máximo de correcciones alcanzado")
            return None
        if time.time() - self.ultimo_cambio < C.CORRECCION_ESPERA_S:
            log.info("Esperando entre correcciones")
            return None

        prop = self._calcular(tipo, delta, estado, acc.get("motivo") or diag.get("explicacion", ""))
        if prop:
            self.pendientes[prop.id] = prop
        return prop

    def _calcular(self, tipo: str, delta: float, e: dict, motivo: str) -> Propuesta | None:
        mat = (e.get("material") or "").upper()
        capa = (e.get("capa") or {}).get("actual") or 0

        if tipo == "velocidad":
            actual = float(e.get("ajuste_velocidad_pct") or 100)
            base = self.base.get(tipo, actual)
            obj = _clamp(actual + _clamp(delta, -30, 10), 60, 110)
            obj = _clamp(obj, base - 40, base + 10)
        elif tipo == "temp_boquilla":
            actual = float((e.get("boquilla") or {}).get("objetivo") or 0)
            if not actual:
                return None
            base = self.base.get(tipo, actual)
            lo, hi = TEMP_BOQUILLA.get(mat, (180, 265))
            obj = _clamp(actual + _clamp(delta, -5, 5), max(lo, base - 10), min(hi, base + 10))
        elif tipo == "temp_cama":
            actual = float((e.get("cama") or {}).get("objetivo") or 0)
            if not actual:
                return None
            base = self.base.get(tipo, actual)
            lo, hi = TEMP_CAMA.get(mat, (40, 110))
            obj = _clamp(actual + _clamp(delta, -5, 5), max(lo, base - 10), min(hi, base + 10))
        elif tipo == "z_offset":
            if capa > 3:
                log.info("Z offset solo en capas 1-3 (capa %s)", capa)
                return None
            actual = float(e.get("z_offset") or 0)
            base = self.base.get(tipo, actual)
            obj = round(_clamp(actual + _clamp(delta, -0.02, 0.02), base - 0.10, base + 0.10), 3)
        elif tipo == "flujo":
            actual = float(e.get("flujo_pct") or 100)
            base = self.base.get(tipo, actual)
            obj = _clamp(actual + _clamp(delta, -5, 5), max(85, base - 10), min(115, base + 10))
        elif tipo == "ventilador":
            if mat in SIN_VENTILADOR:
                log.info("Ventilador vetado para %s", mat)
                return None
            actual = float(e.get("ventilador_capa") or 0)
            base = self.base.get(tipo, actual)
            obj = _clamp(actual + _clamp(delta, -20, 20), 0, 100)
            obj = _clamp(obj, base - 30, base + 40)
        else:
            return None

        if abs(obj - actual) < 1e-6:
            return None
        return Propuesta(tipo, actual, obj, motivo)

    def puede_auto(self, prop: Propuesta) -> bool:
        return C.CORRECCION_MODO == "auto" and prop.tipo not in P.SOLO_CON_PERMISO

    # ------------------------------------------------------------ actuar
    def aplicar(self, prop: Propuesta) -> str:
        getattr(P, POR_CAPACIDAD[prop.tipo])(prop.objetivo)
        self.base.setdefault(prop.tipo, prop.actual)
        self.cambios.append(prop)
        self.ultimo_cambio = time.time()
        self.ok_seguidos = 0
        self.pendientes.pop(prop.id, None)
        log.warning("Corrección aplicada: %s", prop.texto())
        return prop.texto()

    def tras_diagnostico(self, diag: dict) -> list[str]:
        """Cuenta diagnósticos 'ok' seguidos y revierte lo reversible si toca."""
        if diag.get("gravedad") == "ok" and diag.get("estado") == "ok":
            self.ok_seguidos += 1
        else:
            self.ok_seguidos = 0
            return []
        if self.ok_seguidos < C.REVERTIR_TRAS_OK:
            return []
        mensajes = []
        for tipo in list(self.base):
            if tipo not in REVERSIBLES:
                continue
            original = self.base.pop(tipo)
            try:
                getattr(P, POR_CAPACIDAD[tipo])(original)
                mensajes.append(f"↩️ {tipo} devuelto a {original:g}")
            except Exception as e:  # noqa: BLE001
                mensajes.append(f"⚠️ No pude revertir {tipo}: {e}")
        self.ok_seguidos = 0
        return mensajes
