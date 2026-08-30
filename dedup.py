# -*- coding: utf-8 -*-
"""Deduplication a trois niveaux.

Regle d'arbitrage : en cas de doute, c'est un DOUBLON.
Mieux vaut rater une annonce que se faire spammer.
"""

import hashlib
import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from rapidfuzz import fuzz

import config
import geo

PARAMS_PARASITES = re.compile(
    r"^(utm_|gclid|fbclid|mc_|ref|source|origin|_ga|msclkid|cmp|campaign)", re.I
)


def url_normalisee(url: str) -> str:
    """Enleve les parametres de tracking, le fragment, le slash final et le www."""
    if not url:
        return ""
    p = urlsplit(url.strip())
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=False)
         if not PARAMS_PARASITES.match(k)]
    q.sort()
    netloc = p.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = p.path.rstrip("/") or "/"
    return urlunsplit((p.scheme.lower() or "https", netloc, path, urlencode(q), ""))


def _sha(*parties) -> str:
    return hashlib.sha256("|".join(str(p) for p in parties).encode("utf-8")).hexdigest()


def id_hash(annonce) -> str:
    """Niveau 1 : identifiant natif si la source en fournit un, sinon URL normalisee."""
    if annonce.source_id:
        return _sha(annonce.source, annonce.source_id)
    return _sha(annonce.source, url_normalisee(annonce.url))


def _composants(annonce):
    cp = annonce.code_postal
    surface = annonce.surface
    prix = annonce.bouquet or annonce.prix
    if not cp or not surface or not prix:
        return None
    return cp, (int(surface) // 10) * 10, (int(prix) // 5000) * 5000, annonce.chambres


def fingerprint(annonce):
    """Niveau 2 : empreinte tolerante aux arrondis entre sites.

    Surface a la dizaine inferieure, prix aux 5000 EUR inferieurs.
    Retourne None si les donnees sont trop pauvres pour etre fiables.
    """
    c = _composants(annonce)
    if not c:
        return None
    cp, s, p, ch = c
    return _sha("fp", cp, s, p, ch if ch is not None else "?")


def fingerprints_candidats(annonce):
    """Empreintes a chercher en base pour reconnaitre la MEME annonce ailleurs.

    Sur la SURFACE, l'arrondi a la dizaine ne suffit pas : 118 m2 tombe dans 110,
    120 m2 dans 120, et les deux sites decrivent pourtant le meme bien. On
    interroge donc aussi les seaux voisins.

    Sur le PRIX, en revanche, on s'en tient au seau exact : les sites recopient
    le montant sans le reinterpreter, alors qu'elargir a +/- 5000 EUR ferait
    fusionner deux appartements voisins reellement distincts. Ce qui echappe
    ici est rattrape par le niveau 3 (similarite de titre).

    Le nombre de chambres est cherche aussi en version "absente", parce qu'une
    source sur deux ne le publie pas.
    """
    c = _composants(annonce)
    if not c:
        return []
    cp, s, p, ch = c
    chambres = [ch if ch is not None else "?"]
    if ch is not None:
        chambres.append("?")
    out = []
    for ds in (-10, 0, 10):
        for c_ch in chambres:
            h = _sha("fp", cp, max(0, s + ds), p, c_ch)
            if h not in out:
                out.append(h)
    return out


def titre_comparable(titre: str) -> str:
    t = geo.norm(titre or "")
    # retire le bruit commercial commun a tous les sites
    t = re.sub(r"\b(a vendre|te koop|for sale|viager|lijfrente|nouveau|nieuw|exclusivite)\b", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def doublon_fuzzy(base, annonce):
    """Niveau 3 : meme CP, prix a +/-5%, titre similaire >= seuil.

    Utilise seulement quand la surface manque (donc pas de fingerprint).
    """
    prix = annonce.bouquet or annonce.prix
    if not annonce.code_postal or not prix:
        return None
    t_new = titre_comparable(annonce.titre)
    if len(t_new) < 12:
        return None
    for r in base.candidats_fuzzy(annonce.code_postal, prix):
        score = fuzz.token_set_ratio(t_new, titre_comparable(r["titre"]))
        if score >= config.FUZZ_SEUIL:
            return r
    return None


def prix_reference(annonce):
    """Le prix suivi dans l'historique : le bouquet s'il existe, sinon le prix."""
    return annonce.bouquet or annonce.prix


def priorite(annonce) -> int:
    return config.PRIORITE.get(annonce.kind, 40)
