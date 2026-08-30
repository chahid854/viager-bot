# -*- coding: utf-8 -*-
"""Immoweb : API JSON interne, filtre viager natif.

Le point cle est le parametre `isALifeAnnuitySale=true` : c'est lui, et lui
seul, qui restreint la recherche au viager. Le segment "verkoop-op-lijfrente"
present dans les URL publiques est ignore par l'API — sans ce parametre, on
recupere les ~10 000 biens a vendre du pays au lieu des ~230 viagers.

L'API renvoie directement le bouquet, la rente mensuelle, l'age du ou des
credirentiers et le PEB : c'est de loin la source la mieux renseignee.

Si Cloudflare finit par bloquer, on log et on rend une liste vide ; les autres
sources continuent et l'alerte "source muette" se declenche apres 5 runs.
"""

import logging
import re

import config
from models import Annonce
from scrapers import base, generic

log = logging.getLogger("scraper.immoweb")

RACINE = "https://www.immoweb.be"
RECHERCHE = (RACINE + "/fr/search-results/%s/for-sale"
             "?countries=BE&isALifeAnnuitySale=true&page=%d&orderBy=newest")
TYPES = ["house", "apartment"]
PAGES_MAX = 4          # 30 resultats par page, soit 120 par type

# Pages d'agences specialisees viager, en complement de la recherche.
AGENCES = [
    "https://www.immoweb.be/fr/agence/immobiliere-le-viager/1544527",
]


def _entier(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return int(v)
    if isinstance(v, str):
        m = re.search(r"\d+", v.replace(".", "").replace(" ", ""))
        return int(m.group(0)) if m else None
    return None


def _est_viager(item):
    flags = (item.get("flags") or {}).get("secondary") or []
    if "life_annuity" in flags:
        return True
    return bool(((item.get("transaction") or {}).get("sale") or {}).get("lifeAnnuity"))


def _depuis_json(item):
    ident = item.get("id")
    if not ident:
        return None
    prop = item.get("property") or {}
    loc = prop.get("location") or {}
    trans = item.get("transaction") or {}
    vente = trans.get("sale") or {}
    viager = vente.get("lifeAnnuity") or {}

    a = Annonce(source="immoweb", url="%s/fr/annonce/%s" % (RACINE, ident),
                source_id=str(ident), kind="portail_immoweb")
    a.titre = (prop.get("title") or "").strip() or " ".join(filter(None, [
        (prop.get("subtype") or prop.get("type") or "Bien").replace("_", " ").capitalize(),
        "en viager a", loc.get("locality") or "",
    ])).strip()

    a.code_postal = str(loc.get("postalCode") or "").strip() or None
    a.commune = (loc.get("locality") or "").strip() or None
    a.localisation = " ".join(str(x) for x in [
        loc.get("street") or "", loc.get("postalCode") or "", loc.get("locality") or ""
    ] if x).strip()

    a.bouquet = _entier(viager.get("lumpSum"))
    a.rente = _entier(viager.get("monthlyAmount"))
    a.prix = _entier(viager.get("estimatedPropertyValue")) or _entier(vente.get("price"))
    a.chambres = _entier(prop.get("bedroomCount"))
    a.surface = _entier(prop.get("netHabitableSurface"))
    a.terrain = _entier(prop.get("landSurface"))

    peb = trans.get("certificate")
    if isinstance(peb, str) and re.fullmatch(r"[A-G]", peb.strip().upper()):
        a.peb = peb.strip().upper()

    t = (prop.get("type") or "").upper()
    if t == "HOUSE":
        a.type_bien = "maison"
    elif t in ("APARTMENT", "FLAT"):
        a.type_bien = "appartement"

    if viager.get("isBareOwnership"):
        a.type_viager = "nue-propriete"
    else:
        occupation = (viager.get("possibilityOfOccupancy") or "").lower()
        if "immediate" in occupation or "libre" in occupation or "vrij" in occupation:
            a.type_viager = "libre"
        elif occupation:
            a.type_viager = "occupe"
        else:
            a.type_viager = "inconnu"

    ages = viager.get("annuitantAges")
    if isinstance(ages, list) and ages:
        entiers = [_entier(x) for x in ages]
        entiers = [x for x in entiers if x and 40 <= x <= 110]
        if entiers:
            a.age_vendeur = max(entiers)
    elif _entier(ages):
        a.age_vendeur = _entier(ages)

    a.description = " ".join(filter(None, [
        prop.get("title") or "",
        (item.get("price") or {}).get("mainDisplayPrice") or "",
        viager.get("contractMaximumDurationDescription") or "",
        viager.get("specification") or "",
        "viager",
    ]))[:1200]

    client = item.get("customerName")
    if client:
        a.agence_nom = str(client)[:120]
        a.description += " | Agence : %s" % client
    return a


def fetch(source, ctx=None):
    f = base.Fetcher("immoweb")
    f.session.headers.update({"Referer": RACINE + "/fr/recherche/maison/a-vendre"})
    annonces, vus = [], set()

    for type_bien in TYPES:
        for page in range(1, PAGES_MAX + 1):
            if ctx and ctx.temps_ecoule():
                break
            url = RECHERCHE % (type_bien, page)
            try:
                data = f.json(url, headers={"Accept": "application/json"})
            except base.RobotsInterdit:
                break
            except Exception as e:
                log.warning("[immoweb] API %s p%d : %s", type_bien, page, e)
                break
            resultats = data.get("results") if isinstance(data, dict) else None
            if not resultats:
                break
            n = 0
            for item in resultats:
                if not _est_viager(item):
                    continue          # garde-fou : si le filtre saute, on ne noie pas la base
                a = _depuis_json(item)
                if a and a.url not in vus:
                    vus.add(a.url)
                    annonces.append(a)
                    n += 1
            log.info("[immoweb] %s page %d -> %d viagers (total annonce : %s)",
                     type_bien, page, n, data.get("totalItems"))
            if len(resultats) < 30:
                break

    # Pages des agences specialisees viager
    faux_source = {"name": "immoweb", "kind": "portail_immoweb", "tout_viager": True}
    for url in AGENCES:
        if ctx and ctx.temps_ecoule():
            break
        try:
            soup = f.html(url)
        except Exception as e:
            log.warning("[immoweb] agence %s : %s", url, e)
            continue
        for a in generic.depuis_cartes(soup, url, faux_source, AGENCES):
            if a.url not in vus:
                vus.add(a.url)
                a.source, a.kind = "immoweb", "portail_immoweb"
                annonces.append(a)
    return annonces
