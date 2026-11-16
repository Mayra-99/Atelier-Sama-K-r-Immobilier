"""
google_auth.py : la « clé » qui ouvre Google Calendar pour l'agent (exercice 3, tâche d'Atou e3a).

IMAGE SIMPLE : OAuth, c'est une clé de bureau donnée à la secrétaire (l'agent).
- credentials.json = la carte d'identité de NOTRE application (téléchargée sur Google Cloud).
- token.json       = la clé elle-même, remise par Google APRÈS que le compte de test a dit « j'autorise ».
Les deux restent sur l'ordinateur : ils sont dans .gitignore, ils ne vont JAMAIS sur GitHub.

MOINDRE PRIVILÈGE : on ne demande qu'UN droit, « calendar.app.created ».
Il permet de créer nos propres agendas (un par conseiller) et de lire / créer / modifier /
supprimer les événements DE CES AGENDAS-LÀ seulement. L'agent ne voit donc ni l'agenda
personnel du compte, ni les mails, ni les fichiers Drive.

Utilisation dans le reste du code (actions de l'agenda, script de may) :
    from google_auth import service_calendar
    calendar = service_calendar()

Premier lancement, depuis la racine du dépôt (venv activé) :
    python agent/google_auth.py
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

# Le SEUL droit demandé (voir l'explication en haut du fichier).
# Exercice 4 (Gmail) : on ajoutera ici les droits Gmail, puis on supprimera token.json
# pour redemander l'autorisation une fois.
DROITS = ["https://www.googleapis.com/auth/calendar.app.created"]


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


# Test : « python agent/google_auth.py » vérifie que la clé marche.
if __name__ == "__main__":
    calendar = service_calendar()
    print(f"Clé OK : {CHEMIN_TOKEN.name} créé (il reste sur ce PC, jamais sur GitHub).")
    print(f"Droit accordé : {DROITS[0]}")
    try:
        # Avec ce droit, on ne voit QUE les agendas créés par notre application
        # (au début : aucun, c'est normal ; may créera ceux des 3 conseillers).
        agendas = calendar.calendarList().list().execute().get("items", [])
        print(f"Agendas visibles par l'agent : {[a['summary'] for a in agendas] or 'aucun pour l’instant'}")
    except HttpError as erreur:
        # Si Google refuse cette lecture, la clé marche quand même : c'est le moindre privilège.
        print(f"Lecture de la liste refusée par Google (droits limités, normal) : {erreur.status_code}")
