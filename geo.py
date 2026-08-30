# -*- coding: utf-8 -*-
"""Filtre geographique : par code postal ET par nom de commune (FR/NL)."""

import math
import re
import unicodedata

import config

# Abreviations unifiees. "St-Pieters-Leeuw" et "Sint-Pieters-Leeuw" doivent
# produire exactement la meme chaine normalisee.
ABREVIATIONS = {
    "st": "saint", "ste": "sainte", "sint": "saint", "sinte": "sainte",
    "str": "saint",  # jamais rencontre seul, garde-fou
}


def sans_accents(s: str) -> str:
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def norm(s: str) -> str:
    """minuscules, sans accents, tirets/apostrophes -> espaces, abreviations unifiees."""
    if not s:
        return ""
    s = sans_accents(str(s)).lower()
    s = re.sub(r"[’'`]", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    tokens = [ABREVIATIONS.get(t, t) for t in s.split()]
    return " ".join(tokens)


# --------------------------------------------------------------- index -------
def _index_communes():
    """alias normalise -> code postal. Construit une fois au chargement."""
    idx = {}
    for cp, noms in config.COMMUNES.items():
        for n in noms:
            idx.setdefault(norm(n), cp)
    return idx


ALIAS_INDEX = _index_communes()
ALIAS_AMBIGUS_NORM = {norm(a) for a in config.ALIAS_AMBIGUS}

# Regex de detection, alias les plus longs d'abord (pour que
# "woluwe saint pierre" gagne sur "woluwe").
_ALIAS_TRIES = sorted(ALIAS_INDEX.keys(), key=len, reverse=True)
_ALIAS_RE = re.compile(
    r"(?<![a-z0-9])(" + "|".join(re.escape(a) for a in _ALIAS_TRIES) + r")(?![a-z0-9])"
)

CP_RE = re.compile(r"(?<!\d)([1-9]\d{3})(?!\d)")


def cp_dans_texte(texte: str, zone_cps):
    """Extrait un code postal belge plausible.

    Un nombre a 4 chiffres n'est un code postal que s'il est dans la zone,
    ou s'il est immediatement suivi d'un nom de lieu (ex: '1180 Uccle').
    Evite de prendre '1500' dans '1500 EUR de rente'.
    """
    if not texte:
        return None
    t = sans_accents(texte)
    for m in CP_RE.finditer(t):
        cp = m.group(1)
        suite = t[m.end():m.end() + 30]
        if cp in zone_cps or cp in config.COMMUNES:
            # ecarte "1500 euros", "1500 EUR"
            if re.match(r"\s*(euro|eur|€|/|m2|m²)", suite, re.I):
                continue
            return cp
        if re.match(r"\s+[A-Z][a-zA-Z\-]{2,}", suite):
            return cp  # code postal hors zone, mais bien un code postal
    return None


# "Bruxelles" tout court designe la region aussi souvent que la commune 1000 :
# on ne veut pas inventer un code postal a partir de ca.
ALIAS_REGION = {norm(a) for a in ("Bruxelles", "Brussel", "Brussels")}


def communes_dans_texte(texte: str, ambigus_autorises: bool, avec_alias=False):
    """Retourne la liste des codes postaux dont une appellation apparait."""
    if not texte:
        return []
    t = norm(texte)
    trouves, alias_par_cp = [], {}
    for m in _ALIAS_RE.finditer(t):
        alias = m.group(1)
        if alias in ALIAS_AMBIGUS_NORM and not ambigus_autorises:
            continue
        cp = ALIAS_INDEX[alias]
        if cp not in trouves:
            trouves.append(cp)
            alias_par_cp[cp] = alias
    if avec_alias:
        return trouves, alias_par_cp
    return trouves


def nom_commune(cp: str) -> str:
    noms = config.COMMUNES.get(cp)
    return noms[0] if noms else ""


# ------------------------------------------------------------- matching ------
def resoudre(annonce, zone_cps):
    """Determine (garde, cp, commune, avertissements) pour une annonce.

    Regles demandees :
      - retenue si CP dans la zone OU si une appellation de commune y figure
      - en cas de contradiction CP / nom, le CODE POSTAL fait foi (et on loggue)
      - sans CP ni commune reconnue mais avec 'Bruxelles'/'Brussel' : on garde
        avec la mention "localisation a verifier"
      - les alias ambigus ne comptent que dans le champ localisation
    """
    avert = []
    zone_cps = set(zone_cps)

    cp = (annonce.code_postal or "").strip() or None
    if cp and not re.fullmatch(r"[1-9]\d{3}", cp):
        cp = None
    if not cp:
        cp = cp_dans_texte(annonce.localisation, zone_cps) or cp_dans_texte(annonce.titre, zone_cps)
    if not cp:
        cp = cp_dans_texte(annonce.description, zone_cps)

    # noms de commune : champ localisation + titre (alias ambigus autorises),
    # puis description (alias ambigus refuses)
    cps_localisation, alias_vus = communes_dans_texte(
        " ".join(filter(None, [annonce.localisation, annonce.titre, annonce.commune or ""])),
        ambigus_autorises=True, avec_alias=True,
    )
    cps_description = communes_dans_texte(annonce.description, ambigus_autorises=False)
    cps_nom = cps_localisation + [c for c in cps_description if c not in cps_localisation]

    # "Appartement a Bruxelles Saint-Josse-ten-Noode" : les deux noms matchent,
    # et "Bruxelles" gagnerait juste parce qu'il vient en premier. La commune
    # precise l'emporte toujours sur le "Bruxelles" generique.
    if len(cps_nom) > 1 and "1000" in cps_nom and alias_vus.get("1000") in ALIAS_REGION:
        cps_nom = [c for c in cps_nom if c != "1000"]

    # arbitrage CP vs nom. "1020 Laeken" + "Bruxelles" n'est pas une
    # contradiction : Laeken EST Bruxelles. On ne signale que les vrais conflits.
    if cp and cps_nom and cp not in cps_nom:
        familles = {config.COMMUNE_MERE.get(c, c) for c in cps_nom} | set(cps_nom)
        if config.COMMUNE_MERE.get(cp, cp) not in familles:
            avert.append(
                "incoherence localisation : CP %s vs nom(s) %s -> CP retenu"
                % (cp, ",".join(nom_commune(c) for c in cps_nom))
            )

    if cp:
        garde = cp in zone_cps
        return garde, cp, nom_commune(cp) or (annonce.commune or ""), avert

    if cps_nom:
        # cas particulier : le seul indice est un "Bruxelles" generique, qui
        # designe la region autant que la commune 1000. On garde l'annonce mais
        # sans inventer de code postal.
        if cps_nom == ["1000"] and alias_vus.get("1000") in ALIAS_REGION:
            avert.append("⚠️ localisation a verifier")
            return True, None, "Bruxelles (?)", avert
        dans_zone = [c for c in cps_nom if c in zone_cps]
        if dans_zone:
            return True, dans_zone[0], nom_commune(dans_zone[0]), avert
        return False, cps_nom[0], nom_commune(cps_nom[0]), avert

    # filet : mention de la region bruxelloise sans commune identifiee
    t = norm(annonce.texte())
    if re.search(r"(?<![a-z])(region bruxelloise|bruxelloise|brussels hoofdstedelijk|"
                 r"brusselse rand|grand bruxelles)(?![a-z])", t):
        avert.append("⚠️ localisation a verifier")
        return True, None, "Bruxelles (?)", avert

    return False, None, None, avert


# ---------------------------------------------------------------- rayon ------
def distance_km(a, b) -> float:
    lat1, lon1 = a
    lat2, lon2 = b
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def cps_dans_rayon(km: float, centre=None):
    centre = centre or config.CENTRE_BRUXELLES
    return sorted(cp for cp, xy in config.COORDS.items() if distance_km(centre, xy) <= km)


def resoudre_saisie_communes(saisie: str):
    """/commune Uccle,Dilbeek -> (cps trouves, entrees inconnues). Accepte FR et NL."""
    ok, inconnus = [], []
    for brut in saisie.split(","):
        brut = brut.strip()
        if not brut:
            continue
        cp = ALIAS_INDEX.get(norm(brut))
        if cp:
            if cp not in ok:
                ok.append(cp)
        else:
            inconnus.append(brut)
    return ok, inconnus
