# Coste por hora de impresión

El vigía solo gasta en la **API de Claude**. Telegram y la impresora no cuestan nada.
El coste depende sobre todo de **cada cuánto mira** (`INTERVALO_S`) y de **cuántas veces
despierta al experto** (diagnósticos profundos).

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

| Perfil | Ajustes | Filtros/h | Diagnósticos/h* | **Coste/h** |
|---|---|---|---|---|
| **Pruebas** | `INTERVALO_S=30` · `INFORME_CADA_MIN=5` · `DIAG_CADA=10` | 120 × $0,0016 = $0,19 | ~20 × $0,0075 = $0,15 | **≈ $0,35** |
| **Normal** | `INTERVALO_S=30` · `INFORME_CADA_MIN=30` · `DIAG_CADA=20` | 120 × $0,0016 = $0,19 | ~11 × $0,011 = $0,12 | **≈ $0,30** |
| **Económico** | `INTERVALO_S=60` · `INFORME_CADA_MIN=0` · `DIAG_CADA=20` · `FILTRO_CON_ZOOM=false` | 60 × $0,0008 = $0,05 | ~5 × $0,012 = $0,06 | **≈ $0,11** |

\* Periódicos + partes + los que dispara el filtro al sospechar (se suponen 2–5 por hora).

### Ejemplos por impresión
| Impresión | Pruebas | Normal | Económico |
|---|---|---|---|
| 2 h | ~$0,70 | ~$0,60 | ~$0,25 |
| 5 h 46 m (la peana de Dora) | ~$2,00 | ~$1,75 | ~$0,65 |
| 10 h | ~$3,50 | ~$3,00 | ~$1,10 |

## El factor que más pesa: los falsos positivos del filtro

Cada vez que el filtro dice "sospecha", se paga un diagnóstico de Sonnet. Si el filtro se
vuelve alarmista y sospecha en **todos** los ciclos, el coste sube a **~$1/h**
(120 diagnósticos/h). Por eso:
- Mira en el log la línea `filtro: sospecha — <motivo>`. Si se repite sin motivo real,
  marca 👎 en los avisos y ajusta el prompt `FILTRO` en `vigia/vision.py` (ver
  [MODIFICAR.md](MODIFICAR.md)).
- `/coste` a mitad de impresión te dice el ritmo real (`$/h`).

## Cómo bajar el coste

| Palanca | Efecto | Contrapartida |
|---|---|---|
| `INTERVALO_S=60` | Filtro a la mitad | Un fallo se detecta, como mucho, 30 s más tarde |
| `FILTRO_CON_ZOOM=false` | Filtro ~50 % más barato | Ve peor los detalles pequeños |
| `INFORME_CADA_MIN=0` o alto | Menos diagnósticos | Menos partes de "todo va bien" |
| `DIAG_CADA` alto (20–40) | Menos diagnósticos periódicos | El experto revisa con menos frecuencia |
| `MODELO_DIAGNOSTICO` = Haiku | Diagnóstico ~3–5× más barato | Diagnósticos menos finos |

## Referencia: coste de la impresión en sí

Para ponerlo en contexto, una hora de impresión FDM en una máquina como la AD5M Pro gasta
del orden de 10–25 g de filamento (≈ €0,20–0,60) y 0,1–0,3 kWh de electricidad. Con el
perfil normal, el vigía añade un coste del mismo orden. Compensa en cuanto evita **una**
impresión fallida de varias horas.
