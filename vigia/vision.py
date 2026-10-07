"""Análisis visual con Claude: filtro rápido + diagnóstico profundo con la skill."""
import base64
import io
import json
import logging
import re
import time

import anthropic
from PIL import Image

from . import config as C
from .maquina import P

log = logging.getLogger("vigia.vision")

claude = anthropic.Anthropic(
    default_headers={"anthropic-workspace-id": C.ANTHROPIC_WORKSPACE_ID}
    if C.ANTHROPIC_WORKSPACE_ID else None
)

_AJUSTES = ("velocidad", "flujo", "temp_boquilla", "temp_cama", "z_offset", "ventilador", "pausar")
class Contador:
    """Suma tokens y coste (USD) de todas las llamadas a Claude."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.inicio = time.time()
        self.llamadas: dict[str, int] = {}
        self.usd = 0.0
        self.tokens = {"entrada": 0, "salida": 0, "cache_escritura": 0, "cache_lectura": 0}

    def sumar(self, modelo: str, uso) -> None:
        if uso is None:
            return
        ent = getattr(uso, "input_tokens", 0) or 0
        sal = getattr(uso, "output_tokens", 0) or 0
        cw = getattr(uso, "cache_creation_input_tokens", 0) or 0
        cr = getattr(uso, "cache_read_input_tokens", 0) or 0
        pi, po, pw, pr = C.precio(modelo)
        self.usd += (ent * pi + sal * po + cw * pw + cr * pr) / 1_000_000
        for k, n in zip(self.tokens, (ent, sal, cw, cr)):
            self.tokens[k] += n
        self.llamadas[modelo] = self.llamadas.get(modelo, 0) + 1

    def resumen(self, segundos_impresion: float | None = None) -> dict:
        horas = (segundos_impresion if segundos_impresion else time.time() - self.inicio) / 3600
        return {"usd": round(self.usd, 4), "horas": round(horas, 2),
                "usd_hora": round(self.usd / horas, 4) if horas > 0.01 else None,
                "llamadas": dict(self.llamadas), "tokens": dict(self.tokens)}


contador = Contador()


def _crear(**kw):
    resp = claude.messages.create(**kw)
    contador.sumar(kw["model"], getattr(resp, "usage", None))
    return resp


TIPOS_ACCION = ("ninguna",) + tuple(t for t in _AJUSTES if t in P.CAPACIDADES)

# ---------------------------------------------------------------- prompts
FILTRO = """Eres el primer filtro de un vigía de impresión 3D. Miras UNA foto de la \
cámara de la impresora (más una ampliación de la zona de la pieza).

Tu única tarea: decidir si merece una segunda mirada de un experto.
Responde "sospecha" SOLO si ves algo concreto: nido de espagueti, pieza despegada o \
movida, material colgando en el aire, rizos o pegotes claros SOBRE la pieza, capa \
desplazada, bordes claramente levantados, boquilla con un pegote grande.
Purgas en la cama, soportes, relleno visible, sombras, hilos finos y el cabezal \
tapando la pieza son NORMALES: responde "ok".

Responde SOLO con JSON: {"estado": "ok" | "sospecha", "motivo": "<qué ves, 1 frase>"}"""

FORMATO_DIAG = """
## Formato de respuesta
Responde SOLO con un JSON válido, sin texto adicional:
{
  "estado": "ok" | "sospecha" | "fallo",
  "gravedad": "ok" | "vigilar" | "detener",
  "tipo": "<espagueti|despegue_cama|warping|subextrusion|sobreextrusion|stringing|capa_desplazada|rizado_voladizo|isla_fallida|blob_boquilla|boquilla_obstruida|primera_capa_mala|otro|null>",
  "zona": "<parte de la pieza afectada o null>",
  "confianza": <0.0-1.0>,
  "parametro": "<parámetro más probable implicado o null>",
  "accion": {"tipo": "<__TIPOS__>",
             "delta": <número o null>, "motivo": "<por qué, 1 frase>"},
  "explicacion": "<1-2 frases en español sobre lo que ves>"
}"""


def _leer(nombre: str) -> str:
    f = C.DIR_SKILL / nombre
    return f.read_text(encoding="utf-8") if f.exists() else ""


def sistema_diagnostico() -> str:
    """Skill completa: se relee en cada llamada para que los aprendizajes nuevos cuenten."""
    formato = FORMATO_DIAG.replace("__TIPOS__", "|".join(TIPOS_ACCION))
    partes = [_leer("SKILL.md"), P.DESCRIPCION, _leer("materiales.md"), _leer("correcciones.md"),
              f"Acciones que admite ESTA impresora: {', '.join(TIPOS_ACCION)}.",
              _leer("aprendizajes.md"), formato]
    return "\n\n---\n\n".join(p for p in partes if p)


# ---------------------------------------------------------------- imágenes
def _bloque(jpeg: bytes) -> dict:
    return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                        "data": base64.b64encode(jpeg).decode()}}


def ampliar(jpeg: bytes) -> bytes:
    img = Image.open(io.BytesIO(jpeg))
    w, h = img.size
    x0, y0, x1, y1 = C.ZOOM_REGION
    rec = img.crop((int(x0 * w), int(y0 * h), int(x1 * w), int(y1 * h)))
    rec = rec.resize((rec.width * 2, rec.height * 2), Image.LANCZOS)
    out = io.BytesIO()
    rec.convert("RGB").save(out, "JPEG", quality=90)
    return out.getvalue()


def _json(texto: str) -> dict:
    m = re.search(r"\{.*\}", texto, re.S)
    if not m:
        raise ValueError(f"Respuesta sin JSON: {texto[:200]}")
    return json.loads(m.group(0))


def _resumen_estado(estado: dict) -> str:
    claves = ("fichero", "material", "capa", "progreso_pct", "boquilla", "cama",
              "ajuste_velocidad_pct", "ventilador_capa", "z_offset", "puerta", "error")
    return json.dumps({k: estado.get(k) for k in claves}, ensure_ascii=False)


# ---------------------------------------------------------------- llamadas
def filtrar(jpeg: bytes) -> dict:
    resp = _crear(
        model=C.MODELO_FILTRO, max_tokens=150, system=FILTRO,
        messages=[{"role": "user", "content": [_bloque(jpeg)] + ([_bloque(ampliar(jpeg))] if C.FILTRO_CON_ZOOM else [])}],
    )
    return _json("".join(b.text for b in resp.content if b.type == "text"))


def diagnosticar(imagenes: list[bytes], estado: dict) -> dict:
    contenido = []
    for n, img in enumerate(imagenes, 1):
        contenido.append({"type": "text", "text": f"Fotograma {n}/{len(imagenes)} (más reciente al final):"})
        contenido.append(_bloque(img))
    contenido.append({"type": "text", "text": "Ampliación de la zona de la pieza del fotograma más reciente:"})
    contenido.append(_bloque(ampliar(imagenes[-1])))
    contenido.append({"type": "text", "text": f"Estado de la máquina: {_resumen_estado(estado)}"})
    resp = _crear(
        model=C.MODELO_DIAG, max_tokens=700,
        system=[{"type": "text", "text": sistema_diagnostico(),
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": contenido}],
    )
    d = _json("".join(b.text for b in resp.content if b.type == "text"))
    acc = d.get("accion") or {}
    if acc.get("tipo") not in TIPOS_ACCION:
        d["accion"] = {"tipo": "ninguna", "delta": None, "motivo": "acción no reconocida"}
    return d


def preguntar(jpeg: bytes, estado: dict, pregunta: str) -> str:
    """Responde a una pregunta libre del usuario sobre la impresión en curso."""
    resp = _crear(
        model=C.MODELO_DIAG, max_tokens=500,
        system=[{"type": "text", "cache_control": {"type": "ephemeral"},
                 "text": sistema_diagnostico().split("## Formato de respuesta")[0]
                 + "\n\nAhora no respondas en JSON: contesta al usuario en español, "
                   "breve y directo, como en un chat (sin Markdown pesado)."}],
        messages=[{"role": "user", "content": [
            _bloque(jpeg), _bloque(ampliar(jpeg)),
            {"type": "text", "text": f"Estado: {_resumen_estado(estado)}\n\nPregunta: {pregunta}"},
        ]}],
    )
    return "".join(b.text for b in resp.content if b.type == "text").strip()


INFORME = """Eres un experto en impresión FDM y en OrcaSlicer. Te paso el registro de una \
impresión vigilada: diagnósticos de la cámara, correcciones \
aplicadas y comentarios del dueño. Escribe un informe breve en español (Markdown, máx. \
~350 palabras) con:
1. **Resumen**: cómo fue la impresión en 2-3 frases.
2. **Problemas observados**: solo los que tienen respaldo en el registro.
3. **Ajustes de perfil recomendados** en OrcaSlicer para este material: parámetro, valor \
actual si se conoce → valor propuesto, y por qué.
4. **Calibraciones** de Orca que conviene hacer (temperatura, flujo, retracción, \
velocidad volumétrica máx., pressure advance, voladizos), solo si vienen al caso.
No inventes datos que no estén en el registro. Si todo fue bien, dilo y sé breve."""


def informe_postmortem(registro: dict) -> str:
    resp = _crear(
        model=C.MODELO_DIAG, max_tokens=1200,
        system=[{"type": "text", "text": INFORME + "\n\n---\n\n" + P.DESCRIPCION
                  + "\n\n---\n\n" + _leer("materiales.md")}],
        messages=[{"role": "user", "content": json.dumps(registro, ensure_ascii=False)}],
    )
    return "".join(b.text for b in resp.content if b.type == "text").strip()
