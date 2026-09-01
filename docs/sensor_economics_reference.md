# Référence économique capteurs — pour calculateur ROI

**Date :** 2026-08-31
**But :** préparer la partie "coûts" du calculateur ROI capteur (angle #1 retenu dans `docs/differentiation_strategy.md`). Les chiffres de performance viendront après Phase 3 — ici on documente les **prix réels des capteurs et de l'installation**, plus l'**option "courant moteur via VFD existant"** qui est l'argument central du brief §9.
**Sources :** catalogues et comparateurs publics 2025-2026, validés sur plusieurs revendeurs quand possible.

---

## 1. Capteurs de vibration industriels — prix catalogue 2025-2026

### 1.1 IFM (référence sensor + IO-Link)

Source : https://www.ifm.com/us/en/us/condition-monitoring-sensors, comparateurs Zipstore, KR West (distributeur US), Mouser.

| Modèle | Description | Prix indicatif (HT) |
|---|---|---|
| **VVB001** | IO-Link 1-axis vibration sensor (M8 mounting, IP67/68/69K) | 514 EUR |
| **VVB021** | IO-Link 1-axis vibration sensor (M8, IP67/68/69K) | 588 EUR |
| **VVB306** | IO-Link 3-axis vibration sensor (M5 mounting, COM3 230 kbaud) | 670-750 EUR (estim. à partir des 1-axis) |
| **VSA001** | Accelerometer M8 | 147 USD |
| **VSA005** | Accelerometer M5, IP67 | 233 USD |
| **VSP01A** | Accelerometer ATEX (zones explosives) | 683 EUR |
| **VSP004** | Accelerometer submersible IP68 (10 bar) | 698 EUR |
| **VNB001** | Vibration velocity sensor (mm/s) | 465 USD |
| **VKV022 / VTV122** | Vibration velocity | 230-251 USD |
| **VSE951** | Diagnostic electronics, 8-channel input | 2010 EUR |

**Starter kit / accessoires :**
- ZZ0809 VVB IO-Link starter kit : 789 EUR
- EVC001 M12 connector (câble PUR 10 m) : 13.50 USD
- Câbles 5 m / 10 m : 23-69 USD selon connectique

### 1.2 Schaeffler / FAG (référence RUL + diagnostic)

Source : RUBIX UK, RS Africa, eBay, brochure Schaeffler.

| Modèle | Description | Prix indicatif (HT) |
|---|---|---|
| **FAG SmartCheck (SMART-CHECK)** | Vibration 1-canal en ligne, ISO 10816, FFT intégré | 1055-1283 EUR (selon accessoire) |
| **SmartCheck basic starter kit** | Pour intégration | 909 GBP = 1055 EUR environ |
| **ProLink CMS** | 8-channel central, rackable | Prix sur demande (Enterprise) |
| **OPTIME Wireless** | Capteur sans fil, mesh 2.4 GHz, gateway + cloud | Prix sur demande (subscription-based) |

### 1.3 SKF (référence plateforme + format data)

Source : ERIKS UK, ACORN UK, IndustrialWorld Australia.

| Modèle | Description | Prix indicatif (HT) |
|---|---|---|
| **Axios CMWA 6400-5** | Pack 5 capteurs sans fil (3-axis MEMS, 26.7 kHz, IP69) | 1920-2070 USD/pack = **384-414 USD/capteur** |
| **Axios CMWA 6710** | Ethernet gateway | 260-407 USD |
| **Axios CMWA 6720** | Wi-Fi gateway | 200-310 USD |
| **Enlight AI** | Plateforme cloud + analytics | Quote-based (pas publié) |

**Note :** SKF publie "Per sensor custom quote · Annual subscription · Hardware purchased separately" — pas de prix public pour la plateforme.

### 1.4 Capteurs low-cost (alternatives pour petits budgets)

| Source | Modèle | Description | Prix | Note |
|---|---|---|---|---|
| Dragino | LHT65N-VIB | LoRaWAN vibration sensor, 3-axis | ~80-120 USD | 2400 mAh, 3+ ans batterie, IP66 |
| Advantech | WISE-2410 | LoRaWAN ARM Cortex-M4, 3-axis, IP66 | ~250 USD | 2 ans batterie (2x AA 3.6V) |
| Banner Engineering | DXM700 | Vibration + multi-capteurs, Modbus + cellular | 500-2000 USD | Industriel US |
| Prowave | PW-L01 | LoRa vibration, FFT intégré | ~150-300 USD | 1-2 ans batterie |
| MEMS générique (OxMaint 2026) | 3-axis wireless | LoRaWAN, IP67 | **47 USD** (moyenne 2026) | Pour monitoring non-critique |

**Coût moyen capteur 3-axis MEMS wireless 2026 :** ~47 USD (moyenne marché, vs ~500-700 USD pour un IFM/SKF filaire certifié).

## 2. Coût d'installation / retrofit

### 2.1 Installation mécanique

- **Câblage** (chemin de câble, presse-étoupe, connecteur M12) : 50-200 USD/capteur selon distance
- **Point de mesure** (perçage, taraudage, préparation surface) : 30-100 USD/capteur
- **Fixation** (collier, époxy de montage, adhésif) : 10-50 USD/capteur
- **Main d'œuvre installation** (1-2 h par capteur selon environnement) : 100-300 USD/capteur (à 50-150 USD/h atelier)

**Total installation type (hors capteur) :** 200-650 USD/capteur pour du retrofit sur machine existante.

### 2.2 Variateur de fréquence (VFD) — référence pour l'argument "courant moteur gratuit"

Source : ABB catalog, NEEA market report, vfds.org pricing.

| Modèle | Puissance | Prix catalogue (USD) | Prix / HP |
|---|---|---|---|
| **ABB ACS510-01-03A3-4** | 1.1 kW (1.5 HP) | 420 | 280/HP |
| **ABB ACS510-01-017A-4** | 7.5 kW (10 HP) | 767 | 77/HP |
| **ABB ACS510-01-088A-4** | 45 kW (60 HP) | 2940 | 49/HP |
| **ABB ACS510-01-290A-4** | 160 kW (215 HP) | 10722 | 50/HP |
| **ABB ACS800-01-0003-3** | 1.5 kW (2 HP) | 1300 | 650/HP (premium) |
| **ABB ACS800-01-0120-3** | 110 kW (150 HP) | 9550 | 64/HP |
| Generic GK3000-4T0075 | 7.5 kW (10 HP) | 463 | 46/HP |
| **Coût installé typique** (toutes marques) | — | — | **200-500 USD/HP** |

**Conclusion** : un VFD pour 1 machine de 10 HP coûte 500-2500 USD installé. Pour une flotte de 50+ machines neuves, c'est un investissement lourd, mais c'est déjà amorti dans les sites qui en sont équipés (cas typique de l'industrie).

### 2.3 Accès au signal courant moteur — coût marginal

Si un VFD est **déjà installé** sur la machine, l'accès au courant moteur est :

- **Coût matériel** : 0 (le VFD expose déjà le signal sur ses bornes, ou via Modbus/Profibus/Ethernet)
- **Coût logiciel** : 0 (le VFD publie les données, ou un petit script d'extraction sur quelques heures)
- **Coût installation** : ~0 (pas de nouveau capteur, juste un branchement software)

**Si pas de VFD** (moteur asynchrone direct sur secteur) :
- Capteur de courant clip-on (type LEM PR30, 50-200 USD) + conditionnement (5-50 USD)
- Ou pinces ampèremétriques + ADC (~100-500 USD)
- **Mais :** sans VFD, on perd la signature de défaut aux fréquences variables (cf. `docs/theorie_reference.md` §4 — MCSA nécessite conditions de charge ≥ 40% et la modulation VFD révèle mieux les défauts)

## 3. Synthèse — comparatif des 3 options

| Option | Coût d'installation (USD/capteur ou USD/machine) | Coût récurrent | Signal qualité | Inconvénient principal |
|---|---|---|---|---|
| **Vibration IFM VVB IO-Link** | 700-900 (capteur) + 200-650 (install) = **~1000-1500 USD** | 0 (hardware) ou 50-100 USD/an (monitoring) | Très bon, edge computing ISO 20816 | Coût initial élevé |
| **Vibration SKF Axios sans fil** | 400-500 (capteur) + 50-200 (pas de câble) = **~500-700 USD** | 100-500 USD/an (Enlight cloud) | Bon, mais indicateurs calculés seulement (pas de raw) | Vendor lock-in, subscription |
| **Capteur MEMS low-cost (47 USD)** | 47-150 (capteur) + 200-650 (install) = **~250-800 USD** | 0 (DIY) ou 50-100 USD/an (DIY cloud) | Acceptable, précision inférieure | Pas de certification industrielle |
| **Courant moteur via VFD existant** | **~0 USD** (si VFD déjà installé) | 0 | Acceptable pour défaut bague, limité pour défaut bille | Pas de défaut détectable si charge < 40% ou si pas de VFD |
| **Courant moteur via capteur clip-on** | 50-200 (capteur) + 50-200 (conditionnement) = **~100-400 USD** | 0 | Acceptable | Pas de signature VFD, moins de richesse spectrale |

## 4. Implications pour le calculateur ROI (à construire post-Phase 3)

L'angle #1 de `docs/differentiation_strategy.md` est de calculer le ROI d'une installation de monitoring. Les inputs à rentrer sont :

1. **Coût d'installation** (par capteur ou par machine) : tableau §3 ci-dessus
2. **Coût d'un défaut non détecté** : à demander à Patrice — chiffre dépend de la criticité machine
3. **Probabilité de défaut par an** : domaine-dépendant
4. **Performance du modèle** (vibration vs courant vs fusion) : à mesurer en Phase 3
5. **Taux de faux positifs** : à mesurer aussi en Phase 3
6. **Coût d'opportunité d'un faux positif** (inspection inutile) : à discuter

**Le calculateur ne peut PAS être construit avant la Phase 3** (il a besoin des chiffres de performance). Ce document est la partie "coûts d'installation" prête à être branchée dès que les performances seront disponibles.

## 5. Fourchettes cibles (pour le scénario Patrice typique)

Hypothèse : Patrice vise un parc de **100 machines** dans une usine existante (déjà équipée VFD), profil B2B distribution industrielle.

| Option | Coût total parc (USD) | Commentaire |
|---|---|---|
| 100 × vibration IFM VVB filaire | 100 000 - 150 000 | Standard industriel, ROI clair si > 5 défauts/an évités |
| 100 × SKF Axios sans fil + Enlight | 50 000 - 70 000 + 10 000-50 000/an | Plus rapide à déployer, vendor lock-in |
| 100 × MEMS low-cost DIY | 25 000 - 80 000 | Moins précis, plus de faux positifs |
| 100 × courant moteur via VFD existant | **0** (capteur) + ~50-200 h intégration | Argument central du brief §9 — coût marginal |

**Ratio de coût :** l'option "courant moteur via VFD" est **100-1000x moins chère** que les solutions vibration. Si la performance (F1 macro, taux de détection) tient à > 80% de la solution vibration, l'argument économique est massif.

## 6. Limites de ce document

- **Prix non contractuels** : varient selon région, quantité, contrats-cadres, promotions. À valider avec les fournisseurs réels.
- **Pas d'installations réelles documentées** : ce sont des fourchettes catalogue, pas du vécu.
- **Coût total de possession (TCO) non calculé** : maintenance, calibration, remplacement batterie (sans fil), formation, etc. — à ajouter si pertinent.
- **Pas de retour sur investissement chiffré** : nécessite les performances Phase 3 (prévu T+).

## 7. Sources principales

- IFM : https://www.ifm.com/us/en/us/condition-monitoring-sensors, KR West (distributeur US)
- Schaeffler : RUBIX UK (https://uk.rubix.com), RS Africa, brochures Schaeffler
- SKF : ERIKS UK (https://shop.eriks.co.uk), ACORN (https://www.acorn-ind.co.uk)
- Comparateurs low-cost : OxMaint 2026, IoTBearings, Dragino, Advantech
- VFD : ABB catalog, NEEA market report 2025, vfds.org pricing
- iFactory (capteursless MCSA) : https://ifactoryapp.com/industries/power-plant
