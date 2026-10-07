"""Bot de Telegram: envío de avisos con botones y escucha de comandos/respuestas.

Solo atiende mensajes del chat configurado (TELEGRAM_CHAT_ID): nadie más puede
mandar órdenes a la impresora aunque encuentre el bot.
"""
import html
import json
import logging
import threading
import time
from typing import Callable

import requests

from . import config as C

log = logging.getLogger("vigia.telegram")
API = f"https://api.telegram.org/bot{C.TG_TOKEN}"


def esc(texto) -> str:
    return html.escape(str(texto if texto is not None else ""), quote=False)


def _teclado(botones: list[list[tuple[str, str]]] | None) -> str | None:
    if not botones:
        return None
    return json.dumps({"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in fila]
                                           for fila in botones]})


class Bot:
    def __init__(self) -> None:
        self.activo = bool(C.TG_TOKEN and C.TG_CHAT)
        self.offset = 0
        self.on_comando: Callable[[str, str], None] | None = None
        self.on_boton: Callable[[str, dict], None] | None = None
        self.on_texto: Callable[[str], None] | None = None
        if not self.activo:
            log.warning("Telegram sin configurar: los avisos solo saldrán en el log")

    # ------------------------------------------------------------ envío
    def _post(self, metodo: str, **kw):
        if not self.activo:
            return None
        try:
            r = requests.post(f"{API}/{metodo}", timeout=30, **kw)
            j = r.json()
            if not j.get("ok"):
                log.warning("Telegram %s: %s", metodo, j.get("description"))
            return j.get("result")
        except Exception as e:  # noqa: BLE001
            log.warning("Telegram %s falló: %s", metodo, e)
            return None

    def texto(self, texto: str, botones=None) -> dict | None:
        log.info("TG ▶ %s", texto.replace("\n", " | ")[:200])
        datos = {"chat_id": C.TG_CHAT, "text": texto[:4000], "parse_mode": "HTML",
                 "disable_web_page_preview": "true"}
        if botones:
            datos["reply_markup"] = _teclado(botones)
        return self._post("sendMessage", data=datos)

    def foto(self, jpeg: bytes, texto: str, botones=None) -> dict | None:
        log.info("TG ▶ [foto] %s", texto.replace("\n", " | ")[:200])
        datos = {"chat_id": C.TG_CHAT, "caption": texto[:1000], "parse_mode": "HTML"}
        if botones:
            datos["reply_markup"] = _teclado(botones)
        return self._post("sendPhoto", data=datos,
                          files={"photo": ("impresora.jpg", jpeg, "image/jpeg")})

    def quitar_botones(self, mensaje: dict, nota: str) -> None:
        """Quita los botones de un mensaje ya respondido y añade una nota."""
        chat, mid = mensaje["chat"]["id"], mensaje["message_id"]
        self._post("editMessageReplyMarkup", data={"chat_id": chat, "message_id": mid,
                                                   "reply_markup": json.dumps({"inline_keyboard": []})})
        self.texto(nota)

    # ------------------------------------------------------------ escucha
    def escuchar(self) -> None:
        if not self.activo:
            return
        threading.Thread(target=self._bucle, daemon=True, name="telegram").start()

    def _bucle(self) -> None:
        # Ignora lo pendiente de antes de arrancar
        r = self._post("getUpdates", data={"offset": -1, "timeout": 0})
        if r:
            self.offset = r[-1]["update_id"] + 1
        while True:
            try:
                resp = requests.post(f"{API}/getUpdates", timeout=40,
                                     data={"offset": self.offset, "timeout": 30,
                                           "allowed_updates": json.dumps(["message", "callback_query"])})
                for u in resp.json().get("result", []):
                    self.offset = u["update_id"] + 1
                    self._despachar(u)
            except Exception as e:  # noqa: BLE001
                log.debug("getUpdates: %s", e)
                time.sleep(5)

    def _despachar(self, u: dict) -> None:
        if "callback_query" in u:
            cq = u["callback_query"]
            if str(cq["message"]["chat"]["id"]) != str(C.TG_CHAT):
                return
            self._post("answerCallbackQuery", data={"callback_query_id": cq["id"]})
            if self.on_boton:
                self.on_boton(cq.get("data", ""), cq["message"])
            return
        msg = u.get("message") or {}
        if str((msg.get("chat") or {}).get("id")) != str(C.TG_CHAT):
            return
        txt = (msg.get("text") or "").strip()
        if not txt:
            return
        if txt.startswith("/"):
            cmd, _, resto = txt[1:].partition(" ")
            if self.on_comando:
                self.on_comando(cmd.split("@")[0].lower(), resto.strip())
        elif self.on_texto:
            self.on_texto(txt)
