# -*- coding: utf-8 -*-
"""Registre des scrapers. Interface commune : fetch(source, ctx) -> list[Annonce]."""

import importlib
import logging

log = logging.getLogger("scrapers")
_CACHE = {}


def charger(nom_module):
    if nom_module not in _CACHE:
        _CACHE[nom_module] = importlib.import_module("scrapers.%s" % nom_module)
    return _CACHE[nom_module]


def fetch(source, ctx=None):
    module = charger(source.get("module", "generic"))
    return module.fetch(source, ctx)
