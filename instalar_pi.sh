#!/usr/bin/env bash
# Instala el vigía en una Raspberry Pi como SERVICIO (arranca solo y se reinicia si cae).
# Recomendado: Raspberry Pi OS Lite 64 bits (Bookworm). Ejecutar desde la carpeta del proyecto:
#     bash instalar_pi.sh
set -e
cd "$(dirname "$0")"
DIR=$(pwd)

echo "📦 Dependencias del sistema…"
sudo apt-get update -qq
sudo apt-get install -y -qq python3-venv python3-pip ffmpeg v4l-utils git
command -v rpicam-still >/dev/null || command -v libcamera-still >/dev/null || \
  sudo apt-get install -y -qq rpicam-apps || echo "ℹ️  Sin rpicam-apps: solo cámaras USB/URL"
sudo usermod -aG video "$USER"   # acceso a /dev/video* y a la cámara de la Pi

echo "🐍 Entorno de Python y .env…"
bash instalar.sh

D=$(grep -E '^DIR_CASOS=' .env | tail -1 | cut -d= -f2-); D=${D:-casos}
case "$D" in /*) ;; *) D="$DIR/$D";; esac
mkdir -p "$D"

echo "⚙️  Servicio systemd «vigia»…"
sudo tee /etc/systemd/system/vigia.service >/dev/null <<UNIT
[Unit]
Description=Vigía 3D (vigilancia de impresoras con IA)
After=network-online.target
Wants=network-online.target

[Service]
User=$USER
WorkingDirectory=$DIR
ExecStart=/bin/bash -c 'exec ./venv/bin/python -m vigia >> "$D/vigia.log" 2>&1'
Restart=always
RestartSec=15

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable vigia >/dev/null

echo
echo "📷 Cámaras que veo (para CAMARAS_EXTRA en el .env):"
./venv/bin/python -m vigia.camara_extra --listar || true
echo
echo "✅ Listo. Revisa el .env y luego:"
echo "   sudo systemctl restart vigia      # arrancar / aplicar cambios del .env"
echo "   systemctl status vigia            # ¿está vivo?"
echo "   tail -f $D/vigia.log              # qué está haciendo"
