"""
main.py : l'agent de Sama Kër Immobilier.
Exercice 1 : tâche de may (e1e). Exercice 2 : branchement au serveur MCP par Fallou (e2d).
Exercice 3 : ajout des 4 actions de l'agenda Google par Atou (e3c, e3e).
Exercice 4 : ajout des actions Gmail par may (e4a, e4c, e4e).

Ce fichier assemble les morceaux de l'équipe :
  - le MODÈLE        : Groq (gratuit), qui sait appeler des outils ;
  - le PROMPT        : la fiche de poste écrite par Fallou (prompt_systeme.py) ;
  - les OUTILS       : rechercher_biens et detail_bien, fournis par le SERVEUR MCP
                       (serveur_mcp/serveur.py). L'agent est un CLIENT MCP : il ne
                       connaît plus le code des outils, il les demande au guichet ;
  - la BOUCLE        : LangGraph fait tourner « réfléchir -> agir -> observer » ;
  - l'AGENDA         : 4 actions Google Calendar d'Atou (agenda.py), avec validation
                       du conseiller avant chaque écriture ;
  - la BOÎTE MAIL    : actions Gmail de may (gmail.py) : lire, brouillon, envoi validé,
                       libellés, et contenu des mails traité comme une DONNÉE ;
  - les TRACES       : le cahier de bord d'Atou (traces.py) note chaque appel d'outil.

Lancement, depuis la racine du dépôt (environnement virtuel activé) :
    python agent/main.py
Puis taper une demande, par exemple : un F3 à Mermoz à moins de 400 000 F
Taper « quitter » pour arrêter.
"""

import asyncio
from datetime import datetime
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.errors import GraphRecursionError
from langgraph.prebuilt import create_react_agent
from langchain_mcp_adapters.client import MultiServerMCPClient   # le « câble » vers le serveur MCP

from prompt_systeme import PROMPT_SYSTEME   # fichier de Fallou
from traces import CahierDeBord               # fichier d'Atou
from agenda import OUTILS_AGENDA               # exercice 3 : les 4 actions de l'agenda (Atou)
from regles_agenda import FUSEAU, NOMS_JOURS   # exercice 3 : heure de Dakar (may)
from gmail import OUTILS_GMAIL, consignes_emails   # exercice 4 : la boîte de l'agence (may)

# ------------------------------------------------------------------ réglages

RACINE = Path(__file__).resolve().parent.parent
load_dotenv(RACINE / ".env")                      # lit GROQ_API_KEY et MODELE dans .env

MODELE = os.getenv("MODELE", "openai/gpt-oss-120b")
NB_MAX_ETAPES = 10      # garde-fou contre les boucles sans fin (axe 4 de la veille)

# Comment joindre le serveur MCP (exercice 2) :
#   - "stdio" (par défaut) : l'agent lance lui-même serveur_mcp/serveur.py ;
#   - "http" : le serveur tourne déjà dans un autre terminal (python serveur_mcp/serveur.py http)
#     et on le joint à l'adresse MCP_URL du .env.
MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "stdio")
MCP_URL = os.getenv("MCP_URL", "http://127.0.0.1:8000/mcp")

# Les outils MCP sont « asynchrones » (ils attendent la réponse du serveur sans bloquer).
# On garde UNE seule boucle asyncio pour tout le programme, et on s'en sert partout.
BOUCLE = asyncio.new_event_loop()


def configuration_mcp() -> dict:
    """Décrit le serveur MCP à joindre, selon le transport choisi."""
    if MCP_TRANSPORT == "http":
        return {"catalogue": {"transport": "streamable_http", "url": MCP_URL}}
    return {"catalogue": {
        "transport": "stdio",
        "command": sys.executable,                              # le Python du venv
        "args": [str(RACINE / "serveur_mcp" / "serveur.py")],
    }}


def charger_outils_mcp() -> list:
    """Se branche au serveur MCP et récupère la liste de ses outils (avec leur notice)."""
    client = MultiServerMCPClient(configuration_mcp())
    try:
        outils = BOUCLE.run_until_complete(client.get_tools())
    except Exception as e:
        raise SystemExit(f"Impossible de joindre le serveur MCP ({MCP_TRANSPORT}) : {e}")
    if not outils:
        raise SystemExit("Le serveur MCP ne propose aucun outil.")
    return outils


# ------------------------------------------------------------------ consignes de l'exercice 3

def consignes_visites() -> str:
    """Ajoute au prompt de Fallou la date du jour et la façon de prendre un rendez-vous.
    Sans la date du jour, le modèle ne peut pas savoir quel jour tombe « jeudi prochain »."""
    maintenant = datetime.now(FUSEAU)
    return f"""

PRISE DE RENDEZ-VOUS (exercice 3)
- Aujourd'hui, nous sommes le {NOMS_JOURS[maintenant.weekday()]} {maintenant:%d/%m/%Y} (heure de Dakar).
- Pour proposer une visite, tu appelles TOUJOURS lister_creneaux_libres, avec le quartier du bien.
  Tu ne proposes que les créneaux renvoyés par l'outil, jamais un créneau inventé.
  « fin d'après-midi » = à partir de 15:00 ; « matin » = 9:00-12:00.
- Tu n'appelles creer_visite qu'APRÈS que le client a choisi un créneau, avec son nom.
- creer_visite, deplacer_visite et annuler_visite demandent l'accord du conseiller :
  si la réponse est « refusé », tu dis au client que sa demande sera confirmée par un conseiller.
- Garde l'id_visite et le conseiller renvoyés par creer_visite : ils servent pour déplacer ou annuler.
"""


# ------------------------------------------------------------------ l'agent

def construire_agent():
    """Crée l'agent : modèle + outils + prompt système + mémoire de conversation."""
    if not os.getenv("GROQ_API_KEY"):
        raise SystemExit("Clé manquante : mettre GROQ_API_KEY dans le fichier .env (voir .env.example).")
    modele = ChatGroq(model=MODELE, temperature=0)   # température 0 : réponses plus stables
    outils = charger_outils_mcp()                    # exercice 2 : les outils viennent du serveur MCP
    outils = outils + OUTILS_AGENDA                  # exercice 3 : + les 4 actions de l'agenda
    outils = outils + OUTILS_GMAIL                   # exercice 4 : + les actions Gmail
    return create_react_agent(
        model=modele,
        tools=outils,
        prompt=PROMPT_SYSTEME + consignes_visites() + consignes_emails(),
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
        # ainvoke = version asynchrone (obligatoire avec des outils MCP), lancée dans notre boucle
        resultat = BOUCLE.run_until_complete(
            agent.ainvoke({"messages": [("user", question)]}, config)
        )
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
    print(f"Agent Sama Kër prêt (modèle {MODELE}, serveur MCP en {MCP_TRANSPORT}). Trace : traces/{cahier.chemin.name}")
    print("Tapez votre demande, ou « quitter ».\n")
    while True:
        question = input("Client > ").strip()
        if question.lower() in ("quitter", "exit", "q"):
            break
        if question:
            print(f"Agent  > {repondre(agent, question, cahier)}\n")
    cahier.afficher_resume()
