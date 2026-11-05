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

# Cámaras extra (más vistas para el diagnóstico). Ver vigia/camara_extra.py:
#   CAMARAS_EXTRA=superior=picam, frontal=/dev/v4l/by-id/usb-…-video-index0
# CAMARA_EXTRA=<fuente> (una sola) sigue valiendo: equivale a superior=<fuente>.
CAMARAS_EXTRA = os.getenv("CAMARAS_EXTRA", "").strip()
CAMARA_EXTRA = os.getenv("CAMARA_EXTRA", "").strip()
CAMARA_EXTRA_RESOLUCION = os.getenv("CAMARA_EXTRA_RESOLUCION", "1280x960").strip()
CAMARA_EXTRA_ENFOQUE = os.getenv("CAMARA_EXTRA_ENFOQUE", "").strip()  # picam Module 3: dioptrías
CAMARA_EXTRA_V4L2 = os.getenv("CAMARA_EXTRA_V4L2", "").strip()        # USB: p. ej. focus_automatic_continuous=0
CAMARA_EXTRA_DESCRIPCION = os.getenv(
    "CAMARA_EXTRA_DESCRIPCION",
    "Cámara encima de la tapa, mirando hacia abajo en diagonal a través del plástico: "
    "ve la cara superior de la pieza; puede haber reflejos o polvo de la tapa (no son defectos).")

# Claude
ANTHROPIC_WORKSPACE_ID = os.getenv("ANTHROPIC_WORKSPACE_ID", "").strip()
MODELO_FILTRO = os.getenv("MODELO_FILTRO", "claude-haiku-4-5-20251001")
MODELO_DIAG = os.getenv("MODELO_DIAGNOSTICO", "claude-sonnet-5-5")
# Margen de salida del diagnóstico. Si se queda corto, la respuesta llega cortada y se reintenta.
MAX_TOKENS_DIAG = int(os.getenv("MAX_TOKENS_DIAG", "2000"))

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


# Tope de gasto diario en USD (0 = sin tope). Al 80 % avisa; al 100 % deja de llamar a Claude.
PRESUPUESTO_DIA = float(os.getenv("PRESUPUESTO_DIA_USD", "2"))

# Telegram
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID", "")

# Vigilancia
# Frecuencia adaptativa: mira poco cuando todo va bien y mucho cuando hay riesgo
INTERVALO = int(os.getenv("INTERVALO_S", "90"))                  # fase tranquila
INTERVALO_ALERTA = int(os.getenv("INTERVALO_ALERTA_S", "30"))     # fases de riesgo
CAPAS_RIESGO = int(os.getenv("CAPAS_RIESGO", "5"))                # primeras capas = riesgo
ALERTA_MIN = float(os.getenv("ALERTA_MIN", "10"))                 # riesgo tras una sospecha
CONFIANZA_MIN = float(os.getenv("CONFIANZA_MIN", "0.6"))
COOLDOWN = int(os.getenv("COOLDOWN_AVISO_S", "600"))
FALLOS_CAMARA_AVISO = int(os.getenv("FALLOS_CAMARA_AVISO", "3"))
ZOOM_REGION = tuple(float(v) for v in os.getenv("ZOOM_REGION", "0.15,0.2,0.85,0.9").split(","))
FILTRO_CON_ZOOM = _bool("FILTRO_CON_ZOOM", "true")  # false = filtro ~45 % más barato
DIAG_CADA_MIN = float(os.getenv("DIAG_CADA_MIN", "10"))  # diagnóstico experto periódico
INFORME_CADA_MIN = float(os.getenv("INFORME_CADA_MIN", "0"))
# Ante un "detener": pausa, comprueba que la máquina está pausada y avisa para revisarla.
AUTO_PAUSA = _bool("AUTO_PAUSA", "true")
PAUSA_VERIFICAR_S = int(os.getenv("PAUSA_VERIFICAR_S", "15"))
RECORDATORIO_PAUSA_MIN = float(os.getenv("RECORDATORIO_PAUSA_MIN", "5"))
# Red de seguridad: si el filtro sospecha N fotos seguidas y el diagnóstico no confirma
# (falla o no responde), se avisa igualmente.
# Tras un diagnóstico sin fallo, segundos mínimos antes de volver a consultar por una sospecha.
DIAG_ENTRE_SOSPECHAS_S = int(os.getenv("DIAG_ENTRE_SOSPECHAS_S", "120"))
SOSPECHAS_ALARMA = int(os.getenv("SOSPECHAS_ALARMA", "3"))

# Correcciones: off | proponer | auto
CORRECCION_MODO = os.getenv("CORRECCION_MODO", "proponer").strip().lower()
CORRECCION_CONFIANZA = float(os.getenv("CORRECCION_CONFIANZA", "0.8"))
CORRECCION_MAX = int(os.getenv("CORRECCION_MAX", "3"))
CORRECCION_ESPERA_S = int(os.getenv("CORRECCION_ESPERA_S", "300"))
REVERTIR_TRAS_OK = int(os.getenv("REVERTIR_TRAS_OK", "3"))  # diagnósticos ok seguidos

# Fotos de casos de más de N días se borran al empezar cada impresión (0 = nunca)
DIAS_RETENCION = int(os.getenv("DIAS_RETENCION", "30"))

# Ficheros
DIR_CASOS = Path(os.getenv("DIR_CASOS", str(RAIZ / "casos")))
DIR_CASOS.mkdir(parents=True, exist_ok=True)
# Skills: se instalan desde el registro OCI (repo vigia-agentes) en .skills/; si no hay
# ninguna instalada se usa la copia de respaldo del repo (skill/ y skills/).
DIR_SKILL_RESPALDO = RAIZ / "skill"
DIR_SKILLS_RESPALDO = RAIZ / "skills"
DIR_SKILL = DIR_SKILL_RESPALDO                       # skill vigia-3d en uso
DIR_SLICER = DIR_SKILLS_RESPALDO / "ad5m-slicer-engineer"
# Fichas de filamento (marca + tipo). La activa se elige con /filamento o con FILAMENTO.
DIR_FILAMENTOS = DIR_SKILL / "filamentos"
# Capa local: lo que el vigía aprende entre publicaciones (👎, historial de fichas, fichas
# nuevas). Se suma a la skill al leerla y viaja al analista para que lo proponga por PR.
DIR_LOCAL = DIR_CASOS / "aprendido"
DIR_LOCAL.mkdir(parents=True, exist_ok=True)
FICHERO_APRENDIZAJES = DIR_LOCAL / "aprendizajes.md"
DIR_FILAMENTOS_LOCAL = DIR_LOCAL / "filamentos"
FILAMENTO = os.getenv("FILAMENTO", "").strip()
# Carpeta donde guardas los .3mf laminados (Orca → Exportar). Vacía = no leer el perfil.
DIR_LAMINADOS = Path(os.getenv("DIR_LAMINADOS")) if os.getenv("DIR_LAMINADOS", "").strip() else None


SKILLS_OCI = _bool("SKILLS_OCI", "true")  # false = usar solo la copia skill/ del repo


def recargar_skills() -> None:
    """Apunta a las skills instaladas desde OCI (o al respaldo si no hay)."""
    global DIR_SKILL, DIR_SLICER, DIR_FILAMENTOS
    from . import skills_oci
    if SKILLS_OCI:
        DIR_SKILL = skills_oci.ruta("vigia-3d", DIR_SKILL_RESPALDO)
        DIR_SLICER = skills_oci.ruta("ad5m-slicer-engineer", DIR_SKILLS_RESPALDO / "ad5m-slicer-engineer")
    else:
        DIR_SKILL, DIR_SLICER = DIR_SKILL_RESPALDO, DIR_SKILLS_RESPALDO / "ad5m-slicer-engineer"
    DIR_FILAMENTOS = DIR_SKILL / "filamentos"


recargar_skills()

# Agentes de Claude Platform (repo vigia-agentes). ANALISTA=true para usarlos.
ANALISTA = _bool("ANALISTA")
REPO_AGENTES = os.getenv("REPO_AGENTES", "https://github.com/rexcacayo/vigia-agentes")
AGENTES_LOCK_URL = os.getenv(
    "AGENTES_LOCK_URL", "https://raw.githubusercontent.com/rexcacayo/vigia-agentes/main/claude-lock.json")
AGENTE_ANALISTA_ID = os.getenv("AGENTE_ANALISTA_ID", "").strip()    # vacío = del lockfile
AGENTE_FILAMENTO_ID = os.getenv("AGENTE_FILAMENTO_ID", "").strip()
ENTORNO_AGENTES_ID = os.getenv("ENTORNO_AGENTES_ID", "").strip()
VAULT_AGENTES = os.getenv("VAULT_AGENTES", "").strip()              # vlt_... (scripts/crear_vault.py)
GITHUB_TOKEN_AGENTES = os.getenv("GITHUB_TOKEN_AGENTES", "").strip()  # para que el agente abra PRs
ANALISTA_PRESUPUESTO_CENT = int(os.getenv("ANALISTA_PRESUPUESTO_CENT", "150"))  # tope por sesión
ANALISTA_TIMEOUT_MIN = int(os.getenv("ANALISTA_TIMEOUT_MIN", "30"))
