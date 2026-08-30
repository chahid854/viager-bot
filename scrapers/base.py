# -*- coding: utf-8 -*-
"""Socle commun a tous les scrapers : HTTP poli, robots.txt, utilitaires HTML."""

import logging
import random
import re
import time
import urllib.robotparser as robotparser
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

import config

log = logging.getLogger("scraper")

_ROBOTS = {}
_ROBOTS_UA = "*"


class RobotsInterdit(Exception):
    pass


def robots_autorise(url: str) -> bool:
    """Lit robots.txt et respecte ses Disallow.

    Important : on telecharge le fichier avec un vrai User-Agent de navigateur.
    RobotFileParser.read() utilise sinon "Python-urllib", que beaucoup de WAF
    renvoient en 403 — et un 403 sur robots.txt est interprete par la librairie
    comme "tout est interdit", ce qui coupait des sites qui n'interdisent rien.
    Un robots.txt illisible est traite comme absent : on continue, en gardant le
    delai de 2-5 s entre requetes.
    """
    if not config.RESPECT_ROBOTS:
        return True
    p = urlsplit(url)
    racine = "%s://%s" % (p.scheme, p.netloc)

    if racine not in _ROBOTS:
        rp = None
        try:
            r = requests.get(racine + "/robots.txt", timeout=10,
                             headers={"User-Agent": config.USER_AGENTS[0],
                                      "Accept": "text/plain,*/*"})
            if r.status_code == 200 and len(r.text) < 500000:
                rp = robotparser.RobotFileParser()
                rp.parse(r.text.splitlines())
            else:
                log.debug("robots.txt %s : HTTP %s, considere absent", racine, r.status_code)
        except Exception as e:
            log.debug("robots.txt %s illisible (%s), considere absent", racine, e)
        _ROBOTS[racine] = rp

    rp = _ROBOTS[racine]
    if rp is None:
        return True
    try:
        return rp.can_fetch(_ROBOTS_UA, url)
    except Exception:
        return True


class Fetcher:
    """Une session par source (donc par thread)."""

    def __init__(self, source_name="?", verify=True):
        self.name = source_name
        # verify=False sert aux sites dont le certificat ne couvre pas le
        # sous-domaine ("hostname mismatch") : le contenu reste public, la seule
        # chose qu'on perd est l'authentification du serveur.
        self.verify = verify
        self.session = requests.Session()
        self.ua = random.choice(config.USER_AGENTS)
        self.session.headers.update({
            "User-Agent": self.ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "fr-BE,fr;q=0.9,nl-BE;q=0.8,nl;q=0.7,en;q=0.5",
            # pas d'Accept-Encoding force : requests annonce lui-meme ce qu'il
            # sait decompresser. L'imposer avec "br" renvoie du brotli illisible.
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        })
        self._premier = True

    def _pause(self):
        if self._premier:
            self._premier = False
            return
        time.sleep(random.uniform(config.DELAI_MIN, config.DELAI_MAX))

    def get(self, url, **kw):
        if not robots_autorise(url):
            log.info("[%s] robots.txt interdit %s — ignore", self.name, url)
            raise RobotsInterdit(url)
        self._pause()
        kw.setdefault("verify", self.verify)
        r = self.session.get(url, timeout=config.HTTP_TIMEOUT, **kw)
        r.raise_for_status()
        return r

    def html(self, url, **kw):
        r = self.get(url, **kw)
        return BeautifulSoup(r.text, "lxml")

    def json(self, url, **kw):
        headers = kw.pop("headers", {})
        headers.setdefault("Accept", "application/json, text/plain, */*")
        r = self.get(url, headers=headers, **kw)
        return r.json()


# ------------------------------------------------------------- utilitaires --
ESPACES = re.compile(r"\s+")


def texte(el, limite=1500):
    if el is None:
        return ""
    return ESPACES.sub(" ", el.get_text(" ", strip=True))[:limite]


def absolu(base, href):
    return urljoin(base, (href or "").strip())


def domaine(url):
    p = urlsplit(url)
    return "%s://%s" % (p.scheme, p.netloc)


def pages_de(source):
    """Deroule les urls d'une source en remplacant {page}."""
    urls, vues = [], set()
    n_pages = int(source.get("pages") or 1)
    for gabarit in source.get("urls", []):
        if "{page}" in gabarit:
            for n in range(1, n_pages + 1):
                u = gabarit.format(page=n)
                if u not in vues:
                    vues.add(u)
                    urls.append(u)
        else:
            if gabarit not in vues:
                vues.add(gabarit)
                urls.append(gabarit)
    return urls
