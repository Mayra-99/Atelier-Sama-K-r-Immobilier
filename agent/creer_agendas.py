"""
creer_agendas.py : crée un agenda Google par conseiller et y place de faux rendez-vous
(exercice 3, tâche de may e3b).

POURQUOI UN SCRIPT ET PAS À LA MAIN ?
La clé d'Atou (google_auth.py) n'a qu'UN droit : « calendar.app.created ».
L'agent ne voit donc QUE les agendas créés par NOTRE application. Un agenda créé à la main
dans Google Agenda lui serait invisible. C'est le moindre privilège.

IDEMPOTENT (on peut le relancer sans danger) :
- les identifiants des agendas sont rangés dans agent/agendas.json (format convenu avec Atou :
  {"Awa": "...@group.calendar.google.com", ...}). Avec notre droit limité, Google refuse de
  LISTER les agendas (erreur 403) : ce fichier est donc le seul moyen de les retrouver.
  Ces identifiants ne sont pas secrets : le fichier va sur GitHub.
  Si un agenda existe déjà,
  si un agenda existe déjà, on le réutilise au lieu d'en créer un deuxième ;
- chaque faux rendez-vous a un identifiant FIXE : le recréer ne fait pas de doublon.

Lancement, depuis la racine du dépôt (venv activé, credentials.json présent) :
    python agent/creer_agendas.py
"""

import json
from datetime import datetime, time, timedelta
from pathlib import Path

from googleapiclient.errors import HttpError

from google_auth import service_calendar          # la clé d'Atou (e3a)
from regles_agenda import FUSEAU, DUREE_VISITE, en_texte   # le règlement (e3d)

FICHIER_AGENDAS = Path(__file__).resolve().parent / "agendas.json"

# Les 3 conseillers (fictifs) et les quartiers qu'ils suivent
CONSEILLERS = [
    {"cle": "Awa", "nom": "Awa Diop", "quartiers": ["Mermoz", "Sacré-Cœur", "Point E", "Fann Résidence", "Plateau", "Médina"]},
    {"cle": "Ibrahima", "nom": "Ibrahima Sow", "quartiers": ["Almadies", "Ngor", "Ouakam", "Mamelles", "Yoff", "Ouest Foire"]},
    {"cle": "Khady", "nom": "Khady Ba", "quartiers": ["Liberté 6", "Sicap Baobab", "HLM", "Grand Yoff", "Parcelles Assainies"]},
]


def jour_de_la_semaine_prochaine(numero_jour: int):
    """Date du prochain lundi (0) ... samedi (5), à partir de demain."""
    aujourd_hui = datetime.now(FUSEAU).date()
    ecart = (numero_jour - aujourd_hui.weekday()) % 7 or 7
    return aujourd_hui + timedelta(days=ecart)


def faux_rendez_vous():
    """
    Quelques visites déjà prises, pour que les tests aient de vrais « trous » à trouver.
    Exprès : jeudi prochain en fin d'après-midi est en partie occupé (test e3f de Fallou).
    Format : (identifiant fixe, clé du conseiller, jour 0-5, heure, minute, titre)
    Identifiant Google : lettres a à v et chiffres seulement, 5 caractères minimum.
    """
    return [
        ("skrdv0001", "Awa", 3, 16, 30, "Visite SK-001 · client test A"),
        ("skrdv0002", "Awa", 3, 10, 30, "Visite SK-004 · client test B"),
        ("skrdv0003", "Ibrahima", 3, 17, 15, "Visite SK-010 · client test C"),
        ("skrdv0004", "Ibrahima", 1, 9, 45, "Visite SK-012 · client test D"),
        ("skrdv0005", "Khady", 3, 15, 45, "Visite SK-025 · client test E"),
        ("skrdv0006", "Khady", 5, 11, 15, "Visite SK-027 · client test F"),
    ]


def lire_agendas() -> dict:
    """Relit les agendas déjà créés : {"Awa": "id...", ...} (vide la première fois)."""
    if FICHIER_AGENDAS.exists():
        return json.loads(FICHIER_AGENDAS.read_text(encoding="utf-8"))
    return {}


def agenda_existe(calendar, id_agenda: str) -> bool:
    """Vrai si Google connaît encore cet agenda (il n'a pas été supprimé)."""
    try:
        calendar.calendars().get(calendarId=id_agenda).execute()
        return True
    except HttpError:
        return False


def creer_agendas(calendar) -> dict:
    """Crée (ou retrouve) un agenda par conseiller et range leurs identifiants dans agendas.json."""
    deja = lire_agendas()
    resultat = {}
    for c in CONSEILLERS:
        ancien_id = deja.get(c["cle"])
        if ancien_id and agenda_existe(calendar, ancien_id):
            print(f"= Agenda de {c['nom']} déjà présent, réutilisé.")
            resultat[c["cle"]] = ancien_id
            continue
        agenda = calendar.calendars().insert(body={
            "summary": f"Visites · {c['nom']}",
            "description": f"Agenda des visites de {c['nom']} (Sama Kër Immobilier). Quartiers : {', '.join(c['quartiers'])}.",
            "timeZone": "Africa/Dakar",
        }).execute()
        print(f"+ Agenda créé pour {c['nom']}.")
        resultat[c["cle"]] = agenda["id"]   # on GARDE l'identifiant : impossible de le retrouver plus tard

    # On range les identifiants pour les actions de l'agenda (Atou, e3c) et pour la prochaine fois
    FICHIER_AGENDAS.write_text(json.dumps(resultat, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Identifiants rangés dans {FICHIER_AGENDAS.name}")
    return resultat


def placer_faux_rendez_vous(calendar, agendas: dict):
    """Ajoute les faux rendez-vous ; s'ils existent déjà (même identifiant), on passe."""
    for id_rdv, cle, jour, h, m, titre in faux_rendez_vous():
        date_jour = jour_de_la_semaine_prochaine(jour)
        debut = datetime.combine(date_jour, time(h, m), tzinfo=FUSEAU)
        fin = debut + DUREE_VISITE
        evenement = {
            "id": id_rdv,
            "summary": f"[TEST] {titre}",
            "description": "Faux rendez-vous pour les tests de l'atelier.",
            "start": {"dateTime": debut.isoformat(), "timeZone": "Africa/Dakar"},
            "end": {"dateTime": fin.isoformat(), "timeZone": "Africa/Dakar"},
        }
        try:
            calendar.events().insert(calendarId=agendas[cle], body=evenement).execute()
            print(f"+ {cle} : {titre}, {en_texte(debut)}")
        except HttpError as erreur:
            if erreur.status_code == 409:   # 409 = « existe déjà » : pas de doublon, c'est voulu
                print(f"= {id_rdv} déjà présent, ignoré.")
            else:
                raise


if __name__ == "__main__":
    calendar = service_calendar()
    agendas = creer_agendas(calendar)
    placer_faux_rendez_vous(calendar, agendas)
    print("Terminé. Ouvre Google Agenda (compte de TEST) : 3 agendas « Visites · ... » apparaissent à gauche.")
