# -*- coding: utf-8 -*-
"""Pilotage du bot par messages Telegram.

A chaque run, AVANT de scraper : on lit getUpdates (offset persiste en base),
on execute les commandes, on confirme, puis le scraping part avec les filtres
a jour.
"""

import html
import json
import logging
import re
from datetime import datetime, timedelta, timezone

import config
import filtres as F
import geo
import notifier

log = logging.getLogger("commandes")

COMMANDES_TELEGRAM = [
    ("start", "Accueil et liste des commandes"),
    ("filtres", "Afficher les filtres actifs"),
    ("reset_filtres", "Remettre tous les filtres a zero"),
    ("whoami", "Afficher mon chat_id"),
    ("chambres", "Nombre de chambres min (ex: 3 ou 3-5 ou off)"),
    ("surface", "Surface habitable minimum en m2"),
    ("terrain", "Terrain minimum en m2"),
    ("bouquet_max", "Bouquet maximum en euros"),
    ("rente_max", "Rente mensuelle maximum en euros"),
    ("prix_max", "Prix total maximum en euros"),
    ("peb", "PEB minimum (A a G)"),
    ("type", "maison | appartement | tous"),
    ("viager", "libre | occupe | tous"),
    ("jardin", "oui | non"),
    ("garage", "oui | non"),
    ("age_max", "Age maximum du vendeur"),
    ("exclure", "Mots a rejeter, separes par des virgules"),
    ("cp", "Restreindre a des codes postaux"),
    ("commune", "Restreindre a des communes (FR ou NL)"),
    ("zone", "Afficher la zone active (zone reset pour tout remettre)"),
    ("rayon", "Recalculer la zone dans N km autour de Bruxelles"),
    ("silence", "Suspendre les notifications N heures"),
    ("resume", "Reprendre les notifications"),
    ("max", "Plafond de notifications par run"),
    ("suite", "Envoyer les annonces mises en attente"),
    ("historique", "Les 10 annonces les plus recentes"),
    ("test", "Scan immediat sans rien marquer comme vu"),
    ("stats", "Etat de la base et des sources"),
]

AIDE = """🏡 <b>Veille viager — Bruxelles et peripherie</b>

<b>Filtres</b>
/chambres 3 · /chambres 3-5 · /chambres off
/surface 120 — habitable minimum
/terrain 300 — terrain minimum
/bouquet_max 150000 · /rente_max 900 · /prix_max 400000
/peb C — PEB minimum
/type maison | appartement | tous
/viager libre | occupe | tous
/jardin oui · /garage oui
/age_max 80 — age max du vendeur si mentionne
/exclure travaux,rez — rejette ces mots

<b>Zone</b>
/cp 1000,1180,1700
/commune Uccle,Dilbeek — accepte FR et NL
/rayon 15 — resserre la zone a 15 km autour de Bruxelles
/zone — zone active · /zone reset — tout remettre

<b>Contrôle</b>
/filtres · /reset_filtres · /whoami
/silence 24 · /resume · /max 5
/suite · /historique · /test · /stats

Un filtre non defini ne restreint rien. Une donnee absente d'une annonce ne la
fait jamais rejeter : elle passe avec la mention ⚠️."""


# --------------------------------------------------------------- helpers ----
def _entier(s):
    m = re.fullmatch(r"\s*(\d[\d\s.]*)\s*", s or "")
    return int(re.sub(r"[\s.]", "", m.group(1))) if m else None


def _oui_non(s):
    s = (s or "").strip().lower()
    if s in ("oui", "yes", "ja", "1", "on", "true"):
        return True
    if s in ("non", "no", "nee", "0", "off", "false"):
        return False
    return None


def _horodatage_futur(heures):
    return (datetime.now(timezone.utc) + timedelta(hours=heures)).isoformat(timespec="seconds")


def silence_actif(bdd):
    jusqua = bdd.get_meta("silence_jusqua")
    if not jusqua:
        return False
    try:
        return datetime.fromisoformat(jusqua) > datetime.now(timezone.utc)
    except Exception:
        return False


def zone_active(bdd):
    f = bdd.filtres()
    return f.get("zone_cps") or list(config.CODES_POSTAUX)


# ------------------------------------------------------------- traitement ---
class Resultat:
    """Actions demandees par l'utilisateur pendant ce run."""

    def __init__(self):
        self.test = False
        self.suite = False
        self.historique = False
        self.stats = False
        self.envoyer_stock = False
        self.filtres_modifies = False


def traiter(bdd, tg):
    res = Resultat()
    if not tg.token:
        return res

    autorises = set(config.chat_ids())
    offset = bdd.get_meta("tg_offset")
    updates = tg.updates(int(offset) + 1 if offset else None)
    if not updates:
        return res

    dernier = offset
    for upd in updates:
        dernier = upd.get("update_id", dernier)
        try:
            if "callback_query" in upd:
                _callback(bdd, tg, upd["callback_query"], autorises, res)
            elif "message" in upd:
                _message(bdd, tg, upd["message"], autorises, res)
        except Exception as e:
            log.exception("commande ignoree : %s", e)
    if dernier is not None:
        bdd.set_meta("tg_offset", dernier)
    return res


def _confirmer(tg, texte):
    """Toute confirmation part vers TOUS les destinataires : chacun sait ou on en est."""
    tg.envoyer(texte)


def _message(bdd, tg, msg, autorises, res):
    chat_id = str((msg.get("chat") or {}).get("id", ""))
    texte = (msg.get("text") or "").strip()
    if not texte.startswith("/"):
        return
    if autorises and chat_id not in autorises:
        # /whoami reste utile pour s'ajouter soi-meme, mais rien d'autre ne passe
        if texte.lower().startswith("/whoami"):
            tg.envoyer("Ton chat_id : <code>%s</code>\nAjoute-le au secret "
                       "TELEGRAM_CHAT_ID pour recevoir les annonces." % chat_id,
                       cibles=[chat_id])
        else:
            log.warning("message ignore, chat_id non autorise : %s", chat_id)
        return

    m = re.match(r"^/([a-z_]+)(?:@\w+)?\s*(.*)$", texte, re.I | re.S)
    if not m:
        return
    cmd, arg = m.group(1).lower(), m.group(2).strip()
    avant = bdd.filtres()
    reponse = _executer(bdd, tg, cmd, arg, chat_id, res)
    if reponse:
        _confirmer(tg, reponse)
    apres = bdd.filtres()
    if apres != avant:
        res.filtres_modifies = True
        _proposer_stock(bdd, tg, avant, apres)


def _executer(bdd, tg, cmd, arg, chat_id, res):
    f = bdd.filtres()

    # ------------------------------------------------------------ infos ----
    if cmd in ("start", "help", "aide"):
        return AIDE
    if cmd == "whoami":
        tg.envoyer("Ton chat_id : <code>%s</code>" % chat_id, cibles=[chat_id])
        return None
    if cmd == "filtres":
        tg.envoyer("<b>Filtres actifs</b>\n" + F.resume(f, config.CODES_POSTAUX),
                   clavier=_clavier_filtres(f))
        return None
    if cmd == "reset_filtres":
        bdd.reset_filtres()
        return "♻️ Tous les filtres sont remis a zero. Zone complete, aucune restriction."

    # --------------------------------------------------------- numeriques --
    numeriques = {
        "surface": ("surface_min", "Surface minimum", "m²"),
        "terrain": ("terrain_min", "Terrain minimum", "m²"),
        "bouquet_max": ("bouquet_max", "Bouquet maximum", "€"),
        "rente_max": ("rente_max", "Rente maximum", "€/mois"),
        "prix_max": ("prix_max", "Prix maximum", "€"),
        "age_max": ("age_max", "Age maximum du vendeur", "ans"),
        "max": ("max_notif", "Plafond de notifications par run", ""),
    }
    if cmd in numeriques:
        cle, libelle, unite = numeriques[cmd]
        if arg.lower() in ("off", "reset", ""):
            bdd.del_filtre(cle)
            return "✅ %s : filtre desactive." % libelle
        v = _entier(arg)
        if v is None:
            return "❌ Valeur invalide : <code>%s</code>. Exemple : <code>/%s 120</code>" % (
                html.escape(arg), cmd)
        bdd.set_filtre(cle, v)
        return "✅ %s : <b>%s %s</b>" % (libelle, v, unite)

    if cmd == "chambres":
        if arg.lower() in ("off", "reset", ""):
            bdd.del_filtre("chambres_min")
            bdd.del_filtre("chambres_max")
            return "✅ Filtre chambres desactive."
        m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", arg)
        if m:
            lo, hi = int(m.group(1)), int(m.group(2))
            if lo > hi:
                lo, hi = hi, lo
            bdd.set_filtre("chambres_min", lo)
            bdd.set_filtre("chambres_max", hi)
            return "✅ Chambres : entre <b>%d et %d</b>" % (lo, hi)
        v = _entier(arg)
        if v is None:
            return "❌ Valeur invalide. Exemples : <code>/chambres 3</code>, " \
                   "<code>/chambres 3-5</code>, <code>/chambres off</code>"
        bdd.set_filtre("chambres_min", v)
        bdd.del_filtre("chambres_max")
        return "✅ Chambres : <b>%d minimum</b>" % v

    if cmd == "peb":
        v = arg.strip().upper()
        if v in ("OFF", "RESET", ""):
            bdd.del_filtre("peb_min")
            return "✅ Filtre PEB desactive."
        if v not in list("ABCDEFG"):
            return "❌ PEB invalide : <code>%s</code>. Attendu : A a G." % html.escape(arg)
        bdd.set_filtre("peb_min", v)
        return "✅ PEB minimum : <b>%s</b>" % v

    if cmd == "type":
        v = geo.norm(arg)
        table = {"maison": "maison", "huis": "maison", "woning": "maison",
                 "appartement": "appartement", "appart": "appartement",
                 "appt": "appartement", "flat": "appartement",
                 "tous": "tous", "all": "tous", "alles": "tous", "": "tous"}
        if v not in table:
            return "❌ Valeur invalide. Attendu : <code>maison</code>, " \
                   "<code>appartement</code> ou <code>tous</code>."
        if table[v] == "tous":
            bdd.del_filtre("type_bien")
            return "✅ Type de bien : <b>tous</b>"
        bdd.set_filtre("type_bien", table[v])
        return "✅ Type de bien : <b>%s</b>" % table[v]

    if cmd == "viager":
        v = geo.norm(arg)
        table = {"libre": "libre", "vrij": "libre", "occupe": "occupe", "bezet": "occupe",
                 "nue propriete": "nue-propriete", "blote eigendom": "nue-propriete",
                 "tous": "tous", "all": "tous", "": "tous"}
        if v not in table:
            return "❌ Valeur invalide. Attendu : <code>libre</code>, " \
                   "<code>occupe</code> ou <code>tous</code>."
        if table[v] == "tous":
            bdd.del_filtre("type_viager")
            return "✅ Type de viager : <b>tous</b>"
        bdd.set_filtre("type_viager", table[v])
        return "✅ Type de viager : <b>%s</b>" % table[v]

    if cmd in ("jardin", "garage"):
        v = _oui_non(arg)
        if v is None:
            return "❌ Attendu : <code>/%s oui</code> ou <code>/%s non</code>" % (cmd, cmd)
        if v:
            bdd.set_filtre(cmd, True)
            return "✅ %s obligatoire." % cmd.capitalize()
        bdd.del_filtre(cmd)
        return "✅ %s : plus de restriction." % cmd.capitalize()

    if cmd == "exclure":
        if arg.lower() in ("off", "reset", ""):
            bdd.del_filtre("exclure")
            return "✅ Plus aucun mot exclu."
        mots = [m.strip() for m in arg.split(",") if m.strip()]
        bdd.set_filtre("exclure", mots)
        return "✅ Mots exclus : <b>%s</b>" % html.escape(", ".join(mots))

    # -------------------------------------------------------------- zone ---
    if cmd == "cp":
        if arg.lower() in ("reset", "off", ""):
            bdd.del_filtre("zone_cps")
            return "✅ Zone : liste complete retablie (%d codes postaux)." % len(config.CODES_POSTAUX)
        cps = [c.strip() for c in re.split(r"[,\s]+", arg) if c.strip()]
        valides = [c for c in cps if re.fullmatch(r"[1-9]\d{3}", c)]
        inconnus = [c for c in cps if c not in valides]
        if not valides:
            return "❌ Aucun code postal valide dans <code>%s</code>." % html.escape(arg)
        bdd.set_filtre("zone_cps", valides)
        msg = "✅ Zone : <b>%d code(s) postal(aux)</b>\n%s" % (
            len(valides), ", ".join("%s %s" % (c, geo.nom_commune(c)) for c in valides))
        if inconnus:
            msg += "\n⚠️ Ignore : %s" % html.escape(", ".join(inconnus))
        return msg

    if cmd == "commune":
        if arg.lower() in ("reset", "off", ""):
            bdd.del_filtre("zone_cps")
            return "✅ Zone : liste complete retablie."
        cps, inconnus = geo.resoudre_saisie_communes(arg)
        if not cps:
            return "❌ Commune(s) non reconnue(s) : <code>%s</code>\nEssaie le nom FR ou NL " \
                   "exact, ex : <code>/commune Uccle,Dilbeek</code>" % html.escape(arg)
        bdd.set_filtre("zone_cps", cps)
        msg = "✅ Zone : <b>%s</b>" % ", ".join("%s (%s)" % (geo.nom_commune(c), c) for c in cps)
        if inconnus:
            msg += "\n⚠️ Non reconnu : %s" % html.escape(", ".join(inconnus))
        return msg

    if cmd == "zone":
        if arg.lower() in ("reset", "off"):
            bdd.del_filtre("zone_cps")
            return "✅ Zone : liste complete retablie (%d codes postaux)." % len(config.CODES_POSTAUX)
        z = zone_active(bdd)
        lignes = ["%s — %s" % (c, geo.nom_commune(c) or "?") for c in sorted(z)]
        entete = "📍 <b>Zone active : %d communes</b>%s\n" % (
            len(z), "" if bdd.filtres().get("zone_cps") else " (liste complete)")
        return entete + "\n".join(lignes)

    if cmd == "rayon":
        km = _entier(arg)
        if km is None or not (1 <= km <= 60):
            return "❌ Attendu : <code>/rayon 15</code> (entre 1 et 60 km)."
        cps = geo.cps_dans_rayon(km)
        if not cps:
            return "❌ Aucune commune connue dans ce rayon."
        bdd.set_filtre("zone_cps", cps)
        return "✅ Zone recalculee : <b>%d communes</b> dans %d km autour de Bruxelles.\n%s" % (
            len(cps), km, ", ".join(geo.nom_commune(c) for c in cps))

    # ---------------------------------------------------------- controle ---
    if cmd == "silence":
        h = _entier(arg) or 24
        bdd.set_meta("silence_jusqua", _horodatage_futur(h))
        return "🔕 Notifications suspendues <b>%d h</b>. Le scraping continue, tout est " \
               "stocke. /resume pour reprendre." % h
    if cmd == "resume":
        bdd.del_meta("silence_jusqua")
        return "🔔 Notifications reprises."
    if cmd == "suite":
        res.suite = True
        return None
    if cmd == "historique":
        res.historique = True
        return None
    if cmd == "test":
        res.test = True
        return "🧪 Scan de test lance : je montre ce qui passerait le filtre, sans rien " \
               "marquer comme vu."
    if cmd == "stats":
        res.stats = True
        return None

    return "❓ Commande inconnue : <code>/%s</code>\n\n%s" % (html.escape(cmd), AIDE)


# ------------------------------------------------------- clavier inline -----
def _clavier_filtres(f):
    def etiq(libelle, cle, valeur):
        actif = "✅ " if f.get(cle) == valeur or (valeur is True and f.get(cle)) else ""
        return {"text": actif + libelle, "callback_data": "f:%s:%s" % (cle, valeur)}

    return [
        [etiq("Maison", "type_bien", "maison"),
         etiq("Appartement", "type_bien", "appartement"),
         {"text": "Tous", "callback_data": "f:type_bien:tous"}],
        [etiq("Viager libre", "type_viager", "libre"),
         etiq("Viager occupé", "type_viager", "occupe"),
         {"text": "Tous", "callback_data": "f:type_viager:tous"}],
        [etiq("Jardin", "jardin", True), etiq("Garage", "garage", True)],
        [{"text": "🔄 Tout remettre a zero", "callback_data": "f:reset:1"}],
    ]


def _callback(bdd, tg, cq, autorises, res):
    chat_id = str(((cq.get("message") or {}).get("chat") or {}).get("id", ""))
    data = cq.get("data") or ""
    if autorises and chat_id not in autorises:
        tg.repondre_callback(cq.get("id"), "Non autorise")
        return

    avant = bdd.filtres()
    if data.startswith("stock:"):
        if data.endswith(":oui"):
            res.envoyer_stock = True
            tg.repondre_callback(cq.get("id"), "Envoi en cours")
        else:
            bdd.del_meta("stock_propose")
            tg.repondre_callback(cq.get("id"), "Ignore")
            _confirmer(tg, "👍 Annonces deja en base laissees de cote.")
        return

    if data.startswith("f:"):
        _, cle, valeur = data.split(":", 2)
        if cle == "reset":
            bdd.reset_filtres()
            tg.repondre_callback(cq.get("id"), "Filtres remis a zero")
            _confirmer(tg, "♻️ Tous les filtres sont remis a zero.")
        elif valeur in ("tous", "True") and cle in ("type_bien", "type_viager"):
            bdd.del_filtre(cle)
            tg.repondre_callback(cq.get("id"), "OK")
            _confirmer(tg, "✅ %s : tous" % cle.replace("_", " "))
        elif valeur == "True":
            if bdd.filtres().get(cle):
                bdd.del_filtre(cle)
                _confirmer(tg, "✅ %s : plus de restriction" % cle)
            else:
                bdd.set_filtre(cle, True)
                _confirmer(tg, "✅ %s obligatoire" % cle)
            tg.repondre_callback(cq.get("id"), "OK")
        else:
            bdd.set_filtre(cle, valeur)
            tg.repondre_callback(cq.get("id"), "OK")
            _confirmer(tg, "✅ %s : <b>%s</b>" % (cle.replace("_", " "), valeur))

        apres = bdd.filtres()
        if apres != avant:
            res.filtres_modifies = True
            _proposer_stock(bdd, tg, avant, apres)


# ------------------------------------------- proposition du stock existant --
def _proposer_stock(bdd, tg, avant, apres):
    """Si un filtre est assoupli, propose d'envoyer ce qui dort deja en base."""
    rows = bdd.cx.execute("SELECT * FROM annonces WHERE notifie=0").fetchall()
    eligibles = []
    for r in rows:
        ok_apres, _ = F.evaluer(r, apres)
        ok_avant, _ = F.evaluer(r, avant)
        if ok_apres and not ok_avant:
            eligibles.append(r["id_hash"])
    if not eligibles:
        return
    bdd.set_meta("stock_propose", json.dumps(eligibles))
    tg.envoyer(
        "📦 <b>%d annonce(s) deja en base</b> correspondent maintenant a tes criteres.\n"
        "Je te les envoie ?" % len(eligibles),
        clavier=[[{"text": "Oui", "callback_data": "stock:oui"},
                  {"text": "Non", "callback_data": "stock:non"}]],
    )


def envoyer_stock(bdd, tg):
    brut = bdd.get_meta("stock_propose")
    if not brut:
        return 0
    try:
        ids = json.loads(brut)
    except Exception:
        ids = []
    bdd.del_meta("stock_propose")
    n = 0
    for id_hash in ids[:50]:
        r = bdd.par_id(id_hash)
        if not r:
            continue
        tg.envoyer(notifier.formater(r))
        bdd.marquer_notifie(id_hash)
        n += 1
    return n
