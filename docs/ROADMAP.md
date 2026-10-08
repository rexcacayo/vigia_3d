# Hoja de ruta

Qué falta por verificar, qué viene después y hacia dónde puede crecer el Vigía 3D.
Lo ya hecho está en [CHANGELOG.md](../CHANGELOG.md).

Leyenda: 🔴 prioridad alta · 🟡 media · 🟢 idea a explorar

---

## 0. Pendiente de verificar en una impresora real

Funciona en la simulación (`tests/simulacion.py`) pero falta confirmarlo con hardware.

| Qué | Dónde | Riesgo si falla | Plan B |
|---|---|---|---|
| 🔴 **Pausar / reanudar** por la API (`jobCtl_cmd` con `jobID` vacío) | `impresoras/flashforge.py` | No pausa ante un 🛑 | Ya hay respaldo por TCP 8899 (`~M25`/`~M24`); si la API falla, usarlo directamente |
| 🔴 **Z offset** (`zAxisCompensation`): valor absoluto y aplicado en caliente | `impresoras/flashforge.py` | Ajuste de primera capa erróneo | Desactivar la capacidad `z_offset` hasta confirmarlo |
| 🟡 **Escala del ventilador** (0–100 o 0–255) en `printerCtl_cmd` | `impresoras/flashforge.py` | El ventilador queda más bajo o alto de lo previsto | Ya está en `SOLO_CON_PERMISO`; confirmar leyendo `coolingFanSpeed` tras el cambio |
| 🟡 **Velocidad y temperaturas** aplicadas en una impresión real | `correcciones.py` | — | Comprobar con `/estado` tras aplicar |
| 🟡 **Frecuencia adaptativa** en una impresión larga | `main.py` | Más coste o menos detección de lo estimado | Ajustar `INTERVALO_S` / `ALERTA_MIN` con los datos de `/coste` |

Checklist de la prueba completa: [PRUEBA_REAL.md](PRUEBA_REAL.md).

---

## 1. Calidad del diagnóstico

| | Mejora | Por qué | Esfuerzo |
|---|---|---|---|
| 🔴 | **Medición de aciertos**: script que reevalúa los casos marcados con 👍/👎 con la skill actual y da el % de aciertos, falsos positivos y fallos no detectados | Cada cambio de prompt o skill se demuestra con datos, no a ojo | Medio |
| 🔴 | **Ajuste del filtro** con los datos reales (motivos de `filtro: sospecha` en el log) | El filtro decide el coste y la sensibilidad | Bajo |
| 🟡 | **Segunda cámara cenital** (webcam USB) | La cámara de la AD5M ve la pieza de lado; los defectos superiores de piezas pequeñas no se ven (caso de la mano de Dora) | Medio |
| 🟡 | **Revisión antes de imprimir**: foto de la cama vacía y aviso si hay restos | Muchos fallos de primera capa vienen de una cama sucia | Bajo |
| 🟡 | **Contexto del modelo**: pasar a Claude la miniatura de la pieza (`/getThum` de Flashforge) | Saber qué forma debería tener la pieza mejora mucho el diagnóstico | Bajo |
| 🟢 | **Zona de la pieza automática**: calcular `ZOOM_REGION` comparando con la cama vacía | No tener que ajustarla a mano | Medio |
| 🟢 | **Time-lapse con incidencias** al final de cada impresión | Revisar qué pasó y cuándo | Medio |

## 2. Más impresoras

| | Adaptador | Notas |
|---|---|---|
| 🔴 | **Klipper / Moonraker** | Esbozo en [ADAPTADORES.md](ADAPTADORES.md). Desbloquea flujo, retracción, pressure advance y aceleración. Vale para la AD5M con Forge-X/ZMod |
| 🟡 | **Prusa (PrusaLink)** | API local REST; cámara vía Prusa Connect o webcam |
| 🟡 | **Elegoo (Centauri Carbon)** | Protocolo local con cámara integrada |
| 🟡 | **OctoPrint** | Cubre muchas impresoras con Raspberry |
| 🟢 | **Bambu Lab (LAN / modo desarrollador)** | Solo por la vía oficial que permita la marca |
| 🟢 | **Gran formato (Dowell) y pellets (Piocreat)** | Impresiones de días: el caso de uso con más valor; depende de acceso a máquinas |

Cada adaptador nuevo sigue el checklist de [ADAPTADORES.md](ADAPTADORES.md).

## 3. Correcciones en marcha

| | Mejora | Requisito |
|---|---|---|
| 🟡 | `flujo` (M221) | Adaptador Klipper |
| 🟡 | `retraccion`, `pressure_advance`, `aceleracion` | Adaptador Klipper + reglas nuevas ([MODIFICAR.md §5](MODIFICAR.md#5-añadir-un-tipo-de-corrección-nuevo)) |
| 🟢 | **Modo auto por tipo de corrección** (p. ej. automático para velocidad, con permiso para temperatura) | Ampliar `CORRECCION_MODO` |
| 🟢 | **Perfil de impresión aprendido**: que el informe post-mortem acumule recomendaciones por material y proponga un perfil de Orca | Historial de informes |

## 4. Operación y despliegue

| | Mejora | Por qué |
|---|---|---|
| 🔴 | **Servicio systemd en Raspberry Pi** (arranque automático, reinicio si cae) | No depender del PC encendido ni de lanzarlo a mano |
| 🟡 | **Varias impresoras** desde un solo vigía | Granjas de impresión pequeñas |
| 🟡 | **Panel web local** (estado, última foto, historial de casos, coste) | Ver todo sin Telegram y sin ocupar la cámara |
| 🟢 | **Otros canales** de aviso (ntfy, Discord, WhatsApp) | Ver [MODIFICAR.md §9](MODIFICAR.md#9-otro-canal-de-avisos-whatsapp-discord-ntfy) |
| 🟢 | **Imagen Docker** | Instalación en un comando |

## 5. Comunidad y proyecto

| | Tarea |
|---|---|
| 🔴 | Capturas reales (aviso en Telegram, parte, informe) en el README |
| 🔴 | Topics del repositorio en GitHub |
| 🟡 | Documentación en inglés (al menos README y ADAPTADORES) |
| 🟡 | Plantillas de *issues* (fallo, nueva impresora, mejora de criterio) |
| 🟡 | Solicitud al programa **Let's Make It Fund** de Bambu Lab y contacto con fabricantes para unidades de prueba |
| 🟢 | Vídeo de demostración |

---

## Cómo proponer algo
Abre un *issue* en GitHub con la etiqueta adecuada o sigue [CONTRIBUTING.md](../CONTRIBUTING.md).
