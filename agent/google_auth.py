"""
google_auth.py : la « clé » qui ouvre Google Calendar et Gmail pour l'agent.
Exercice 3 : tâche d'Atou (e3a). Exercice 4 : ajout du droit Gmail par may (e4a).

IMAGE SIMPLE : OAuth, c'est une clé de bureau donnée à la secrétaire (l'agent).
- credentials.json = la carte d'identité de NOTRE application (téléchargée sur Google Cloud).
- token.json       = la clé elle-même, remise par Google APRÈS que le compte de test a dit « j'autorise ».
Les deux restent sur l'ordinateur : ils sont dans .gitignore, ils ne vont JAMAIS sur GitHub.

MOINDRE PRIVILÈGE : on ne demande que DEUX droits.
- « calendar.app.created » (exercice 3) : créer nos propres agendas (un par conseiller) et
  gérer les événements DE CES AGENDAS-LÀ seulement (pas l'agenda personnel du compte).
- « gmail.modify » (exercice 4) : lire les mails, poser des libellés, créer des brouillons
  et les envoyer. Il ne permet PAS de supprimer définitivement un mail.
  Pourquoi pas « gmail.readonly » + « gmail.compose » ? readonly ne permet pas de changer
  les libellés (tâche e4c), donc il faudrait quand même modify : un seul droit suffit.
L'agent ne voit jamais les fichiers Drive ni les contacts.

Utilisation dans le reste du code :
    from google_auth import service_calendar, service_gmail
    calendar = service_calendar()     # agenda.py, creer_agendas.py
    gmail = service_gmail()           # gmail.py (exercice 4)

Premier lancement, depuis la racine du dépôt (venv activé) :
    python agent/google_auth.py
APRÈS L'AJOUT DU DROIT GMAIL : supprimer token.json, puis relancer cette commande une fois
(l'ancienne clé ne contient que le droit Calendar ; Google refuserait les appels Gmail).
Le navigateur s'ouvre : se connecter avec le compte Google DE TEST, puis « Autoriser ».
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

RACINE = Path(__file__).resolve().parent.parent
load_dotenv(RACINE / ".env")

# Chemins des deux fichiers secrets (valeurs par défaut : à la racine du dépôt)
CHEMIN_CREDENTIALS = RACINE / os.getenv("GOOGLE_CREDENTIALS", "credentials.json")
CHEMIN_TOKEN = RACINE / os.getenv("GOOGLE_TOKEN", "token.json")

# Les SEULS droits demandés (voir l'explication en haut du fichier).
DROITS = [
    "https://www.googleapis.com/auth/calendar.app.created",   # exercice 3 : nos agendas seulement
    "https://www.googleapis.com/auth/gmail.modify",           # exercice 4 : lire, libellés, brouillons, envoi
]


def obtenir_identifiants() -> Credentials:
    """Renvoie une clé valide : la relit, la renouvelle, ou la demande au compte de test."""
    identifiants = None

    # 1. Une clé existe déjà sur l'ordinateur ? On la relit.
    if CHEMIN_TOKEN.exists():
        identifiants = Credentials.from_authorized_user_file(str(CHEMIN_TOKEN), DROITS)

    # 2. Clé absente ou périmée ?
    if not identifiants or not identifiants.valid:
        if identifiants and identifiants.expired and identifiants.refresh_token:
            # 2a. Périmée : on la renouvelle en silence (pas besoin du navigateur)
            identifiants.refresh(Request())
        else:
            # 2b. Pas de clé : on ouvre le navigateur pour que le compte de test autorise
            if not CHEMIN_CREDENTIALS.exists():
                raise SystemExit(
                    f"Fichier introuvable : {CHEMIN_CREDENTIALS.name}. "
                    "Le télécharger depuis Google Cloud (Identifiants > ID client OAuth) "
                    "et le placer à la racine du dépôt."
                )
            flux = InstalledAppFlow.from_client_secrets_file(str(CHEMIN_CREDENTIALS), DROITS)
            identifiants = flux.run_local_server(port=0)

        # 3. On range la clé dans token.json pour les prochaines fois
        CHEMIN_TOKEN.write_text(identifiants.to_json(), encoding="utf-8")

    return identifiants


def service_calendar():
    """Renvoie l'objet qui parle à l'API Google Calendar, prêt à l'emploi."""
    return build("calendar", "v3", credentials=obtenir_identifiants())


def service_gmail():
    """Renvoie l'objet qui parle à l'API Gmail, prêt à l'emploi (exercice 4)."""
    return build("gmail", "v1", credentials=obtenir_identifiants())


# Test : « python agent/google_auth.py » vérifie que la clé marche.
if __name__ == "__main__":
    calendar = service_calendar()
    print(f"Clé OK : {CHEMIN_TOKEN.name} créé (il reste sur ce PC, jamais sur GitHub).")
    print(f"Droits accordés : {', '.join(DROITS)}")
    try:
        # Avec ce droit, on ne voit QUE les agendas créés par notre application
        # (au début : aucun, c'est normal ; may créera ceux des 3 conseillers).
        agendas = calendar.calendarList().list().execute().get("items", [])
        print(f"Agendas visibles par l'agent : {[a['summary'] for a in agendas] or 'aucun pour l’instant'}")
    except HttpError as erreur:
        # Si Google refuse cette lecture, la clé marche quand même : c'est le moindre privilège.
        print(f"Lecture de la liste refusée par Google (droits limités, normal) : {erreur.status_code}")

    # Exercice 4 : on vérifie aussi Gmail (adresse du compte connecté)
    try:
        profil = service_gmail().users().getProfile(userId="me").execute()
        print(f"Gmail OK : boîte {profil['emailAddress']} ({profil.get('messagesTotal', '?')} messages)")
    except HttpError as erreur:
        print(f"Gmail refusé ({erreur.status_code}) : supprimer token.json, activer Gmail API, relancer.")
