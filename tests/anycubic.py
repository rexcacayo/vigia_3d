"""Prueba del adaptador Anycubic sin impresora: apretón de manos cifrado y lectura del estado.

    python -m tests.anycubic
"""
import base64
import json
import os
import tempfile
import types

os.environ.update({"PRINTER_TIPO": "anycubic", "PRINTER_IP": "192.168.1.50",
                   "ANTHROPIC_API_KEY": "x", "DIR_CASOS": tempfile.mkdtemp(prefix="vigia_any_")})

from cryptography.hazmat.primitives import padding  # noqa: E402
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes  # noqa: E402

from vigia.impresoras import anycubic as A, validar  # noqa: E402


def comprobar(cond: bool, texto: str) -> None:
    print(("  ✅ " if cond else "  ❌ ") + texto)
    if not cond:
        raise SystemExit(1)


def main() -> None:
    print("Adaptador Anycubic:")
    comprobar(not validar(A), "cumple el contrato de adaptador")

    # --- apretón de manos: ciframos como lo haría la impresora y comprobamos que se descifra
    token = "0123456789abcdefFEDCBA9876543210"
    iv = "ivivivivivivivi1"
    cred = {"username": "user123", "password": "secreto", "deviceId": "d" * 32, "modeId": "20026"}
    rel = padding.PKCS7(128).padder()
    plano = rel.update(json.dumps(cred).encode()) + rel.finalize()
    cif = Cipher(algorithms.AES(token[16:32].encode()), modes.CBC(iv.encode())).encryptor()
    info = base64.b64encode(cif.update(plano) + cif.finalize()).decode()
    llamadas = []

    def get(url, timeout):
        llamadas.append(url)
        return types.SimpleNamespace(json=lambda: {"token": token, "ctrlInfoUrl": "http://x:18910/ctrl"})

    def post(url, params, timeout):
        llamadas.append(params)
        esperada = A._md5(A._md5(token[:16]) + params["ts"] + params["nonce"])
        ok = params["sign"] == esperada
        return types.SimpleNamespace(json=lambda: {"code": 200 if ok else 401,
                                                   "data": {"info": info, "token": iv}})

    A.requests.get, A.requests.post = get, post
    comprobar(A.credenciales() == cred, "firma md5 + descifrado AES-128-CBC de las credenciales")

    # --- estado a partir de un info/report
    rep = {"state": "busy", "fan_speed_pct": 60, "print_speed_mode": 2,
           "temp": {"curr_nozzle_temp": 229.5, "target_nozzle_temp": 230,
                    "curr_hotbed_temp": 70, "target_hotbed_temp": 70},
           "project": {"state": "printing", "progress": 42, "curr_layer": 120, "total_layers": 900,
                       "print_time": 95, "filename": "jarron_PETG.gcode", "pause": 0}}
    A._c.consultar = lambda *a, **k: rep
    e = A.estado()
    comprobar(e["imprimiendo"] and not e["pausada"] and e["material"] == "PETG", "estado: imprimiendo, PETG")
    comprobar(e["capa"] == {"actual": 120, "total": 900} and e["tiempo_impresion_s"] == 95 * 60,
              "capas y tiempo (minutos → segundos)")
    rep["project"]["state"] = "pause"
    comprobar(A.estado()["pausada"], "estado: pausada")
    rep["project"]["state"] = "finished"
    e = A.estado()
    comprobar(not e["imprimiendo"] and not e["pausada"], "estado: terminada")

    # --- aviso de filamento en un mensaje cualquiera
    rep["project"]["state"] = "printing"
    msg = types.SimpleNamespace(topic="anycubic/x/print/report",
                                payload=json.dumps({"type": "print", "action": "report",
                                                    "data": {"reason": "filament_runout"}}).encode())
    A._c._al_recibir(None, None, msg)
    comprobar("filamento" in (A.estado()["error"] or ""), "detecta «filament_runout» en los mensajes")

    # --- órdenes
    enviados = []
    A._c.enviar = lambda tipo, accion, datos=None, ruta="web": enviados.append((tipo, accion, datos))
    A.pausar()
    A.reanudar()
    comprobar(enviados == [("print", "pause", {"taskid": "-1"}), ("print", "resume", {"taskid": "-1"})],
              "pausa y reanuda con print/pause y print/resume")
    print("\nTODO OK ✅")


if __name__ == "__main__":
    main()
