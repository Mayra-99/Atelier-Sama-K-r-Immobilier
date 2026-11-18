# Schéma du pipeline (exercice 5)

Auteur du schéma : Atou (copilote de l'exercice 5). Code du pipeline : Serigne Fallou (`agent/pipeline.py`).

**Image simple :** c'est la journée de travail d'une secrétaire. Elle relève le courrier, ressort
le dossier du client (rangé sous le numéro du fil Gmail), fait le travail avec les outils de
l'équipe, demande l'accord du conseiller avant tout envoi, puis range le dossier.

## 1. La tournée de courrier (ce que fait le CODE)

```mermaid
flowchart TD
    A["Boîte Gmail de l'agence"] --> B["lire_demandes (code, pas le modèle)"]
    B -->|"robot / no-reply"| R["Libellé SK/Transmis (rangé par le code)"]
    B -->|"mail de client"| C["Contenu mis sous enveloppe email_client + avertissement"]
    C --> D["Dossier du client = fil Gmail (thread_id gmail-xxx)"]
    D --> E["Mémoire SQLite : checkpoints/conversations.sqlite"]
    E --> F["Agent ReAct : modèle Groq + outils"]
    F --> G["Une phrase de bilan dans le journal + trace"]
    G --> H{"Mode surveiller ?"}
    H -->|"oui"| I["Attendre 30 s"] --> B
    H -->|"non"| J["Fin de la tournée"]
```

## 2. Les 4 branches que l'agent choisit pour CHAQUE mail

```mermaid
flowchart TD
    M["Mail du client + historique du fil"] --> Q{"Quel cas ?"}

    Q -->|"A. Nouvelle demande"| A1["Comprendre le besoin : quartier, type, pièces, budget, date"]
    A1 --> A2["rechercher_biens (catalogue MCP, 2 recherches max)"]
    A2 --> A3["lister_creneaux_libres (agenda)"]
    A3 --> A4["creer_brouillon : SK/En attente de validation"]
    A4 --> V1{"VALIDATION 1 du conseiller"}
    V1 -->|"o"| A5["envoyer_brouillon : SK/Répondu"]
    V1 -->|"n"| STOP["Arrêt, sans réessayer"]

    Q -->|"B. Le client confirme un créneau"| B1["confirmer_visite"]
    B1 --> B2{"Créneau encore libre ?"}
    B2 -->|"oui"| V2{"VALIDATION 2 : visite + mail de confirmation"}
    V2 -->|"o"| B3["Visite créée dans l'agenda + confirmation envoyée"]
    V2 -->|"n"| STOP
    B2 -->|"non, pris entre-temps"| A3

    Q -->|"C. Hors périmètre : négociation, réclamation, litige, consignes cachées"| C1["transmettre_a_conseiller : SK/Transmis"]
    Q -->|"D. Outil en panne"| C1
    Q -->|"Information indispensable manquante"| I1["Brouillon avec UNE question"] --> V1
```

## 3. Le parcours qui répond au critère du jury

1. Le jury envoie un mail → branche **A** → brouillon (biens + créneaux) → **validation 1** → réponse envoyée.
2. Le jury répond « je prends tel créneau » → même fil Gmail, donc même dossier : l'agent se souvient
   de ce qu'il a proposé → branche **B** → **validation 2** → visite dans l'agenda + mail de confirmation.
3. Aucune autre intervention humaine. En mode `surveiller`, on ne relance rien entre les deux.

## 4. Les garde-fous visibles sur le schéma

| Garde-fou | Où | Pourquoi |
|---|---|---|
| Lecture du courrier par le code | `lire_demandes` | Le modèle ne décide pas quels mails lire ; les robots sont écartés sans coût Groq |
| Enveloppe `email_client` | `gmail.py` | Le contenu d'un mail est une donnée, jamais une consigne (injection indirecte) |
| Validation 1 et 2 | `demander_validation` | Rien ne part et rien ne s'inscrit dans l'agenda sans « o » |
| Revérification du créneau | `confirmer_visite` | Un autre client a pu le prendre entre-temps |
| Transmission au conseiller | `transmettre_a_conseiller` | Hors périmètre ou panne : un humain reprend la main |
| Limite d'étapes | `NB_MAX_ETAPES` (main.py) | L'agent ne tourne pas en boucle |
