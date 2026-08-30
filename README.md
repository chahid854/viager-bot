# Veille viager — Bruxelles et périphérie

Bot personnel qui surveille les annonces de **viager / lijfrente** sur les
sources belges qui en publient vraiment, filtre sur Bruxelles + 20 km, mémorise
ce qu'il a déjà vu, et envoie les nouveautés sur Telegram. Il tourne 2 fois par
jour sur GitHub Actions.

41 sources sont déclarées, **12 sont actives** : les autres sont éteintes avec
la raison en commentaire dans `config.py` (domaine mort, pas de filtre viager,
catalogue en JavaScript…). Voir le §4, qui détaille chaque cas.

**Zéro euro** : aucune API payante, aucun proxy, aucun service tiers, pas de
carte bancaire. Uniquement l'API Bot Telegram (gratuite) et les minutes GitHub
Actions.

---

## 1. Installation en 10 minutes

### a. Créer le bot Telegram

1. Dans Telegram, ouvre une conversation avec **@BotFather**.
2. Envoie `/newbot`, choisis un nom (ex. `Veille Viager`) puis un identifiant
   finissant par `bot` (ex. `veille_viager_bxl_bot`).
3. BotFather répond avec un **token** du type
   `7123456789:AAF...`. C'est le secret `TELEGRAM_TOKEN`. Ne le mets jamais
   dans le code.

### b. Récupérer ton chat_id

**Méthode simple (destinataires individuels)**

1. Ouvre une conversation avec ton bot et envoie-lui `/start`.
   Un bot ne peut pas écrire le premier : sans ce message, rien n'arrivera.
2. Ouvre dans un navigateur :
   `https://api.telegram.org/bot<TON_TOKEN>/getUpdates`
3. Cherche `"chat":{"id":123456789`. Ce nombre est ton chat_id.

Une fois le bot en service, la commande `/whoami` renvoie directement le chat_id
de qui l'envoie — c'est le plus simple pour ajouter quelqu'un.

Plusieurs destinataires : sépare les ids par des virgules, sans espace.

```
TELEGRAM_CHAT_ID = 123456789,987654321
```

**Méthode groupe (tout le monde au même endroit)**

1. Crée un groupe Telegram, ajoute ton bot dedans.
2. Envoie n'importe quel message dans le groupe.
3. Ouvre `https://api.telegram.org/bot<TON_TOKEN>/getUpdates` et cherche
   `"chat":{"id":-1001234567890`. **L'id d'un groupe est négatif**, garde le
   signe moins.
4. Mets cet id seul dans `TELEGRAM_CHAT_ID`.

> Si `getUpdates` te renvoie une liste vide dans un groupe, désactive le mode
> "privacy" du bot : `/setprivacy` chez @BotFather → `Disable`. Sinon le bot ne
> voit que les messages qui commencent par `/`.

Les deux méthodes se combinent : `-1001234567890,123456789` envoie au groupe
**et** en privé.

### c. Configurer GitHub

1. Crée un dépôt (privé de préférence — la base contient ton historique de
   recherche) et pousse ce dossier.
2. `Settings` → `Secrets and variables` → `Actions` → `New repository secret` :
   - `TELEGRAM_TOKEN` = le token de BotFather
   - `TELEGRAM_CHAT_ID` = tes ids séparés par des virgules
3. `Settings` → `Actions` → `General` → `Workflow permissions` :
   coche **Read and write permissions** (le bot doit pouvoir committer sa base).
4. Onglet `Actions` → `Veille viager` → `Run workflow` pour un premier
   lancement manuel.

Le premier run n'envoie **aucune** annonce individuelle : il enregistre tout
comme « déjà vu » et envoie un seul message d'initialisation. À partir du
deuxième run, tu ne reçois que les nouveautés.

### d. En local (facultatif)

```bash
pip install -r requirements.txt

python main.py --dry-run              # affiche tout en console, n'écrit rien
python main.py --source viagerbel -v  # une seule source, en détail
python test_local.py                  # tests hors ligne : géo, parsing, dedup, filtres
python test_flux.py                   # tests hors ligne : dedup inter-sources, plafond,
                                      # baisses de prix, silence, premier run
```

Sous Windows PowerShell, pour un test avec envoi réel :

```powershell
$env:TELEGRAM_TOKEN="123:AAA..."; $env:TELEGRAM_CHAT_ID="123456789"
python main.py
```

---

## 2. Commandes Telegram

Tout se règle par message, sans toucher au code. Les réglages sont stockés dans
`seen.db` et survivent aux redéploiements.

| Commande | Effet |
|---|---|
| `/start` | Accueil et aide complète |
| `/filtres` | Filtres actifs + boutons de réglage |
| `/reset_filtres` | Tout remettre à zéro |
| `/whoami` | Renvoie ton chat_id |
| `/chambres 3` · `/chambres 3-5` · `/chambres off` | Nombre de chambres |
| `/surface 120` | Surface habitable minimum |
| `/terrain 300` | Terrain minimum |
| `/bouquet_max 150000` | Bouquet maximum |
| `/rente_max 900` | Rente mensuelle maximum |
| `/prix_max 400000` | Prix total / valeur vénale maximum |
| `/peb C` | PEB minimum (A→G) |
| `/type maison` | `maison` · `appartement` · `tous` |
| `/viager libre` | `libre` · `occupe` · `tous` |
| `/jardin oui` · `/garage oui` | Équipements obligatoires |
| `/age_max 80` | Âge maximum du vendeur, si mentionné |
| `/exclure travaux,rez` | Rejette les annonces contenant ces mots |
| `/cp 1000,1180,1700` | Restreint par code postal |
| `/commune Uccle,Dilbeek` | Restreint par nom (FR **ou** NL) |
| `/rayon 15` | Recalcule la zone dans N km autour de Bruxelles |
| `/zone` · `/zone reset` | Affiche / réinitialise la zone |
| `/silence 24` · `/resume` | Suspend les notifications (le scraping continue) |
| `/max 5` | Change le plafond de notifications par run |
| `/suite` | Envoie les annonces retenues par le plafond |
| `/historique` | Les 10 annonces les plus récentes |
| `/test` | Scan immédiat, montre ce qui passerait, **sans** marquer comme vu |
| `/stats` | État de la base, compte par source, date du dernier run |

**Un filtre non défini ne restreint rien.** Et si une donnée manque dans une
annonce (surface non renseignée par exemple), l'annonce **passe quand même**,
avec la mention `⚠️ surface inconnue`. Mieux vaut un faux positif qu'une
occasion ratée.

Les filtres s'appliquent à la **notification**, jamais au stockage : tout ce qui
est trouvé va en base. Si tu assouplis un critère plus tard, le bot te propose
« 12 annonces déjà en base correspondent maintenant, les envoyer ? » avec deux
boutons.

### Délai de réponse aux commandes

Le bot n'est pas un serveur permanent : il lit ses messages quand il tourne. Le
workflow `commandes.yml` relève donc les messages **toutes les 30 minutes**
(~20 secondes par passage, sans scraping). Compte jusqu'à une demi-heure entre
ta commande et sa confirmation. Pour aller plus vite : `Actions` →
`Commandes Telegram` → `Run workflow`.

---

## 3. Ce que fait le bot, dans l'ordre

1. **Commandes** — `getUpdates` avec un offset persisté en base, exécution,
   confirmation à **tous** les destinataires.
2. **Scraping** — les sources actives en parallèle (8 à la fois), User-Agent
   réaliste, délai aléatoire de 2 à 5 s entre deux requêtes d'une même source,
   `robots.txt` respecté. Une source qui plante n'arrête pas les autres.
3. **Filtre géographique** — par code postal **et** par nom de commune, en
   français et en néerlandais.
4. **Enrichissement** — pour les seules annonces encore inconnues, la fiche
   détaillée est ouverte afin de récupérer bouquet, rente et PEB, que les pages
   de liste affichent rarement.
5. **Déduplication** — trois niveaux (voir plus bas).
6. **Notification** — nouveautés et baisses de prix, sous plafond.

### Filtre géographique

La zone couvre **92 codes postaux** : les 19 communes de Bruxelles-Capitale,
la première couronne, et la deuxième couronne jusqu'à 20 km de la Grand-Place
(Waterloo, Braine-l'Alleud, La Hulpe, Rixensart, Lasne, Braine-le-Château côté
wallon ; Roosdaal, Gooik, Pepingen, Liedekerke, Affligem, Opwijk, Londerzeel,
Kapelle-op-den-Bos, Kampenhout, Huldenberg, Bertem, Leefdaal côté flamand).
Tubize est à 20,4 km, donc juste dehors : une ligne dans `config.py` suffit à
l'ajouter. `/rayon 15` ramène la zone à 66 communes, `/rayon 10` à 40.

Beaucoup de sites d'agences n'affichent que le nom de la commune, sans code
postal. Le matching fonctionne donc des deux façons, avec ces précautions :

- normalisation avant comparaison : minuscules, accents supprimés, tirets et
  apostrophes unifiés. `Rhode-Saint-Genèse` = `rhode saint genese` =
  `Rhode-St-Genese` = `Sint-Genesius-Rode` (via la liste d'appellations) ;
- `St-` → `Saint-`, `Ste-` → `Sainte-`, `Sint-` → `Saint-` ;
- match sur **mot entier** : `Halle` ne matche pas « les Halles », `Lot` ne
  matche pas « lotissement » ni « lot 3 » ;
- les appellations ambiguës (`Lot`, `Forest`, `Haren`, `Asse`…) ne comptent que
  dans le champ localisation, jamais au milieu d'une description ;
- **si code postal et nom se contredisent, le code postal gagne**, et
  l'incohérence part dans les logs ;
- une annonce sans code postal ni commune reconnue mais qui parle de la région
  bruxelloise est **gardée**, avec la mention `⚠️ localisation à vérifier`.

### Déduplication

Le script tourne 2 fois par jour : la même annonce ne doit jamais arriver deux
fois. Trois niveaux, dans cet ordre :

1. `id_hash` = SHA256(source + identifiant natif), ou à défaut SHA256(URL
   normalisée : sans paramètres UTM, sans fragment, sans `www`, sans slash
   final).
2. `fingerprint` = SHA256(code postal + surface + prix + chambres), avec
   tolérance : surface arrondie à la dizaine inférieure, prix aux 5 000 €
   inférieurs. Comme un arrondi ne suffit pas (118 m² tombe dans 110, 120 m²
   dans 120, alors que c'est le même bien), la recherche interroge aussi les
   **seaux voisins** en surface et en prix. Si l'empreinte existe déjà, rien
   n'est notifié : la nouvelle source est simplement ajoutée à la liste
   `sources[]` de l'entrée existante — la même annonce apparaît souvent sur 4 ou
   5 sites (agence → Immoweb → Trovit → Waa2).
3. Si la surface manque : similarité de titre (rapidfuzz, seuil 85 %) + même
   code postal + prix à ±5 %.

**Règle d'arbitrage : dans le doute, c'est un doublon.** Mieux vaut rater une
annonce que se faire spammer — `/stats` et `/historique` permettent de vérifier.

Par annonce :

- `id_hash` absent → insertion + notification ;
- présent, prix inchangé → mise à jour de `last_seen`, aucun envoi ;
- présent, prix modifié → mise à jour + notification **📉 BAISSE DE PRIX** avec
  l'ancien et le nouveau prix.

Le lien envoyé suit une priorité : **site de l'agence > Immoweb > autres
portails > particuliers > agrégateurs**.

### Anti-spam

- **Premier run** : aucune notification individuelle, un seul récapitulatif.
- **Plafond** : 15 notifications par run (`/max` pour changer). Au-delà :
  « +N autres annonces, tape `/suite` ». Les restantes sont en base.
- **Throttle** : 1 message par seconde (limite Telegram).
- **Baisse de prix** : notifiée seulement si elle dépasse 3 % **ou** 5 000 €, et
  au maximum une fois par annonce et par semaine.
- **Silence** : `/silence 24` met les notifications en pause ; le scraping
  continue et tout ressort à `/resume`.

### Destinataires multiples

Chaque notification part vers tous les ids de `TELEGRAM_CHAT_ID`. Si un envoi
échoue pour l'un d'eux (bot bloqué, id invalide), l'erreur est loguée et les
autres reçoivent quand même — le run ne plante pas. Les commandes sont acceptées
depuis n'importe quel id autorisé, et la confirmation part vers tous, pour que
chacun sache que les critères ont changé. Un message venant d'un id non autorisé
est ignoré (sauf `/whoami`, qui répond seulement à son expéditeur).

---

## 4. Sources

Les 41 sources de la liste de départ sont toutes déclarées dans `config.py`,
chacune avec un flag `enabled`. **12 sont actives**, les 29 autres sont
désactivées avec, en commentaire au-dessus de chaque ligne, la raison exacte
constatée en les testant une par une les 29 et 30 août 2026. Il suffit de
repasser `enabled` à `True` si un site revient.

Un run complet ramène **~580 annonces brutes, dont 148 dans la zone, en 53
secondes**.

### Actives

| Source | Ce qu'elle rapporte |
|---|---|
| **immoweb** | 226 viagers en Belgique, et de loin la source la mieux renseignée : bouquet, rente, âge du crédirentier et PEB fournis en clair |
| **viagerbel** | catalogue de 274 fiches, mais **8 disponibles** seulement : le reste est leur vitrine de ventes passées |
| **vente-en-viager** | 120 biens |
| **leviager.be** | ~50 biens (les « vendu » sont écartés) |
| **lijfrente-makelaar** | ~22 biens |
| **2dehands** / **2ememain** | ~35 annonces de particuliers, via l'API de recherche interne |
| **leefrente** | ~16 biens |
| **leviager.eu**, **immoviager**, **viagerim**, **immorenier** | petits catalogues d'agences viager |

Le point clé côté Immoweb : le filtre viager s'obtient avec le paramètre
**`isALifeAnnuitySale=true`**, et lui seul. Le segment `verkoop-op-lijfrente`
présent dans les URL publiques est ignoré par l'API — sans le bon paramètre,
elle renvoie les ~10 000 biens à vendre du pays au lieu des ~226 viagers. Le
scraper revérifie ensuite chaque résultat (`flags.secondary = life_annuity`)
pour ne pas noyer la base si le filtre sautait un jour.

### Désactivées, et pourquoi

**Aucun filtre viager possible** — ces portails ignorent le paramètre de
recherche et renvoient des annonces ordinaires. Les laisser actifs remplirait
la base de faux positifs :
Immovlan (recherche rendue en JavaScript, le mot « viager » n'apparaît nulle
part dans le HTML servi), Zimmo (`?search=viager` ignoré : vérifié, il renvoyait
des maisons à Gand et Fontaine-l'Évêque), Realo, Immoscoop, ERA, Century 21,
Immotop, ImmoBrussels.

**Doublons d'une source déjà active** : Logic-Immo et Hebbes redirigent vers
Zimmo ; viager-bruxelles.be redirige vers Viagerbel.

**Domaines éteints** (aucune résolution DNS ou connexion refusée, testés en
www et sans www, en https et en http) : monviager.be, viagerplus.be,
belgiumviager.be, renteviager.be, vitaviager.be, lijfrentehuis.be,
immobelgique.be, repimmo.be, nuroa.be, immosearch.be, maisons.mitula.be,
woning-unie.eu. Viagimmo.be répond encore mais ne publie plus aucun catalogue.

**Bloquées à tout client non-navigateur** (HTTP 401 systématique) : Trovit et
Nestoria. Y accéder demanderait de contourner une protection, ce que le bot ne
fait pas.

**Catalogue rendu en JavaScript**, donc invisible pour `requests` :
lijfrentemakelaar.be (à ne pas confondre avec lijfrente-makelaar.be, qui lui
fonctionne) et immo2life.be.

**Sans fiches exploitables** : huizen.waa2.be ne sert que des pages de
« recherches associées », pas d'annonces.

> Concrètement, la perte est faible : les agences qui publient sur Immovlan ou
> Zimmo publient aussi sur Immoweb, où le filtre viager existe vraiment, et les
> agences spécialisées sont scrapées en direct.

Tous les mots-clés sont testés, en FR (viager, viager occupé/libre, rente
viagère, nue-propriété, bouquet, usufruit, vente à terme), en NL (lijfrente,
leefrente, bezette/vrije lijfrente, blote eigendom, vruchtgebruik, boeket,
verkoop op termijn) et en EN (life annuity, bare ownership).

### Les biens déjà vendus

Beaucoup d'agences gardent leurs ventes passées en ligne, en vitrine : sur les
274 fiches du catalogue viagerbel, 266 portent un badge « Vendu ». Elles sont
écartées avant tout stockage.

Deux pièges ont demandé un traitement particulier, et valent d'être connus si tu
ajoutes une source :

**Une annonce est souvent liée plusieurs fois dans une même page** — depuis sa
carte, depuis sa photo, depuis un lien « Descriptif complet » — et ces liens
n'ont pas le même bloc parent. Chez viagerbel, un seul de ces blocs porte le
badge « Vendu ». Ne regarder que la première occurrence laissait donc passer
tous les biens vendus. Le scraper regroupe maintenant toutes les occurrences
d'une URL et considère le bien comme vendu si **l'une** d'elles le signale.

**La pagination ne s'arrête pas sur une page sans résultat**, mais sur une page
sans aucun lien d'annonce. Sinon, une page entièrement composée de biens vendus
couperait l'exploration et laisserait les pages suivantes inexplorées — c'est
exactement ce qui arrivait sur viagerbel dès la page 3.

La détection ne regarde que le titre et les 60 premiers caractères de la carte,
là où les sites posent leur badge. Chercher plus loin produisait deux faux
positifs systématiques : « le bien est vendu **en** nue-propriété » décrit le
montage de la vente et non un bien parti, et le texte d'une carte déborde
souvent sur l'annonce voisine. Pour la même raison, « vendu en viager / en
nue-propriété / op lijfrente » n'est jamais compté comme une vente conclue.

Si des biens vendus sont déjà en base (enregistrés avant ce tri) :

```bash
python main.py --purge-vendus --dry-run   # liste sans rien toucher
python main.py --purge-vendus             # supprime
```

### La sonde, pour réparer une source

`sonde.py` sert à retrouver la vraie page de catalogue d'un site quand une
source se tait :

```bash
python sonde.py viagerbel.be leefrente.be
```

Pour chaque domaine, elle essaie www/sans-www et https/http, affiche les
formulaires de recherche avec le nom de leurs champs, puis liste les pages
internes en comptant combien de liens d'annonces chacune contient. La ligne
marquée `<<< CANDIDAT` donne l'URL à mettre dans `config.py`.

### Découverte automatique d'agences

Quand une annonce viager sur Immoweb ou Immovlan est publiée par une agence dont
le site est identifiable, l'URL est enregistrée dans
`agences_decouvertes.json`, commité avec la base. Tu la valides à la main en
ajoutant la source dans `config.py`.

### Quand une source casse

Les sites changent de structure sans prévenir. Le bot le détecte :

- le nombre d'annonces par source est logué à chaque run ;
- si une source renvoie **0 résultat pendant 5 runs consécutifs**, tu reçois une
  alerte Telegram « source muette » (une seule fois, pas à chaque run) ;
- si un scraper plante, les autres continuent et tu reçois **un** message
  d'alerte groupé par run.

Pour désactiver une source, passe son `enabled` à `False` dans `config.py`. Rien
d'autre ne bouge.

> **À savoir** : le scraper générique est volontairement tolérant (JSON-LD
> d'abord, détection heuristique des cartes ensuite) plutôt que collé à des
> classes CSS précises, justement parce que 40 sites qui changent, ça arrive.
> Certaines sources rendront donc parfois 0 annonce : c'est le rôle de l'alerte
> ci-dessus de te le dire.

---

## 5. Exécution sur GitHub Actions

### Horaires

`veille.yml` tourne à **13h et 19h, heure de Bruxelles**. Le cron GitHub étant
en UTC et ignorant l'heure d'été, le workflow se déclenche aux deux heures UTC
possibles (11h/12h et 17h/18h) et une première étape vérifie l'heure réelle à
Bruxelles. Le changement d'heure est donc géré tout seul.

**Les tâches planifiées de GitHub arrivent en retard, et parfois pas du tout.**
C'est documenté et sans recours : la file est partagée, et les dépôts privés sur
compte gratuit passent après les autres. Trois précautions en tiennent compte :

- les crons ne sont **jamais à l'heure pile ni à la demie** (`5 11,12`, `13,43`),
  les créneaux les plus encombrés ;
- la fenêtre d'acceptation fait **deux heures** (13h-14h, 19h-20h) et non une,
  pour qu'un déclenchement en retard fasse quand même son travail ;
- `--min-interval 5` refuse de rescraper si la veille précédente date de moins
  de 5 heures. C'est lui qui garantit un seul passage réel par créneau, quel que
  soit celui des deux déclenchements qui arrive en premier.

Si une exécution saute malgré tout, la suivante rattrape : rien n'est perdu, les
annonces manquées sont simplement notifiées plus tard. Et `Actions` →
`Veille viager` → `Run workflow` force un passage immédiat à tout moment.

Un dépôt **public** est nettement mieux servi par l'ordonnanceur, en plus d'avoir
des minutes illimitées. Le code ne contient aucun secret ; le seul frein est que
`seen.db`, donc ton historique de recherche, deviendrait visible.

`workflow_dispatch` permet un lancement manuel à tout moment, avec une case
« dry run ».

### Persistance de `seen.db` : commit, pas cache

**Choix : commit automatique dans le dépôt.** `actions/cache` a été écarté :

- une entrée de cache est **supprimée après 7 jours sans accès**, et l'ensemble
  est purgé quand le dépôt dépasse 10 Go — perdre la base signifie tout
  renotifier depuis zéro ;
- les caches sont cloisonnés par branche, avec des règles de restauration
  subtiles ;
- un cache ne s'inspecte pas : avec un commit, je peux télécharger `seen.db`,
  l'ouvrir, corriger une ligne, et l'historique git donne une sauvegarde
  gratuite de chaque run.

Le coût est un commit par run (au plus 4 par jour avec le workflow de
commandes). Les deux workflows partagent `concurrency: viager-db` et font un
`git pull --rebase` avant de pousser, donc pas de conflit.

Si tu préfères quand même le cache : remplace l'étape « Sauvegarder la base »
par `actions/cache@v4` avec `path: seen.db` et une clé horodatée + `restore-keys`.

### Consommation de minutes

| Workflow | Fréquence | Durée | Par mois |
|---|---|---|---|
| Veille | 2×/jour (4 déclenchements, 2 s'arrêtent aussitôt) | ~2 min (53 s de scraping + installation) | ~130 min |
| Gardes qui s'arrêtent | 2×/jour | ~5 s | ~5 min |
| Commandes | toutes les 30 min | ~25 s | ~730 min |
| **Total** | | | **~865 min** |

Le quota gratuit d'un dépôt **privé** est de 2 000 min/mois : on est dans les
clous avec de la marge. Sur un dépôt **public**, les minutes Actions sont
**illimitées et gratuites** — mais publie alors sans hésiter, il n'y a aucun
secret dans le code (token et chat_ids passent uniquement par les secrets
GitHub, jamais par un fichier).

Pour réduire : passe `commandes.yml` à `0 * * * *` (toutes les heures, ~360
min/mois) ou supprime ce workflow — les commandes seront alors lues au début de
chacune des deux veilles.

Le run complet est borné à **240 secondes** de scraping (`BUDGET_SECONDES` dans
`config.py`) : au-delà, la pagination s'arrête proprement et le run se termine
normalement.

---

## 6. Options en ligne de commande

```
python main.py                  # run normal
python main.py --dry-run        # console uniquement : n'envoie rien, n'écrit rien
python main.py --reset          # vide la base et quitte
python main.py --purge-vendus   # retire de la base les biens déjà vendus
                                #   (ajoute --dry-run pour voir sans supprimer)
python main.py --source zimmo   # une seule source (debug)
python main.py --commands-only  # traite les commandes Telegram, sans scraper
python main.py --no-telegram    # scrape et stocke, sans envoyer
python main.py -v               # logs détaillés
```

---

## 7. Structure

```
config.py        sources, communes FR/NL, codes postaux, coordonnées, réglages
models.py        la dataclass Annonce, structure commune à toutes les sources
geo.py           normalisation, matching commune/code postal, calcul de rayon
parsing.py       extraction bouquet, rente, chambres, m², PEB, âge du vendeur…
dedup.py         les trois niveaux de déduplication
db.py            SQLite : annonces, filtres, méta, stats, file d'attente, agences
filtres.py       filtres de notification (une donnée absente ne rejette jamais)
telegram.py      client API Bot : envoi multi-destinataires, getUpdates
commandes.py     analyse et exécution des commandes, claviers inline
notifier.py      mise en forme HTML des messages
details.py       ouverture des fiches détaillées des annonces neuves
main.py          orchestration du run
scrapers/
  base.py        HTTP poli, robots.txt, utilitaires HTML
  generic.py     moteur générique (JSON-LD puis heuristique) pour ~35 sites
  immoweb.py     API JSON interne + secours HTML + pages d'agences
  immovlan.py    catégorie viager
  marktplaats.py 2ememain.be et 2dehands.be
  immovlan.py    catégorie viager (source désactivée, voir §4)
test_local.py    tests hors ligne : géo, parsing, déduplication, filtres
test_flux.py     tests hors ligne du flux complet de notification
sonde.py         outil de diagnostic pour retrouver l'URL d'un catalogue
```

Ajouter une source ne demande en général qu'une ligne dans `SOURCES` :

```python
{"name": "nouveau-site", "module": "generic", "enabled": True, "kind": "agence",
 "urls": ["https://nouveau-site.be/biens?page={page}"], "pages": 5},
```

`kind` détermine la priorité du lien envoyé (`agence` > `portail_immoweb` >
`portail` > `particulier` > `agregateur`) et, pour `agence`, dispense de
chercher un mot-clé viager dans chaque annonce puisque tout le site en est.

---

## 8. Limites connues

- **Immoweb pèse lourd dans le total.** C'est la seule source généraliste avec
  un vrai filtre viager, donc si Cloudflare durcit ses règles, le volume chute.
  L'alerte « source muette » te préviendra et les agences spécialisées
  continuent de tourner, mais c'est le point de fragilité principal.
- **Les portails généralistes hors Immoweb sont désactivés**, faute de filtre
  viager exploitable (détail au §4). Ce n'est pas un oubli : les activer
  remplirait la base d'annonces ordinaires. Si l'un d'eux ajoute un filtre un
  jour, une ligne dans `config.py` suffit.
- **Immovlan demanderait Playwright.** Sa recherche est rendue en JavaScript ;
  aucun scraping `requests` + BeautifulSoup n'en tirera quoi que ce soit. Tu as
  demandé d'éviter Playwright, la source est donc éteinte plutôt que bricolée.
- **viagerim.eu est lu avec `verify: False`** : son certificat TLS ne couvre
  pas le domaine. C'est une lecture de pages publiques, sans aucun identifiant
  envoyé, mais un attaquant réseau pourrait en théorie fabriquer une fausse
  annonce. Si ça te gêne, passe cette source à `enabled: False` — c'est la
  seule dans ce cas.
- L'extraction du bouquet et de la rente est heuristique sur les sites
  d'agences (Immoweb, lui, les fournit en clair). Elle est fiable quand
  l'annonce les nomme (« bouquet », « rente », « boeket », « lijfrente »),
  moins quand elle noie les chiffres dans une phrase. Le lien vers l'annonce
  reste la référence.
- `robots.txt` est respecté : quelques pages seront ignorées, avec une ligne de
  log. Un `robots.txt` illisible (403 d'un pare-feu, timeout) est traité comme
  absent, et le délai poli de 2 à 5 s entre requêtes s'applique toujours.
- Usage strictement personnel, à faible cadence. Ne redistribue pas les données
  collectées.
