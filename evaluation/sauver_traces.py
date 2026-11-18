"""
sauver_traces.py : garder la trace COMPLÈTE de quelques traitements (exercice 6, tâche e6e, Maimouna).

IMAGE SIMPLE : evaluer_pipeline.py est le CORRECTEUR. Il met une note à chaque copie, mais il ne
garde pas le brouillon de l'élève. Ici, on garde le BROUILLON COMPLET : toutes les étapes de
réflexion de l'agent, chaque outil appelé, avec quoi, et ce qui est revenu. C'est ce qu'on
montre au jury pendant « la lecture commentée de la trace ».

Ce script réutilise TOUT ce qu'Atou a écrit dans evaluer_pipeline.py : le même agent, les mêmes
doublures (rien n'est envoyé, rien n'est créé dans l'agenda), la même correction.
Il ajoute seulement l'enregistrement de chaque message de la conversation.

LANCEMENT (depuis la racine du dépôt, venv activé, .env + token.json présents) :
    python evaluation/sauver_traces.py --ids 1 7 13

    -> on choisit 3 mails : 2 réussis + 1 échec (celui qu'analyse Serigne Fallou).
    -> le faire JUSTE APRÈS « evaluer_pipeline.py --etiquette avant », AVANT la correction :
       sinon l'échec risque d'avoir disparu.

Résultat, pour chaque mail :
    traces/exemples/mail_07_creneau_pris.md     la trace lisible par un humain (pour le jury)
    traces/exemples/mail_07_creneau_pris.json   la même trace, lisible par un programme
"""

import argparse
import builtins
import json
import sys
import time
import unicodedata
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "evaluation"))   # pour importer le script d'Atou

import evaluer_pipeline as ev                    # il ajoute lui-même agent/ au chemin

DOSSIER = RACINE / "traces" / "exemples"
LONGUEUR_MAX = 1500                              # on coupe les très longs résultats d'outil


def couper(texte: str) -> str:
    texte = str(texte)
    return texte if len(texte) <= LONGUEUR_MAX else texte[:LONGUEUR_MAX] + " [...coupé]"


# ---------------------------------------------------------------------------
# 1. Rejouer UN mail en gardant TOUS les messages (pas seulement la note)
# ---------------------------------------------------------------------------
def rejouer_avec_trace(agent, mail: dict) -> dict:
    from langgraph.errors import GraphRecursionError
    from main import BOUCLE, NB_MAX_ETAPES

    ev.CARNET = ev.Carnet()           # carnet vide : les doublures d'Atou y notent ce que l'agent veut faire
    config = {"configurable": {"thread_id": f"trace-{mail['id']}-{time.time()}"},
              "recursion_limit": NB_MAX_ETAPES * 2 + 1}
    debut = time.perf_counter()
    arret = None
    try:
        resultat = BOUCLE.run_until_complete(
            agent.ainvoke({"messages": [("user", ev.consigne_du_mail(mail))]}, config))
        messages = resultat["messages"]
    except GraphRecursionError:
        arret = f"garde-fou : plus de {NB_MAX_ETAPES} étapes"
        messages = agent.get_state(config).values.get("messages", [])
    duree = round(time.perf_counter() - debut, 1)

    # Chaque message devient une ÉTAPE de la trace
    etapes, appels, tokens = [], [], 0
    for m in messages:
        if m.type == "human":
            etapes.append({"qui": "mail reçu", "texte": m.content})
        elif m.type == "ai":
            reflexion = (getattr(m, "additional_kwargs", {}) or {}).get("reasoning_content", "")
            for appel in m.tool_calls or []:
                appels.append({"outil": appel["name"], "arguments": appel["args"]})
            etapes.append({
                "qui": "modèle",
                "reflexion": reflexion,                       # ce que le modèle a « pensé » (si Groq le donne)
                "texte": m.content,                           # sa réponse écrite (vide s'il appelle un outil)
                "appels": [{"outil": a["name"], "arguments": a["args"]} for a in (m.tool_calls or [])],
            })
            usage = getattr(m, "usage_metadata", None)
            if usage:
                tokens += usage.get("total_tokens", 0)
        elif m.type == "tool":
            etapes.append({"qui": "outil", "outil": m.name, "resultat": m.content})

    fautes = ev.corriger(mail["attendu"], ev.CARNET, appels)   # la même correction qu'evaluer_pipeline.py
    if arret:
        fautes.append(arret)
    return {"id": mail["id"], "categorie": mail["categorie"], "objet": mail["objet"],
            "texte_du_mail": mail["texte"], "attendu": mail["attendu"], "pourquoi": mail.get("pourquoi", ""),
            "reussi": not fautes, "fautes": fautes, "nb_appels": len(appels), "tokens": tokens,
            "secondes": duree, "date": time.strftime("%Y-%m-%d %H:%M"), "etapes": etapes}


# ---------------------------------------------------------------------------
# 2. Écrire la trace en Markdown (lisible sur GitHub, pour le jury)
# ---------------------------------------------------------------------------
def en_markdown(t: dict) -> str:
    l = [f"# Trace du mail {t['id']} · {t['categorie']}",
         "",
         f"- **Objet :** {t['objet']}",
         f"- **Résultat :** {'✅ réussi' if t['reussi'] else '❌ échec : ' + '; '.join(t['fautes'])}",
         f"- **Mesures :** {t['nb_appels']} appels d'outils · {t['tokens']} tokens · {t['secondes']} s",
         f"- **Date :** {t['date']} (rejoué avec les doublures : rien n'a été envoyé ni créé)",
         "",
         "## Le mail du client",
         "",
         "> " + t["texte_du_mail"].replace("\n", "\n> "),
         "",
         "## Ce qu'on attendait",
         "",
         "```json",
         json.dumps(t["attendu"], ensure_ascii=False, indent=2),
         "```",
         "",
         f"Pourquoi : {t['pourquoi']}",
         "",
         "## Le déroulé, étape par étape",
         ""]
    n = 0
    for e in t["etapes"]:
        if e["qui"] == "mail reçu":
            continue                                   # déjà montré plus haut
        n += 1
        if e["qui"] == "modèle":
            if e["appels"]:
                for a in e["appels"]:
                    l.append(f"**{n}. Le modèle décide** d'appeler `{a['outil']}` avec :")
                    l += ["```json", json.dumps(a["arguments"], ensure_ascii=False, indent=2), "```"]
            else:
                l.append(f"**{n}. Le modèle conclut :** {e['texte']}")
            if e["reflexion"]:
                l.append(f"<details><summary>Ce que le modèle a pensé</summary>\n\n{couper(e['reflexion'])}\n\n</details>")
        else:
            l.append(f"**{n}. L'outil `{e['outil']}` répond :**")
            l += ["```", couper(e["resultat"]), "```"]
        l.append("")
    l += ["## Analyse (à compléter par l'équipe)", "",
          "- Ce que l'agent a bien fait :",
          "- Ce qui ne va pas (s'il y a un échec) :",
          "- La cause (prompt, outil, modèle, données ?) :",
          "- La correction :", ""]
    return "\n".join(l)


# ---------------------------------------------------------------------------
# 3. Le programme
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Garde la trace complète de quelques mails de test.")
    parser.add_argument("--ids", type=int, nargs="+", required=True,
                        help="numéros des mails à rejouer, ex. --ids 1 7 13 (2 réussis + 1 échec)")
    args = parser.parse_args()

    # Comme dans evaluer_pipeline.py : toute validation reçoit « n », rien n'est créé ni envoyé
    builtins.input = lambda question="": (print(question + "n (réponse automatique)"), "n")[1]

    mails = [m for m in json.loads(ev.FICHIER_EMAILS.read_text(encoding="utf-8")) if m["id"] in args.ids]
    if not mails:
        sys.exit("Aucun mail trouvé avec ces numéros (il y en a 15, numérotés de 1 à 15).")
    agent, modele = ev.construire_agent_test()
    DOSSIER.mkdir(parents=True, exist_ok=True)
    print(f"Traces complètes : {len(mails)} mail(s), modèle {modele}.")

    for i, mail in enumerate(mails):
        if i:
            time.sleep(ev.PAUSE_ENTRE_MAILS)           # quota Groq : 8 000 tokens par minute
        print(f"\n--- Mail {mail['id']} ({mail['categorie']}) : {mail['objet']}")
        t = rejouer_avec_trace(agent, mail)
        # nom de fichier sans accent ni espace (plus sûr sous Windows et sur GitHub)
        sans_accent = unicodedata.normalize("NFD", t["categorie"]).encode("ascii", "ignore").decode()
        nom = f"mail_{t['id']:02d}_{sans_accent.replace(' ', '_')}"
        (DOSSIER / f"{nom}.json").write_text(json.dumps(t, ensure_ascii=False, indent=2), encoding="utf-8")
        (DOSSIER / f"{nom}.md").write_text(en_markdown(t), encoding="utf-8")
        print(f"    {'✅' if t['reussi'] else '❌ ' + '; '.join(t['fautes'])}")
        print(f"    trace enregistrée : traces/exemples/{nom}.md")
