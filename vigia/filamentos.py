"""Fichas de filamento: lo que se sabe de cada marca/tipo y lo que se aprende al imprimir.

Las fichas vienen de la skill vigia-3d (filamentos/<id>.md, instalada desde OCI). Lo que
el vigía aprende entre publicaciones va a la **capa local** (DIR_FILAMENTOS_LOCAL):
- <id>.md: fichas nuevas creadas con /filamento nuevo.
- <id>.historial: líneas de historial añadidas por los informes.
Al leer una ficha se juntan las dos; lo que ya esté en la skill no se repite. El analista
de la plataforma recibe la capa local y la propone por PR al repo vigia-agentes.
La ficha activa se guarda en DIR_CASOS/filamento_actual.txt.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from pathlib import Path

from . import config as C

SECCION_HISTORIAL = "## Historial de impresiones"
MAX_LINEAS_HISTORIAL = 40  # se conservan las más recientes para no inflar el prompt


def _slug(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def _fichero_actual() -> Path:
    return C.DIR_CASOS / "filamento_actual.txt"


def _de_skill(fid: str) -> Path:
    return C.DIR_FILAMENTOS / f"{fid}.md"


def _local(fid: str) -> Path:
    return C.DIR_FILAMENTOS_LOCAL / f"{fid}.md"


def _historial_local(fid: str) -> Path:
    return C.DIR_FILAMENTOS_LOCAL / f"{fid}.historial"


def lista() -> list[str]:
    nombres = set()
    for d in (C.DIR_FILAMENTOS, C.DIR_FILAMENTOS_LOCAL):
        if d.exists():
            nombres |= {f.stem for f in d.glob("*.md") if not f.stem.startswith("_")}
    return sorted(nombres)


def es_nueva(fid: str) -> bool:
    """La ficha solo existe en la capa local (aún no está en la skill publicada)."""
    return not _de_skill(fid).exists() and _local(fid).exists()


def lineas_locales(fid: str) -> list[str]:
    """Historial local que todavía no ha llegado a la skill publicada."""
    f = _historial_local(fid)
    if not f.exists():
        return []
    base = _de_skill(fid).read_text(encoding="utf-8") if _de_skill(fid).exists() else ""
    return [l for l in f.read_text(encoding="utf-8").splitlines() if l.startswith("- ") and l not in base]


def buscar(nombre: str) -> str | None:
    """Encuentra una ficha por nombre aproximado: «elegoo petg rapid», «rapid»…"""
    q = _slug(nombre)
    if not q:
        return None
    fichas = lista()
    if q in fichas:
        return q
    trozos = q.split("-")
    candidatas = [f for f in fichas if all(t in f for t in trozos)]
    return candidatas[0] if len(candidatas) == 1 else None


def actual() -> str | None:
    f = _fichero_actual()
    if f.exists():
        fid = f.read_text(encoding="utf-8").strip()
        if fid in lista():
            return fid
    return buscar(C.FILAMENTO) if C.FILAMENTO else None


def fijar(nombre: str) -> str | None:
    fid = buscar(nombre)
    if fid:
        C.DIR_CASOS.mkdir(parents=True, exist_ok=True)
        _fichero_actual().write_text(fid, encoding="utf-8")
    return fid


def crear(nombre: str) -> str:
    """Crea una ficha nueva desde la plantilla y la deja activa."""
    fid = _slug(nombre)
    if not (_de_skill(fid).exists() or _local(fid).exists()):
        plantilla = C.DIR_FILAMENTOS / "_plantilla.md"
        if not plantilla.exists():
            plantilla = C.DIR_SKILL_RESPALDO / "filamentos" / "_plantilla.md"
        C.DIR_FILAMENTOS_LOCAL.mkdir(parents=True, exist_ok=True)
        _local(fid).write_text(plantilla.read_text(encoding="utf-8").replace("{{NOMBRE}}", nombre.strip()),
                               encoding="utf-8")
    fijar(fid)
    return fid


def ficha(fid: str | None = None) -> str:
    fid = fid or actual()
    if not fid:
        return ""
    f = _de_skill(fid) if _de_skill(fid).exists() else _local(fid)
    if not f.exists():
        return ""
    texto = f.read_text(encoding="utf-8").rstrip("\n")
    locales = lineas_locales(fid)
    if locales:
        if SECCION_HISTORIAL not in texto:
            texto += f"\n\n{SECCION_HISTORIAL}\n"
        texto += "\n" + "\n".join(locales) + "\n"
    # Solo las últimas entradas del historial: lo reciente es lo que más vale.
    if SECCION_HISTORIAL in texto:
        cabeza, hist = texto.split(SECCION_HISTORIAL, 1)
        lineas = [l for l in hist.splitlines() if l.startswith("- ")]
        texto = cabeza + SECCION_HISTORIAL + "\n" + "\n".join(lineas[-MAX_LINEAS_HISTORIAL:]) + "\n"
    return texto


def anotar(fid: str, cabecera: str, lecciones: list[str]) -> int:
    """Añade al historial (capa local) las lecciones de una impresión. Devuelve cuántas."""
    if not (_de_skill(fid).exists() or _local(fid).exists()) or not lecciones:
        return 0
    fecha = f"{datetime.now():%Y-%m-%d}"
    nuevas = [f"- {fecha} · {cabecera}: {l.strip().lstrip('-•* ').strip()}" for l in lecciones if l.strip()]
    C.DIR_FILAMENTOS_LOCAL.mkdir(parents=True, exist_ok=True)
    with _historial_local(fid).open("a", encoding="utf-8") as f:
        f.write("\n".join(nuevas) + "\n")
    return len(nuevas)


def extraer_lecciones(informe: str) -> list[str]:
    """Saca las viñetas de la sección «Para la ficha del filamento» del informe."""
    m = re.search(r"#+\s*\**\s*Para la ficha del filamento.*?\n(.*?)(?=\n#+\s|\Z)", informe, re.S | re.I)
    if not m:
        return []
    lecciones = [l.strip()[1:].strip() for l in m.group(1).splitlines()
                 if l.strip().startswith(("-", "*", "•"))]
    return [l for l in lecciones if l and "nada nuevo" not in l.lower()][:3]
