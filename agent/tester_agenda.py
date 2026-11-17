"""
tester_agenda.py : essaie les 4 actions de l'agenda SANS passer par le modèle (exercice 3, Atou).

On appelle les outils directement, comme le ferait l'agent, sur l'agenda d'Awa (Mermoz),
jeudi prochain en fin d'après-midi. Ça vérifie le critère du jury étape par étape :
  1. 3 créneaux réellement libres (le faux RDV de may à 16h30 doit être sauté) ;
  2. une visite créée, avec la bonne adresse, chez la bonne conseillère ;
  3. la même demande une 2e fois : aucun doublon ;
  4. déplacement, puis annulation (on laisse l'agenda propre à la fin).

Lancement, depuis la racine du dépôt (venv activé, token.json présent) :
    python agent/tester_agenda.py
"""

from datetime import timedelta

from agenda import annuler_visite, creer_visite, deplacer_visite, lister_creneaux_libres
from creer_agendas import jour_de_la_semaine_prochaine

jeudi = jour_de_la_semaine_prochaine(3)

print("1) Créneaux libres jeudi prochain à partir de 15h, quartier Mermoz :")
r = lister_creneaux_libres.invoke({"date_debut": jeudi.isoformat(), "apres_heure": "15:00", "quartier": "Mermoz"})
print("  ", r)
if not r.get("creneaux"):
    raise SystemExit("Aucun créneau : vérifier agendas.json et token.json.")
premier = r["creneaux"][0]["debut"]

print("\n2) Création d'une visite sur le 1er créneau :")
r1 = creer_visite.invoke({"id_bien": "SK-001", "debut": premier, "client": "Client test Atou"})
print("  ", r1)

print("\n3) Même créneau une 2e fois (doit être refusé, pas de doublon) :")
print("  ", creer_visite.invoke({"id_bien": "SK-001", "debut": premier, "client": "Autre client"}))

if r1.get("id_visite"):
    print("\n4) Déplacement au dernier créneau proposé :")
    print("  ", deplacer_visite.invoke({"id_visite": r1["id_visite"], "conseiller": "Awa",
                                         "nouveau_debut": r["creneaux"][-1]["debut"]}))
    print("\n5) Annulation (on remet l'agenda propre) :")
    print("  ", annuler_visite.invoke({"id_visite": r1["id_visite"], "conseiller": "Awa"}))
