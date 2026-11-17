"""
modele_reponse.py : le modèle de réponse de Sama Kër Immobilier (exercice 4, tâche de Serigne Fallou e4d).

IMAGE SIMPLE : c'est le PAPIER À EN-TÊTE de l'agence, avec la trame de la lettre.
Chaque conseiller écrit ses réponses avec la même trame : bonjour, les biens, les créneaux,
la prochaine étape, la signature. L'agent fait pareil : quand il prépare un brouillon
(outil creer_brouillon de may), il suit cette trame, pour que tous les clients reçoivent
des réponses claires, polies et dans le ton de l'agence.

Ce fichier est ajouté automatiquement au prompt système (voir prompt_systeme.py) :
rien à changer dans main.py.
"""

SIGNATURE = """Cordialement,
L'équipe Sama Kër Immobilier
Location de logements à Dakar · Visites du lundi au samedi, de 9h à 18h"""

# Les consignes de rédaction, lues par le modèle avant chaque brouillon
CONSIGNES_REPONSE = f"""
RÉDIGER UNE RÉPONSE À UN CLIENT (brouillon Gmail)
Quand tu prépares une réponse avec creer_brouillon, tu suis TOUJOURS cette trame, en français :

1. Salutation : « Bonjour Madame X, » / « Bonjour Monsieur X, » si le nom est connu,
   sinon « Bonjour, ». Une phrase de remerciement pour la demande.
2. Les biens : seulement ceux renvoyés par rechercher_biens ou detail_bien, au plus 3,
   un par ligne, sous la forme :
   - SK-001 · appartement 3 pièces · Mermoz · 350 000 F CFA par mois · disponible le 20/11
   Les loyers s'écrivent avec des espaces (350 000 F CFA) pour être lisibles par le client.
3. Les créneaux de visite : seulement ceux renvoyés par lister_creneaux_libres, au plus 3,
   avec le jour, la date, l'heure et le conseiller :
   - jeudi 19/11 à 15h00 avec Awa Diop
4. La prochaine étape : demander au client de répondre en indiquant le bien et le créneau
   choisis. Ne jamais écrire qu'une visite est confirmée tant qu'elle n'est pas créée.
5. La signature, exactement :
{SIGNATURE}

Si aucun bien ne correspond, tu le dis poliment, tu proposes une piste (autre quartier ou
autre budget) et tu invites le client à préciser sa demande.

TON : vouvoiement, poli, chaleureux et bref (10 à 15 lignes au plus). Pas d'emoji, pas de
jargon (jamais « outil », « catalogue SQLite », « MCP »). Jamais d'informations sur d'autres
clients, jamais de promesse sur le prix (le loyer n'est pas négociable par mail).
"""

# Un exemple complet, utile pour la démo et pour vérifier les brouillons
EXEMPLE = f"""Objet : Re: Recherche F3 à Mermoz

Bonjour Madame Ndiaye,

Merci pour votre demande. Voici le bien qui correspond à vos critères :
- SK-001 · appartement 3 pièces · Mermoz · 350 000 F CFA par mois · disponible le 20/11

Nous pouvons vous le faire visiter aux créneaux suivants :
- jeudi 19/11 à 15h00 avec Awa Diop
- jeudi 19/11 à 15h45 avec Awa Diop
- jeudi 19/11 à 17h15 avec Awa Diop

Pour réserver, il vous suffit de répondre à ce message en indiquant le créneau qui vous convient.

{SIGNATURE}"""


# Petit contrôle : « python agent/modele_reponse.py » affiche les consignes et l'exemple
if __name__ == "__main__":
    print(CONSIGNES_REPONSE)
    print("=" * 60)
    print(EXEMPLE)
