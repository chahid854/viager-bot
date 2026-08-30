# -*- coding: utf-8 -*-
"""Sonde de decouverte : trouve la vraie page de liste d'un site.

`python sonde.py viagerplus.be leefrente.be ...`

Pour chaque domaine : essaie www/sans-www, https/http, puis liste les pages
internes qui ressemblent a un catalogue et compte les liens d'annonces qu'elles
contiennent. Sert a corriger une URL dans config.py quand une source se tait.
"""

import re
import sys
import urllib3
from collections import Counter

import requests
from bs4 import BeautifulSoup

urllib3.disable_warnings()
for _f in (sys.stdout, sys.stderr):
    try:
        _f.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
     "Accept-Language": "fr-BE,fr;q=0.9,nl;q=0.8"}

CATALOGUE = re.compile(
    r"(bien|goed|aanbod|viager|lijfrente|te-koop|a-vendre|propriet|panden|"
    r"woningen|offre|annonce|realisation|vastgoed|properties|catalog)", re.I)
ANNONCE = re.compile(r"/(bien|goed|pand|woning|annonce|property|detail|te-koop|"
                     r"a-vendre|viager|lijfrente|id)[/-]", re.I)


def essaie(url, verify=True):
    try:
        r = requests.get(url, headers=H, timeout=20, verify=verify, allow_redirects=True)
        return r
    except Exception as e:
        return e


def racine_vivante(domaine):
    for prefixe in ("https://www.", "https://", "http://www.", "http://"):
        for verify in (True, False):
            r = essaie(prefixe + domaine, verify)
            if isinstance(r, requests.Response) and r.status_code < 400:
                return r, prefixe + domaine, verify
    return None, None, True


def sonder(domaine):
    print("\n=== %s ===" % domaine)
    r, base_url, verify = racine_vivante(domaine)
    if r is None:
        print("  injoignable (DNS, connexion refusee ou 4xx sur toutes les variantes)")
        return
    print("  vivant : %s -> %s (%s, verify=%s)" % (base_url, r.url, r.status_code, verify))
    s = BeautifulSoup(r.text, "lxml")
    liens = {}
    for a in s.find_all("a", href=True):
        h = a["href"]
        if h.startswith(("mailto:", "tel:", "#", "javascript:")):
            continue
        u = requests.compat.urljoin(r.url, h)
        if requests.compat.urlsplit(u).netloc != requests.compat.urlsplit(r.url).netloc:
            continue
        if CATALOGUE.search(u):
            liens[u.split("#")[0]] = a.get_text(" ", strip=True)[:40]

    for form in s.find_all("form")[:4]:
        action = form.get("action") or "(page courante)"
        champs = [i.get("name") for i in form.find_all(("input", "select")) if i.get("name")]
        if champs:
            print("  form action=%s champs=%s" % (action, champs[:8]))

    directes = [u for u in liens if ANNONCE.search(u)]
    print("  %d lien(s) catalogue, dont %d ressemblant a des annonces" % (len(liens), len(directes)))
    candidats = [u for u in liens if u not in directes][:12]
    for u in candidats:
        rr = essaie(u, verify)
        if not isinstance(rr, requests.Response) or rr.status_code >= 400:
            continue
        ss = BeautifulSoup(rr.text, "lxml")
        n = len({requests.compat.urljoin(rr.url, a["href"])
                 for a in ss.find_all("a", href=True) if ANNONCE.search(a["href"])})
        marque = " <<< CANDIDAT" if n >= 4 else ""
        print("   %3d annonces  %s  (%s)%s" % (n, u, liens[u], marque))


if __name__ == "__main__":
    for d in sys.argv[1:]:
        sonder(d)
