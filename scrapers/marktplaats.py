# -*- coding: utf-8 -*-
"""2ememain.be / 2dehands.be — les deux faces du meme moteur.

Ces sites exposent une API de recherche JSON (celle utilisee par leur propre
front) : /lrp/api/search. Pas de cle, pas de compte. On y cherche les mots-cles
viager / lijfrente dans le titre ET la description, categorie immobilier.

Secours : la page de recherche HTML /l/immo/q/viager/.
"""

import logging
import re
from urllib.parse import quote

import config
import parsing
from models import Annonce
from scrapers import base, generic

log = logging.getLogger("scraper.marktplaats")

API = ("%s/lrp/api/search?attributesByKey[]=Language%%3Aall-languages"
       "&limit=60&offset=0&query=%s&searchInTitleAndDescription=true"
       "&sortBy=SORT_INDEX&sortOrder=DECREASING&viewOptions=list-view")

# categories immobilier (l1) chez Marktplaats/2ememain
CATEGORIES_IMMO = {1032, 1085, 1086, 1087, 1088, 1089, 1090, 1091, 1092, 1093, 1094}


def _annonce_depuis_listing(item, base_url, nom_source):
    ident = item.get("itemId") or item.get("id")
    url = item.get("vipUrl") or ""
    if url and not url.startswith("http"):
        url = base_url.rstrip("/") + "/" + url.lstrip("/")
    if not url:
        return None
    a = Annonce(source=nom_source, url=url, source_id=str(ident) if ident else None,
                kind="particulier")
    a.titre = (item.get("title") or "")[:200]
    a.description = (item.get("description") or "")[:1500]
    prix = (item.get("priceInfo") or {}).get("priceCents")
    if isinstance(prix, int) and prix > 0:
        a.prix = prix // 100
    loc = item.get("location") or {}
    a.localisation = " ".join(filter(None, [
        str(loc.get("cityName") or ""), str(loc.get("postcode") or "")
    ]))
    a.commune = (loc.get("cityName") or "").strip() or None
    return a


def fetch(source, ctx=None):
    base_url = source.get("base", "https://www.2ememain.be")
    nom = source["name"]
    f = base.Fetcher(nom)
    f.session.headers.update({"Referer": base_url + "/", "Accept": "application/json"})
    annonces, vus = [], set()

    for requete in source.get("queries", ["viager"]):
        if ctx and ctx.temps_ecoule():
            break
        url = API % (base_url, quote(requete))
        try:
            data = f.json(url)
        except base.RobotsInterdit:
            break
        except Exception as e:
            log.warning("[%s] API %s : %s", nom, requete, e)
            continue
        listings = data.get("listings") or data.get("results") or []
        n = 0
        for item in listings:
            cat = item.get("categoryId") or (item.get("categorySpecificDescription") or {}).get("id")
            if cat and int(cat) not in CATEGORIES_IMMO:
                # la recherche plein texte remonte parfois du hors-sujet
                if not parsing.contient_mot_cle_viager(
                        (item.get("title") or "") + " " + (item.get("description") or ""),
                        config.MOTS_CLES):
                    continue
            a = _annonce_depuis_listing(item, base_url, nom)
            if a and a.url not in vus:
                vus.add(a.url)
                annonces.append(a)
                n += 1
        log.info("[%s] '%s' -> %d annonces", nom, requete, n)

    # secours HTML
    if not annonces:
        faux_source = {"name": nom, "kind": "particulier", "tout_viager": False}
        for requete in source.get("queries", ["viager"])[:2]:
            url = "%s/l/immo/q/%s/" % (base_url, quote(requete.replace(" ", "-")))
            try:
                soup = f.html(url)
            except Exception as e:
                log.warning("[%s] HTML %s : %s", nom, url, e)
                continue
            for a in generic.depuis_cartes(soup, url, faux_source):
                if a.url not in vus:
                    vus.add(a.url)
                    a.source = nom
                    a.kind = "particulier"
                    annonces.append(a)
    return annonces
