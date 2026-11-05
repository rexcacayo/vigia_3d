# Historial de cambios

Lo que viene: ver [docs/ROADMAP.md](docs/ROADMAP.md).

## 0.12.0: cámara extra (vista superior)
- `CAMARA_EXTRA`: cámara de la Raspberry (`picam`), webcam USB (`/dev/video0`) o URL. El
  diagnóstico recibe la vista superior del mismo momento, se guarda con cada caso, viaja al
  analista y llega por Telegram con los partes, los avisos y `/foto`.
- Si la cámara extra falla, el vigía sigue con la de la impresora.
- Prueba rápida: `python -m vigia.camara_extra`.

## 0.11.0: una sola fuente de verdad para las skills
- El vigía **instala sus skills desde GHCR** (artefactos OCI publicados por `vigia-agentes`)
  por digest, al arrancar y al empezar cada impresión: `skills.json` declara cuáles y
  `.skills/skills.lock.json` registra la versión exacta en uso. Sin red, sigue con lo
  instalado o con la copia `skill/` de respaldo.
- **Capa local** (`DIR_CASOS/aprendido/`): 👎, historial de fichas y fichas nuevas se
  guardan aquí, se suman a la skill al leerla y viajan al analista, que los propone por PR.
  Al publicarse, dejan de duplicarse. La primera vez se rescata lo aprendido en `skill/`.
- Orden `/analizar` (0.10.1): análisis de la última impresión por el agente, en Telegram.

## 0.10.0: agentes en Claude Platform
- Nuevo repo **[vigia-agentes](https://github.com/rexcacayo/vigia-agentes)**: agentes, entorno
  y skills como código (`ant apply` desde la CI) y skills publicadas como artefactos OCI.
- Con `ANALISTA=true`, al terminar cada impresión el vigía envía fotos (con su capa),
  perfil, casos, informe y **capacidades de la máquina** al *analista de proceso*, y
  manda su análisis por Telegram. El agente propone lo aprendido por PR.
- `/fichas`: el *agente de filamento* consolida las fichas (por PR).

## 0.9.0: el vigía conoce el perfil del laminado
- **`skills/ad5m-slicer-engineer/`**: el proyecto «AD5M Pro Slicer Engineer» de Claude
  Desktop convertido en skill del repo. Modo A: generar la tríada de perfiles de Orca;
  modo B: analizar una impresión cruzando fotos y perfil.
- **Lectura del perfil** del `.3mf` que imprime la máquina (`DIR_LAMINADOS`):
  temperaturas, velocidades, ventilador, retracción, capa… El diagnóstico lo recibe y el
  informe final incluye veredicto y tabla «clave · actual · propuesto · motivo · evidencia».

## 0.8.0: Anycubic Kobra 3 y falta de filamento
- **Adaptador `anycubic`** para Kobra 3 / 3 Max / 3 V2 / S1 / S1 Max por su protocolo
  LAN (MQTT con TLS en la impresora, sin nube): estado, pausar, reanudar, luz y foto.
  Pendiente de probar en la Kobra 3 Max. Pruebas a mano:
  `python -m vigia.impresoras.anycubic estado|pausa|reanudar|foto|escuchar`.
- **Falta de filamento**: si la impresora informa de ello, el vigía pausa y avisa; si
  se pausa sola, avisa con foto y lo recuerda; por cámara, «la capa avanza y la pieza no
  crece» → `sin_filamento` → pausa.
- Cada fotograma del diagnóstico lleva su número de capa.

## 0.7.0: fichas de filamento que aprenden
- **Fichas por marca y tipo** en `skill/filamentos/`, con datos del fabricante, perfil
  validado, recomendaciones pendientes de probar, síntomas en cámara y correcciones.
  Primera ficha: **ELEGOO Rapid PETG**.
- `/filamento` en Telegram para ver, elegir o crear la ficha del filamento cargado; el
  vigía lo pregunta al empezar cada impresión.
- El diagnóstico usa la ficha, y el informe final **añade lo aprendido** a su historial.
- `materiales.md`: PETG higroscópico (hilos = humedad), cama limpia, brillo ≠ deformación.

## 0.6.1: el aviso ya no se pierde
Caso real (Pikachu, PETG, 8-oct): el filtro vio espagueti desde la capa 3, pero el
diagnóstico llegaba cortado y el 🛑 salió 15 minutos tarde.
- Diagnóstico con más margen (`MAX_TOKENS_DIAG=2000`) y **reintento** si la respuesta
  llega cortada o mal formada; el log indica el `stop_reason`.
- **Aviso de respaldo**: si el filtro sospecha `SOSPECHAS_ALARMA` fotos seguidas (3) y el
  diagnóstico no confirma, avisa igualmente (🛑 si el filtro habla de espagueti, despegue…).
- No analiza mientras calienta en capa 0 (ahorro y menos falsas sospechas por cama sucia).
- Aprendizaje nuevo: islas que se mueven en las primeras capas = despegue.
- **Ahorro**: si el diagnóstico acaba de decir que no hay fallo, las sospechas del filtro
  no lo vuelven a consultar hasta pasados `DIAG_ENTRE_SOSPECHAS_S` (120). En la prueba
  real el filtro marcó sospecha en 269 fotos de una pieza sana y agotó los $2 del día.
- **Pausa primero, aviso después** (`AUTO_PAUSA=true` por defecto): ante un fallo grave
  pausa, **comprueba en la máquina** que está pausada y avisa «he pausado, revísala» con
  botón ▶️ Reanudar. Si no consigue pausarla, avisa «párala tú». Mientras siga pausada,
  lo recuerda con foto cada `RECORDATORIO_PAUSA_MIN` (5).

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
