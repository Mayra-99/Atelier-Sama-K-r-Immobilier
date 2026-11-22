"""
decisions.py : le lien entre le poste du conseiller (page web) et l'agent (pipeline.py). Maimouna.

IMAGE SIMPLE : deux pièces et deux meubles.
  - LE CLASSEUR (checkpoints/conversations.sqlite) : c'est la mémoire de l'agent. Quand un outil
    demande une validation, interrupt() y range le dossier EN PAUSE, avec un post-it « à valider ».
    La page web LIT ce classeur pour afficher les post-its. Elle n'y écrit jamais.
  - LA BOÎTE AUX LETTRES (checkpoints/decisions.sqlite) : quand le conseiller clique, la page y
    dépose un petit papier « dossier X : oui / non, signé Awa ». L'agent passe relever la boîte
    toutes les 5 secondes et relance le dossier avec Command(resume=...).

Pourquoi la page ne relance pas l'agent elle-même ? Parce que l'agent (Groq, serveur MCP, Gmail)
vit dans le programme pipeline.py. La page reste légère : elle lit et elle dépose, c'est tout.
"""

import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CLASSEUR = RACINE / "checkpoints" / "conversations.sqlite"   # la mémoire de l'agent (pipeline.py)
BOITE = RACINE / "checkpoints" / "decisions.sqlite"           # les décisions du conseiller


# ---------------------------------------------------------------------------
# 1. Lire les dossiers en pause dans le classeur (utilisé par la page web)
# ---------------------------------------------------------------------------
def dossiers_en_attente() -> list:
    """Renvoie les dossiers qui attendent le conseiller, le plus ancien d'abord.
    Chaque dossier : {fil, id_question, resume, depuis (date), heures (âge)}."""
    if not CLASSEUR.exists():
        return []                                # l'agent n'a encore traité aucun mail
    from langgraph.checkpoint.sqlite import SqliteSaver   # même format que la mémoire de l'agent

    connexion = sqlite3.connect(str(CLASSEUR), check_same_thread=False)
    try:
        classeur = SqliteSaver(connexion)
        fils = [f for (f,) in connexion.execute("SELECT DISTINCT thread_id FROM checkpoints")]
        dossiers = []
        for fil in fils:
            dernier = classeur.get_tuple({"configurable": {"thread_id": fil}})
            if dernier is None:
                continue
            # Un post-it = une écriture « __interrupt__ » encore sans réponse dans le dernier état
            canaux = {canal for _, canal, _ in dernier.pending_writes or []}
            if "__resume__" in canaux:
                continue                         # déjà répondu, l'agent est en train de reprendre
            for _, canal, valeur in dernier.pending_writes or []:
                if canal != "__interrupt__":
                    continue
                for question in valeur:          # en général une seule question par dossier
                    depuis = datetime.fromisoformat(dernier.checkpoint["ts"])
                    dossiers.append({
                        "fil": fil,
                        "id_question": question.id,
                        "resume": question.value.get("resume", str(question.value)),
                        "depuis": depuis.astimezone().strftime("%d/%m %H:%M"),
                        "heures": (datetime.now(timezone.utc) - depuis).total_seconds() / 3600,
                    })
        return sorted(dossiers, key=lambda d: -d["heures"])
    finally:
        connexion.close()


# ---------------------------------------------------------------------------
# 2. La boîte aux lettres des décisions
# ---------------------------------------------------------------------------
def _boite() -> sqlite3.Connection:
    BOITE.parent.mkdir(exist_ok=True)
    connexion = sqlite3.connect(str(BOITE))
    connexion.row_factory = sqlite3.Row
    connexion.execute("""CREATE TABLE IF NOT EXISTS decisions (
        id_question TEXT PRIMARY KEY,   -- le post-it exact auquel on répond (pas d'erreur de dossier)
        fil         TEXT NOT NULL,
        resume      TEXT NOT NULL,      -- ce que le conseiller a vu au moment de cliquer (trace)
        reponse     TEXT NOT NULL,      -- "o" (valider) ou "n" (refuser)
        conseiller  TEXT NOT NULL,      -- qui a décidé (trace)
        decidee_le  TEXT NOT NULL,
        appliquee   INTEGER DEFAULT 0,  -- 0 = l'agent ne l'a pas encore relevée, 1 = c'est fait
        resultat    TEXT DEFAULT ''     -- ce que l'agent a fait ensuite (phrase finale)
    )""")
    return connexion


def deposer(dossier: dict, reponse: str, conseiller: str) -> None:
    """La page dépose la décision du conseiller. Un 2e clic sur le même post-it est ignoré."""
    with _boite() as c:
        c.execute("INSERT OR IGNORE INTO decisions (id_question, fil, resume, reponse, conseiller, decidee_le) "
                  "VALUES (?, ?, ?, ?, ?, ?)",
                  (dossier["id_question"], dossier["fil"], dossier["resume"], reponse, conseiller,
                   time.strftime("%d/%m %H:%M")))


def a_appliquer() -> list:
    """L'agent relève la boîte : les décisions pas encore appliquées, dans l'ordre des clics."""
    with _boite() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM decisions WHERE appliquee = 0 ORDER BY decidee_le")]


def marquer_appliquee(id_question: str, resultat: str) -> None:
    with _boite() as c:
        c.execute("UPDATE decisions SET appliquee = 1, resultat = ? WHERE id_question = ?",
                  (resultat, id_question))


def historique(limite: int = 20) -> list:
    with _boite() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM decisions ORDER BY rowid DESC LIMIT ?", (limite,))]


def noter_action(fil: str, action: str, conseiller: str, resultat: str) -> None:
    """Trace d'une action sur un dossier bloqué (pas de post-it : l'agent n'a rien à reprendre)."""
    with _boite() as c:
        c.execute("INSERT INTO decisions (id_question, fil, resume, reponse, conseiller, decidee_le, appliquee, resultat) "
                  "VALUES (?, ?, ?, ?, ?, ?, 1, ?)",
                  (f"bloque-{fil}-{time.time()}", fil, "Dossier bloqué", action, conseiller,
                   time.strftime("%d/%m %H:%M"), resultat))


def signe_de_vie() -> None:
    """L'agent (pipeline.py) écrit l'heure à chaque tour : « je suis à mon poste »."""
    with _boite() as c:
        c.execute("CREATE TABLE IF NOT EXISTS etat (cle TEXT PRIMARY KEY, valeur REAL)")
        c.execute("INSERT OR REPLACE INTO etat VALUES ('agent_vu', ?)", (time.time(),))


def agent_vu_il_y_a():
    """Secondes depuis le dernier signe de vie de l'agent, ou None s'il n'a jamais tourné."""
    with _boite() as c:
        c.execute("CREATE TABLE IF NOT EXISTS etat (cle TEXT PRIMARY KEY, valeur REAL)")
        ligne = c.execute("SELECT valeur FROM etat WHERE cle = 'agent_vu'").fetchone()
    return None if ligne is None else time.time() - ligne[0]


def bilan_du_jour() -> dict:
    """Combien de décisions aujourd'hui : {"o": validées, "n": refusées, "main": pris en main, ...}."""
    with _boite() as c:
        lignes = c.execute("SELECT reponse, COUNT(*) FROM decisions WHERE decidee_le LIKE ? GROUP BY reponse",
                           (time.strftime("%d/%m") + "%",)).fetchall()
    return {reponse: nombre for reponse, nombre in lignes}


# ---------------------------------------------------------------------------
# 3. (22 nov, may) Ce que la page lit dans GMAIL : compteurs et dossiers bloqués
#    Même clé token.json que l'agent, aucun appel à Groq (0 token).
# ---------------------------------------------------------------------------
def compter_aujourdhui() -> dict:
    """Combien de fils ont bougé AUJOURD'HUI dans « Répondu » et « Transmis » :
    {"repondu": 3, "transmis": 1}. (Les totaux depuis le début grossissent et ne disent plus rien.)"""
    import gmail
    g = gmail._google().users()
    aujourdhui = time.strftime("%Y/%m/%d")
    return {cle: len(g.threads().list(userId="me", labelIds=[gmail._id_libelle(cle)],
                                      q=f"after:{aujourdhui}", maxResults=100).execute().get("threads", []))
            for cle in ("repondu", "transmis")}


def dossiers_bloques() -> list:
    """Les fils « En attente de validation » SANS post-it dans le classeur.
    IMAGE : une lettre posée sur la pile « à valider », mais sans fiche dans le classeur :
    personne ne viendra la chercher. Ça arrive avec l'ancien input() (un « n », un Ctrl+C)
    ou quand le modèle oublie envoyer_brouillon."""
    import gmail
    g = gmail._google().users()
    avec_post_it = {d["fil"] for d in dossiers_en_attente()} | {d["fil"] for d in a_appliquer()}
    fils = g.threads().list(userId="me", labelIds=[gmail._id_libelle("en_attente")],
                            maxResults=50).execute().get("threads", [])
    # les brouillons, rangés par fil (pour pouvoir les supprimer si on fait retraiter)
    brouillons = {}
    for b in g.drafts().list(userId="me", maxResults=100).execute().get("drafts", []):
        brouillons.setdefault(b["message"]["threadId"], []).append(b["id"])
    bloques = []
    for f in fils:
        if f"gmail-{f['id']}" in avec_post_it:
            continue                                   # il a un post-it : il est dans « À valider »
        detail = g.threads().get(userId="me", id=f["id"], format="metadata",
                                 metadataHeaders=["From", "Subject"]).execute()
        premier = detail["messages"][0]
        dernier = int(detail["messages"][-1].get("internalDate", 0)) / 1000
        bloques.append({
            "fil": f["id"],
            "client": gmail._entete(premier, "From"),
            "objet": gmail._entete(premier, "Subject") or "(aucun objet)",
            "extrait": f.get("snippet", ""),
            "depuis": time.strftime("%d/%m %H:%M", time.localtime(dernier)),
            "brouillons": brouillons.get(f["id"], []),
        })
    return bloques


def prendre_en_main(dossier: dict, conseiller: str) -> str:
    """👤 Le conseiller s'en occupe : le fil passe dans « Transmis », le brouillon reste pour lui."""
    import gmail
    gmail._ranger(dossier["fil"], "transmis")
    resultat = "rangé dans « Transmis à un conseiller » (brouillon gardé dans Gmail)"
    noter_action(f"gmail-{dossier['fil']}", "main", conseiller, resultat)
    return resultat


def faire_retraiter(dossier: dict, conseiller: str) -> str:
    """🔁 L'agent recommence ce dossier à zéro : vieux brouillon supprimé, libellés retirés,
    mémoire du fil vidée (sinon il se souviendrait du brouillon supprimé et voudrait l'envoyer)."""
    import gmail
    from langgraph.checkpoint.sqlite import SqliteSaver
    g = gmail._google().users()
    for id_brouillon in dossier["brouillons"]:
        g.drafts().delete(userId="me", id=id_brouillon).execute()
    g.threads().modify(userId="me", id=dossier["fil"],
                       body={"removeLabelIds": [gmail._id_libelle(c) for c in gmail.LIBELLES]}).execute()
    if CLASSEUR.exists():
        connexion = sqlite3.connect(str(CLASSEUR))
        try:
            SqliteSaver(connexion).delete_thread(f"gmail-{dossier['fil']}")
        finally:
            connexion.close()
    resultat = (f"{len(dossier['brouillons'])} brouillon(s) supprimé(s), mémoire du fil vidée : "
                "l'agent le relit au prochain tour (≈ 30 s)")
    noter_action(f"gmail-{dossier['fil']}", "retraiter", conseiller, resultat)
    return resultat
