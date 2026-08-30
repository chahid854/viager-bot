# -*- coding: utf-8 -*-
"""Extraction heuristique des champs a partir du texte brut d'une annonce.

Partage par tous les scrapers : chaque source remplit ce qu'elle sait de facon
structuree, puis on complete les trous en lisant le texte.
"""

import re

import geo

# ------------------------------------------------------------- montants -----
_MONTANT = re.compile(
    r"(?:€|eur\b|euros?\b)?\s*"
    r"(\d{1,3}(?:[.\s ]\d{3})+|\d{4,8})"
    r"\s*(?:€|eur\b|euros?\b|k\b)?",
    re.I,
)


def _valeur(m):
    return int(re.sub(r"[.\s ]", "", m.group(1)))


def montants(texte):
    """Liste de (valeur, debut, fin) pour tous les montants plausibles."""
    out = []
    if not texte:
        return out
    for m in _MONTANT.finditer(texte):
        v = _valeur(m)
        if 100 <= v <= 9_000_000:
            out.append((v, m.start(), m.end()))
    return out


def _proche(texte, mots, fenetre=90):
    """Retourne les intervalles autour des mots-cles donnes."""
    zones = []
    for mot in mots:
        for m in re.finditer(mot, texte, re.I):
            zones.append((max(0, m.start() - 20), m.end() + fenetre))
    return zones


def _montant_pres_de(texte, mots, mini=0, maxi=10_000_000, fenetre=90):
    zones = _proche(texte, mots, fenetre)
    if not zones:
        return None
    for v, d, f in montants(texte):
        if not (mini <= v <= maxi):
            continue
        for z0, z1 in zones:
            if z0 <= d <= z1:
                return v
    return None


def bouquet(texte):
    return _montant_pres_de(texte, [r"bouquet", r"boeket", r"kapitaal bij akte"],
                            mini=1000, maxi=5_000_000)


def rente(texte):
    """Rente mensuelle. Cherche un montant lie a rente/lijfrente ou suivi de /mois."""
    if not texte:
        return None
    m = re.search(
        r"(\d{1,3}(?:[.\s ]\d{3})*|\d{3,6})\s*(?:€|eur|euros?)?\s*"
        r"(?:/|par |pe?r |p/)\s*(mois|maand|month|mnd)",
        texte, re.I,
    )
    if m:
        v = int(re.sub(r"[.\s ]", "", m.group(1)))
        if 50 <= v <= 20000:
            return v
    v = _montant_pres_de(texte, [r"rente\s*viag", r"rente\s*mensuelle", r"lijfrente",
                                 r"maandelijkse\s*rente", r"\brente\b"],
                         mini=50, maxi=20000, fenetre=60)
    return v


def prix(texte):
    """Prix affiche / valeur venale. Ecarte les montants deja lus comme rente."""
    if not texte:
        return None
    v = _montant_pres_de(texte, [r"prix", r"vraagprijs", r"prijs", r"valeur\s*v[ée]nale",
                                 r"waarde", r"price"], mini=10000, maxi=9_000_000)
    if v:
        return v
    grands = [v for v, _, _ in montants(texte) if 25000 <= v <= 5_000_000]
    return min(grands) if grands else None


# --------------------------------------------------------------- champs -----
def chambres(texte):
    if not texte:
        return None
    m = re.search(r"(\d{1,2})\s*(?:chambres?|ch\.|chbr|slaapkamers?|slpks?|slk|bedrooms?|bed\b)",
                  texte, re.I)
    if m:
        n = int(m.group(1))
        return n if 0 < n <= 20 else None
    m = re.search(r"(?:chambres?|slaapkamers?|bedrooms?)\s*[:\-]?\s*(\d{1,2})", texte, re.I)
    if m:
        n = int(m.group(1))
        return n if 0 < n <= 20 else None
    return None


_M2 = r"(\d{2,5})\s*(?:m²|m2|m\^2|\bm\b)"


def surface(texte):
    if not texte:
        return None
    # "180 m² habitables" d'abord : le mot-cle suit le nombre plus souvent qu'il
    # ne le precede, et chercher dans l'autre sens ferait sauter la virgule
    # jusqu'au "320 m² de terrain" de la phrase suivante.
    m = re.search(_M2 + r"\s*(?:habitables?|bewoonbaar|woonopp)", texte, re.I)
    if not m:
        m = re.search(r"(?:habitable|bewoonbaar|woonopp\w*|superficie habitable|living area)"
                      r"[^,;.\d]{0,12}" + _M2, texte, re.I)
    if not m:
        m = re.search(_M2, texte, re.I)
    if m:
        v = int(m.group(1))
        return v if 10 <= v <= 2000 else None
    return None


def terrain(texte):
    if not texte:
        return None
    for pat in (r"(?:terrain|grond|perceel|grondopp\w*|jardin|tuin|plot)\D{0,15}" + _M2,
                _M2 + r"\s*(?:de\s*terrain|grond|perceel)"):
        m = re.search(pat, texte, re.I)
        if m:
            v = int(m.group(1))
            if 10 <= v <= 100000:
                return v
    return None


def peb(texte):
    if not texte:
        return None
    m = re.search(r"(?:peb|epc|epb|energie\w*|energy)\s*[:\-]?\s*(?:label\s*)?\b([A-G])\b",
                  texte, re.I)
    if m:
        return m.group(1).upper()
    m = re.search(r"\b(?:label|klasse|classe)\s*([A-G])\b", texte, re.I)
    return m.group(1).upper() if m else None


PEB_ORDRE = {c: i for i, c in enumerate("ABCDEFG")}


def type_bien(texte):
    t = geo.norm(texte or "")
    if re.search(r"\b(appartement|appart|appt|flat|studio|duplex|penthouse|loft|rez de chaussee)\b", t):
        return "appartement"
    if re.search(r"\b(maison|huis|woning|villa|bungalow|fermette|hoeve|herenhuis|cottage)\b", t):
        return "maison"
    if re.search(r"\b(terrain|bouwgrond|grond te koop|perceel bouwgrond)\b", t):
        return "terrain"
    if re.search(r"\b(immeuble|opbrengsteigendom|gebouw|commerce|handelspand)\b", t):
        return "immeuble"
    return None


def type_viager(texte):
    t = geo.norm(texte or "")
    if re.search(r"\b(nue propriete|nue proprietes|blote eigendom|naakte eigendom|bare ownership)\b", t):
        return "nue-propriete"
    if re.search(r"\b(viager libre|vrije lijfrente|libre d occupation|vrij van bewoning|leeg opgeleverd)\b", t):
        return "libre"
    if re.search(r"\b(viager occupe|bezette lijfrente|occupe|bezet|bewoond|met vruchtgebruik|usufruit)\b", t):
        return "occupe"
    if re.search(r"\b(vente a terme|verkoop op termijn)\b", t):
        return "vente-a-terme"
    if re.search(r"\b(viager|lijfrente|leefrente|life annuity)\b", t):
        return "inconnu"
    return None


def jardin(texte):
    t = geo.norm(texte or "")
    if re.search(r"\b(sans jardin|geen tuin)\b", t):
        return False
    return True if re.search(r"\b(jardin|tuin|garden)\b", t) else None


def garage(texte):
    t = geo.norm(texte or "")
    if re.search(r"\b(sans garage|geen garage|geen parking)\b", t):
        return False
    return True if re.search(r"\b(garage|parking|carport|box|standplaats)\b", t) else None


def age_vendeur(texte):
    if not texte:
        return None
    ages = []
    for m in re.finditer(r"(\d{2})\s*(?:ans|jaar|j\.|years)\b", texte, re.I):
        contexte = texte[max(0, m.start() - 90):m.end() + 40].lower()
        if re.search(r"vendeur|vendeuse|credirentier|cr[ée]direntier|occupant|dame|monsieur|madame|"
                     r"homme|femme|verkoper|verkoopster|bewoner|mevrouw|meneer|dame van|leeftijd|"
                     r"[âa]ge", contexte):
            v = int(m.group(1))
            if 50 <= v <= 105:
                ages.append(v)
    return max(ages) if ages else None


# Attention aux faux positifs : "a vendre" n'est pas "vendu", et "reserve
# d'usufruit" est du vocabulaire viager courant, pas une reservation. On ne
# retient donc que des marqueurs sans ambiguite.
VENDU = re.compile(
    r"\b(?:vendus?|vendues?|verkocht|sold|uitverkocht|"
    r"sous\s+option|en\s+option|onder\s+optie|in\s+optie|onder\s+bod|"
    r"sous\s+compromis|compromis\s+sign\w*|gereserveerd|"
    r"n['e]\s*est\s+plus\s+disponible|niet\s+meer\s+beschikbaar|"
    r"plus\s+disponible)\b"
    # "vendu EN nue-propriete / EN viager" decrit le montage de la vente,
    # pas un bien parti : ce n'est pas un marqueur de vente conclue.
    r"(?!\s+(?:en|op)\s+(?:nue|nu\b|pleine|toute|viager|lijfrente|blote|"
    r"naakte|indivision|bloc))", re.I)


# Les badges "Vendu" sont colles en tete de carte. Au-dela, on tombe sur le
# texte de l'annonce voisine, dont le statut n'a rien a voir.
FENETRE_VENDU = 60


def est_vendu(titre, texte="", fenetre=FENETRE_VENDU):
    """Le bien est-il deja vendu ? Beaucoup d'agences les gardent en vitrine.

    On ne regarde QUE le titre et le tout debut de la carte, la ou les sites
    posent leur badge ("Vendu Viager Occupe Schaerbeek..."). Chercher plus loin
    produit deux faux positifs constants :

      - "le bien est vendu en nue-propriete" decrit le type de vente, pas un
        bien parti ;
      - le texte d'une carte deborde souvent sur l'annonce voisine, dont le
        "vendu" contaminerait celle qu'on examine.
    """
    if VENDU.search(titre or ""):
        return True
    return bool(VENDU.search((texte or "")[:fenetre]))


def contient_mot_cle_viager(texte, mots_cles):
    t = geo.norm(texte or "")
    for mot in mots_cles:
        if geo.norm(mot) in t:
            return True
    return False


def completer(annonce, mots_cles):
    """Remplit tous les champs manquants a partir du texte de l'annonce."""
    txt = annonce.texte()
    if annonce.bouquet is None:
        annonce.bouquet = bouquet(txt)
    if annonce.rente is None:
        annonce.rente = rente(txt)
    if annonce.prix is None:
        annonce.prix = prix(txt)
    if annonce.prix and annonce.bouquet and annonce.prix == annonce.rente:
        annonce.prix = None
    if annonce.chambres is None:
        annonce.chambres = chambres(txt)
    if annonce.surface is None:
        annonce.surface = surface(txt)
    if annonce.terrain is None:
        annonce.terrain = terrain(txt)
    if annonce.peb is None:
        annonce.peb = peb(txt)
    if annonce.type_bien is None:
        annonce.type_bien = type_bien(txt)
    if annonce.type_viager is None:
        annonce.type_viager = type_viager(txt)
    if annonce.jardin is None:
        annonce.jardin = jardin(txt)
    if annonce.garage is None:
        annonce.garage = garage(txt)
    if annonce.age_vendeur is None:
        annonce.age_vendeur = age_vendeur(txt)
    return annonce
