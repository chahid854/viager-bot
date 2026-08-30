# -*- coding: utf-8 -*-
"""Scraper generique pilote par la config.

Couvre les ~35 sites d'agences et de portails qui n'ont pas d'API : il lit
d'abord le JSON-LD (schema.org) quand le site en publie, ce qui est fiable, et
retombe sinon sur une detection heuristique des cartes d'annonces.

C'est volontairement tolerant : mieux vaut ramener une annonce a moitie remplie
(parsing.completer fera le reste) que de rien ramener parce qu'une classe CSS a
change.
"""

import json
import logging
import re

import config
import parsing
from models import Annonce
from scrapers import base

log = logging.getLogger("scraper.generic")

MAX_PAR_SOURCE = 120

LIEN_DETAIL = re.compile(
    r"/(?:bien|biens|goed|property|properties|annonce|annonces|te-koop|a-vendre|"
    r"pand|panden|woning|woningen|huis|maison|appartement|apartment|detail|details|"
    r"listing|listings|estate|object|objecten|immo|viager|viagers|lijfrente|"
    r"aanbod|realisatie|vastgoed|id)\b", re.I,
)
LIEN_NUMERIQUE = re.compile(r"(?:[-/](\d{4,})/?$)|(?:[?&]id=\d+)", re.I)
LIEN_EXCLU = re.compile(
    r"^(?:mailto:|tel:|javascript:|#)|"
    r"(?:\.pdf|\.jpg|\.png|\.zip|\.doc\w*)$|"
    r"/(?:wp-content|wp-admin|wp-json|category|categorie|tag|author|feed|contact|"
    r"about|a-propos|over-ons|nieuws|actualites|blog|faq|cookie|privacy|"
    r"mentions|disclaimer|login|connexion|panier)\b|"
    r"(?:facebook|instagram|linkedin|twitter|youtube|pinterest|whatsapp)\.com",
    re.I,
)
CLASSES_CARTE = re.compile(
    r"(card|item|result|listing|annonce|bien|property|pand|woning|teaser|tile|"
    r"estate|object|product|entry|post)", re.I,
)
CLASSES_LOC = re.compile(r"(location|localisation|city|ville|gemeente|adres|address|plaats|commune)", re.I)

TYPES_LD = {
    "product", "offer", "realestatelisting", "residence", "house", "apartment",
    "singlefamilyresidence", "accommodation", "place", "listing",
}


# ---------------------------------------------------------------- JSON-LD ---
def _plat(obj):
    """Aplati un JSON-LD (objets, listes, @graph) en une liste de dicts."""
    out = []
    if isinstance(obj, list):
        for o in obj:
            out.extend(_plat(o))
    elif isinstance(obj, dict):
        out.append(obj)
        for cle in ("@graph", "itemListElement", "item", "mainEntity", "offers"):
            if cle in obj:
                out.extend(_plat(obj[cle]))
    return out


def _type_ld(d):
    t = d.get("@type") or d.get("type") or ""
    if isinstance(t, list):
        t = t[0] if t else ""
    return str(t).lower()


def _nombre(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return int(v)
    m = re.search(r"\d[\d.\s]*", str(v))
    return int(re.sub(r"[.\s]", "", m.group(0))) if m else None


def depuis_jsonld(soup, url_page, source):
    annonces = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        brut = script.string or script.get_text() or ""
        if not brut.strip():
            continue
        try:
            data = json.loads(brut)
        except Exception:
            try:
                data = json.loads(re.sub(r",\s*([}\]])", r"\1", brut))
            except Exception:
                continue
        for d in _plat(data):
            if _type_ld(d) not in TYPES_LD:
                continue
            lien = d.get("url") or d.get("@id") or ""
            if isinstance(lien, dict):
                lien = lien.get("@id") or lien.get("url") or ""
            if not lien or not str(lien).startswith("http"):
                continue
            nom = d.get("name") or d.get("headline") or ""
            if not nom:
                continue
            a = Annonce(source=source["name"], url=str(lien), titre=str(nom)[:200],
                        kind=source.get("kind", "portail"))
            a.description = str(d.get("description") or "")[:1200]

            offre = d.get("offers")
            if isinstance(offre, list):
                offre = offre[0] if offre else None
            if isinstance(offre, dict):
                a.prix = _nombre(offre.get("price"))

            adresse = d.get("address")
            if isinstance(adresse, dict):
                a.code_postal = str(adresse.get("postalCode") or "").strip() or None
                a.commune = (adresse.get("addressLocality") or "").strip() or None
                a.localisation = " ".join(filter(None, [
                    str(adresse.get("streetAddress") or ""),
                    str(adresse.get("postalCode") or ""),
                    str(adresse.get("addressLocality") or ""),
                ]))
            elif isinstance(adresse, str):
                a.localisation = adresse

            a.chambres = _nombre(d.get("numberOfRooms") or d.get("numberOfBedrooms"))
            taille = d.get("floorSize")
            if isinstance(taille, dict):
                a.surface = _nombre(taille.get("value"))
            annonces.append(a)
    return annonces


# ------------------------------------------------------------- heuristique --
def _conteneur(lien):
    """Remonte jusqu'au bloc qui represente la carte de l'annonce."""
    el = lien
    meilleur = lien
    for _ in range(5):
        el = el.parent
        if el is None or el.name in ("body", "html"):
            break
        classes = " ".join(el.get("class") or []) + " " + (el.get("id") or "")
        longueur = len(el.get_text(" ", strip=True))
        if CLASSES_CARTE.search(classes) and 40 <= longueur <= 2500:
            return el
        if longueur > 2500:
            break
        meilleur = el
    return meilleur


GENERIQUE = re.compile(
    r"^(?:viager|lijfrente|leefrente|bien|goed|te koop|a vendre|occupe|libre|"
    r"bezet|vrij|nouveau|nieuw|voir|lire|details?|plus)[\s\-]*"
    r"(?:occupe|libre|bezet|vrij|viager|lijfrente)?$", re.I,
)


def _titre_depuis_url(url):
    """Beaucoup d'agences mettent un titre passe-partout dans la carte
    ("Viager Occupé") et le vrai libelle dans le slug de l'URL."""
    segments = [s for s in re.split(r"[/?#]", url) if s]
    for seg in reversed(segments):
        if re.fullmatch(r"\d+", seg) or len(seg) < 12:
            continue
        mots = re.split(r"[-_+]", re.sub(r"\.(html?|php|aspx?)$", "", seg))
        mots = [m for m in mots if m and not re.fullmatch(r"\d{1,3}", m)]
        if len(mots) >= 3:
            return " ".join(mots).replace("ch ", "chambres ").capitalize()[:200]
    return ""


BRUIT_TITRE = re.compile(
    r"^\s*(?:a la une|à la une|nouveau|nieuw|new|exclusivite|exclusivité|top)\s*[:\-]?\s*|"
    r"\s*(?:miniature|thumbnail|photo|afbeelding|image)\s*$", re.I)


def _nettoyer_titre(t):
    """Retire les etiquettes de vignette collees au libelle par les cartes HTML."""
    avant = None
    while avant != t:
        avant = t
        t = BRUIT_TITRE.sub("", t).strip(" -–—:|")
    return re.sub(r"\s{2,}", " ", t)


def _titre(conteneur, lien, url=""):
    candidats = []
    for balise in ("h1", "h2", "h3", "h4", "h5"):
        h = conteneur.find(balise)
        if h:
            t = base.texte(h, 200)
            if len(t) > 3:
                candidats.append(t)
                break
    t = base.texte(lien, 200)
    if len(t) > 3:
        candidats.append(t)
    for attr in ("title", "aria-label"):
        if lien.get(attr):
            candidats.append(lien[attr][:200])
    img = conteneur.find("img")
    if img and img.get("alt"):
        candidats.append(img["alt"][:200])

    candidats = [_nettoyer_titre(c) for c in candidats]
    for t in candidats:
        t = t.strip()
        if not GENERIQUE.match(t) and 12 < len(t) <= 90:
            return t
    depuis_url = _titre_depuis_url(url)
    if depuis_url:
        return depuis_url
    # dernier recours : un bloc de carte concatene, coupe proprement
    for t in candidats:
        t = t.strip()
        if len(t) > 90:
            return re.split(r"\s+[€•|]|\s{2,}", t)[0][:90].strip() or t[:90]
    return candidats[0] if candidats else ""


def _localisation(conteneur):
    for el in conteneur.find_all(True, class_=CLASSES_LOC, limit=3):
        t = base.texte(el, 120)
        if t:
            return t
    m = re.search(r"\b[1-9]\d{3}\b[^\n,;|]{0,40}", conteneur.get_text(" ", strip=True))
    return m.group(0)[:120] if m else ""


def depuis_cartes(soup, url_page, source, pages_liste=None, infos=None):
    """`infos` recoit le compte de liens candidats et d'annonces vendues.

    C'est ce qui permet de distinguer une page reellement vide (fin de la
    pagination) d'une page pleine dont tout a ete filtre.
    """
    annonces, vus = [], set()
    tout_viager = source.get("tout_viager", source.get("kind") == "agence")
    # certains sites nomment leurs fiches autrement (slug aleatoire, id maison) :
    # "lien_re" dans config.py remplace alors la detection par defaut
    perso = source.get("lien_re")
    perso = re.compile(perso, re.I) if perso else None
    # les pages de liste elles-memes ("/biens/", "/aanbod") matchent les memes
    # motifs que les annonces : on les ecarte explicitement
    exclues = {url_page.rstrip("/")}
    for u in (pages_liste or []):
        exclues.add(u.split("?")[0].rstrip("/"))
        exclues.add(re.sub(r"/page/\d+/?$", "", u.split("?")[0]).rstrip("/"))

    # Une meme annonce est souvent liee plusieurs fois dans la page : depuis sa
    # carte, depuis sa photo, depuis un "Descriptif complet"... Ces liens n'ont
    # pas le meme bloc parent, et un seul d'entre eux porte le badge "Vendu".
    # On regroupe donc toutes les occurrences d'une URL avant de decider.
    groupes = {}
    ordre = []
    for lien in soup.find_all("a", href=True):
        href = lien["href"].strip()
        if not href or LIEN_EXCLU.search(href):
            continue
        if perso is not None:
            if not perso.search(href):
                continue
        elif not (LIEN_DETAIL.search(href) or LIEN_NUMERIQUE.search(href)):
            continue
        url = base.absolu(url_page, href)
        if url.split("?")[0].rstrip("/") in exclues:
            continue
        if url not in groupes:
            groupes[url] = []
            ordre.append(url)
        if len(groupes[url]) < 4:
            groupes[url].append(lien)

    if infos is not None:
        infos["candidats"] = len(ordre)
        infos["vendus"] = 0

    for url in ordre:
        blocs = []
        for lien in groupes[url]:
            conteneur = _conteneur(lien)
            blocs.append((conteneur, base.texte(conteneur, 1500),
                          _titre(conteneur, lien, url)))

        # le bloc le plus riche sert de description, mais le statut "vendu" est
        # teste sur chacun : il suffit qu'une seule occurrence le signale
        if any(parsing.est_vendu(t, txt) for _, txt, t in blocs):
            if infos is not None:
                infos["vendus"] += 1
            continue

        conteneur, txt, titre = max(blocs, key=lambda b: len(b[1]))
        for _, _, t in blocs:                       # un vrai libelle plutot que
            if t and not GENERIQUE.match(t.strip()) and 12 < len(t.strip()) <= 90:
                titre = t                           # "Descriptif complet"
                break
        if not titre or len(txt) < 25:
            continue
        # Le mot-cle se cherche dans le CHEMIN de l'url, jamais dans sa query :
        # plusieurs portails recopient "?search=viager" dans chaque lien de
        # resultat, ce qui faisait passer n'importe quelle annonce pour du viager.
        chemin = url.split("?")[0]
        if not tout_viager and not parsing.contient_mot_cle_viager(
                " ".join([titre, txt, chemin]), config.MOTS_CLES):
            continue

        vus.add(url)
        a = Annonce(source=source["name"], url=url, titre=titre,
                    kind=source.get("kind", "portail"))
        a.description = txt
        a.localisation = _localisation(conteneur)
        annonces.append(a)
        if len(annonces) >= MAX_PAR_SOURCE:
            break
    return annonces


# ------------------------------------------------------------------ fetch ---
def fetch(source, ctx=None):
    f = base.Fetcher(source["name"], verify=source.get("verify", True))
    resultats, vus = [], set()
    liste_pages = base.pages_de(source)
    for url in liste_pages:
        if ctx and ctx.temps_ecoule():
            log.warning("[%s] budget temps atteint, arret de la pagination", source["name"])
            break
        try:
            soup = f.html(url)
        except base.RobotsInterdit:
            continue
        except Exception as e:
            log.warning("[%s] %s : %s", source["name"], url, e)
            continue

        infos = {"candidats": 0, "vendus": 0}
        lot = depuis_jsonld(soup, url, source)
        if len(lot) < 2:
            lot = depuis_cartes(soup, url, source, liste_pages, infos) or lot
        else:
            infos["candidats"] = len(lot)

        nouveaux = 0
        for a in lot:
            if a.url in vus:
                continue
            vus.add(a.url)
            resultats.append(a)
            nouveaux += 1
        log.info("[%s] %s -> %d annonces (%d liens, %d vendus ecartes)",
                 source["name"], url, nouveaux, infos["candidats"], infos["vendus"])

        # Pagination : on s'arrete quand la page ne contient PLUS AUCUN lien
        # d'annonce. Se fier au nombre d'annonces retenues couperait la
        # pagination des qu'une page entiere est filtree (que des biens vendus,
        # par exemple), en laissant les pages suivantes inexplorees.
        m = re.search(r"(?:page[=/]|/page/)(\d+)", url)
        if infos["candidats"] == 0 and m and int(m.group(1)) >= 2:
            break
        if len(resultats) >= MAX_PAR_SOURCE:
            break
    return resultats
