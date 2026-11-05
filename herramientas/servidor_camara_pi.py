"""Servidor mínimo para usar la cámara de una Raspberry como CAMARA_EXTRA desde otro equipo.

En la Raspberry (solo necesita Python 3 y rpicam-still/libcamera-still):
    python3 servidor_camara_pi.py            # escucha en el puerto 8081
En el .env del vigía (en el PC):
    CAMARA_EXTRA=http://<ip-de-la-pi>:8081/foto.jpg

Cada petición saca una foto nueva. Solo para la red local: no tiene autenticación.
"""
import http.server
import shutil
import subprocess
import sys
import threading

PUERTO = int(sys.argv[1]) if len(sys.argv) > 1 else 8081
EXE = shutil.which("rpicam-still") or shutil.which("libcamera-still")
LOCK = threading.Lock()


class Manejador(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path.split("?")[0] != "/foto.jpg":
            self.send_error(404, "Usa /foto.jpg")
            return
        with LOCK:  # la cámara CSI no admite dos capturas a la vez
            r = subprocess.run([EXE, "-n", "-t", "800", "--width", "1280", "--height", "960",
                                "-e", "jpg", "-o", "-"], capture_output=True, timeout=20, check=False)
        if r.stdout[:2] != b"\xff\xd8":
            self.send_error(500, "La cámara no dio imagen")
            return
        self.send_response(200)
        self.send_header("Content-Type", "image/jpeg")
        self.send_header("Content-Length", str(len(r.stdout)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(r.stdout)

    def log_message(self, *_):
        pass


if __name__ == "__main__":
    if not EXE:
        sys.exit("No encuentro rpicam-still ni libcamera-still: ¿está la cámara activada en Raspberry Pi OS?")
    print(f"📷 Cámara de la Pi en http://0.0.0.0:{PUERTO}/foto.jpg  (Ctrl+C para parar)")
    http.server.ThreadingHTTPServer(("0.0.0.0", PUERTO), Manejador).serve_forever()
