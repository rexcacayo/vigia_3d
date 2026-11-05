"""Instala las skills del vigía desde un registro OCI (GHCR), según «Agent Skills as OCI Artifacts».

- `skills.json` (en el repo) declara qué skills usa el vigía y de dónde.
- `.skills/` (no se versiona) guarda las skills instaladas y `skills.lock.json` con la
  referencia y el **digest** exacto de cada una: se sabe siempre qué versión se usó.
- Sin red o sin registro, el vigía sigue con lo último instalado o con la copia de `skill/`.

    python -m vigia.skills_oci          # instala/actualiza y muestra el lock
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import shutil
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import requests

log = logging.getLogger("vigia.skills")

RAIZ = Path(__file__).resolve().parent.parent
DECLARACION = RAIZ / "skills.json"
DIR_INSTALADAS = RAIZ / ".skills"
LOCK = DIR_INSTALADAS / "skills.lock.json"

TIPO_ARTEFACTO = "application/vnd.agentskills.skill.v1"
TIPO_CONTENIDO = "application/vnd.agentskills.skill.content.v1.tar+gzip"
ACEPTA = ", ".join(["application/vnd.oci.image.manifest.v1+json",
                    "application/vnd.oci.image.index.v1+json"])


def _partes(ref: str) -> tuple[str, str, str]:
    """ghcr.io/dueño/repo/skill:etiqueta → (registro, repositorio, etiqueta)."""
    registro, resto = ref.split("/", 1)
    if ":" in resto.rsplit("/", 1)[-1]:
        repo, etiqueta = resto.rsplit(":", 1)
    else:
        repo, etiqueta = resto, "latest"
    return registro, repo, etiqueta


def _token(registro: str, repo: str) -> str | None:
    """Token anónimo de lectura (paquetes públicos de GHCR)."""
    r = requests.get(f"https://{registro}/token", params={"scope": f"repository:{repo}:pull"}, timeout=15)
    return r.json().get("token") if r.ok else None


def _get(url: str, token: str | None, accept: str | None = None) -> requests.Response:
    cab = {"Authorization": f"Bearer {token}"} if token else {}
    if accept:
        cab["Accept"] = accept
    r = requests.get(url, headers=cab, timeout=30)
    r.raise_for_status()
    return r


def resolver(ref: str) -> dict:
    """Devuelve {ref, digest (manifiesto), capa (digest del contenido), version}."""
    registro, repo, etiqueta = _partes(ref)
    token = _token(registro, repo)
    r = _get(f"https://{registro}/v2/{repo}/manifests/{etiqueta}", token, ACEPTA)
    manifiesto = r.json()
    if manifiesto.get("artifactType") != TIPO_ARTEFACTO:
        raise RuntimeError(f"{ref} no es una skill (artifactType {manifiesto.get('artifactType')})")
    capas = [c for c in manifiesto.get("layers", []) if c.get("mediaType") == TIPO_CONTENIDO]
    if len(capas) != 1:
        raise RuntimeError(f"{ref}: debe tener exactamente una capa de contenido")
    anot = manifiesto.get("annotations") or {}
    digest = r.headers.get("Docker-Content-Digest") or \
        "sha256:" + hashlib.sha256(r.content).hexdigest()
    return {"ref": ref, "digest": digest, "capa": capas[0]["digest"],
            "version": anot.get("org.opencontainers.image.version"),
            "nombre": anot.get("io.agentskills.skill.name")}


def instalar(nombre: str, info: dict) -> None:
    registro, repo, _ = _partes(info["ref"])
    token = _token(registro, repo)
    datos = _get(f"https://{registro}/v2/{repo}/blobs/{info['capa']}", token).content
    if "sha256:" + hashlib.sha256(datos).hexdigest() != info["capa"]:
        raise RuntimeError(f"{nombre}: el contenido no coincide con su digest; no se instala")
    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(fileobj=io.BytesIO(datos), mode="r:gz") as tar:
            for m in tar.getmembers():  # nada fuera de <nombre>/
                if m.name.startswith("/") or ".." in Path(m.name).parts or not m.name.startswith(nombre + "/"):
                    raise RuntimeError(f"{nombre}: ruta no permitida en el artefacto: {m.name}")
            try:
                tar.extractall(tmp, filter="data")
            except TypeError:  # Python sin «filter»: las rutas ya se han validado arriba
                tar.extractall(tmp)
        destino = DIR_INSTALADAS / nombre
        if destino.exists():
            shutil.rmtree(destino)
        shutil.move(str(Path(tmp) / nombre), destino)


def leer_lock() -> dict:
    try:
        return json.loads(LOCK.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"skills": {}}


def sincronizar() -> dict:
    """Instala lo declarado en skills.json si cambió su digest. Nunca lanza: registra y sigue."""
    try:
        declaradas = json.loads(DECLARACION.read_text(encoding="utf-8")).get("skills", {})
    except (OSError, ValueError):
        return leer_lock()
    DIR_INSTALADAS.mkdir(exist_ok=True)
    lock = leer_lock()
    for nombre, ref in declaradas.items():
        try:
            info = resolver(ref)
            actual = lock["skills"].get(nombre, {})
            if actual.get("digest") == info["digest"] and (DIR_INSTALADAS / nombre / "SKILL.md").exists():
                continue
            instalar(nombre, info)
            info["instalada"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            lock["skills"][nombre] = info
            log.info("Skill %s %s instalada (%s)", nombre, info.get("version"), info["digest"][:19])
        except Exception as ex:  # noqa: BLE001 — el vigía no puede depender del registro
            log.warning("Skill %s: no se pudo actualizar desde %s (%s); sigo con la instalada", nombre, ref, ex)
    LOCK.write_text(json.dumps(lock, ensure_ascii=False, indent=2), encoding="utf-8")
    return lock


def ruta(nombre: str, respaldo: Path) -> Path:
    """Carpeta de la skill instalada, o la copia de respaldo del repo si no hay ninguna."""
    instalada = DIR_INSTALADAS / nombre
    return instalada if (instalada / "SKILL.md").exists() else respaldo


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(json.dumps(sincronizar(), ensure_ascii=False, indent=2))
