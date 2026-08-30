# -*- coding: utf-8 -*-
"""Test du flux complet sans reseau : integration, dedup, notifications.

Verifie ce qui coute cher en cas de bug : recevoir deux fois la meme annonce,
ou etre inonde au premier run. `python test_flux.py`
"""

import os
import sys
import tempfile

os.environ["VIAGER_DB"] = os.path.join(tempfile.gettempdir(), "viager_flux.db")

import config
import db as dbmod
import main
from models import Annonce

echecs = []


def verifie(nom, condition, detail=""):
    print(("  ok   " if condition else "  ECHEC ") + nom + (" " + str(detail) if not condition else ""))
    if not condition:
        echecs.append(nom)


class TelegramFactice:
    """Enregistre les messages au lieu de les envoyer."""

    def __init__(self):
        self.messages = []
        self.token = ""
        self.dry_run = False

    def envoyer(self, texte, clavier=None, cibles=None, apercu=False):
        self.messages.append(texte)
        return True

    def vider(self):
        self.messages = []


CODES = ["1180", "1050", "1000", "1200", "1700", "1030", "1160", "1150", "1170",
         "1190", "1140", "1090", "1080", "1060", "1040", "1500", "1600", "1640",
         "1800", "1930", "3080", "1780", "1850", "1560", "1070"]


def annonce(i, source="viagerbel", bouquet=None, cp=None, surface=None, chambres=3):
    """Chaque i produit un bien franchement distinct des autres."""
    cp = cp or CODES[i % len(CODES)]
    bouquet = bouquet if bouquet is not None else 100000 + i * 25000
    surface = surface if surface is not None else 60 + i * 17
    return Annonce(source=source, url="https://exemple.be/bien/%d" % i, source_id=str(i),
                   titre="Maison en viager occupe numero %d" % i,
                   description="Belle maison en viager occupe. Bouquet et rente.",
                   localisation="%s Uccle" % cp, code_postal=cp, commune="Uccle",
                   bouquet=bouquet, rente=800, surface=surface, chambres=chambres,
                   type_bien="maison", type_viager="occupe", kind="agence")


dbmod.reset_base(os.environ["VIAGER_DB"])
bdd = dbmod.Base(os.environ["VIAGER_DB"])
tg = TelegramFactice()

print("\n== Run 1 : base vide ==")
lot1 = [annonce(i) for i in range(1, 6)]
nouvelles, baisses = main.integrer(bdd, lot1)
verifie("5 annonces inserees", len(nouvelles) == 5 and bdd.compte() == 5)
bdd.marquer_tout_vu()   # ce que fait main.executer au premier run
verifie("aucune notification individuelle au premier run", len(tg.messages) == 0)

print("\n== Run 2 : memes annonces ==")
tg.vider()
nouvelles, baisses = main.integrer(bdd, [annonce(i) for i in range(1, 6)])
verifie("aucune nouvelle", nouvelles == [])
verifie("aucune baisse", baisses == [])
envoyes = main.notifier_lot(bdd, tg, nouvelles, baisses, {}, False)
verifie("aucun message renvoye", envoyes == 0 and len(tg.messages) == 0)
verifie("toujours 5 en base", bdd.compte() == 5)

print("\n== Run 3 : la meme annonce vue sur une autre source ==")
tg.vider()
ailleurs = annonce(1, source="immoweb", bouquet=127000, surface=71)   # arrondis differents
ailleurs.source_id = "999"
ailleurs.kind = "portail_immoweb"
nouvelles, baisses = main.integrer(bdd, [ailleurs])
verifie("reconnue comme doublon", nouvelles == [] and bdd.compte() == 5)
row = bdd.par_id(main.dedup.id_hash(annonce(1)))
verifie("la source a ete ajoutee", "immoweb" in (row["sources"] or ""), row["sources"])
verifie("le lien reste celui de l'agence", row["url_principale"].startswith("https://exemple.be"))

print("\n== Run 4 : nouvelle annonce ==")
tg.vider()
neuve = annonce(42, bouquet=740000, surface=333)
nouvelles, baisses = main.integrer(bdd, [neuve])
verifie("1 nouvelle detectee", len(nouvelles) == 1)
envoyes = main.notifier_lot(bdd, tg, nouvelles, baisses, {}, False)
verifie("1 notification envoyee", envoyes == 1 and len(tg.messages) == 1)
verifie("message correctement forme", "🏡" in tg.messages[0] and "Uccle" in tg.messages[0])

print("\n== Run 5 : baisse de prix ==")
tg.vider()
baisse_faible = annonce(42, bouquet=739000, surface=333)     # -1000 EUR, -0,1 % : sous les seuils
nouvelles, baisses = main.integrer(bdd, [baisse_faible])
verifie("baisse sous le seuil ignoree", baisses == [])

baisse_forte = annonce(42, bouquet=700000, surface=333)      # -40 000 EUR
nouvelles, baisses = main.integrer(bdd, [baisse_forte])
verifie("baisse significative detectee", len(baisses) == 1)
envoyes = main.notifier_lot(bdd, tg, nouvelles, baisses, {}, False)
verifie("notification de baisse envoyee", envoyes == 1)
verifie("le message annonce la baisse", "BAISSE DE PRIX" in tg.messages[0], tg.messages[0][:60])

tg.vider()
encore = annonce(42, bouquet=650000, surface=333)
nouvelles, baisses = main.integrer(bdd, [encore])
verifie("2e baisse dans la semaine : pas de 2e message", baisses == [])

print("\n== Run 6 : plafond de notifications ==")
tg.vider()
lot = [annonce(100 + i) for i in range(20)]
nouvelles, baisses = main.integrer(bdd, lot)
verifie("20 nouvelles annonces", len(nouvelles) == 20)
envoyes = main.notifier_lot(bdd, tg, nouvelles, baisses, {}, False)
verifie("plafond respecte", envoyes == config.MAX_NOTIF_PAR_RUN, envoyes)
verifie("message de debordement", any("/suite" in m for m in tg.messages))
verifie("le reste est en file d'attente", bdd.taille_attente() == 5, bdd.taille_attente())

tg.vider()
n = main.envoyer_attente(bdd, tg, 15)
verifie("/suite envoie les 5 restantes", n == 5)
verifie("file videe", bdd.taille_attente() == 0)

print("\n== Run 7 : silence ==")
tg.vider()
lot = [annonce(300 + i) for i in range(3)]
nouvelles, baisses = main.integrer(bdd, lot)
envoyes = main.notifier_lot(bdd, tg, nouvelles, baisses, {}, True)   # silence actif
verifie("rien envoye pendant le silence", envoyes == 0 and len(tg.messages) == 0)
verifie("les annonces restent a notifier", len(bdd.non_notifiees()) == 3)

tg.vider()
envoyes = main.notifier_lot(bdd, tg, [], [], {}, False)   # /resume : plus de silence
verifie("elles partent une fois le silence leve", envoyes == 3)
verifie("plus rien en attente de notification", len(bdd.non_notifiees()) == 0)

print("\n== Run 8 : les filtres ne bloquent que la notification ==")
tg.vider()
petite = annonce(500, bouquet=63000, surface=45, chambres=1)
nouvelles, baisses = main.integrer(bdd, [petite])
avant = bdd.compte()
envoyes = main.notifier_lot(bdd, tg, nouvelles, baisses, {"chambres_min": 3}, False)
verifie("annonce filtree non notifiee", envoyes == 0)
verifie("mais bien stockee en base", bdd.compte() == avant)
verifie("elle reste candidate si le filtre change",
        any(r["id_hash"] == main.dedup.id_hash(petite) for r in bdd.non_notifiees()))

envoyes = main.notifier_lot(bdd, tg, [], [], {"chambres_min": 1}, False)
verifie("filtre assoupli : elle part", envoyes == 1)

bdd.close()
dbmod.reset_base(os.environ["VIAGER_DB"])

print("\n" + "=" * 50)
if echecs:
    print("%d test(s) en echec : %s" % (len(echecs), ", ".join(echecs)))
    sys.exit(1)
print("Flux complet valide.")
