# Correcciones en marcha (lista blanca)

Qué se puede cambiar en caliente depende de la impresora (ver "Acciones que admite
ESTA impresora"). Proponer algo que la máquina no admite no sirve de nada.

| tipo | qué hace | cuándo proponerlo | delta orientativo |
|---|---|---|---|
| `velocidad` | % de velocidad global (M220) | islas/voladizos que se deforman, subextrusión ligera | -20 a -30 |
| `flujo` | % de flujo (M221), solo si la máquina lo admite | subextrusión/sobreextrusión clara y estable | ±5 |
| `temp_boquilla` | °C de boquilla | hilos persistentes (bajar), subextrusión o mala unión entre capas (subir) | ±5 |
| `temp_cama` | °C de cama | esquinas que empiezan a levantarse (subir) | +5 |
| `z_offset` | mm de ajuste fino de altura | **solo capas 1–3**: primera capa aplastada (subir, +) o sin pegar/líneas sueltas (bajar, −) | ±0,02 |
| `ventilador` | ventilador de capa | voladizos rizados en PLA/PETG | +20 |
| `pausar` | pausa la impresión | espagueti, pieza despegada, capa desplazada, pegote enorme en boquilla | — |
| `ninguna` | no tocar nada | todo bien, o el fallo no tiene arreglo en marcha | — |

Reglas que aplica el programa (no hace falta que las impongas tú, pero tenlas en cuenta):
- Solo se actúa con confianza ≥ 0,8 y si la misma acción se repite en 2 diagnósticos seguidos.
- Máximo 3 cambios por impresión, y unos minutos entre cambios.
- Límites por material para temperaturas; velocidad entre 60 y 110 %.
- Nada de ventilador alto en ASA/ABS.
- Si tras corregir todo va bien un rato, se revierten velocidad y ventilador.
