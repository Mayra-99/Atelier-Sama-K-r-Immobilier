"""
gmail.py : les actions de l'agent sur la boîte Gmail de l'agence (exercice 4, tâches de may).
  e4a : 3 actions : lire les demandes non traitées, créer un brouillon dans le bon fil,
        envoyer un brouillon validé par un conseiller.

IMAGE SIMPLE : l'agent est la SECRÉTAIRE qui ouvre le courrier de l'agence.
- Elle LIT les lettres (lire_demandes) : sans risque.
- Elle prépare une réponse au crayon (creer_brouillon) : rien ne part.
- Avant de POSTER la lettre (envoyer_brouillon), elle la montre au conseiller : sans « oui »,
  rien ne part.

Brancher sur l'agent (main.py) :
    from gmail import OUTILS_GMAIL
    outils = charger_outils_mcp() + OUTILS_AGENDA + OUTILS_GMAIL
"""

import base64
from email.message import EmailMessage
from email.utils import parseaddr
from typing import Optional

from langchain_core.tools import tool

from agenda import demander_validation   # la même validation « o/n » que pour l'agenda (Atou)

TAILLE_MAX_TEXTE = 3000   # on coupe les très longs mails (coût en tokens + quota Groq)

_gmail = None             # l'objet Google, créé une seule fois (au premier besoin)


# ---------------------------------------------------------------------------
# 1. Petites aides « en coulisse » (le modèle ne les voit pas)
# ---------------------------------------------------------------------------
def _google():
    """Ouvre la connexion à Gmail une seule fois, avec la clé de google_auth.py."""
    global _gmail
    if _gmail is None:
        from google_auth import service_gmail
        _gmail = service_gmail()
    return _gmail


def _entete(message: dict, nom: str) -> str:
    """Lit un en-tête du mail (From, Subject, Message-ID...)."""
    for e in message.get("payload", {}).get("headers", []):
        if e["name"].lower() == nom.lower():
            return e["value"]
    return ""


def _texte_du_mail(partie: dict) -> str:
    """Cherche la partie « texte simple » du mail (un mail peut avoir texte + HTML + pièces jointes)."""
    if partie.get("mimeType") == "text/plain" and partie.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(partie["body"]["data"]).decode("utf-8", errors="replace")
    for sous_partie in partie.get("parts", []) or []:
        texte = _texte_du_mail(sous_partie)
        if texte:
            return texte
    return ""


# ---------------------------------------------------------------------------
# 2. Les actions (outils). La notice entre """ """ est lue par le modèle.
# ---------------------------------------------------------------------------
@tool
def lire_demandes(nombre: int = 5) -> dict:
    """Lit les nouvelles demandes de clients dans la boîte de l'agence (mails non lus).

    Args:
        nombre: nombre maximum de mails à lire (1 à 10). Par défaut 5.
    """
    nombre = max(1, min(int(nombre), 10))
    try:
        # Pour l'instant « non traité » = non lu. À la tâche e4c, on utilisera les libellés.
        reponse = _google().users().messages().list(
            userId="me", labelIds=["INBOX"], q="is:unread", maxResults=nombre).execute()
        demandes = []
        for m in reponse.get("messages", []):
            message = _google().users().messages().get(userId="me", id=m["id"], format="full").execute()
            demandes.append({
                "id_message": message["id"],
                "expediteur": _entete(message, "From"),
                "objet": _entete(message, "Subject"),
                "date": _entete(message, "Date"),
                "texte": (_texte_du_mail(message["payload"]) or message.get("snippet", ""))[:TAILLE_MAX_TEXTE],
            })
    except Exception as e:
        return {"erreur": f"Boîte mail inaccessible : {e}", "conseil": "Réessayer plus tard."}

    if not demandes:
        return {"nombre": 0, "demandes": [], "message": "Aucune nouvelle demande."}
    return {"nombre": len(demandes), "demandes": demandes}


@tool
def creer_brouillon(id_message: str, texte: str) -> dict:
    """Prépare (sans l'envoyer) la réponse au client, dans le même fil que sa demande.
    Le destinataire et l'objet sont repris automatiquement du mail du client.

    Args:
        id_message: l'id_message renvoyé par lire_demandes.
        texte: le texte complet de la réponse, en français, vouvoiement, signé « L'équipe Sama Kër Immobilier ».
    """
    try:
        origine = _google().users().messages().get(
            userId="me", id=id_message, format="metadata",
            metadataHeaders=["From", "Reply-To", "Subject", "Message-ID", "References"]).execute()
    except Exception as e:
        return {"erreur": f"Mail {id_message} introuvable : {e}",
                "conseil": "Utiliser un id_message renvoyé par lire_demandes."}

    # Le destinataire vient du mail d'origine (adresse de réponse, sinon expéditeur)
    destinataire = parseaddr(_entete(origine, "Reply-To") or _entete(origine, "From"))[1]
    if "@" not in destinataire:
        return {"erreur": "Adresse de l'expéditeur illisible.", "conseil": "Transmettre à un conseiller."}
    objet = _entete(origine, "Subject")
    if not objet.lower().startswith("re:"):
        objet = f"Re: {objet}"

    reponse = EmailMessage()
    reponse["To"] = destinataire
    reponse["Subject"] = objet
    # Ces deux en-têtes disent à Gmail (et au client) : « ceci répond à ce mail-là » -> même fil
    id_origine = _entete(origine, "Message-ID")
    if id_origine:
        reponse["In-Reply-To"] = id_origine
        reponse["References"] = f"{_entete(origine, 'References')} {id_origine}".strip()
    reponse.set_content(texte)
    brut = base64.urlsafe_b64encode(reponse.as_bytes()).decode()

    try:
        brouillon = _google().users().drafts().create(
            userId="me", body={"message": {"raw": brut, "threadId": origine["threadId"]}}).execute()
    except Exception as e:
        return {"erreur": f"Brouillon non créé : {e}", "conseil": "Transmettre à un conseiller."}
    return {"statut": "brouillon créé", "id_brouillon": brouillon["id"], "destinataire": destinataire,
            "message": "Brouillon prêt. Il ne part qu'avec envoyer_brouillon, après accord du conseiller."}


@tool
def envoyer_brouillon(id_brouillon: str) -> dict:
    """Envoie un brouillon au client, SEULEMENT si le conseiller le valide (o/n).

    Args:
        id_brouillon: l'id_brouillon renvoyé par creer_brouillon.
    """
    try:
        brouillon = _google().users().drafts().get(userId="me", id=id_brouillon, format="full").execute()
    except Exception as e:
        return {"erreur": f"Brouillon {id_brouillon} introuvable : {e}"}
    message = brouillon["message"]

    # Validation humaine : le conseiller voit QUI reçoit et QUOI, avant tout envoi
    if not demander_validation(
        f"ENVOYER ce mail\n  À : {_entete(message, 'To')}\n  Objet : {_entete(message, 'Subject')}\n"
        f"---\n{_texte_du_mail(message['payload']).strip()}\n---"
    ):
        return {"statut": "refusé", "message": "Le conseiller n'a pas validé : rien n'a été envoyé. "
                                               "Le brouillon reste dans Gmail pour être corrigé."}
    try:
        _google().users().drafts().send(userId="me", body={"id": id_brouillon}).execute()
    except Exception as e:
        return {"erreur": f"Envoi impossible : {e}", "conseil": "Le conseiller enverra le brouillon à la main."}
    return {"statut": "envoyé", "message": "Réponse envoyée au client."}


# La liste à ajouter aux outils de l'agent (main.py)
OUTILS_GMAIL = [lire_demandes, creer_brouillon, envoyer_brouillon]


# Test sans le modèle : « python agent/gmail.py » lit les 3 premières demandes (rien n'est envoyé)
if __name__ == "__main__":
    import json
    print(json.dumps(lire_demandes.invoke({"nombre": 3}), ensure_ascii=False, indent=2))
