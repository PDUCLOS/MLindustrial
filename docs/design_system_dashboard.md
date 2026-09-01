# Règles d'interface — dashboard Streamlit

Règles à suivre pour tout nouvel onglet/composant du dashboard (`app/dashboard.py`, `app/tabs/*`). Trouvées en corrigeant des incohérences visuelles réelles (2026-09-01) — pas des préférences esthétiques, chacune a une cause concrète documentée ci-dessous. Toute nouvelle contribution qui les enfreint recrée le problème déjà corrigé une fois.

## 1. Source de vérité de la palette

Une seule palette, trois endroits synchronisés à la main (Streamlit ne permet pas de partager des variables CSS/Python nativement entre config et code) :

| Emplacement | Rôle |
|---|---|
| `.streamlit/config.toml` | Thème natif Streamlit (fond, texte, accent) |
| `app/dashboard.py` (`st.html` en tête de fichier, bloc `:root`) | Variables CSS pour le CSS custom injecté |
| `app/tabs/_styles.py::Palette` | Couleurs Python pour tout composant/graphique |

**Règle : si tu changes une couleur, change-la aux trois endroits.** Le commentaire dans `:root` (`app/dashboard.py`) et dans `Palette` (`_styles.py`) rappelle explicitement cette dépendance — ne pas le supprimer.

Couleurs sémantiques (`crit`/`warn`/`ok`) = Material Design 3, variantes 400 (assez claires pour rester lisibles sur fond sombre). Toute nouvelle couleur ajoutée doit citer sa source dans un commentaire, même règle que le "0 mock" du projet appliqué aux couleurs : pas de hex "plausible" sans raison.

## 2. Tout graphique matplotlib DOIT être thémé

**Constat (2026-09-01)** : les boxplots (onglet Indicateurs) et le scatter (onglet Historique) gardaient le fond blanc par défaut de matplotlib — contraste violent au milieu d'un dashboard sombre partout ailleurs. Corrigé.

**Règle** : tout nouveau `plt.subplots()` dans le dashboard doit :
```python
from app.tabs._styles import style_figure, BOXPLOT_PROPS, DEFECT_ORIGIN_COLOR, PALETTE

fig, ax = plt.subplots(...)
# ... tracé ...
style_figure(fig, ax)   # ou *axes si plusieurs sous-graphiques
st.pyplot(fig)           # PAS st.pyplot(fig, transparent=True) - deprecated,
                          # style_figure() a deja mis fig.patch alpha=0
```
Pour un boxplot pandas (`DataFrame.boxplot()`), passer `**BOXPLOT_PROPS` en argument — sinon boîtes/médiane/moustaches restent noires, quasi invisibles sur fond sombre.

Pour les couleurs de séries (scatter, courbes par catégorie) : utiliser `DEFECT_ORIGIN_COLOR` ou `STATUS_COLOR` (déjà dans `_styles.py`) plutôt que les noms `tab:red`/`tab:green` de matplotlib — garde la même sémantique couleur que le reste du dashboard (rouge = défaut réel/critique, vert = sain, orange = artificiel/warning).

## 3. Jamais de `st.sidebar` pour un contrôle spécifique à un onglet

**Constat (2026-09-01)** : le slider "graine aléatoire" de l'onglet Factory Twin était dans `st.sidebar`, donc visible sur les 10 onglets — y compris ceux qui n'ont rien à voir avec la simulation (Indicateurs, Alertes...). Corrigé en le déplaçant dans le corps de l'onglet.

**Règle** : `st.sidebar` est un espace GLOBAL, partagé par tous les onglets Streamlit (ce n'est pas scopé par tab). Ne l'utiliser que pour un contrôle vraiment transverse à tout le dashboard (aucun cas identifié à ce jour). Tout filtre/paramètre propre à un onglet reste dans le corps de cet onglet — suivre le pattern déjà en place (`st.selectbox("Feature", ...)` dans Alertes/Historique).

## 4. Les alertes Streamlit (`st.info`/`success`/`warning`/`error`) sont restylées via CSS testid

**Constat (2026-09-01)** : couleurs web génériques (bleu/vert/orange/rouge) par défaut, en rupture avec la palette terracotta. Corrigé par CSS ciblant `[data-testid="stAlertContainer"]` + `[data-testid="stAlertContent{Info,Success,Warning,Error}"]` (liseret gauche coloré + fond sombre uniforme).

**Fragilité connue** : ces `data-testid` sont des détails d'implémentation interne de Streamlit, pas une API publique stable — vérifiés sur la version du projet à cette date (voir `pyproject.toml`). **En cas d'upgrade Streamlit, si les alertes reviennent en bleu/vert par défaut**, ré-inspecter le DOM (`javascript_tool` ou devtools : chercher l'élément contenant le texte de l'alerte, remonter les parents jusqu'à trouver le nouveau testid) avant de réécrire le CSS à l'aveugle.

## 5. Checklist avant de merger un nouvel onglet

- [ ] Toute couleur vient de `Palette` (`_styles.py`), pas un hex inventé
- [ ] Tout graphique matplotlib passe par `style_figure()` (+ `BOXPLOT_PROPS` si boxplot)
- [ ] Aucun `st.sidebar.*` sauf contrôle réellement global
- [ ] Testé visuellement dans le navigateur (pas seulement `python -c "import ..."` qui ne détecte pas les problèmes de rendu)
