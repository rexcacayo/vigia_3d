# Coste por hora de impresión

El vigía solo gasta en la **API de Claude**. Telegram y la impresora no cuestan nada.
El coste depende sobre todo de **cada cuánto mira** y de **cuántas veces despierta al
experto** (diagnósticos profundos). La frecuencia es **adaptativa**: cada `INTERVALO_S` en
calma y cada `INTERVALO_ALERTA_S` en las primeras capas y tras cualquier sospecha, así que
se paga precisión solo cuando hace falta.

> 💡 No hace falta fiarse de estas estimaciones: el vigía **mide el coste real** con los
> tokens que devuelve la API. Escribe `/coste` en Telegram durante la impresión; el
> informe final también lo incluye.

## Precios usados (USD por millón de tokens)

| Modelo | Uso | Entrada | Salida | Escritura caché | Lectura caché |
|---|---|---|---|---|---|
| Claude Haiku 4.5 | Filtro | $1,00 | $5,00 | $1,25 | $0,10 |
| Claude Sonnet 5.5 | Diagnóstico, preguntas, informe | $2,00 | $10,00 | $2,50 | $0,20 |

Fuente: [precios de la API](https://platform.claude.com/docs/en/about-claude/pricing), consultados en
octubre de 2026. Los precios cambian: compruébalos y, si hace falta, ajústalos con
`PRECIO_<MODELO>` en el `.env` (ver [CONFIGURACION.md](CONFIGURACION.md)).

## Qué cuesta cada llamada

Las imágenes cuestan `⌈ancho/28⌉ × ⌈alto/28⌉` tokens: una foto de 640×480 son **414
tokens** y la ampliación (896×672), **768 tokens**.

| Llamada | Contenido aproximado | Coste por llamada |
|---|---|---|
| **Filtro con zoom** (Haiku) | foto + ampliación + prompt ≈ 1.400 tokens · respuesta ≈ 40 | **≈ $0,0016** |
| **Filtro sin zoom** (Haiku) | foto + prompt ≈ 630 tokens · respuesta ≈ 40 | **≈ $0,0008** |
| **Diagnóstico** (Sonnet) | 3 fotos + ampliación + estado ≈ 2.260 tokens · skill ≈ 2.100 (en caché) · respuesta ≈ 250 | **≈ $0,007** con caché · **≈ $0,012** sin caché |
| **Pregunta libre** (Sonnet) | foto + ampliación + skill + pregunta | ≈ $0,008 |
| **Informe final** (Sonnet) | registro de la impresión | ≈ $0,01–0,03 (una vez) |

La skill se envía con **caché de prompt**: si dos diagnósticos están a menos de 5 minutos,
el segundo lee la skill de la caché, unas 10 veces más barato.

## Coste por hora según el perfil

| Perfil | Ajustes | Filtros/h† | Diagnósticos/h* | **Coste/h** |
|---|---|---|---|---|
| **Pruebas** | calma 60 s · alerta 20 s · experto cada 5 min · parte cada 5 min | ~70 × $0,0016 = $0,11 | ~15 × $0,0075 = $0,11 | **≈ $0,22** |
| **Normal** (defecto) | calma 90 s · alerta 30 s · experto cada 10 min · parte cada 30 min | ~45 × $0,0016 = $0,07 | ~9 × $0,011 = $0,10 | **≈ $0,17** |
| **Económico** | calma 180 s · alerta 45 s · experto cada 20 min · sin partes · filtro sin zoom | ~25 × $0,0008 = $0,02 | ~5 × $0,012 = $0,06 | **≈ $0,08** |

† Suponiendo ~15 % del tiempo en modo alerta (primeras capas + sospechas).
\* Periódicos + partes + los que dispara el filtro al sospechar (se suponen 2–5 por hora).

**Tiempo de detección:** en calma, un fallo se ve como mucho en `INTERVALO_S` (90 s en el
perfil normal). Desde la primera sospecha, el vigía mira cada `INTERVALO_ALERTA_S` (30 s).

### Ejemplos por impresión
| Impresión | Pruebas | Normal | Económico |
|---|---|---|---|
| 2 h | ~$0,45 | ~$0,35 | ~$0,16 |
| 5 h 46 m (la peana de Dora) | ~$1,25 | ~$1,00 | ~$0,45 |
| 10 h | ~$2,20 | ~$1,70 | ~$0,80 |

## El factor que más pesa: los falsos positivos del filtro

Cada vez que el filtro dice "sospecha", se paga un diagnóstico de Sonnet. Si el filtro se
vuelve alarmista y sospecha en **todos** los ciclos, el coste sube a **~$1/h**
(el modo alerta lo mantiene a 30 s y cada ciclo despierta a Sonnet: ~120 diagnósticos/h). Por eso:
- Mira en el log la línea `filtro: sospecha — <motivo>`. Si se repite sin motivo real,
  marca 👎 en los avisos y ajusta el prompt `FILTRO` en `vigia/vision.py` (ver
  [MODIFICAR.md](MODIFICAR.md)).
- `/coste` a mitad de impresión te dice el ritmo real (`$/h`).

## Tope de gasto diario

`PRESUPUESTO_DIA_USD` (2 $ por defecto) protege de sorpresas, por ejemplo un filtro
alarmista o una impresión de 3 días:
- Al **80 %** del tope, aviso por Telegram.
- Al **100 %**, el vigía deja de consultar a Claude hasta el día siguiente y sigue
  vigilando solo el estado de la máquina (errores y fin de impresión). Te avisa.
- El gasto se guarda en `DIR_CASOS/gasto_diario.json`, así que sobrevive a reinicios.
- `/coste` muestra lo gastado en la impresión y en el día.

Con el perfil normal (~$0,17/h), 2 $ dan para unas 11 horas de vigilancia al día.

## Cómo bajar el coste

| Palanca | Efecto | Contrapartida |
|---|---|---|
| `INTERVALO_S` más alto (120–180) | Menos filtros en calma | En calma, un fallo tarda más en verse (el modo alerta sigue a 30 s) |
| `FILTRO_CON_ZOOM=false` | Filtro ~50 % más barato | Ve peor los detalles pequeños |
| `INFORME_CADA_MIN=0` o alto | Menos diagnósticos | Menos partes de "todo va bien" |
| `DIAG_CADA_MIN` alto (20–30) | Menos diagnósticos periódicos | El experto revisa con menos frecuencia |
| `ALERTA_MIN` más bajo (5) | Menos tiempo a frecuencia alta | Menos fotos para confirmar una sospecha |
| `MODELO_DIAGNOSTICO` = Haiku | Diagnóstico ~3–5× más barato | Diagnósticos menos finos |

## Referencia: coste de la impresión en sí

Para ponerlo en contexto, una hora de impresión FDM en una máquina como la AD5M Pro gasta
del orden de 10–25 g de filamento (≈ €0,20–0,60) y 0,1–0,3 kWh de electricidad. Con el
perfil normal, el vigía añade un coste menor que eso. Compensa en cuanto evita **una**
impresión fallida de varias horas.
