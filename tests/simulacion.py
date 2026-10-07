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
    "INFORME_CADA_MIN": "0", "INTERVALO_S": "0", "CORRECCION_MODO": "proponer",
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
P.capturar = lambda: JPG
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

    DET["status"] = "completed"
    RESPUESTAS.append("## Resumen\nTodo **bien**.")
    v.ciclo_vigilancia()
    comprobar(any(f.suffix == ".md" for f in (TMP / "informes").iterdir()), "informe final guardado")
    comprobar(any("Coste de vigilancia" in e[1] for e in ENVIADOS), "el informe incluye el coste")

    shutil.rmtree(TMP, ignore_errors=True)
    print("\nTODO OK ✅")


if __name__ == "__main__":
    main()
