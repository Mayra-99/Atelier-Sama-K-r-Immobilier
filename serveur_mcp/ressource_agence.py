"""
Ressource MCP « agence » (exercice 2, tâche d'Atou).

Image simple : un OUTIL, c'est un serveur de restaurant à qui on demande
quelque chose (« cherche-moi un F3 ») et qui agit. Une RESSOURCE, c'est le
menu affiché au mur : une information fixe que l'agent peut LIRE, sans rien
déclencher. Ici, le « menu » de l'agence : horaires, zones, conditions.

Utilisation dans le serveur de Serigne Fallou (serveur_mcp/serveur.py) :

    from mcp.server.fastmcp import FastMCP
    from ressource_agence import enregistrer_ressource_agence

    mcp = FastMCP("catalogue-sama-ker")
    enregistrer_ressource_agence(mcp)   # une seule ligne à ajouter
"""

import json

# 1. Les informations de l'agence, rangées dans un dictionnaire Python.
#    On les garde ici, à un seul endroit : si un horaire change, on modifie
#    juste ce bloc. Les règles de visite reprennent celles de l'énoncé.
INFOS_AGENCE = {
    "nom": "Sama Kër Immobilier",
    "ville": "Dakar",
    "horaires_visite": {
        "jours": "du lundi au samedi",
        "heures": "9h00 - 18h00",
        "duree_visite_minutes": 45,
        "fuseau": "Africa/Dakar",
    },
    "zones_couvertes": [
        "Plateau", "Médina", "Fann Résidence", "Point E", "Mermoz", "Sacré-Cœur",
        "Liberté 6", "Sicap Baobab", "HLM", "Grand Yoff", "Parcelles Assainies",
        "Ouest Foire", "Yoff", "Ouakam", "Mamelles", "Ngor", "Almadies",
    ],
    "conditions_location": [
        "Caution : 2 mois de loyer",
        "Avance : 1 mois de loyer",
        "Frais d'agence : 1 mois de loyer",
        "Pièces : carte d'identité et justificatif de revenus",
        "Bail d'un an minimum, renouvelable",
    ],
    "contact": "Toute visite est confirmée par un conseiller avant l'envoi du rendez-vous.",
}


def enregistrer_ressource_agence(mcp):
    """Ajoute la ressource « agence » au serveur MCP reçu en paramètre."""

    # 2. Le décorateur @mcp.resource donne une ADRESSE à la ressource
    #    (une URI, comme l'adresse d'une page web). Le client MCP la lira
    #    avec cette adresse : agence://infos
    @mcp.resource(
        "agence://infos",
        name="infos_agence",
        description="Horaires de visite, zones couvertes et conditions de location de l'agence.",
        mime_type="application/json",
    )
    def infos_agence() -> str:
        # 3. Une ressource renvoie du texte : on transforme le dictionnaire
        #    en JSON. ensure_ascii=False garde les accents (Médina, Sacré-Cœur).
        return json.dumps(INFOS_AGENCE, ensure_ascii=False, indent=2)

    return infos_agence


# 4. Petit test autonome : `python serveur_mcp/ressource_agence.py`
#    lance un mini-serveur qui n'a QUE la ressource, pour vérifier avec
#    l'inspecteur MCP sans attendre le serveur complet.
if __name__ == "__main__":
    from mcp.server.fastmcp import FastMCP

    serveur_test = FastMCP("test-ressource-agence")
    enregistrer_ressource_agence(serveur_test)
    serveur_test.run()  # transport stdio par défaut
