"""
poste_conseiller.py : le poste du conseiller de Sama Kër, une page web (Maimouna, 22 nov).

IMAGE SIMPLE : le bureau du conseiller.
  - L'agent (pipeline.py) met en PAUSE chaque dossier qui demande une validation (interrupt).
  - Cette page montre ces dossiers en pause, le plus ancien en haut, avec EXACTEMENT ce qui
    partira au client ou sera créé dans l'agenda.
  - Le conseiller clique : ✅ Valider ou ✋ Refuser (je m'en occupe).
  - La page dépose la décision dans la boîte aux lettres (decisions.py). L'agent la relève
    dans les 5 secondes et relance le dossier là où il s'était arrêté.
  - En haut : le TABLEAU DE BORD (combien de fils dans chaque bannette Gmail, décisions du jour).
  - En bas : les DOSSIERS BLOQUÉS (en attente dans Gmail mais sans post-it) avec 2 boutons :
    👤 je m'en occupe (-> Transmis) ou 🔁 faire retraiter par l'agent (on repart de zéro).
Pendant ce temps, l'agent continue de traiter les autres clients : il n'attend jamais.

LANCEMENT : deux fenêtres PowerShell, venv activé, à la racine du dépôt.
    Fenêtre 1 (l'agent) :  python agent/pipeline.py interface
    Fenêtre 2 (le poste) : streamlit run agent/poste_conseiller.py     -> http://localhost:8501
On peut fermer la page ou arrêter l'agent (Ctrl+C) à tout moment : les dossiers en pause
restent rangés dans le classeur SQLite et réapparaissent au redémarrage.
"""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))
import decisions
from creer_agendas import CONSEILLERS

RELANCE_HEURES = 2     # 🟠 : un dossier attend depuis plus de 2 h
URGENT_HEURES = 24     # 🔴 : plus de 24 h, le confier à un collègue

st.set_page_config(page_title="Sama Kër · Poste du conseiller", page_icon="🏠", layout="centered")
st.title("🏠 Sama Kër Immobilier")
st.caption("Poste du conseiller · rien ne part au client et aucune visite n'est créée sans votre décision")

# Qui décide ? (trace : chaque décision est enregistrée avec le nom du conseiller)
with st.sidebar:
    qui = st.selectbox("Je suis", [c["nom"] for c in CONSEILLERS], index=None, placeholder="Choisir mon nom")
    st.caption(f"🟠 en attente depuis plus de {RELANCE_HEURES} h · 🔴 plus de {URGENT_HEURES} h")
    st.caption("L'agent doit tourner dans une autre fenêtre : python agent/pipeline.py interface")


@st.cache_data(ttl=20, show_spinner=False)
def lire_gmail():
    """Compteurs + dossiers bloqués, relus dans Gmail au plus toutes les 20 s (0 token Groq)."""
    return decisions.compter_aujourdhui(), decisions.dossiers_bloques()


def age(heures: float) -> str:
    duree = f"{int(heures * 60)} min" if heures < 1 else f"{heures:.0f} h"
    if heures >= URGENT_HEURES:
        return f"🔴 en attente depuis {duree} : à confier à un collègue"
    if heures >= RELANCE_HEURES:
        return f"🟠 en attente depuis {duree}"
    return f"🟢 depuis {duree}"


# La bannette se relit toute seule toutes les 5 secondes : les nouveaux dossiers apparaissent seuls.
@st.fragment(run_every="5s")
def bannette():
    deja_decides = {d["id_question"] for d in decisions.a_appliquer()}   # clic fait, l'agent arrive
    dossiers = [d for d in decisions.dossiers_en_attente() if d["id_question"] not in deja_decides]

    # --- 1. Le tableau de bord : ce qu'un conseiller doit savoir d'un coup d'œil -----------------
    try:
        jour_gmail, bloques = lire_gmail()
    except Exception as e:
        jour_gmail, bloques = None, []
        st.warning(f"Gmail inaccessible (token.json ?) : compteurs Gmail indisponibles. {e}")
    vu = decisions.agent_vu_il_y_a()
    agent_actif = vu is not None and vu < 180      # 3 min : le temps de traiter un mail avec Groq
    c = st.columns(5)
    # 1) L'agent tourne-t-il ? S'il est arrêté, vos clics attendront qu'il redémarre.
    c[0].metric("🤖 Agent", "actif" if agent_actif else "arrêté")
    # 2) La charge du conseiller et le retard sur les clients
    c[1].metric("⏸ À valider", len(dossiers))
    # 3) LE chiffre de sécurité : il doit rester à 0 (un client attend une réponse que personne n'enverra)
    c[2].metric("⚠️ Bloqués", len(bloques) if jour_gmail is not None else "?")
    # 4) L'activité du jour (pas les totaux depuis le début, qui grossissent sans rien dire)
    c[3].metric("✅ Répondus", jour_gmail["repondu"] if jour_gmail else "?", help="aujourd'hui")
    c[4].metric("👤 Transmis", jour_gmail["transmis"] if jour_gmail else "?", help="aujourd'hui")
    # Les détails en une phrase
    etat = f"agent vu il y a {int(vu)} s" if agent_actif else "⛔ agent arrêté : lancez python agent/pipeline.py interface"
    attente = f"le plus ancien attend depuis le {dossiers[0]['depuis']}" if dossiers else "aucun client n'attend"
    alerte = " · ⚠️ dossiers bloqués à traiter en bas de page" if bloques else ""
    st.caption(f"{etat} · {attente}{alerte}")
    # 5) La qualité des brouillons de l'agent : beaucoup de refus = revoir le prompt
    jour = decisions.bilan_du_jour()
    decides = jour.get("o", 0) + jour.get("n", 0)
    taux = f"{100 * jour.get('o', 0) // decides} % des propositions validées" if decides else "aucune décision"
    st.caption(f"Aujourd'hui : {taux} ({jour.get('o', 0)} ✅, {jour.get('n', 0)} ✋) · "
               f"{jour.get('main', 0)} pris en main, {jour.get('retraiter', 0)} relancé(s) · "
               "Répondus et Transmis = fils du jour")

    # --- 2. Les dossiers à valider ----------------------------------------------------------
    st.subheader(f"À valider ({len(dossiers)})")
    if deja_decides:
        st.info(f"⏳ {len(deja_decides)} décision(s) transmise(s) : l'agent les applique dans quelques secondes.")
    if not dossiers:
        st.write("Aucun dossier en attente. La page se met à jour toute seule.")
    elif not qui:
        st.warning("Choisissez votre nom dans le menu de gauche pour pouvoir décider.")

    for d in dossiers:
        with st.container(border=True):
            st.caption(f"Dossier {d['fil']} · reçu le {d['depuis']} · {age(d['heures'])}")
            st.text(d["resume"])                        # exactement ce qui partira / sera créé
            c1, c2 = st.columns(2)
            if c1.button("✅ Valider", key=f"o{d['id_question']}", type="primary",
                         disabled=not qui, use_container_width=True):
                decisions.deposer(d, "o", qui)
                st.toast("Validé : l'agent exécute dans quelques secondes.")
                st.rerun()
            if c2.button("✋ Refuser, je m'en occupe", key=f"n{d['id_question']}",
                         disabled=not qui, use_container_width=True):
                decisions.deposer(d, "n", qui)
                st.toast("Refusé : rien ne part. Le fil passe dans « Transmis à un conseiller ».")
                st.rerun()

    # --- 3. Les dossiers bloqués --------------------------------------------------------------
    if bloques:
        st.subheader(f"⚠️ Dossiers bloqués ({len(bloques)})")
        st.caption("En attente dans Gmail, mais sans question en cours chez l'agent (ancien o/n "
                   "interrompu, ou brouillon jamais soumis). Personne ne viendra les chercher : à vous de choisir.")
        for b in bloques:
            with st.container(border=True):
                st.text(f"{b['client']} · {b['objet']}")
                st.caption(f"Dernier message le {b['depuis']} · {len(b['brouillons'])} brouillon(s) · {b['extrait'][:120]}")
                c1, c2 = st.columns(2)
                if c1.button("👤 Je m'en occupe", key=f"m{b['fil']}", disabled=not qui, use_container_width=True):
                    st.toast(decisions.prendre_en_main(b, qui))
                    lire_gmail.clear()
                    st.rerun()
                if c2.button("🔁 Faire retraiter par l'agent", key=f"r{b['fil']}", disabled=not qui,
                             use_container_width=True, help="Supprime le vieux brouillon ; l'agent relit le mail "
                             "et repart de zéro (≈ 14 000 tokens Groq)."):
                    st.toast(decisions.faire_retraiter(b, qui))
                    lire_gmail.clear()
                    st.rerun()

    # --- 4. L'historique ------------------------------------------------------------------------
    st.subheader("Historique")
    lignes = decisions.historique()
    if not lignes:
        st.write("Aucune décision pour l'instant.")
    CHOIX = {"o": "✅ validé", "n": "✋ refusé", "main": "👤 pris en main", "retraiter": "🔁 relancé"}
    for h in lignes:
        choix = CHOIX.get(h["reponse"], h["reponse"])
        etat = h["resultat"] if h["appliquee"] else "⏳ en cours"
        st.text(f"{h['decidee_le']} · {h['fil']} · {choix} par {h['conseiller']}")
        st.caption(f"{h['resume'].splitlines()[0]} → {etat}")


bannette()
