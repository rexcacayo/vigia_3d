# Cómo crear un adaptador de impresora

Un adaptador es **un fichero Python** en `vigia/impresoras/` que traduce el idioma de una
familia de impresoras al contrato común del vigía. Es lo único que hay que escribir para
soportar otra máquina: la visión, la skill, las reglas y Telegram no cambian.

## Pasos

```bash
cp vigia/impresoras/plantilla.py vigia/impresoras/klipper.py   # 1. parte de la plantilla
# 2. rellénalo (ver contrato abajo)
echo 'PRINTER_TIPO=klipper' >> .env                             # 3. actívalo
./venv/bin/python -m vigia.probar                               # 4. verifícalo (solo lee)
./venv/bin/python -m vigia.probar --claude                      # 5. con un diagnóstico real
./arrancar.sh                                                   # 6. a vigilar
```

El nombre del fichero es el valor de `PRINTER_TIPO`: solo minúsculas, números y `_`.

## El contrato

### Constantes obligatorias
| Constante | Tipo | Para qué |
|---|---|---|
| `NOMBRE` | `str` | Nombre legible (log y Telegram) |
| `CAPACIDADES` | `set[str]` | Lo que sabe hacer. Cada capacidad exige su función (tabla siguiente) |
| `DESCRIPCION` | `str` (Markdown) | Se añade al prompt de Claude: máquina y, sobre todo, **cómo es la cámara y qué ve** |
| `SOLO_CON_PERMISO` | `set[str]` *(opcional)* | Capacidades que nunca se aplican en modo `auto` |

### Funciones
| Función | Obligatoria | Capacidad | Debe… |
|---|---|---|---|
| `estado() -> dict` | ✅ | — | Devolver el estado normalizado (ver abajo). Rápida, con `timeout` |
| `capturar() -> bytes` | ✅ | — | Devolver **un** JPEG y soltar la cámara. Con `timeout` |
| `pausar()` | | `pausar` | Pausar la impresión |
| `reanudar()` | | `reanudar` | Reanudarla |
| `poner_velocidad(pct)` | | `velocidad` | Velocidad global en % (100 = normal) |
| `poner_flujo(pct)` | | `flujo` | Flujo en % (100 = normal) |
| `poner_temp_boquilla(c)` | | `temp_boquilla` | Temperatura objetivo de boquilla en °C |
| `poner_temp_cama(c)` | | `temp_cama` | Temperatura objetivo de cama en °C |
| `poner_z_offset(mm)` | | `z_offset` | Z offset **absoluto** en mm (no incremento) |
| `poner_ventilador(valor)` | | `ventilador` | Ventilador de capa, 0–100 |
| `encender_luz()` | | `luz` | Encender la luz de la cámara |

Si una capacidad está en `CAPACIDADES` pero falta su función, el vigía no arranca y te
dice qué falta.

### Claves de `estado()`
Todas deben existir (usa `None` si tu máquina no lo da):

| Clave | Tipo | Ejemplo |
|---|---|---|
| `maquina` | str | `"printing"` (texto del firmware) |
| `imprimiendo` | bool | `True` si hay una impresión **activa** (no pausada) |
| `pausada` | bool | `True` si está en pausa |
| `fichero` | str | `"pieza_PETG_2h.gcode"` |
| `material` | str | `"PETG"` (usa `material_de(fichero)` si la máquina no lo sabe) |
| `capa` | dict | `{"actual": 120, "total": 400}` |
| `progreso_pct` | float | `31.5` (0–100) |
| `boquilla` | dict | `{"actual": 240.1, "objetivo": 240}` |
| `cama` | dict | `{"actual": 70.0, "objetivo": 70}` |
| `ajuste_velocidad_pct` | number | `100` |
| `ventilador_capa` | number | `40` (0–100) |
| `z_offset` | float | `0.025` |
| `error` | str \| None | código de error o `None` |
| `tiempo_impresion_s` | int | segundos impresos |

Opcionales que el vigía aprovecha si existen: `flujo_pct`, `puerta`, `luz`, `velocidad_mm_s`.

## Reglas de oro
1. **Declara solo lo que hayas probado** en tu máquina. Mejor pocas capacidades fiables.
2. **Timeouts siempre** (`requests` con `timeout=`). Una llamada colgada congela el vigía.
3. **Valores absolutos**: `poner_velocidad(80)` deja la velocidad en 80 %, no le resta 80.
4. **Lanza excepción si algo falla**: el vigía la captura, la registra y te avisa.
5. **Nunca cancelar.** El contrato no incluye cancelar a propósito.
6. **Cámara de un solo cliente** (como Flashforge): conecta, coge un fotograma y suelta.
   Explícalo en `DESCRIPCION` si limita lo que se ve.
7. **Credenciales** en el `.env` con nombres propios (`MIMARCA_TOKEN`), leídas con
   `os.getenv`. Nunca en el código.
8. **Unidades del vigía**: °C, mm, % (0–100). Convierte en el adaptador si la máquina usa
   otras (p. ej. ventilador 0–255).

## Ejemplo orientativo: Klipper / Moonraker

Esbozo **sin probar**, como punto de partida (Moonraker en el puerto 7125):

```python
import requests
from .. import config as C
from . import material_de

NOMBRE = "Klipper + Moonraker"
CAPACIDADES = {"velocidad", "flujo", "temp_boquilla", "temp_cama", "z_offset",
               "ventilador", "pausar", "reanudar"}
DESCRIPCION = "## Máquina: Klipper\n- Describe aquí tu impresora y su cámara."
BASE = f"http://{C.PRINTER_IP}:7125"


def _gcode(script: str) -> None:
    requests.post(f"{BASE}/printer/gcode/script", params={"script": script}, timeout=10).raise_for_status()


def estado() -> dict:
    q = "print_stats&virtual_sdcard&extruder&heater_bed&gcode_move&fan"
    s = requests.get(f"{BASE}/printer/objects/query?{q}", timeout=8).json()["result"]["status"]
    ps, gm = s["print_stats"], s["gcode_move"]
    info = ps.get("info") or {}
    return {
        "maquina": ps["state"], "imprimiendo": ps["state"] == "printing",
        "pausada": ps["state"] == "paused", "fichero": ps.get("filename"),
        "material": material_de(ps.get("filename")),
        "capa": {"actual": info.get("current_layer"), "total": info.get("total_layer")},
        "progreso_pct": round(100 * s["virtual_sdcard"]["progress"], 1),
        "boquilla": {"actual": s["extruder"]["temperature"], "objetivo": s["extruder"]["target"]},
        "cama": {"actual": s["heater_bed"]["temperature"], "objetivo": s["heater_bed"]["target"]},
        "ajuste_velocidad_pct": round(gm["speed_factor"] * 100),
        "flujo_pct": round(gm["extrude_factor"] * 100),
        "ventilador_capa": round(s["fan"]["speed"] * 100),
        "z_offset": gm["homing_origin"][2],
        "error": None, "tiempo_impresion_s": int(ps.get("print_duration") or 0),
    }


def capturar() -> bytes:
    r = requests.get(f"http://{C.PRINTER_IP}/webcam/?action=snapshot", timeout=(5, 10))
    r.raise_for_status()
    return r.content


def poner_velocidad(pct): _gcode(f"M220 S{int(pct)}")
def poner_flujo(pct): _gcode(f"M221 S{int(pct)}")
def poner_temp_boquilla(c): _gcode(f"M104 S{int(c)}")
def poner_temp_cama(c): _gcode(f"M140 S{int(c)}")
def poner_z_offset(mm): _gcode(f"SET_GCODE_OFFSET Z={mm:.3f} MOVE=1")
def poner_ventilador(v): _gcode(f"M106 S{round(v * 2.55)}")
def pausar(): requests.post(f"{BASE}/printer/print/pause", timeout=10).raise_for_status()
def reanudar(): requests.post(f"{BASE}/printer/print/resume", timeout=10).raise_for_status()
```

## Checklist antes de compartir tu adaptador
- [ ] `python -m vigia.probar` acaba en **TODO OK ✅** con tu impresora
- [ ] `python -m vigia.probar --claude` da un diagnóstico con sentido
- [ ] Cada capacidad declarada probada a mano al menos una vez
- [ ] `DESCRIPCION` explica la cámara (ángulo, resolución, qué no se ve)
- [ ] Variables nuevas documentadas en `docs/CONFIGURACION.md` y `.env.example`
- [ ] Fila nueva en `docs/COMPATIBILIDAD.md`
- [ ] `python -m tests.simulacion` sigue en **TODO OK ✅**
