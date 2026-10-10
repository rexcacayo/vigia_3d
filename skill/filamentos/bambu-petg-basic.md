# Bambu Lab PETG Basic

Tipo: PETG estándar (no de alta velocidad) · Marca: Bambu Lab

## Datos del fabricante
- Boquilla 230–260 °C · cama 65–75 °C.
- Velocidad: **menos de 200 mm/s**. Es un PETG normal, no «HF» ni «Rapid».
- Secado: 65 °C durante 8 h. Guardar por debajo del 20 % de humedad, con desecante.
- Placa: lisa en frío, alta temperatura o PEI texturizada; **con pegamento** (stick o
  líquido) como separador. Sin él, el PETG puede arrancar trozos de la placa lisa.
- Para un acabado más brillante: más lento y algo más caliente.

## Perfil validado en esta máquina (Flashforge AD5M Pro)
Sin datos todavía.

## Recomendaciones sin validar
- En OrcaSlicer, partir del perfil «Bambu PETG Basic» o «Generic PETG» y **limitar la
  velocidad**: los perfiles de la AD5M van mucho más rápido de 200 mm/s. Lo más cómodo
  es bajar la **velocidad volumétrica máx.** del filamento y calibrarla con la prueba de
  Orca.
- Empezar en 240 °C / 70 °C y ajustar con la torre de temperatura.
- Ventilador bajo en las primeras capas y medio (30–50 %) después.
- Retracción y Z-hop: mismos criterios que la ficha de ELEGOO Rapid PETG; confirmar
  con la prueba de retracción.
- Comparar con el ELEGOO Rapid PETG: hilos, unión entre capas, acabado y tiempo.

## Qué se ve en la cámara
- Como cualquier PETG: hilos finos entre islas son normales si no se acumulan.
- Grave: pegotes en la boquilla, bolas de hilo sobre la pieza, islas que se mueven en
  las primeras capas (despegue).
- Si se imprime demasiado rápido para este filamento: paredes con huecos o rayas
  mates (subextrusión). Es la diferencia clave con el Rapid PETG.

## Correcciones en marcha
- Subextrusión por velocidad: `velocidad` −20 a −30 % (es el ajuste más útil con este
  filamento en la AD5M).
- Hilos persistentes: `temp_boquilla` −5 °C; voladizos rizados: `ventilador` +20.

## Historial de impresiones
