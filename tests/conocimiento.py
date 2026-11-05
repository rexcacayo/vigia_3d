"""Skills desde OCI + capa local: sin duplicados, nada se pierde y la migración desde skill/.

    python -m tests.conocimiento
"""
import os
import tempfile
from pathlib import Path

TMP = Path(tempfile.mkdtemp(prefix="vigia_co_"))
os.environ.update({"PRINTER_TIPO": "flashforge", "PRINTER_IP": "1.2.3.4", "PRINTER_SN": "x",
                   "PRINTER_CHECK_CODE": "x", "ANTHROPIC_API_KEY": "x", "DIR_CASOS": str(TMP / "casos"),
                   "SKILLS_OCI": "false"})

from vigia import config as C, conocimiento as CO, filamentos as F  # noqa: E402


def comprobar(cond: bool, texto: str) -> None:
    print(("  ✅ " if cond else "  ❌ ") + texto)
    if not cond:
        raise SystemExit(1)


def main() -> None:
    print("Conocimiento (skills OCI + capa local):")
    # Skill «instalada» desde OCI
    inst = TMP / "instalada" / "vigia-3d"
    (inst / "filamentos").mkdir(parents=True)
    (inst / "aprendizajes.md").write_text("# Aprendizajes\n- A publicada\n")
    (inst / "filamentos" / "elegoo-petg-rapid.md").write_text(
        "# ELEGOO Rapid PETG\n\n## Historial de impresiones\n- 2026-10-07 · dora: ok\n")
    (inst / "filamentos" / "_plantilla.md").write_text("# {{NOMBRE}}\n\n## Historial de impresiones\n")
    # Copia antigua skill/ con cosas aprendidas en local por versiones anteriores
    viejo = TMP / "skill"
    (viejo / "filamentos").mkdir(parents=True)
    (viejo / "aprendizajes.md").write_text("- A publicada\n- B solo en local antiguo\n")
    (viejo / "filamentos" / "elegoo-petg-rapid.md").write_text(
        "## Historial de impresiones\n- 2026-10-07 · dora: ok\n- 2026-10-08 · pikachu: despegue\n")
    (viejo / "filamentos" / "sunlu-pla-matte.md").write_text("# Sunlu PLA Matte\n")
    C.DIR_SKILL_RESPALDO, C.DIR_SKILL = viejo, inst
    C.DIR_FILAMENTOS = inst / "filamentos"

    n = CO.migrar_respaldo()
    comprobar(n == 3, "rescata de skill/ lo que no está publicado (1 aprendizaje, 1 historial, 1 ficha)")
    comprobar(CO.migrar_respaldo() == 0, "la migración es idempotente")
    comprobar("B solo en local antiguo" in CO.aprendizajes() and CO.aprendizajes().count("A publicada") == 1,
              "aprendizajes = publicados + locales, sin duplicar")
    comprobar("pikachu: despegue" in F.ficha("elegoo-petg-rapid"), "la ficha junta skill + historial local")
    comprobar("sunlu-pla-matte" in F.lista() and F.es_nueva("sunlu-pla-matte"), "fichas nuevas en la capa local")

    F.anotar("elegoo-petg-rapid", "jarron (2h, completed)", ["245 °C sin hilos"])
    p = CO.pendiente_de_publicar("elegoo-petg-rapid")
    comprobar(len(p["filamento"]["historial"]) == 2 and p["aprendizajes"] == ["- B solo en local antiguo"],
              "el analista recibe exactamente lo pendiente de publicar")

    # Se publica una versión nueva de la skill que ya incluye esas líneas literalmente
    (inst / "aprendizajes.md").write_text("- A publicada\n- B solo en local antiguo\n")
    (inst / "filamentos" / "elegoo-petg-rapid.md").write_text(
        "## Historial de impresiones\n- 2026-10-07 · dora: ok\n" + "\n".join(p["filamento"]["historial"]) + "\n")
    p2 = CO.pendiente_de_publicar("elegoo-petg-rapid")
    comprobar(not p2["aprendizajes"] and not p2["filamento"]["historial"],
              "al publicarse, la capa local deja de duplicarlo")
    comprobar(F.ficha("elegoo-petg-rapid").count("245 °C sin hilos") == 1, "y la ficha no repite líneas")
    print("\nTODO OK ✅")


if __name__ == "__main__":
    main()
