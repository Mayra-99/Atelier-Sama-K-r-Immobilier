"""
analyser_echecs.py : préparer l'analyse de trois échecs (exercice 6, tâche e6c, Serigne Fallou).

IMAGE SIMPLE : le correcteur (evaluer_pipeline.py) a rendu les copies avec des croix rouges.
Ce script fait la FICHE DE RÉVISION : pour chaque copie ratée, il recopie la question, le corrigé,
ce que l'agent a fait, ses fautes, et il donne un PREMIER INDICE sur la cause.
Il ne remplace pas l'humain : la vraie cause, on la trouve en lisant la trace complète
(traces/exemples/...md, créée par sauver_traces.py). On complète ensuite la fiche à la main.

LANCEMENT (sans Groq, instantané, après « evaluer_pipeline.py --etiquette avant ») :
    python evaluation/analyser_echecs.py                 # les 3 premiers échecs du passage « avant »
    python evaluation/analyser_echecs.py --ids 7 9 14    # choisir soi-même les 3 échecs

Résultat : docs/analyse_echecs.md (à compléter, puis à envoyer sur GitHub).
"""

import argparse
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SORTIE = RACINE / "docs" / "analyse_echecs.md"

# Premier indice selon le type de faute (le mot cherché -> où regarder dans la trace)
INDICES = [
    ("plantage", "Panne technique, pas une erreur de raisonnement. Souvent une 429 de Groq (quota) : relancer ce mail seul avec --ids."),
    ("garde-fou", "L'agent tourne en rond (trop d'étapes). Regarder s'il relance rechercher_biens plusieurs fois : le prompt limite à 2 recherches."),
    ("adresse interdite", "GRAVE : l'injection a marché, l'agent a obéi au mail. Vérifier l'enveloppe <email_client> et la règle C du prompt (consignes cachées -> transmettre)."),
    ("devait transmettre", "L'agent n'a pas reconnu un cas hors périmètre. Comparer le mail à la règle C de CONSIGNES_PIPELINE (pipeline.py)."),
    ("devait répondre", "L'agent a été trop prudent : il a transmis une demande normale. Regarder la raison donnée dans transmettre_a_conseiller."),
    ("ni répondu ni transmis", "L'agent s'est arrêté sans agir. Regarder sa conclusion finale : a-t-il cru avoir fini ? Un outil a-t-il échoué ?"),
    ("manquant", "Le bon bien n'est pas proposé. Regarder les ARGUMENTS de rechercher_biens : un filtre trop strict (pièces, budget, quartier mal écrit) ?"),
    ("cité alors", "Un bien qui ne répond pas à la demande est cité. Regarder si le modèle a lu le résultat de l'outil ou s'il a inventé."),
    ("aucun créneau", "Pas de créneau dans le brouillon. Regarder si lister_creneaux_libres a été appelé, et ce qu'il a répondu."),
    ("créneaux proposés alors", "Créneaux proposés à tort (bien inexistant ou hors zone). La règle « pas de bien = pas de créneau » manque peut-être au prompt."),
    ("question", "L'agent a deviné au lieu de demander. Règle A du prompt : s'il manque une info indispensable, poser UNE question."),
    ("créneau interdit", "L'agent propose un créneau déjà pris. Regarder le résultat de lister_creneaux_libres : le créneau y était-il ? (outil ou modèle ?)"),
    ("confirmer une visite", "L'agent a voulu confirmer une visite que le client n'a pas choisie. Règle B : seulement après une proposition dans le même fil."),
]


def indice(fautes: list) -> str:
    vus = [texte for mot, texte in INDICES if any(mot in f for f in fautes)]
    return "\n".join(f"- {v}" for v in vus) or "- Lire la trace complète : aucun indice automatique."


def fiche(n: int, r: dict, mail: dict) -> str:
    return "\n".join([
        f"## Échec {n} · mail {r['id']} ({r['categorie']})",
        "",
        f"**Objet :** {r['objet']}",
        "",
        "**Le mail :** " + mail["texte"].replace("\n", " "),
        "",
        "**Ce qu'on attendait :** `" + json.dumps(mail["attendu"], ensure_ascii=False) + "`",
        f"({mail.get('pourquoi', '')})",
        "",
        f"**Ce que l'agent a fait :** décision = {r['decision'] or 'rien'} · "
        f"outils = {' → '.join(r['outils']) or 'aucun'} · {r['tokens']} tokens · {r['secondes']} s",
        "",
        "**Fautes relevées par le correcteur :** " + "; ".join(r["fautes"]),
        "",
        "**Extrait du brouillon :**" if r["brouillon"] else "**Raison de la transmission :**",
        "",
        "> " + (r["brouillon"] or r["raison_transmis"] or "(rien)")[:600].replace("\n", "\n> "),
        "",
        "**Premier indice (automatique) :**",
        indice(r["fautes"]),
        "",
        "**Cause réelle (après lecture de la trace) :** `<À COMPLÉTER>`",
        "",
        "**Est-ce un vrai échec de l'agent, ou une erreur du correcteur ?** `<À COMPLÉTER>`",
        "(exemple : « 16h30 n'est plus libre » est une BONNE réponse, même si le texte contient 16h30)",
        "",
        "**Correction proposée :** `<À COMPLÉTER>`",
        "",
    ])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prépare la fiche d'analyse de trois échecs.")
    parser.add_argument("--etiquette", default="avant", help="passage à analyser (par défaut : avant)")
    parser.add_argument("--ids", type=int, nargs="*", help="numéros des échecs à analyser")
    args = parser.parse_args()

    fichier = RACINE / "evaluation" / f"resultats_ex6_{args.etiquette}.json"
    if not fichier.exists():
        sys.exit(f"{fichier.name} n'existe pas : lancer d'abord evaluer_pipeline.py --etiquette {args.etiquette}")
    donnees = json.loads(fichier.read_text(encoding="utf-8"))
    mails = {m["id"]: m for m in json.loads((RACINE / "evaluation" / "emails_test.json").read_text(encoding="utf-8"))}

    echecs = [r for r in donnees["resultats"] if not r["reussi"]]
    if args.ids:
        echecs = [r for r in echecs if r["id"] in args.ids]
    echecs = echecs[:3]
    if not echecs:
        sys.exit("Aucun échec à analyser : 15/15 ! (dans ce cas, analyser les mails les plus lents ou les plus chers en tokens)")

    s = donnees["resume"]
    texte = "\n".join([
        "# Analyse de trois échecs (exercice 6)",
        "",
        f"Passage « {donnees['etiquette']} » du {donnees['date']}, modèle {donnees['modele']} : "
        f"**{s['reussis']}/{s['total']} réussis ({s['taux']} %)**, "
        f"{s['appels_moyens']} appels d'outils, {s['tokens_moyens']} tokens, {s['secondes_moyennes']} s par email.",
        "",
        "Méthode : pour chaque échec, on lit la trace complète (`traces/exemples/`), on cherche à quelle étape "
        "l'agent s'est trompé, et on classe la cause : **prompt** (consigne absente ou floue), **outil** "
        "(mauvais résultat), **modèle** (il a mal lu un résultat correct), **données** (catalogue, agenda) "
        "ou **correcteur** (l'agent avait raison, le test est trop strict).",
        "",
    ] + [fiche(i + 1, r, mails[r["id"]]) for i, r in enumerate(echecs)] + [
        "## Échec corrigé et résultat",
        "",
        "Échec choisi : `<À COMPLÉTER>` · Correction faite dans : `<fichier>` · Commit : `<numéro>`",
        "Tableau avant / après : `python evaluation/evaluer_pipeline.py --comparer`",
        "",
    ])
    SORTIE.write_text(texte, encoding="utf-8")
    print(f"{len(echecs)} échec(s) préparé(s) dans {SORTIE.relative_to(RACINE)} : à compléter à la main.")
