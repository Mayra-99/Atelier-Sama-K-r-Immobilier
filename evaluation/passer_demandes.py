"""
passer_demandes.py : passe les 10 demandes de test à l'agent (exercice 1, tâche d'Atou e1g).

Image simple : c'est l'examen blanc de l'agent. On lui pose 10 questions dont
on connaît déjà la bonne réponse (evaluation/demandes_test.json), puis on
corrige sa copie automatiquement.

Règle de correction (critère du jury pour l'exercice 1) :
  - l'agent ne doit citer QUE des biens attendus (aucun bien inventé, aucun bien loué) ;
  - quand rien ne correspond, il doit le dire clairement.

Lancement, depuis la racine du dépôt (venv activé, .env rempli, base créée) :
    python evaluation/passer_demandes.py
Résultat : un tableau dans le terminal + evaluation/resultats_ex1.json
La trace de tous les appels d'outils est dans traces/ (cahier de bord).
"""

import json
import re
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "agent"))      # pour importer main.py et traces.py

from groq import RateLimitError                # erreur 429 : quota gratuit dépassé
from main import construire_agent, repondre    # code de may
from traces import CahierDeBord                # code d'Atou

FICHIER_DEMANDES = RACINE / "evaluation" / "demandes_test.json"
FICHIER_RESULTATS = RACINE / "evaluation" / "resultats_ex1.json"

# Un identifiant de bien ressemble à SK-001 : on les repère dans la réponse.
MOTIF_ID = re.compile(r"SK-\d{3}", re.IGNORECASE)

# Pause entre deux demandes : le palier gratuit de Groq autorise environ
# 8 000 tokens PAR MINUTE. Sans pause, les 10 demandes vont trop vite (erreur 429).
PAUSE_ENTRE_DEMANDES = 15   # secondes

# Message du garde-fou de main.py quand l'agent tourne en rond (trop d'étapes).
# Ce n'est PAS une bonne réponse : l'agent aurait dû dire « aucun bien » tout de suite.
MESSAGE_GARDE_FOU = "je n'arrive pas à traiter votre demande"

# Des mots qui montrent que l'agent dit « je n'ai rien » ou « ce n'est pas mon rôle ».
MOTS_AUCUN = ["aucun", "pas de bien", "ne correspond", "pas disponible", "n'existe",
              "introuvable", "pas trouvé", "ne dispose", "uniquement", "seulement",
              "ne peux pas", "pas en mesure", "conseiller"]


def corriger(test: dict, reponse: str) -> tuple[bool, str]:
    """Compare la réponse de l'agent à ce qu'on attendait. Renvoie (réussi ?, explication)."""
    # Le modèle écrit souvent l'apostrophe typographique ’ au lieu de ' : on l'uniformise.
    reponse = reponse.replace("’", "'")
    if MESSAGE_GARDE_FOU in reponse.lower():
        return False, "l'agent a tourné en rond jusqu'au garde-fou (trop d'appels d'outils)"
    cites = {i.upper() for i in MOTIF_ID.findall(reponse)}
    attendus = set(test["ids_attendus"])
    en_trop = cites - attendus                  # biens cités alors qu'ils ne devaient pas l'être

    if en_trop:
        return False, f"biens en trop : {sorted(en_trop)}"

    if test["attendu"] == "biens":
        manquants = attendus - cites
        if manquants:
            return False, f"biens oubliés : {sorted(manquants)}"
        return True, f"cite {sorted(cites)}"

    # attendu = "aucun" ou "hors_perimetre" : l'agent doit le dire clairement
    texte = reponse.lower()
    if any(mot in texte for mot in MOTS_AUCUN):
        return True, "dit clairement qu'il n'a rien / hors périmètre"
    return False, "ne dit pas clairement qu'aucun bien ne correspond"


def main():
    tests = json.loads(FICHIER_DEMANDES.read_text(encoding="utf-8"))
    agent = construire_agent()
    cahier = CahierDeBord("trace_tests_ex1.jsonl")
    resultats = []

    for test in tests:
        print(f"\n[{test['id']}] {test['demande']}")
        # une conversation différente par demande, pour que les tests ne se mélangent pas
        try:
            reponse = repondre(agent, test["demande"], cahier, id_conversation=f"test-{test['id']}")
        except RateLimitError:
            # quota de la minute dépassé : on attend une minute et on réessaie une fois
            print("    ⏳ Quota Groq atteint, on attend 60 s puis on réessaie...")
            time.sleep(60)
            reponse = repondre(agent, test["demande"], cahier, id_conversation=f"test-{test['id']}-bis")
        ok, explication = corriger(test, reponse)
        print(f"    Agent : {reponse[:200]}")
        print(f"    {'✅ RÉUSSI' if ok else '❌ ÉCHEC'} : {explication}")
        resultats.append({**test, "reponse": reponse, "reussi": ok, "explication": explication})
        time.sleep(PAUSE_ENTRE_DEMANDES)   # on laisse respirer le quota gratuit

    nb_ok = sum(r["reussi"] for r in resultats)
    print(f"\n===== Score : {nb_ok}/{len(resultats)} demandes réussies =====")
    print(f"Détail : {FICHIER_RESULTATS.name} · Trace : traces/{cahier.chemin.name}")
    FICHIER_RESULTATS.write_text(json.dumps(resultats, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
