# -*- coding: utf-8 -*-
"""Immovlan : categorie viager dediee.

Immovlan change regulierement le nom de son parametre de transaction viager.
On tente donc plusieurs URL connues, et on garde la premiere qui donne des
resultats. Les autres sont ignorees silencieusement.
"""

import logging

import config
import parsing
from models import Annonce
from scrapers import base, generic

log = logging.getLogger("scraper.immovlan")

CANDIDATES = [
    "https://immovlan.be/fr/immobilier?transactiontypes=vente-en-viager&noindex=1",
    "https://immovlan.be/fr/immobilier?transactiontypes=a-vendre&keyword=viager",
    "https://immovlan.be/nl/vastgoed?transactiontypes=verkoop-op-lijfrente&noindex=1",
    "https://immovlan.be/nl/vastgoed?transactiontypes=te-koop&keyword=lijfrente",
]
PAGES_MAX = 3


def fetch(source, ctx=None):
    f = base.Fetcher("immovlan")
    faux_source = {"name": "immovlan", "kind": "portail", "tout_viager": False}
    annonces, vus = [], set()

    for gabarit in CANDIDATES:
        if ctx and ctx.temps_ecoule():
            break
        trouve_ici = 0
        for page in range(1, PAGES_MAX + 1):
            url = gabarit + ("&page=%d" % page if page > 1 else "")
            try:
                soup = f.html(url)
            except base.RobotsInterdit:
                break
            except Exception as e:
                log.warning("[immovlan] %s : %s", url, e)
                break
            lot = generic.depuis_jsonld(soup, url, faux_source)
            if len(lot) < 2:
                lot = generic.depuis_cartes(soup, url, faux_source) or lot
            nouveaux = 0
            for a in lot:
                if a.url in vus:
                    continue
                # la categorie viager n'est pas garantie : on revalide au mot-cle
                if not parsing.contient_mot_cle_viager(a.texte() + " " + a.url, config.MOTS_CLES):
                    continue
                vus.add(a.url)
                a.source = "immovlan"
                a.kind = "portail"
                annonces.append(a)
                nouveaux += 1
            trouve_ici += nouveaux
            log.info("[immovlan] %s -> %d", url, nouveaux)
            if nouveaux == 0:
                break
        if trouve_ici:
            break  # cette URL fonctionne, inutile d'essayer les variantes
    return annonces
