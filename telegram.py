# -*- coding: utf-8 -*-
"""Client minimal de l'API Bot Telegram. Aucun service tiers."""

import json
import logging
import time

import requests

import config

log = logging.getLogger("telegram")
API = "https://api.telegram.org/bot%s/%s"
_dernier_envoi = [0.0]


class Telegram:
    def __init__(self, token=None, destinataires=None, dry_run=False):
        self.token = token or config.TELEGRAM_TOKEN
        self.destinataires = destinataires if destinataires is not None else config.chat_ids()
        self.dry_run = dry_run
        self.session = requests.Session()

    @property
    def actif(self):
        return bool(self.token and self.destinataires)

    # ------------------------------------------------------------- bas niveau
    def _appel(self, methode, payload=None, files=None):
        if not self.token:
            log.warning("TELEGRAM_TOKEN absent, appel %s ignore", methode)
            return None
        try:
            r = self.session.post(API % (self.token, methode), json=payload,
                                  timeout=config.HTTP_TIMEOUT)
            data = r.json()
            if not data.get("ok"):
                log.error("Telegram %s a echoue : %s", methode, data.get("description"))
                return None
            return data.get("result")
        except Exception as e:
            log.error("Telegram %s : %s", methode, e)
            return None

    def _throttle(self):
        """1 message par seconde maximum (rate limit Telegram)."""
        delta = time.time() - _dernier_envoi[0]
        if delta < 1.0:
            time.sleep(1.0 - delta)
        _dernier_envoi[0] = time.time()

    # -------------------------------------------------------------- envoi ---
    def envoyer(self, texte, clavier=None, cibles=None, apercu=False):
        """Envoie a tous les destinataires. Un echec sur l'un n'arrete pas les autres."""
        cibles = cibles or self.destinataires
        if self.dry_run:
            print("\n--- TELEGRAM (dry-run) ---\n%s\n" % texte)
            return True
        envoye = False
        for chat_id in cibles:
            self._throttle()
            payload = {
                "chat_id": chat_id,
                "text": texte,
                "parse_mode": "HTML",
                "disable_web_page_preview": not apercu,
            }
            if clavier:
                payload["reply_markup"] = {"inline_keyboard": clavier}
            res = self._appel("sendMessage", payload)
            if res is None:
                log.error("Envoi impossible vers %s (bot bloque ou id invalide) — on continue",
                          chat_id)
            else:
                envoye = True
        return envoye

    # ------------------------------------------------------------ commandes -
    def updates(self, offset=None):
        payload = {"timeout": 0, "allowed_updates": ["message", "callback_query"]}
        if offset:
            payload["offset"] = int(offset)
        return self._appel("getUpdates", payload) or []

    def repondre_callback(self, callback_id, texte=""):
        if self.dry_run:
            return
        self._appel("answerCallbackQuery", {"callback_query_id": callback_id, "text": texte})

    def declarer_commandes(self, commandes):
        """setMyCommands : autocompletion dans le client Telegram."""
        if self.dry_run:
            return
        self._appel("setMyCommands", {
            "commands": [{"command": c, "description": d} for c, d in commandes]
        })
