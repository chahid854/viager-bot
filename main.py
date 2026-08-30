# -*- coding: utf-8 -*-
"""Veille viager Bruxelles + peripherie — point d'entree.

Ordre d'un run :
  1. lire et executer les commandes Telegram (offset persiste)
  2. scraper toutes les sources actives, en parallele
  3. filtrer geographiquement, dedupliquer, stocker
  4. notifier les nouveautes et les baisses de prix, sous plafond
"""

import argparse
import json
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

import commandes
import config
import db as dbmod
import dedup
import details
import filtres as F
import geo
import notifier
import parsing
import scrapers
from telegram import Telegram

log = logging.getLogger("main")
FICHIER_AGENCES = "agences_decouvertes.json"


class Contexte:
    def __init__(self, zone_cps, budget=None):
        self.zone_cps = list(zone_cps)
        self.debut = time.time()
        self.budget = budget or config.BUDGET_SECONDES

    def temps_ecoule(self):
        return (time.time() - self.debut) > self.budget

    def restant(self):
        return max(0, self.budget - (time.time() - self.debut))


# ------------------------------------------------------------- scraping -----
def collecter(ctx, source_unique=None):
    """Lance toutes les sources en parallele. Un scraper qui plante n'arrete rien."""
    sources = config.sources_actives(source_unique)
    resultats, erreurs, comptes = [], [], {}

    with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as pool:
        futurs = {pool.submit(scrapers.fetch, s, ctx): s for s in sources}
        for fut in as_completed(futurs):
            s = futurs[fut]
            try:
                lot = fut.result() or []
            except Exception as e:
                log.exception("[%s] scraper en erreur", s["name"])
                erreurs.append("%s : %s" % (s["name"], str(e)[:120]))
                lot = []
            comptes[s["name"]] = len(lot)
            log.info("[%s] %d annonces brutes", s["name"], len(lot))
            for a in lot:
                a.kind = a.kind or s.get("kind", "portail")
                resultats.append(a)
    return resultats, comptes, erreurs


def retenir(annonce, zone_cps):
    """Complete les champs, ecarte les biens vendus, applique le filtre geo.

    True = a garder. Le tri "vendu" est fait ici, et pas dans chaque scraper,
    pour qu'il s'applique de la meme facon a toutes les sources : les agences
    laissent souvent leurs biens vendus en vitrine.
    """
    parsing.completer(annonce, config.MOTS_CLES)
    if parsing.est_vendu(annonce.titre, annonce.description):
        log.debug("[%s] deja vendu, ignore : %s", annonce.source, annonce.titre[:60])
        return False
    garde, cp, commune, avert = geo.resoudre(annonce, zone_cps)
    if cp:
        annonce.code_postal = cp
    if commune:
        annonce.commune = commune
    for a in avert:
        if a.startswith("⚠️"):
            annonce.avertissements.append(a)
        else:
            log.info("[%s] %s (%s)", annonce.source, a, annonce.url)
    return garde


# ------------------------------------------------------------ integration ---
def integrer(bdd, annonces, ecrire=True):
    """Dedup + stockage. Retourne (nouvelles, baisses) sous forme de lignes DB."""
    nouvelles, baisses = [], []
    for a in annonces:
        idh = dedup.id_hash(a)
        prix_ref = dedup.prix_reference(a)
        prio = dedup.priorite(a)
        existante = bdd.par_id(idh)

        if existante:
            ancien = existante["bouquet"] if existante["bouquet"] is not None else existante["prix"]
            if prix_ref and ancien and prix_ref != ancien:
                if ecrire:
                    bdd.maj_prix(idh, prix_ref)
                if prix_ref < ancien and _baisse_notifiable(existante, ancien, prix_ref):
                    baisses.append((bdd.par_id(idh) if ecrire else existante, ancien, prix_ref))
            elif ecrire:
                bdd.toucher(idh)
            continue

        # niveau 2 : empreinte tolerante (seaux voisins compris)
        fp = dedup.fingerprint(a)
        jumelle = bdd.par_fingerprints(dedup.fingerprints_candidats(a)) if fp else None
        # niveau 3 : fallback titre quand la surface manque
        if jumelle is None and not fp:
            jumelle = dedup.doublon_fuzzy(bdd, a)

        if jumelle is not None:
            log.info("doublon inter-sources : %s <- %s", jumelle["id_hash"][:10], a.source)
            if ecrire:
                bdd.ajouter_source(jumelle["id_hash"], a.source, a.url, prio)
                bdd.enrichir(jumelle["id_hash"], a)
            continue

        if ecrire:
            bdd.inserer(a, idh, fp, prio, prix_ref)
            nouvelles.append(bdd.par_id(idh))
        else:
            nouvelles.append(a)
    return nouvelles, baisses


def _baisse_notifiable(row, ancien, nouveau):
    ecart = ancien - nouveau
    if ecart < config.BAISSE_MIN_EUR and (ecart / ancien * 100.0) < config.BAISSE_MIN_PCT:
        return False
    derniere = row["last_drop_notif"]
    if derniere:
        try:
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(derniere)).days
            if age < config.BAISSE_COOLDOWN_JOURS:
                return False
        except Exception:
            pass
    return True


def enregistrer_agences(bdd, annonces):
    """Note les agences croisees sur les portails, a valider a la main.

    Immoweb ne publie pas le site de l'agence, seulement son nom : on enregistre
    alors une cle "agence://<nom>" pour que le nom apparaisse quand meme dans
    agences_decouvertes.json. Une recherche suffit ensuite pour trouver le site
    et l'ajouter comme source dans config.py.
    """
    for a in annonces:
        if a.agence_url and a.agence_url.startswith("http"):
            bdd.decouvrir_agence(a.agence_url, a.agence_nom or a.commune or "", a.source)
        elif a.agence_nom:
            bdd.decouvrir_agence("agence://" + a.agence_nom, a.agence_nom, a.source)
    lignes = [{"url": r["url"], "vue_sur": r["vue_sur"], "depuis": r["first_seen"],
               "validee": bool(r["validee"])} for r in bdd.agences()]
    if lignes:
        with open(FICHIER_AGENCES, "w", encoding="utf-8") as fh:
            json.dump(lignes, fh, ensure_ascii=False, indent=2)


# ---------------------------------------------------------- notifications ---
def notifier_lot(bdd, tg, nouvelles, baisses, f, silence):
    plafond = int(f.get("max_notif") or config.MAX_NOTIF_PAR_RUN)
    candidats = []

    for row in nouvelles:
        ok, av = F.evaluer(row, f)
        if ok:
            candidats.append((row, av, None))
    for row, ancien, nouveau in baisses:
        ok, av = F.evaluer(row, f)
        if ok:
            candidats.append((row, av, (ancien, nouveau)))

    # les annonces stockees pendant un silence ou un ancien plafond
    for row in bdd.non_notifiees():
        if any(row["id_hash"] == c[0]["id_hash"] for c in candidats):
            continue
        ok, av = F.evaluer(row, f)
        if ok:
            candidats.append((row, av, None))

    if not candidats:
        log.info("aucune nouveaute a notifier")
        return 0

    if silence:
        log.info("silence actif : %d annonce(s) gardees pour plus tard", len(candidats))
        return 0

    envoyes = 0
    for row, av, baisse in candidats[:plafond]:
        tg.envoyer(notifier.formater(row, av, baisse))
        bdd.marquer_notifie(row["id_hash"], baisse=bool(baisse))
        bdd.retirer_attente(row["id_hash"])
        envoyes += 1

    reste = candidats[plafond:]
    for row, _, _ in reste:
        bdd.mettre_en_attente(row["id_hash"])
        bdd.marquer_notifie(row["id_hash"])  # ne reviendra pas spammer au prochain run
    if reste:
        tg.envoyer("➕ <b>%d autre(s) annonce(s)</b> trouvee(s) mais non envoyees "
                   "(plafond de %d par run).\nTape /suite pour les voir." % (len(reste), plafond))
    return envoyes


def envoyer_attente(bdd, tg, limite):
    rows = bdd.file_attente(limite)
    if not rows:
        tg.envoyer("📭 Rien en attente.")
        return 0
    for r in rows:
        tg.envoyer(notifier.formater(r))
        bdd.retirer_attente(r["id_hash"])
    restant = bdd.taille_attente()
    if restant:
        tg.envoyer("➕ Encore %d en attente. /suite pour la suite." % restant)
    return len(rows)


def purger_vendus(bdd, dry_run=False):
    """Retire de la base les biens deja vendus qui y ont ete stockes.

    Utile apres coup : les annonces enregistrees avant que le tri "vendu"
    n'existe restent sinon dans /historique.
    """
    supprimes = []
    for r in bdd.toutes():
        if parsing.est_vendu(r["titre"] or "", r["description"] or ""):
            supprimes.append((r["id_hash"], (r["titre"] or "")[:70]))
    for id_hash, titre in supprimes:
        print("  vendu  %s" % titre)
        if not dry_run:
            bdd.supprimer(id_hash)
    return len(supprimes)


def envoyer_historique(bdd, tg, n=10):
    rows = bdd.recentes(n)
    if not rows:
        tg.envoyer("📭 La base est vide.")
        return
    tg.envoyer("🗂 <b>Les %d annonces les plus recentes</b>" % len(rows))
    for r in rows:
        tg.envoyer(notifier.formater(r))


def envoyer_stats(bdd, tg):
    total = bdd.compte()
    lignes = ["📊 <b>Etat de la veille</b>",
              "Annonces en base : <b>%d</b>" % total,
              "En attente d'envoi : <b>%d</b>" % bdd.taille_attente(),
              "Dernier run : <b>%s</b>" % (bdd.get_meta("dernier_run") or "jamais"),
              ""]
    stats = bdd.stats()
    if stats:
        lignes.append("<b>Par source</b> (dernier run / total)")
        for s in stats:
            muette = " ⚠️ muette depuis %d runs" % s["zero_streak"] if s["zero_streak"] >= 3 else ""
            lignes.append("• %s : %d / %d%s" % (s["source"], s["dernier_compte"],
                                                s["total_vu"], muette))
    actives = len(config.sources_actives())
    lignes.append("")
    lignes.append("Sources actives : <b>%d</b> sur %d" % (actives, len(config.SOURCES)))
    tg.envoyer("\n".join(lignes))


# ----------------------------------------------------------------- run -------
def executer(args):
    bdd = dbmod.Base()
    tg = Telegram(dry_run=args.dry_run or args.no_telegram)

    # commandes Telegram (jamais en dry-run : on ne consomme pas l'offset)
    res = commandes.Resultat()
    if not args.dry_run and not args.no_telegram and tg.token:
        if not bdd.get_meta("commandes_declarees"):
            tg.declarer_commandes(commandes.COMMANDES_TELEGRAM)
            bdd.set_meta("commandes_declarees", "1")
        res = commandes.traiter(bdd, tg)
        if res.envoyer_stock:
            n = commandes.envoyer_stock(bdd, tg)
            tg.envoyer("✅ %d annonce(s) envoyee(s) depuis la base." % n)
        if res.historique:
            envoyer_historique(bdd, tg)
        if res.stats:
            envoyer_stats(bdd, tg)
        if res.suite:
            f = bdd.filtres()
            envoyer_attente(bdd, tg, int(f.get("max_notif") or config.MAX_NOTIF_PAR_RUN))

    if args.commands_only:
        bdd.close()
        return 0

    # Garde-fou anti-doublon de passage. Les taches planifiees de GitHub
    # arrivent en retard, parfois de plus d'une heure, et le workflow declenche
    # volontairement deux heures UTC pour couvrir l'heure d'ete. Plutot que de
    # se fier a l'heure exacte, on refuse simplement de rescraper si la derniere
    # veille est trop recente : le premier des deux declenchements fait le
    # travail, le second repart aussitot.
    if args.min_interval:
        precedent = bdd.get_meta("dernier_run")
        if precedent:
            try:
                ecoule = (datetime.now(timezone.utc)
                          - datetime.fromisoformat(precedent)).total_seconds() / 3600.0
                if ecoule < args.min_interval:
                    log.info("derniere veille il y a %.1f h (< %.1f h) : on ne rescrape pas",
                             ecoule, args.min_interval)
                    bdd.close()
                    return 0
            except Exception:
                pass

    f = bdd.filtres()
    zone = commandes.zone_active(bdd)
    ctx = Contexte(zone)
    premier_run = bdd.vide()
    # --dry-run affiche exactement ce que /test montrerait, sans rien ecrire
    mode_test = res.test or args.dry_run

    log.info("zone : %d codes postaux | filtres : %s | premier run : %s",
             len(zone), sorted(f.keys()) or "aucun", premier_run)

    brutes, comptes, erreurs = collecter(ctx, args.source)
    log.info("total brut : %d annonces en %.0f s", len(brutes), time.time() - ctx.debut)

    gardees = [a for a in brutes if retenir(a, zone)]
    log.info("apres filtre geographique : %d annonces", len(gardees))

    # Les pages de liste donnent rarement le bouquet et la rente : on ouvre la
    # fiche complete des seules annonces encore inconnues (quelques-unes par
    # run), avant la dedup pour que l'empreinte travaille sur de bonnes donnees.
    inconnues = [a for a in gardees if not bdd.par_id(dedup.id_hash(a))]
    if inconnues and not ctx.temps_ecoule():
        details.enrichir(inconnues, ctx)
        for a in inconnues:
            garde, cp, commune, _ = geo.resoudre(a, zone)
            if cp and not a.code_postal:
                a.code_postal, a.commune = cp, commune

    # --- mode test : on montre, on n'ecrit rien -----------------------------
    if mode_test:
        vus = set()
        apercu = []
        for a in gardees:
            idh = dedup.id_hash(a)
            if idh in vus:
                continue
            vus.add(idh)
            ok, av = F.evaluer(a, f)
            if ok:
                deja = " (deja en base)" if bdd.par_id(idh) else ""
                apercu.append((a, av, deja))
        tg.envoyer("🧪 <b>Test</b> : %d annonce(s) passeraient le filtre sur %d trouvees "
                   "dans la zone (%d brutes). Rien n'a ete marque comme vu."
                   % (len(apercu), len(gardees), len(brutes)))
        for a, av, deja in apercu[:15]:
            tg.envoyer(notifier.formater(a, av) + (("\n" + deja) if deja else ""))
        if not args.dry_run:
            bdd.set_meta("dernier_run", dbmod.maintenant())
        bdd.close()
        return 0

    # --- integration --------------------------------------------------------
    nouvelles, baisses = integrer(bdd, gardees, ecrire=not args.dry_run)
    enregistrer_agences(bdd, gardees)

    for nom, n in comptes.items():
        streak = bdd.enregistrer_stat(nom, n)
        if streak >= config.ZERO_RUNS_ALERTE:
            row = [s for s in bdd.stats() if s["source"] == nom]
            if row and not row[0]["alerte_envoyee"]:
                tg.envoyer("🔧 <b>Source muette</b> : <code>%s</code> ne renvoie plus rien "
                           "depuis %d runs. Le site a probablement change de structure — "
                           "passe son flag <code>enabled</code> a False dans config.py en "
                           "attendant." % (nom, streak))
                bdd.marquer_alerte_source(nom)

    if erreurs:
        tg.envoyer("⚠️ <b>%d scraper(s) en erreur ce run</b>\n%s\n\nLes autres sources ont "
                   "tourne normalement." % (len(erreurs), "\n".join("• " + e for e in erreurs[:10])))

    # --- premier run : on n'inonde pas --------------------------------------
    if premier_run:
        if not args.dry_run:
            bdd.marquer_tout_vu()
        tg.envoyer(
            "🚀 <b>Initialisation</b>\n%d annonces trouvees dans la zone, toutes enregistrees "
            "comme deja vues.\nTu ne recevras desormais que les nouveautes.\n\n"
            "/historique pour voir les 10 plus recentes · /filtres pour regler tes criteres."
            % bdd.compte())
        bdd.set_meta("dernier_run", dbmod.maintenant())
        bdd.close()
        return 0

    silence = commandes.silence_actif(bdd)
    envoyes = notifier_lot(bdd, tg, nouvelles, baisses, f, silence)
    log.info("%d notification(s) envoyee(s) | %d nouvelles | %d baisses",
             envoyes, len(nouvelles), len(baisses))

    bdd.set_meta("dernier_run", dbmod.maintenant())
    bdd.close()
    return 0


def main():
    p = argparse.ArgumentParser(description="Veille viager Bruxelles + peripherie")
    p.add_argument("--dry-run", action="store_true",
                   help="affiche en console, n'envoie rien, n'ecrit rien en base")
    p.add_argument("--reset", action="store_true", help="vide la base et quitte")
    p.add_argument("--purge-vendus", action="store_true",
                   help="retire de la base les biens deja vendus, puis quitte")
    p.add_argument("--source", metavar="NOM", help="ne scrape qu'une seule source (debug)")
    p.add_argument("--min-interval", type=float, metavar="HEURES",
                   help="ne rien rescraper si la derniere veille date de moins "
                        "de N heures (absorbe les retards du cron GitHub)")
    p.add_argument("--commands-only", action="store_true",
                   help="traite seulement les commandes Telegram, sans scraper")
    p.add_argument("--no-telegram", action="store_true", help="scrape sans rien envoyer")
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args()

    # la console Windows est en cp1252 : sans ca, un emoji fait planter le run
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)-18s %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    if args.reset:
        dbmod.reset_base()
        print("Base %s supprimee." % config.DB_PATH)
        return 0

    if args.purge_vendus:
        bdd = dbmod.Base()
        n = purger_vendus(bdd, args.dry_run)
        total = bdd.compte()
        bdd.close()
        print("%d annonce(s) vendue(s) %s. Il reste %d annonce(s) en base."
              % (n, "detectee(s)" if args.dry_run else "supprimee(s)", total))
        return 0

    if args.source and args.source not in [s["name"] for s in config.SOURCES]:
        print("Source inconnue : %s" % args.source)
        print("Disponibles : %s" % ", ".join(s["name"] for s in config.SOURCES))
        return 2

    if not config.TELEGRAM_TOKEN and not (args.dry_run or args.no_telegram):
        print("TELEGRAM_TOKEN absent. Utilise --dry-run pour tester sans Telegram.")
        return 2

    return executer(args)


if __name__ == "__main__":
    sys.exit(main())
