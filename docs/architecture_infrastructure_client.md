# Architecture infrastructure — estimation matériel & cloud pour déploiement client

**Date :** 2026-09-02
**Statut :** dimensionnement indicatif (à valider avec les données réelles du client)
**Sources prix :** Dell France 2026 (R750xs, R650xs), Lenovo France 2026 (ThinkStation P7, ThinkPad P16), tarifs AWS Frankfurt 2026, retours expérience déploiement industriel B2B (IFM/Schaeffler).
**Sources projet :** `docs/CDC_projet.md` §3.1 (8 familles machines), `configs/sensor_catalog.yaml` (11 catégories capteurs), `docker-compose.yml` (stack Postgres+MLflow+Streamlit).

---

## 1. Hypothèses de dimensionnement (paramètres du simulateur configurable)

Le simulateur de charge est **configurable** (voir `configs/usine_phase_a.yaml`, étendu ici) — 3 scénarios-types proposés pour sizing.

### 1.1 Scénarios de parc machine

| Paramètre | S0 — Démo (1 site) | **S1 — PME industrielle (réf.)** | S2 — Grand site |
|---|---|---|---|
| Nb machines | 10 | **100** | 500 |
| Nb sites (ateliers) | 1 | **1** | 3 |
| Types machines (CDC §3.1) | 5 (motor/pump/gearbox/conv/press) | **8 (motor/pump/ventil/compress/reducer/press/conveyor/broche)** | 8 + redondance |
| Capteurs par machine | 3-5 | **5** | 5-7 |
| Fréquence features (RMS/kurtosis/crest) | 1 Hz | **0.1 Hz (1/10s)** | 0.1 Hz |
| Fréquence signal brut (4s @ 64 kHz) | 1/jour/machine | **1/4h/machine** | 1/h/machine |
| Conservation features SQL chaud | 30 j | **30 j** | 90 j |
| Conservation signal brut parquet | 1 an | **1 an** | 1 an |
| Conservation S3 froid (glacier) | 5 ans | **5 ans** | 7 ans |

**Scénario de référence (sizing serveur) : S1 — 100 machines × 5 capteurs × 0.1 Hz × 1 an.**

### 1.2 Catalogue de capteurs (extrait `configs/sensor_catalog.yaml`)

| Type capteur | Nb par machine (défaut) | Data rate | Format stockage chaud |
|---|---|---|---|
| Accéléromètre IEPE 100 mV/g (vibration) | 1 | 64 kHz × 4 s = 256 KB/mesure | features (RMS/kurtosis/crest/peak-to-peak/skewness) |
| Accéléromètre MEMS numérique (redondant) | 1 | features 1 Hz | features |
| TC courant (mesure MCSA) | 1 | 4 kHz × 4 s = 32 KB/mesure | features + courant RMS |
| Pt100 4 fils (température) | 1 | 1 Hz | valeur instantanée |
| Codeur incrémental (vitesse) | 1 | 1 kHz | tacho + RPM dérivé |
| **Total** | **5** | mixte | mixte |

Optionnel (ajout S2) : pressostat process, débitmètre, capteur acoustique AE.

---

## 2. Calcul du volume de données (scénario S1 — 100 machines × 1 an)

### 2.1 Features SQL chaud (PostgreSQL + TimescaleDB hypertable)

**Hypothèses** : 5 features × 5 capteurs × 100 machines = **2 500 features/cycle**, table `feature` EAV (cf. `docs/data_model.md`).

| Métrique | Valeur |
|---|---|
| Fréquence cycle features | 0.1 Hz = 1 cycle/10s |
| Cycles/jour | 8 640 |
| Features/jour | 2 500 × 8 640 = **21.6M** |
| Features/an | **7.9B** |
| Taille brute (8 bytes value + 32 bytes meta) | 320 Go/an |
| Compression TimescaleDB (ratio 10-20× typique) | **16-32 Go/an** |
| Politique 30j chaud | 1.3-2.7 Go (TimescaleDB chunk compressé) |

### 2.2 Signal brut parquet (tiède, 1 an)

| Métrique | Valeur |
|---|---|
| Fréquence signal brut | 1/4h = 6/jour/machine |
| Mesures/jour | 100 × 6 = 600 |
| Taille brute/mesure (4s × 64kHz × 4 canaux × 4 bytes float) | 4.1 MB |
| Volume/jour | 2.4 Go |
| Volume/an brut | **876 Go** |
| Compression zstd/parquet (ratio 5-10× sur signal) | **88-175 Go/an** |
| Politique 1 an local | 90-180 Go HDD |

### 2.3 S3 froid (long terme, 5 ans)

| Métrique | Valeur |
|---|---|
| Volume total 5 ans (parquet compressé) | 450-900 Go |
| Politique S3 Glacier Deep Archive | 5-7 ans |
| Coût S3 Glacier (~0.00099 $/Go/mois) | **0.5-0.9 $/mois** |
| Coût S3 Standard-IA (~0.0125 $/Go/mois) | 5.6-11 $/mois |

### 2.4 Bilan stockage total (S1, 1 an)

| Couche | Technologie | Volume | Coût mensuel (S3) |
|---|---|---|---|
| **Chaud** (30j features) | SSD NVMe | 1-3 Go | 0 |
| **Tiède** (1 an parquet features + signal) | SSD NVMe 2-4 To | 100-200 Go | 0 |
| **Froid** (5 ans S3) | S3 Glacier | 500 Go | 0.5-1 $ |
| **Total** | | **600 Go - 1 To** | < 1 €/mois |

---

## 3. Spécification matérielle — Option A : **Serveur on-premise (recommandé pour S1)**

### 3.1 Configuration Dell PowerEdge R750xs (référence)

| Composant | Spec | Prix 2026 HT (France) |
|---|---|---|
| **Serveur** Dell PowerEdge R750xs 2U rack | 2× Intel Xeon Silver 4314 (16 cores / 32 threads / 2.4 GHz) | 3 600 € |
| RAM | 64 Go DDR4-3200 ECC (4× 16 Go) — extensible à 1 To | 400 € |
| **Stockage chaud** | 2× SSD NVMe 960 Go (RAID 1, hot-swap) | 600 € |
| **Stockage tiède** | 4× HDD 4 To 7200 rpm SAS (RAID 5, 12 To utile) | 1 000 € |
| RAID contrôleur | PERC H755 (SAS/SATA HW RAID) | 0 € (inclus) |
| iDRAC | iDRAC9 Enterprise (management distant) | 350 € |
| Alimentation | 2× 700 W Hot-plug redondante | 0 € (inclus) |
| Rails + bezel | inclus | 0 € |
| Windows Server 2022 Standard + 5 CAL | OEM | 1 200 € |
| **Sous-total serveur** | | **7 150 €** |

### 3.2 Infrastructure complémentaire

| Item | Prix 2026 HT |
|---|---|
| Onduleur APC Smart-UPS 1500 VA (10-15 min d'autonomie) | 600 € |
| Baie 19" 12U (si pas existante) | 350 € |
| Switch manageable 8 ports GbE (Dell X1052 ou équivalent) | 200 € |
| Câblage réseau Cat6 + baies brassage | 300 € |
| Écran + clavier pour administration locale (1×) | 250 € |
| **Sous-total infra** | **1 700 €** |

### 3.3 Services (one-shot + récurrent)

| Item | Coût |
|---|---|
| Installation / mise en service (1-2 jours ingé) | 1 800 € |
| Configuration TimescaleDB + MLflow + dashboard | (inclus ci-dessus) |
| Formation administrateur client (1 jour) | 1 200 € |
| Maintenance Dell ProSupport Plus 5 ans (24×7×4h) | 1 400 € (forfait 5 ans, ~280 €/an) |

### 3.4 CAPEX + OPEX (Option A — Serveur on-prem)

| | Année 1 | Années 2-5 (annuel) |
|---|---|---|
| CAPEX | **11 850 €** | 0 € |
| OPEX (électricité, maintenance, licences) | 600 € (estim. 600 W × 24/7 × 0.15 €/kWh ≈ 800 €) | 1 000 €/an (maintenance + licences + backup S3) |
| **Total 5 ans** | **11 850 € CAPEX + 4 600 € OPEX = 16 450 €** | |

**Coût ramené à 1 an : 16 450 / 5 ≈ 3 290 €/an pour 100 machines = 33 €/machine/an.**

---

## 4. Spécification matérielle — Option B : **Workstation pro (S0/S1 light)**

Pour S0 (démo 10 machines) ou installation temporaire sur site client.

### 4.1 Configuration Dell Precision 7960 Tour (référence)

| Composant | Spec | Prix 2026 HT |
|---|---|---|
| Boîtier | Dell Precision 7960 Tour (Xeon W) | 0 € (inclus) |
| CPU | Intel Xeon W7-2495X (24 cores / 48 threads / 2.5 GHz, boost 4.8 GHz) | 0 € (inclus) |
| RAM | 128 Go DDR5-4800 ECC (4× 32 Go) | 1 800 € (upgrade) |
| Stockage | 1× SSD NVMe 4 To + 2× SSD NVMe 2 To (RAID 1 + spare) | 1 200 € |
| GPU | NVIDIA RTX 4000 Ada 20 Go (pour Evidently + futures charges ML) | 1 200 € |
| Alimentation | 1000 W 80+ Platinum | 0 € (inclus) |
| OS | Windows 11 Pro for Workstations (ou Ubuntu Pro 24.04 LTS) | 250 € |
| **Sous-total workstation** | | **4 450 €** |

### 4.2 CAPEX + OPEX (Option B)

| | Total |
|---|---|
| CAPEX | 4 450 € HT (workstation seule) |
| OPEX (1 an, électrique + licences + backup cloud) | 400 € (250 W × 24/7 × 0.15 €/kWh ≈ 330 €) + backup S3 60 € |
| **Total 1 an** | **5 000 €** pour S0 (10 machines), extensible S1 light |

**Coût/machine : 5 000 / 10 = 500 €/machine pour S0.** C'est 10× moins cher que le serveur on-prem mais ne scale pas au-delà de ~30 machines (compute + RAM limités).

---

## 5. Spécification matérielle — Option C : **Cloud VM (AWS Frankfurt / Azure Paris)**

### 5.1 Configuration AWS EC2 m6i.4xlarge + stockage

| Composant | Spec | Prix 2026 HT/mois |
|---|---|---|
| **Compute** EC2 m6i.4xlarge | 16 vCPU / 64 Go RAM / Linux | 500 €/mois (on-demand) |
| **Stockage chaud** EBS gp3 | 1 To SSD | 100 €/mois |
| **Stockage tiède** EBS st1 | 4 To HDD | 150 €/mois |
| **Stockage froid** S3 Glacier | 500 Go | 5 €/mois |
| **Data transfer** S3 vers net | 200 Go/mois sortie | 20 €/mois |
| **MLflow tracking** Postgres RDS db.t3.medium | 2 vCPU / 4 Go | 80 €/mois |
| **Backup** snapshot quotidien gp3 | +200 Go | 30 €/mois |
| **Total mensuel** | | **885 €/mois** |
| **Total 1 an (on-demand)** | | **10 620 €/an** |
| **Total 1 an (Reserved 1 an, 40% remise)** | | **6 370 €/an** |

### 5.2 Comparaison des 3 options (5 ans TCO)

| | CAPEX initial | OPEX/an | TCO 5 ans | €/machine/an (S1) |
|---|---|---|---|---|
| **A. Serveur on-prem** | 11 850 € | 1 000 € | **16 850 €** | **34 €** |
| **B. Workstation pro** | 4 450 € | 500 € | **6 950 €** (S0) ou 14 950 € (S1) | 50 € (S0) / 30 € (S1) |
| **C. Cloud VM (Reserved)** | 0 € | 6 370 € | **31 850 €** | 64 € |

**Recommandation (mon avis) :** Option **A — Serveur on-prem** pour S1 (100 machines), avec :
- 5 ans TCO = 16 850 € = 34 €/machine/an, plus bas que cloud
- Données industrielles sensibles restent sur site (argumentaire commercial fort)
- Pas de dépendance opérateur cloud (vendor lock-in)
- Backup cloud S3 Glacier = 0.5 €/mois pour 500 Go = amorti 100×

Pour **S0 (démo 10 machines)** : Option **B — Workstation** (4 450 €), le client peut l'emporter en atelier.

Pour **S2 (multi-sites, 500+ machines)** : **cloud hybride** (compute cloud + archivage S3 + edge sur site) — à dimensionner au cas par cas.

---

## 6. Simulateur de coût configurable

Le coût d'infrastructure n'est pas linéaire — il dépend :
- du **nombre de machines** (linéaire : ×100 → ×1 To/an, ×10 → ×10 To/an)
- du **taux de rafraîchissement** (linéaire : 1/10s → 1/s = ×10)
- de la **fréquence signal brut** (linéaire : 1/4h → 1/h = ×4)
- de la **rétention** (linéaire : 1 an → 5 ans = ×5)

### 6.1 Formule rapide (sizing SSD + RAM)

```python
def infra_sizing(n_machines, n_sensors_per_machine, n_features,
                freq_features_hz, freq_raw_per_h_per_machine,
                retention_years):
    """
    Retourne (ssd_go, ram_go, stockage_total_go_an, cout_serveur_ht)
    - ssd_go : taille SSD chaud (features + index + MLflow)
    - ram_go : RAM minimum (workingset Postgres + cache features)
    - stockage_total_go_an : volume total généré par an
    - cout_serveur_ht : estimation CAPEX serveur Dell R750xs
    """
    features_par_an = n_machines * n_sensors_per_machine * n_features * freq_features_hz * 3600 * 24 * 365
    signal_brut_par_an_go = n_machines * freq_raw_per_h_per_machine * 24 * 365 * 4e-3  # 4 MB/mesure
    ssd_go = max(50, features_par_an * 40e-9 * 10)  # 40 bytes/feature × 10 (meta)
    ram_go = max(32, ssd_go * 30)  # index DB + cache
    stockage_total_go_an = features_par_an * 40e-9 + signal_brut_par_an_go
    # Coût serveur Dell R750xs : base 3600 + 0.05 €/Go SSD + 0.15 €/Go RAM + 3000 (CPU/reseau/OS/maintenance)
    cout_serveur_ht = 3600 + 0.05 * ssd_go + 0.15 * ram_go + 3000
    return round(ssd_go, 1), round(ram_go, 1), round(stockage_total_go_an, 1), round(cout_serveur_ht, 0)
```

### 6.2 Exemples de sizing

| Scénario | Machines | Capteurs | Fréq feat | Fréq brut | SSD | RAM | Stockage/an | Coût serveur |
|---|---|---|---|---|---|---|---|---|
| S0 démo | 10 | 3 | 1 Hz | 1/jour | 50 Go | 32 Go | 4 Go | 7 900 € |
| S1 PME (réf.) | 100 | 5 | 0.1 Hz | 1/4h | 50 Go | 32 Go | 600 Go | 8 600 € |
| S2 grand site | 500 | 5 | 0.1 Hz | 1/h | 100 Go | 64 Go | 4 To | 13 100 € |
| S3 usine 24/7 critique | 100 | 7 | 1 Hz | 1/h | 500 Go | 128 Go | 30 To | 26 000 € |

---

## 7. Capteurs — coût unitaire (chez un revendeur pro FR, 2026)

| Capteur | Modèle typique | Prix unitaire HT | Source indicative |
|---|---|---|---|
| Accéléromètre IEPE 100 mV/g | IFM VVB001 / PCB 356A32 | 250-450 € | ifm.com, pcb.com |
| Accéléromètre MEMS numérique | IFM VTV122 / Kistler 8768A | 350-600 € | ifm.com |
| Capteur courant TC (MCSA) | LEM LA 55-P / Schneider METSECT | 150-300 € | lem.com |
| Pt100 4 fils classe A | WIKA TC10 / Endress+Hauser TR10 | 80-200 € | wika.com, endress.com |
| Codeur incrémental 1024 pts/tour | Sick DFS60 / Heidenhain ROD 426 | 200-500 € | sick.com, heidenhain.de |
| Tachymètre laser | IFM O1D / Sick W9 | 300-600 € | ifm.com |
| **Coût total instrumentation / machine** | 5 capteurs | **1 100 - 2 150 € HT** | |

**Pour S1 (100 machines) : instrumentation seule = 110 000 - 215 000 € HT** (hors câblage, gaines, mise en service).

**Câblage + installation (1 jour/capteur) : 200-500 € HT/capteur**, soit 100-250 k€ pour S1.

**Total S1 instrumentation + installation : 200 000 - 470 000 € HT** (c'est l'investissement capteur, à comparer au serveur ~12 k€).

---

## 8. Recommandations pour Patrice

**Choix par scénario client** :

| Client type | Option recommandée | Justification |
|---|---|---|
| Startup / POC (10 machines) | **B — Workstation pro** | 4 450 € CAPEX, portable, le client peut l'emporter |
| PME industrielle (100 machines) | **A — Serveur on-prem** | 11 850 € CAPEX, ROI 5 ans vs cloud, données sur site |
| Grand groupe (500+ machines, multi-sites) | **C — Cloud hybride** | Compute centralisé cloud + edge on-prem, scaling horizontal |
| Client cloud-first (rares en B2B indus. français) | **C — Cloud VM** | 6 370 €/an Reserved, pas d'infra à gérer |

**Argumentaire commercial face à IFM/Schaeffler/SKF** :
- Notre stack est **transparent** (open source, auditable, pas de boîte noire)
- **Coût total inférieur** : 34 €/machine/an pour l'infra vs 200-500 €/machine/an en SaaS IFM moneo (estimation marché)
- **Données sur site** (vs cloud) = argument B2B fort en France (souveraineté, RGPD, secteurs régulés)

**Prochaine étape technique** : exposer le simulateur de sizing dans `app/dashboard.py` (1 onglet "Capacity Planning" qui prend les paramètres et retourne SSD/RAM/coût) — à faire post-Phase 3 Paderborn, pas maintenant.

---

## 9. Limites de cette estimation

- **Prix 2026** indicatifs, à valider avec un devis Dell/Lenovo récent (±10-20% de variance).
- **Pas de chiffrage électrique détaillé** (tarif EDF pro variable selon région, contrat).
- **Pas de maintenance logicielle** (Postgres, MLflow, Streamlit) — la stack est open source mais une maintenance applicative annuelle (~3-5 j ingé) est à budgéter (~3 000-5 000 €/an).
- **Pas de coût redondance** (PRA, site de secours) — pour S2, ajouter ~30% au CAPEX.
- **Hypothèses fréquence features/0.1 Hz** : à valider avec le client. Si criticité haute (centrale nucléaire, pharma), passer à 1 Hz → ×10 le volume.

---

**Recommandation finale :** pour 90% des prospects B2B français (PME industrielles 50-200 machines), **Option A — Serveur Dell PowerEdge R750xs on-prem** est le bon compromis coût/souveraineté/simplicité. Coût total 5 ans ≈ 17 k€ pour 100 machines, soit 34 €/machine/an — un argument commercial fort vs les SaaS concurrents.
