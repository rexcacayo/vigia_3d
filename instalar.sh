#!/usr/bin/env bash
# Instala dependencias y completa el .env con las opciones nuevas SIN tocar las que ya tienes.
set -e
cd "$(dirname "$0")"
[ -d venv ] || python3 -m venv venv
./venv/bin/pip install -q -r requirements.txt
if [ ! -f .env ]; then
  cp .env.example .env
  echo "⚠️  He creado .env desde el ejemplo: rellena PRINTER_SN, PRINTER_CHECK_CODE, API key y Telegram."
else
  ./venv/bin/python - <<'PY'
from pathlib import Path
env, ej = Path(".env"), Path(".env.example")
texto = env.read_text(encoding="utf-8")
tengo = {l.split("=",1)[0].strip() for l in texto.splitlines() if "=" in l and not l.lstrip().startswith("#")}
nuevas = [l for l in ej.read_text(encoding="utf-8").splitlines()
          if "=" in l and not l.lstrip().startswith("#") and l.split("=",1)[0].strip() not in tengo]
# Nunca añadir valores de ejemplo de credenciales
nuevas = [l for l in nuevas if not l.startswith(("PRINTER_SN=", "PRINTER_CHECK_CODE=", "ANTHROPIC_API_KEY=",
                                                 "TELEGRAM_BOT_TOKEN=", "TELEGRAM_CHAT_ID=", "PRINTER_IP="))]
if nuevas:
    if not texto.endswith("\n"):
        texto += "\n"
    texto += "\n# --- añadido por instalar.sh\n" + "\n".join(nuevas) + "\n"
    env.write_text(texto, encoding="utf-8")
    print("Añadidas al .env:", ", ".join(l.split("=")[0] for l in nuevas))
else:
    print(".env ya tenía todas las opciones")
PY
fi
D=$(grep -E '^DIR_CASOS=' .env | tail -1 | cut -d= -f2-); mkdir -p "${D:-casos}"
chmod +x arrancar.sh
echo "✅ Instalado. Arranca con: ./arrancar.sh"
