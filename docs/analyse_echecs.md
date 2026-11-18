# Analyse de trois échecs (exercice 6)

Auteur : Serigne Fallou (tâche e6c). Fiche préparée par `evaluation/analyser_echecs.py`, puis complétée à la main après lecture des traces.

Passage « avant » du 2026-11-18 21:39, modèle openai/gpt-oss-120b : **13/15 réussis (87 %)**, 2,6 appels d'outils, 14 446 tokens et 47,1 s par email en moyenne.

Méthode : pour chaque cas, on lit la trace complète (`traces/exemples/`), on cherche à quelle étape l'agent s'est trompé, et on classe la cause : **prompt** (consigne absente ou floue), **outil** (mauvais résultat), **modèle** (il a mal lu un résultat correct), **données** (catalogue, agenda) ou **correcteur** (l'agent avait raison, le test est trop strict).

Le passage « avant » n'a que 2 échecs (mails 5 et 15). Le 3e cas est un mail **réussi mais trop coûteux** (mail 1) : un agent juste mais lent et cher est aussi un problème en production.

| Cas | Mail | Résultat | Famille de cause | Trace |
|---|---|---|---|---|
| 1 | 5 · Villa à Saly | transmis au lieu de répondre | **prompt** | `traces/exemples/mail_05_bien_inexistant.md` |
| 2 | 15 · Liberté 6 (wolof) | transmis au lieu de répondre | **outil** (panne passagère) | `traces/exemples/mail_15_francais_et_wolof.md` |
| 3 | 1 · F3 Mermoz | réussi, mais 102 s et 20 692 tokens | coût / lenteur | `traces/exemples/mail_01_simple.md` |

## Échec 1 · mail 5 (bien inexistant)

**Objet :** Villa à Saly

**Le mail :** Bonjour, avez-vous une villa avec piscine à Saly pour 200 000 F ? Ibrahima

**Ce qu'on attendait :** `{"decision": "brouillon", "ids_attendus": [], "ids_interdits": [], "creneaux": false}`
(L'agence ne loue qu'à Dakar : réponse polie, aucun bien inventé.)

**Ce que l'agent a fait :** décision = transmis · outils = transmettre_a_conseiller · 7 363 tokens · 35,8 s

**Fautes relevées par le correcteur :** devait répondre par un brouillon (a transmis)

**Raison de la transmission :**

> Demande de location hors de Dakar

**Cause réelle (après lecture de la trace) :** famille **prompt**. Deux consignes se contredisaient. La règle 3 de `PROMPT_SYSTEME` dit « Dakar seulement : répondre poliment ». Mais la branche C de `CONSIGNES_PIPELINE` parle de « hors périmètre », et le modèle a compris « hors de Dakar » = « hors périmètre » = transmettre. Il n'a même pas cherché dans le catalogue.

**Est-ce un vrai échec de l'agent, ou une erreur du correcteur ?** Vrai échec, mais sans danger : rien n'est parti et un conseiller aurait repris la demande. Il fait perdre du temps au conseiller pour une réponse simple que l'agent sait faire.

**Correction faite :** Atou a ajouté 4 lignes à la branche C de `CONSIGNES_PIPELINE` (`agent/pipeline.py`) : une demande hors de Dakar n'est PAS hors périmètre. On répond poliment par un brouillon, sans bien et sans créneau, et cela passe par la validation du conseiller comme d'habitude.

## Échec 2 · mail 15 (français et wolof)

**Objet :** Kër ci Liberté 6

**Le mail :** Salam, damay wut appartement bu am 3 néeg ci Liberté 6, budget 300 000 F. Jërëjëf. Aminata

**Ce qu'on attendait :** `{"decision": "brouillon", "ids_attendus": ["SK-021"], "ids_interdits": [], "creneaux": true}`
(Français et wolof mêlés (« je cherche un appartement de 3 pièces à Liberté 6 ») : réponse en français avec SK-021 (260 000 F).)

**Ce que l'agent a fait :** décision = transmis · outils = rechercher_biens → lister_creneaux_libres → transmettre_a_conseiller · 15 698 tokens · 72,8 s

**Fautes relevées par le correcteur :** devait répondre par un brouillon (a transmis)

**Raison de la transmission :**

> Impossible de récupérer les créneaux de visite (agenda inaccessible).

**Cause réelle (après lecture de la trace) :** famille **outil**. Le wolof n'est PAS le problème : l'agent a bien compris la demande et `rechercher_biens` a trouvé le bon bien. C'est `lister_creneaux_libres` qui a répondu « Agenda inaccessible » sur l'agenda de Khady Ba, la conseillère de Liberté 6. On a relancé le même mail seul : il a réussi. C'était donc une panne passagère de l'API Google Calendar.

**Est-ce un vrai échec de l'agent, ou une erreur du correcteur ?** Ni l'un ni l'autre. L'agent a fait exactement ce que dit la branche D (outil en panne → transmettre à un conseiller) : il n'a pas inventé de créneau. Le correcteur ne pouvait pas savoir que l'agenda était en panne à ce moment-là. C'est même une **sortie de route qui a bien marché**.

**Correction proposée (non faite, à dire au jury) :** laisser l'agent tel quel, car transmettre est le bon réflexe. Amélioration possible : dans `lister_creneaux_libres`, réessayer une fois après 2 secondes avant de déclarer l'agenda inaccessible, comme `main.py` le fait déjà pour l'erreur 429 de Groq.

## Cas 3 · mail 1 (réussi, mais le plus lent et le plus cher)

**Objet :** Recherche F3 Mermoz

**Le mail :** Bonjour, je cherche un F3 à Mermoz à moins de 400 000 F par mois, à partir de décembre. Merci. Fatou Ndiaye

**Ce que l'agent a fait :** décision = brouillon (bonne réponse, SK-001) · outils = rechercher_biens → lister_creneaux_libres → creer_brouillon → envoyer_brouillon · **20 692 tokens · 102,4 s** (moyenne : 14 446 tokens, 47,1 s)

**Cause réelle (après lecture de la trace) :** ce n'est pas une erreur de raisonnement, c'est le prix du parcours complet. À chaque étape, le modèle relit TOUT : le prompt système (règles, consignes visites, consignes emails, consignes pipeline), le mail et les réponses des outils déjà appelés. 4 appels d'outils, donc environ 5 lectures complètes, soit environ 20 000 tokens. Groq gratuit accepte environ 8 000 tokens par minute : avec 20 000 tokens, l'agent dépasse ce quota et doit probablement attendre (erreur 429 puis nouvelle tentative). C'est l'explication la plus probable des 102 s ; à vérifier dans la trace (`mail_01_simple.md`), en regardant le temps entre deux étapes.

**Est-ce un vrai échec ?** Non pour le correcteur, oui pour la production : un vrai client accepterait d'attendre 2 minutes, mais 50 mails par jour dépasseraient vite le quota gratuit.

**Correction proposée (non faite, à dire au jury) :** raccourcir le prompt système (des consignes se répètent entre les 4 blocs), ou passer à une offre Groq payante avec un quota plus élevé.

## Échec corrigé et résultat

Échec choisi : **mail 5** (le seul qui venait de notre propre consigne) · Correction faite dans : `agent/pipeline.py`, branche C de `CONSIGNES_PIPELINE` (par Atou) · Commit : `b0f8394`

Passage « après » : **15/15** (avant : 13/15). Tableau avant / après : `python evaluation/evaluer_pipeline.py --comparer`, et section Exercice 6 du README.

**Ce qu'on retient :** sur 3 cas, un seul vient d'une erreur de notre prompt. Le deuxième est une panne extérieure bien gérée par le garde-fou « transmettre ». Le troisième montre la limite du quota gratuit de Groq. Lire la trace étape par étape a été indispensable : sans elle, on aurait cru que le mail 15 ratait à cause du wolof.
