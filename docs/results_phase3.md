# Phase 3 — resultats

**Statut :** squelette prepare avant le run P3-A (validation kurtogramme
consensus sur 32 roulements). A remplir a l'issue du run, selon la regle
d'arret actee dans `docs/known_issues.md` §F-07. Aucun chiffre dans ce
document tant que le run n'a pas eu lieu — pas de placeholder invente.

---

## P3-A — Validation kurtogramme consensus (32 roulements)

### Grille d'analyse post-run

Une ligne par roulement. `bande_reference` = bande consensus K001/KA01
etablie sur l'echantillon initial (~15872-16384 Hz, cf. `known_issues.md`
§F-07).

| bearing_id | health_state | defect_origin | bande_top1 | kurtosis_top1 | bande_top2 | kurtosis_top2 | ecart_top1_top2 | matches_bande_reference | verdict |
|---|---|---|---|---|---|---|---|---|---|
| ... | sain / artificiel / reel | ... | ... | ... | ... | ... | ... | oui/non | clair / ambigu |

**Definition "ambigu"** : ecart top1/top2 < 10% de kurtosis_top1 (seuil a
ajuster si besoin, mais fixer AVANT de lire les resultats pour ne pas
l'ajuster a posteriori pour faire converger la conclusion).

### Aggregation

| Categorie | N | % bande_reference matchee | % ambigu |
|---|---|---|---|
| Sains (healthy) | ... | ... | ... |
| Defaut artificiel | ... | ... | ... |
| Defaut reel | ... | ... | ... |

### Decision (regle d'arret `known_issues.md` §F-07)

- [ ] **Cas A — activation** : motif reproductible sur la majorite des
  roulements a defaut reel -> voir §"Cas A" ci-dessous.
- [ ] **Cas B — desactivation** : ambiguite multi-candidats repetee sans
  regle de discrimination fiable -> voir §"Cas B" ci-dessous.

---

## Cas A — F-06/F-07/F-08 actives par defaut

*A remplir seulement si la decision ci-dessus coche "Cas A".*

- Bande de resonance consensus retenue : `<a completer>`
- % roulements matchant la bande de reference : `<a completer>`
- Changement de pipeline : `--with-envelope` active par defaut dans
  `scripts/build_dataset.py`, F-08 (energie BPFO/BPFI/BSF/FTF) debloque.
- Impact attendu sur le GBM (a mesurer, pas a anticiper) : nouvelles
  features disponibles pour le run P3-B (artificiel -> reel).
- Prochaine etape : relancer `scripts/build_dataset.py --with-envelope`
  sur les 32 roulements, puis P3-B avec le jeu de features etendu.

## Cas B — F-06/F-07/F-08 desactivees definitivement (resultat negatif)

*A remplir seulement si la decision ci-dessus coche "Cas B".*

- Nature de l'ambiguite observee (ex. motif KA04 generalise, ou autre) :
  `<a completer>`
- % roulements a defaut reel concernes : `<a completer>`
- Pourquoi aucune regle de discrimination fiable n'a ete trouvee :
  `<a completer>`
- Consequence : `--with-envelope` reste desactive, F-08 reste bloque. Le
  GBM Phase 3 tourne sur les features temporelles seules (RMS, kurtosis,
  crest factor) — cf. docs/brief_projet.md regle 4, resultat honnete plutot qu'un
  raffinement sans fin.
- Valeur du resultat : documente une limite reelle de l'analyse
  d'enveloppe/kurtogramme sur ce dataset, pas un echec de mise en oeuvre —
  a rapporter tel quel (docs/brief_projet.md §9, "des resultats negatifs assumes").

---

## P3-B — Generalisation artificiel -> reel

*A demarrer une fois P3-A tranche (Cas A ou Cas B). Squelette a completer
une fois ce run lance — pas de resultat anticipe ici.*
