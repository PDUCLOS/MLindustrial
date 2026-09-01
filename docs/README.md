# Index de la documentation

Ce dossier contient la documentation stratégique et opérationnelle du projet, en français, datée par sujet.

> **Le brief du projet est [`brief_projet.md`](brief_projet.md).** À lire en premier pour le contexte et l'intention.

---

## 📂 Couches de documentation

| Couche | Fichier | Quand le lire |
|---|---|---|
| **Brief projet** | [`brief_projet.md`](brief_projet.md) | Toujours en premier — contexte, objectifs, pièges méthodologiques, roadmap |
| **Glossaire** | [`glossaire_pedagogique.md`](glossaire_pedagogique.md) | 12 termes en langage accessible (opérateur / chef d'atelier) |
| **Architecture DB** | [`data_model.md`](data_model.md) | Quand on touche au schéma, aux splits, à l'ingestion |
| **Théorie métier** | [`theorie_reference.md`](theorie_reference.md) | Fondement physique (normes ISO, fréquences caractéristiques, MCSA, kurtogramme) |
| **Règles UI dashboard** | [`design_system_dashboard.md`](design_system_dashboard.md) | Avant tout nouvel onglet/composant Streamlit |
| **Positionnement produit** | [`differentiation_strategy.md`](differentiation_strategy.md) | Pourquoi certaines choses ne sont pas faites (CMMS, RUL, ...) |
| **Scalabilité** | [`scaling_path.md`](scaling_path.md) | Si on se demande si on a besoin de Ray/K8s/Airflow |
| **Résultats Phase 2** | [`results_phase2.md`](results_phase2.md) | Chiffres baseline/GBM avec intervalles de confiance |
| **Résultats Phase 3** | [`results_phase3.md`](results_phase3.md) | Squelette de grille d'analyse — à remplir à l'issue du run, aucun chiffre inventé |
| **Problèmes ouverts** | [`known_issues.md`](known_issues.md) | Anomalies documentées (kurtogramme, confusion date/asset, géométrie corrigée) |
| **Concurrence** | [`competitive_analysis.md`](competitive_analysis.md) | Ce que font les leaders (IFM, Schaeffler, SKF, Augury, ...) |
| **Communication** | [`communication_architecture.md`](communication_architecture.md) | Trajectoire d'interopérabilité (OPC-UA, MQTT, Sparkplug B, AAS) |
| **Backlog** | [`feature_backlog.md`](feature_backlog.md) | Implémenté / désactivé / planifié / hors scope / piste future |

---

## 🗺 Carte mentale rapide

```
                    brief_projet.md
                            │
        ┌───────────────────┼─────────────────────────┐
        │                   │                          │
   Couche data         Couche métier            Couche produit
        │                   │                          │
   data_model.md    theorie_reference.md      differentiation_strategy.md
                            │                          │
                            │                   competitive_analysis.md
                            │                          │
                            │              communication_architecture.md
                            │                          │
                            └────────────┬─────────────┘
                                         │
                                  feature_backlog.md
                                         │
                            ┌────────────┼────────────┐
                            │            │             │
                       Résultats    Problèmes      Scaling
                            │            │             │
                   results_phase2  known_issues  scaling_path
                            │
                       README.md (racine) — présentation du projet
```

---

## 🔄 Règle de maintenance

À chaque fin de phase (Phase 3, Phase 4) :
1. Vérifier que les statuts dans `feature_backlog.md` sont à jour
2. Compléter `results_phaseN.md` (nouveau fichier par phase)
3. Si de nouveaux pièges émergent, ajouter dans `known_issues.md`
4. Si de nouvelles features sont décidées, mettre à jour `brief_projet.md`

Ne pas modifier un doc sans raison — chaque fichier a un objet précis, éviter les redites entre docs.
