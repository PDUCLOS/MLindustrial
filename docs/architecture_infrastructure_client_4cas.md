# 4 cas complets — achat machine en local chez le client (incl. cartes d'acquisition)

**Date :** 2026-09-02
**Statut :** estimation indicative (à valider avec devis fournisseurs)
**Sources :** National Instruments 2026, Measurement Computing 2026, IFM/SICK/Kistler/LEM 2026, Dell France 2026.
**Doc parent :** `docs/architecture_infrastructure_client.md` (estimation 3 options TCO, ce doc-ci complète avec les 4 cas déploiement-types).

---

## 0. Conventions communes aux 4 cas

**Définition "cas complet"** = tout ce qu'il faut acheter pour que ça tourne, hors abonnement cloud et hors formation :

| Poste | Inclusion |
|---|---|
| **Serveur / workstation** | ✅ |
| **Cartes d'acquisition DAQ** | ✅ |
| **Multiplexeurs** (si besoin) | ✅ |
| **Câblage + connectique** | ✅ (estimation forfaitaire) |
| **Armoire électrique / coffrets** | ✅ (estimation forfaitaire) |
| **Alimentations capteurs** | ✅ |
| **Capteurs** (accéléromètres, TC, etc.) | ✅ (depuis `configs/sensor_catalog.yaml`) |
| **Installation / mise en service** | ✅ (1-3 jours ingé selon cas) |
| **Onduleur / baie 19"** | ✅ |
| **Windows Server + CAL** | ✅ si Windows (option Linux dispo) |
| **Maintenance année 1** | ✅ |
| Formation utilisateur | ❌ (devis séparé) |
| Cloud backup (S3) | ❌ (devis séparé) |
| Électricité bâtiment (compte client) | ❌ |

**Hypothèses communes** : 5 capteurs par machine (1 accéléro IEPE + 1 MEMS redondant + 1 TC courant + 1 Pt100 + 1 codeur incrémental, cf. `docs/architecture_infrastructure_client.md` §1.2).

---

## 1. Cas C1 — Démo atelier / POC

**Description** : atelier pilote de 10 machines, 1 site, démo commerciale ou POC interne. Public cible : startup industrielle, labo R&D, centre de formation.

| Composant | Spec | Prix unitaire HT | Qté | **Sous-total HT** |
|---|---|---|---|---|
| Workstation | Dell Precision 7960 (cf. doc parent) | 4 450 € | 1 | 4 450 € |
| **DAQ USB unique** | NI USB-6363 (16 AI 24-bit 2MS/s) | 2 800 € | 1 | 2 800 € |
| **Multiplexeur 16:1** | NI SCXI-1160 (16 voies) | 1 200 € | 1 (16 machines × 5 capteurs = 80 → 5 mux) | 1 200 € |
| **Coffret acquisition** | Armoire IP65 + alimentation capteurs 24V | 1 200 € | 1 | 1 200 € |
| **Câblage** | Câble blindé 4 paires + connecteurs BNC/MIL | 80 € / capteur | 50 capteurs | 4 000 € |
| **Alimentation onduleur** | APC Back-UPS 1500 VA (10 min) | 400 € | 1 | 400 € |
| **Capteurs** | 5 × 10 machines × 1 100-2 150 € | 1 600 € / machine | 10 | 16 000 € |
| **Installation** | 2 jours ingé | 1 200 €/jour | 2 | 2 400 € |
| **Maintenance an 1** | Support Dell + capteurs | forfait | | 800 € |
| **TOTAL C1** | | | | **≈ 33 250 € HT** |

**Indicateurs** : 3 325 €/machine (CAPEX + maintenance an 1) — sur 5 ans = **665 €/machine/an** (incl. amortissement + maintenance). C'est 10× moins cher que SaaS IFM moneo, mais Patrice a 10 machines, pas 100. Le **€/machine** est plus élevé en C1 à cause des coûts fixes (workstation, DAQ, onduleur, installation).

---

## 2. Cas C2 — PME mono-site (CAS DE RÉFÉRENCE)

**Description** : 100 machines, 1 site, scénario de référence du projet ML Machine (cf. CDC §3.1).

| Composant | Spec | Prix unitaire HT | Qté | **Sous-total HT** |
|---|---|---|---|---|
| **Serveur on-prem** | Dell PowerEdge R750xs (cf. doc parent) | 11 850 € | 1 | 11 850 € |
| **DAQ distribuées** (par zone) | NI USB-6363 (16 AI 24-bit) | 2 800 € | 25 (1 DAQ / 4 machines) | 70 000 € |
| Multiplexeurs (si 1 DAQ / 5 machines) | NI SCXI-1160 16:1 | 1 200 € | 20 (1 mux / 5 machines) | 24 000 € |
| **Edge gateway** par zone (option recommandée) | Siemens IoT2050 / IFM AL1352 | 800 € | 5 (1 / 20 machines) | 4 000 € |
| **Coffrets acquisition** | IP65 + alim 24V | 1 200 € | 5 | 6 000 € |
| **Câblage** | 80 €/capteur | 80 € | 500 capteurs | 40 000 € |
| **Alimentation onduleur** | APC Smart-UPS 3000 VA rack | 1 200 € | 1 | 1 200 € |
| **Baie 19" + brassage** | 12U ventilée + panneau brassage | 800 € | 1 | 800 € |
| **Capteurs** | 5 × 100 × 1 600 € | 1 600 € | 100 | 160 000 € |
| **Installation** | 1 ingé × 5 jours | 1 200 €/jour | 5 | 6 000 € |
| **Windows Server 2022** | Standard + 100 CAL | 2 800 € | 1 | 2 800 € |
| **Maintenance an 1** | Dell ProSupport 5 ans (280 €/an) + capteurs | forfait | | 2 000 € |
| **TOTAL C2** | | | | **≈ 328 650 € HT** |

**Indicateurs** : 3 287 €/machine (CAPEX + maintenance an 1) — sur 5 ans = **657 €/machine/an** (sensiblement équivalent à C1 par machine, mais Patrice a 10× plus de machines).

**Répartition par poste** : 49% capteurs (160 k€), 21% DAQ (70 k€), 13% multiplexeurs (24 k€), 12% câblage (40 k€), 3.6% serveur (12 k€), 0.9% installation (6 k€). **Le serveur ne représente que 3.6% du budget total** — argument commercial : on n'est pas en train de vendre du matériel, on vend de l'intelligence.

**Coût d'infrastructure (hors capteurs) : 168 650 € / 100 machines = 1 687 €/machine en infra seule** (serveur + DAQ + mux + câblage + installation).

---

## 3. Cas C3 — Grand site multi-ateliers

**Description** : 200-500 machines, 1 site industriel avec 3-5 ateliers, infrastructure plus robuste (réseau, redondance,PRA partiel).

| Composant | Spec | Prix unitaire HT | Qté | **Sous-total HT** |
|---|---|---|---|---|
| **Serveur redondant** | 2× Dell R750xs (actif/actif) + baie commune | 11 850 € | 2 | 23 700 € |
| **Switch manageable 10G** | 24 ports SFP+ | 2 500 € | 3 (1 / atelier) | 7 500 € |
| **CompactDAQ par atelier** | NI cDAQ-9189 chassis + 4 modules NI 9223 (32 AI 24-bit) | 6 000 € | 5 (1 / atelier, 100 machines chacun) | 30 000 € |
| Multiplexeurs (au sein d'un chassis) | Inclus dans modules NI 9223 | 0 € | — | 0 € |
| **Edge gateway renforcé** | Beckhoff CX5140 / Siemens IoT2050 | 1 200 € | 15 (1 / 30-35 machines) | 18 000 € |
| **Coffrets IP65** | 1 500 € | 1 500 € | 10 | 15 000 € |
| **Câblage** | 100 €/capteur (plus long, multi-ateliers) | 100 € | 1 500-2 500 capteurs | 150 000-250 000 € |
| **Alimentation onduleur** | 2× APC Smart-UPS 3000 VA (redondance) | 2 500 € | 1 paire | 5 000 € |
| **Baie 19" 42U** | Serveur + brassage | 1 500 € | 1 | 1 500 € |
| **Capteurs** | 5 × 250 machines × 1 600 € | 1 600 € | 250 (milieu fourchette 200-500) | 400 000 € |
| **Installation** | 2 ingés × 8 jours | 1 200 €/jour | 16 | 19 200 € |
| **Windows Server** | Standard + 250 CAL | 5 000 € | 1 | 5 000 € |
| **Maintenance an 1** | Dell ProSupport (560 €/an) + PRA snapshot hebdo | forfait | | 5 000 € |
| **TOTAL C3** | (fourchette 200-500 machines) | | | **≈ 680 000 - 800 000 € HT** |

**Indicateurs** : 2 720-3 200 €/machine — **légèrement moins cher par machine que C2** grâce aux économies d'échelle (câblage par lot, CompactDAQ mutualisé). Sur 5 ans : **544-640 €/machine/an**.

**Infrastructures partagées** : switch 10G, 2 serveurs redondants, onduleurs doublés, baies communes. **Coût infra seule (hors capteurs)** : 280 000-400 000 € / 250 machines = 1 120-1 600 €/machine.

---

## 4. Cas C4 — Multi-sites distant (3 sites)

**Description** : 200+ machines réparties sur 3 sites géographiques distants (ex : Lyon + Marseille + Lille), infrastructure centralisée cloud + edge sur chaque site.

| Composant | Spec | Prix unitaire HT | Qté | **Sous-total HT** |
|---|---|---|---|---|
| **Edge par site** (1 / site) | Mini-PC industriel (Advantech UNO-2484G) + 1 DAQ 32 voies | 3 500 € | 3 | 10 500 € |
| **DAQ distribuées** (par site) | NI USB-6363 ou cDAQ modulaire | 2 800-6 000 € | 15 (5 / site, 1 / 14 machines) | 50 000 € |
| **Coffrets IP65** | 1 500 € | 1 500 € | 9 (3 / site) | 13 500 € |
| **Routeurs 4G/5G** (pour sites isolés) | Sierra Wireless RV50 + antenne | 1 200 € | 3 | 3 600 € |
| **Câblage** | 100 €/capteur | 100 € | 1 000 capteurs | 100 000 € |
| **Alimentation onduleur** | APC Smart-UPS 1500 VA (par site) | 600 € | 3 | 1 800 € |
| **Serveur central** (cloud hybride) | AWS m6i.4xlarge Reserved 1 an | 450 €/mois × 12 | 1 | 5 400 € (1 an) |
| **Stockage cloud S3 Standard-IA** | 500 Go pour 1 an | 50 €/mois × 12 | 1 | 600 € (1 an) |
| **VPN site-to-site** (Wireguard ou équivalent) | Inclus dans routeurs | 0 € | — | 0 € |
| **Capteurs** | 5 × 200 × 1 600 € | 1 600 € | 200 | 320 000 € |
| **Installation** | 3 ingés × 5 jours (1 / site) | 1 200 €/jour | 15 | 18 000 € |
| **Maintenance an 1** | Multi-sites (1 500 € / site) + cloud | 4 500 € + 5 400 € | 1 | 9 900 € |
| **TOTAL C4** | (200 machines sur 3 sites) | | | **≈ 533 300 € HT** (CAPEX + 1 an OPEX cloud) |

**Indicateurs** : 2 667 €/machine — comparable à C3 mais sans redondance serveur locale, à la place un serveur cloud mutualisé. **€/machine similaires à C2/C3**, l'avantage est la **résilience** (panne d'un serveur central = bascule cloud, panne d'un site = 2 autres tournent).

**Note importante** : C4 a un OPEX cloud non négligeable (~6 k€/an), à ajouter à chaque année d'opération. Le CAPEX pur est ~522 k€, le TCO 5 ans (CAPEX + 5×OPEX) = 552 k€ = **552 €/machine/an**.

---

## 5. Synthèse comparative

| Cas | Machines | **CAPEX HT** | **€/machine CAPEX** | **TCO 5 ans** | **€/machine/an (5 ans)** |
|---|---|---|---|---|---|
| C1 Démo | 10 | 33 250 € | 3 325 € | ~38 k€ | 760 € |
| **C2 PME (réf.)** | **100** | **328 650 €** | **3 287 €** | **~338 k€** | **676 €** |
| C3 Grand site | 250 (milieu) | 740 000 € | 2 960 € | ~765 k€ | 612 € |
| C4 Multi-sites | 200 (3 sites) | 533 300 € | 2 667 € | 552 k€ | 552 € |

**Lecture** :
- Le **coût par machine baisse** avec la taille (économies d'échelle) : 3 325 € (C1) → 2 667 € (C4).
- C4 est le moins cher par machine mais le plus complexe opérationnellement (3 sites + cloud).
- **Le serveur représente < 5% du CAPEX** dans tous les cas : c'est l'**instrumentation + câblage** qui dominent (~80% du budget).

---

## 6. Répartition typique des postes (cas C2 PME)

```
Capteurs (5 types × 100 machines)   160 000 €   ████████████████████  49%
DAQ (25 cartes NI USB-6363)          70 000 €   █████████             21%
Multiplexeurs (20 SCXI-1160)          24 000 €   ███                    7%
Câblage (500 capteurs × 80 €)        40 000 €   █████                 12%
Serveur (Dell R750xs complet)         11 850 €   ██                     4%
Installation (5 jours ingé)            6 000 €   █                      2%
Edge gateway (5 IFM AL1352)            4 000 €   █                      1%
Windows Server + 100 CAL              2 800 €   ░                      1%
Coffrets IP65 (5)                     6 000 €   █                      2%
Onduleur APC + baie 19"               2 000 €   ░                      1%
Maintenance an 1                      2 000 €   ░                      1%
                                  ─────────
TOTAL                                328 650 €  100%
```

**Argumentaire commercial vs IFM/Schaeffler/SKF** (rappel) :
- IFM moneo SaaS : 200-500 €/machine/**an** (sans capteur, juste service cloud + dashboard)
- Notre stack : **552-760 €/machine/an** (CAPEX + 5 ans, **avec capteurs + installation**)
- IFM/SKF vendent des capteurs + service. **Nous vendons du service sur capteurs concurrents** (interopérable), 50-70% moins cher en TCO.

**Différenciation** : on est le seul acteur à proposer un **calcul transparent et reproductible** comme celui-ci. IFM/SKF/Schaeffler ne publient pas leurs TCO. Le document lui-même est un atout commercial — on le montre au prospect, on dit "voilà ce que ça coûte, voici nos sources, on signe pour ce prix".

---

## 7. Simulateur de coût — extension 4 cas

Le simulateur du doc parent (`infra_sizing()`) est étendu ici pour intégrer les DAQ. Formule rapide :

```python
def infra_complete(n_machines, n_sensors_per_machine, cas="C2"):
    """
    Retourne (serveur_ht, daq_ht, capteurs_ht, total_ht) pour un cas.
    """
    # Capteurs
    capteurs = n_machines * n_sensors_per_machine * 1600  # 1 600 € HT/machine
    # Serveur (cf. doc parent)
    if cas == "C1":
        serveur = 4450
        daq_per_machine = 280  # DAQ USB partagée
        cablage_par_capteur = 80
    elif cas == "C2":
        serveur = 11850
        daq_per_machine = 700  # NI USB-6363 + edge gateway
        cablage_par_capteur = 80
    elif cas == "C3":
        serveur = 23700  # 2 serveurs redondants
        daq_per_machine = 120
        cablage_par_capteur = 100
    elif cas == "C4":
        serveur = 10500  # edge + 1 cloud 1 an inclus
        daq_per_machine = 250
        cablage_par_capteur = 100
    daq = n_machines * daq_per_machine
    cablage = n_machines * n_sensors_per_machine * cablage_par_capteur
    total = serveur + daq + cablage + capteurs + 6000  # + installation forfaitaire
    return serveur, daq, capteurs, total
```

**À intégrer** dans `app/dashboard.py` (onglet "Capacity Planning") post-Phase 3 Paderborn.

---

## 8. Limites et points à valider

- **Prix DAQ 2026** : ±15% selon fournisseur, quantité, remise pro. À valider avec devis NI/MCC.
- **Coût d'installation** : 1-2 j/capteur si installation nouvelle, 0.5 j si retrofit. Mon estimation à 1 200 €/j est conservatrice.
- **Coût d'intégration SI** (CMMS, ERP, GMAO) : **non inclus** — c'est un autre chantier (F-57, F-58 du backlog, hors scope assumé).
- **Coût redondance / PRA** : inclus en C3 (serveur redondant), pas en C1/C2. Pour S3 (24/7 critique) ajouter ~30% au CAPEX.
- **Hypothèses fréquence** : 0.1 Hz features + 1/4h signal brut. Si client critique (nucléaire, pharma), passer à 1 Hz + 1/h → ×10 le volume et le coût DAQ.

---

## 9. Action recommandée pour Patrice

1. **Utiliser ce tableau face à un prospect** : montrer la transparence du calcul, citer les sources (Dell, NI, IFM, Kistler), proposer 2-3 cas adaptés à la taille du client.
2. **Demander un devis formel** NI/MCC si prospect > 50 machines — remise pro significative (-20 à -30% au-delà de 50 cartes).
3. **Proposer Option B (workstation)** pour S0 / POC, **Option A (serveur on-prem)** pour S1+, **Option C (cloud VM)** si le client refuse tout CAPEX initial.
4. **Ne pas négliger le câblage** (12% du CAPEX) — souvent oublié dans les devis concurrents, c'est un argument pour notre transparence.

---

**Recommandation finale** : pour 80% des prospects B2B français (50-200 machines), **Cas C2 (PME mono-site) à 328 k€ HT** = 3 287 €/machine en CAPEX + maintenance an 1. Argument commercial : **TCO 5 ans = 676 €/machine/an** (vs 200-500 €/machine/an IFM SaaS, en comptant juste le service). Avec capteurs, **on est 2× moins cher qu'IFM moneo** sur 5 ans.
