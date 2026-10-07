"""Comprueba un adaptador de impresora SIN mover la máquina.

    ./venv/bin/python -m vigia.probar            # adaptador de PRINTER_TIPO
    ./venv/bin/python -m vigia.probar --claude   # además, un diagnóstico real con Claude

Solo lee: contrato, estado() y una captura. Nunca llama a funciones que cambian algo.
"""
import json
import sys

from . import config as C
from .impresoras import CLAVES_ESTADO, POR_CAPACIDAD, cargar


def ok(msg: str) -> None:
    print(f"  ✅ {msg}")


def mal(msg: str) -> None:
    print(f"  ❌ {msg}")


def main() -> int:
    fallos = 0
    print(f"Adaptador: {C.PRINTER_TIPO}")
    try:
        P = cargar(C.PRINTER_TIPO)
    except Exception as e:  # noqa: BLE001
        mal(f"no carga: {e}")
        return 1
    ok(f"carga y cumple el contrato · {P.NOMBRE}")
    print(f"  Capacidades: {', '.join(sorted(P.CAPACIDADES)) or '(ninguna)'}")
    desconocidas = set(P.CAPACIDADES) - set(POR_CAPACIDAD)
    if desconocidas:
        mal(f"capacidades desconocidas: {desconocidas}")
        fallos += 1

    print("estado():")
    try:
        e = P.estado()
        faltan = [k for k in CLAVES_ESTADO if k not in e]
        if faltan:
            mal(f"faltan claves: {faltan}")
            fallos += 1
        else:
            ok("todas las claves presentes")
        for k in ("capa", "boquilla", "cama"):
            if not isinstance(e.get(k), dict):
                mal(f"'{k}' debe ser un dict")
                fallos += 1
        if not isinstance(e.get("imprimiendo"), bool):
            mal("'imprimiendo' debe ser bool")
            fallos += 1
        print("  " + json.dumps(e, ensure_ascii=False)[:400])
    except Exception as ex:  # noqa: BLE001
        mal(f"estado() falla: {ex}")
        return 1

    print("capturar():")
    try:
        jpg = P.capturar()
        if jpg[:2] == b"\xff\xd8" and jpg[-2:] == b"\xff\xd9":
            ok(f"JPEG de {len(jpg) // 1024} KB")
            open("prueba_camara.jpg", "wb").write(jpg)
            print("  guardado en prueba_camara.jpg")
        else:
            mal("no parece un JPEG completo")
            fallos += 1
    except Exception as ex:  # noqa: BLE001
        mal(f"capturar() falla: {ex}")
        return 1

    if "--claude" in sys.argv:
        from . import vision as V
        print("diagnóstico con Claude:")
        d = V.diagnosticar([jpg], e)
        print("  " + json.dumps(d, ensure_ascii=False, indent=2).replace("\n", "\n  "))
        print(f"  coste: ${V.contador.resumen()['usd']:.4f}")

    print("\nResultado:", "TODO OK ✅" if not fallos else f"{fallos} problema(s) ❌")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
