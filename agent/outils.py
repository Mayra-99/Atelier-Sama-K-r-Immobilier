"""
outils.py : les deux outils métier de l'agent (exercice 1, tâche de may e1c).

  - rechercher_biens : trouve les biens du catalogue qui correspondent à un besoin
  - detail_bien      : donne la fiche complète d'un bien à partir de son identifiant

Rappel du principe (axe 1 de la veille, « appel d'outils ») :
  * le MODÈLE lit la description de chaque outil (le texte entre triple guillemets)
    et décide lui-même quand l'appeler et avec quels arguments ;
  * NOTRE PROGRAMME exécute vraiment la recherche dans la base SQLite ;
  * le résultat revient au modèle, qui s'en sert pour répondre.

Les erreurs ne font jamais planter l'agent : elles sont renvoyées au modèle sous la
forme {"erreur": "...", "conseil": "..."} pour qu'il puisse corriger son appel ou
expliquer au client.

À l'exercice 2, ces fonctions seront remplacées par le serveur MCP.
"""

import sqlite3
import unicodedata
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool

# La base est créée par serveur_mcp/creer_catalogue.py
CHEMIN_BASE = Path(__file__).resolve().parent.parent / "serveur_mcp" / "catalogue.db"

TYPES_VALIDES = ("studio", "appartement", "villa", "chambre")
MAX_RESULTATS = 5   # on ne renvoie pas tout le catalogue : le « bureau » du modèle reste léger


# ---------------------------------------------------------------- outils internes

def _sans_accents(texte: str) -> str:
    """'Sacré-Cœur' -> 'sacre-coeur' : pour que « sacre coeur » trouve « Sacré-Cœur »."""
    texte = texte.replace("œ", "oe").replace("Œ", "Oe")
    texte = unicodedata.normalize("NFD", texte)
    texte = "".join(c for c in texte if unicodedata.category(c) != "Mn")
    return texte.lower().replace("-", " ").strip()


def _lire_biens() -> list[dict]:
    """Lit toute la table « biens » et renvoie une liste de dictionnaires."""
    if not CHEMIN_BASE.exists():
        raise FileNotFoundError(
            "La base catalogue.db n'existe pas. Lancer : python serveur_mcp/creer_catalogue.py"
        )
    with sqlite3.connect(CHEMIN_BASE) as connexion:
        connexion.row_factory = sqlite3.Row          # pour avoir les colonnes par leur nom
        lignes = connexion.execute("SELECT * FROM biens").fetchall()
    biens = []
    for ligne in lignes:
        bien = dict(ligne)
        bien["meuble"] = bool(bien["meuble"])         # 1/0 -> True/False
        bien["disponible"] = bool(bien["disponible"])
        biens.append(bien)
    return biens


# ---------------------------------------------------------------- outil 1

@tool
def rechercher_biens(
    quartier: Optional[str] = None,
    type_bien: Optional[str] = None,
    pieces: Optional[int] = None,
    loyer_max: Optional[int] = None,
    meuble: Optional[bool] = None,
) -> dict:
    """Cherche dans le catalogue de l'agence les biens À LOUER qui correspondent au besoin du client.
    Ne renvoie que des biens disponibles. Tous les arguments sont facultatifs : ne remplir que ceux
    que le client a précisés.

    Args:
        quartier: quartier de Dakar demandé, par exemple "Mermoz", "Almadies", "Sacré-Cœur".
        type_bien: "studio", "appartement", "villa" ou "chambre".
        pieces: nombre de pièces exact. Un F3 = 3 pièces, un F4 = 4 pièces.
        loyer_max: loyer mensuel maximum en F CFA, nombre entier sans espace (ex. 400000).
        meuble: True si le client veut un meublé, False s'il veut un non meublé.
    """
    # 1. Validation des arguments : message clair au modèle plutôt qu'un plantage
    if type_bien is not None and type_bien.lower() not in TYPES_VALIDES:
        return {"erreur": f"type_bien « {type_bien} » inconnu.",
                "conseil": f"Utiliser une de ces valeurs : {', '.join(TYPES_VALIDES)}."}
    if pieces is not None and pieces < 1:
        return {"erreur": "pieces doit être un entier positif.", "conseil": "Un F3 = 3."}
    if loyer_max is not None and loyer_max <= 0:
        return {"erreur": "loyer_max doit être un montant positif en F CFA.",
                "conseil": "Écrire 400000 pour 400 000 F."}

    # 2. Lecture de la base
    try:
        biens = _lire_biens()
    except Exception as e:                       # base absente ou illisible
        return {"erreur": f"Catalogue inaccessible : {e}",
                "conseil": "Dire au client que la recherche est momentanément impossible et transmettre à un conseiller."}

    # 3. Filtrage : on garde seulement ce qui correspond à TOUS les critères donnés
    resultats = []
    for b in biens:
        if not b["disponible"]:
            continue
        if quartier and _sans_accents(quartier) not in _sans_accents(b["quartier"]):
            continue
        if type_bien and b["type"] != type_bien.lower():
            continue
        if pieces is not None and b["pieces"] != pieces:
            continue
        if loyer_max is not None and b["loyer"] > loyer_max:
            continue
        if meuble is not None and b["meuble"] != meuble:
            continue
        resultats.append(b)

    resultats.sort(key=lambda b: b["loyer"])     # les moins chers d'abord

    # 4. Réponse : on dit clairement quand rien ne correspond (critère de l'exercice 1)
    if not resultats:
        return {"nombre": 0, "biens": [],
                "message": "Aucun bien disponible ne correspond à ces critères dans le catalogue."}
    return {"nombre": len(resultats), "biens": resultats[:MAX_RESULTATS],
            "message": f"{len(resultats)} bien(s) trouvé(s)"
                       + (f", les {MAX_RESULTATS} moins chers sont affichés." if len(resultats) > MAX_RESULTATS else ".")}


# ---------------------------------------------------------------- outil 2

@tool
def detail_bien(id_bien: str) -> dict:
    """Donne la fiche complète d'un bien du catalogue (adresse, loyer, pièces, meublé, date d'entrée).
    À utiliser quand le client pose une question sur un bien précis déjà trouvé par rechercher_biens.

    Args:
        id_bien: identifiant du bien, au format "SK-001".
    """
    id_bien = id_bien.strip().upper()
    if not (id_bien.startswith("SK-") and id_bien[3:].isdigit()):
        return {"erreur": f"Identifiant « {id_bien} » mal formé.",
                "conseil": "Utiliser l'identifiant renvoyé par rechercher_biens, par exemple SK-001."}
    try:
        biens = _lire_biens()
    except Exception as e:
        return {"erreur": f"Catalogue inaccessible : {e}",
                "conseil": "Transmettre la demande à un conseiller."}
    for b in biens:
        if b["id"] == id_bien:
            return {"bien": b}
    return {"erreur": f"Aucun bien {id_bien} dans le catalogue.",
            "conseil": "Ne pas inventer de bien : relancer rechercher_biens."}


# La liste que l'agent recevra (exercice 1, tâche e1e)
OUTILS = [rechercher_biens, detail_bien]
