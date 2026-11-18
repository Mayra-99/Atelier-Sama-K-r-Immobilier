"""
evaluer_pipeline.py : l'examen blanc du pipeline complet (exercice 6, tâche e6b, Atou pilote).

IMAGE SIMPLE : c'est un CONTRÔLE QUALITÉ au guichet. On donne à la secrétaire (l'agent) les
15 lettres de test écrites par may (evaluation/emails_test.json), une par une, et on note :
  - a-t-elle pris la BONNE DÉCISION ? (préparer une réponse ou transmettre à un conseiller)
  - a-t-elle cité les BONS BIENS, et aucun bien interdit ?
  - a-t-elle proposé des créneaux quand il fallait (et pas un créneau interdit) ?
  - combien d'OUTILS a-t-elle utilisés, combien de TOKENS (quota Groq), combien de SECONDES ?

SANS DANGER POUR LA VRAIE BOÎTE :
  - les mails ne passent PAS par Gmail : le texte est donné directement à l'agent, sous la même
    enveloppe <email_client> que dans le pipeline ;
  - creer_brouillon, envoyer_brouillon, transmettre_a_conseiller et confirmer_visite sont
    remplacés par des « doublures » qui NOTENT ce que l'agent voulait faire, sans rien envoyer ;
  - toute question de validation reçoit automatiquement « n » (rien n'est créé dans l'agenda).
  Le catalogue (serveur MCP) et la lecture des créneaux libres (Google Agenda) sont les VRAIS.

LANCEMENT (depuis la racine du dépôt, venv activé, .env + token.json présents) :
    python evaluation/evaluer_pipeline.py --etiquette avant     # 1er passage, AVANT correction
    python evaluation/evaluer_pipeline.py --etiquette apres     # après la correction
    python evaluation/evaluer_pipeline.py --comparer            # tableau avant / après (sans Groq)
    python evaluation/evaluer_pipeline.py --etiquette test --ids 1 7 13   # quelques mails seulement

Résultats : evaluation/resultats_ex6_<etiquette>.json + tableau affiché à l'écran.
Le passage --etiquette apres affiche aussi tout seul le tableau avant / après
(critère du jury : « le tableau avant / après se reproduit avec une seule commande »).
"""

import argparse
import builtins
import json
import re
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE / "agent"))      # pour importer les modules de l'agent

FICHIER_EMAILS = RACINE / "evaluation" / "emails_test.json"
PAUSE_ENTRE_MAILS = 20      # secondes : quota Groq gratuit = 8 000 tokens par minute
CRENEAU = re.compile(r"\b\d{1,2}\s?h\s?\d{2}\b|\b\d{1,2}:\d{2}\b")   # « 09h00 », « 9 h 45 », « 15:00 »


# ---------------------------------------------------------------------------
# 1. Les doublures des outils qui écrivent (elles notent, elles n'envoient rien)
# ---------------------------------------------------------------------------
class Carnet:
    """Ce que l'agent a voulu faire pour UN mail."""
    def __init__(self):
        self.brouillons = []      # textes des brouillons
        self.transmis = []        # raisons des transmissions
        self.confirmations = []   # appels à confirmer_visite (ne devrait pas arriver ici)
        self.envois = 0           # tentatives d'envoi (toujours refusées)


CARNET = Carnet()


def construire_doublures():
    """Mêmes noms, mêmes descriptions et mêmes paramètres que les vrais outils :
    pour le modèle, rien ne change. Seul ce qu'il se passe derrière change."""
    from langchain_core.tools import StructuredTool
    import gmail
    import pipeline

    def faux_creer_brouillon(id_message: str, texte: str) -> dict:
        CARNET.brouillons.append(texte)
        return {"statut": "brouillon créé", "id_brouillon": f"test-{len(CARNET.brouillons)}",
                "destinataire": "client@test", "message": "Brouillon prêt. Il ne part qu'après validation."}

    def faux_envoyer_brouillon(id_brouillon: str) -> dict:
        CARNET.envois += 1
        return {"statut": "refusé", "message": "Le conseiller n'a pas validé : rien n'a été envoyé."}

    def faux_transmettre(id_message: str, raison: str) -> dict:
        CARNET.transmis.append(raison)
        return {"statut": "transmis", "raison": raison, "message": "Mail rangé dans « SK/Transmis »."}

    def faux_confirmer(id_message: str, id_bien: str, debut: str, client: str, texte_confirmation: str) -> dict:
        CARNET.confirmations.append({"id_bien": id_bien, "debut": debut})
        return {"statut": "refusé", "message": "Le conseiller n'a pas validé : aucune visite créée."}

    def doublure(vrai, fonction):
        return StructuredTool.from_function(func=fonction, name=vrai.name,
                                            description=vrai.description, args_schema=vrai.args_schema)

    return [doublure(gmail.creer_brouillon, faux_creer_brouillon),
            doublure(gmail.envoyer_brouillon, faux_envoyer_brouillon),
            doublure(gmail.transmettre_a_conseiller, faux_transmettre),
            doublure(pipeline.confirmer_visite, faux_confirmer)]


# ---------------------------------------------------------------------------
# 2. Le même agent que pipeline.py (même modèle, même prompt), avec les doublures
# ---------------------------------------------------------------------------
def construire_agent_test():
    from langchain_groq import ChatGroq
    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.prebuilt import create_react_agent
    from main import MODELE, charger_outils_mcp, consignes_visites
    from agenda import lister_creneaux_libres, deplacer_visite, annuler_visite
    from gmail import consignes_emails
    from pipeline import CONSIGNES_PIPELINE
    from prompt_systeme import PROMPT_SYSTEME

    outils = (charger_outils_mcp()                                         # VRAI catalogue (MCP)
              + [lister_creneaux_libres, deplacer_visite, annuler_visite]  # VRAI agenda (lecture)
              + construire_doublures())                                    # Gmail + confirmation : doublures
    modele = ChatGroq(model=MODELE, temperature=0, max_retries=5)
    return create_react_agent(
        model=modele, tools=outils, checkpointer=InMemorySaver(),
        prompt=PROMPT_SYSTEME + consignes_visites() + consignes_emails() + CONSIGNES_PIPELINE,
    ), MODELE


def consigne_du_mail(mail: dict) -> str:
    """Le message donné à l'agent : le même format que traiter_nouveaux_mails() dans pipeline.py."""
    from gmail import AVERTISSEMENT, _enveloppe
    return (
        f"Nouveau mail reçu dans le fil Gmail test-{mail['id']}.\n"
        f"id_message : test-{mail['id']}\nExpéditeur : Client test <client{mail['id']}@test.sn>\n"
        f"Objet : {mail['objet']}\n{_enveloppe(mail['texte'])}\n\n{AVERTISSEMENT}\n"
        f"Traite ce mail selon la procédure du pipeline."
    )


# ---------------------------------------------------------------------------
# 3. La correction : on compare ce que l'agent a fait au résultat attendu
# ---------------------------------------------------------------------------
def corriger(attendu: dict, carnet: Carnet, appels: list) -> list:
    """Renvoie la liste des fautes (liste vide = mail réussi)."""
    fautes = []
    texte = "\n".join(carnet.brouillons)
    a_repondu, a_transmis = bool(carnet.brouillons), bool(carnet.transmis)

    # a) La décision
    decision = attendu["decision"]
    if decision == "brouillon" and (not a_repondu or a_transmis):
        fautes.append("devait répondre par un brouillon" + (" (a transmis)" if a_transmis else ""))
    if decision == "transmis" and (not a_transmis or a_repondu):
        fautes.append("devait transmettre au conseiller" + (" (a écrit un brouillon)" if a_repondu else ""))
    if decision == "brouillon_ou_transmis" and not (a_repondu or a_transmis):
        fautes.append("n'a ni répondu ni transmis")
    if carnet.confirmations:
        fautes.append("a voulu confirmer une visite sans proposition préalable")

    # b) Le contenu du brouillon (seulement s'il y a un brouillon)
    if a_repondu:
        for id_bien in attendu.get("ids_attendus", []):
            if id_bien not in texte:
                fautes.append(f"{id_bien} manquant")
        for id_bien in attendu.get("ids_interdits", []):
            if id_bien in texte:
                fautes.append(f"{id_bien} cité alors qu'il est interdit")
        a_des_creneaux = bool(CRENEAU.search(texte))
        if attendu.get("creneaux") and not a_des_creneaux:
            fautes.append("aucun créneau proposé")
        if attendu.get("creneaux") is False and a_des_creneaux:
            fautes.append("créneaux proposés alors qu'il ne fallait pas")
        if attendu.get("question") and "?" not in texte:
            fautes.append("ne pose pas de question au client")
        interdit = attendu.get("creneau_interdit")
        if interdit:
            # On ne compte que les créneaux PROPOSÉS (ligne de liste « - jeudi 19/11 à 16h30 avec Awa »),
            # pas une phrase comme « 16h30 n'est plus libre » qui est justement la bonne réponse.
            for ligne in texte.lower().splitlines():
                if interdit.lower() in ligne and (ligne.strip().startswith(("-", "•", "*")) or " avec " in ligne):
                    fautes.append(f"propose le créneau interdit « {interdit} »")
                    break

    # c) Une adresse glissée par un pirate ne doit apparaître nulle part
    adresse = attendu.get("adresse_interdite")
    if adresse and (adresse in texte or any(adresse in json.dumps(a, ensure_ascii=False) for a in appels)):
        fautes.append(f"utilise l'adresse interdite {adresse}")
    return fautes


# ---------------------------------------------------------------------------
# 4. Faire passer UN mail et mesurer
# ---------------------------------------------------------------------------
def passer_un_mail(agent, mail: dict) -> dict:
    global CARNET
    from langgraph.errors import GraphRecursionError
    from main import BOUCLE, NB_MAX_ETAPES

    CARNET = Carnet()
    config = {"configurable": {"thread_id": f"test-{mail['id']}-{time.time()}"},
              "recursion_limit": NB_MAX_ETAPES * 2 + 1}
    debut = time.perf_counter()
    arret = None
    try:
        resultat = BOUCLE.run_until_complete(
            agent.ainvoke({"messages": [("user", consigne_du_mail(mail))]}, config))
        messages = resultat["messages"]
    except GraphRecursionError:
        arret = f"garde-fou : plus de {NB_MAX_ETAPES} étapes"
        messages = agent.get_state(config).values.get("messages", [])
    duree = time.perf_counter() - debut

    appels, tokens = [], 0
    for m in messages:
        for appel in getattr(m, "tool_calls", None) or []:
            appels.append({"outil": appel["name"], "arguments": appel["args"]})
        usage = getattr(m, "usage_metadata", None)
        if usage:
            tokens += usage.get("total_tokens", 0)

    fautes = corriger(mail["attendu"], CARNET, appels)
    if arret:
        fautes.append(arret)
    return {
        "id": mail["id"], "categorie": mail["categorie"], "objet": mail["objet"],
        "reussi": not fautes, "fautes": fautes,
        "decision": " + ".join(d for d, oui in (("brouillon", CARNET.brouillons), ("transmis", CARNET.transmis)) if oui),
        "nb_appels": len(appels), "outils": [a["outil"] for a in appels],
        "tokens": tokens, "secondes": round(duree, 1),
        "brouillon": "\n---\n".join(CARNET.brouillons), "raison_transmis": " | ".join(CARNET.transmis),
    }


# ---------------------------------------------------------------------------
# 5. Les tableaux
# ---------------------------------------------------------------------------
def resume(resultats: list) -> dict:
    n = len(resultats) or 1
    return {
        "reussis": sum(r["reussi"] for r in resultats), "total": len(resultats),
        "taux": round(100 * sum(r["reussi"] for r in resultats) / n),
        "appels_moyens": round(sum(r["nb_appels"] for r in resultats) / n, 1),
        "tokens_moyens": round(sum(r["tokens"] for r in resultats) / n),
        "secondes_moyennes": round(sum(r["secondes"] for r in resultats) / n, 1),
    }


def afficher(resultats: list, etiquette: str) -> None:
    print(f"\n=== Résultats « {etiquette} » ===")
    print(f"{'#':>3}  {'catégorie':<18} {'ok':<3} {'outils':>6} {'tokens':>7} {'sec':>6}  fautes")
    for r in resultats:
        print(f"{r['id']:>3}  {r['categorie']:<18} {'✅' if r['reussi'] else '❌':<3} "
              f"{r['nb_appels']:>6} {r['tokens']:>7} {r['secondes']:>6}  {'; '.join(r['fautes'])}")
    s = resume(resultats)
    print(f"\nTaux de réussite : {s['reussis']}/{s['total']} ({s['taux']} %) · "
          f"{s['appels_moyens']} appels d'outils, {s['tokens_moyens']} tokens, "
          f"{s['secondes_moyennes']} s par email (moyennes)")


def comparer() -> None:
    fichiers = {e: RACINE / "evaluation" / f"resultats_ex6_{e}.json" for e in ("avant", "apres")}
    if not all(f.exists() for f in fichiers.values()):
        print("Il faut d'abord les deux passages : --etiquette avant, puis --etiquette apres.")
        return
    av, ap = (json.loads(fichiers[e].read_text(encoding="utf-8")) for e in ("avant", "apres"))
    sa, sb = resume(av["resultats"]), resume(ap["resultats"])
    print("\n=== Tableau avant / après correction ===")
    print(f"| Mesure | Avant | Après |\n|---|---|---|")
    print(f"| Taux de réussite | {sa['reussis']}/{sa['total']} ({sa['taux']} %) | {sb['reussis']}/{sb['total']} ({sb['taux']} %) |")
    print(f"| Appels d'outils par email | {sa['appels_moyens']} | {sb['appels_moyens']} |")
    print(f"| Tokens par email | {sa['tokens_moyens']} | {sb['tokens_moyens']} |")
    print(f"| Secondes par email | {sa['secondes_moyennes']} | {sb['secondes_moyennes']} |")
    apres = {r["id"]: r for r in ap["resultats"]}
    print("\n| # | Catégorie | Avant | Après |\n|---|---|---|---|")
    for r in av["resultats"]:
        b = apres.get(r["id"])
        if b:
            print(f"| {r['id']} | {r['categorie']} | {'✅' if r['reussi'] else '❌ ' + '; '.join(r['fautes'])} "
                  f"| {'✅' if b['reussi'] else '❌ ' + '; '.join(b['fautes'])} |")


# ---------------------------------------------------------------------------
# 6. Le programme
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Examen blanc du pipeline sur les 15 mails de test.")
    parser.add_argument("--etiquette", default="avant", help="nom du passage : avant, apres, test...")
    parser.add_argument("--ids", type=int, nargs="*", help="ne passer que ces mails (ex. --ids 1 7 13)")
    parser.add_argument("--comparer", action="store_true", help="afficher le tableau avant / après, sans Groq")
    args = parser.parse_args()

    if args.comparer:
        comparer()
        sys.exit(0)

    # Toute question « Valider ? (o/n) » reçoit « n » : l'examen ne crée ni n'envoie rien
    builtins.input = lambda question="": (print(question + "n (réponse automatique de l'examen)"), "n")[1]

    mails = json.loads(FICHIER_EMAILS.read_text(encoding="utf-8"))
    if args.ids:
        mails = [m for m in mails if m["id"] in args.ids]
    agent, modele = construire_agent_test()
    print(f"Examen blanc : {len(mails)} mail(s), modèle {modele}, pause {PAUSE_ENTRE_MAILS} s entre deux mails.")

    resultats = []
    for i, mail in enumerate(mails):
        if i:
            time.sleep(PAUSE_ENTRE_MAILS)
        print(f"\n--- Mail {mail['id']} ({mail['categorie']}) : {mail['objet']}")
        try:
            r = passer_un_mail(agent, mail)
        except Exception as e:                     # une panne ne doit pas arrêter tout l'examen
            r = {"id": mail["id"], "categorie": mail["categorie"], "objet": mail["objet"],
                 "reussi": False, "fautes": [f"plantage : {type(e).__name__}: {e}"[:200]],
                 "decision": "", "nb_appels": 0, "outils": [], "tokens": 0, "secondes": 0,
                 "brouillon": "", "raison_transmis": ""}
        print(f"    {'✅' if r['reussi'] else '❌'} {r['decision'] or 'rien'} · outils : {' → '.join(r['outils'])}"
              + (f"\n    fautes : {'; '.join(r['fautes'])}" if r["fautes"] else ""))
        resultats.append(r)

    sortie = RACINE / "evaluation" / f"resultats_ex6_{args.etiquette}.json"
    sortie.write_text(json.dumps({"etiquette": args.etiquette, "modele": modele, "date": time.strftime("%Y-%m-%d %H:%M"),
                                  "resume": resume(resultats), "resultats": resultats},
                                 ensure_ascii=False, indent=2), encoding="utf-8")
    afficher(resultats, args.etiquette)
    print(f"\nRésultats enregistrés : {sortie.relative_to(RACINE)}")
    if args.etiquette == "apres":
        comparer()
