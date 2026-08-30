# -*- coding: utf-8 -*-
"""Tests locaux, sans reseau. `python test_local.py`

Verifie la geo, le parsing, la dedup et les filtres — la partie du bot ou une
erreur silencieuse coute des annonces ratees ou du spam.
"""

import os
import sys
import tempfile

os.environ.setdefault("VIAGER_DB", os.path.join(tempfile.gettempdir(), "viager_test.db"))

import config
import db as dbmod
import dedup
import filtres as F
import geo
import parsing
from models import Annonce

echecs = []


def verifie(nom, condition, detail=""):
    if condition:
        print("  ok   %s" % nom)
    else:
        print("  ECHEC %s %s" % (nom, detail))
        echecs.append(nom)


print("\n== Normalisation et communes ==")
verifie("accents et tirets", geo.norm("Rhode-Saint-Genèse") == "rhode saint genese",
        geo.norm("Rhode-Saint-Genèse"))
verifie("St- = Saint-", geo.norm("Rhode-St-Genese") == geo.norm("Rhode-Saint-Genèse"))
verifie("Sint- = Saint-", geo.norm("Sint-Pieters-Leeuw") == "saint pieters leeuw")
verifie("NL reconnu", geo.resoudre_saisie_communes("Ukkel")[0] == ["1180"])
verifie("FR reconnu", geo.resoudre_saisie_communes("Uccle")[0] == ["1180"])
verifie("multi + inconnu", geo.resoudre_saisie_communes("Uccle,Dilbeek,Namur")
        == (["1180", "1700"], ["Namur"]))

print("\n== Matching geographique ==")
zone = config.CODES_POSTAUX


def loc(titre="", localisation="", description="", cp=None):
    return Annonce(source="t", url="http://x/1", titre=titre, localisation=localisation,
                   description=description, code_postal=cp)


garde, cp, com, av = geo.resoudre(loc(localisation="1180 Uccle"), zone)
verifie("CP + commune", garde and cp == "1180" and com == "Uccle")

garde, cp, com, av = geo.resoudre(loc(localisation="Dilbeek", titre="Maison en viager"), zone)
verifie("commune seule sans CP", garde and cp == "1700")

garde, cp, com, av = geo.resoudre(loc(localisation="Sint-Genesius-Rode"), zone)
verifie("commune NL seule", garde and cp == "1640")

garde, cp, com, av = geo.resoudre(loc(localisation="4000 Liege"), zone)
verifie("hors zone rejetee", not garde)

garde, cp, com, av = geo.resoudre(loc(localisation="1180 Uccle", description="proche de Halle"),
                                  zone)
verifie("CP prime sur le nom", cp == "1180")

garde, cp, com, av = geo.resoudre(
    loc(titre="Viager", description="Belle maison, grand lotissement, lot 3 disponible"), zone)
verifie("'lot 3' ne matche pas Lot", not garde, "cp=%s" % cp)

garde, cp, com, av = geo.resoudre(
    loc(titre="Viager occupe", description="Aux Halles Saint-Gery, superbe bien"), zone)
verifie("'Halles' ne matche pas Halle", cp != "1500", "cp=%s" % cp)

garde, cp, com, av = geo.resoudre(
    loc(titre="Viager occupe a Bruxelles", description="Bien en region bruxelloise"), zone)
verifie("Bruxelles sans commune -> garde avec avertissement",
        garde and any("verifier" in a for a in av))

garde, cp, com, av = geo.resoudre(loc(localisation="1500 Halle"), zone)
verifie("Halle dans le champ localisation", garde and cp == "1500")

print("\n== Rayon ==")
cps15 = geo.cps_dans_rayon(15)
verifie("Uccle dans 15 km", "1180" in cps15)
verifie("Zemst hors 15 km", "1980" not in cps15, str(len(cps15)))
verifie("rayon 5 plus petit que 15", len(geo.cps_dans_rayon(5)) < len(cps15))

print("\n== Parsing ==")
txt = ("Maison en viager occupe a Uccle. Bouquet : 120.000 € et rente de 950 €/mois. "
       "4 chambres, 180 m² habitables, terrain de 320 m². PEB : D. Jardin et garage. "
       "Vendeuse de 82 ans.")
verifie("bouquet", parsing.bouquet(txt) == 120000, str(parsing.bouquet(txt)))
verifie("rente", parsing.rente(txt) == 950, str(parsing.rente(txt)))
verifie("chambres", parsing.chambres(txt) == 4, str(parsing.chambres(txt)))
verifie("surface", parsing.surface(txt) == 180, str(parsing.surface(txt)))
verifie("terrain", parsing.terrain(txt) == 320, str(parsing.terrain(txt)))
verifie("peb", parsing.peb(txt) == "D", str(parsing.peb(txt)))
verifie("type bien", parsing.type_bien(txt) == "maison")
verifie("type viager", parsing.type_viager(txt) == "occupe")
verifie("jardin", parsing.jardin(txt) is True)
verifie("garage", parsing.garage(txt) is True)
verifie("age vendeur", parsing.age_vendeur(txt) == 82, str(parsing.age_vendeur(txt)))

nl = ("Huis te koop op lijfrente in Dilbeek. Boeket 95.000 euro, maandelijkse rente 700 EUR. "
      "3 slaapkamers, 145 m2 bewoonbaar, EPC C. Verkoper 78 jaar.")
verifie("NL bouquet", parsing.bouquet(nl) == 95000, str(parsing.bouquet(nl)))
verifie("NL chambres", parsing.chambres(nl) == 3, str(parsing.chambres(nl)))
verifie("NL surface", parsing.surface(nl) == 145, str(parsing.surface(nl)))
verifie("NL peb", parsing.peb(nl) == "C", str(parsing.peb(nl)))
verifie("NL type viager", parsing.type_viager(nl) == "inconnu", str(parsing.type_viager(nl)))
verifie("NL age", parsing.age_vendeur(nl) == 78, str(parsing.age_vendeur(nl)))

print("\n== Deduplication ==")
verifie("url normalisee", dedup.url_normalisee("https://WWW.Site.be/bien/12/?utm_source=x#a")
        == "https://site.be/bien/12", dedup.url_normalisee("https://WWW.Site.be/bien/12/?utm_source=x#a"))

a1 = Annonce(source="immoweb", url="https://immoweb.be/fr/annonce/1", source_id="1",
             code_postal="1180", surface=118, bouquet=121000, chambres=3)
a2 = Annonce(source="trovit", url="https://trovit.be/x/9", code_postal="1180",
             surface=120, bouquet=123000, chambres=3)
verifie("ids differents", dedup.id_hash(a1) != dedup.id_hash(a2))
verifie("seaux voisins couvrent 118 vs 120 m2",
        dedup.fingerprint(a1) in dedup.fingerprints_candidats(a2))

a3 = Annonce(source="x", url="u", code_postal="1180", surface=118, bouquet=145000, chambres=3)
verifie("prix trop different -> pas de doublon",
        dedup.fingerprint(a3) not in dedup.fingerprints_candidats(a1))
verifie("pas d'empreinte sans surface", dedup.fingerprint(
    Annonce(source="x", url="u", code_postal="1180", bouquet=100000)) is None)

dbmod.reset_base(os.environ["VIAGER_DB"])
bdd = dbmod.Base(os.environ["VIAGER_DB"])
bdd.inserer(a1, dedup.id_hash(a1), dedup.fingerprint(a1), 20, 121000)
verifie("insertion", bdd.compte() == 1)
verifie("retrouve malgre 118 vs 120 m2",
        bdd.par_fingerprints(dedup.fingerprints_candidats(a2)) is not None)
bdd.ajouter_source(dedup.id_hash(a1), "trovit", a2.url, 50)
row = bdd.par_id(dedup.id_hash(a1))
verifie("source ajoutee sans changer le lien", "trovit" in row["sources"]
        and row["url_principale"] == a1.url)
bdd.ajouter_source(dedup.id_hash(a1), "viagerbel", "https://viagerbel.be/bien/7", 10)
row = bdd.par_id(dedup.id_hash(a1))
verifie("lien agence prioritaire", row["url_principale"] == "https://viagerbel.be/bien/7")

a4 = Annonce(source="y", url="u4", titre="Belle maison de maitre a Uccle avec jardin",
             code_postal="1180", bouquet=120000)
bdd.inserer(a4, "hash4", None, 30, 120000)
a5 = Annonce(source="z", url="u5", titre="Maison de maitre avec jardin, Uccle",
             code_postal="1180", bouquet=122000)
verifie("fallback titre detecte le doublon", dedup.doublon_fuzzy(bdd, a5) is not None)

print("\n== Filtres ==")
bien = Annonce(source="t", url="u", chambres=4, surface=180, terrain=320, bouquet=120000,
               rente=950, prix=None, peb="D", type_bien="maison", type_viager="occupe",
               jardin=True, garage=True, age_vendeur=82, code_postal="1180",
               titre="Maison en viager", description="belle maison")
verifie("passe sans filtre", F.evaluer(bien, {})[0])
verifie("chambres min ok", F.evaluer(bien, {"chambres_min": 3})[0])
verifie("chambres min ko", not F.evaluer(bien, {"chambres_min": 5})[0])
verifie("plage chambres", not F.evaluer(bien, {"chambres_min": 1, "chambres_max": 3})[0])
verifie("bouquet max ko", not F.evaluer(bien, {"bouquet_max": 100000})[0])
verifie("rente max ok", F.evaluer(bien, {"rente_max": 1000})[0])
verifie("peb min C ko", not F.evaluer(bien, {"peb_min": "C"})[0])
verifie("peb min E ok", F.evaluer(bien, {"peb_min": "E"})[0])
verifie("type ko", not F.evaluer(bien, {"type_bien": "appartement"})[0])
verifie("viager libre ko", not F.evaluer(bien, {"type_viager": "libre"})[0])
verifie("zone ko", not F.evaluer(bien, {"zone_cps": ["1000"]})[0])
verifie("exclure", not F.evaluer(bien, {"exclure": ["belle"]})[0])
verifie("age max ko", not F.evaluer(bien, {"age_max": 75})[0])

incomplet = Annonce(source="t", url="u", titre="Viager a Uccle", code_postal="1180")
ok, av = F.evaluer(incomplet, {"surface_min": 120, "chambres_min": 3})
verifie("donnee absente ne rejette pas", ok)
verifie("avertissements produits", len(av) >= 2, str(av))

print("\n== Mise en forme ==")
import notifier
msg = notifier.formater(bien, ["⚠️ surface inconnue"])
verifie("html valide", "<b>" in msg and "🏡" in msg)
msg2 = notifier.formater(bien, [], (130000, 120000))
verifie("baisse de prix", "BAISSE DE PRIX" in msg2)

bdd.close()
dbmod.reset_base(os.environ["VIAGER_DB"])

print("\n%s" % ("=" * 50))
if echecs:
    print("%d test(s) en echec : %s" % (len(echecs), ", ".join(echecs)))
    sys.exit(1)
print("Tous les tests passent.")
