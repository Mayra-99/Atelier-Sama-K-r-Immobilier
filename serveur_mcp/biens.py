"""
biens.py : les 30 biens fictifs du catalogue de Sama Kër Immobilier.

Ce fichier ne contient QUE des données (pas de base, pas de modèle).
- Le script de may (serveur_mcp/creer_catalogue.py) lit la liste BIENS
  et la range dans la base SQLite catalogue.db.
- Tous les biens sont inventés : aucune vraie adresse, aucun vrai client.

Chaque bien est un dictionnaire avec toujours les mêmes clés :
    id            : identifiant unique, ex. "SK-001" (l'agent s'en sert pour detail_bien)
    type          : "studio", "appartement", "villa" ou "chambre"
    quartier      : quartier de Dakar
    adresse       : adresse fictive (sera mise dans l'événement de visite à l'exercice 3)
    pieces        : nombre de pièces principales (F3 = 3 pièces : salon + 2 chambres)
    loyer         : loyer mensuel en F CFA (nombre entier, sans espace)
    meuble        : True si le bien est meublé, sinon False
    disponible    : True si on peut le louer, False s'il est déjà loué
    disponible_le : date à partir de laquelle on peut entrer (AAAA-MM-JJ), None si loué
"""

BIENS = [
    # --- Mermoz : plusieurs F3 pour tester « un F3 à Mermoz à moins de 400 000 F » ---
    {"id": "SK-001", "type": "appartement", "quartier": "Mermoz", "adresse": "Rue MZ-12, Villa 45, Mermoz",
     "pieces": 3, "loyer": 350000, "meuble": False, "disponible": True, "disponible_le": "2026-11-20"},
    {"id": "SK-002", "type": "appartement", "quartier": "Mermoz", "adresse": "Rue MZ-27, Immeuble Kër Ndiaye, 2e étage, Mermoz",
     "pieces": 3, "loyer": 450000, "meuble": True, "disponible": True, "disponible_le": "2026-12-01"},
    {"id": "SK-003", "type": "appartement", "quartier": "Mermoz", "adresse": "Rue MZ-08, Villa 12, Mermoz",
     "pieces": 2, "loyer": 250000, "meuble": False, "disponible": False, "disponible_le": None},
    {"id": "SK-004", "type": "studio", "quartier": "Mermoz", "adresse": "Rue MZ-33, Studio B, Mermoz",
     "pieces": 1, "loyer": 150000, "meuble": True, "disponible": True, "disponible_le": "2026-11-16"},

    # --- Sacré-Cœur ---
    {"id": "SK-005", "type": "appartement", "quartier": "Sacré-Cœur", "adresse": "Sacré-Cœur 3, Villa 8810",
     "pieces": 3, "loyer": 300000, "meuble": False, "disponible": True, "disponible_le": "2026-11-25"},
    {"id": "SK-006", "type": "appartement", "quartier": "Sacré-Cœur", "adresse": "Sacré-Cœur 2, Immeuble Baobab, 1er étage",
     "pieces": 4, "loyer": 420000, "meuble": False, "disponible": True, "disponible_le": "2026-12-15"},
    {"id": "SK-007", "type": "studio", "quartier": "Sacré-Cœur", "adresse": "Sacré-Cœur 1, Villa 120, studio arrière",
     "pieces": 1, "loyer": 120000, "meuble": False, "disponible": False, "disponible_le": None},

    # --- Point E et Fann ---
    {"id": "SK-008", "type": "appartement", "quartier": "Point E", "adresse": "Rue de Kaolack x Rue C, Point E",
     "pieces": 3, "loyer": 500000, "meuble": True, "disponible": True, "disponible_le": "2026-11-18"},
    {"id": "SK-009", "type": "villa", "quartier": "Fann Résidence", "adresse": "Rue F-14, Villa 3, Fann Résidence",
     "pieces": 6, "loyer": 1500000, "meuble": False, "disponible": True, "disponible_le": "2027-01-01"},

    # --- Almadies, Ngor, Ouakam (bord de mer, plus cher) ---
    {"id": "SK-010", "type": "villa", "quartier": "Almadies", "adresse": "Route des Almadies, Villa Les Filaos",
     "pieces": 5, "loyer": 2000000, "meuble": True, "disponible": True, "disponible_le": "2026-12-01"},
    {"id": "SK-011", "type": "appartement", "quartier": "Almadies", "adresse": "Zone 12, Résidence Océane, apt 4",
     "pieces": 3, "loyer": 800000, "meuble": True, "disponible": True, "disponible_le": "2026-11-20"},
    {"id": "SK-012", "type": "studio", "quartier": "Ngor", "adresse": "Ngor Village, Rue NG-5, studio 2",
     "pieces": 1, "loyer": 200000, "meuble": True, "disponible": True, "disponible_le": "2026-11-17"},
    {"id": "SK-013", "type": "villa", "quartier": "Ngor", "adresse": "Ngor Virage, Villa 22",
     "pieces": 4, "loyer": 1200000, "meuble": False, "disponible": False, "disponible_le": None},
    {"id": "SK-014", "type": "appartement", "quartier": "Ouakam", "adresse": "Cité Avion, Immeuble 7, 3e étage, Ouakam",
     "pieces": 2, "loyer": 220000, "meuble": False, "disponible": True, "disponible_le": "2026-11-22"},
    {"id": "SK-015", "type": "appartement", "quartier": "Ouakam", "adresse": "Route de la Mosquée de la Divinité, Villa 9, Ouakam",
     "pieces": 3, "loyer": 330000, "meuble": False, "disponible": True, "disponible_le": "2026-12-05"},

    # --- Yoff ---
    {"id": "SK-016", "type": "appartement", "quartier": "Yoff", "adresse": "Yoff Tonghor, Rue YF-40, Villa 6",
     "pieces": 3, "loyer": 280000, "meuble": False, "disponible": True, "disponible_le": "2026-11-30"},
    {"id": "SK-017", "type": "chambre", "quartier": "Yoff", "adresse": "Cité Biagui, Villa 101, chambre 2, Yoff",
     "pieces": 1, "loyer": 75000, "meuble": True, "disponible": True, "disponible_le": "2026-11-15"},

    # --- Plateau et Médina (centre-ville) ---
    {"id": "SK-018", "type": "appartement", "quartier": "Plateau", "adresse": "Avenue Pompidou, Immeuble Le Soleil, 5e étage, Plateau",
     "pieces": 2, "loyer": 400000, "meuble": True, "disponible": True, "disponible_le": "2026-11-19"},
    {"id": "SK-019", "type": "appartement", "quartier": "Plateau", "adresse": "Rue Carnot, Immeuble 14, 2e étage, Plateau",
     "pieces": 4, "loyer": 650000, "meuble": False, "disponible": False, "disponible_le": None},
    {"id": "SK-020", "type": "studio", "quartier": "Médina", "adresse": "Rue 22 x Rue 17, Médina",
     "pieces": 1, "loyer": 100000, "meuble": False, "disponible": True, "disponible_le": "2026-11-21"},

    # --- Liberté, Sicap, HLM ---
    {"id": "SK-021", "type": "appartement", "quartier": "Liberté 6", "adresse": "Liberté 6 Extension, Villa 6120",
     "pieces": 3, "loyer": 260000, "meuble": False, "disponible": True, "disponible_le": "2026-11-28"},
    {"id": "SK-022", "type": "appartement", "quartier": "Sicap Baobab", "adresse": "Sicap Baobab, Villa 512",
     "pieces": 2, "loyer": 180000, "meuble": False, "disponible": True, "disponible_le": "2026-12-01"},
    {"id": "SK-023", "type": "chambre", "quartier": "HLM", "adresse": "HLM 5, Villa 1830, chambre 1",
     "pieces": 1, "loyer": 50000, "meuble": False, "disponible": True, "disponible_le": "2026-11-15"},

    # --- Grand Yoff, Parcelles Assainies (prix plus doux) ---
    {"id": "SK-024", "type": "appartement", "quartier": "Grand Yoff", "adresse": "Grand Yoff, Cité Millionnaire, Villa 77",
     "pieces": 3, "loyer": 200000, "meuble": False, "disponible": True, "disponible_le": "2026-11-24"},
    {"id": "SK-025", "type": "appartement", "quartier": "Parcelles Assainies", "adresse": "Unité 15, Villa 230, Parcelles Assainies",
     "pieces": 3, "loyer": 170000, "meuble": False, "disponible": True, "disponible_le": "2026-11-20"},
    {"id": "SK-026", "type": "appartement", "quartier": "Parcelles Assainies", "adresse": "Unité 22, Villa 48, Parcelles Assainies",
     "pieces": 4, "loyer": 230000, "meuble": False, "disponible": False, "disponible_le": None},
    {"id": "SK-027", "type": "studio", "quartier": "Parcelles Assainies", "adresse": "Unité 9, Villa 115, studio, Parcelles Assainies",
     "pieces": 1, "loyer": 80000, "meuble": False, "disponible": True, "disponible_le": "2026-11-16"},

    # --- Ouest Foire et Mamelles ---
    {"id": "SK-028", "type": "villa", "quartier": "Ouest Foire", "adresse": "Cité Fadia, Villa 30, Ouest Foire",
     "pieces": 5, "loyer": 900000, "meuble": False, "disponible": True, "disponible_le": "2026-12-10"},
    {"id": "SK-029", "type": "appartement", "quartier": "Mamelles", "adresse": "Route des Mamelles, Résidence Phare, apt 2",
     "pieces": 3, "loyer": 550000, "meuble": True, "disponible": True, "disponible_le": "2026-11-26"},
    {"id": "SK-030", "type": "appartement", "quartier": "Mamelles", "adresse": "Mamelles Aviation, Villa 18",
     "pieces": 2, "loyer": 300000, "meuble": False, "disponible": True, "disponible_le": "2026-12-03"},
]


# Petit contrôle : lance « python serveur_mcp/biens.py » pour vérifier la liste.
# (Ce bloc ne s'exécute que si on lance CE fichier directement, pas quand un autre fichier l'importe.)
if __name__ == "__main__":
    ids = [b["id"] for b in BIENS]
    assert len(BIENS) == 30, f"Il faut 30 biens, il y en a {len(BIENS)}"
    assert len(set(ids)) == 30, "Deux biens ont le même id"
    dispo = [b for b in BIENS if b["disponible"]]
    print(f"{len(BIENS)} biens, dont {len(dispo)} disponibles et {len(BIENS) - len(dispo)} déjà loués.")
    print("Quartiers :", ", ".join(sorted({b['quartier'] for b in BIENS})))
