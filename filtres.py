# -*- coding: utf-8 -*-
"""Filtres de NOTIFICATION.

Tout ce qui est trouve va en base ; les filtres decident seulement de ce qui
part en Telegram. Une donnee absente ne fait jamais rejeter une annonce :
mieux vaut un faux positif qu'une occasion ratee.
"""

import geo
from parsing import PEB_ORDRE

DEFAUTS_ZONE = None  # None = zone complete de config.CODES_POSTAUX


def _get(obj, cle):
    """Lit indifferemment une dataclass Annonce ou une ligne sqlite3.Row."""
    if hasattr(obj, cle):
        return getattr(obj, cle)
    try:
        return obj[cle]
    except Exception:
        return None


def evaluer(obj, f):
    """Retourne (passe, avertissements). f = dict des filtres actifs."""
    av = []

    def manquant(message):
        if message not in av:
            av.append("⚠️ " + message)

    # -- chambres --------------------------------------------------------
    ch = _get(obj, "chambres")
    if "chambres_min" in f or "chambres_max" in f:
        if ch is None:
            manquant("nombre de chambres inconnu")
        else:
            if "chambres_min" in f and ch < f["chambres_min"]:
                return False, av
            if "chambres_max" in f and ch > f["chambres_max"]:
                return False, av

    # -- surface / terrain ----------------------------------------------
    for cle, champ, message in (("surface_min", "surface", "surface inconnue"),
                                ("terrain_min", "terrain", "surface du terrain inconnue")):
        if cle in f:
            v = _get(obj, champ)
            if v is None:
                manquant(message)
            elif v < f[cle]:
                return False, av

    # -- argent ----------------------------------------------------------
    bouquet = _get(obj, "bouquet")
    if "bouquet_max" in f:
        if bouquet is None:
            manquant("bouquet inconnu")
        elif bouquet > f["bouquet_max"]:
            return False, av

    rente = _get(obj, "rente")
    if "rente_max" in f:
        if rente is None:
            manquant("rente inconnue")
        elif rente > f["rente_max"]:
            return False, av

    prix = _get(obj, "prix")
    if "prix_max" in f:
        reference = prix if prix is not None else bouquet
        if reference is None:
            manquant("prix inconnu")
        elif reference > f["prix_max"]:
            return False, av

    # -- PEB -------------------------------------------------------------
    if "peb_min" in f:
        p = (_get(obj, "peb") or "").upper()
        if p not in PEB_ORDRE:
            manquant("PEB inconnu")
        elif PEB_ORDRE[p] > PEB_ORDRE[f["peb_min"].upper()]:
            return False, av

    # -- types -----------------------------------------------------------
    if f.get("type_bien") and f["type_bien"] != "tous":
        tb = _get(obj, "type_bien")
        if tb is None:
            manquant("type de bien inconnu")
        elif tb != f["type_bien"]:
            return False, av

    if f.get("type_viager") and f["type_viager"] != "tous":
        tv = _get(obj, "type_viager")
        if tv in (None, "inconnu"):
            manquant("viager libre ou occupe non precise")
        elif tv != f["type_viager"]:
            return False, av

    # -- equipements -----------------------------------------------------
    for cle in ("jardin", "garage"):
        if f.get(cle):
            v = _get(obj, cle)
            if v is None:
                manquant("presence d'un %s non precisee" % cle)
            elif not v:
                return False, av

    # -- age du vendeur --------------------------------------------------
    if "age_max" in f:
        a = _get(obj, "age_vendeur")
        if a is None:
            manquant("age du vendeur non mentionne")
        elif a > f["age_max"]:
            return False, av

    # -- mots exclus -----------------------------------------------------
    exclus = f.get("exclure") or []
    if exclus:
        texte = geo.norm(" ".join(str(_get(obj, c) or "") for c in ("titre", "description", "commune")))
        for mot in exclus:
            m = geo.norm(mot)
            if m and m in texte:
                return False, av

    # -- zone ------------------------------------------------------------
    zone = f.get("zone_cps")
    if zone:
        cp = _get(obj, "code_postal")
        if cp and cp not in zone:
            return False, av

    return True, av


def resume(f, zone_par_defaut):
    """Texte HTML des filtres actifs, pour /filtres."""
    if not f:
        return "Aucun filtre actif : tout ce qui est trouve dans la zone est notifie."
    lignes = []
    libelles = [
        ("chambres_min", "Chambres min"), ("chambres_max", "Chambres max"),
        ("surface_min", "Surface min (m²)"), ("terrain_min", "Terrain min (m²)"),
        ("bouquet_max", "Bouquet max (€)"), ("rente_max", "Rente max (€/mois)"),
        ("prix_max", "Prix max (€)"), ("peb_min", "PEB minimum"),
        ("type_bien", "Type de bien"), ("type_viager", "Type de viager"),
        ("jardin", "Jardin obligatoire"), ("garage", "Garage obligatoire"),
        ("age_max", "Age max du vendeur"),
    ]
    for cle, lib in libelles:
        if cle in f:
            v = f[cle]
            v = "oui" if v is True else ("non" if v is False else v)
            lignes.append("• %s : <b>%s</b>" % (lib, v))
    if f.get("exclure"):
        lignes.append("• Mots exclus : <b>%s</b>" % ", ".join(f["exclure"]))
    zone = f.get("zone_cps")
    if zone:
        lignes.append("• Zone restreinte : <b>%d communes</b> (/zone pour le detail)" % len(zone))
    else:
        lignes.append("• Zone : <b>complete</b> (%d codes postaux)" % len(zone_par_defaut))
    if f.get("max_notif"):
        lignes.append("• Plafond par run : <b>%s</b>" % f["max_notif"])
    return "\n".join(lignes) or "Aucun filtre actif."
