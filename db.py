# -*- coding: utf-8 -*-
"""Persistance SQLite : annonces vues, filtres, etat Telegram, stats sources."""

import json
import os
import sqlite3
from datetime import datetime, timezone

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS annonces (
    id_hash        TEXT PRIMARY KEY,
    fingerprint    TEXT,
    sources        TEXT DEFAULT '[]',
    url_principale TEXT,
    url_priorite   INTEGER DEFAULT 99,
    titre          TEXT,
    description    TEXT,
    prix           INTEGER,
    bouquet        INTEGER,
    rente          INTEGER,
    code_postal    TEXT,
    commune        TEXT,
    chambres       INTEGER,
    surface        INTEGER,
    terrain        INTEGER,
    peb            TEXT,
    type_bien      TEXT,
    type_viager    TEXT,
    jardin         INTEGER,
    garage         INTEGER,
    age_vendeur    INTEGER,
    avertissements TEXT DEFAULT '[]',
    first_seen     TEXT,
    last_seen      TEXT,
    price_history  TEXT DEFAULT '[]',
    notifie        INTEGER DEFAULT 0,
    last_drop_notif TEXT
);
CREATE INDEX IF NOT EXISTS idx_fingerprint ON annonces(fingerprint);
CREATE INDEX IF NOT EXISTS idx_cp ON annonces(code_postal);
CREATE INDEX IF NOT EXISTS idx_notifie ON annonces(notifie);

CREATE TABLE IF NOT EXISTS filtres (
    cle TEXT PRIMARY KEY,
    valeur TEXT
);

CREATE TABLE IF NOT EXISTS meta (
    cle TEXT PRIMARY KEY,
    valeur TEXT
);

CREATE TABLE IF NOT EXISTS source_stats (
    source TEXT PRIMARY KEY,
    dernier_run TEXT,
    dernier_compte INTEGER DEFAULT 0,
    zero_streak INTEGER DEFAULT 0,
    total_vu INTEGER DEFAULT 0,
    alerte_envoyee INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS attente (
    id_hash TEXT PRIMARY KEY,
    ajoute_le TEXT
);

CREATE TABLE IF NOT EXISTS agences (
    url TEXT PRIMARY KEY,
    nom TEXT,
    vue_sur TEXT,
    first_seen TEXT,
    validee INTEGER DEFAULT 0
);
"""


def maintenant() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Base:
    def __init__(self, path=None):
        self.path = path or config.DB_PATH
        self.cx = sqlite3.connect(self.path)
        self.cx.row_factory = sqlite3.Row
        self.cx.executescript(SCHEMA)
        self.cx.commit()

    def close(self):
        self.cx.close()

    # -------------------------------------------------------------- meta ----
    def get_meta(self, cle, defaut=None):
        r = self.cx.execute("SELECT valeur FROM meta WHERE cle=?", (cle,)).fetchone()
        return r["valeur"] if r else defaut

    def set_meta(self, cle, valeur):
        self.cx.execute(
            "INSERT INTO meta(cle,valeur) VALUES(?,?) "
            "ON CONFLICT(cle) DO UPDATE SET valeur=excluded.valeur",
            (cle, str(valeur)),
        )
        self.cx.commit()

    def del_meta(self, cle):
        self.cx.execute("DELETE FROM meta WHERE cle=?", (cle,))
        self.cx.commit()

    # ------------------------------------------------------------ filtres ---
    def filtres(self) -> dict:
        rows = self.cx.execute("SELECT cle, valeur FROM filtres").fetchall()
        out = {}
        for r in rows:
            try:
                out[r["cle"]] = json.loads(r["valeur"])
            except Exception:
                out[r["cle"]] = r["valeur"]
        return out

    def set_filtre(self, cle, valeur):
        self.cx.execute(
            "INSERT INTO filtres(cle,valeur) VALUES(?,?) "
            "ON CONFLICT(cle) DO UPDATE SET valeur=excluded.valeur",
            (cle, json.dumps(valeur, ensure_ascii=False)),
        )
        self.cx.commit()

    def del_filtre(self, cle):
        self.cx.execute("DELETE FROM filtres WHERE cle=?", (cle,))
        self.cx.commit()

    def reset_filtres(self):
        self.cx.execute("DELETE FROM filtres")
        self.cx.commit()

    # ----------------------------------------------------------- annonces ---
    def par_id(self, id_hash):
        return self.cx.execute("SELECT * FROM annonces WHERE id_hash=?", (id_hash,)).fetchone()

    def par_fingerprint(self, fp):
        if not fp:
            return None
        return self.cx.execute(
            "SELECT * FROM annonces WHERE fingerprint=? ORDER BY first_seen LIMIT 1", (fp,)
        ).fetchone()

    def par_fingerprints(self, fps):
        """Cherche plusieurs empreintes voisines d'un coup (arrondis differents)."""
        fps = [f for f in (fps or []) if f]
        if not fps:
            return None
        trous = ",".join("?" * len(fps))
        return self.cx.execute(
            "SELECT * FROM annonces WHERE fingerprint IN (%s) ORDER BY first_seen LIMIT 1" % trous,
            fps,
        ).fetchone()

    def candidats_fuzzy(self, cp, prix):
        """Annonces du meme code postal a +/-5% de prix, pour le fallback titre."""
        if not cp or not prix:
            return []
        lo, hi = int(prix * 0.95), int(prix * 1.05)
        return self.cx.execute(
            "SELECT * FROM annonces WHERE code_postal=? AND "
            "COALESCE(bouquet, prix) BETWEEN ? AND ?",
            (cp, lo, hi),
        ).fetchall()

    def inserer(self, a, id_hash, fingerprint, priorite, prix_ref):
        now = maintenant()
        hist = json.dumps([{"date": now, "prix": prix_ref}] if prix_ref else [])
        self.cx.execute(
            """INSERT INTO annonces (id_hash, fingerprint, sources, url_principale, url_priorite,
               titre, description, prix, bouquet, rente, code_postal, commune, chambres, surface,
               terrain, peb, type_bien, type_viager, jardin, garage, age_vendeur, avertissements,
               first_seen, last_seen, price_history, notifie)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)""",
            (id_hash, fingerprint, json.dumps([a.source]), a.url, priorite,
             a.titre, a.description[:2000], a.prix, a.bouquet, a.rente, a.code_postal,
             a.commune, a.chambres, a.surface, a.terrain, a.peb, a.type_bien, a.type_viager,
             _b(a.jardin), _b(a.garage), a.age_vendeur, json.dumps(a.avertissements, ensure_ascii=False),
             now, now, hist),
        )
        self.cx.commit()

    def toucher(self, id_hash):
        self.cx.execute("UPDATE annonces SET last_seen=? WHERE id_hash=?", (maintenant(), id_hash))
        self.cx.commit()

    def ajouter_source(self, id_hash, source, url, priorite):
        r = self.par_id(id_hash)
        if not r:
            return
        srcs = json.loads(r["sources"] or "[]")
        if source not in srcs:
            srcs.append(source)
        # le lien envoye suit la priorite : agence > immoweb > portails > agregateurs
        if priorite < (r["url_priorite"] if r["url_priorite"] is not None else 99):
            self.cx.execute(
                "UPDATE annonces SET sources=?, url_principale=?, url_priorite=?, last_seen=? "
                "WHERE id_hash=?",
                (json.dumps(srcs), url, priorite, maintenant(), id_hash),
            )
        else:
            self.cx.execute(
                "UPDATE annonces SET sources=?, last_seen=? WHERE id_hash=?",
                (json.dumps(srcs), maintenant(), id_hash),
            )
        self.cx.commit()

    def enrichir(self, id_hash, a):
        """Complete les champs vides d'une entree existante avec ceux d'une autre source."""
        r = self.par_id(id_hash)
        if not r:
            return
        champs = ["prix", "bouquet", "rente", "code_postal", "commune", "chambres",
                  "surface", "terrain", "peb", "type_bien", "type_viager", "age_vendeur"]
        maj, vals = [], []
        for c in champs:
            nouveau = getattr(a, c, None)
            if nouveau not in (None, "") and (r[c] is None or r[c] == ""):
                maj.append("%s=?" % c)
                vals.append(nouveau)
        if maj:
            vals.append(id_hash)
            self.cx.execute("UPDATE annonces SET %s WHERE id_hash=?" % ",".join(maj), vals)
            self.cx.commit()

    def maj_prix(self, id_hash, prix_ref):
        r = self.par_id(id_hash)
        hist = json.loads(r["price_history"] or "[]")
        hist.append({"date": maintenant(), "prix": prix_ref})
        col = "bouquet" if r["bouquet"] is not None else "prix"
        self.cx.execute(
            "UPDATE annonces SET %s=?, price_history=?, last_seen=? WHERE id_hash=?" % col,
            (prix_ref, json.dumps(hist), maintenant(), id_hash),
        )
        self.cx.commit()

    def marquer_notifie(self, id_hash, baisse=False):
        if baisse:
            self.cx.execute(
                "UPDATE annonces SET notifie=1, last_drop_notif=? WHERE id_hash=?",
                (maintenant(), id_hash),
            )
        else:
            self.cx.execute("UPDATE annonces SET notifie=1 WHERE id_hash=?", (id_hash,))
        self.cx.commit()

    def marquer_tout_vu(self):
        self.cx.execute("UPDATE annonces SET notifie=1")
        self.cx.commit()

    def non_notifiees(self):
        return self.cx.execute(
            "SELECT * FROM annonces WHERE notifie=0 ORDER BY first_seen DESC"
        ).fetchall()

    def recentes(self, n=10):
        return self.cx.execute(
            "SELECT * FROM annonces ORDER BY first_seen DESC LIMIT ?", (n,)
        ).fetchall()

    def compte(self):
        return self.cx.execute("SELECT COUNT(*) c FROM annonces").fetchone()["c"]

    def toutes(self):
        return self.cx.execute("SELECT * FROM annonces").fetchall()

    def supprimer(self, id_hash):
        self.cx.execute("DELETE FROM annonces WHERE id_hash=?", (id_hash,))
        self.cx.execute("DELETE FROM attente WHERE id_hash=?", (id_hash,))
        self.cx.commit()

    def vide(self):
        return self.compte() == 0

    # ------------------------------------------------------------ attente ---
    def mettre_en_attente(self, id_hash):
        self.cx.execute(
            "INSERT OR IGNORE INTO attente(id_hash, ajoute_le) VALUES(?,?)",
            (id_hash, maintenant()),
        )
        self.cx.commit()

    def file_attente(self, limite=15):
        rows = self.cx.execute(
            "SELECT a.* FROM attente t JOIN annonces a ON a.id_hash=t.id_hash "
            "ORDER BY t.ajoute_le LIMIT ?", (limite,)
        ).fetchall()
        return rows

    def taille_attente(self):
        return self.cx.execute("SELECT COUNT(*) c FROM attente").fetchone()["c"]

    def retirer_attente(self, id_hash):
        self.cx.execute("DELETE FROM attente WHERE id_hash=?", (id_hash,))
        self.cx.commit()

    # -------------------------------------------------------------- stats ---
    def enregistrer_stat(self, source, compte):
        r = self.cx.execute("SELECT * FROM source_stats WHERE source=?", (source,)).fetchone()
        streak = 0 if compte > 0 else ((r["zero_streak"] if r else 0) + 1)
        total = (r["total_vu"] if r else 0) + compte
        alerte = 0 if compte > 0 else (r["alerte_envoyee"] if r else 0)
        self.cx.execute(
            "INSERT INTO source_stats(source,dernier_run,dernier_compte,zero_streak,total_vu,alerte_envoyee) "
            "VALUES(?,?,?,?,?,?) ON CONFLICT(source) DO UPDATE SET "
            "dernier_run=excluded.dernier_run, dernier_compte=excluded.dernier_compte, "
            "zero_streak=excluded.zero_streak, total_vu=excluded.total_vu, "
            "alerte_envoyee=excluded.alerte_envoyee",
            (source, maintenant(), compte, streak, total, alerte),
        )
        self.cx.commit()
        return streak

    def stats(self):
        return self.cx.execute("SELECT * FROM source_stats ORDER BY source").fetchall()

    def marquer_alerte_source(self, source):
        self.cx.execute("UPDATE source_stats SET alerte_envoyee=1 WHERE source=?", (source,))
        self.cx.commit()

    # ------------------------------------------------------------ agences ---
    def decouvrir_agence(self, url, nom, vue_sur):
        self.cx.execute(
            "INSERT OR IGNORE INTO agences(url,nom,vue_sur,first_seen) VALUES(?,?,?,?)",
            (url, nom, vue_sur, maintenant()),
        )
        self.cx.commit()

    def agences(self):
        return self.cx.execute("SELECT * FROM agences ORDER BY first_seen DESC").fetchall()


def _b(v):
    return None if v is None else (1 if v else 0)


def reset_base(path=None):
    path = path or config.DB_PATH
    if os.path.exists(path):
        os.remove(path)
