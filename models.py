# -*- coding: utf-8 -*-
"""Structure commune a toutes les sources."""

from dataclasses import dataclass, field, asdict
from typing import Optional, List


@dataclass
class Annonce:
    source: str                       # nom de la source (config.SOURCES[].name)
    url: str                          # url de l'annonce
    titre: str = ""
    source_id: Optional[str] = None   # identifiant natif chez la source, si dispo
    description: str = ""
    localisation: str = ""            # champ localisation brut (ville, adresse)
    prix: Optional[int] = None        # prix affiche / valeur venale
    bouquet: Optional[int] = None
    rente: Optional[int] = None       # rente mensuelle en euros
    code_postal: Optional[str] = None
    commune: Optional[str] = None
    chambres: Optional[int] = None
    surface: Optional[int] = None     # m2 habitables
    terrain: Optional[int] = None     # m2 de terrain
    peb: Optional[str] = None         # A..G
    type_bien: Optional[str] = None   # maison | appartement | terrain | autre
    type_viager: Optional[str] = None # occupe | libre | nue-propriete | inconnu
    jardin: Optional[bool] = None
    garage: Optional[bool] = None
    age_vendeur: Optional[int] = None
    agence_url: Optional[str] = None  # site de l'agence, pour la decouverte auto
    agence_nom: Optional[str] = None  # nom de l'agence publiante, si le site le donne
    kind: str = "portail"             # categorie de source, pour la priorite du lien
    avertissements: List[str] = field(default_factory=list)

    def texte(self) -> str:
        return " ".join(filter(None, [self.titre, self.localisation, self.description]))

    def to_dict(self) -> dict:
        return asdict(self)
