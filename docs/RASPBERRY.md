# Vigía en una Raspberry Pi con una o varias cámaras

El vigía corre en la Pi las 24 h como servicio; Claude y los agentes siguen en la nube, así
que la Pi solo saca fotos y hace llamadas HTTP.

## Equipo
| Pieza | Recomendación | Notas |
|---|---|---|
| Raspberry Pi | Pi 4 o 5 (2–4 GB). Una **Pi 3 B+** vale para 1–2 cámaras | Con más cámaras o reemisión de vídeo, Pi 4/5 |
| Fuente | Oficial (Pi 3/4: 5 V 3 A · Pi 5: 27 W) | Fuentes malas = cuelgues y cámaras que desaparecen |
| Almacenamiento | Tarjeta para el sistema + **pendrive/SSD USB** para `DIR_CASOS` | Las fotos continuas desgastan la tarjeta SD |
| Cámara superior | Logitech C920/C922 encima de la tapa, con cubrelente negro | Autoenfoque apagado con `CAMARA_<NOMBRE>_V4L2` |
| Cámara de la Pi | Cualquier Camera Module (v1.3, v2, 3) por cinta CSI | Cinta larga (50 cm–1 m) si la Pi no está pegada a la tapa |
| Más cámaras USB | UVC con salida MJPEG | Sin MJPEG, la Pi 3 se satura |

## Instalación
1. Raspberry Pi OS **Lite 64 bits** (Raspberry Pi Imager: usuario, Wi-Fi y SSH desde el propio Imager).
2. En la Pi:
   ```bash
   git clone https://github.com/rexcacayo/vigia_3d.git && cd vigia_3d && bash instalar_pi.sh
   ```
   Instala dependencias, crea el servicio `vigia` y **lista las cámaras** que ve.
3. Copia tu `.env` del PC (por `scp`, nunca por chat) y ajusta:
   ```
   DIR_CASOS=/mnt/vigia          # el pendrive/SSD
   CAMARAS_EXTRA=superior=/dev/v4l/by-id/usb-046d_HD_Pro_Webcam_C920_XXXX-video-index0, pi=picam
   CAMARA_SUPERIOR_V4L2=focus_automatic_continuous=0,focus_absolute=40
   ```
   Usa las rutas `/dev/v4l/by-id/…` que imprime el instalador: `/dev/video0` puede cambiar
   al reiniciar.
4. Prueba las cámaras y arranca:
   ```bash
   ./venv/bin/python -m vigia.camara_extra      # una foto por cámara en DIR_CASOS
   sudo systemctl restart vigia && systemctl status vigia
   ```

## Cómo usa el vigía las cámaras
- El **filtro rápido** (Haiku) mira solo la cámara de la impresora: no sube el coste por foto.
- El **diagnóstico** (Sonnet) recibe todas las vistas del mismo momento, cada una con su
  descripción (`CAMARA_<NOMBRE>_DESCRIPCION`). Cada vista extra añade ~400–800 tokens.
- Cada caso guarda una foto por cámara (`<caso>_<nombre>.jpg`), que también recibe el analista.
- Por Telegram llegan todas las vistas con los partes, los avisos y `/foto`.
- Si una cámara falla, el vigía sigue con las demás.

## Mantenimiento
| Quiero… | Hago |
|---|---|
| Ver si está vivo | `systemctl status vigia` o `/estado` en Telegram |
| Ver el log | `tail -f /mnt/vigia/vigia.log` |
| Actualizar | `git pull --autostash && bash instalar.sh && sudo systemctl restart vigia` |
| Pararlo | `sudo systemctl stop vigia` |
