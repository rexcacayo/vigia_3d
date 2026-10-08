# Configuración (`.env`)

Copia `.env.example` a `.env` **solo la primera vez**. Para añadir opciones nuevas tras
actualizar, usa `bash instalar.sh`, que completa tu `.env` sin tocar lo que ya tienes.

## Impresora
| Variable | Por defecto | Qué es |
|---|---|---|
| `PRINTER_TIPO` | `flashforge` | Adaptador a usar: `vigia/impresoras/<PRINTER_TIPO>.py` |
| `PRINTER_IP` | — | IP de la impresora en tu red |
| `PRINTER_SN` | — | *(Flashforge)* Número de serie (`~M115` o *Ajustes → Acerca de*) |
| `PRINTER_CHECK_CODE` | — | *(Flashforge)* "ID de la impresora" en *Ajustes → Red* |

## Claude
| Variable | Por defecto | Qué es |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Key de la API (console.anthropic.com). La suscripción de Claude no sirve |
| `ANTHROPIC_WORKSPACE_ID` | vacío | Solo si tu key no está asociada a un workspace (`wrkspc_…`) |
| `MODELO_FILTRO` | `claude-haiku-4-5-20251001` | Modelo del filtro rápido |
| `MODELO_DIAGNOSTICO` | `claude-sonnet-5-5` | Modelo del diagnóstico, preguntas e informes |
| `PRECIO_<MODELO>` | ver `config.py` | Precios USD/millón: `entrada,salida,escritura_caché,lectura_caché` (p. ej. `PRECIO_CLAUDE_SONNET_5_5=2,10,2.5,0.2`) |

## Telegram
| Variable | Qué es |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token de @BotFather |
| `TELEGRAM_CHAT_ID` | Tu chat (el único que puede dar órdenes). Escribe al bot y consulta `getUpdates` |

## Vigilancia
| Variable | Por defecto | Qué es |
|---|---|---|
| `INTERVALO_S` | `90` | Segundos entre ciclos (foto + filtro) en **calma** |
| `INTERVALO_ALERTA_S` | `30` | Segundos entre ciclos en **fases de riesgo** |
| `CAPAS_RIESGO` | `5` | Las primeras N capas se vigilan como riesgo |
| `ALERTA_MIN` | `10` | Minutos en modo alerta tras una sospecha o un diagnóstico no-ok |
| `DIAG_CADA_MIN` | `10` | Diagnóstico experto periódico cada N minutos aunque el filtro diga ok |
| `INFORME_CADA_MIN` | `0` | Parte con foto cada N minutos (0 = solo avisos) |
| `CONFIANZA_MIN` | `0.6` | Confianza mínima para avisar de un problema |
| `COOLDOWN_AVISO_S` | `600` | No repetir el mismo aviso antes de N s (los de detener, a la tercera parte) |
| `FALLOS_CAMARA_AVISO` | `3` | Avisar tras N fallos seguidos de cámara |
| `ZOOM_REGION` | `0.15,0.2,0.85,0.9` | Zona de la foto (fracciones x0,y0,x1,y1) que se amplía |
| `FILTRO_CON_ZOOM` | `true` | El filtro mira también la ampliación (más preciso, ~2× su coste) |
| `AUTO_PAUSA` | `true` | Ante un "detener": pausa, comprueba que la máquina está pausada y avisa para que la revises (con `false` solo te da el botón) |
| `RECORDATORIO_PAUSA_MIN` | `5` | Mientras siga pausada por el vigía, recuerda cada N min con foto (0 = no recordar) |
| `PAUSA_VERIFICAR_S` | `15` | Segundos que espera a ver la máquina pausada; si no, avisa «no he podido pausarla» |
| `DIAG_ENTRE_SOSPECHAS_S` | `120` | Tras un diagnóstico sin fallo, espera mínima antes de volver a consultar por una sospecha del filtro (ahorro) |
| `SOSPECHAS_ALARMA` | `3` | Sospechas seguidas del filtro sin diagnóstico que confirme → aviso de respaldo |
| `MAX_TOKENS_DIAG` | `2000` | Margen de respuesta del diagnóstico (si llega cortado, reintenta con el doble) |

## Gasto y limpieza
| Variable | Por defecto | Qué es |
|---|---|---|
| `PRESUPUESTO_DIA_USD` | `2` | Tope de gasto diario en Claude (0 = sin tope). Al 80 % avisa; al 100 % deja de consultar a Claude hasta el día siguiente y sigue vigilando solo el estado de la máquina |
| `DIAS_RETENCION` | `30` | Borra las fotos de casos con más de N días al arrancar y al empezar cada impresión (0 = nunca). `casos.jsonl` e informes se conservan |

## Correcciones
| Variable | Por defecto | Qué es |
|---|---|---|
| `CORRECCION_MODO` | `proponer` | `off`, `proponer` (botones) o `auto`. Se cambia en marcha con `/modo` |
| `CORRECCION_CONFIANZA` | `0.8` | Confianza mínima para proponer una corrección |
| `CORRECCION_MAX` | `3` | Cambios máximos por impresión |
| `CORRECCION_ESPERA_S` | `300` | Espera mínima entre cambios |
| `REVERTIR_TRAS_OK` | `3` | Diagnósticos "ok" seguidos para revertir velocidad/ventilador/flujo |

## Ficheros
| Variable | Por defecto | Qué es |
|---|---|---|
| `DIR_CASOS` | `casos` | Fotos, `casos.jsonl`, log e informes. En WSL puede ser una carpeta de Windows (`/mnt/c/Users/<usuario>/Documents/vigia`) |

## Perfiles de ejemplo
| Perfil | Ajustes | Para qué |
|---|---|---|
| **Pruebas** | `INTERVALO_S=60` `INTERVALO_ALERTA_S=20` `DIAG_CADA_MIN=5` `INFORME_CADA_MIN=5` | Ver qué piensa en cada momento y calibrar |
| **Normal** (por defecto) | `INTERVALO_S=90` `INTERVALO_ALERTA_S=30` `DIAG_CADA_MIN=10` `INFORME_CADA_MIN=30` | Uso diario |
| **Económico** | `INTERVALO_S=180` `INTERVALO_ALERTA_S=45` `DIAG_CADA_MIN=20` `INFORME_CADA_MIN=0` `FILTRO_CON_ZOOM=false` | Impresiones largas y fiables |

Costes de cada perfil: [COSTES.md](COSTES.md).
