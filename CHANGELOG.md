# Historial de cambios

Lo que viene: ver [docs/ROADMAP.md](docs/ROADMAP.md).

## 0.6.1: el aviso ya no se pierde
Caso real (Pikachu, PETG, 8-oct): el filtro vio espagueti desde la capa 3, pero el
diagnóstico llegaba cortado y el 🛑 salió 15 minutos tarde.
- Diagnóstico con más margen (`MAX_TOKENS_DIAG=2000`) y **reintento** si la respuesta
  llega cortada o mal formada; el log indica el `stop_reason`.
- **Aviso de respaldo**: si el filtro sospecha `SOSPECHAS_ALARMA` fotos seguidas (3) y el
  diagnóstico no confirma, avisa igualmente (🛑 si el filtro habla de espagueti, despegue…).
- No analiza mientras calienta en capa 0 (ahorro y menos falsas sospechas por cama sucia).
- Aprendizaje nuevo: islas que se mueven en las primeras capas = despegue.

## 0.6.0: robustez para uso público
- **Tope de gasto diario** (`PRESUPUESTO_DIA_USD`): aviso al 80 %, corte al 100 %.
- **Candado de cámara**: el bucle y Telegram nunca piden foto a la vez.
- **Reintentos** ante fallos de Claude y Telegram; aviso si Claude deja de responder y
  cuando vuelve; los errores repetidos ya no inundan el log.
- **Limpieza** automática de fotos antiguas (`DIAS_RETENCION`).
- **Tests automáticos** en GitHub Actions y aviso de seguridad en el README.

## 0.5.0: frecuencia adaptativa
- Mira cada 90 s en calma y cada 30 s en las primeras capas y durante 10 min tras
  cualquier sospecha: menos coste sin perder precisión cuando algo empieza a fallar.
- El diagnóstico experto periódico pasa a medirse en minutos (`DIAG_CADA_MIN`).
- Coste estimado del perfil normal: ~$0,17/h (antes ~$0,30/h).

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
