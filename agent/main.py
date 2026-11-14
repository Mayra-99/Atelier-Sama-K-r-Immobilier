"""
main.py : l'agent de Sama Kër Immobilier (exercice 1, tâche de may e1e).

Ce fichier assemble les morceaux de l'équipe :
  - le MODÈLE        : Groq (gratuit), qui sait appeler des outils ;
  - le PROMPT        : la fiche de poste écrite par Fallou (prompt_systeme.py) ;
  - les OUTILS       : rechercher_biens et detail_bien (outils.py) ;
  - la BOUCLE        : LangGraph fait tourner « réfléchir -> agir -> observer » ;
  - les TRACES       : le cahier de bord d'Atou (traces.py) note chaque appel d'outil.

Lancement, depuis la racine du dépôt (environnement virtuel activé) :
    python agent/main.py
Puis taper une demande, par exemple : un F3 à Mermoz à moins de 400 000 F
Taper « quitter » pour arrêter.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import GraphRecursionError
from langgraph.prebuilt import create_react_agent

from outils import OUTILS
from prompt_systeme import PROMPT_SYSTEME   # fichier de Fallou
from traces import CahierDeBord               # fichier d'Atou

# ------------------------------------------------------------------ réglages

RACINE = Path(__file__).resolve().parent.parent
load_dotenv(RACINE / ".env")                      # lit GROQ_API_KEY et MODELE dans .env

MODELE = os.getenv("MODELE", "openai/gpt-oss-120b")
NB_MAX_ETAPES = 10      # garde-fou contre les boucles sans fin (axe 4 de la veille)


# ------------------------------------------------------------------ l'agent

def construire_agent():
    """Crée l'agent : modèle + outils + prompt système + mémoire de conversation."""
    if not os.getenv("GROQ_API_KEY"):
        raise SystemExit("Clé manquante : mettre GROQ_API_KEY dans le fichier .env (voir .env.example).")
    modele = ChatGroq(model=MODELE, temperature=0)   # température 0 : réponses plus stables
    return create_react_agent(
        model=modele,
        tools=OUTILS,
        prompt=PROMPT_SYSTEME,
        checkpointer=InMemorySaver(),   # garde l'historique de la conversation en cours
    )


def repondre(agent, question: str, cahier: CahierDeBord, id_conversation: str = "client-1") -> str:
    """Envoie une demande à l'agent et renvoie sa réponse finale."""
    config = {
        "configurable": {"thread_id": id_conversation},
        "recursion_limit": NB_MAX_ETAPES * 2 + 1,   # 1 étape = modèle + outil
        "callbacks": [cahier],                       # le cahier de bord écoute chaque étape
    }
    cahier._noter({"type": "demande", "texte": question})
    debut = len(cahier.evenements)
    try:
        resultat = agent.invoke({"messages": [("user", question)]}, config)
        reponse = resultat["messages"][-1].content
    except GraphRecursionError:
        # garde-fou : l'agent a tourné trop longtemps, on s'arrête proprement
        reponse = ("Je n'arrive pas à traiter votre demande pour le moment. "
                   "Un conseiller va reprendre contact avec vous.")
        cahier._noter({"type": "arret", "raison": f"plus de {NB_MAX_ETAPES} étapes"})
    # on affiche les appels d'outils de CETTE demande seulement
    for e in cahier.evenements[debut:]:
        if e["type"] == "appel_outil":
            print(f"   → {e['outil']}({e['arguments']})")
        elif e["type"] == "erreur_outil":
            print(f"   ✗ {e['erreur']}")
    cahier._noter({"type": "reponse", "texte": reponse})
    return reponse


if __name__ == "__main__":
    agent = construire_agent()
    cahier = CahierDeBord()
    print(f"Agent Sama Kër prêt (modèle {MODELE}). Trace : traces/{cahier.chemin.name}")
    print("Tapez votre demande, ou « quitter ».\n")
    while True:
        question = input("Client > ").strip()
        if question.lower() in ("quitter", "exit", "q"):
            break
        if question:
            print(f"Agent  > {repondre(agent, question, cahier)}\n")
    cahier.afficher_resume()
