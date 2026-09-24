# -*- coding: utf-8 -*-
"""Configuration centrale du bot de veille viager Bruxelles + peripherie."""

import os

# ---------------------------------------------------------------- Telegram ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()


def chat_ids():
    """Liste des destinataires. Accepte '123,456' ou un id de groupe negatif."""
    return [c.strip() for c in TELEGRAM_CHAT_ID.split(",") if c.strip()]


# ------------------------------------------------------------ Comportement ---
DB_PATH = os.environ.get("VIAGER_DB", "seen.db")
MAX_NOTIF_PAR_RUN = 15           # surchargeable via /max
HTTP_TIMEOUT = 25
DELAI_MIN, DELAI_MAX = 2.0, 5.0  # delai aleatoire entre 2 requetes d'une meme source
RESPECT_ROBOTS = True
MAX_WORKERS = 8                  # sources scrapees en parallele
ZERO_RUNS_ALERTE = 5             # alerte si une source rend 0 pendant N runs
BAISSE_MIN_PCT = 3.0
BAISSE_MIN_EUR = 5000
BAISSE_COOLDOWN_JOURS = 7
FUZZ_SEUIL = 85                  # similarite de titre pour le fallback de dedup
BUDGET_SECONDES = 240            # arret propre avant la limite des 5 min

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
]

# ------------------------------------------------------------- Mots-cles -----
MOTS_CLES_FR = [
    "viager", "viager occupe", "viager libre", "vente en viager",
    "rente viagere", "nue-propriete", "nue propriete", "bouquet",
    "usufruit", "vente a terme",
]
MOTS_CLES_NL = [
    "lijfrente", "leefrente", "verkoop op lijfrente", "bezette lijfrente",
    "vrije lijfrente", "blote eigendom", "naakte eigendom", "vruchtgebruik",
    "boeket", "verkoop op termijn",
]
MOTS_CLES_EN = ["life annuity", "bare ownership"]
MOTS_CLES = MOTS_CLES_FR + MOTS_CLES_NL + MOTS_CLES_EN

# Mots-cles pour les requetes de recherche plein texte
REQUETES = ["viager", "lijfrente", "nue-propriete", "blote eigendom", "leefrente"]

# ------------------------------------------------------------- Communes ------
# cp -> toutes les appellations FR / NL / EN rencontrees dans les annonces
COMMUNES = {
    # --- Region de Bruxelles-Capitale ---
    "1000": ["Bruxelles", "Brussel", "Brussels", "Ville de Bruxelles", "Stad Brussel", "Bruxelles-Ville"],
    "1020": ["Laeken", "Laken"],
    "1030": ["Schaerbeek", "Schaarbeek"],
    "1040": ["Etterbeek"],
    "1050": ["Ixelles", "Elsene"],
    "1060": ["Saint-Gilles", "Sint-Gillis"],
    "1070": ["Anderlecht"],
    "1080": ["Molenbeek-Saint-Jean", "Sint-Jans-Molenbeek", "Molenbeek"],
    "1081": ["Koekelberg"],
    "1082": ["Berchem-Sainte-Agathe", "Sint-Agatha-Berchem"],
    "1083": ["Ganshoren"],
    "1090": ["Jette"],
    "1120": ["Neder-Over-Heembeek"],
    "1130": ["Haren"],
    "1140": ["Evere"],
    "1150": ["Woluwe-Saint-Pierre", "Sint-Pieters-Woluwe"],
    "1160": ["Auderghem", "Oudergem"],
    "1170": ["Watermael-Boitsfort", "Watermaal-Bosvoorde"],
    "1180": ["Uccle", "Ukkel"],
    "1190": ["Forest", "Vorst"],
    "1200": ["Woluwe-Saint-Lambert", "Sint-Lambrechts-Woluwe"],
    "1210": ["Saint-Josse-ten-Noode", "Sint-Joost-ten-Node", "Saint-Josse"],
    # --- Peripherie ---
    "1500": ["Halle", "Hal"],
    "1501": ["Buizingen"],
    "1502": ["Lembeek"],
    "1560": ["Hoeilaart"],
    "1600": ["Sint-Pieters-Leeuw", "Leeuw-Saint-Pierre"],
    "1601": ["Ruisbroek"],
    "1602": ["Vlezenbeek"],
    "1620": ["Drogenbos"],
    "1630": ["Linkebeek"],
    "1640": ["Rhode-Saint-Genese", "Sint-Genesius-Rode", "Rhode-St-Genese"],
    "1650": ["Beersel"],
    "1651": ["Lot"],
    "1652": ["Alsemberg"],
    "1653": ["Dworp", "Tourneppe"],
    "1654": ["Huizingen"],
    "1700": ["Dilbeek"],
    "1701": ["Itterbeek"],
    "1702": ["Groot-Bijgaarden", "Grand-Bigard"],
    "1730": ["Asse"],
    "1740": ["Ternat"],
    "1750": ["Lennik"],
    "1780": ["Wemmel"],
    "1785": ["Merchtem"],
    "1800": ["Vilvoorde", "Vilvorde"],
    "1820": ["Steenokkerzeel"],
    "1830": ["Machelen"],
    "1831": ["Diegem"],
    "1850": ["Grimbergen"],
    "1851": ["Humbeek"],
    "1852": ["Beigem"],
    "1853": ["Strombeek-Bever", "Strombeek"],
    "1860": ["Meise"],
    "1861": ["Wolvertem"],
    "1930": ["Zaventem"],
    "1932": ["Sint-Stevens-Woluwe", "Woluwe-Saint-Etienne"],
    "1933": ["Sterrebeek"],
    "1950": ["Kraainem", "Crainhem"],
    "1970": ["Wezembeek-Oppem"],
    "1980": ["Zemst"],
    "3070": ["Kortenberg"],
    "3080": ["Tervuren", "Tervueren"],
    "3090": ["Overijse"],

    # --- Deuxieme couronne : communes entre 15 et 20 km de la Grand-Place ---
    # Brabant wallon (francophone) :
    "1310": ["La Hulpe", "Terhulpen"],
    "1330": ["Rixensart"],
    "1331": ["Rosieres-Saint-Andre", "Rosieres"],
    "1332": ["Genval"],
    "1380": ["Lasne", "Lasne-Chapelle-Saint-Lambert", "Ohain", "Plancenoit",
             "Couture-Saint-Germain", "Maransart"],
    "1410": ["Waterloo"],
    "1420": ["Braine-l'Alleud", "Eigenbrakel", "Lillois-Witterzee",
             "Ophain-Bois-Seigneur-Isaac"],
    "1440": ["Braine-le-Chateau", "Kasteelbrakel", "Wauthier-Braine"],
    # Brabant flamand (neerlandophone) :
    "1670": ["Pepingen", "Bellingen", "Beert", "Bogaarden", "Heikruis"],
    "1745": ["Opwijk", "Mazenzele"],
    "1755": ["Gooik", "Kester", "Leerbeek", "Oetingen", "Strijland"],
    "1760": ["Roosdaal", "Pamel", "Strijtem", "Onze-Lieve-Vrouw-Lombeek",
             "Borchtlombeek"],
    "1770": ["Liedekerke"],
    "1790": ["Affligem", "Essene", "Hekelgem", "Teralfene"],
    "1840": ["Londerzeel", "Malderen", "Steenhuffel"],
    "1880": ["Kapelle-op-den-Bos", "Nieuwenrode", "Ramsdonk"],
    "1910": ["Kampenhout", "Berg", "Buken", "Nederokkerzeel"],
    "3040": ["Huldenberg", "Ottenburg", "Loonbeek", "Neerijse", "Sint-Agatha-Rode"],
    "3060": ["Bertem", "Korbeek-Dijle"],
    "3061": ["Leefdaal"],

    # --- Sections des communes ci-dessus, avec leur propre code postal ---
    # Ajoutees parce qu'un bien a Erps-Kwerps est un bien a Kortenberg : sans
    # ces lignes, il serait rejete pour cause de code postal hors liste.
    # Supprime ce bloc si tu veux t'en tenir strictement aux codes d'origine.
    "1703": ["Schepdaal"],                      # Dilbeek
    "1731": ["Relegem", "Zellik"],              # Asse
    "1741": ["Wambeek"],                        # Ternat
    "1742": ["Sint-Katherina-Lombeek"],         # Ternat
    "1981": ["Hofstade"],                       # Zemst
    "1982": ["Elewijt", "Weerde"],              # Zemst
    "3071": ["Erps-Kwerps"],                    # Kortenberg
    "3078": ["Everberg", "Meerbeek"],           # Kortenberg

    # --- Troisieme couronne : 20 a 35 km de la Grand-Place (demande du 24/09) ---
    "2811": ["Hombeek", "Leest"],   # section de 2800
    "9470": ["Denderleeuw"],
    "1480": ["Tubize", "Tubeke", "Clabecq", "Oisquercq", "Saintes"],
    "9472": ["Iddergem"],   # section de 9470
    "1461": ["Haut-Ittre"],   # section de 1460
    "2812": ["Muizen"],   # section de 2800
    "3191": ["Hever"],   # section de 3190
    "3190": ["Boortmeerbeek"],
    "3051": ["Sint-Joris-Weert"],   # section de 3050
    "9310": ["Moorsel", "Meldert", "Baardegem", "Herdersem"],   # section de 9300
    "9255": ["Buggenhout", "Opdorp"],
    "3050": ["Oud-Heverlee"],
    "2801": ["Heffen"],   # section de 2800
    "2800": ["Mechelen", "Malines", "Walem"],
    "9473": ["Welle"],   # section de 9470
    "1301": ["Bierges"],   # section de 1300
    "9320": ["Erembodegem", "Nieuwerkerken"],   # section de 9300
    "1541": ["Sint-Pieters-Kapelle"],   # section de 1540
    "3054": ["Vaalbeek"],   # section de 3050
    "1300": ["Wavre", "Waver", "Limal"],
    "3052": ["Blanden"],   # section de 3050
    "3020": ["Herent", "Winksele", "Veltem-Beisem"],
    "1460": ["Ittre", "Virginal-Samme", "Virginal"],
    "9280": ["Lebbeke", "Wieze", "Denderbelle"],
    "2830": ["Willebroek", "Blaasveld", "Heindonk", "Tisselt"],
    "9402": ["Meerbeke"],   # section de 9400
    "9403": ["Neigem"],   # section de 9400
    "2820": ["Bonheiden", "Rijmenam"],
    "9300": ["Aalst", "Alost"],
    "3001": ["Heverlee"],   # section de 3000
    "1342": ["Limelette"],   # section de 1340
    "9308": ["Hofstade", "Gijzegem"],   # section de 9300
    "1473": ["Glabais"],   # section de 1470
    "1341": ["Ceroux-Mousty"],   # section de 1340
    "3150": ["Haacht", "Wespelaar", "Tildonk"],
    "3000": ["Leuven", "Louvain"],
    "1401": ["Baulers"],   # section de 1400
    "9400": ["Ninove", "Okegem", "Voorde", "Appelterre-Eichem", "Denderwindeke", "Lieferinge", "Nederhasselt", "Aspelare"],
    "3053": ["Haasrode"],   # section de 3050
    "1340": ["Ottignies-Louvain-la-Neuve", "Ottignies"],
    "3012": ["Wilsele"],   # section de 3000
    "2890": ["Sint-Amands", "Oppuurs", "Lippelo"],   # section de 2870
    "9450": ["Haaltert", "Denderhoutem", "Heldergem"],
    "1402": ["Thines"],   # section de 1400
    "2870": ["Puurs-Sint-Amands", "Puurs", "Breendonk", "Liezele"],
    "9451": ["Kerksken"],   # section de 9450
    "1472": ["Vieux-Genappe"],   # section de 1470
    "1404": ["Bornival"],   # section de 1400
    "3018": ["Wijgmaal"],   # section de 3000
    "1540": ["Herne", "Herinnes", "Herfelingen"],
    "3140": ["Keerbergen"],
    "1430": ["Rebecq", "Quenast", "Bierghes", "Rebecq-Rognon"],
    "9401": ["Pollare"],   # section de 9400
    "2840": ["Rumst", "Terhagen"],
    "1390": ["Grez-Doiceau", "Archennes", "Bossut-Gottechain", "Biez", "Nethen"],
    "1474": ["Ways"],   # section de 1470
    "9200": ["Dendermonde", "Termonde", "Appels", "Baasrode", "Grembergen", "Oudegem", "Schoonaarde", "Sint-Gillis-bij-Dendermonde", "Mespelare"],
    "9406": ["Outer"],   # section de 9400
    "2850": ["Boom"],
    "1348": ["Louvain-la-Neuve"],   # section de 1340
    "1470": ["Genappe", "Baisy-Thy", "Bousval"],
    "3010": ["Kessel-Lo"],   # section de 3000
    "2860": ["Sint-Katelijne-Waver"],
    "1400": ["Nivelles", "Nijvel", "Monstreux"],
    "7850": ["Enghien", "Edingen", "Petit-Enghien", "Marcq"],
    "3110": ["Rotselaar"],
    "1490": ["Court-Saint-Etienne"],
    "2861": ["Onze-Lieve-Vrouw-Waver"],   # section de 2860
    "1471": ["Loupoigne"],   # section de 1470
    "1570": ["Galmaarden", "Gammerages", "Tollembeek", "Vollezele"],
    "3360": ["Bierbeek", "Korbeek-Lo", "Lovenjoel"],
    "9340": ["Lede", "Oordegem", "Wanzele", "Impe", "Smetlede"],
    "9420": ["Erpe-Mere", "Erpe", "Mere", "Aaigem", "Bambrugge", "Erondegem", "Ottergem", "Vlekkem"],
    "2845": ["Niel"],
    "3220": ["Holsbeek", "Sint-Pieters-Rode", "Kortrijk-Dutsel"],
    "2570": ["Duffel"],
    "1435": ["Mont-Saint-Guibert", "Corbais", "Hevillers"],
    "3120": ["Tremelo"],
    "3118": ["Werchter"],   # section de 3110
    "7090": ["Braine-le-Comte", "s-Gravenbrakel", "Hennuyeres", "Ronquieres", "Petit-Roeulx-lez-Braine", "Steenkerque"],
    "3111": ["Wezemaal"],   # section de 3110
    "1320": ["Beauvechain", "Hamme-Mille", "Tourinnes-la-Grosse", "Nodebais"],
    "2627": ["Schelle"],
    "3128": ["Baal"],   # section de 3120
    "9220": ["Hamme", "Moerzeke"],
    "1325": ["Chaumont-Gistoux", "Corroy-le-Grand", "Dion-Valmont", "Bonlez", "Longueville"],
    "9260": ["Wichelen", "Serskamp", "Schellebelle"],
    "2630": ["Aartselaar"],
    "1495": ["Villers-la-Ville", "Marbais", "Mellery", "Tilly", "Sart-Dames-Avelines"],
    "9290": ["Berlare", "Overmere", "Uitbergen"],
    "2550": ["Kontich", "Waarloos"],
    "1547": ["Bever", "Bievene"],
    "9550": ["Herzele", "Hillegem", "Borsbeke", "Ressegem", "Woubrechtegem"],
    "9240": ["Zele"],
    "2620": ["Hemiksem"],
    "7190": ["Ecaussinnes", "Ecaussinnes-d'Enghien", "Ecaussinnes-Lalaing", "Marche-lez-Ecaussinnes"],
    "1450": ["Chastre", "Blanmont", "Cortil-Noirmont", "Saint-Gery"],
    "3370": ["Boutersem", "Vertrijk", "Roosbeek"],
    "9500": ["Geraardsbergen", "Grammont"],
    "3210": ["Lubbeek", "Linden"],
    "1457": ["Walhain", "Tourinnes-Saint-Lambert", "Nil-Saint-Vincent"],
}

CODES_POSTAUX = list(COMMUNES.keys())

# Code postal d'une section -> code postal de la commune mere.
# Sert uniquement a ne pas crier a l'incoherence quand une annonce dit
# "1020 Laeken" et "Bruxelles", ou "1502" et "Halle" : c'est le meme endroit.
COMMUNE_MERE = {
    "1020": "1000", "1120": "1000", "1130": "1000",
    "1501": "1500", "1502": "1500",
    "1601": "1600", "1602": "1600",
    "1651": "1650", "1652": "1650", "1653": "1650", "1654": "1650",
    "1701": "1700", "1702": "1700", "1703": "1700",
    "1731": "1730", "1741": "1740", "1742": "1740",
    "1831": "1830",
    "1851": "1850", "1852": "1850", "1853": "1850",
    "1861": "1860",
    "1932": "1930", "1933": "1930",
    "1981": "1980", "1982": "1980",
    "3071": "3070", "3078": "3070",
    "1331": "1330", "1332": "1330",      # Rosieres et Genval font partie de Rixensart
    "3061": "3060",                      # Leefdaal fait partie de Bertem
    # sections de la troisieme couronne
    "2811": "2800", "9472": "9470", "1461": "1460", "2812": "2800",
    "3191": "3190", "3051": "3050", "9310": "9300", "2801": "2800",
    "9473": "9470", "1301": "1300", "9320": "9300", "1541": "1540",
    "3054": "3050", "3052": "3050", "9402": "9400", "9403": "9400",
    "3001": "3000", "1342": "1340", "9308": "9300", "1473": "1470",
    "1341": "1340", "1401": "1400", "3053": "3050", "3012": "3000",
    "2890": "2870", "1402": "1400", "9451": "9450", "1472": "1470",
    "1404": "1400", "3018": "3000", "9401": "9400", "1474": "1470",
    "9406": "9400", "1348": "1340", "3010": "3000", "2861": "2860",
    "1471": "1470", "3118": "3110", "3111": "3110", "3128": "3120",
}

# Appellations trop courtes / ambigues : ne comptent QUE si elles apparaissent
# dans le champ localisation, jamais au milieu d'une description libre.
ALIAS_AMBIGUS = {
    "lot", "halle", "hal", "haren", "forest", "vorst", "asse", "meise",
    "brussels", "molenbeek", "strombeek",
    # deuxieme couronne : noms qui sont aussi des mots courants
    "berg", "beert", "kester", "lasne", "genval",
    # troisieme couronne : noms qui sont aussi des mots courants
    "boom", "muizen", "leest", "heffen", "welle", "lede", "mere",
    "hever", "baal", "linden", "appels", "duffel", "outer", "ways",
    "saintes", "walem", "biez", "tilly", "zele", "hamme", "erpe",
    "limal", "thines", "puurs",
}

# cp -> (lat, lon) approximatif, pour la commande /rayon
COORDS = {
    "1000": (50.8465, 4.3517), "1020": (50.8843, 4.3450), "1030": (50.8676, 4.3737),
    "1040": (50.8367, 4.3894), "1050": (50.8270, 4.3714), "1060": (50.8267, 4.3450),
    "1070": (50.8383, 4.3083), "1080": (50.8556, 4.3222), "1081": (50.8622, 4.3272),
    "1082": (50.8656, 4.2939), "1083": (50.8711, 4.3139), "1090": (50.8783, 4.3269),
    "1120": (50.9017, 4.3878), "1130": (50.8917, 4.4133), "1140": (50.8706, 4.4022),
    "1150": (50.8317, 4.4344), "1160": (50.8158, 4.4269), "1170": (50.7994, 4.4131),
    "1180": (50.8000, 4.3383), "1190": (50.8106, 4.3181), "1200": (50.8467, 4.4292),
    "1210": (50.8531, 4.3706),
    "1500": (50.7350, 4.2367), "1501": (50.7500, 4.2500), "1502": (50.7167, 4.2167),
    "1560": (50.7683, 4.4700), "1600": (50.7800, 4.2400), "1601": (50.7889, 4.2828),
    "1602": (50.8161, 4.2181), "1620": (50.7933, 4.3117), "1630": (50.7719, 4.3378),
    "1640": (50.7433, 4.3600), "1650": (50.7622, 4.3011), "1651": (50.7639, 4.2711),
    "1652": (50.7472, 4.3242), "1653": (50.7383, 4.3006), "1654": (50.7519, 4.2789),
    "1700": (50.8556, 4.2603), "1701": (50.8394, 4.2597), "1702": (50.8722, 4.2589),
    "1730": (50.9117, 4.2011), "1740": (50.8686, 4.1683), "1750": (50.8069, 4.1592),
    "1780": (50.9078, 4.3078), "1785": (50.9558, 4.2311), "1800": (50.9281, 4.4267),
    "1820": (50.9111, 4.5111), "1830": (50.9083, 4.4353), "1831": (50.8894, 4.4419),
    "1850": (50.9339, 4.3719), "1851": (50.9686, 4.3719), "1852": (50.9317, 4.3900),
    "1853": (50.9083, 4.3506), "1860": (50.9294, 4.3283), "1861": (50.9422, 4.3067),
    "1930": (50.8833, 4.4700), "1932": (50.8722, 4.4467), "1933": (50.8628, 4.4933),
    "1950": (50.8556, 4.4633), "1970": (50.8444, 4.4917), "1980": (50.9833, 4.4667),
    "3070": (50.8917, 4.5417), "3080": (50.8228, 4.5147), "3090": (50.7739, 4.5361),
    # deuxieme couronne (15-20 km)
    "1310": (50.7300, 4.4850), "1330": (50.7150, 4.5280), "1331": (50.7220, 4.5450),
    "1332": (50.7200, 4.5000), "1380": (50.6950, 4.4600), "1410": (50.7150, 4.3990),
    "1420": (50.6840, 4.3700), "1440": (50.6800, 4.2700),
    "1670": (50.7500, 4.1700), "1745": (50.9700, 4.1900), "1755": (50.7900, 4.1100),
    "1760": (50.8400, 4.1200), "1770": (50.8700, 4.0800), "1790": (50.9000, 4.1100),
    "1840": (51.0000, 4.3000), "1880": (51.0100, 4.3600), "1910": (50.9400, 4.5500),
    "3040": (50.7900, 4.5800), "3060": (50.8500, 4.6200), "3061": (50.8400, 4.5800),
    # sections ayant leur propre code postal : sans coordonnees, /rayon les
    # ecarterait alors que leur commune mere est dans la zone
    "1703": (50.8394, 4.2094), "1731": (50.8833, 4.2667), "1741": (50.8558, 4.1531),
    "1742": (50.8683, 4.1439), "1981": (50.9928, 4.4642), "1982": (50.9639, 4.5011),
    "3071": (50.8958, 4.5842), "3078": (50.8622, 4.5806),
    # troisieme couronne (20-35 km)
    "2811": (51.0100, 4.4370), "9470": (50.8850, 4.0730), "1480": (50.6900, 4.2000),
    "9472": (50.8730, 4.0550), "1461": (50.6600, 4.2900), "2812": (51.0080, 4.5130),
    "3191": (51.0000, 4.5350), "3190": (50.9790, 4.5750), "3051": (50.8080, 4.6530),
    "9310": (50.9500, 4.0900), "9255": (51.0170, 4.2020), "3050": (50.8360, 4.6600),
    "2801": (51.0370, 4.4230), "2800": (51.0280, 4.4800), "9473": (50.8800, 4.0400),
    "1301": (50.7120, 4.5850), "9320": (50.9180, 4.0550), "1541": (50.7400, 4.0700),
    "3054": (50.8340, 4.6800), "1300": (50.7170, 4.6100), "3052": (50.8280, 4.6810),
    "3020": (50.9060, 4.6710), "1460": (50.6430, 4.2640), "9280": (51.0040, 4.1280),
    "2830": (51.0600, 4.3600), "9402": (50.8200, 4.0150), "9403": (50.8000, 4.0200),
    "2820": (51.0230, 4.5470), "9300": (50.9380, 4.0410), "3001": (50.8610, 4.6940),
    "1342": (50.6800, 4.5750), "9308": (50.9650, 4.0600), "1473": (50.6330, 4.4400),
    "1341": (50.6600, 4.5400), "3150": (50.9760, 4.6380), "3000": (50.8790, 4.7010),
    "1401": (50.6220, 4.3400), "9400": (50.8280, 3.9970), "3053": (50.8410, 4.7100),
    "1340": (50.6650, 4.5670), "3012": (50.9000, 4.7030), "2890": (51.0560, 4.2080),
    "9450": (50.9050, 4.0000), "1402": (50.6170, 4.3650), "2870": (51.0750, 4.2850),
    "9451": (50.8900, 3.9900), "1472": (50.6180, 4.4200), "1404": (50.6180, 4.2830),
    "3018": (50.9250, 4.7000), "1540": (50.7250, 4.0360), "3140": (51.0030, 4.6330),
    "1430": (50.6580, 4.1250), "9401": (50.8120, 3.9800), "2840": (51.0810, 4.4200),
    "1390": (50.7400, 4.6900), "1474": (50.6180, 4.4700), "9200": (51.0280, 4.1010),
    "9406": (50.8450, 3.9700), "2850": (51.0880, 4.3710), "1348": (50.6690, 4.6120),
    "1470": (50.6100, 4.4510), "3010": (50.8850, 4.7350), "2860": (51.0650, 4.5350),
    "1400": (50.5980, 4.3280), "7850": (50.6900, 4.0400), "3110": (50.9510, 4.7160),
    "1490": (50.6330, 4.5680), "2861": (51.0580, 4.5750), "1471": (50.5950, 4.4300),
    "1570": (50.7550, 3.9700), "3360": (50.8300, 4.7600), "9340": (50.9650, 3.9860),
    "9420": (50.9260, 3.9600), "2845": (51.1100, 4.3340), "3220": (50.9180, 4.7580),
    "2570": (51.0960, 4.5080), "1435": (50.6340, 4.6110), "3120": (50.9950, 4.7070),
    "3118": (50.9600, 4.7400), "7090": (50.6100, 4.1450), "3111": (50.9410, 4.7550),
    "1320": (50.7800, 4.7700), "2627": (51.1260, 4.3400), "3128": (50.9820, 4.7400),
    "9220": (51.0960, 4.1350), "1325": (50.6770, 4.7200), "9260": (51.0050, 3.9700),
    "2630": (51.1340, 4.3850), "1495": (50.5790, 4.5310), "9290": (51.0360, 4.0000),
    "2550": (51.1320, 4.4500), "1547": (50.7100, 3.9400), "9550": (50.8880, 3.8900),
    "9240": (51.0660, 4.0400), "2620": (51.1430, 4.3400), "7190": (50.5680, 4.1700),
    "1450": (50.6080, 4.6430), "3370": (50.8340, 4.8330), "9500": (50.7710, 3.8820),
    "3210": (50.8830, 4.8390), "1457": (50.6260, 4.7000),
}

CENTRE_BRUXELLES = (50.8465, 4.3517)  # Grand-Place

# --------------------------------------------------------------- Sources -----
# Priorite du lien envoye : plus le chiffre est bas, plus la source est preferee.
PRIORITE = {"agence": 10, "portail_immoweb": 20, "portail": 30,
            "particulier": 35, "agregateur": 50}

# module  : module python dans scrapers/
# enabled : mets False pour desactiver une source cassee sans toucher au reste
# urls    : {page} est remplace par le numero de page (1..pages)
SOURCES = [
    # ---------------------------------------------------- A. portails -------
    {"name": "immoweb", "module": "immoweb", "enabled": True, "kind": "portail_immoweb"},
    # La recherche Immovlan est rendue en JavaScript et n'expose aucun filtre
    # viager cote URL : le HTML servi ne contient meme pas le mot. Il faudrait
    # Playwright, qu'on evite. Les agences qui publient sur Immovlan publient
    # aussi sur Immoweb, ou le filtre viager existe (isALifeAnnuitySale).
    {"name": "immovlan", "module": "immovlan", "enabled": False, "kind": "portail"},
    {"name": "2ememain", "module": "marktplaats", "enabled": True, "kind": "particulier",
     "base": "https://www.2ememain.be", "queries": ["viager", "nue-propriete", "rente viagere"]},
    {"name": "2dehands", "module": "marktplaats", "enabled": True, "kind": "particulier",
     "base": "https://www.2dehands.be", "queries": ["lijfrente", "blote eigendom", "leefrente"]},

    # Zimmo IGNORE le parametre ?search=viager : il renvoie des annonces
    # ordinaires de toute la Belgique. Verifie le 2026-08-30, a laisser eteint
    # tant qu'aucun filtre viager natif n'existe.
    {"name": "zimmo", "module": "generic", "enabled": False, "kind": "portail",
     "urls": ["https://www.zimmo.be/fr/rechercher/?search=viager"]},
    # logic-immo.be redirige vers zimmo.be : meme moteur, memes limites
    {"name": "logic-immo", "module": "generic", "enabled": False, "kind": "portail",
     "urls": ["https://www.logic-immo.be/"]},
    # aucun filtre ni recherche plein texte viager exploitable
    {"name": "realo", "module": "generic", "enabled": False, "kind": "portail",
     "urls": ["https://www.realo.be/fr/search?q=viager"]},
    # pas de filtre lijfrente ; ?q= est ignore
    {"name": "immoscoop", "module": "generic", "enabled": False, "kind": "portail",
     "urls": ["https://www.immoscoop.be/zoeken/te-koop"]},
    # ERA ne propose que des filtres par type de bien et par commune,
    # aucune recherche plein texte : impossible d'isoler le viager
    {"name": "era", "module": "generic", "enabled": False, "kind": "portail",
     "urls": ["https://www.era.be/fr/a-vendre"]},
    # meme limite qu'ERA : ?search= est ignore
    {"name": "century21", "module": "generic", "enabled": False, "kind": "portail",
     "urls": ["https://www.century21.be/fr/a-vendre"]},
    # domaine eteint (DNS)
    {"name": "immobelgique", "module": "generic", "enabled": False, "kind": "portail",
     "urls": ["https://www.immobelgique.be/"]},
    # les slugs de recherche renvoient 404, pas de filtre viager identifie
    {"name": "immotop", "module": "generic", "enabled": False, "kind": "portail",
     "urls": ["https://www.immotop.be/fr/"]},
    # hebbes.be redirige lui aussi vers zimmo.be
    {"name": "hebbes", "module": "generic", "enabled": False, "kind": "portail",
     "urls": ["https://www.hebbes.be/"]},
    # domaine injoignable (DNS / timeout permanent)
    {"name": "woning-unie", "module": "generic", "enabled": False, "kind": "portail",
     "urls": ["https://www.woning-unie.eu/"]},
    # repimmo.be ne resout plus (le service subsiste en .com, cote francais)
    {"name": "repimmo", "module": "generic", "enabled": False, "kind": "portail",
     "urls": ["https://www.repimmo.be/"]},
    # catalogue par type de bien uniquement, sans notion de viager
    {"name": "immobrussels", "module": "generic", "enabled": False, "kind": "portail",
     "urls": ["https://www.immobrussels.be/fr/immo-a-vendre/maison/province-bruxelles-capitale/"]},

    # ------------------------------------------------- C. agregateurs -------
    # renvoie 401 a tout client non-navigateur : inaccessible sans contourner une
    # protection, ce que le bot ne fait pas
    {"name": "trovit", "module": "generic", "enabled": False, "kind": "agregateur",
     "urls": ["https://immo.trovit.be/viager-bruxelles"]},
    # huizen.waa2.be n'expose que des pages de categories ("recherches
    # associees"), pas de fiches : lien_re cible les vraies annonces si le site
    # en publie a nouveau
    {"name": "waa2", "module": "generic", "enabled": False, "kind": "agregateur",
     "urls": ["https://huizen.waa2.be/te-koop/verkoop-lijfrente"],
     "lien_re": r"/(huis|appartement|woning)-te-koop"},
    # domaine eteint (Mitula a ete absorbe par Lifull/Trovit)
    {"name": "mitula", "module": "generic", "enabled": False, "kind": "agregateur",
     "urls": ["https://maisons.mitula.be/l/viager-bruxelles"]},
    # 401 systematique, meme raison que Trovit
    {"name": "nestoria", "module": "generic", "enabled": False, "kind": "agregateur",
     "urls": ["https://www.nestoria.be/bruxelles/immobilier/a-vendre?keywords=viager"]},
    # domaine eteint (DNS)
    {"name": "nuroa", "module": "generic", "enabled": False, "kind": "agregateur",
     "urls": ["https://www.nuroa.be/viager-bruxelles"]},
    # domaine eteint (DNS)
    {"name": "immosearch", "module": "generic", "enabled": False, "kind": "agregateur",
     "urls": ["https://www.immosearch.be/fr/recherche?q=viager"]},

    # --------------------------- Notaires (souvent AVANT les portails) ------
    # immo.notaire.be = portail officiel des ventes notariales (Fednot). Le
    # formulaire cache un vrai filtre "Vente en viager" (sale_type_accurate=A),
    # absent de l'interface visible. National : notre filtre geo fait le tri.
    # Les notaires y publient des viagers de succession/gre a gre qui
    # n'atteignent jamais Immoweb.
    # lien_re obligatoire : les liens de navigation du portail ("biens a
    # vendre dans la province de...") ressemblent a des annonces et passaient
    # pour des biens situes "a Bruxelles". Une vraie fiche a la forme
    # /fr/<titre>/a-vendre/<adresse>/<id>.
    {"name": "notaire.be", "module": "generic", "enabled": True, "kind": "agence",
     "urls": ["https://immo.notaire.be/fr/biens-a-vendre?sale_type_accurate=A&page={page}"],
     "pages": 3, "lien_re": r"/a-vendre/.+/\d+"},
    # Vitrines des "maisons des notaires" provinciales. Pas de filtre viager :
    # tri par mot-cle (tout_viager=False via kind portail). Leuven n'a pas de
    # vitrine propre : son Notarishuis renvoie vers immo.notaire.be, deja
    # couvert ci-dessus. Namur est hors zone.
    {"name": "nvn", "module": "generic", "enabled": True, "kind": "portail",
     "urls": ["https://nvn.be/immobilier"]},                       # Bruxelles
    {"name": "notaires-bw", "module": "generic", "enabled": True, "kind": "portail",
     "urls": ["https://mnbw.be/immobilier"]},                      # Brabant wallon
    {"name": "notaires-hainaut", "module": "generic", "enabled": True, "kind": "portail",
     "urls": ["https://maisondunotariatduhainaut.be/immobilier"]}, # Enghien, Braine...
    {"name": "notarishuis-antwerpen", "module": "generic", "enabled": True, "kind": "portail",
     "urls": ["https://www.notarishuis.eu/nl/te-koop/?page={page}"], "pages": 2},  # Malines, Rupel

    # ---- Agences reperees par la decouverte automatique (Immoweb) ----------
    # VIAH! : page "nos biens" sans aucun lien d'annonce (vitrine texte) ;
    # leurs biens passent par Immoweb, deja capte. Pas de source dediee.
    {"name": "homeselect", "module": "generic", "enabled": True, "kind": "agence",
     "urls": ["https://www.homeselect.be/nl/", "https://www.homeselect.be/fr/"],
     "lien_re": r"/pand/|/bien/", "tout_viager": False},   # /pand/lijfrente-verkoop/... dans l'URL
    {"name": "burima", "module": "generic", "enabled": True, "kind": "portail",
     "urls": ["https://www.burima.be/immobiliers/biens-a-vendre/"]},
    {"name": "immopicke", "module": "generic", "enabled": True, "kind": "portail",
     "urls": ["https://www.immopicke.be/fr/a-vendre", "https://www.immopicke.be/nl/te-koop"]},

    # -------------------------------------- D. agences viager (FR) ----------
    {"name": "viagerbel", "module": "generic", "enabled": True, "kind": "agence",
     "urls": ["https://www.viagerbel.be/biens/", "https://www.viagerbel.be/biens/page/{page}/"],
     "pages": 28},
    {"name": "leviager.be", "module": "generic", "enabled": True, "kind": "agence",
     "urls": ["https://www.leviager.be/index.php?action=list&ctypmandatmeta=v&page={page}"],
     "pages": 10},
    {"name": "leviager.eu", "module": "generic", "enabled": True, "kind": "agence",
     "urls": ["https://www.leviager.eu/viagers", "https://www.leviager.eu/viagers?page={page}"],
     "pages": 8},
    {"name": "immoviager", "module": "generic", "enabled": True, "kind": "agence",
     "urls": ["https://www.immoviager.be/", "https://www.immoviager.be/nos-biens/"]},
    # le certificat TLS ne couvre pas www.viagerim.eu : on passe par le domaine nu,
    # et verify=False reste necessaire sur la redirection. Lecture seule de pages
    # publiques, aucun identifiant n'est envoye a ce site.
    {"name": "viagerim", "module": "generic", "enabled": True, "kind": "agence",
     "urls": ["https://viagerim.eu/nos-biens-immobiliers/", "https://viagerim.eu/"],
     "verify": False},
    # les fiches ont un slug a prefixe aleatoire (/bpdfjh-vente-en-viager-maison-...)
    # que la detection par defaut ne reconnait pas : d'ou "lien_re"
    {"name": "vente-en-viager", "module": "generic", "enabled": True, "kind": "agence",
     "urls": ["https://www.vente-en-viager.be/recherche-maison-appartement-en-vente-en-viager-belgique",
              "https://www.vente-en-viager.be/"],
     "lien_re": r"vente-en-viager-(maison|appartement|immeuble|terrain)-"},
    # viager-bruxelles.be redirige vers viagerbel.be : ce serait la meme source deux fois
    {"name": "viager-bruxelles", "module": "generic", "enabled": False, "kind": "agence",
     "urls": ["https://www.viager-bruxelles.be/"]},
    # site vivant en http mais sans page catalogue (aucun lien d'annonce)
    {"name": "viagimmo", "module": "generic", "enabled": False, "kind": "agence",
     "urls": ["http://www.viagimmo.be/"]},
    # domaine eteint : aucune resolution DNS (verifie le 2026-08-29)
    {"name": "belgiumviager", "module": "generic", "enabled": False, "kind": "agence",
     "urls": ["https://www.belgiumviager.be/"]},
    # agence generaliste : ses fiches sont prefixees "achat," et son catalogue
    # melange viager et ventes classiques, d'ou tout_viager=False
    {"name": "immorenier", "module": "generic", "enabled": True, "kind": "agence",
     "urls": ["https://www.immorenier.be/nos-biens", "https://www.immorenier.be/viager"],
     "lien_re": r"achat,", "tout_viager": False},
    # domaine eteint (DNS)
    {"name": "renteviager", "module": "generic", "enabled": False, "kind": "agence",
     "urls": ["https://www.renteviager.be/"]},
    # domaine eteint
    {"name": "viagerplus", "module": "generic", "enabled": False, "kind": "agence",
     "urls": ["https://www.viagerplus.be/"]},
    # domaine eteint
    {"name": "monviager", "module": "generic", "enabled": False, "kind": "agence",
     "urls": ["https://www.monviager.be/"]},

    # ------------------------------------- E. agences lijfrente (NL) --------
    {"name": "leefrente", "module": "generic", "enabled": True, "kind": "agence",
     "urls": ["https://www.leefrente.be/aanbod", "https://www.leefrente.be/aanbod?page={page}"],
     "pages": 6},
    # les fiches sont des articles "/te-koop-op-lijfrente-in-{commune}/" ; sans
    # lien_re on ramassait aussi les pages FAQ et simulateur du site
    {"name": "lijfrente-makelaar", "module": "generic", "enabled": True, "kind": "agence",
     "urls": ["https://www.lijfrente-makelaar.be/category/lijfrente/te-koop-op-lijfrente/",
              "https://www.lijfrente-makelaar.be/category/lijfrente/te-koop-op-lijfrente/page/{page}/"],
     "pages": 6, "lien_re": r"te-koop-op-lijfrente-in-"},
    # le catalogue est injecte en JavaScript : le HTML servi ne contient aucun
    # lien de fiche, seulement des renvois vers la page elle-meme
    {"name": "lijfrentemakelaar", "module": "generic", "enabled": False, "kind": "agence",
     "urls": ["https://www.lijfrentemakelaar.be/nl/lijfrente-te-koop"]},
    # meme cas que lijfrentemakelaar : catalogue rendu en JavaScript
    {"name": "immo2life", "module": "generic", "enabled": False, "kind": "agence",
     "urls": ["https://www.immo2life.be/nl/te-koop-op-lijfrente"]},
    # domaine eteint (DNS)
    {"name": "lijfrentehuis", "module": "generic", "enabled": False, "kind": "agence",
     "urls": ["https://www.lijfrentehuis.be/"]},
    # domaine eteint (DNS)
    {"name": "vitaviager", "module": "generic", "enabled": False, "kind": "agence",
     "urls": ["https://www.vitaviager.be/"]},
]


def sources_actives(only=None):
    out = [s for s in SOURCES if s.get("enabled")]
    if only:
        out = [s for s in out if s["name"] == only]
    return out
