# ELEGOO Rapid PETG

Tipo: PETG de alta velocidad · Marca: ELEGOO

## Datos del fabricante
- Boquilla 230–260 °C · cama 70–85 °C (algunos usuarios hasta 90 °C).
- Hasta 600 mm/s solo con hotend de alto caudal y ventilación fuerte; en máquinas
  normales, 50–250 mm/s.
- Secado: 65 °C unas horas si la bobina lleva tiempo abierta. Recién sacada del
  vacío suele venir bien, pero no siempre.
- Ventilador: menos que en PLA para no perder unión entre capas; solo mucho
  ventilador a velocidades muy altas.

## Perfil validado en esta máquina (Flashforge AD5M Pro)
- Se ha impreso a 250 °C boquilla / 70 °C cama sin fallos de unión (Dora, 4h26m).
- Falta validar: temperatura mínima sin hilos, retracción y ventilador.

## Recomendaciones sin validar
Recogidas el 2026-10-10 de una guía contra hilos. Valoradas para la AD5M:
- **Secar a 65 °C 6–8 h** (prioridad 1). Es la causa más habitual de hilos y pegotes
  en este filamento. Señal de humedad: chasquidos al imprimir, burbujas o vapor en
  la purga. Guardar después en bolsa con desecante.
- **Bajar boquilla a 230–235 °C**: menos goteo. Cuidado: a las velocidades de la AD5M
  baja la velocidad volumétrica que da el hotend y puede subextruir. Hacerlo con
  **torre de temperatura** (Orca → Calibración → Temperatura, 255→225 °C) y quedarse
  con la más baja que aún une bien las capas. Si se baja la temperatura, limitar
  también la **velocidad volumétrica máx.** (Orca → Calibración → Vel. volumétrica).
- **Retracción 1,0–1,2 mm a 40–45 mm/s** (extrusión directa: no pasar de ~1,4 mm).
  Mejor con la **prueba de retracción** de Orca que a ojo.
- **Z-hop**: la guía dice desactivarlo. Matiz: sin Z-hop la boquilla puede arrastrar
  pegotes de PETG sobre la pieza. Alternativa: Z-hop bajo (0,2 mm) o solo sobre
  superficies superiores, y comparar.
- **Evitar cruzar paredes**: sí, buena idea para PETG.
- **Velocidad de desplazamiento 250–300 mm/s**: en la AD5M el perfil ya viaja bastante
  más rápido. No bajarla.
- **Ventilador 40–60 %** desde la capa 3; primeras capas con poco o nada para que
  pegue bien a la cama.
- Añadidos que la guía no menciona: **limpiar al retraer (wipe)**, **retraer al
  cambiar de capa**, y calibrar **flujo** y **pressure advance** en Orca.

## Qué se ve en la cámara
- Hilos finos entre islas (soportes, dedos, orejas): **normal** si son finos y no se
  acumulan. No es motivo de `detener`.
- Grave: hilos que se juntan en **bolas o pegotes** sobre la pieza, pegotes en la
  boquilla que caen encima, o material arrastrado por la cama.
- En las primeras capas, islas que se mueven entre fotogramas = **despegue** (caso del
  8-oct): `fallo` / `detener`.
- Las paredes finas en PETG se ven onduladas por el brillo del material: no confundir
  con deformación si no cambian entre fotogramas.

## Correcciones en marcha
- Hilos persistentes: `temp_boquilla` −5 °C (no bajar de 235 °C sin torre validada) y,
  si hay voladizos, `ventilador` +20.
- La retracción y el Z-hop **no** se pueden cambiar en marcha en esta máquina: van al
  informe como recomendación de perfil.

## Historial de impresiones
- 2026-10-07 · dora_exploradora_peana (4h26m, completed): 250/70 °C sin fallos; el
  filtro dio una falsa alarma de isla fallida.
- 2026-10-08 · Pikachu_Scream (cancelada en capa 28): despegue en las primeras capas
  con la cama sucia → espagueti. Limpiar la cama (agua y jabón + alcohol isopropílico) antes de PETG.
- 2026-10-08 · Pikachu_Scream (3h40m, terminada): 250/70 °C; el filtro marcó
  deformación en paredes finas que estaban bien.
