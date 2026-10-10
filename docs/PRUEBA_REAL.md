# Prueba en una impresora real

Checklist para validar una versión nueva (o un adaptador nuevo) con hardware.
Usa una impresión corta y fiable (1–2 h, PLA) y anota el resultado de cada punto.

## Preparación
```bash
git pull --autostash          # última versión sin perder lo aprendido
bash instalar.sh              # añade al .env las opciones nuevas sin tocar las tuyas
./venv/bin/python -m tests.simulacion        # debe acabar en "TODO OK ✅"
./venv/bin/python -m vigia.probar --claude   # impresora, cámara y Claude
```
Ajustes recomendados para la prueba en `.env`: `INFORME_CADA_MIN=10`, `INTERVALO_S=90`,
`CORRECCION_MODO=proponer`, `PRESUPUESTO_DIA_USD=2`.

> Flashforge: cierra la pestaña *Dispositivo* de Orca (la cámara solo admite un espectador).

## Durante la impresión

| ✔ | Qué comprobar | Cómo | Resultado esperado |
|---|---|---|---|
| ☐ | Arranque | `./arrancar.sh` | "🤖 Vigía en marcha" en Telegram |
| ☐ | Detección de la impresión | Lanzar la impresión | "👀 Empiezo a vigilar" + luz encendida |
| ☐ | Frecuencia adaptativa | `tmux attach -t vigia` | Ciclos cada 30 s en las primeras capas, luego cada 90 s |
| ☐ | Partes | Esperar | Parte con foto cada `INFORME_CADA_MIN` |
| ☐ | Candado de cámara | `/foto` mientras vigila | Llega la foto y el vigía no da error de cámara |
| ☐ | Preguntas libres | "¿cómo va la pieza?" | Respuesta con foto |
| ☐ | **Pausa** | `/pausa` → Sí (al principio de la impresión) | La impresora se pausa de verdad |
| ☐ | **Reanudar** | `/reanudar` | La impresora continúa |
| ☐ | Feedback | 👎 en un parte + una frase | "📚 Aprendido" y línea nueva en `skill/aprendizajes.md` |
| ☐ | Coste | `/coste` | Gasto de la impresión, ritmo $/h y gasto del día |
| ☐ | Correcciones *(si aparecen)* | ✅ Aplicar | El cambio se ve en `/estado` y se revierte cuando todo va bien |
| ☐ | Informe final | Al terminar | "🏁" + informe con recomendaciones y coste |

## Después
- Revisa `DIR_CASOS/vigia.log` y `casos.jsonl`: ¿hubo sospechas sin motivo? ¿se le escapó algo?
- Anota los resultados en un *issue* o en el CHANGELOG y actualiza la sección 0 de
  [ROADMAP.md](ROADMAP.md).
