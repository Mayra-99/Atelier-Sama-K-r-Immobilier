"""
serveur.py : le serveur MCP du catalogue de Sama Kër Immobilier.

Exercice 2, tâche de Serigne Fallou (e2a).

IMAGE SIMPLE : le serveur MCP est le GUICHET du catalogue.
- Avant (exercice 1), les outils étaient rangés DANS l'agent.
- Maintenant, le catalogue a son propre guichet : n'importe quel agent
  (le nôtre, ou celui d'une autre équipe) vient y poser ses questions,
  avec un format standard (MCP) que tout le monde comprend.

Le serveur expose 2 OUTILS (des actions que le modèle peut appeler) :
    rechercher_biens(...)  -> liste des biens libres qui correspondent
    detail_bien(id_bien)   -> fiche complète d'un bien

Lancement, depuis la racine du dépôt :
    python serveur_mcp/serveur.py          # transport local (stdio)
    python serveur_mcp/serveur.py http     # transport HTTP sur http://127.0.0.1:8000/mcp

Prérequis : la base doit exister (python serveur_mcp/creer_catalogue.py)
et le paquet mcp en version 1 (pip install "mcp<2"), car en version 2
FastMCP a changé de nom.
"""

import sqlite3
import sys
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

# La base créée par le script de may, dans le même dossier que ce fichier
CHEMIN_BASE = Path(__file__).parent / "catalogue.db"

# On crée le serveur et on lui donne un nom (visible dans l'inspecteur MCP)
mcp = FastMCP("catalogue-sama-ker")


# ---------------------------------------------------------------------------
# Fonctions utilitaires (pas visibles par le modèle)
# ---------------------------------------------------------------------------

def _connexion() -> sqlite3.Connection:
    """Ouvre la base. Si elle n'existe pas, on lève une erreur claire."""
    if not CHEMIN_BASE.exists():
        raise FileNotFoundError(
            "La base catalogue.db n'existe pas. Lancer d'abord : python serveur_mcp/creer_catalogue.py"
        )
    connexion = sqlite3.connect(CHEMIN_BASE)
    connexion.row_factory = sqlite3.Row      # chaque ligne se lit comme un dictionnaire
    return connexion


def _en_dict(ligne: sqlite3.Row) -> dict:
    """Transforme une ligne SQLite en dictionnaire lisible (1/0 -> True/False)."""
    bien = dict(ligne)
    bien["meuble"] = bool(bien["meuble"])
    bien["disponible"] = bool(bien["disponible"])
    return bien


# ---------------------------------------------------------------------------
# Les outils : le texte entre """ """ est la DESCRIPTION lue par le modèle.
# Les types (str, int, Optional...) disent au modèle quels arguments donner.
# ---------------------------------------------------------------------------

@mcp.tool()
def rechercher_biens(
    quartier: Optional[str] = None,
    type_bien: Optional[str] = None,
    pieces: Optional[int] = None,
    loyer_max: Optional[int] = None,
    meuble: Optional[bool] = None,
) -> dict:
    """Cherche dans le catalogue de Sama Kër Immobilier les biens À LOUER encore libres.

    Tous les arguments sont facultatifs ; ne remplir que ceux donnés par le client.
    - quartier : quartier de Dakar, ex. "Mermoz", "Almadies", "Parcelles Assainies".
    - type_bien : "studio", "appartement", "villa" ou "chambre".
    - pieces : nombre de pièces exact (un F3 = 3).
    - loyer_max : loyer mensuel maximum en F CFA, en chiffres (400 000 F -> 400000).
    - meuble : true pour meublé, false pour non meublé.

    Renvoie {"nombre": N, "biens": [...]}. Si nombre vaut 0, aucun bien ne correspond :
    il faut le dire au client, sans rien inventer.
    """
    # On construit la requête morceau par morceau, avec des « ? » (jamais de texte collé)
    conditions = ["disponible = 1"]          # on ne propose jamais un bien déjà loué
    valeurs = []
    if quartier:
        conditions.append("LOWER(quartier) = LOWER(?)")
        valeurs.append(quartier.strip())
    if type_bien:
        conditions.append("LOWER(type) = LOWER(?)")
        valeurs.append(type_bien.strip())
    if pieces is not None:
        conditions.append("pieces = ?")
        valeurs.append(pieces)
    if loyer_max is not None:
        conditions.append("loyer <= ?")
        valeurs.append(loyer_max)
    if meuble is not None:
        conditions.append("meuble = ?")
        valeurs.append(int(meuble))

    requete = "SELECT * FROM biens WHERE " + " AND ".join(conditions) + " ORDER BY loyer"
    try:
        with _connexion() as connexion:
            lignes = connexion.execute(requete, valeurs).fetchall()
    except Exception as erreur:
        # Erreur renvoyée sous une forme que le modèle peut lire et expliquer
        return {"erreur": f"Catalogue indisponible : {erreur}"}

    biens = [_en_dict(l) for l in lignes]
    return {"nombre": len(biens), "biens": biens}


@mcp.tool()
def detail_bien(id_bien: str) -> dict:
    """Donne la fiche complète d'un bien du catalogue à partir de son identifiant.

    - id_bien : identifiant du bien, au format "SK-001" (renvoyé par rechercher_biens).

    Renvoie la fiche du bien (adresse, loyer, pièces, disponibilité...),
    ou {"erreur": ...} si l'identifiant n'existe pas.
    """
    try:
        with _connexion() as connexion:
            ligne = connexion.execute(
                "SELECT * FROM biens WHERE UPPER(id) = UPPER(?)", (id_bien.strip(),)
            ).fetchone()
    except Exception as erreur:
        return {"erreur": f"Catalogue indisponible : {erreur}"}

    if ligne is None:
        return {"erreur": f"Aucun bien avec l'identifiant {id_bien}. Les identifiants vont de SK-001 à SK-030."}
    return _en_dict(ligne)


# ---------------------------------------------------------------------------
# La RESSOURCE « agence » (horaires, zones, conditions), écrite par Atou (e2b).
# Une ressource, c'est un document que le modèle peut LIRE (pas une action).
# Tant que le fichier d'Atou n'est pas dans le dépôt, le serveur marche sans.
# ---------------------------------------------------------------------------
try:
    from ressource_agence import enregistrer_ressource_agence
    enregistrer_ressource_agence(mcp)
except ImportError:
    pass


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
