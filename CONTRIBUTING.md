# Cómo contribuir

¡Gracias por querer mejorar el Vigía 3D! Las aportaciones más valiosas:

1. **Adaptadores para otras impresoras** (Klipper, OctoPrint, Bambu…) → [docs/ADAPTADORES.md](docs/ADAPTADORES.md)
2. **Mejoras de criterio** en `skill/` con casos reales (foto + qué pasaba) → [docs/MODIFICAR.md](docs/MODIFICAR.md)
3. **Nuevas correcciones** seguras para máquinas que las permitan
4. **Canales de aviso** alternativos (Discord, ntfy, WhatsApp…)

## Flujo
1. Haz un fork y crea una rama: `git checkout -b adaptador-klipper`.
2. Haz tus cambios siguiendo [docs/MODIFICAR.md](docs/MODIFICAR.md).
3. Comprueba que todo sigue en verde:
   ```bash
   ./venv/bin/python -m tests.simulacion
   ./venv/bin/python -m vigia.probar          # si tienes la impresora
   ```
4. Abre un Pull Request explicando qué cambia, en qué impresora lo has probado y, si
   afecta al criterio, un ejemplo de antes y después.

## Normas
- La IA **nunca** controla la impresora directamente: toda acción pasa por la lista blanca
  y las reglas de `vigia/correcciones.py`.
- Declara en un adaptador solo las capacidades que hayas **probado** en una máquina real.
- Sin credenciales ni datos personales en el código ni en los ejemplos.
- Código en español, como el resto del proyecto (nombres claros, comentarios breves).
