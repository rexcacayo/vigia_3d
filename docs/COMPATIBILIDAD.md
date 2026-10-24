# Compatibilidad del Vigía

El vigía tiene dos partes:

- **Independiente de la impresora**: visión con Claude, skill, reglas de corrección,
  Telegram e informes.
- **Adaptador de impresora** (`vigia/impresoras/<tipo>.py`): la única pieza que habla con
  la máquina. Para soportar otra familia basta con escribir otro adaptador: ver
  [ADAPTADORES.md](ADAPTADORES.md).

## Impresoras

| Impresora / firmware | Estado | Adaptador | Cámara |
|---|---|---|---|
| **Flashforge Adventurer 5M Pro**, firmware de serie 5.1.9 | ✅ Probada | `flashforge` | Interna, MJPEG :8080 |
| Flashforge Adventurer 5M, firmware de serie | 🟡 Debería funcionar (misma API), sin probar | `flashforge` | Necesita cámara USB compatible |
| Flashforge AD5X / Creator 5 / Creator 5 Pro | 🟡 Misma familia de API, sin probar | `flashforge` | Según modelo |
| **Anycubic Kobra 3 / 3 Max / 3 V2 / S1 / S1 Max**, firmware de serie, modo LAN | 🧪 Implementado, pendiente de probar en la Kobra 3 Max | `anycubic` | Accesorio, HTTP-FLV :18088 (necesita ffmpeg) |
| Cualquier impresora con **Klipper + Moonraker** (Creality K1, Qidi, Voron, Sovol, AD5M con Forge-X/ZMod…) | 🔜 Planificado | `klipper` (pendiente, hay un esbozo en ADAPTADORES.md) | Webcam de Moonraker/crowsnest |
| OctoPrint (Prusa, Ender… con Raspberry) | 💡 Posible | pendiente | Webcam de OctoPrint |
| Bambu Lab en modo LAN | 💡 Posible (MQTT) | pendiente | Stream propio |

---

## API Flashforge (firmware de serie)

### Requisitos
- Impresora y PC en la misma red local.
- **Número de serie** (`PRINTER_SN`) y **código de acceso** (`PRINTER_CHECK_CODE`):
  en la pantalla, *Ajustes → Red*, aparece como "ID de la impresora".
- La cámara admite **un solo espectador**: si la pestaña *Dispositivo* de Orca está
  abierta, el vigía no puede ver.

### Puertos
| Puerto | Protocolo | Uso |
|---|---|---|
| 8898 | HTTP + JSON (`POST /detail`, `POST /control`) | Estado y control. Pide nº de serie + código |
| 8080 | MJPEG (`/?action=stream`) | Vídeo. **No tiene snapshot**, solo stream |
| 8899 | TCP, comandos `~Mxxx` | Protocolo clásico. El vigía lo usa como respaldo para pausar |

### Comandos de `/control` (8898)

Formato: `{"serialNumber": "...", "checkCode": "...", "payload": {"cmd": "<cmd>", "args": {...}}}`

| `cmd` | `args` | Qué hace | ¿Lo usa el vigía? |
|---|---|---|---|
| `streamCtrl_cmd` | `{"action": "open"}` | Enciende el stream de la cámara | ✅ Antes de cada captura |
| `lightControl_cmd` | `{"status": "open" \| "close"}` | Luz interna | ✅ Al empezar a vigilar |
| `printerCtl_cmd` | `{"speed": 50-150}` | Velocidad global en % (M220) | ✅ Corrección (60–110 %) |
| `printerCtl_cmd` | `{"zAxisCompensation": mm}` | Z offset (`SET_GCODE_OFFSET`), de −5 a +5 | ✅ Corrección, solo capas 1–3, ±0,10 mm total |
| `printerCtl_cmd` | `{"coolingFan": n}` | Ventilador de capa | ⚠️ Solo con permiso (escala sin confirmar) |
| `printerCtl_cmd` | `{"chamberFan": n}`, `{"coolingLeftFan": n}` | Ventiladores de cámara / izquierdo | ❌ |
| `temperatureCtl_cmd` | `{"rightNozzle": °C}` | Temperatura de boquilla | ✅ Corrección (±5 °C por paso, ±10 °C total) |
| `temperatureCtl_cmd` | `{"platform": °C}` | Temperatura de cama | ✅ Corrección (±5 °C por paso, ±10 °C total) |
| `temperatureCtl_cmd` | `{"chamber": °C}` | Temperatura de cámara | ❌ |
| `jobCtl_cmd` | `{"jobID": "", "action": "pause" \| "continue" \| "cancel"}` | Pausar / reanudar / cancelar | ✅ Pausar y reanudar. Cancelar **nunca** |
| `circulateCtl_cmd` | `{"internal": ..., "external": ...}` | Filtración de aire (Pro) | ❌ |
| `delayClose_cmd`, `reName_cmd`, `calibration_cmd`… | — | Apagado automático, nombre, calibración | ❌ |

> En `printerCtl_cmd` hay que mandar **solo** el campo que se quiere cambiar: un campo con
> valor por defecto sobrescribe el ajuste actual.

### Datos de `/detail` que usa el vigía
`status` · `printFileName` · `printLayer` / `targetPrintLayer` · `printProgress` ·
`printDuration` · `rightTemp` / `rightTargetTemp` · `platTemp` / `platTargetTemp` ·
`printSpeedAdjust` · `currentPrintSpeed` · `coolingFanSpeed` · `zAxisCompensation` ·
`doorStatus` · `lightStatus` · `errorCode` · `cameraStreamUrl`

### Comandos TCP (8899)
| Comando | Qué hace |
|---|---|
| `~M601 S1` / `~M602` | Abrir / cerrar sesión |
| `~M115` | Información de la máquina (modelo, firmware, nº de serie) |
| `~M119` | Estado de la máquina |
| `~M105` | Temperaturas |
| `~M27` | Progreso |
| `~M25` / `~M24` / `~M26` | Pausar / reanudar / parar |

### Lo que NO permite el firmware de serie
- ❌ **Flujo** (M221)
- ❌ **Retracción**
- ❌ **Pressure advance**
- ❌ Aceleraciones y límites de velocidad
- ❌ Snapshot de la cámara (solo stream) y más de un espectador a la vez

---

## API Anycubic Kobra 3 / S1 (firmware de serie, modo LAN)

Protocolo de ingeniería inversa de la comunidad, el mismo que usa Anycubic Slicer
Next en modo LAN ([notas](https://github.com/sebmueller/kobra3-lan-bridge/blob/main/docs/mqtt-protocol.md)).
Sin nube ni cuenta. La impresora sigue funcionando con el slicer y la app.

### Requisitos
- Impresora y PC en la misma red; modo LAN de Anycubic Slicer Next disponible
  (firmware 2.4.x o posterior; versiones viejas pueden pedir vincularla una vez con la app).
- `ffmpeg` instalado para sacar fotos del vídeo (`sudo apt install ffmpeg`).
- En el `.env`: `PRINTER_TIPO=anycubic` y `PRINTER_IP`.

### Puertos
| Puerto | Protocolo | Uso |
|---|---|---|
| 18910 | HTTP | Apretón de manos: `GET /info` → token; `POST /ctrl` firmado (md5) → credenciales MQTT cifradas (AES-128-CBC) |
| 9883 | MQTT con TLS (broker en la impresora) | Estado y órdenes |
| 18088 | HTTP-FLV (`/flv`) | Vídeo; solo da imagen tras `video/startCapture` |

### Órdenes MQTT (`anycubic/anycubicCloud/v1/web/printer/<modelo>/<id>/<tipo>`)
| `type` / `action` | `data` | Qué hace | ¿Lo usa el vigía? |
|---|---|---|---|
| `info` / `query` | — | Estado completo (`project`, `temp`, `fan_speed_pct`…) | ✅ En cada ciclo |
| `print` / `pause` | `{"taskid": "-1"}` | Pausar | ✅ |
| `print` / `resume` | `{"taskid": "-1"}` | Reanudar (es `resume`, no `continue`) | ✅ |
| `print` / `stop` | `{"taskid": "-1"}` | Cancelar | ❌ Nunca |
| `print` / `update` | `{"taskid": "-1", "settings": {...}}` | Temperaturas, ventilador, modo de velocidad (1/2/3) | 🧪 Implementado, desactivado hasta probarlo |
| `light` / `control` | `{"type": 1, "status": 1, "brightness": 100}` | Luz del cabezal | ✅ |
| `video` / `startCapture` | — | Enciende el codificador de vídeo | ✅ Antes de capturar |

### Lo que NO permite
- ❌ G-code libre, flujo, retracción, Z offset en marcha.
- ❌ % de velocidad: solo modos silencioso / estándar / deportivo.

### Falta de filamento
- Si la impresora **se pausa sola** (sensor), el vigía avisa con foto y recuerda cada
  `RECORDATORIO_PAUSA_MIN` hasta que se reanude.
- Si algún mensaje de la impresora menciona falta de filamento (`runout`, `lack`…) y
  sigue imprimiendo, el vigía **pausa** y avisa.
- Por cámara: si la capa avanza y la pieza no crece, el diagnóstico lo marca como
  `sin_filamento` y pausa.
- Todos los mensajes de la impresora se guardan en `DIR_CASOS/anycubic_mensajes.jsonl`
  para descubrir el campo exacto del sensor la primera vez que salte.

---

## Con Klipper (Moonraker)

Klipper con Moonraker expone una API REST completa en el puerto **7125** y acepta
**cualquier G-code o macro** en caliente. Con eso el vigía puede corregir bastante más.

### Cómo se haría
| Necesidad | Moonraker |
|---|---|
| Estado | `GET /printer/objects/query?print_stats&virtual_sdcard&extruder&heater_bed&gcode_move&fan` |
| Enviar G-code | `POST /printer/gcode/script?script=<G-code>` |
| Pausar / reanudar / cancelar | `POST /printer/print/pause` · `/resume` · `/cancel` |
| Cámara | `/webcam/?action=snapshot`: **tiene snapshot** y admite varios espectadores (crowsnest) |
| Fichero en curso | `print_stats.filename` |

### Correcciones posibles: Flashforge de serie frente a Klipper

| Corrección | Flashforge de serie | Klipper | G-code en Klipper |
|---|---|---|---|
| Velocidad | ✅ | ✅ | `M220 S80` |
| **Flujo** | ❌ | ✅ | `M221 S105` |
| Temperatura boquilla / cama | ✅ | ✅ | `M104 S240` / `M140 S70` |
| Ventilador de capa | ⚠️ | ✅ (escala clara, 0–255) | `M106 S128` |
| Z offset (primeras capas) | ✅ | ✅ | `SET_GCODE_OFFSET Z_ADJUST=0.02 MOVE=1` |
| **Pressure advance** | ❌ | ✅ | `SET_PRESSURE_ADVANCE ADVANCE=0.04` |
| **Retracción** | ❌ | ✅ (con retracción de firmware) | `SET_RETRACTION RETRACT_LENGTH=0.8` |
| **Aceleración** | ❌ | ✅ | `SET_VELOCITY_LIMIT ACCEL=4000` |
| Pausar / reanudar | ✅ | ✅ | `PAUSE` / `RESUME` |

### Qué ganaría el vigía con Klipper
- **Hilos (PETG)**: subir la retracción en marcha, además de bajar la temperatura.
- **Subextrusión / sobreextrusión**: corregir el **flujo** directamente.
- **Esquinas con bultos, ringing**: ajustar pressure advance o aceleración.
- **Mejor visión**: snapshot directo y convivencia con Mainsail/Fluidd sin bloquear la cámara.

### Tu AD5M Pro con Klipper
Los mods de la comunidad **Forge-X** y **ZMod** instalan Klipper + Moonraker en la
AD5M Pro con **arranque dual**: se puede volver al firmware de serie. Son mods no
oficiales y la placa va justa de RAM (128 MB), así que conviene seguir sus guías.
Con el mod puesto, el vigía usaría el adaptador `klipper` (`PRINTER_TIPO=klipper`).

### Estado
El adaptador de Klipper **está por escribir** (hay un esbozo en [ADAPTADORES.md](ADAPTADORES.md)).
El `flujo` ya está soportado por el vigía: bastaría con declararlo en el adaptador.
`retraccion`, `pressure_advance` y `aceleracion` se añadirían siguiendo
[MODIFICAR.md → Añadir un tipo de corrección](MODIFICAR.md#5-añadir-un-tipo-de-corrección-nuevo).
