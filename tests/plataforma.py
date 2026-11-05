"""Prueba de la integración con los agentes de Claude Platform, con la API simulada.

    python -m tests.plataforma
"""
import io
import json
import os
import tempfile
import types
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="vigia_pl_"))
os.environ.update({"PRINTER_TIPO": "flashforge", "PRINTER_IP": "1.2.3.4", "PRINTER_SN": "x",
                   "PRINTER_CHECK_CODE": "x", "ANTHROPIC_API_KEY": "x", "DIR_CASOS": str(TMP),
                   "ANALISTA": "true", "GITHUB_TOKEN_AGENTES": "token-de-prueba",
                   "VAULT_AGENTES": "vlt_prueba"})

from vigia import plataforma as PL  # noqa: E402


def comprobar(cond: bool, texto: str) -> None:
    print(("  ✅ " if cond else "  ❌ ") + texto)
    if not cond:
        raise SystemExit(1)


class _Api:
    def __init__(self):
        self.creada, self.subidos, self.borrados, self.estados = None, [], [], ["running", "idle"]
        self.beta = types.SimpleNamespace(
            files=types.SimpleNamespace(upload=self.upload, delete=self.borrados.append,
                                        list=self.listar, download=self.descargar),
            sessions=types.SimpleNamespace(create=self.crear, retrieve=self.recuperar))

    def upload(self, file):
        self.subidos.append(file[0])
        return types.SimpleNamespace(id=f"file_{len(self.subidos)}")

    def crear(self, **kw):
        self.creada = kw
        return types.SimpleNamespace(id="sesn_1")

    def recuperar(self, _id):
        return types.SimpleNamespace(status=self.estados.pop(0) if self.estados else "idle")

    def listar(self, scope_id):
        return [types.SimpleNamespace(id="out_1", filename="analisis.md")]

    def descargar(self, _id):
        return io.BytesIO("**Veredicto:** aceptable".encode())


def main() -> None:
    print("Agentes de Claude Platform:")
    api = _Api()
    PL._cliente = lambda: api
    PL.time.sleep = lambda s: None
    PL.requests.get = lambda url, timeout: types.SimpleNamespace(
        raise_for_status=lambda: None,
        json=lambda: {"resources": {"./agents/analista-proceso.md": {"id": "agent_A"},
                                    "./environments/vigia-cloud.yaml": {"id": "env_E"}}})
    casos = []
    for i, clase in enumerate(["parte", "diag", "aviso", "parte", "diag"]):
        cid = f"2026110{i}-1200"
        (TMP / f"{cid}.jpg").write_bytes(b"\xff\xd8x\xff\xd9")
        casos.append({"id": cid, "clase": clase, "capa": i * 50})
    registro = {"fichero": "tapacubos_ASA.gcode.3mf", "estado_final": "completed", "duracion": "7h29m",
                "casos": casos, "perfil": {"temperaturas": {"nozzle_temperature": "270"}}}
    sesion, texto = PL.analizar_impresion(registro, "## Resumen\nbien")

    kw = api.creada
    comprobar(kw["agent"] == "agent_A" and kw["environment_id"] == "env_E", "IDs leídos del claude-lock.json")
    rutas = [r.get("mount_path") for r in kw["resources"]]
    comprobar({"/registro.json", "/maquina.json", "/informe.md"} <= set(rutas), "sube registro, máquina e informe")
    comprobar(sum(1 for r in rutas if r and r.startswith("/fotos/c0100_aviso")) == 1,
              "incluye las fotos con su capa en el nombre")
    repo = [r for r in kw["resources"] if r["type"] == "github_repository"]
    comprobar(repo and repo[0]["url"].endswith("vigia-agentes"), "monta el repo de agentes para el PR")
    comprobar(kw["vault_ids"] == ["vlt_prueba"] and kw["budget"]["max_list_cost"]["amount"] == "150",
              "usa el vault y el tope de gasto por sesión")
    maq = PL.maquina()
    comprobar("pausar" in maq["capacidades"], "la máquina viaja con sus capacidades (abierto a otras impresoras)")
    comprobar(sesion == "sesn_1" and "aceptable" in texto, "devuelve el analisis.md del agente")
    comprobar(len(api.borrados) == len(api.subidos), "borra los ficheros subidos al terminar")
    print("\nTODO OK ✅")


if __name__ == "__main__":
    main()
