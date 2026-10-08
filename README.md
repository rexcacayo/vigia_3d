# 🔭 Vigía 3D

[![tests](https://github.com/rexcacayo/vigia_3d/actions/workflows/tests.yml/badge.svg)](https://github.com/rexcacayo/vigia_3d/actions/workflows/tests.yml)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)

**Un vigía con IA para tu impresora 3D.** Mira la impresión por la cámara, entiende qué
pasa con Claude, te avisa por Telegram con foto y diagnóstico, **propone correcciones en
marcha** (velocidad, temperatura, Z offset…) que aplicas con un botón, y al terminar te
da un **informe con ajustes de perfil** para tu slicer. Y aprende de tus correcciones.

> Los sistemas comerciales detectan el espagueti y pausan. El Vigía 3D además te dice
> **qué parámetro falló y qué cambiar**, y lo corrige en la propia impresión cuando se puede.

```
🟡 Aviso
Claude: fallo / vigilar (85 %) · isla_fallida
Zona: dedos de la mano
Rizos y pegotes sobre los dedos: las islas pequeñas no llegan a enfriar.
Propone: velocidad -20 — más tiempo de capa para los detalles

🔧 Propongo una corrección
Velocidad: 100 % → 80 %            [ ✅ Aplicar ]  [ ❌ Ignorar ]
```

## Qué hace

- 👁️ **Vigila con frecuencia adaptativa**: cada 90 s en calma y cada 30 s en las primeras
  capas o en cuanto algo le parece raro. Un filtro barato (Claude Haiku) llama al experto
  (Claude Sonnet + skill) solo cuando hace falta.
- 🧠 **Diagnostica** con contexto: material, capa, temperaturas, evolución entre fotos y
  una ampliación de la pieza.
- 📲 **Telegram**: avisos 🟡/🛑, partes periódicos, `⏸️ Pausar ahora`, preguntas libres
  ("¿cómo va la mano?") y órdenes (`/estado`, `/foto`, `/parte`, `/pausa`, `/coste`…).
- 🔧 **Corrige en marcha** con seguridad: la IA **propone**, unas reglas fijas **deciden**
  (lista blanca, límites por material, persistencia, máximo de cambios, reversión).
- 📚 **Aprende**: 👎 + una frase en Telegram y ese caso pasa a la skill.
- 📝 **Informe post-mortem** con recomendaciones de perfil y calibraciones para OrcaSlicer.
- 💶 **Mide su propio coste**: unos **$0,08–0,25 por hora** de impresión según el perfil.
- 🔌 **Enchufable**: un fichero por familia de impresoras.

## Impresoras

| | Estado |
|---|---|
| Flashforge Adventurer 5M Pro (firmware de serie) | ✅ Probada |
| Flashforge AD5M / AD5X / Creator 5 | 🟡 Misma API, sin probar |
| Klipper + Moonraker | 🔜 Esbozo de adaptador listo para completar |
| OctoPrint · Bambu Lab (LAN) | 💡 Posibles |

Detalle y comandos de cada API: [docs/COMPATIBILIDAD.md](docs/COMPATIBILIDAD.md).

## Requisitos
- Linux, WSL o Raspberry Pi con Python 3.10+ y `tmux`, en la misma red que la impresora.
- Una **API key de Claude** ([console.anthropic.com](https://console.anthropic.com)): es
  independiente de la suscripción de Claude.
- Un **bot de Telegram** (@BotFather) y tu `chat_id`.

## Instalación

```bash
git clone https://github.com/rexcacayo/vigia_3d.git
cd vigia_3d
bash instalar.sh          # crea venv, instala dependencias y crea .env
nano .env                 # IP, nº de serie y código de la impresora, API key, Telegram
./venv/bin/python -m vigia.probar --claude   # comprueba impresora, cámara y Claude
./arrancar.sh             # ¡a vigilar! (en segundo plano, con log)
```

Escribe `/ayuda` a tu bot. Guía de todas las opciones: [docs/CONFIGURACION.md](docs/CONFIGURACION.md).

> ⚠️ **Flashforge:** la cámara admite un solo espectador. Si la pestaña *Dispositivo* de
> Orca está abierta, el vigía no puede ver.

## Documentación

| Documento | Para… |
|---|---|
| [Arquitectura](docs/ARQUITECTURA.md) | Entender el diseño, los flujos y las decisiones |
| [Estructura](docs/ESTRUCTURA.md) | Saber qué hace cada fichero |
| [Configuración](docs/CONFIGURACION.md) | Todas las variables del `.env` y perfiles |
| [Modificar](docs/MODIFICAR.md) | Recetas: criterio, filtro, reglas, órdenes, nuevas correcciones |
| [Adaptadores](docs/ADAPTADORES.md) | Soportar otra impresora |
| [Compatibilidad](docs/COMPATIBILIDAD.md) | Impresoras y comandos de cada API |
| [Costes](docs/COSTES.md) | Cuánto cuesta por hora y cómo bajarlo |
| [Prueba real](docs/PRUEBA_REAL.md) | Checklist para validar una versión con la impresora |
| [Hoja de ruta](docs/ROADMAP.md) | Qué falta por verificar, mejoras y nuevos alcances |

## ⚠️ Aviso de seguridad

Una impresora 3D trabaja con piezas a más de 200 °C. **El Vigía 3D es una ayuda, no
sustituye la supervisión humana ni las medidas de seguridad de tu taller** (detector de
humo, no dejar la impresora sin nadie cerca de forma prolongada, revisar la instalación
eléctrica…). La IA puede equivocarse: no detectar un fallo o avisar de uno que no existe.
Este software se ofrece **sin ninguna garantía** (ver [LICENSE](LICENSE)) y lo usas bajo
tu propia responsabilidad.

## Seguridad del diseño
- Solo **tu chat** de Telegram puede dar órdenes.
- La IA **nunca** envía comandos directos: elige de una lista blanca y el código aplica
  límites duros. **Nunca cancela** una impresión.
- Modo por defecto `proponer`: nada cambia sin que pulses **Aplicar**.
- **Tope de gasto diario** (`PRESUPUESTO_DIA_USD`, 2 $ por defecto): al alcanzarlo deja de
  consultar a Claude y te avisa.

## Probar sin impresora
```bash
./venv/bin/python -m tests.simulacion
```

## Contexto
La corrección de errores en tiempo real con visión ya se ha demostrado en investigación
([CAXTON, Cambridge 2022](https://www.nature.com/articles/s41467-022-31985-y);
[agentes con LLM, 2026](https://techxplore.com/news/2026-02-ai-3d-defects-real.html)).
Este proyecto lo lleva a una impresora doméstica, sin entrenar modelos, con una skill
editable y supervisión humana.

## Licencia
[GPL-3.0](LICENSE). Contribuciones bienvenidas: ver [CONTRIBUTING.md](CONTRIBUTING.md).

---

### English summary
**Vigía 3D** is an AI watchdog for 3D printers. It watches the print through the
printer's camera, diagnoses issues with Claude (cheap Haiku filter + Sonnet expert with an
editable Markdown "skill"), sends Telegram alerts with photos, proposes safe live
corrections (speed, temperatures, Z offset) gated by deterministic rules, learns from your
👍/👎 feedback, and writes a post-print report with slicer profile recommendations.
Works today with the Flashforge Adventurer 5M Pro; printer support is pluggable
(one adapter file per printer family). Docs are in Spanish.
