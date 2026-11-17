"""
creer_libelles.py : crée les libellés Gmail de l'agence (exercice 4, tâche de Serigne Fallou e4b).

IMAGE SIMPLE : un libellé Gmail, c'est une ÉTIQUETTE collée sur un mail, comme les bacs
« à traiter » / « fait » sur le bureau d'une secrétaire. L'agent change l'étiquette
à chaque étape (code de may, e4c), et le conseiller voit d'un coup d'œil où en est chaque demande :

    SK/À traiter                  -> mail client reçu, pas encore traité par l'agent
    SK/En attente de validation   -> brouillon prêt, le conseiller doit dire oui ou non
    SK/Répondu                    -> réponse validée et envoyée
    SK/Transmis à un conseiller   -> hors périmètre (réclamation, négociation...) : un humain prend la main

Le « / » range les 4 libellés sous un libellé parent « SK » dans la colonne de gauche de Gmail.

IDEMPOTENT (on peut le relancer sans danger) : on liste d'abord les libellés qui existent déjà,
et on ne crée que ceux qui manquent. Jamais de doublon.

Lancement, depuis la racine du dépôt (venv activé, token.json avec le droit Gmail) :
    python agent/creer_libelles.py
"""

from google_auth import service_gmail   # la clé Google (droit gmail.modify ajouté par may)

# Les noms EXACTS, convenus avec may : agent/gmail.py les cherche par ces noms.
LIBELLE_PARENT = "SK"
LIBELLES = {
    "a_traiter": "SK/À traiter",
    "en_attente": "SK/En attente de validation",
    "repondu": "SK/Répondu",
    "transmis": "SK/Transmis à un conseiller",
}


def creer_libelles(gmail=None) -> dict:
    """Crée les libellés manquants et renvoie {nom du libellé: identifiant Gmail}."""
    gmail = gmail or service_gmail()

    # 1. Les libellés qui existent déjà dans la boîte : {nom: identifiant}
    reponse = gmail.users().labels().list(userId="me").execute()
    existants = {l["name"]: l["id"] for l in reponse.get("labels", [])}

    # 2. On crée d'abord le parent « SK », puis les 4 étiquettes, seulement s'ils manquent
    resultat = {}
    for nom in [LIBELLE_PARENT, *LIBELLES.values()]:
        if nom in existants:
            print(f"  déjà là  : {nom}")
            resultat[nom] = existants[nom]
            continue
        corps = {
            "name": nom,
            "labelListVisibility": "labelShow",   # visible dans la colonne de gauche
            "messageListVisibility": "show",      # visible sur les mails
        }
        cree = gmail.users().labels().create(userId="me", body=corps).execute()
        print(f"  créé     : {nom}")
        resultat[nom] = cree["id"]
    return resultat


if __name__ == "__main__":
    print("Libellés Gmail de Sama Kër Immobilier :")
    libelles = creer_libelles()
    print(f"\n{len(libelles)} libellés prêts (parent compris). Relance possible sans doublon.")
