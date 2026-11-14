"""
serveur.py : le serveur MCP du catalogue de Sama Kër Immobilier.

Exercice 2, tâche de Serigne Fallou (e2a).

IMAGE SIMPLE : le serveur MCP est le GUICHET du catalogue.
- À l'exercice 1, les outils étaient rangés DANS l'agent (agent/outils.py, code de may).
- Maintenant, le catalogue a son propre guichet : n'importe quel agent
  (le nôtre, ou celui d'une autre équipe) vient y poser ses questions,
  avec un format standard (MCP) que tout le monde comprend.
- Les deux outils gardent EXACTEMENT les mêmes noms, arguments et règles que
  ceux de may : c'est ce qui garantit « les mêmes résultats qu'à l'exercice 1 ».

Le serveur expose :
    2 OUTILS (des actions)    : rechercher_biens(...) et detail_bien(id_bien)
    1 RESSOURCE (un document) : agence://infos, écrite par Atou (ressource_agence.py)

Lancement, depuis la racine du dépôt :
    python serveur_mcp/serveur.py          # transport local (stdio)
    python serveur_mcp/serveur.py http     # transport HTTP sur http://127.0.0.1:8000/mcp

Prérequis : la base doit exister (python serveur_mcp/creer_catalogue.py)
et le paquet mcp en version 1 (pip install "mcp<2"), car en version 2
FastMCP a changé de nom.
"""

import sqlite3
import sys
import unicodedata
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

# La base créée par le script de may, dans le même dossier que ce fichier
CHEMIN_BASE = Path(__file__).parent / "catalogue.db"
TYPES_VALIDES = ("studio", "appartement", "villa", "chambre")
MAX_RESULTATS = (
    5  # on ne renvoie pas tout le catalogue : la réponse reste légère pour le modèle
)

# On crée le serveur et on lui donne un nom (visible dans l'inspecteur MCP)
mcp = FastMCP("catalogue-sama-ker")


# ---------------------------------------------------------------------------
# Fonctions internes (pas visibles par le modèle) : reprises de agent/outils.py
# ---------------------------------------------------------------------------


def _sans_accents(texte: str) -> str:
    """'Sacré-Cœur' -> 'sacre coeur' : pour que « sacre coeur » trouve « Sacré-Cœur »."""
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
        connexion.row_factory = sqlite3.Row  # pour avoir les colonnes par leur nom
        lignes = connexion.execute("SELECT * FROM biens").fetchall()
    biens = []
    for ligne in lignes:
        bien = dict(ligne)
        bien["meuble"] = bool(bien["meuble"])  # 1/0 -> True/False
        bien["disponible"] = bool(bien["disponible"])
        biens.append(bien)
    return biens


# ---------------------------------------------------------------------------
# Les outils : @mcp.tool() les publie au guichet.
# Le texte entre """ """ est la NOTICE lue par le modèle ;
# les types (str, int, Optional...) lui disent quels arguments donner.
# ---------------------------------------------------------------------------


@mcp.tool()
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
        return {
            "erreur": f"type_bien « {type_bien} » inconnu.",
            "conseil": f"Utiliser une de ces valeurs : {', '.join(TYPES_VALIDES)}.",
        }
    if pieces is not None and pieces < 1:
        return {
            "erreur": "pieces doit être un entier positif.",
            "conseil": "Un F3 = 3.",
        }
    if loyer_max is not None and loyer_max <= 0:
        return {
            "erreur": "loyer_max doit être un montant positif en F CFA.",
            "conseil": "Écrire 400000 pour 400 000 F.",
        }

    # 2. Lecture de la base
    try:
        biens = _lire_biens()
    except Exception as e:  # base absente ou illisible
        return {
            "erreur": f"Catalogue inaccessible : {e}",
            "conseil": "Dire au client que la recherche est momentanément impossible et transmettre à un conseiller.",
        }

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

    resultats.sort(key=lambda b: b["loyer"])  # les moins chers d'abord

    # 4. Réponse : on dit clairement quand rien ne correspond
    if not resultats:
        return {
            "nombre": 0,
            "biens": [],
            "message": "Aucun bien disponible ne correspond à ces critères dans le catalogue.",
        }
    return {
        "nombre": len(resultats),
        "biens": resultats[:MAX_RESULTATS],
        "message": f"{len(resultats)} bien(s) trouvé(s)"
        + (
            f", les {MAX_RESULTATS} moins chers sont affichés."
            if len(resultats) > MAX_RESULTATS
            else "."
        ),
    }


@mcp.tool()
def detail_bien(id_bien: str) -> dict:
    """Donne la fiche complète d'un bien du catalogue (adresse, loyer, pièces, meublé, date d'entrée).
    À utiliser quand le client pose une question sur un bien précis déjà trouvé par rechercher_biens.

    Args:
        id_bien: identifiant du bien, au format "SK-001".
    """
    id_bien = id_bien.strip().upper()
    if not (id_bien.startswith("SK-") and id_bien[3:].isdigit()):
        return {
            "erreur": f"Identifiant « {id_bien} » mal formé.",
            "conseil": "Utiliser l'identifiant renvoyé par rechercher_biens, par exemple SK-001.",
        }
    try:
        biens = _lire_biens()
    except Exception as e:
        return {
            "erreur": f"Catalogue inaccessible : {e}",
            "conseil": "Transmettre la demande à un conseiller.",
        }
    for b in biens:
        if b["id"] == id_bien:
            return {"bien": b}
    return {
        "erreur": f"Aucun bien {id_bien} dans le catalogue.",
        "conseil": "Ne pas inventer de bien : relancer rechercher_biens.",
    }


# ---------------------------------------------------------------------------
# La RESSOURCE « agence » (horaires, zones, conditions), écrite par Atou (e2b).
# Une ressource, c'est un document que le modèle peut LIRE (pas une action).
# ---------------------------------------------------------------------------
try:
    from ressource_agence import enregistrer_ressource_agence

    enregistrer_ressource_agence(mcp)
except ImportError:
    pass  # si le fichier d'Atou manque, le serveur marche quand même avec ses 2 outils


# ---------------------------------------------------------------------------
# Démarrage du serveur
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "http":
        # HTTP : le serveur écoute sur http://127.0.0.1:8000/mcp (voir MCP_URL dans .env)
        mcp.run(transport="streamable-http")
    else:
        # stdio : l'agent lance le serveur lui-même et lui parle par l'entrée/sortie standard
        mcp.run()
