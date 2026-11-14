"""
creer_catalogue.py : crée la base SQLite du catalogue de Sama Kër Immobilier.

Exercice 1, tâche de may (e1b).

Ce script :
  1. lit la liste BIENS écrite par Fallou dans biens.py ;
  2. crée (ou recrée) le fichier catalogue.db à côté de ce script ;
  3. y range les 30 biens dans une table « biens ».

Lancement, depuis la racine du dépôt :
    python serveur_mcp/creer_catalogue.py

On peut le relancer autant de fois qu'on veut : la table est vidée puis remplie
à nouveau, donc il n'y a jamais de doublon.
"""

import sqlite3                 # SQLite est inclus dans Python : rien à installer
from pathlib import Path       # pour construire des chemins qui marchent sous Windows

from biens import BIENS        # la liste des 30 biens (fichier de Fallou, même dossier)

# Le fichier de base est créé dans le même dossier que ce script : serveur_mcp/catalogue.db
DOSSIER = Path(__file__).parent
CHEMIN_BASE = DOSSIER / "catalogue.db"

# Description de la table : une colonne par clé des dictionnaires de biens.py.
# SQLite n'a pas de vrai type « booléen » : on range True/False comme 1/0 (INTEGER).
CREATION_TABLE = """
CREATE TABLE IF NOT EXISTS biens (
    id            TEXT PRIMARY KEY,   -- identifiant unique, ex. "SK-001"
    type          TEXT    NOT NULL,   -- studio, appartement, villa ou chambre
    quartier      TEXT    NOT NULL,   -- quartier de Dakar
    adresse       TEXT    NOT NULL,   -- adresse fictive
    pieces        INTEGER NOT NULL,   -- nombre de pièces (F3 = 3)
    loyer         INTEGER NOT NULL,   -- loyer mensuel en F CFA
    meuble        INTEGER NOT NULL,   -- 1 = meublé, 0 = non meublé
    disponible    INTEGER NOT NULL,   -- 1 = libre, 0 = déjà loué
    disponible_le TEXT                -- date d'entrée possible (AAAA-MM-JJ) ou NULL
)
"""

# Requête d'insertion : les « ? » sont remplacés par les valeurs, dans l'ordre.
# On n'assemble jamais une requête SQL avec du texte collé à la main (risque d'injection SQL).
INSERTION = """
INSERT INTO biens (id, type, quartier, adresse, pieces, loyer, meuble, disponible, disponible_le)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
"""


def verifier(bien: dict) -> None:
    """Vérifie qu'un bien a toutes les clés attendues, avec le bon type.
    Si quelque chose manque, on arrête tout avec un message clair plutôt que
    de créer une base à moitié fausse."""
    attendu = {
        "id": str, "type": str, "quartier": str, "adresse": str,
        "pieces": int, "loyer": int, "meuble": bool, "disponible": bool,
    }
    for cle, type_attendu in attendu.items():
        if cle not in bien:
            raise ValueError(f"Le bien {bien.get('id', '?')} n'a pas la clé « {cle} ».")
        if not isinstance(bien[cle], type_attendu):
            raise ValueError(f"Le bien {bien['id']} : « {cle} » devrait être de type {type_attendu.__name__}.")
    if "disponible_le" not in bien:
        raise ValueError(f"Le bien {bien['id']} n'a pas la clé « disponible_le » (mettre None si loué).")


def creer_catalogue() -> int:
    """Crée la table et y range tous les biens. Renvoie le nombre de biens enregistrés."""
    # 1. Contrôle des données avant de toucher à la base
    for bien in BIENS:
        verifier(bien)
    identifiants = [b["id"] for b in BIENS]
    if len(identifiants) != len(set(identifiants)):
        raise ValueError("Deux biens ont le même identifiant dans biens.py.")

    # 2. Ouverture de la base (le fichier est créé s'il n'existe pas)
    with sqlite3.connect(CHEMIN_BASE) as connexion:
        curseur = connexion.cursor()
        curseur.execute(CREATION_TABLE)
        curseur.execute("DELETE FROM biens")          # on vide pour pouvoir relancer sans doublon

        # 3. Insertion de chaque bien, dans l'ordre des colonnes
        for b in BIENS:
            curseur.execute(INSERTION, (
                b["id"], b["type"], b["quartier"], b["adresse"],
                b["pieces"], b["loyer"],
                int(b["meuble"]), int(b["disponible"]),   # True/False -> 1/0
                b["disponible_le"],                        # None devient NULL
            ))
        # « with » enregistre (commit) automatiquement à la fin du bloc

        # 4. Petit contrôle : on recompte ce qui est vraiment dans la base
        nombre = curseur.execute("SELECT COUNT(*) FROM biens").fetchone()[0]
    return nombre


if __name__ == "__main__":
    total = creer_catalogue()
    print(f"Base créée : {CHEMIN_BASE}")
    print(f"{total} biens enregistrés dans la table « biens ».")
