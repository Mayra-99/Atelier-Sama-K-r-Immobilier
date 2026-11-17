"""
regles_agenda.py : les règles de l'agence pour les visites (exercice 3, tâche de may e3d).

IMAGE SIMPLE : c'est le règlement affiché au mur de l'agence.
Les actions de l'agenda (Atou, e3c) le consultent AVANT de proposer ou de créer une visite :
- une visite dure 45 minutes ;
- on visite du lundi au samedi, de 9 h à 18 h (la visite doit être FINIE à 18 h) ;
- toutes les heures sont à l'heure de Dakar (fuseau Africa/Dakar) ;
- l'adresse du bien est écrite dans l'événement (champ « lieu »).

Ce fichier ne parle PAS à Google : il ne fait que des calculs. On peut donc le tester
sans compte Google :  python agent/regles_agenda.py

Utilisation dans le reste du code :
    from regles_agenda import creneaux_libres, verifier_creneau, construire_evenement
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo   # sous Windows, il faut le paquet « tzdata » (requirements.txt)

# ---------------------------------------------------------------------------
# 1. Les règles, en un seul endroit (si l'agence change d'horaires, on ne touche qu'ici)
# ---------------------------------------------------------------------------
FUSEAU = ZoneInfo("Africa/Dakar")
DUREE_VISITE = timedelta(minutes=45)
OUVERTURE = time(9, 0)             # première visite possible à 9 h 00
FERMETURE = time(18, 0)            # la visite doit être terminée à 18 h 00
JOURS_OUVRES = {0, 1, 2, 3, 4, 5}  # lundi = 0 ... samedi = 5 (dimanche = 6 : fermé)
PAS = timedelta(minutes=45)        # écart entre deux débuts de créneau : 9h00, 9h45, 10h30...

NOMS_JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


# ---------------------------------------------------------------------------
# 2. Petits outils sur les dates
# ---------------------------------------------------------------------------
def a_dakar(moment: datetime) -> datetime:
    """Met une date à l'heure de Dakar. Une date sans fuseau est considérée comme déjà à Dakar."""
    if moment.tzinfo is None:
        return moment.replace(tzinfo=FUSEAU)
    return moment.astimezone(FUSEAU)


def lire_date_google(texte: str) -> datetime:
    """Transforme une date renvoyée par Google ('2026-11-19T16:30:00Z' ou '+00:00') en datetime à Dakar."""
    return a_dakar(datetime.fromisoformat(texte.replace("Z", "+00:00")))


def en_texte(moment: datetime) -> str:
    """Écrit un créneau lisiblement pour le client : 'jeudi 19/11 à 16h30'."""
    m = a_dakar(moment)
    return f"{NOMS_JOURS[m.weekday()]} {m:%d/%m} à {m:%H}h{m:%M}"


# ---------------------------------------------------------------------------
# 3. Vérifier qu'un créneau respecte les règles
# ---------------------------------------------------------------------------
def verifier_creneau(debut: datetime) -> str | None:
    """
    Renvoie None si le créneau est autorisé, sinon une phrase qui explique pourquoi.
    (Une phrase claire aide le modèle à corriger sa demande au tour suivant.)
    """
    debut = a_dakar(debut)
    fin = debut + DUREE_VISITE
    if debut.weekday() not in JOURS_OUVRES:
        return "L'agence ne fait pas de visite le dimanche."
    if debut.time() < OUVERTURE:
        return "Les visites commencent à 9h00 au plus tôt."
    if fin.date() != debut.date() or fin.time() > FERMETURE:
        return "La visite doit être terminée à 18h00 : dernier début possible 17h15."
    if debut < datetime.now(FUSEAU):
        return "Ce créneau est déjà passé."
    return None


# ---------------------------------------------------------------------------
# 4. Fabriquer tous les créneaux possibles sur une période
# ---------------------------------------------------------------------------
def creneaux_possibles(du: date, au: date, apres: time | None = None) -> list[datetime]:
    """
    Tous les débuts de visite autorisés entre deux dates (incluses), sans regarder l'agenda.
    'apres' permet de ne garder que la fin de journée (ex. time(16, 0) pour « fin d'après-midi »).
    """
    resultat = []
    jour = du
    while jour <= au:
        if jour.weekday() in JOURS_OUVRES:
            moment = datetime.combine(jour, OUVERTURE, tzinfo=FUSEAU)
            while (moment + DUREE_VISITE).time() <= FERMETURE and (moment + DUREE_VISITE).date() == jour:
                if (apres is None or moment.time() >= apres) and verifier_creneau(moment) is None:
                    resultat.append(moment)
                moment += PAS
        jour += timedelta(days=1)
    return resultat


def chevauche(debut: datetime, occupations: list[tuple[datetime, datetime]]) -> bool:
    """Vrai si la visite [debut, debut + 45 min] touche une plage déjà occupée."""
    fin = debut + DUREE_VISITE
    return any(debut < occ_fin and occ_debut < fin for occ_debut, occ_fin in occupations)


def creneaux_libres(du: date, au: date, occupations: list[tuple[datetime, datetime]],
                    apres: time | None = None, nombre: int = 3) -> list[datetime]:
    """
    Les 'nombre' premiers créneaux autorisés ET libres.
    'occupations' = les plages déjà prises dans l'agenda du conseiller (début, fin),
    lues par l'action de l'agenda (Google « freebusy » ou liste des événements).
    """
    occupations = [(a_dakar(d), a_dakar(f)) for d, f in occupations]
    libres = [c for c in creneaux_possibles(du, au, apres) if not chevauche(c, occupations)]
    return libres[:nombre]


# ---------------------------------------------------------------------------
# 5. Construire l'événement Google Calendar d'une visite
# ---------------------------------------------------------------------------
def construire_evenement(debut: datetime, bien: dict, client: str, conseiller: str) -> dict:
    """
    Le « formulaire » à envoyer à Google pour créer la visite.
    'bien' = la fiche renvoyée par detail_bien (id, type, quartier, adresse, pieces, loyer).
    L'adresse va dans 'location' : Google Agenda l'affiche avec un lien vers la carte.
    """
    probleme = verifier_creneau(debut)
    if probleme:
        raise ValueError(probleme)
    debut = a_dakar(debut)
    fin = debut + DUREE_VISITE
    loyer = f"{bien['loyer']:,}".replace(",", " ")   # 350000 -> "350 000"
    return {
        "summary": f"Visite {bien['id']} · {client}",
        "location": bien["adresse"],
        "description": (
            f"Visite du bien {bien['id']} : {bien['type']} de {bien['pieces']} pièce(s) "
            f"à {bien['quartier']}, loyer {loyer} F CFA/mois.\n"
            f"Client : {client}\nConseiller : {conseiller}\n"
            "Créé par l'agent Sama Kër après validation du conseiller."
        ),
        "start": {"dateTime": debut.isoformat(), "timeZone": "Africa/Dakar"},
        "end": {"dateTime": fin.isoformat(), "timeZone": "Africa/Dakar"},
    }


# ---------------------------------------------------------------------------
# 6. Petit test sans Google : python agent/regles_agenda.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    aujourd_hui = datetime.now(FUSEAU).date()
    jeudi = aujourd_hui + timedelta(days=(3 - aujourd_hui.weekday()) % 7 or 7)  # jeudi prochain
    print(f"Jeudi prochain : {jeudi:%d/%m/%Y}")

    tous = creneaux_possibles(jeudi, jeudi)
    print(f"Créneaux possibles ce jour-là : {len(tous)} (de {en_texte(tous[0])} à {en_texte(tous[-1])})")

    # On imagine que le conseiller a déjà une visite de 16h30 à 17h15
    occupe = [(datetime.combine(jeudi, time(16, 30), tzinfo=FUSEAU),
               datetime.combine(jeudi, time(17, 15), tzinfo=FUSEAU))]
    proposes = creneaux_libres(jeudi, jeudi, occupe, apres=time(15, 0))
    print("Fin d'après-midi, 3 créneaux libres :", [en_texte(c) for c in proposes])

    dimanche = datetime.combine(jeudi + timedelta(days=3), time(10, 0), tzinfo=FUSEAU)
    print("Dimanche 10h ->", verifier_creneau(dimanche))
    print("17h30 ->", verifier_creneau(datetime.combine(jeudi, time(17, 30), tzinfo=FUSEAU)))

    bien = {"id": "SK-001", "type": "appartement", "quartier": "Mermoz",
            "adresse": "Rue MZ-12, Villa 45, Mermoz", "pieces": 3, "loyer": 350000}
    ev = construire_evenement(proposes[0], bien, "Mme Diallo", "Awa Diop")
    print("Événement :", ev["summary"], "|", ev["location"], "|", ev["start"]["dateTime"], "->", ev["end"]["dateTime"])
