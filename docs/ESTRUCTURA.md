# Estructura del proyecto (scaffolding)

```
vigia_3d/
├── README.md                  ← qué es, instalación rápida
├── CONTRIBUTING.md            ← cómo colaborar
├── CHANGELOG.md               ← historia de versiones
├── LICENSE
├── .env.example               ← plantilla de configuración (cópiala a .env)
├── .gitignore
├── .github/workflows/tests.yml  ← ejecuta la simulación en cada push (GitHub Actions)
├── requirements.txt           ← anthropic, requests, pillow
├── instalar.sh                ← crea venv, instala y completa tu .env sin pisarlo
├── arrancar.sh                ← lanza el vigía en tmux con log
│
├── vigia/                     ← el programa
│   ├── __main__.py            ← `python -m vigia`
│   ├── main.py                ← bucle principal, órdenes y botones de Telegram, informes
│   ├── config.py              ← lee .env, parámetros, precios de la API
│   ├── maquina.py             ← carga el adaptador elegido en PRINTER_TIPO
│   ├── vision.py              ← llamadas a Claude: filtro, diagnóstico, preguntas, informe, coste
│   ├── correcciones.py        ← reglas que validan/aplican/revierten correcciones
│   ├── telegram.py            ← bot: envío con botones y escucha de órdenes
│   ├── probar.py              ← verificador de adaptadores (solo lectura)
│   └── impresoras/            ← adaptadores (uno por familia de impresoras)
│       ├── __init__.py        ← contrato: capacidades, claves de estado, validación
│       ├── flashforge.py      ← Flashforge AD5M / AD5M Pro (firmware de serie)
│       └── plantilla.py       ← punto de partida para un adaptador nuevo
│
├── skill/                     ← el CONOCIMIENTO (Markdown, se relee en cada diagnóstico)
│   ├── SKILL.md               ← rol, cómo razonar, gravedades
│   ├── materiales.md          ← qué es normal y qué vigilar por material
│   ├── correcciones.md        ← lista blanca de acciones y cuándo proponerlas
│   └── aprendizajes.md        ← casos corregidos por el usuario (crece solo con 👎)
│
├── tests/
│   └── simulacion.py          ← impresión simulada de principio a fin (sin hardware)
│
└── docs/
    ├── ARQUITECTURA.md        ← diseño, flujos, decisiones, seguridad
    ├── ESTRUCTURA.md          ← este fichero
    ├── CONFIGURACION.md       ← todas las variables del .env
    ├── MODIFICAR.md           ← recetas para cambiar cada parte
    ├── ADAPTADORES.md         ← cómo soportar otra impresora
    ├── COMPATIBILIDAD.md      ← impresoras y comandos de cada API
    └── COSTES.md              ← cuánto cuesta por hora de impresión
```

## Qué hace cada módulo

### `vigia/main.py`: orquestación
| Pieza | Qué hace |
|---|---|
| `Vigia.ciclo_vigilancia()` | Un ciclo: estado → foto → filtro → (diagnóstico) → avisos → correcciones |
| `_nuevo_trabajo()` / `_fin_trabajo()` | Detecta inicio y fin de impresión; reinicia motor y contador; lanza el informe |
| `_avisar_problema()` | Aviso 🟡 o 🛑 con foto y botones, con espera anti-spam (`COOLDOWN_AVISO_S`) |
| `_correcciones()` | Pasa el diagnóstico al motor; propone con botones o aplica (modo auto); revierte |
| `comando()` | Órdenes `/estado /foto /parte /pausa /reanudar /modo /coste /informe /ayuda` |
| `boton()` | Botones: pausar, aplicar/ignorar corrección, 👍/👎 |
| `texto_libre()` | Comentario tras 👎 → aprendizaje; si no, pregunta libre a Claude con foto |
| `_guardar_caso()` | Foto + línea en `casos.jsonl` |

### `vigia/vision.py`: IA
| Pieza | Modelo | Qué hace |
|---|---|---|
| `filtrar(jpeg)` | Haiku | ¿Merece una segunda mirada? → `{estado, motivo}` |
| `diagnosticar(fotos, estado)` | Sonnet | Diagnóstico con la skill → JSON con gravedad y acción |
| `preguntar(jpeg, estado, texto)` | Sonnet | Responde preguntas libres por Telegram |
| `informe_postmortem(registro)` | Sonnet | Informe con recomendaciones de perfil Orca |
| `ampliar(jpeg)` | — | Recorta `ZOOM_REGION` y amplía ×2 |
| `sistema_diagnostico()` | — | Monta el prompt: SKILL + máquina + materiales + correcciones + aprendizajes |
| `Contador` | — | Suma tokens y USD de cada llamada |

### `vigia/correcciones.py`: decisiones
| Pieza | Qué hace |
|---|---|
| `Motor.evaluar(diag, estado)` | Valida la propuesta: capacidad de la máquina, confianza, persistencia, máximo, espera, límites |
| `Motor._calcular()` | Calcula el valor objetivo con límites por material |
| `Motor.aplicar(prop)` | Llama al adaptador y registra el valor original |
| `Motor.tras_diagnostico(diag)` | Tras N diagnósticos "ok" seguidos, revierte velocidad/ventilador/flujo |

### `vigia/impresoras/`: adaptadores
Contrato completo en [ADAPTADORES.md](ADAPTADORES.md).
