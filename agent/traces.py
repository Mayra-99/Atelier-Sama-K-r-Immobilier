"""
Traces de l'agent (exercice 1, tâche d'Atou).

Image simple : la trace, c'est le cahier de bord du restaurant. À chaque fois
que le serveur (le modèle) va en cuisine (un outil), on note : quel plat
(le nom de l'outil), avec quelles précisions (les arguments), ce qui est
revenu (le résultat), et combien de temps ça a pris.

Le cahier est un fichier JSONL dans traces/ : une ligne = un événement.

Utilisation dans agent/main.py (code de may), une seule ligne à changer :

    from traces import CahierDeBord

    cahier = CahierDeBord()
    resultat = agent.invoke(
        {"messages": [("user", demande)]},
        config={"callbacks": [cahier], "recursion_limit": 10},
    )
    cahier.afficher_resume()

Ça marche avec n'importe quel agent LangChain / LangGraph, car on passe par
les « callbacks » : des fonctions que LangChain appelle tout seul à chaque
étape, comme une sonnette qui sonne quand un plat part en cuisine.
"""

import json
import time
from datetime import datetime
from pathlib import Path

from langchain_core.callbacks import BaseCallbackHandler

# Dossier traces/ à la racine du dépôt (ce fichier est dans agent/).
DOSSIER_TRACES = Path(__file__).resolve().parent.parent / "traces"


class CahierDeBord(BaseCallbackHandler):
    """Note chaque appel d'outil (et chaque erreur) dans un fichier JSONL."""

    def __init__(self, nom_fichier=None):
        DOSSIER_TRACES.mkdir(exist_ok=True)
        if nom_fichier is None:
            # Un fichier par lancement, daté : trace_20261114_141530.jsonl
            nom_fichier = datetime.now().strftime("trace_%Y%m%d_%H%M%S.jsonl")
        self.chemin = DOSSIER_TRACES / nom_fichier
        self.debuts = {}       # heure de départ de chaque appel en cours
        self.evenements = []   # copie en mémoire, pour le résumé

    # --- petite fonction utilitaire : écrire une ligne dans le cahier ---
    def _noter(self, evenement):
        evenement["heure"] = datetime.now().isoformat(timespec="seconds")
        self.evenements.append(evenement)
        with open(self.chemin, "a", encoding="utf-8") as f:
            f.write(json.dumps(evenement, ensure_ascii=False, default=str) + "\n")

    # 1. Un outil démarre : on note son nom et ses arguments.
    def on_tool_start(self, serialized, input_str, *, run_id, inputs=None, **kwargs):
        self.debuts[run_id] = time.perf_counter()
        self._noter({
            "type": "appel_outil",
            "outil": (serialized or {}).get("name", "?"),
            "arguments": inputs if inputs is not None else input_str,
        })

    # 2. L'outil a répondu : on note le résultat et la durée.
    def on_tool_end(self, output, *, run_id, **kwargs):
        debut = self.debuts.pop(run_id, time.perf_counter())
        contenu = getattr(output, "content", output)   # ToolMessage ou texte
        self._noter({
            "type": "resultat_outil",
            "resultat": str(contenu)[:2000],            # on coupe les très longs résultats
            "duree_s": round(time.perf_counter() - debut, 3),
        })

    # 3. L'outil a planté : on note l'erreur (utile pour l'exercice 6).
    def on_tool_error(self, error, *, run_id, **kwargs):
        self.debuts.pop(run_id, None)
        self._noter({"type": "erreur_outil", "erreur": repr(error)})

    # 4. Le modèle a fini de parler : on note les tokens consommés si dispo.
    def on_llm_end(self, response, **kwargs):
        usage = (response.llm_output or {}).get("token_usage")
        if usage:
            self._noter({"type": "tokens_modele", "usage": usage})

    def afficher_resume(self):
        """Affiche dans le terminal ce qui s'est passé, lisible par un humain."""
        print(f"\n--- Cahier de bord : {self.chemin.name} ---")
        for e in self.evenements:
            if e["type"] == "appel_outil":
                print(f"→ {e['outil']}({e['arguments']})")
            elif e["type"] == "resultat_outil":
                print(f"  ← {e['resultat'][:150]}  ({e['duree_s']} s)")
            elif e["type"] == "erreur_outil":
                print(f"  ✗ ERREUR : {e['erreur']}")
        nb = sum(1 for e in self.evenements if e["type"] == "appel_outil")
        print(f"Total : {nb} appel(s) d'outil\n")
