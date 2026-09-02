# Faut-il construire un modèle ML ? (arbre de décision)

Question distincte de [[arbre_decision]] (diagnostic d'un cas donné) : ici,
c'est une décision de MÉTHODE — est-ce que ce sujet (détérioration de dent,
manque de lubrification) justifie d'entraîner un modèle, ou est-ce que
l'approche par règles ([[algorithme_propose]]) suffit ? Reprend la
discipline déjà appliquée dans `docs/brief_projet.md` §4 (baseline
obligatoire avant tout modèle) et `docs/known_issues.md` (règle d'arrêt
binaire pré-enregistrée avant le run kurtogramme P3-A — même logique
appliquée ici en amont, avant même de lancer quoi que ce soit).

```
Nouveau sujet de détection envisagé (ex. dent/lubrification réducteur)
│
├─ Y a-t-il une vérité terrain labellisée (défaut confirmé / sain confirmé,
│  pas une supposition) pour CE type d'équipement ?
│  └─ NON → PAS DE ML. Rester sur l'arbre de règles (physique sourcée,
│           [[algorithme_propose]]) tant qu'aucune vérité terrain n'existe.
│           C'est le cas actuel du projet pour les réducteurs (aucun
│           réducteur réel en base, contrairement aux 32 roulements
│           Paderborn qui ont une vérité terrain).
│
├─ OUI, vérité terrain disponible → combien de cas labellisés distincts
│  (pas de mesures — d'ÉQUIPEMENTS/événements distincts, même piège que
│  `docs/brief_projet.md` piège #1, split par entité) ?
│  ├─ Poignée de cas (< ~20-30, ordre de grandeur Paderborn) →
│  │  ML à haut risque de sur-apprentissage / faux résultat. PRÉFÉRER un
│  │  seuil/règle sur un indicateur physique (ex. NA4, énergie de bande
│  │  latérale) avec baseline chiffrée AVANT tout modèle plus complexe -
│  │  exactement le protocole déjà suivi pour les roulements
│  │  (`docs/results_phase2.md`).
│  └─ Volume suffisant pour une validation croisée robuste (pas de chiffre
│     magique - dépend du nombre de classes et du déséquilibre, mais
│     l'ordre de grandeur "quelques centaines de cas distincts" est un
│     repère raisonnable) → ML envisageable, MAIS seulement après avoir
│     mesuré la baseline règles/seuil et vérifié qu'un modèle la bat
│     FRANCHEMENT (`docs/brief_projet.md` §4, règle 4).
│
├─ Est-ce que la question posée a une réponse interprétable par un chef
│  d'atelier avec l'approche par règles (fréquence + étage identifié) ?
│  └─ OUI → argument supplémentaire pour NE PAS ajouter de ML tout de
│           suite : `docs/brief_projet.md` §9, l'interprétabilité EST la
│           valeur du projet, pas un obstacle à contourner avec un modèle
│           plus "précis" mais opaque.
│
└─ L'utilisateur demande-t-il explicitement un modèle sur un capteur/sujet
   précis (voir capacité "demander un ML spécifique" évoquée en session) ?
   └─ OUI → l'exécuter est légitime SI la vérité terrain existe (retour à
            la première branche), mais présenter la limite honnêtement si
            le volume est faible plutôt que de cacher un résultat instable
            derrière un chiffre unique (même règle que `docs/results_phase2.md`,
            écarts-types affichés systématiquement).
```

## Conclusion pour le sujet dent/lubrification réducteur, à ce jour (2026-09-02)

**Pas de ML aujourd'hui.** Aucune vérité terrain sur un réducteur réel dans
le projet — seul le simulateur Factory Twin (`src/gearbox/helical.py`)
génère des signatures, labellisées "SIMULÉ" et distinctes du réel
(`docs/brief_projet.md` §1, extension simulation). Utiliser ces données
simulées pour VALIDER que [[algorithme_propose]] détecte bien les défauts
qu'on y a injectés (dent cassée, usure) est légitime et utile — les
utiliser pour entraîner un modèle présenté comme généralisable au réel ne
le serait pas (même piège que la génération artificiel→réel documentée
pour les roulements, `docs/known_issues.md`).
