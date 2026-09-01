# Brief du projet — analyse vibratoire & maintenance prédictive

## Contexte et intention

Projet portfolio de Patrice Duclos, Lead Data / Data Analyst basé à Lyon.

Angle différenciant : ~20 ans en distribution industrielle B2B, dont le déploiement de solutions IoT de maintenance prédictive chez des clients industriels avec IFM, Schaeffler et SKF. Ce projet exploite cette expertise métier plutôt que de la masquer derrière un CNN générique. Concrètement :

- privilégier les **features physiques** (fréquences caractéristiques de défaut, analyse d'enveloppe, kurtosis spectral) sur le deep learning bout-en-bout ;
- traiter le **vrai problème industriel** — un modèle qui marche sur banc et s'effondre en atelier — plutôt que le score de classification ;
- raisonner en **coût de capteur et d'installation**, pas seulement en accuracy.

Ce n'est pas une vitrine MLOps (pas besoin d'empiler Kubernetes, Airflow et un feature store) — c'est un projet **expertise domaine + rigueur méthodologique**.

**Discipline "0 mock" (non négociable)** : aucune valeur inventée dans le code de production. Tout chiffre affiché vient d'une lecture réelle (base de données, MLflow, fichier). Seuil, calibration, unité, valeur normale : tout doit être sourcé ou marqué explicitement comme estimé, avec la méthode de dérivation. Données synthétiques autorisées uniquement en fixtures de test. Afficher "non disponible" plutôt qu'inventer une valeur plausible.

**Extension simulation** : un chantier de jumeau numérique (Factory Twin) peut produire des signaux synthétiques — ce n'est pas un mock en soi, à condition que toute donnée simulée affichée porte un label visible distinct ("SIMULÉ") de toute donnée réelle.

## Objectifs

**Objectif principal — généralisation défauts artificiels → défauts réels**

Entraîner sur des roulements à défauts usinés (perçage, électroérosion, gravure), évaluer sur des roulements à défauts naturels issus d'essais de vieillissement accéléré. Mesurer l'écart. C'est exactement le mur rencontré en production.

**Objectif secondaire — vibration seule vs courant moteur seul**

Le courant moteur s'extrait des variateurs existants, sans capteur supplémentaire : si la performance tient, l'argument coût est décisif en distribution industrielle.

**Objectif tertiaire — publication du dataset et trajectoire d'interopérabilité**

Publier le dataset Paderborn en parquet avec fiche descriptive et géométrie des roulements. Au-delà : préparer la transition du mode "datasets publics batch" vers l'ingestion continue depuis des capteurs réels (protocoles industriels, modèle sémantique standardisé).

## Datasets

Principal : **Paderborn (KAt)** — 32 roulements 6203 (6 sains, 12 défauts artificiels, 14 défauts réels), 4 conditions de fonctionnement, vibration 64 kHz + 2 courants moteur, licence CC BY-NC 4.0 (citation obligatoire, voir plus bas).

Secondaires (référence/sanity-check) : XJTU-SY, NASA IMS, FEMTO-ST/PRONOSTIA, MAFAULDA, CWRU. **CWRU sert uniquement de sanity check** — dataset saturé dans la littérature, non conçu pour le ML, jamais utilisé pour un résultat conclusif.

## Pièges méthodologiques — la discipline qui différencie ce projet

1. **Split par roulement, jamais par fenêtre de signal.** Segmenter un signal en fenêtres puis mélanger train/test fait fuiter la même bague dans les deux ensembles — résultat : une accuracy trompeuse qui ne veut rien dire.
2. **Attention au proxy "condition de fonctionnement".** Un modèle peut apprendre la charge ou la vitesse plutôt que le défaut — toujours évaluer en cross-condition.
3. **Un dataset saturé dans la littérature sert de sanity check, pas de résultat.**
4. **Baseline obligatoire avant tout modèle.** Un seuil simple, avec sa matrice de confusion. Si un modèle plus complexe ne le bat pas franchement, c'est ce résultat-là qu'il faut publier.
5. **Pas de normalisation calculée avant le split.** Les statistiques de mise à l'échelle se calculent sur l'entraînement uniquement.
6. **Déséquilibre de classes** systématique sur les données de dégradation progressive — métrique principale F1 macro, pas accuracy brute.

## Ce qui fait la valeur de ce projet

Un score élevé sur un dataset archi-connu n'intéresse plus personne. Ce qui intéresse un industriel ou un recruteur :

- l'écart mesuré entre défauts artificiels et défauts réels, chiffré et expliqué ;
- une chaîne de features interprétable devant un chef d'atelier — "la raie à 46 Hz correspond au défaut de bague extérieure de ce roulement à cette vitesse" ;
- la comparaison honnête entre approche physique légère et deep learning coûteux ;
- l'argument coût capteur (courant moteur vs accéléromètre) ;
- des résultats négatifs assumés, pas maquillés.

**Règle de conduite du projet :** ne jamais présenter un résultat sans avoir vérifié qu'il ne provient pas d'une fuite de données. Si un score paraît trop beau, chercher la fuite avant de le rapporter.

## Stack technique

Python 3.11+, `uv` pour l'environnement, `numpy`/`scipy.signal`/`polars`/`pandas`, `scikit-learn`, `xgboost`/`lightgbm`, `PyTorch` (branche CNN 1D en comparaison), tracking `mlflow` local, tests `pytest`, configuration en YAML, TimescaleDB, Docker Compose.

## Roadmap

- **Socle de données** — téléchargement Paderborn, loader `.mat` → parquet, splits par roulement et cross-condition, avec tests. ✅ Terminé.
- **Features et baseline** — indicateurs temporels, baseline seuil, gradient boosting sur features physiques. ✅ Terminé.
- **Le vrai test** — entraînement sur défauts artificiels, évaluation sur défauts réels ; évaluation cross-condition ; comparaison vibration seule / courant seul / fusion ; CNN 1D en comparaison. 🔄 En cours — objectif principal du projet.
- **Restitution** — résultats honnêtes y compris ce qui n'a pas marché, figures annotées, publication du dataset, série de retours d'expérience. ⏳ À venir.

## Citations obligatoires

- **Paderborn :** Lessmeier, C.; Kimotho, J. K.; Zimmer, D.; Sextro, W. — KAt-DataCenter, Chair of Design and Drive Technology, Paderborn University.
- **XJTU-SY :** Biao Wang, Yaguo Lei, Naipeng Li, Ningbo Li, « A Hybrid Prognostics Approach for Estimating Remaining Useful Life of Rolling Element Bearings », *IEEE Transactions on Reliability*, vol. 69, no. 1, pp. 401-412, 2020.
- **NASA IMS :** J. Lee, H. Qiu, G. Yu, J. Lin, and Rexnord Technical Services (2007). IMS, University of Cincinnati, « Bearing Data Set », NASA Prognostics Data Repository, NASA Ames Research Center.
