"""Fichas de filamento: lo que se sabe de cada marca/tipo y lo que se aprende al imprimir.

Cada ficha es un Markdown en skill/filamentos/<id>.md. La activa se guarda en
DIR_CASOS/filamento_actual.txt (se elige con /filamento en Telegram o con FILAMENTO).
El informe post-mortem añade al final de la ficha lo aprendido en cada impresión.
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


def lista() -> list[str]:
    if not C.DIR_FILAMENTOS.exists():
        return []
    return sorted(f.stem for f in C.DIR_FILAMENTOS.glob("*.md") if not f.stem.startswith("_"))


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
    destino = C.DIR_FILAMENTOS / f"{fid}.md"
    if not destino.exists():
        plantilla = (C.DIR_FILAMENTOS / "_plantilla.md").read_text(encoding="utf-8")
        destino.write_text(plantilla.replace("{{NOMBRE}}", nombre.strip()), encoding="utf-8")
    fijar(fid)
    return fid


def ficha(fid: str | None = None) -> str:
    fid = fid or actual()
    if not fid:
        return ""
    f = C.DIR_FILAMENTOS / f"{fid}.md"
    if not f.exists():
        return ""
    texto = f.read_text(encoding="utf-8")
    # Solo las últimas entradas del historial: lo reciente es lo que más vale.
    if SECCION_HISTORIAL in texto:
        cabeza, hist = texto.split(SECCION_HISTORIAL, 1)
        lineas = [l for l in hist.splitlines() if l.startswith("- ")]
        texto = cabeza + SECCION_HISTORIAL + "\n" + "\n".join(lineas[-MAX_LINEAS_HISTORIAL:]) + "\n"
    return texto


def anotar(fid: str, cabecera: str, lecciones: list[str]) -> int:
    """Añade al historial de la ficha las lecciones de una impresión. Devuelve cuántas."""
    f = C.DIR_FILAMENTOS / f"{fid}.md"
    if not f.exists() or not lecciones:
        return 0
    texto = f.read_text(encoding="utf-8").rstrip("\n")
    if SECCION_HISTORIAL not in texto:
        texto += f"\n\n{SECCION_HISTORIAL}\n"
    fecha = f"{datetime.now():%Y-%m-%d}"
    nuevas = [f"- {fecha} · {cabecera}: {l.strip().lstrip('-•* ').strip()}" for l in lecciones if l.strip()]
    f.write_text(texto + "\n" + "\n".join(nuevas) + "\n", encoding="utf-8")
    return len(nuevas)


def extraer_lecciones(informe: str) -> list[str]:
    """Saca las viñetas de la sección «Para la ficha del filamento» del informe."""
    m = re.search(r"#+\s*\**\s*Para la ficha del filamento.*?\n(.*?)(?=\n#+\s|\Z)", informe, re.S | re.I)
    if not m:
        return []
    lecciones = [l.strip()[1:].strip() for l in m.group(1).splitlines()
                 if l.strip().startswith(("-", "*", "•"))]
    return [l for l in lecciones if l and "nada nuevo" not in l.lower()][:3]
