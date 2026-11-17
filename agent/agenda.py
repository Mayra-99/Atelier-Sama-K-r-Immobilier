"""
agenda.py : les 4 actions de l'agent sur Google Calendar (exercice 3, tâche d'Atou e3c).

IMAGE SIMPLE : l'agent est la SECRÉTAIRE de l'agence, avec le cahier de rendez-vous
des 3 conseillers.
- Elle peut LIRE le cahier quand elle veut (lister les créneaux libres) : sans risque.
- Elle peut ÉCRIRE, DÉPLACER ou RAYER un rendez-vous, en respectant le règlement.
  (Étape suivante, e3e : demander l'accord du conseiller avant chaque écriture.)

Ce fichier s'appuie sur le travail de l'équipe :
- google_auth.py     (Atou) : la clé OAuth, droit minimal calendar.app.created ;
- regles_agenda.py   (may)  : 45 min, lundi-samedi 9h-18h, Africa/Dakar, adresse dans l'événement ;
- creer_agendas.py   (may)  : la liste CONSEILLERS (nom complet, quartiers suivis) ;
- agendas.json       (may)  : les identifiants Google des 3 agendas, {"Awa": "...", ...} ;
- serveur_mcp/catalogue.db  : lu EN LECTURE SEULE pour recopier l'adresse exacte du bien
  (on ne laisse pas le modèle recopier une adresse : il pourrait se tromper).

AUCUN DOUBLON (idempotence) : l'identifiant Google d'une visite est CALCULÉ à partir du
conseiller et de l'heure. Deux demandes sur le même créneau donnent le même identifiant :
Google refuse la deuxième (erreur 409), donc jamais deux visites au même moment.

Brancher sur l'agent (main.py) :
    from agenda import OUTILS_AGENDA
    outils = charger_outils_mcp() + OUTILS_AGENDA
"""

import hashlib
import json
import sqlite3
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Optional

from googleapiclient.errors import HttpError
from langchain_core.tools import tool

from regles_agenda import (DUREE_VISITE, FUSEAU, a_dakar, construire_evenement,
                           creneaux_libres, en_texte, lire_date_google, verifier_creneau)

DOSSIER = Path(__file__).resolve().parent
FICHIER_AGENDAS = DOSSIER / "agendas.json"
CHEMIN_CATALOGUE = DOSSIER.parent / "serveur_mcp" / "catalogue.db"

_calendar = None   # l'objet Google, créé une seule fois (au premier besoin)


# ---------------------------------------------------------------------------
# 1. Petites aides « en coulisse » (le modèle ne les voit pas)
# ---------------------------------------------------------------------------
def _google():
    """Ouvre la connexion à Google Calendar une seule fois, avec la clé d'Atou."""
    global _calendar
    if _calendar is None:
        from google_auth import service_calendar
        _calendar = service_calendar()
    return _calendar


def _conseillers() -> dict:
    """Assemble, pour chaque conseiller : son nom complet, ses quartiers (creer_agendas.py de may)
    et l'identifiant de son agenda (agendas.json, écrit par le même script).
    Résultat : {"Awa": {"nom": "Awa Diop", "quartiers": [...], "id_agenda": "..."}, ...}"""
    from creer_agendas import CONSEILLERS
    if not FICHIER_AGENDAS.exists():
        raise FileNotFoundError("agendas.json absent : lancer d'abord python agent/creer_agendas.py")
    ids = json.loads(FICHIER_AGENDAS.read_text(encoding="utf-8"))
    return {c["cle"]: {"nom": c["nom"], "quartiers": c["quartiers"], "id_agenda": ids[c["cle"]]}
            for c in CONSEILLERS if c["cle"] in ids}


def _sans_accents(texte: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", texte.lower()) if unicodedata.category(c) != "Mn")


def _conseiller_du_quartier(quartier: str) -> Optional[str]:
    """Renvoie la clé du conseiller qui suit ce quartier (ex. 'Mermoz' -> 'Awa')."""
    for cle, c in _conseillers().items():
        if any(_sans_accents(quartier) in _sans_accents(q) for q in c["quartiers"]):
            return cle
    return None


def _fiche_bien(id_bien: str) -> Optional[dict]:
    """Lit la fiche d'un bien dans le catalogue, en lecture seule."""
    if not CHEMIN_CATALOGUE.exists():
        return None
    uri = f"file:{CHEMIN_CATALOGUE.as_posix()}?mode=ro"          # ro = read only
    with sqlite3.connect(uri, uri=True) as connexion:
        connexion.row_factory = sqlite3.Row
        ligne = connexion.execute("SELECT * FROM biens WHERE id = ?", (id_bien.strip().upper(),)).fetchone()
    return dict(ligne) if ligne else None


def _lire_debut(texte: str) -> datetime:
    """'2026-11-19T16:30' -> datetime à l'heure de Dakar."""
    return a_dakar(datetime.fromisoformat(texte.strip()))


def _id_visite(cle_conseiller: str, debut: datetime) -> str:
    """Identifiant calculé : même conseiller + même heure = même identifiant (anti-doublon).
    Google accepte les lettres a-v et les chiffres : un code hexadécimal (0-9, a-f) convient."""
    return "visite" + hashlib.sha1(f"{cle_conseiller}|{debut.isoformat()}".encode()).hexdigest()[:20]


def _occupations(id_agenda: str, du: datetime, au: datetime, sauf: Optional[str] = None) -> list:
    """Les plages déjà prises dans un agenda entre deux moments (on peut en exclure une)."""
    reponse = _google().events().list(
        calendarId=id_agenda, timeMin=du.isoformat(), timeMax=au.isoformat(),
        singleEvents=True, orderBy="startTime",
    ).execute()
    plages = []
    for ev in reponse.get("items", []):
        if ev.get("status") == "cancelled" or ev["id"] == sauf or "dateTime" not in ev["start"]:
            continue
        plages.append((lire_date_google(ev["start"]["dateTime"]), lire_date_google(ev["end"]["dateTime"])))
    return plages


def _creneau_pris(id_agenda: str, debut: datetime, sauf: Optional[str] = None) -> bool:
    """Vrai si la visite [debut, debut + 45 min] tombe sur un rendez-vous existant."""
    fin = debut + DUREE_VISITE
    return any(d < fin and debut < f for d, f in _occupations(id_agenda, debut, fin, sauf))


# ---------------------------------------------------------------------------
# 2. Les 4 actions (outils). La notice entre """ """ est lue par le modèle.
# ---------------------------------------------------------------------------
@tool
def lister_creneaux_libres(date_debut: str, date_fin: Optional[str] = None,
                           apres_heure: Optional[str] = None, quartier: Optional[str] = None) -> dict:
    """Propose les 3 premiers créneaux de visite RÉELLEMENT libres (45 min, lundi-samedi 9h-18h, heure de Dakar).

    Args:
        date_debut: premier jour cherché, format "AAAA-MM-JJ" (ex. "2026-11-19" pour jeudi prochain).
        date_fin: dernier jour cherché, format "AAAA-MM-JJ". Par défaut : le même jour que date_debut.
        apres_heure: ne garder que les créneaux à partir de cette heure, format "HH:MM".
            « fin d’après-midi » = "15:00", « après-midi » = "14:00", « matin » : laisser vide.
        quartier: quartier du bien à visiter ; le conseiller qui suit ce quartier est choisi.
            Si vide, on regarde les 3 conseillers.
    """
    try:
        du = date.fromisoformat(date_debut)
        au = date.fromisoformat(date_fin) if date_fin else du
        apres = time.fromisoformat(apres_heure) if apres_heure else None
    except ValueError:
        return {"erreur": "Format invalide.", "conseil": "Dates en AAAA-MM-JJ, heure en HH:MM."}

    try:
        conseillers = _conseillers()
        cles = list(conseillers)
        if quartier:
            cle = _conseiller_du_quartier(quartier)
            if cle is None:
                return {"erreur": f"Aucun conseiller ne suit le quartier « {quartier} »."}
            cles = [cle]

        debut_periode = datetime.combine(du, time(0, 0), tzinfo=FUSEAU)
        fin_periode = datetime.combine(au + timedelta(days=1), time(0, 0), tzinfo=FUSEAU)
        propositions = []
        for cle in cles:
            occupees = _occupations(conseillers[cle]["id_agenda"], debut_periode, fin_periode)
            for c in creneaux_libres(du, au, occupees, apres=apres, nombre=3):
                propositions.append({"conseiller": cle, "nom_conseiller": conseillers[cle]["nom"],
                                     "debut": c.strftime("%Y-%m-%dT%H:%M"), "lisible": en_texte(c)})
    except Exception as e:
        return {"erreur": f"Agenda inaccessible : {e}",
                "conseil": "Dire au client qu'un conseiller le recontactera pour fixer la visite."}

    propositions.sort(key=lambda p: p["debut"])
    if not propositions:
        return {"nombre": 0, "creneaux": [], "message": "Aucun créneau libre sur cette période."}
    return {"nombre": len(propositions[:3]), "creneaux": propositions[:3]}


@tool
def creer_visite(id_bien: str, debut: str, client: str, conseiller: Optional[str] = None) -> dict:
    """Réserve une visite dans l'agenda du conseiller.

    Args:
        id_bien: identifiant du bien à visiter, ex. "SK-001" (renvoyé par rechercher_biens).
        debut: début de la visite, format "AAAA-MM-JJTHH:MM" (ex. "2026-11-19T16:00"),
            de préférence un créneau proposé par lister_creneaux_libres.
        client: nom du client, ex. "Mme Diallo".
        conseiller: clé du conseiller ("Awa", "Ibrahima" ou "Khady"). Si vide : celui du quartier du bien.
    """
    bien = _fiche_bien(id_bien)
    if bien is None:
        return {"erreur": f"Bien {id_bien} introuvable dans le catalogue.", "conseil": "Ne pas inventer de bien."}
    try:
        moment = _lire_debut(debut)
    except ValueError:
        return {"erreur": "Format de date invalide.", "conseil": "Utiliser AAAA-MM-JJTHH:MM."}
    probleme = verifier_creneau(moment)
    if probleme:
        return {"erreur": probleme, "conseil": "Proposer un autre créneau avec lister_creneaux_libres."}

    try:
        conseillers = _conseillers()
        cle = conseiller or _conseiller_du_quartier(bien["quartier"])
        if cle not in conseillers:
            return {"erreur": f"Conseiller « {conseiller} » inconnu.", "conseil": f"Choisir parmi {list(conseillers)}."}
        id_agenda, nom = conseillers[cle]["id_agenda"], conseillers[cle]["nom"]

        # Le créneau a pu être pris entre la proposition et la réservation : on revérifie.
        if _creneau_pris(id_agenda, moment):
            return {"erreur": f"Le créneau {en_texte(moment)} n'est plus libre chez {nom}.",
                    "conseil": "Relancer lister_creneaux_libres et proposer un autre créneau."}

        evenement = construire_evenement(moment, bien, client, nom)    # règles de may
        evenement["id"] = _id_visite(cle, moment)

        try:
            _google().events().insert(calendarId=id_agenda, body=evenement).execute()
        except HttpError as e:
            if e.status_code != 409:
                raise
            # 409 = cet identifiant existe déjà : même conseiller, même heure -> pas de doublon
            existant = _google().events().get(calendarId=id_agenda, eventId=evenement["id"]).execute()
            if existant.get("status") != "cancelled":
                return {"statut": "déjà réservé", "id_visite": evenement["id"],
                        "message": f"Une visite existe déjà à ce créneau chez {nom} : aucun doublon créé."}
            # Ancienne visite annulée au même créneau : on la réactive au lieu d'en créer une autre
            evenement["status"] = "confirmed"
            _google().events().update(calendarId=id_agenda, eventId=evenement["id"], body=evenement).execute()
    except Exception as e:
        return {"erreur": f"Agenda inaccessible : {e}", "conseil": "Transmettre la demande à un conseiller."}

    return {"statut": "créée", "id_visite": evenement["id"], "conseiller": cle,
            "message": f"Visite de {bien['id']} réservée {en_texte(moment)} avec {nom}, au {bien['adresse']}."}


@tool
def deplacer_visite(id_visite: str, conseiller: str, nouveau_debut: str) -> dict:
    """Déplace une visite existante vers un autre créneau.

    Args:
        id_visite: identifiant renvoyé par creer_visite (commence par "visite").
        conseiller: clé du conseiller de la visite ("Awa", "Ibrahima" ou "Khady").
        nouveau_debut: nouveau début, format "AAAA-MM-JJTHH:MM".
    """
    try:
        moment = _lire_debut(nouveau_debut)
    except ValueError:
        return {"erreur": "Format de date invalide.", "conseil": "Utiliser AAAA-MM-JJTHH:MM."}
    probleme = verifier_creneau(moment)
    if probleme:
        return {"erreur": probleme}
    try:
        conseillers = _conseillers()
        if conseiller not in conseillers:
            return {"erreur": f"Conseiller « {conseiller} » inconnu.", "conseil": f"Choisir parmi {list(conseillers)}."}
        id_agenda, nom = conseillers[conseiller]["id_agenda"], conseillers[conseiller]["nom"]
        try:
            ev = _google().events().get(calendarId=id_agenda, eventId=id_visite).execute()
        except HttpError:
            return {"erreur": f"Visite {id_visite} introuvable chez {nom}."}
        if ev.get("status") == "cancelled":
            return {"erreur": "Cette visite a été annulée : on ne peut pas la déplacer."}
        ancien = lire_date_google(ev["start"]["dateTime"])
        if _creneau_pris(id_agenda, moment, sauf=id_visite):
            return {"erreur": f"Le créneau {en_texte(moment)} n'est pas libre chez {nom}.",
                    "conseil": "Proposer un autre créneau avec lister_creneaux_libres."}


        _google().events().patch(calendarId=id_agenda, eventId=id_visite, body={
            "start": {"dateTime": moment.isoformat(), "timeZone": "Africa/Dakar"},
            "end": {"dateTime": (moment + DUREE_VISITE).isoformat(), "timeZone": "Africa/Dakar"},
        }).execute()
    except Exception as e:
        return {"erreur": f"Agenda inaccessible : {e}", "conseil": "Transmettre la demande à un conseiller."}
    return {"statut": "déplacée", "message": f"Visite déplacée de {en_texte(ancien)} à {en_texte(moment)} avec {nom}."}


@tool
def annuler_visite(id_visite: str, conseiller: str) -> dict:
    """Annule une visite existante.

    Args:
        id_visite: identifiant renvoyé par creer_visite (commence par "visite").
        conseiller: clé du conseiller de la visite ("Awa", "Ibrahima" ou "Khady").
    """
    try:
        conseillers = _conseillers()
        if conseiller not in conseillers:
            return {"erreur": f"Conseiller « {conseiller} » inconnu.", "conseil": f"Choisir parmi {list(conseillers)}."}
        id_agenda, nom = conseillers[conseiller]["id_agenda"], conseillers[conseiller]["nom"]
        try:
            ev = _google().events().get(calendarId=id_agenda, eventId=id_visite).execute()
        except HttpError:
            return {"erreur": f"Visite {id_visite} introuvable chez {nom}."}
        if ev.get("status") == "cancelled":
            return {"statut": "déjà annulée", "message": "Cette visite était déjà annulée."}


        _google().events().delete(calendarId=id_agenda, eventId=id_visite).execute()
    except Exception as e:
        return {"erreur": f"Agenda inaccessible : {e}", "conseil": "Transmettre la demande à un conseiller."}
    return {"statut": "annulée", "message": f"Visite annulée chez {nom}."}


# La liste à ajouter aux outils de l'agent (main.py)
OUTILS_AGENDA = [lister_creneaux_libres, creer_visite, deplacer_visite, annuler_visite]
