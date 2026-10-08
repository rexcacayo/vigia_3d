"""Simulación de una impresión completa SIN impresora, SIN Claude y SIN Telegram.

    ./venv/bin/python -m tests.simulacion

Comprueba: inicio de vigilancia, avisos, propuesta y aplicación de correcciones,
reversión, pausa, aprendizaje por feedback, coste e informe final.
"""
import io
import json
import os
import shutil
import tempfile
import types
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="vigia_test_"))
os.environ.update({
    "PRINTER_TIPO": "flashforge", "PRINTER_IP": "192.0.2.1", "PRINTER_SN": "SN-TEST",
    "PRINTER_CHECK_CODE": "test", "ANTHROPIC_API_KEY": "sk-test", "TELEGRAM_BOT_TOKEN": "t",
    "TELEGRAM_CHAT_ID": "42", "DIR_CASOS": str(TMP), "CORRECCION_ESPERA_S": "0",
    "INFORME_CADA_MIN": "0", "INTERVALO_S": "90", "INTERVALO_ALERTA_S": "30",
    "CAPAS_RIESGO": "5", "CORRECCION_MODO": "proponer", "PRESUPUESTO_DIA_USD": "2",
    "DIAS_RETENCION": "30",
})

from PIL import Image  # noqa: E402

from vigia import config as C  # noqa: E402
from vigia import main as M  # noqa: E402
from vigia import telegram as T  # noqa: E402
from vigia import vision as V  # noqa: E402
from vigia.maquina import P  # noqa: E402

# El fichero de aprendizajes real no debe ensuciarse con la prueba
APRENDIZAJES_REAL = C.FICHERO_APRENDIZAJES
C.FICHERO_APRENDIZAJES = TMP / "aprendizajes.md"
shutil.copy(APRENDIZAJES_REAL, C.FICHERO_APRENDIZAJES)

# ---------------------------------------------------------------- dobles de prueba
_b = io.BytesIO()
Image.new("RGB", (640, 480), "gray").save(_b, "JPEG")
JPG = _b.getvalue()

DET = {"status": "printing", "printFileName": "pieza_PETG_5h.gcode.3mf", "printLayer": 240,
       "targetPrintLayer": 769, "printProgress": 0.31, "rightTemp": 250, "rightTargetTemp": 250,
       "platTemp": 70, "platTargetTemp": 70, "printSpeedAdjust": 100, "coolingFanSpeed": 40,
       "zAxisCompensation": 0.0, "errorCode": "", "printDuration": 6000}
CONTROLES: list = []
ENVIADOS: list = []
RESPUESTAS: list = []


def _control(cmd, args):
    CONTROLES.append((cmd, args))
    if "speed" in args:
        DET["printSpeedAdjust"] = args["speed"]


P.detalle = lambda: dict(DET)
P.control = _control
import vigia.maquina as _maq  # noqa: E402
_maq._capturar_original = lambda: JPG
T.Bot._post = lambda self, metodo, **kw: ENVIADOS.append(
    (metodo, (kw.get("data") or {}).get("text") or (kw.get("data") or {}).get("caption") or "")
) or {"message_id": 1, "chat": {"id": 42}}


class _Mensajes:
    def create(self, **kw):
        r = RESPUESTAS.pop(0)
        uso = types.SimpleNamespace(input_tokens=1500, output_tokens=100,
                                    cache_creation_input_tokens=0, cache_read_input_tokens=0)
        return types.SimpleNamespace(
            content=[types.SimpleNamespace(type="text", text=r if isinstance(r, str) else json.dumps(r))],
            usage=uso)


V.claude.messages = _Mensajes()

OK = {"estado": "ok", "gravedad": "ok", "confianza": 0.85, "accion": {"tipo": "ninguna"}, "explicacion": "bien"}
LENTO = {"estado": "fallo", "gravedad": "vigilar", "tipo": "isla_fallida", "confianza": 0.85,
         "accion": {"tipo": "velocidad", "delta": -20, "motivo": "más tiempo de capa"}, "explicacion": "rizos"}
STOP = {"estado": "fallo", "gravedad": "detener", "tipo": "espagueti", "confianza": 0.9,
        "accion": {"tipo": "pausar"}, "explicacion": "nido de espagueti"}
SOSPECHA = {"estado": "sospecha", "motivo": "algo raro"}
FILTRO_OK = {"estado": "ok", "motivo": "normal"}
MSG = {"chat": {"id": 42}, "message_id": 1}


def comprobar(cond: bool, texto: str) -> None:
    print(("  ✅ " if cond else "  ❌ ") + texto)
    if not cond:
        raise SystemExit(1)


def main() -> None:
    v = M.Vigia()

    def ciclo(*resp):
        RESPUESTAS.extend(resp)
        v.ciclo_vigilancia()

    print("Simulación de impresión:")
    ciclo(SOSPECHA, LENTO)
    comprobar(any("Empiezo a vigilar" in e[1] for e in ENVIADOS), "detecta la impresión y avisa")
    comprobar(not v.motor.pendientes, "la primera propuesta solo se anota (persistencia)")

    ciclo(SOSPECHA, LENTO)
    comprobar(len(v.motor.pendientes) == 1, "a la segunda, propone la corrección con botones")

    v.boton(f"apl:{next(iter(v.motor.pendientes))}", MSG)
    comprobar(CONTROLES[-1] == ("printerCtl_cmd", {"speed": 80}), "✅ Aplicar baja la velocidad al 80 %")

    for _ in range(C.REVERTIR_TRAS_OK):
        ciclo(SOSPECHA, OK)
    comprobar(CONTROLES[-1] == ("printerCtl_cmd", {"speed": 100}), "revierte la velocidad cuando todo va bien")

    ciclo(SOSPECHA, STOP)
    comprobar(any("DETENER" in e[1] for e in ENVIADOS), "aviso 🛑 de detener")
    v.boton("pausa:si", MSG)
    comprobar(CONTROLES[-1][0] == "jobCtl_cmd", "⏸️ Pausar ahora pausa la impresión")

    cid = v.trabajo["casos"][-1]["id"]
    v.boton(f"fb-:{cid}", MSG)
    v.texto_libre("No era espagueti, era el soporte")
    comprobar("No era espagueti" in C.FICHERO_APRENDIZAJES.read_text(), "👎 + comentario → aprendizaje")

    comprobar(V.contador.resumen()["usd"] > 0, "cuenta el coste de Claude")

    print("Frecuencia adaptativa:")
    v.alerta_hasta = 0
    v.ultimo_diag_ts = __import__("time").time()
    ciclo(FILTRO_OK)
    comprobar(v.espera == 90, "fase tranquila → una foto cada 90 s")
    ciclo(SOSPECHA, OK)
    comprobar(v.espera == 30, "tras una sospecha → modo alerta, cada 30 s")
    v.alerta_hasta = 0
    DET["printLayer"] = 3
    ciclo(FILTRO_OK)
    comprobar(v.espera == 30, "primeras capas → cada 30 s")
    DET["printLayer"] = 240

    print("Diagnóstico que falla (caso real Pikachu, 8-oct):")
    CORTADO = '{\n  "estado": "fallo",\n  "grav'
    ESPAGUETI = {"estado": "sospecha", "motivo": "Nido de espagueti: material enredado en la cama."}
    ciclo(SOSPECHA, CORTADO, STOP)
    comprobar(v.ultimo_diag.get("tipo") == "espagueti", "respuesta cortada → reintenta y diagnostica")
    v.sospechas_seguidas = 0
    n = len(ENVIADOS)
    for _ in range(C.SOSPECHAS_ALARMA):
        ciclo(ESPAGUETI, CORTADO, "")
    comprobar(any("DETENER" in e[1] and "No he podido confirmarlo" in e[1] for e in ENVIADOS[n:]),
              f"{C.SOSPECHAS_ALARMA} sospechas sin diagnóstico → 🛑 de respaldo")
    DET.update(printLayer=0, rightTemp=140)
    RESPUESTAS.clear()
    v.ciclo_vigilancia()
    comprobar(not RESPUESTAS and v.espera == 30, "calentando en capa 0 → no gasta en Claude")
    DET.update(printLayer=240, rightTemp=250)

    print("Robustez:")
    # candado de cámara: dos capturas simultáneas nunca se solapan
    import threading
    import time as _t
    dentro, maximo = [0], [0]

    def lenta():
        dentro[0] += 1
        maximo[0] = max(maximo[0], dentro[0])
        _t.sleep(0.05)
        dentro[0] -= 1
        return JPG
    _maq._capturar_original = lenta
    hilos = [threading.Thread(target=P.capturar) for _ in range(4)]
    [h.start() for h in hilos]
    [h.join() for h in hilos]
    _maq._capturar_original = lambda: JPG
    comprobar(maximo[0] == 1, "candado de cámara: nunca dos capturas a la vez")

    # limpieza de fotos antiguas
    vieja = TMP / "20200101-000000.jpg"
    vieja.write_bytes(JPG)
    os.utime(vieja, (0, 0))
    v._limpiar_casos()
    comprobar(not vieja.exists(), "borra fotos con más de DIAS_RETENCION días")

    # aviso si Claude no responde
    import anthropic
    # Error de conexión de la API sin depender de la librería HTTP concreta del SDK
    err = anthropic.APIConnectionError.__new__(anthropic.APIConnectionError)
    Exception.__init__(err, "sin conexión")
    err.message = "sin conexión"
    for _ in range(3):
        v._error_ciclo(err)
    comprobar(any("Claude no responde" in e[1] for e in ENVIADOS), "avisa si Claude no responde 3 veces")
    RESPUESTAS.append(FILTRO_OK)
    v.ciclo_vigilancia()
    comprobar(any("vuelve a responder" in e[1] for e in ENVIADOS), "avisa cuando Claude vuelve")

    # tope de gasto diario
    V.gasto.datos[V.gasto._hoy()] = 2.5
    llamadas_antes = len(RESPUESTAS)
    RESPUESTAS.append(FILTRO_OK)
    v.ciclo_vigilancia()
    comprobar(len(RESPUESTAS) == llamadas_antes + 1, "con el presupuesto agotado no llama a Claude")
    comprobar(any("Presupuesto diario agotado" in e[1] for e in ENVIADOS), "y avisa del presupuesto agotado")
    RESPUESTAS.clear()
    V.gasto.datos[V.gasto._hoy()] = 0

    DET["status"] = "completed"
    RESPUESTAS.append("## Resumen\nTodo **bien**.")
    v.ciclo_vigilancia()
    comprobar(any(f.suffix == ".md" for f in (TMP / "informes").iterdir()), "informe final guardado")
    comprobar(any("Coste de vigilancia" in e[1] for e in ENVIADOS), "el informe incluye el coste")

    shutil.rmtree(TMP, ignore_errors=True)
    print("\nTODO OK ✅")


if __name__ == "__main__":
    main()
