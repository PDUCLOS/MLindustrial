# Analyse vibratoire & maintenance prédictive

**Un modèle qui marche sur banc d'essai et s'effondre en atelier — c'est le vrai problème de la maintenance prédictive. Ce projet mesure cet écart au lieu de le cacher.**

La plupart des démonstrations de détection de défaut de roulement s'entraînent et se testent sur les mêmes conditions de laboratoire. Ce projet fait l'inverse : il entraîne sur des défauts usinés (perçage, électroérosion — reproductibles, mais artificiels) et évalue sur des défauts nés d'un vrai vieillissement mécanique. L'écart mesuré entre les deux, c'est le mur que rencontre tout modèle qui passe du banc à l'atelier.

---

## Pourquoi ce projet est différent

Porté par **Patrice Duclos**, ~20 ans en distribution industrielle B2B, dont le déploiement sur le terrain de solutions IoT de maintenance prédictive avec **IFM, Schaeffler et SKF**. L'angle n'est pas "encore un CNN sur des spectrogrammes" :

- **Features physiques, pas boîte noire** — fréquences caractéristiques de défaut (BPFO/BPFI/BSF/FTF), analyse d'enveloppe, kurtogramme. Une raie à 46 Hz qui correspond au défaut de bague extérieure d'un roulement à 900 tr/min, c'est explicable devant un chef d'atelier. Un score de CNN ne l'est pas.
- **Le coût du capteur compte** — comparaison vibration (accéléromètre) vs courant moteur (déjà présent sur tout variateur, zéro capteur à installer). Si le courant suffit, c'est un argument business, pas juste une note de bas de page.
- **La généralisation est le résultat, pas un détail** — la question n'est pas "quel F1 sur ce dataset" mais "qu'est-ce qui casse quand on change de contexte", avec l'écart chiffré.
- **Rigueur avant tout** — split par roulement (jamais par fenêtre de signal, sous peine de fuite de données), validation croisée stratifiée, baseline seuil obligatoire avant tout modèle plus complexe, et une discipline "0 mock" stricte : toute valeur affichée est sourcée ou marquée comme telle, jamais inventée.

Ce n'est pas un projet vitrine MLOps (Kubernetes, Airflow, feature store) — c'est un projet **expertise métier + méthode**.

---

## Où en est le projet

| Phase | Statut | Ce qui a été fait |
|---|---|---|
| **Socle de données** | ✅ Terminé | Paderborn (32 roulements, 4 conditions, vibration + 2 courants moteur) ingéré, géométrie roulement vérifiée contre la fiche constructeur officielle (pas une valeur générique de catalogue) |
| **Features & baseline** | ✅ Terminé | Indicateurs temporels, baseline seuil, gradient boosting — voir les chiffres ci-dessous |
| **Généralisation artificiel → réel** | 🔄 En cours | L'objectif principal du projet. Kurtogramme (sélection de bande de résonance pour l'analyse d'enveloppe) en cours de fiabilisation avant le run complet |
| **Restitution finale** | ⏳ À venir | Résultats complets, y compris ce qui n'a pas marché — publiés une fois obtenus, pas avant |

Aucun chiffre de généralisation n'est publié tant que le run n'a pas eu lieu. Un résultat qui semble trop beau est vérifié avant d'être montré, pas après.

## Chiffres publiés à ce jour (Phase 2 — intra-condition)

| Approche | F1 macro (validation croisée 5-fold) |
|---|---|
| Baseline seuil (kurtosis) | 0.682 ± 0.158 |
| Gradient boosting (vibration seule) | 0.738 ± 0.208 |
| Vibration / courant / fusion | Intervalles qui se chevauchent — **pas de conclusion tranchée** sur l'argument coût capteur à ce stade |

Les écarts-types sont volontairement affichés à côté des moyennes : avec 32 roulements, un chiffre seul sans intervalle serait trompeur. Détail complet : [`docs/results_phase2.md`](docs/results_phase2.md).

---

## Dans le dashboard

Suivi Streamlit temps réel sur les données ingérées : indicateurs par état de santé, alertes basées sur un seuil entraîné (pas un seuil arbitraire), dérive temporelle des mesures, catalogue équipements, et un jumeau numérique d'usine (simulation physique déterministe, clairement labellisée comme telle — jamais confondue avec une donnée réelle).

```bash
docker compose up -d
open http://localhost:8501
```

---

## Démarrage rapide

Pré-requis : Docker + Docker Compose.

```bash
docker compose up -d                                        # TimescaleDB + MLflow + dashboard
docker compose exec app python scripts/init_db.py            # seed machines/roulements
docker compose exec app python scripts/build_dataset.py      # ingestion Paderborn (32 roulements)
docker compose exec app python scripts/run_baseline.py       # baseline seuil
docker compose exec app python scripts/run_gbm.py            # gradient boosting
```

Dashboard : http://localhost:8501 · MLflow : http://localhost:5001 · Tests : `docker compose exec app pytest tests/ -v`

---

## Aller plus loin

| | |
|---|---|
| **Le brief complet** | [`docs/brief_projet.md`](docs/brief_projet.md) — contexte, objectifs, pièges méthodologiques, roadmap |
| **Fondements physiques** | [`docs/theorie_reference.md`](docs/theorie_reference.md) — normes ISO, fréquences de défaut, kurtogramme |
| **Modèle de données** | [`docs/data_model.md`](docs/data_model.md) |
| **Problèmes connus** | [`docs/known_issues.md`](docs/known_issues.md) — anomalies documentées honnêtement, pas cachées |
| **Backlog & positionnement** | [`docs/feature_backlog.md`](docs/feature_backlog.md), [`docs/differentiation_strategy.md`](docs/differentiation_strategy.md) |
| **Index complet** | [`docs/README.md`](docs/README.md) |

**Datasets** — principal : Paderborn KAt (32 roulements 6203, CC BY-NC 4.0, citation obligatoire, voir [`docs/brief_projet.md`](docs/brief_projet.md)). CWRU utilisé en sanity check uniquement, jamais comme résultat.

**Stack** — Python 3.11+, numpy/scipy/polars, scikit-learn, XGBoost/LightGBM, PyTorch (comparaison CNN 1D), MLflow, Streamlit, TimescaleDB, Docker Compose.

---

**Patrice Duclos** — `patrice.noel.duclos@gmail.com`
