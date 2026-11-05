"""Agentes de Claude Platform (repo vigia-agentes): el vigía les pasa el trabajo pesado.

- Analista de proceso: al terminar cada impresión recibe fotos, perfil, casos, informe y
  la descripción de la máquina; devuelve un análisis y abre un PR con lo aprendido.
- Agente de filamento: consolida las fichas de filamento (orden /fichas).

Los IDs salen del claude-lock.json del repo de agentes (o del .env si se fijan a mano).
Se ejecuta en un hilo aparte: nunca bloquea la vigilancia.
"""
from __future__ import annotations

import io
import json
import logging
import time
from pathlib import Path

import requests

from . import config as C
from .maquina import P

log = logging.getLogger("vigia.plataforma")

RUTA_ANALISTA = "agents/analista-proceso.md"
RUTA_FILAMENTO = "agents/agente-filamento.md"
RUTA_ENTORNO = "environments/vigia-cloud.yaml"
MAX_FOTOS = 14


def activo() -> bool:
    return C.ANALISTA


# ---------------------------------------------------------------- IDs
def _ids() -> dict:
    """{ruta → id} a partir del lockfile del repo de agentes."""
    ids: dict = {}
    try:
        r = requests.get(C.AGENTES_LOCK_URL, timeout=10)
        r.raise_for_status()
        for ruta, rec in (r.json().get("resources") or {}).items():
            if isinstance(rec, dict) and rec.get("id"):
                ids[ruta.lstrip("./")] = rec["id"]
    except Exception as ex:  # noqa: BLE001
        log.warning("No pude leer el claude-lock.json de los agentes: %s", ex)
    return ids


def _id(ruta: str, fijo: str, ids: dict) -> str:
    valor = fijo or ids.get(ruta)
    if not valor:
        raise RuntimeError(f"Sin ID para {ruta}: ¿se ha desplegado el repo de agentes?")
    return valor


# ---------------------------------------------------------------- material
def maquina() -> dict:
    return {"nombre": P.NOMBRE, "descripcion": P.DESCRIPCION,
            "capacidades": sorted(P.CAPACIDADES), "solo_con_permiso": sorted(P.SOLO_CON_PERMISO)}


def elegir_fotos(casos: list[dict]) -> list[tuple[str, Path]]:
    """Todos los avisos y, del resto, fotos repartidas a lo largo de la impresión."""
    con_foto = [c for c in casos if (C.DIR_CASOS / f"{c['id']}.jpg").exists()]
    avisos = [c for c in con_foto if c.get("clase") == "aviso"]
    resto = [c for c in con_foto if c.get("clase") != "aviso"]
    hueco = max(MAX_FOTOS - len(avisos), 0)
    if resto and hueco:
        paso = max(len(resto) / hueco, 1)
        resto = [resto[int(i * paso)] for i in range(min(hueco, len(resto)))]
    elegidos = sorted(avisos[:MAX_FOTOS] + resto[:hueco], key=lambda c: c["id"])
    fotos = []
    for c in elegidos:
        capa = c.get("capa") or 0
        nombre = f"c{int(capa):04d}_{c.get('clase')}_{c['id']}.jpg"
        fotos.append((nombre, C.DIR_CASOS / f"{c['id']}.jpg"))
    return fotos


# ---------------------------------------------------------------- sesiones
def _cliente():
    from .vision import claude
    return claude


def _subir(cli, nombre: str, datos: bytes, tipo: str, subidos: list) -> str:
    f = cli.beta.files.upload(file=(nombre, io.BytesIO(datos), tipo))
    subidos.append(f.id)
    return f.id


def _sesion(agente: str, titulo: str, mensaje: str, ficheros: list[tuple[str, bytes, str]],
            presupuesto_cent: int) -> tuple[str, str]:
    """Lanza una sesión, espera a que termine y devuelve (id de sesión, texto de analisis.md)."""
    cli = _cliente()
    ids = _ids()
    agente_id = _id(agente, C.AGENTE_ANALISTA_ID if agente == RUTA_ANALISTA else C.AGENTE_FILAMENTO_ID, ids)
    entorno_id = _id(RUTA_ENTORNO, C.ENTORNO_AGENTES_ID, ids)
    subidos: list[str] = []
    try:
        recursos = [{"type": "file", "file_id": _subir(cli, Path(ruta).name, datos, tipo, subidos),
                     "mount_path": ruta} for ruta, datos, tipo in ficheros]
        if C.GITHUB_TOKEN_AGENTES:
            recursos.append({"type": "github_repository", "url": C.REPO_AGENTES,
                             "mount_path": "/workspace/vigia-agentes",
                             "authorization_token": C.GITHUB_TOKEN_AGENTES})
        extra = {"vault_ids": [C.VAULT_AGENTES]} if C.VAULT_AGENTES else {}
        sesion = cli.beta.sessions.create(
            agent=agente_id, environment_id=entorno_id, title=titulo[:200], resources=recursos,
            budget={"type": "limit", "max_list_cost": {"amount": str(presupuesto_cent), "currency": "USD"}},
            initial_events=[{"type": "user.message", "content": [{"type": "text", "text": mensaje}]}],
            metadata={"proyecto": "vigia-3d"}, **extra)
        log.info("Sesión %s lanzada (%s)", sesion.id, agente)
        limite = time.time() + C.ANALISTA_TIMEOUT_MIN * 60
        time.sleep(15)
        while time.time() < limite:
            estado = cli.beta.sessions.retrieve(sesion.id).status
            if estado in ("idle", "terminated"):
                break
            time.sleep(20)
        else:
            raise TimeoutError(f"la sesión {sesion.id} no terminó en {C.ANALISTA_TIMEOUT_MIN} min")
        if estado == "terminated":
            raise RuntimeError(f"la sesión {sesion.id} terminó con error")
        return sesion.id, _descargar(cli, sesion.id, "analisis.md")
    finally:
        for fid in subidos:  # la sesión tiene su copia; no acumular ficheros
            try:
                cli.beta.files.delete(fid)
            except Exception:  # noqa: BLE001
                pass


def _descargar(cli, sesion_id: str, nombre: str) -> str:
    for _ in range(4):  # los ficheros de salida tardan unos segundos en aparecer
        for f in cli.beta.files.list(scope_id=sesion_id):
            if f.filename == nombre:
                return cli.beta.files.download(f.id).read().decode("utf-8", "replace")
        time.sleep(5)
    return ""


# ---------------------------------------------------------------- casos de uso
def analizar_impresion(registro: dict, informe: str) -> tuple[str, str]:
    ficheros = [
        ("/registro.json", json.dumps(registro, ensure_ascii=False, default=str).encode(), "application/json"),
        ("/maquina.json", json.dumps(maquina(), ensure_ascii=False).encode(), "application/json"),
        ("/informe.md", informe.encode(), "text/markdown"),
    ]
    for nombre, ruta in elegir_fotos(registro.get("casos") or []):
        ficheros.append((f"/fotos/{nombre}", ruta.read_bytes(), "image/jpeg"))
    pieza = (registro.get("fichero") or "impresion").split(".")[0]
    mensaje = (f"Analiza la impresión «{pieza}» ({registro.get('estado_final')}, "
               f"{registro.get('duracion')}). Los datos están en /mnt/session/uploads/. "
               "Sigue tus instrucciones: análisis en /mnt/session/outputs/ y PR solo si hay "
               "lecciones con evidencia.")
    return _sesion(RUTA_ANALISTA, f"Análisis · {pieza}", mensaje, ficheros, C.ANALISTA_PRESUPUESTO_CENT)


def consolidar_fichas() -> tuple[str, str]:
    mensaje = ("Consolida las fichas de filamento según tus instrucciones. Deja un resumen "
               "de lo hecho en /mnt/session/outputs/analisis.md.")
    return _sesion(RUTA_FILAMENTO, "Consolidación de fichas", mensaje, [], C.ANALISTA_PRESUPUESTO_CENT)
