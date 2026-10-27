"""Genere docs/architecture.drawio (4 pages) a partir d'une description en Python.

Positions explicites + connecteurs orthogonaux : les fleches restent propres
quand on modifie une boite. Export PNG : voir docs/README_vitrine (draw.io CLI).

Usage : python scripts/build_architecture_drawio.py
"""

from html import escape
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "docs" / "architecture.drawio"

C = {  # (fill, stroke)
    "src": ("#f5f5f5", "#666666"), "ing": ("#dae8fc", "#6c8ebf"), "sto": ("#e1d5e7", "#9673a6"),
    "feat": ("#d5e8d4", "#82b366"), "ml": ("#fff2cc", "#d6b656"), "ops": ("#f8cecc", "#b85450"),
    "ui": ("#ffe6cc", "#d79b00"), "k8s": ("#dae8fc", "#326ce5"), "white": ("#ffffff", "#666666"),
}


class Page:
    def __init__(self, pid: str, name: str, title: str, subtitle: str, w=1654, h=1169):
        self.pid, self.name, self.w, self.h = pid, name, w, h
        self.cells: list[str] = []
        self.n = 0
        self.text(title, 40, 15, 1400, 30, 18, "#333333")
        self.text(subtitle, 40, 47, 1500, 22, 12, "#555555")

    def _id(self) -> str:
        self.n += 1
        return f"{self.pid}-{self.n}"

    def text(self, value, x, y, w, h, size=12, color="#333333", align="left"):
        cid = self._id()
        style = (f"text;html=1;whiteSpace=wrap;fontSize={size};align={align};"
                 f"verticalAlign=middle;fontColor={color};")
        self._vertex(cid, value, style, x, y, w, h)
        return cid

    def group(self, label, x, y, w, h, kind):
        fill, stroke = C[kind]
        style = (f"rounded=1;arcSize=3;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};"
                 "verticalAlign=top;align=left;spacingLeft=10;spacingTop=4;fontStyle=1;fontSize=13;")
        cid = self._id()
        self._vertex(cid, label, style, x, y, w, h)
        return cid

    def box(self, value, x, y, w=200, h=60, kind="white", dashed=False, size=11):
        fill, stroke = C[kind]
        style = (f"rounded=1;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};"
                 f"fontSize={size};" + ("dashed=1;" if dashed else ""))
        cid = self._id()
        self._vertex(cid, value, style, x, y, w, h)
        return cid

    def edge(self, a, b, label="", dashed=False, exit_=None, entry=None, color="#444444"):
        style = ("edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;html=1;endArrow=block;"
                 f"endFill=1;strokeWidth=1.5;strokeColor={color};fontSize=10;labelBackgroundColor=#ffffff;")
        if dashed:
            style += "dashed=1;"
        if exit_:
            style += f"exitX={exit_[0]};exitY={exit_[1]};exitDx=0;exitDy=0;"
        if entry:
            style += f"entryX={entry[0]};entryY={entry[1]};entryDx=0;entryDy=0;"
        cid = self._id()
        self.cells.append(
            f'<mxCell id="{cid}" value="{escape(label)}" style="{style}" edge="1" parent="1" '
            f'source="{a}" target="{b}"><mxGeometry relative="1" as="geometry" /></mxCell>'
        )

    def _vertex(self, cid, value, style, x, y, w, h):
        self.cells.append(
            f'<mxCell id="{cid}" value="{escape(value)}" style="{style}" vertex="1" parent="1">'
            f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry" /></mxCell>'
        )

    def xml(self) -> str:
        body = "\n        ".join(self.cells)
        return (
            f'  <diagram id="{self.pid}" name="{escape(self.name)}">\n'
            f'    <mxGraphModel dx="1600" dy="1000" grid="1" gridSize="10" guides="1" tooltips="1" '
            f'connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="{self.w}" '
            f'pageHeight="{self.h}" math="0" shadow="0">\n      <root>\n'
            f'        <mxCell id="0" />\n        <mxCell id="1" parent="0" />\n        {body}\n'
            "      </root>\n    </mxGraphModel>\n  </diagram>"
        )


R, L, T, B = (1, 0.5), (0, 0.5), (0.5, 0), (0.5, 1)


def page_pipeline() -> Page:
    p = Page("p1", "1. Pipeline données et ML",
             "<b>MLindustrial</b> — du signal brut au diagnostic (code actuel du dépôt)",
             "Chaque étape correspond à un script ou un module du dépôt. Les signaux bruts restent en "
             "Parquet ; la base ne stocke que les métadonnées et les indicateurs.", h=620)
    p.group("1. Source", 40, 90, 220, 460, "src")
    s1 = p.box("<b>Paderborn KAt</b><br>32 roulements 6203<br>4 régimes x 20 mesures<br>"
               "64 kHz, 4 s, .mat (21 Go)", 50, 130, 200, 90, "white")
    s2 = p.box("<b>scripts/download_paderborn.sh</b><br>archives .rar officielles<br>(5,4 Go)",
               50, 250, 200, 70)
    s3 = p.box("<b>configs/*.yaml</b><br>géométrie roulement (fiche<br>constructeur), libellés défauts",
               50, 350, 200, 70)
    p.group("2. Ingestion", 290, 90, 230, 460, "ing")
    i1 = p.box("<b>src/data/loaders.py</b><br>parse nom de fichier :<br>régime, roulement, mesure",
               305, 130, 200, 70)
    i2 = p.box("<b>src/data/plausibility.py</b><br>contrôles physiques<br>(valeurs impossibles)",
               305, 230, 200, 70)
    i3 = p.box("<b>Parquet</b> par mesure<br>vibration + 2 courants", 305, 330, 200, 60)
    p.group("3. Stockage", 550, 90, 230, 460, "sto")
    d1 = p.box("<b>PostgreSQL / TimescaleDB</b><br>site → machine → actif<br>→ signal → feature",
               565, 130, 200, 80)
    d3 = p.box("tables <b>machine, asset,<br>bearing_attributes</b><br>(géométrie, libellés)",
               565, 340, 200, 70)
    d2 = p.box("table <b>feature</b> (format long)<br>hypertable si Timescale<br>"
               "(sinon table classique)", 565, 240, 200, 70)
    p.group("4. Features", 810, 90, 230, 460, "feat")
    f1 = p.box("<b>Temporel</b><br>RMS, crête à crête, facteur<br>de crête, kurtosis, asymétrie",
               825, 130, 200, 80)
    f2 = p.box("<b>Fréquences de défaut</b><br>BPFO / BPFI / BSF / FTF<br>depuis la géométrie",
               825, 240, 200, 70)
    f3 = p.box("<b>Enveloppe + kurtogramme</b><br>désactivé par défaut<br>(instabilité documentée)",
               825, 340, 200, 70, dashed=True)
    p.group("5. Modèles", 1070, 90, 230, 460, "ml")
    m1 = p.box("<b>Baseline seuil</b><br>kurtosis, sens appris<br>sur le train", 1085, 130, 200, 70)
    m2 = p.box("<b>XGBoost</b><br>vibration / courant / fusion", 1085, 230, 200, 60)
    m3 = p.box("<b>CV groupée par roulement</b><br>StratifiedGroupKFold 5 folds<br>"
               "+ assert_no_asset_leakage", 1085, 320, 200, 80)
    m4 = p.box("<b>Artificiel → réel</b><br>scripts/bench_vitrine.py", 1085, 430, 200, 60)
    p.group("6. Suivi et restitution", 1330, 90, 260, 460, "ui")
    o1 = p.box("<b>MLflow</b><br>params, F1, hash dataset", 1345, 130, 230, 60, "white")
    o2 = p.box("<b>Evidently</b><br>dérive train / test (KS)", 1345, 220, 230, 60)
    p.box("<b>Streamlit</b><br>alertes, spectre, jumeau<br>numérique d'usine", 1345, 310, 230, 70)
    o4 = p.box("<b>API FastAPI</b> (api/main.py)<br>signal brut → diagnostic<br>"
               "modèle exporté models/*.json", 1345, 410, 230, 80, "ui")
    p.edge(s2, s1, "", exit_=T, entry=B)
    p.edge(s1, i1, "", exit_=R, entry=L)
    p.edge(i1, i2, "", exit_=B, entry=T)
    p.edge(i2, i3, "", exit_=B, entry=T)
    p.edge(i3, d1, "chemins", exit_=R, entry=L)
    p.edge(s3, d3, "init_db.py (seed)", exit_=B, entry=B, dashed=True)
    p.edge(d1, d2, "", exit_=B, entry=T)
    p.edge(d2, f1, "", exit_=R, entry=L)
    p.edge(f1, m1, "", exit_=R, entry=L)
    p.edge(f1, m2, "", exit_=R, entry=L)
    p.edge(f2, f3, "", exit_=B, entry=T, dashed=True)
    p.edge(m2, m3, "", exit_=B, entry=T)
    p.edge(m3, m4, "", exit_=B, entry=T)
    p.edge(m1, o1, "", exit_=R, entry=L)
    p.edge(m3, o1, "", exit_=R, entry=L)
    p.edge(m3, o2, "", exit_=R, entry=L)
    p.edge(m4, o4, "export", exit_=R, entry=L)
    p.text("Pointillés = composant présent mais inactif par défaut. Ligne de commande de chaque étape "
           "dans le README ; mesures dans docs/PORTFOLIO.md.", 40, 570, 1500, 30, 11, "#666666")
    return p


def page_eval() -> Page:
    p = Page("p2", "2. Protocole d'évaluation",
             "<b>Évaluer honnetement</b> — le roulement est l'unité de découpage, jamais la fenêtre de signal",
             "Une même bague vue en entraînement et en test donnerait des scores flatteurs : chaque "
             "découpage ci-dessous garantit qu'aucun roulement n'est des deux côtés.", h=820)
    p.group("Jeu de données : 32 roulements, 2 559 mesures lisibles", 40, 90, 330, 600, "src")
    a = p.box("<b>6 sains</b><br>K001 à K006", 60, 140, 290, 60, "feat")
    b = p.box("<b>12 défauts artificiels</b><br>électroérosion, gravure, perçage<br>KA01…KA09, KI01…KI08",
              60, 230, 290, 80, "ml")
    c = p.box("<b>14 défauts réels</b><br>fatigue (pitting) après vieillissement<br>"
              "accéléré : KA04, KA15, KI04, KB23…", 60, 340, 290, 80, "ops")
    p.text("Chaque roulement : 4 régimes (vitesse, couple, effort radial) x 20 mesures de 4 s.",
           60, 440, 290, 50, 11, "#555555")
    p.group("A. Intra-dataset (Phase 2 publiée)", 420, 90, 520, 280, "ing")
    e1 = p.box("<b>StratifiedGroupKFold 5 folds</b><br>groupe = roulement · tous états confondus",
               440, 130, 480, 60)
    e2 = p.box("Baseline kurtosis : F1 macro <b>0,682 ± 0,158</b> (reproduit à l'identique)<br>"
               "XGBoost vibration : F1 macro <b>0,734 ± 0,206</b><br>"
               "<i>publié : 0,738 ± 0,208 — écart de 0,004, versions de librairies</i>", 440, 220, 480, 80, "white")
    p.text("Intervalles qui se chevauchent : le gain du GBM n'est pas significatif.",
           440, 315, 480, 40, 11, "#555555")
    p.group("B. Artificiel → réel (question centrale)", 420, 400, 520, 290, "ops")
    g1 = p.box("<b>Train</b> : 12 artificiels + 3 sains", 440, 440, 230, 60)
    g2 = p.box("<b>Test</b> : 14 réels + 3 autres sains", 690, 440, 230, 60)
    g3 = p.box("Répété sur les <b>20</b> partitions 3/3 des roulements sains<br>"
               "contrôle : mêmes sains, défauts réels en CV groupée", 440, 530, 480, 60)
    g4 = p.box("Artificiel → réel : F1 macro <b>0,620 ± 0,102</b><br>Contrôle réel → réel : F1 macro <b>0,694 ± 0,107</b>", 440, 610, 480, 60, "white")
    p.group("Garde-fous dans le code", 990, 90, 600, 600, "feat")
    p.box("<b>assert_no_asset_leakage(train, test)</b><br>lève une erreur si un roulement est des deux "
          "côtés (src/data/splits.py, testé)", 1010, 130, 560, 70)
    p.box("<b>Seuils appris sur le train uniquement</b><br>le sens de la règle (kurtosis haute ou basse)"
          " n'est pas supposé", 1010, 220, 560, 70)
    p.box("<b>Moyenne ± écart-type sur les folds</b><br>avec 32 roulements, un chiffre seul serait "
          "trompeur", 1010, 310, 560, 70)
    p.box("<b>Hash du dataset dans MLflow</b><br>chaque métrique est rattachée aux fichiers exacts "
          "utilisés", 1010, 400, 560, 70)
    p.box("<b>Audit « zéro mock » en CI</b><br>aucune valeur inventée affichée dans le dashboard",
          1010, 490, 560, 70)
    p.box("<b>Résultats négatifs publiés</b><br>kurtogramme instable, courant moteur moins bon : "
          "documentés, pas cachés", 1010, 580, 560, 70)
    p.edge(a, e1, "", exit_=R, entry=L)
    p.edge(e1, e2, "", exit_=B, entry=T)
    p.edge(b, g1, "", exit_=R, entry=L)
    p.edge(c, g2, "", exit_=R, entry=T)
    p.edge(g1, g2, "modèle figé", exit_=R, entry=L)
    p.edge(g2, g3, "", exit_=B, entry=(0.75, 0))
    p.edge(g3, g4, "", exit_=B, entry=T)
    return p


def page_serving() -> Page:
    p = Page("p3", "3. Service d'inférence et Kubernetes",
             "<b>API de diagnostic</b> — image sans état, déployable avec Kustomize",
             "Le modèle exporté (JSON XGBoost, quelques centaines de Ko) est embarqué dans l'image : "
             "pas de base, pas de MLflow en production, mise à l'échelle horizontale triviale.", h=800)
    p.group("Construction", 40, 90, 300, 600, "src")
    b1 = p.box("<b>scripts/export_model.py</b><br>CV + réentraînement sur 29<br>roulements, 3 tenus à l'écart",
               60, 130, 260, 80)
    b2 = p.box("<b>models/</b><br>gbm_vibration.json<br>model_card.json · demo_samples.npz",
               60, 240, 260, 80)
    b3 = p.box("<b>Dockerfile.api</b><br>python:3.12-slim, xgboost-cpu<br>utilisateur non root",
               60, 350, 260, 80)
    b4 = p.box("Registre d'images (pull par les pods)<br>ghcr.io/pduclos/mlindustrial-api", 60, 460, 260, 60, dashed=True)
    p.group("Cluster Kubernetes — namespace bearing-diagnosis", 380, 90, 900, 600, "k8s")
    k1 = p.box("<b>Ingress</b> (overlay prod)<br>TLS, corps max 8 Mo", 410, 140, 220, 70)
    k2 = p.box("<b>Service</b> bearing-api<br>ClusterIP (NodePort 30765<br>en overlay local)", 410, 260, 220, 80)
    k3 = p.box("<b>Pod</b> uvicorn<br>/predict · /samples · /model", 720, 140, 230, 70, "ui")
    k4 = p.box("<b>Pod</b> uvicorn", 720, 240, 230, 50, "ui")
    k5 = p.box("<b>Pod</b> uvicorn", 720, 320, 230, 50, "ui")
    k6 = p.box("<b>HPA</b> 3 → 10 réplicas<br>cible CPU 70 %", 1010, 140, 240, 70)
    p.box("<b>PodDisruptionBudget</b><br>minAvailable 1", 1010, 240, 240, 60)
    p.box("<b>NetworkPolicy</b><br>entrée 8765 seulement,<br>aucune sortie", 1010, 330, 240, 70)
    p.box("<b>Sécurité des pods</b> : runAsNonRoot, readOnlyRootFilesystem, capabilities drop ALL, "
          "seccomp RuntimeDefault, pas de token de service account.<br><b>Sondes</b> : readiness et "
          "liveness sur /health.", 410, 440, 840, 70)
    p.box("<b>overlays/local</b> : 1 replica, 1 worker, NodePort &nbsp;·&nbsp; <b>overlays/prod</b> : "
          "3 réplicas + HPA + Ingress TLS + image du registre. Rendu vérifié par "
          "<i>kubectl kustomize</i>.", 410, 540, 840, 70, "white")
    cl = p.box("<b>Client</b><br>superviseur, MES, passerelle<br>IoT (signal 64 kHz)", 1330, 140, 260, 80, "ui")
    p.edge(b1, b2, "", exit_=B, entry=T)
    p.edge(b2, b3, "", exit_=B, entry=T)
    p.edge(b3, b4, "push", exit_=B, entry=T, dashed=True)
    p.edge(cl, k1, "HTTPS JSON", exit_=T, entry=T)
    p.edge(k1, k2, "", exit_=B, entry=T)
    p.edge(k2, k3, "", exit_=R, entry=L)
    p.edge(k2, k4, "", exit_=R, entry=L)
    p.edge(k2, k5, "", exit_=R, entry=L)
    p.edge(k6, k3, "scale", exit_=L, entry=R, dashed=True)
    return p


def page_physics() -> Page:
    p = Page("p4", "4. Du signal aux indicateurs",
             "<b>Physique avant le ML</b> — des indicateurs qu'un responsable maintenance comprend",
             "Le modèle ne voit pas le signal brut : il voit 5 nombres calculés par des formules connues "
             "des vibriciens. Une prédiction se discute devant un chef d'atelier.", h=700)
    s = p.box("<b>Accéléromètre</b><br>64 000 points / s<br>4 s par mesure", 40, 150, 200, 80, "src")
    t1 = p.box("<b>RMS</b><br>énergie vibratoire globale<br>(usure généralisée)", 320, 100, 230, 70, "feat")
    t2 = p.box("<b>Kurtosis</b><br>impulsivité : chocs d'un<br>défaut localisé", 320, 190, 230, 70, "feat")
    t3 = p.box("<b>Facteur de crête, crête à crête,<br>asymétrie</b>", 320, 280, 230, 60, "feat")
    g = p.box("<b>Géométrie 6203</b><br>billes, diametres, angle<br>(fiche constructeur)", 40, 420, 200, 80, "src")
    f = p.box("<b>BPFO / BPFI / BSF / FTF</b><br>fréquence à laquelle une bille<br>"
              "frappe le défaut (Hz)", 320, 420, 230, 80, "feat")
    m = p.box("<b>XGBoost</b><br>5 indicateurs → P(défaut)", 640, 190, 230, 70, "ml")
    bl = p.box("<b>Baseline</b><br>kurtosis ≤ seuil ⇒ défaut", 640, 300, 230, 60, "ml")
    e = p.box("<b>Spectre d'enveloppe</b><br>raie à BPFO = défaut bague<br>extérieure (onglet Spectre)",
              640, 420, 230, 80, "ui")
    out = p.box("<b>Diagnostic</b><br>sain / défaut + indicateurs<br>+ comparaison baseline",
                960, 230, 230, 80, "ui")
    for t in (t1, t2, t3):
        p.edge(s, t, "", exit_=R, entry=L)
    p.edge(g, f, "", exit_=R, entry=L)
    p.edge(t1, m, "", exit_=R, entry=L)
    p.edge(t2, m, "", exit_=R, entry=L)
    p.edge(t3, m, "", exit_=R, entry=L)
    p.edge(t2, bl, "", exit_=R, entry=L, dashed=True)
    p.edge(f, e, "", exit_=R, entry=L)
    p.edge(m, out, "", exit_=R, entry=L)
    p.edge(bl, out, "", exit_=R, entry=L, dashed=True)
    p.text("Constat mesure dans le projet : sur ce banc, la kurtosis est plus BASSE sur les roulements "
           "défectueux (sens appris, non supposé) — voir docs/known_issues.md.", 40, 560, 1150, 40, 11,
           "#666666")
    return p


def main() -> None:
    pages = [page_pipeline(), page_eval(), page_serving(), page_physics()]
    xml = ('<mxfile host="app.diagrams.net" agent="scripts/build_architecture_drawio.py" '
           f'version="24.7.17" type="device" pages="{len(pages)}">\n'
           + "\n".join(pg.xml() for pg in pages) + "\n</mxfile>\n")
    OUT.write_text(xml, encoding="utf-8")
    print(f"-> {OUT} ({len(pages)} pages)")


if __name__ == "__main__":
    main()
