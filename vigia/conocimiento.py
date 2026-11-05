"""Conocimiento del vigía = skills publicadas (OCI) + capa local de lo aprendido después.

- `sincronizar()`: instala/actualiza las skills desde el registro y apunta a ellas.
- `aprendizajes()`: los de la skill más los locales que aún no han llegado a ella.
- `pendiente_de_publicar()`: lo local que el analista debe proponer por PR.
- `migrar_respaldo()`: la primera vez, rescata lo aprendido en la copia antigua `skill/`.
"""
from __future__ import annotations

import logging

from . import config as C
from . import filamentos as F

log = logging.getLogger("vigia.conocimiento")


def _lineas(texto: str) -> list[str]:
    return [l for l in texto.splitlines() if l.startswith("- ")]


def _skill_aprendizajes() -> str:
    f = C.DIR_SKILL / "aprendizajes.md"
    return f.read_text(encoding="utf-8") if f.exists() else ""


def aprendizajes_locales() -> list[str]:
    f = C.FICHERO_APRENDIZAJES
    if not f.exists():
        return []
    base = _skill_aprendizajes()
    return [l for l in _lineas(f.read_text(encoding="utf-8")) if l not in base]


def aprendizajes() -> str:
    texto = _skill_aprendizajes().rstrip("\n")
    locales = aprendizajes_locales()
    if locales:
        texto += "\n\n## Aprendido en local (pendiente de publicar)\n" + "\n".join(locales)
    return texto


def pendiente_de_publicar(fid: str | None) -> dict:
    """Lo que el analista recibe para proponerlo por PR (líneas literales, para que al
    publicarse la capa local las reconozca y deje de duplicarlas)."""
    datos: dict = {"aprendizajes": aprendizajes_locales()}
    if fid:
        datos["filamento"] = {"id": fid, "nueva": F.es_nueva(fid), "historial": F.lineas_locales(fid)}
        if F.es_nueva(fid):
            datos["filamento"]["ficha"] = F.ficha(fid)
    return datos


def migrar_respaldo() -> int:
    """Si las skills vienen de OCI, pasa a la capa local lo que solo esté en `skill/`
    (aprendizajes por 👎 e historial de fichas de versiones anteriores del vigía)."""
    if C.DIR_SKILL == C.DIR_SKILL_RESPALDO:
        return 0
    movidas = 0
    viejo = C.DIR_SKILL_RESPALDO / "aprendizajes.md"
    if viejo.exists():
        ya = _skill_aprendizajes() + "\n".join(aprendizajes_locales())
        nuevas = [l for l in _lineas(viejo.read_text(encoding="utf-8")) if l not in ya]
        if nuevas:
            with C.FICHERO_APRENDIZAJES.open("a", encoding="utf-8") as f:
                f.write("\n".join(nuevas) + "\n")
            movidas += len(nuevas)
    viejas = C.DIR_SKILL_RESPALDO / "filamentos"
    if viejas.exists():
        C.DIR_FILAMENTOS_LOCAL.mkdir(parents=True, exist_ok=True)
        for ficha in viejas.glob("*.md"):
            if ficha.stem.startswith("_"):
                continue
            publicada = C.DIR_FILAMENTOS / ficha.name
            if not publicada.exists():
                destino = C.DIR_FILAMENTOS_LOCAL / ficha.name
                if not destino.exists():
                    destino.write_text(ficha.read_text(encoding="utf-8"), encoding="utf-8")
                    movidas += 1
                continue
            ya = publicada.read_text(encoding="utf-8") + "\n".join(F.lineas_locales(ficha.stem))
            nuevas = [l for l in _lineas(ficha.read_text(encoding="utf-8")) if l not in ya]
            if nuevas:
                with (C.DIR_FILAMENTOS_LOCAL / f"{ficha.stem}.historial").open("a", encoding="utf-8") as f:
                    f.write("\n".join(nuevas) + "\n")
                movidas += len(nuevas)
    if movidas:
        log.info("Capa local: %s línea(s)/ficha(s) rescatadas de skill/", movidas)
    return movidas


def sincronizar() -> None:
    if C.SKILLS_OCI:
        from . import skills_oci
        skills_oci.sincronizar()
    C.recargar_skills()
    migrar_respaldo()
    log.info("Skills en uso: %s", C.DIR_SKILL)
