# Cómo modificar el vigía

Recetas para los cambios más habituales, de menos a más técnicos. Después de cualquier
cambio de código, ejecuta la simulación:

```bash
./venv/bin/python -m tests.simulacion     # sin impresora ni Claude: debe acabar en "TODO OK ✅"
./venv/bin/python -m vigia.probar         # con tu impresora: contrato + estado + foto
./venv/bin/python -m vigia.probar --claude   # además, un diagnóstico real
```

Y reinicia el vigía: `./arrancar.sh`.

---

## 1. Cambiar el criterio de diagnóstico (sin programar)

El conocimiento está en `skill/` y **se relee en cada diagnóstico**: no hace falta
reiniciar para que un cambio cuente.

| Quiero… | Edito |
|---|---|
| Que sea más o menos estricto, cambiar qué es "normal" | `skill/SKILL.md` → *Cómo razonar* |
| Ajustar lo que espera de un material o añadir uno | `skill/materiales.md` |
| Cambiar cuándo propone cada corrección | `skill/correcciones.md` |
| Enseñarle un caso concreto | `skill/aprendizajes.md` (o 👎 + comentario por Telegram) |
| Describir mejor la cámara de mi máquina | `DESCRIPCION` en `vigia/impresoras/<tipo>.py` |

Consejos:
- Escribe reglas **concretas y observables** ("rizos sobre la pieza en zonas de detalle")
  en vez de genéricas ("ten cuidado").
- Un aprendizaje por línea, con material y contexto. Si `aprendizajes.md` crece mucho,
  agrupa los casos parecidos en una regla y pásala a `SKILL.md` o `materiales.md`.

## 2. Ajustar el filtro rápido

El filtro decide cuándo despertar al diagnóstico (y, por tanto, gran parte del coste).
Está en `vigia/vision.py`, constante `FILTRO`.
- **Demasiado alarmista** (mucho `filtro: sospecha` en el log sin motivo): añade a la lista
  de cosas *normales* lo que esté confundiendo.
- **Se le escapan cosas**: añade el patrón a la lista de "sospecha SOLO si ves…".
- Para ver sus motivos: `grep "filtro:" casos/vigia.log`.

## 3. Cambiar modelos o precios

En `.env`:
```
MODELO_FILTRO=claude-haiku-4-5-20251001
MODELO_DIAGNOSTICO=claude-sonnet-5-5
PRECIO_CLAUDE_SONNET_5_5=2,10,2.5,0.2   # entrada, salida, escritura caché, lectura caché
```
Si usas un modelo nuevo, añade su precio por defecto en `PRECIOS_DEFECTO` de
`vigia/config.py` (o con `PRECIO_<MODELO>` en el `.env`).

## 4. Reglas de corrección

Todas en `vigia/correcciones.py`:

| Qué | Dónde |
|---|---|
| Rangos de temperatura por material | `TEMP_BOQUILLA`, `TEMP_CAMA` |
| Materiales sin ventilador | `SIN_VENTILADOR` |
| Qué se revierte cuando todo va bien | `REVERSIBLES` |
| Paso máximo y límite total de cada ajuste | `Motor._calcular()`, una rama por tipo |
| Confianza, persistencia, máximo, espera | `.env`: `CORRECCION_*`, `REVERTIR_TRAS_OK` |

Ejemplo, permitir bajar la velocidad hasta el 50 % en vez del 60 %:
```python
# Motor._calcular(), rama "velocidad"
obj = _clamp(actual + _clamp(delta, -30, 10), 50, 110)
```

## 5. Añadir un tipo de corrección nuevo

Ejemplo: `aceleracion` (solo tendría sentido con un adaptador Klipper).

1. **Contrato**: en `vigia/impresoras/__init__.py`, añade `"aceleracion": "poner_aceleracion"`
   a `POR_CAPACIDAD`.
2. **Adaptador**: en el adaptador que lo soporte, añade `"aceleracion"` a `CAPACIDADES` e
   implementa `poner_aceleracion(valor)`. Si puedes, devuelve el valor actual en
   `estado()` (p. ej. `"aceleracion": 5000`).
3. **Visión**: añade `"aceleracion"` a `_AJUSTES` en `vigia/vision.py`. Solo se ofrecerá
   a Claude si la impresora la declara.
4. **Reglas**: en `Motor._calcular()`, añade una rama `elif tipo == "aceleracion":` con paso
   máximo y límites; si debe revertirse, añádelo a `REVERSIBLES`; si nunca debe ir en
   automático, ponlo en `SOLO_CON_PERMISO` del adaptador.
5. **Textos**: nombre y unidades en `Propuesta.texto()`.
6. **Skill**: una fila nueva en `skill/correcciones.md` explicando cuándo proponerla.
7. **Prueba**: añade un caso en `tests/simulacion.py` y ejecútala.

## 6. Añadir una orden de Telegram

En `vigia/main.py`, método `comando()`:
```python
elif cmd == "temperaturas":
    e = P.estado()
    self.bot.texto(f"Boquilla {e['boquilla']['actual']} °C · cama {e['cama']['actual']} °C")
```
Y añádela al texto `AYUDA`. Si quieres que aparezca en el menú de Telegram, regístrala en
@BotFather con `/setcommands`.

## 7. Añadir un botón

1. Envíalo con `self.bot.texto(texto, [[("Texto del botón", "clave:valor")]])`
   (o `self.bot.foto(...)`). `callback_data` admite como mucho 64 bytes.
2. Gestiónalo en `Vigia.boton()` con una rama `elif clave == "...":`.
3. Quita los botones al responder: `self.bot.quitar_botones(mensaje, "nota")`.

## 8. Cambiar los textos de los avisos

`vigia/main.py`: `_texto_estado()`, `_texto_diag()`, `_avisar_problema()` y el parte en
`ciclo_vigilancia()`. Telegram usa HTML: escapa siempre el texto variable con `esc()`.

## 9. Otro canal de avisos (WhatsApp, Discord, ntfy…)

Crea una clase con los mismos métodos que `Bot` (`texto`, `foto`, `quitar_botones`,
`escuchar`, y los callbacks `on_comando`, `on_boton`, `on_texto`) y úsala en
`Vigia.__init__`. Si el canal no tiene botones, limita el uso a `CORRECCION_MODO=off` o
`auto`.

## 10. Soportar otra impresora

Ver [ADAPTADORES.md](ADAPTADORES.md).

---

## Buenas prácticas
- **Nunca** des a Claude capacidad de enviar comandos libres a la impresora: toda acción
  pasa por la lista blanca y `correcciones.py`.
- Todo lo que pueda fallar (red, cámara, API) va con `timeout` y dentro de `try`: el bucle
  no debe morir.
- Cambios de criterio → `skill/`. Cambios de límites y seguridad → código, con prueba.
