# -*- coding: utf-8 -*-
"""Enrichissement des annonces NEUVES par leur page de detail.

Les pages de liste affichent rarement le bouquet, la rente ou le PEB. On va
donc chercher la fiche complete — mais uniquement pour les annonces qui viennent
d'entrer en base (quelques-unes par run), et seulement si des champs utiles
manquent. C'est ce qui fait la difference entre une notification "prix non
communique" et une notification exploitable.

Une page par domaine a la fois, avec le meme delai poli que le reste.
"""

import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

import config
import parsing
from scrapers import base

log = logging.getLogger("details")

CHAMPS_UTILES = ("bouquet", "rente", "prix", "surface", "chambres", "peb", "terrain")


def _incomplete(a):
    if a.bouquet is None and a.prix is None:
        return True
    return sum(1 for c in CHAMPS_UTILES if getattr(a, c, None) is None) >= 3


def _traiter_domaine(annonces, ctx):
    f = base.Fetcher(annonces[0].source)
    for a in annonces:
        if ctx and ctx.temps_ecoule():
            return
        try:
            soup = f.html(a.url)
        except base.RobotsInterdit:
            return
        except Exception as e:
            log.debug("detail %s : %s", a.url, e)
            continue
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        corps = soup.find("main") or soup.find("article") or soup.body or soup
        a.description = (a.description + " " + base.texte(corps, 6000))[:6000]
        parsing.completer(a, config.MOTS_CLES)


def enrichir(annonces, ctx, limite=18):
    """Complete sur place les Annonce passees. Retourne le nombre traite."""
    cibles = [a for a in annonces if _incomplete(a)][:limite]
    if not cibles:
        return 0
    par_domaine = defaultdict(list)
    for a in cibles:
        par_domaine[base.domaine(a.url)].append(a)
    log.info("enrichissement de %d annonce(s) neuves sur %d domaine(s)",
             len(cibles), len(par_domaine))
    with ThreadPoolExecutor(max_workers=min(6, len(par_domaine))) as pool:
        list(pool.map(lambda lot: _traiter_domaine(lot, ctx), par_domaine.values()))
    return len(cibles)
