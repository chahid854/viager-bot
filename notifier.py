# -*- coding: utf-8 -*-
"""Mise en forme des messages Telegram."""

import html
import json

LIBELLE_VIAGER = {
    "occupe": "Viager occupé",
    "libre": "Viager libre",
    "nue-propriete": "Nue-propriété",
    "vente-a-terme": "Vente à terme",
    "inconnu": "Viager (type non précisé)",
}

LIBELLE_BIEN = {
    "maison": "Maison", "appartement": "Appartement",
    "terrain": "Terrain", "immeuble": "Immeuble",
}


def _g(obj, cle):
    if hasattr(obj, cle):
        return getattr(obj, cle)
    try:
        return obj[cle]
    except Exception:
        return None


def euros(v):
    return "{:,}".format(int(v)).replace(",", ".") + " €"


def formater(obj, avertissements=None, baisse=None):
    """baisse = (ancien_prix, nouveau_prix) pour une notification de baisse."""
    titre = html.escape((_g(obj, "titre") or "Annonce viager").strip())[:150]
    lignes = []

    if baisse:
        ancien, nouveau = baisse
        pct = (ancien - nouveau) / ancien * 100 if ancien else 0
        lignes.append("📉 <b>BAISSE DE PRIX</b> — %s → %s (-%.1f %%)"
                      % (euros(ancien), euros(nouveau), pct))

    lignes.append("🏡 <b>%s</b>" % titre)

    commune = _g(obj, "commune") or ""
    cp = _g(obj, "code_postal") or ""
    if commune or cp:
        loc = "%s (%s)" % (html.escape(commune), cp) if (commune and cp) else html.escape(commune or cp)
        lignes.append("📍 %s" % loc)

    bouquet, rente, prix = _g(obj, "bouquet"), _g(obj, "rente"), _g(obj, "prix")
    if bouquet or rente:
        bits = []
        bits.append("Bouquet : %s" % (euros(bouquet) if bouquet else "n.c."))
        bits.append("Rente : %s/mois" % (euros(rente) if rente else "n.c."))
        lignes.append("💰 %s" % " | ".join(bits))
    elif prix:
        lignes.append("💰 Prix affiché : %s" % euros(prix))
    else:
        lignes.append("💰 Prix non communiqué")

    tv = _g(obj, "type_viager")
    tb = _g(obj, "type_bien")
    ligne_type = " · ".join(filter(None, [LIBELLE_BIEN.get(tb), LIBELLE_VIAGER.get(tv)]))
    if ligne_type:
        lignes.append("🏠 %s" % ligne_type)

    detail = []
    ch, surf, terr = _g(obj, "chambres"), _g(obj, "surface"), _g(obj, "terrain")
    if ch:
        detail.append("🛏 %d chambre%s" % (ch, "s" if ch > 1 else ""))
    if surf:
        detail.append("📐 %d m²" % surf)
    if terr:
        detail.append("🌳 terrain %d m²" % terr)
    if detail:
        lignes.append(" · ".join(detail))

    peb = _g(obj, "peb")
    if peb:
        lignes.append("⚡ PEB %s" % peb)

    age = _g(obj, "age_vendeur")
    if age:
        lignes.append("👤 Vendeur ~%d ans" % age)

    url = _g(obj, "url_principale") or _g(obj, "url") or ""
    if url:
        # L'adresse complete plutot qu'un "Voir l'annonce" : on veut voir sur
        # quel site on atterrit, et pouvoir copier le lien sans l'ouvrir.
        lignes.append('🔗 <a href="%s">%s</a>'
                      % (html.escape(url, quote=True), html.escape(url)))

    srcs = _g(obj, "sources")
    if isinstance(srcs, str):
        try:
            srcs = json.loads(srcs)
        except Exception:
            srcs = [srcs]
    if not srcs:
        s = _g(obj, "source")
        srcs = [s] if s else []
    if srcs:
        lignes.append("🏷 %s" % html.escape(", ".join(srcs)))

    av = list(avertissements or [])
    stockes = _g(obj, "avertissements")
    if isinstance(stockes, str):
        try:
            stockes = json.loads(stockes)
        except Exception:
            stockes = []
    for a in (stockes or []):
        if a not in av:
            av.append(a)
    av = [a for a in av if a.startswith("⚠️")]
    if av:
        lignes.append("\n" + "\n".join(html.escape(a) for a in av))

    return "\n".join(lignes)
