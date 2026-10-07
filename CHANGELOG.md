# Historial de cambios

## 0.4.0: agente con skill
- Arquitectura modular con **adaptadores de impresora** enchufables (`PRINTER_TIPO`).
- **Skill** en Markdown (`skill/`) que se relee en cada diagnóstico; la máquina aporta su
  propia descripción de cámara.
- **Bot de Telegram interactivo**: botones Aplicar/Ignorar, 👍/👎 con aprendizaje, pausa,
  preguntas libres y órdenes.
- **Motor de correcciones** con lista blanca, límites por material, persistencia, máximo de
  cambios y reversión automática. Modos `off` / `proponer` / `auto`.
- **Informe post-mortem** con recomendaciones de perfil para OrcaSlicer.
- **Medición del coste real** por impresión (`/coste`).
- Verificador de adaptadores (`python -m vigia.probar`) y simulación completa (`tests/`).

## 0.3.0
- Ampliación de la zona de la pieza, criterio más estricto (`isla_fallida`), gravedad
  `ok / vigilar / detener`, diagnóstico profundo periódico, pausa automática opcional.
- Partes periódicos con foto.

## 0.2.0
- API local de Flashforge (8898): estado completo y encendido de cámara y luz.
- Descubrimiento clave: la cámara de la AD5M solo admite un espectador.

## 0.1.0
- Primer prototipo: foto por la cámara, filtro + diagnóstico con Claude, avisos.
