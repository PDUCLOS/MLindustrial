# Maintenance prédictive vibratoire — fiche portfolio vérifiée

Fiche destinée à l'intégration dans le portfolio (slug `maintenance-predictive`).
**Toutes les valeurs ci-dessous ont été mesurées le 27/10/2026** sur un poste Windows 11
(AMD Ryzen 9 3900X, 32 Go, RTX 4070 Ti SUPER 16 Go, Python 3.12.3), branche
`feat/vitrine-maintenance-predictive`. Ce qui n'a pas pu être exécuté est signalé comme tel.

- Dépôt : https://github.com/PDUCLOS/MLindustrial
- Vitrine (après merge et activation de GitHub Pages sur `/docs`) : `docs/index.html`
- Vidéo : `docs/video/maintenance-predictive-promo.mp4` (118 s, 9,1 Mo) + `docs/video/poster.png`

## En une phrase

Diagnostic de défauts de roulements sur les 32 roulements réels du banc Paderborn à partir de
5 indicateurs vibratoires explicables, avec une validation qui ne mélange jamais un roulement
entre entraînement et test, et une mesure chiffrée de l'écart entre défauts de laboratoire et
défauts réels.

## Faits vérifiés

| Fait | Valeur mesurée | Comment |
|---|---|---|
| Jeu de données | 32 roulements, 2 560 fichiers .mat (4 régimes × 20 mesures × 32) | source officielle `groups.uni-paderborn.de/kat/BearingDataCenter` |
| Taille des archives officielles | 5 357 708 539 octets (5,4 Go) | somme des `Content-Length` des 32 `.rar` |
| Taille extraite | 22,4 Go (.mat) ; 6,6 Go de Parquet produits | `du -sb` |
| Fichiers illisibles | 1 (`KA08/N15_M01_F10_KA08_2.mat`, « Expecting matrix here ») | écarté et listé par `build_dataset.py` |
| Ingestion complète | 473 s → 2 559 mesures, 7 677 signaux, 46 062 indicateurs | `scripts/build_dataset.py` |
| Tests | **223 passés, 0 échec, 0 ignoré** (données présentes) ; 222 + 1 ignoré sans données | `pytest` |
| Lint CI | `ruff check src/ scripts/ tests/ app/ api/` : 0 erreur | ruff 0.16.5 (version verrouillée) |
| Manifestes K8s | overlay `local` : 6 objets, `prod` : 8 objets, rendus sans erreur | `kubectl kustomize` |
| Image API (simulée) | API fonctionnelle dans un venv vierge avec seulement `api/requirements.txt` + les fichiers copiés par `Dockerfile.api` ; probabilités identiques au venv complet | voir « Non vérifié » pour le `docker build` |

## Tableau de mesures

### Reproduction des chiffres publiés (Phase 2, F1 macro, StratifiedGroupKFold 5 folds, groupe = roulement)

| Approche | Publié (README / portfolio) | Mesuré | Écart |
|---|---|---|---|
| Baseline seuil kurtosis | 0,682 ± 0,158 | **0,682 ± 0,158** | aucun |
| Baseline facteur de crête | 0,576 ± 0,174 | 0,576 ± 0,174 | aucun |
| Baseline RMS | 0,430 ± 0,090 | 0,430 ± 0,090 | aucun (sens instable selon le fold, comme documenté) |
| XGBoost vibration seule (5 indicateurs) | **0,738 ± 0,208** | **0,734 ± 0,206** | −0,004 |
| XGBoost fusion vibration + courant (15) | 0,726 ± 0,222 | 0,726 ± 0,219 | écart-type −0,003 |
| XGBoost courant seul (10) | 0,542 ± 0,121 | 0,550 ± 0,123 | +0,008 |

Balanced accuracy XGBoost vibration seule : 0,743. F1 par fold : 0,978 / 0,473 / 0,847 / 0,869 / 0,502.
Les baselines, déterministes, sont reproduites au millième. Les écarts XGBoost sont
vraisemblablement dus à la version de bibliothèque (xgboost 3.4.1 ici, version d'origine non
tracée) ; ils sont ~50 fois plus petits que l'écart-type et ne changent aucune conclusion.

### Généralisation artificiel → réel (mesure ajoutée, exploratoire)

`scripts/bench_vitrine.py`, indicateurs temporels vibration seuls, XGBoost identique à la Phase 2.
Train = 12 roulements à défaut artificiel + 3 sains (1 199 mesures) ; test = 14 roulements à
défaut réel + 3 autres sains (1 360 mesures) ; répété sur les 20 partitions 3/3 des 6 sains.
Contrôle : mêmes sains, défauts réels appris en CV groupée (GroupKFold 5).

| Scénario | F1 macro | Balanced acc. | Rappel défauts | Rappel sains |
|---|---|---|---|---|
| Artificiel → réel | **0,620 ± 0,102** | 0,646 ± 0,109 | 0,809 ± 0,098 | 0,484 ± 0,229 |
| Contrôle réel → réel | **0,694 ± 0,107** | 0,690 ± 0,105 | 0,930 ± 0,030 | 0,449 ± 0,218 |

Lecture : entraîné sur des défauts usinés, le modèle manque ~1 défaut réel sur 5, contre ~1 sur 14
s'il a vu des défauts réels. La reconnaissance des sains reste faible dans les deux cas (6 roulements
sains seulement). Note : la fonction existante `split_artificial_to_real()` met tous les sains en
train et ne laisse que des défauts réels en test (une seule classe, F1 macro non interprétable) ;
le banc répartit donc les sains entre train et test.

### Démo API (3 roulements exclus de l'entraînement du modèle servi)

Modèle servi : XGBoost vibration seule réentraîné sur 29 roulements (2 319 mesures) ; K006 (sain),
KI08 (artificiel), KA22 (réel) tenus à l'écart, choisis avant tout résultat.

| Mesure | Vérité | XGBoost | P(défaut) | Baseline kurtosis (≤ 13,3845 ⇒ défaut) |
|---|---|---|---|---|
| K006 N15_M07_F10 | sain | sain ✔ | 0,0094 | sain ✔ |
| K006 N09_M07_F10 | sain | sain ✔ | 0,0083 | sain ✔ |
| KI08 N15_M07_F10 | artificiel | défaut ✔ | 0,9961 | défaut ✔ |
| KI08 N09_M07_F10 | artificiel | défaut ✔ | 0,9778 | sain ✘ |
| KA22 N15_M07_F10 | **réel** | sain ✘ | 0,1198 | défaut ✔ |
| KA22 N09_M07_F10 | **réel** | sain ✘ | 0,0229 | sain ✘ |

### Temps d'inférence et entraînement (CPU, `scripts/bench_vitrine.py`)

| Mesure | Valeur |
|---|---|
| Calcul des 5 indicateurs sur une mesure de 256 001 points | **23,2 ms** (médiane de 50) |
| Prédiction XGBoost unitaire | 0,91 ms (médiane de 200) |
| Prédiction XGBoost en lot (2 559 mesures) | 3,3 ms |
| `POST /predict` bout en bout (TestClient, sans réseau) | 317 ms (médiane de 20), dominé par le JSON de 256 000 flottants |
| Entraînement XGBoost complet (2 559 × 5), CPU | 154 ms |
| Même entraînement sur GPU (CUDA, RTX 4070 Ti SUPER) | 365 ms → GPU non pertinent à cette échelle |
| Taille du modèle exporté | 279 048 octets (JSON XGBoost) |

## Ce qui a été corrigé ou ajouté

Corrections (échecs réels constatés) :

1. **CI lint cassée** : ruff 0.16.5 (verrouillé dans `uv.lock`) active 67 règles supplémentaires par
   défaut → `ruff check` échouait. Jeu de règles épinglé dans `pyproject.toml` (base E4/E7/E9/F + B015/B017).
2. **Deux tests qui ne testaient rien** : `tests/test_splits.py` (`f(...) is None` sans `assert`) et
   `tests/test_aas.py` (`pytest.raises(Exception)` → `FrozenInstanceError`).
3. **Test d'intégration jamais exécuté** : `test_load_paderborn_measurement_integration` faisait un
   `pytest.skip` inconditionnel ; il charge maintenant un vrai .mat quand les données sont présentes.
4. **TimescaleDB obligatoire** : `make_feature_hypertable()` plantait sur un PostgreSQL sans
   l'extension ; il dégrade désormais en table classique avec avertissement.
5. **Dashboard bloqué hors Docker** : `http://mlflow:5000` codé en dur dans `app/dashboard.py` et
   `app/tabs/alertes.py` → onglets Alertes et Résultats vides ; lisent maintenant `MLFLOW_TRACKING_URI`.
6. **Image de service** : `XGBClassifier.load_model` exige scikit-learn ; le service utilise `xgb.Booster`
   (constaté en simulant l'image dans un venv vierge).

Ajouts : `api/` (FastAPI + page de démo), `src/serving/predictor.py`, `scripts/export_model.py`,
`models/` (modèle, model card, 6 mesures réelles de démo en int16 sans perte),
`scripts/bench_vitrine.py` + `reports/bench/bench_results.json`, `tests/test_api.py` (9 tests),
`Dockerfile.api`, `deploy/k8s` (base + overlays local / prod), `docs/architecture.drawio` (4 pages)
+ `scripts/build_architecture_drawio.py`, `docs/index.html`, `scripts/promo_video.py`, vidéo.

## Extraits de code exacts

Garde-fou anti-fuite (`src/data/splits.py`) :

```python
def assert_no_asset_leakage(
    train_df: pd.DataFrame, test_df: pd.DataFrame, asset_col: str = "asset_id"
) -> None:
    """Garde-fou : leve une erreur si un asset_id apparait dans train ET test."""
    leaked = set(train_df[asset_col]) & set(test_df[asset_col])
    if leaked:
        raise ValueError(f"Fuite de donnees : assets presents dans train ET test : {leaked}")
```

Généralisation artificiel → réel (`scripts/bench_vitrine.py`) :

```python
    for train_h in itertools.combinations(healthy, 3):
        h_train = df[df["code"].isin(train_h)]
        h_test = df[(df["origin"] == "na") & ~df["code"].isin(train_h)]

        # (a) artificiel -> reel
        train = pd.concat([art, h_train])
        test = pd.concat([real, h_test])
        assert_no_asset_leakage(train, test, asset_col="asset_id")
        m = train_gbm(train[FEATURE_ORDER].to_numpy(), train["label"].to_numpy())
        transfer.append(scores(test["label"], m.predict(test[FEATURE_ORDER].to_numpy())))
```

Inférence (`src/serving/predictor.py`) — mêmes fonctions d'indicateurs qu'à l'entraînement :

```python
    def features_from_signal(self, signal: np.ndarray) -> dict[str, float]:
        x = np.asarray(signal, dtype=np.float64)
        if x.ndim != 1 or x.size < MIN_SAMPLES:
            raise ValueError(f"signal 1D d'au moins {MIN_SAMPLES} echantillons attendu")
        if not np.all(np.isfinite(x)):
            raise ValueError("signal contenant des valeurs non finies")
        return {f"vibration_{k}": v for k, v in time_domain_features(x).items()}
```

## Limites

- Un seul banc, un seul modèle de roulement (6203), 32 roulements dont 6 sains : écarts-types de
  0,10 à 0,21 sur le F1 macro ; aucune garantie de transfert vers une autre machine.
- Indicateurs temporels seuls : l'analyse d'enveloppe (BPFO / BPFI) reste désactivée tant que la
  sélection de bande (kurtogramme) n'est pas stabilisée (`docs/known_issues.md`).
- Régimes mélangés : la généralisation vers un régime de fonctionnement inconnu n'est pas mesurée.
- Le banc artificiel → réel est exploratoire ; `docs/results_phase3.md` n'a pas été rempli (il attend
  la décision P3-A sur le kurtogramme, qui n'a pas été prise dans cette session).
- Données sous licence CC BY-NC 4.0 (usage non commercial, citation de Lessmeier et al., 2016).

## Non vérifié dans cette session

- **`docker build` / `docker run`** de `Dockerfile.api` et du `Dockerfile` racine, et
  **`docker compose up`** : Docker Desktop n'était pas démarré (et sa VM est partagée avec d'autres
  projets). L'image API a été simulée par un venv vierge (voir ci-dessus), pas construite.
- **TimescaleDB** : le pipeline a tourné sur PostgreSQL 16.2 natif (`pgserver`), sans l'extension ;
  l'hypertable n'a donc pas été testée.
- **Déploiement Kubernetes réel** : seuls les rendus `kubectl kustomize` sont validés.
- **Mémoire de l'API** : non mesurée en conteneur ; les `requests/limits` des manifestes sont des estimations.
- **Rapport Evidently** (`scripts/run_drift_report.py`) : non relancé.
- **Onglet Spectre** du dashboard : ne s'est pas affiché dans le délai de capture (non investigué).
- **CI GitHub Actions** : non déclenchée (pas de PR créée) ; vérifiée localement uniquement.

## Écarts avec la fiche portfolio actuelle (`projects.py`)

| Fiche actuelle | Constat | Proposition |
|---|---|---|
| « 189 tests » | 214 tests à l'origine du clonage, **223** après ajouts | « 223 tests » |
| « 0,738 F1 macro XGBoost » | 0,734 ± 0,206 reproduit (0,738 publié) | « 0,73 F1 macro » ou « 0,734 ± 0,206 » |
| « 5,4 Go signaux bruts » | 5,4 Go d'archives (22,4 Go extraits) | conserver, préciser « archives » |
| « 5 folds » | confirmé | conserver |
| CI « pipeline ML complet sur données réelles » | sous-ensemble de 2 roulements (K001, KA01) en CI | préciser « smoke test 2 roulements » |
| — | nouveau : écart artificiel → réel mesuré | KPI « 0,62 F1 artificiel → réel » |

## Médias produits

| Fichier | Contenu |
|---|---|
| `docs/index.html` | vitrine GitHub Pages (vidéo, démo, évaluation, architecture, démarche, K8s, limites, glossaire) |
| `docs/video/maintenance-predictive-promo.mp4` | vidéo narrée 1080p, 118 s, 9,1 Mo (`scripts/promo_video.py`) |
| `docs/video/poster.png` | affiche de la vidéo |
| `docs/architecture.drawio` | 4 pages : pipeline, protocole d'évaluation, service + Kubernetes, du signal aux indicateurs |
| `docs/img/architecture-{1..4}.png` | exports PNG draw.io (échelle 1,5) |
| `docs/img/demo-api.png`, `demo-api-artificiel.png`, `demo-api-reel-manque.png` | captures réelles de la page de démo de l'API |
| `docs/img/demo-swagger.png` | documentation OpenAPI |
| `docs/img/dashboard-{indicateurs,alertes,resultats,jumeau}.png` | captures réelles du dashboard Streamlit sur les 32 roulements |
| `reports/bench/bench_results.json` | résultats bruts du banc |

## Reproduire

```bash
uv sync --all-extras
bash scripts/download_paderborn.sh               # ou curl + 7-Zip sous Windows
export DATABASE_URL=postgresql+psycopg2://...     # PostgreSQL ou TimescaleDB
uv run python scripts/init_db.py
uv run python scripts/build_dataset.py
MLFLOW_TRACKING_URI=sqlite:///mlruns/mlflow.db uv run python scripts/run_baseline.py
MLFLOW_TRACKING_URI=sqlite:///mlruns/mlflow.db uv run python scripts/run_gbm.py
uv run python scripts/export_model.py
uv run python scripts/bench_vitrine.py
uv run uvicorn api.main:app --port 8765
```
