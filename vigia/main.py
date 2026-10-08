"""Vigía de impresión: bucle principal + órdenes por Telegram."""
import json
import logging
import threading
import time
from collections import deque
from datetime import datetime

import anthropic

from . import config as C
from .maquina import P
from . import vision as V
from .correcciones import Motor
from .telegram import Bot, esc

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                    datefmt="%H:%M:%S")
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("vigia")

AYUDA = (
    "🤖 <b>Vigía de impresión</b>\n"
    "/estado – cómo va la impresión\n"
    "/foto – foto ahora\n"
    "/parte – parte con diagnóstico ahora\n"
    "/pausa – pausar (pide confirmación)\n"
    "/reanudar – reanudar\n"
    "/modo off|proponer|auto – correcciones\n"
    "/informe – informe con recomendaciones de perfil\n"
    "/coste – lo que lleva gastado en Claude esta impresión\n"
    "También puedes escribirme cualquier pregunta sobre la impresión."
)


def _hm(s: float) -> str:
    s = int(max(s or 0, 0))
    return f"{s // 3600}h{(s % 3600) // 60:02d}m"


def md_a_telegram(md: str) -> str:
    """Convierte el Markdown sencillo del informe al HTML que entiende Telegram."""
    import re
    t = esc(md)
    t = re.sub(r"^#{1,6}\s*(.+)$", r"<b>\1</b>", t, flags=re.M)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<!\w)\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"<i>\1</i>", t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"^\s*[-*]\s+", "• ", t, flags=re.M)
    return t


def _icono(diag: dict) -> str:
    return {"ok": "🟢", "vigilar": "🟡", "detener": "🛑"}.get(diag.get("gravedad"), "⚪")


class Vigia:
    def __init__(self) -> None:
        self.bot = Bot()
        self.motor = Motor()
        self.lock = threading.RLock()
        self.historial: deque[bytes] = deque(maxlen=3)
        self.estado: dict = {}
        self.ultimo_jpeg: bytes | None = None
        self.ultimo_diag: dict = {}
        self.ultimo_aviso: dict[str, float] = {}
        self.ultimo_parte = 0.0
        self.ciclo = 0
        self.ultimo_diag_ts = 0.0
        self.alerta_hasta = 0.0
        self.espera = C.INTERVALO
        self.fallos_camara = 0
        self.aviso_camara = False
        self.esperando_comentario: str | None = None
        self.fallos_claude = 0
        self.aviso_claude = False
        self.ultimo_error = ("", 0.0)
        self.trabajo: dict | None = None
        self.bot.on_comando = self.comando
        self.bot.on_boton = self.boton
        self.bot.on_texto = self.texto_libre

    # ================================================================ registro
    def _nuevo_trabajo(self, e: dict) -> None:
        self.trabajo = {"fichero": e.get("fichero"), "material": e.get("material"),
                        "inicio": datetime.now().isoformat(timespec="seconds"),
                        "capas_total": (e.get("capa") or {}).get("total"),
                        "casos": [], "correcciones": [], "feedback": []}
        self.motor.reset()
        V.contador.reset()
        self._limpiar_casos()
        self.historial.clear()
        self.ciclo = 0
        self.ultimo_diag_ts = 0.0
        self.alerta_hasta = 0.0
        self.ultimo_parte = 0.0
        self.fallos_camara = 0
        self.aviso_camara = False

    def _guardar_caso(self, jpeg: bytes, e: dict, diag: dict, clase: str) -> str:
        cid = datetime.now().strftime("%Y%m%d-%H%M%S")
        (C.DIR_CASOS / f"{cid}.jpg").write_bytes(jpeg)
        reg = {"id": cid, "clase": clase, "estado": e, "diagnostico": diag}
        with (C.DIR_CASOS / "casos.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(reg, ensure_ascii=False) + "\n")
        if self.trabajo is not None:
            self.trabajo["casos"].append({
                "id": cid, "clase": clase, "capa": (e.get("capa") or {}).get("actual"),
                "estado": diag.get("estado"), "gravedad": diag.get("gravedad"),
                "tipo": diag.get("tipo"), "confianza": diag.get("confianza"),
                "explicacion": diag.get("explicacion")})
        return cid

    def _caso(self, cid: str) -> dict | None:
        f = C.DIR_CASOS / "casos.jsonl"
        if not f.exists():
            return None
        for linea in reversed(f.read_text(encoding="utf-8").splitlines()):
            try:
                c = json.loads(linea)
            except json.JSONDecodeError:
                continue
            if c.get("id") == cid:
                return c
        return None

    # ================================================================ textos
    def _texto_estado(self, e: dict) -> str:
        capa = e.get("capa") or {}
        pct = e.get("progreso_pct") or 0
        dur = e.get("tiempo_impresion_s") or 0
        resta = (dur / (pct / 100) - dur) if pct > 0.5 else None
        return (f"<b>{esc(e.get('fichero'))}</b> ({esc(e.get('material') or '¿material?')})\n"
                f"Capa {capa.get('actual')}/{capa.get('total')} · {pct} %\n"
                f"Llevo {_hm(dur)}" + (f" · quedan ~{_hm(resta)}" if resta else "") + "\n"
                f"Boquilla {(e.get('boquilla') or {}).get('actual')} °C · "
                f"cama {(e.get('cama') or {}).get('actual')} °C · "
                f"velocidad {e.get('ajuste_velocidad_pct')} %")

    def _texto_diag(self, d: dict) -> str:
        acc = d.get("accion") or {}
        t = (f"<b>Claude:</b> {esc(d.get('estado'))} / {esc(d.get('gravedad'))}"
             f" ({int(100 * (d.get('confianza') or 0))} %)")
        if d.get("tipo"):
            t += f" · {esc(d.get('tipo'))}"
        if d.get("zona"):
            t += f"\n<b>Zona:</b> {esc(d.get('zona'))}"
        t += f"\n{esc(d.get('explicacion', ''))}"
        if acc.get("tipo") not in (None, "ninguna"):
            t += f"\n<b>Propone:</b> {esc(acc.get('tipo'))} {esc(acc.get('delta') or '')} — {esc(acc.get('motivo') or '')}"
        return t

    def _texto_coste(self) -> str:
        c = V.contador.resumen()
        llam = ", ".join(f"{m.split('-')[1]} ×{n}" for m, n in c["llamadas"].items()) or "ninguna"
        por_hora = f" · ~${c['usd_hora']:.2f}/h" if c["usd_hora"] else ""
        tope = f" de ${C.PRESUPUESTO_DIA:.2f}" if C.PRESUPUESTO_DIA > 0 else ""
        return (f"💶 <b>Coste de vigilancia</b>: ${c['usd']:.3f} en {c['horas']:.1f} h{por_hora}\n"
                f"Llamadas: {esc(llam)}\n"
                f"Hoy: ${V.gasto.hoy():.2f}{tope}")

    @staticmethod
    def _botones_feedback(cid: str):
        return [[("👍 Bien visto", f"fb+:{cid}"), ("👎 Se equivoca", f"fb-:{cid}")]]

    # ================================================================ bucle
    def ciclo_vigilancia(self) -> None:
        e = P.estado()
        with self.lock:
            self.estado = e

        if e["pausada"] or not e["imprimiendo"]:
            if not e["pausada"] and self.trabajo is not None:
                self._fin_trabajo(e)
            self.espera = C.INTERVALO
            return

        if self.trabajo is None or self.trabajo["fichero"] != e.get("fichero"):
            self._nuevo_trabajo(e)
            self.bot.texto(f"👀 Empiezo a vigilar\n{self._texto_estado(e)}\n\n/ayuda para ver órdenes")
            if "luz" in P.CAPACIDADES:
                try:
                    P.encender_luz()
                except Exception as ex:  # noqa: BLE001
                    log.warning("Luz: %s", ex)

        if e.get("error"):
            self._avisar_una_vez("error:" + str(e["error"]),
                                 lambda: self.bot.texto(f"⚠️ La impresora reporta el error <b>{esc(e['error'])}</b>"))

        try:
            jpeg = P.capturar()
            self.fallos_camara, self.aviso_camara = 0, False
        except Exception as ex:  # noqa: BLE001
            self.fallos_camara += 1
            log.warning("Cámara no disponible (%s): %s", self.fallos_camara, ex)
            if self.fallos_camara >= C.FALLOS_CAMARA_AVISO and not self.aviso_camara:
                self.bot.texto("📷 No consigo ver la cámara. ¿Está abierta la pestaña "
                               "<b>Dispositivo</b> de Orca? Solo admite un espectador.")
                self.aviso_camara = True
            return

        with self.lock:
            self.historial.append(jpeg)
            self.ultimo_jpeg = jpeg
        self.ciclo += 1

        if V.gasto.agotado():
            self._aviso_presupuesto_agotado()
            return
        try:
            filtro = V.filtrar(jpeg)
        except V.PresupuestoAgotado:
            self._aviso_presupuesto_agotado()
            return
        self._claude_ok()
        log.info("Capa %s/%s · filtro: %s — %s", e["capa"]["actual"], e["capa"]["total"],
                 filtro.get("estado"), filtro.get("motivo"))

        toca_parte = C.INFORME_CADA_MIN > 0 and time.time() - self.ultimo_parte >= C.INFORME_CADA_MIN * 60
        if filtro.get("estado") != "ok":
            self._modo_alerta("el filtro sospecha")
        toca_diag = time.time() - self.ultimo_diag_ts >= C.DIAG_CADA_MIN * 60
        profundo = filtro.get("estado") != "ok" or toca_diag or toca_parte
        self._calcular_espera(e)
        if not profundo:
            return
        self.ultimo_diag_ts = time.time()

        try:
            with self.lock:
                diag = V.diagnosticar(list(self.historial), e)
        except V.PresupuestoAgotado:
            self._aviso_presupuesto_agotado()
            return
        self.ultimo_diag = diag
        if V.gasto.fraccion() >= 0.8:
            self._avisar_una_vez("presupuesto80:" + time.strftime("%Y-%m-%d"), lambda: self.bot.texto(
                f"💶 Llevas ${V.gasto.hoy():.2f} de ${C.PRESUPUESTO_DIA:.2f} de presupuesto diario "
                f"(PRESUPUESTO_DIA_USD). Al llegar al tope dejaré de consultar a Claude hasta mañana."),
                espera=86400)
        log.info("Diagnóstico: %s", json.dumps(diag, ensure_ascii=False))

        hay_problema = diag.get("estado") != "ok" and diag.get("confianza", 0) >= C.CONFIANZA_MIN
        if diag.get("estado") != "ok" or diag.get("gravedad") != "ok":
            self._modo_alerta(f"diagnóstico {diag.get('estado')}/{diag.get('gravedad')}")
        self._calcular_espera(e)
        cid = self._guardar_caso(jpeg, e, diag, "aviso" if hay_problema else ("parte" if toca_parte else "diag"))

        if hay_problema:
            self._avisar_problema(jpeg, e, diag, cid)
        elif toca_parte:
            self.bot.foto(jpeg, f"📋 <b>Parte</b> {_icono(diag)}\n{self._texto_estado(e)}\n\n{self._texto_diag(diag)}",
                          self._botones_feedback(cid))
        if toca_parte:
            self.ultimo_parte = time.time()

        self._correcciones(jpeg, e, diag)

    def _aviso_presupuesto_agotado(self) -> None:
        self._avisar_una_vez("presupuesto100:" + time.strftime("%Y-%m-%d"), lambda: self.bot.texto(
            f"💶 <b>Presupuesto diario agotado</b> (${V.gasto.hoy():.2f} de ${C.PRESUPUESTO_DIA:.2f}). "
            "Hasta mañana no consulto a Claude: sigo vigilando solo el estado de la máquina "
            "(errores y fin de impresión). Puedes subir PRESUPUESTO_DIA_USD en el .env y reiniciar."),
            espera=86400)

    def _claude_ok(self) -> None:
        if self.aviso_claude:
            self.bot.texto("✅ Claude vuelve a responder. Sigo vigilando con normalidad.")
        self.fallos_claude, self.aviso_claude = 0, False

    def _limpiar_casos(self) -> None:
        """Borra fotos de casos con más de DIAS_RETENCION días (casos.jsonl se conserva)."""
        if C.DIAS_RETENCION <= 0:
            return
        limite = time.time() - C.DIAS_RETENCION * 86400
        borradas = 0
        for f in C.DIR_CASOS.glob("*.jpg"):
            try:
                if f.stat().st_mtime < limite:
                    f.unlink()
                    borradas += 1
            except OSError:
                pass
        if borradas:
            log.info("Limpieza: %s fotos de más de %s días borradas", borradas, C.DIAS_RETENCION)

    def _modo_alerta(self, motivo: str) -> None:
        """Sube la frecuencia durante ALERTA_MIN minutos para confirmar o descartar."""
        if time.time() >= self.alerta_hasta:
            log.info("⚠️ Modo alerta (%s): una foto cada %ss durante %s min",
                     motivo, C.INTERVALO_ALERTA, C.ALERTA_MIN)
        self.alerta_hasta = time.time() + C.ALERTA_MIN * 60

    def _calcular_espera(self, e: dict) -> None:
        capa = (e.get("capa") or {}).get("actual") or 0
        riesgo = capa <= C.CAPAS_RIESGO or time.time() < self.alerta_hasta
        self.espera = C.INTERVALO_ALERTA if riesgo else C.INTERVALO

    def _avisar_una_vez(self, clave: str, enviar, espera: int | None = None) -> None:
        if time.time() - self.ultimo_aviso.get(clave, 0) > (espera or C.COOLDOWN):
            enviar()
            self.ultimo_aviso[clave] = time.time()

    def _avisar_problema(self, jpeg: bytes, e: dict, d: dict, cid: str) -> None:
        grav = d.get("gravedad")
        clave = f"{d.get('estado')}:{grav}:{d.get('tipo')}"
        if grav == "detener":
            cab = "🛑 <b>HAY QUE DETENER LA IMPRESIÓN</b>"
            botones = ([[("⏸️ Pausar ahora", "pausa:si")]] if "pausar" in P.CAPACIDADES else []) \
                + self._botones_feedback(cid)
            if C.AUTO_PAUSA and "pausar" in P.CAPACIDADES:
                try:
                    P.pausar()
                    cab += "\n⏸️ <b>La he pausado automáticamente.</b> /reanudar para seguir."
                    botones = self._botones_feedback(cid)
                except Exception as ex:  # noqa: BLE001
                    cab += f"\n⚠️ No pude pausarla: {esc(ex)}"
            espera = C.COOLDOWN // 3
        else:
            cab = f"{_icono(d)} <b>Aviso</b>"
            botones, espera = self._botones_feedback(cid), C.COOLDOWN
        self._avisar_una_vez(clave, lambda: self.bot.foto(
            jpeg, f"{cab}\n{self._texto_diag(d)}\n\n{self._texto_estado(e)}", botones), espera)

    def _correcciones(self, jpeg: bytes, e: dict, d: dict) -> None:
        with self.lock:
            prop = self.motor.evaluar(d, e)
            if prop and self.motor.puede_auto(prop):
                try:
                    txt = self.motor.aplicar(prop)
                    self.trabajo["correcciones"].append({"cambio": txt, "motivo": prop.motivo, "modo": "auto"})
                    self.bot.foto(jpeg, f"🔧 <b>He corregido sobre la marcha</b>\n{esc(txt)}\n<i>{esc(prop.motivo)}</i>")
                except Exception as ex:  # noqa: BLE001
                    self.bot.texto(f"⚠️ No pude aplicar {esc(prop.texto())}: {esc(ex)}")
            elif prop:
                self.bot.foto(jpeg, f"🔧 <b>Propongo una corrección</b>\n{esc(prop.texto())}\n<i>{esc(prop.motivo)}</i>",
                              [[("✅ Aplicar", f"apl:{prop.id}"), ("❌ Ignorar", f"ign:{prop.id}")]])
            for m in self.motor.tras_diagnostico(d):
                self.trabajo["correcciones"].append({"cambio": m, "modo": "revertir"})
                self.bot.texto(m)

    # ================================================================ fin
    def _fin_trabajo(self, e: dict) -> None:
        t, self.trabajo = self.trabajo, None
        t["fin"] = datetime.now().isoformat(timespec="seconds")
        t["estado_final"] = e.get("maquina")
        t["duracion"] = _hm(e.get("tiempo_impresion_s") or 0)
        t["coste_vigilancia"] = V.contador.resumen()
        self.bot.texto(f"🏁 Impresión terminada ({esc(e.get('maquina'))}): <b>{esc(t['fichero'])}</b>\n"
                       f"Preparando el informe…")
        self._informe(t)

    def _informe(self, t: dict) -> None:
        try:
            texto = V.informe_postmortem(t)
        except Exception as ex:  # noqa: BLE001
            self.bot.texto(f"⚠️ No pude generar el informe: {esc(ex)}")
            return
        carpeta = C.DIR_CASOS / "informes"
        carpeta.mkdir(exist_ok=True)
        nombre = f"{datetime.now():%Y%m%d-%H%M}_{(t.get('fichero') or 'impresion').split('.')[0]}.md"
        (carpeta / nombre).write_text(f"# Informe: {t.get('fichero')}\n\n{texto}\n\n---\n"
                                      f"```json\n{json.dumps(t, ensure_ascii=False, indent=2)}\n```\n",
                                      encoding="utf-8")
        self.bot.texto(f"📝 <b>Informe</b>\n\n{md_a_telegram(texto)}\n\n{self._texto_coste()}")

    # ================================================================ Telegram
    def comando(self, cmd: str, arg: str) -> None:
        try:
            if cmd in ("start", "ayuda", "help"):
                self.bot.texto(AYUDA)
            elif cmd == "estado":
                self.bot.texto(self._texto_estado(P.estado()))
            elif cmd == "foto":
                self.bot.foto(P.capturar(), self._texto_estado(P.estado()))
            elif cmd == "parte":
                e, j = P.estado(), P.capturar()
                with self.lock:
                    self.historial.append(j)
                    d = V.diagnosticar(list(self.historial), e)
                cid = self._guardar_caso(j, e, d, "parte")
                self.bot.foto(j, f"📋 <b>Parte</b> {_icono(d)}\n{self._texto_estado(e)}\n\n{self._texto_diag(d)}",
                              self._botones_feedback(cid))
            elif cmd in ("pausa", "pausar"):
                self.bot.texto("¿Pauso la impresión?", [[("⏸️ Sí, pausar", "pausa:si"), ("Cancelar", "pausa:no")]])
            elif cmd in ("reanudar", "continuar"):
                P.reanudar()
                self.bot.texto("▶️ Reanudada.")
            elif cmd == "modo":
                if arg in ("off", "proponer", "auto"):
                    C.CORRECCION_MODO = arg
                    self.bot.texto(f"Modo de correcciones: <b>{arg}</b>")
                else:
                    self.bot.texto(f"Modo actual: <b>{C.CORRECCION_MODO}</b>. Usa /modo off|proponer|auto")
            elif cmd == "coste":
                self.bot.texto(self._texto_coste())
            elif cmd == "informe":
                if self.trabajo:
                    self.bot.texto("Generando informe parcial…")
                    self._informe(dict(self.trabajo))
                else:
                    self.bot.texto("No hay ninguna impresión vigilada ahora mismo.")
            else:
                self.bot.texto("No conozco esa orden. /ayuda")
        except V.PresupuestoAgotado:
            self.bot.texto("💶 Presupuesto diario agotado: hoy no puedo consultar a Claude.")
        except Exception as ex:  # noqa: BLE001
            log.exception("Comando %s", cmd)
            self.bot.texto(f"⚠️ Error con /{esc(cmd)}: {esc(ex)}")

    def boton(self, data: str, mensaje: dict) -> None:
        clave, _, valor = data.partition(":")
        try:
            if clave == "pausa":
                if valor == "si":
                    P.pausar()
                    self.bot.quitar_botones(mensaje, "⏸️ Impresión pausada. /reanudar para seguir.")
                else:
                    self.bot.quitar_botones(mensaje, "Vale, no la pauso.")
            elif clave in ("apl", "ign"):
                with self.lock:
                    prop = self.motor.pendientes.pop(valor, None)
                    if not prop:
                        self.bot.quitar_botones(mensaje, "Esa propuesta ya no está vigente.")
                    elif clave == "ign":
                        self.bot.quitar_botones(mensaje, f"❌ Ignorada: {esc(prop.texto())}")
                        if self.trabajo:
                            self.trabajo["correcciones"].append({"cambio": prop.texto(), "modo": "rechazada"})
                    elif time.time() - prop.ts > 600 or not self.estado.get("imprimiendo"):
                        self.bot.quitar_botones(mensaje, "Propuesta caducada (más de 10 min o ya no imprime).")
                    else:
                        self.motor.pendientes[prop.id] = prop
                        txt = self.motor.aplicar(prop)
                        if self.trabajo:
                            self.trabajo["correcciones"].append({"cambio": txt, "motivo": prop.motivo, "modo": "aprobada"})
                        self.bot.quitar_botones(mensaje, f"✅ Aplicado: {esc(txt)}")
            elif clave in ("fb+", "fb-"):
                if self.trabajo:
                    self.trabajo["feedback"].append({"caso": valor, "valoracion": clave})
                if clave == "fb+":
                    self.bot.quitar_botones(mensaje, "👍 Anotado, gracias.")
                else:
                    self.esperando_comentario = valor
                    self.bot.quitar_botones(mensaje, "👎 Anotado. Escríbeme en una frase <b>qué ha fallado</b> "
                                                     "y lo añado a los aprendizajes.")
        except Exception as ex:  # noqa: BLE001
            log.exception("Botón %s", data)
            self.bot.texto(f"⚠️ Error: {esc(ex)}")

    def texto_libre(self, texto: str) -> None:
        if self.esperando_comentario:
            cid, self.esperando_comentario = self.esperando_comentario, None
            self._aprender(cid, texto)
            return
        try:
            jpeg, e = P.capturar(), P.estado()
            self.bot.foto(jpeg, esc(V.preguntar(jpeg, e, texto)))
        except V.PresupuestoAgotado:
            self.bot.texto("💶 Presupuesto diario agotado: hoy no puedo consultar a Claude.")
        except Exception as ex:  # noqa: BLE001
            self.bot.texto(f"⚠️ No pude mirar la impresión: {esc(ex)}")

    def _aprender(self, cid: str, comentario: str) -> None:
        caso = self._caso(cid) or {}
        d, e = caso.get("diagnostico") or {}, caso.get("estado") or {}
        linea = (f"- {datetime.now():%Y-%m-%d} · {e.get('material') or '?'} · capa "
                 f"{(e.get('capa') or {}).get('actual')} · {e.get('fichero') or ''}: "
                 f"el vigía dijo {d.get('estado')}/{d.get('gravedad')}/{d.get('tipo')} "
                 f"(«{(d.get('explicacion') or '')[:120]}»). Usuario: «{comentario}»\n")
        with C.FICHERO_APRENDIZAJES.open("a", encoding="utf-8") as f:
            f.write(linea)
        if self.trabajo:
            self.trabajo["feedback"].append({"caso": cid, "comentario": comentario})
        self.bot.texto("📚 Aprendido. Lo tendré en cuenta en los próximos diagnósticos.")

    # ================================================================ arranque
    def run(self) -> None:
        log.info("Vigía arrancado — %s · cada %ss (riesgo: %ss) · correcciones: %s",
                 P.NOMBRE, C.INTERVALO, C.INTERVALO_ALERTA, C.CORRECCION_MODO)
        self._limpiar_casos()
        self.bot.escuchar()
        self.bot.texto("🤖 Vigía en marcha. /ayuda para ver lo que puedo hacer.")
        while True:
            try:
                self.ciclo_vigilancia()
            except Exception as ex:  # noqa: BLE001 — el bucle no debe morir
                self._error_ciclo(ex)
            time.sleep(self.espera)

    def _error_ciclo(self, ex: Exception) -> None:
        """Registra el error sin inundar el log y avisa si Claude deja de responder."""
        texto = f"{type(ex).__name__}: {ex}"[:200]
        anterior, cuando = self.ultimo_error
        if texto != anterior or time.time() - cuando > 600:
            log.warning("Error en el ciclo: %s", texto)
            self.ultimo_error = (texto, time.time())
        else:
            log.debug("Error repetido: %s", texto)
        if isinstance(ex, anthropic.APIError):
            self.fallos_claude += 1
            if self.fallos_claude >= 3 and not self.aviso_claude:
                self.bot.texto("⚠️ Claude no responde desde hace varios intentos "
                               f"({esc(type(ex).__name__)}). Sigo reintentando; la impresión no se toca.")
                self.aviso_claude = True


def main() -> None:
    Vigia().run()


if __name__ == "__main__":
    main()
