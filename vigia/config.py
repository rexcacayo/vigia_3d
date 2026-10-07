"""Configuración: lee .env (sin pisar variables ya exportadas)."""
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def _cargar_env(ruta: Path) -> None:
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        k, v = linea.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_cargar_env(RAIZ / ".env")


def _bool(nombre: str, defecto: str = "false") -> bool:
    return os.getenv(nombre, defecto).strip().lower() in ("1", "true", "si", "sí", "yes")


# Impresora: qué adaptador usar (fichero vigia/impresoras/<PRINTER_TIPO>.py)
PRINTER_TIPO = os.getenv("PRINTER_TIPO", "flashforge").strip().lower()
PRINTER_IP = os.getenv("PRINTER_IP", "")

# Claude
ANTHROPIC_WORKSPACE_ID = os.getenv("ANTHROPIC_WORKSPACE_ID", "").strip()
MODELO_FILTRO = os.getenv("MODELO_FILTRO", "claude-haiku-4-5-20251001")
MODELO_DIAG = os.getenv("MODELO_DIAGNOSTICO", "claude-sonnet-5-5")

# Precios en USD por millón de tokens: entrada, salida, escritura de caché, lectura de caché.
# Revisa https://claude.com/pricing: si cambian, ajústalos en el .env (PRECIO_<MODELO>=a,b,c,d).
PRECIOS_DEFECTO = {
    "claude-haiku-4-5": (1.00, 5.00, 1.25, 0.10),
    "claude-sonnet-5-5": (2.00, 10.00, 2.50, 0.20),
}


def precio(modelo: str) -> tuple[float, float, float, float]:
    clave = "PRECIO_" + modelo.upper().replace("-", "_").replace(".", "_")
    if os.getenv(clave):
        return tuple(float(x) for x in os.environ[clave].split(","))  # type: ignore[return-value]
    for prefijo, p in PRECIOS_DEFECTO.items():
        if modelo.startswith(prefijo):
            return p
    return (3.00, 15.00, 3.75, 0.30)  # desconocido: estimación prudente


# Telegram
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID", "")

# Vigilancia
INTERVALO = int(os.getenv("INTERVALO_S", "30"))
CONFIANZA_MIN = float(os.getenv("CONFIANZA_MIN", "0.6"))
COOLDOWN = int(os.getenv("COOLDOWN_AVISO_S", "600"))
FALLOS_CAMARA_AVISO = int(os.getenv("FALLOS_CAMARA_AVISO", "3"))
ZOOM_REGION = tuple(float(v) for v in os.getenv("ZOOM_REGION", "0.15,0.2,0.85,0.9").split(","))
FILTRO_CON_ZOOM = _bool("FILTRO_CON_ZOOM", "true")  # false = filtro ~45 % más barato
DIAG_CADA = int(os.getenv("DIAG_CADA", "10"))
INFORME_CADA_MIN = float(os.getenv("INFORME_CADA_MIN", "0"))
AUTO_PAUSA = _bool("AUTO_PAUSA")

# Correcciones: off | proponer | auto
CORRECCION_MODO = os.getenv("CORRECCION_MODO", "proponer").strip().lower()
CORRECCION_CONFIANZA = float(os.getenv("CORRECCION_CONFIANZA", "0.8"))
CORRECCION_MAX = int(os.getenv("CORRECCION_MAX", "3"))
CORRECCION_ESPERA_S = int(os.getenv("CORRECCION_ESPERA_S", "300"))
REVERTIR_TRAS_OK = int(os.getenv("REVERTIR_TRAS_OK", "3"))  # diagnósticos ok seguidos

# Ficheros
DIR_CASOS = Path(os.getenv("DIR_CASOS", str(RAIZ / "casos")))
DIR_CASOS.mkdir(parents=True, exist_ok=True)
DIR_SKILL = RAIZ / "skill"
FICHERO_APRENDIZAJES = DIR_SKILL / "aprendizajes.md"
