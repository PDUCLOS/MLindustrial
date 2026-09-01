"""Dashboard de suivi maintenance predictive.

Lit uniquement la DB (metadonnees + features deja calculees) et mlflow
(resultats de modeles deja entraines) - aucun calcul lourd ici. Voir
docs/data_model.md pour le schema, docs/known_issues.md pour les limites
connues des features enveloppe, docs/results_phase2.md pour la baseline.
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import mlflow
import pandas as pd
import streamlit as st
from streamlit_flow import streamlit_flow
from streamlit_flow.elements import StreamlitFlowEdge, StreamlitFlowNode
from streamlit_flow.state import StreamlitFlowState

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import re
import textwrap
import uuid
from datetime import datetime

from src.data.db import ApplicationType, Asset, Machine, MaintenanceEvent, Site, Zone, add_machine, get_engine, get_session
from src.models.baseline import apply_threshold
from src.evaluation.temporal_drift import (
    correlation_by_group,
    defect_type_crosstab,
    load_asset_level_series,
    same_day_pairs,
)
from app.tabs.alertes import render as render_alertes
from app.tabs._glossaire import render as render_glossaire, help_text
from app.tabs.factory_twin import render as render_factory_twin
from app.tabs._styles import BOXPLOT_PROPS, DEFECT_ORIGIN_COLOR, PALETTE, style_figure

st.set_page_config(page_title="Maintenance predictive - suivi", layout="wide", page_icon="\U0001F50D")

st.html(
    textwrap.dedent(
        """
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:wght@600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
    :root {
        --accent: #CC785C;
        --accent-soft: rgba(204, 120, 92, 0.12);
        --surface: rgba(255, 255, 255, 0.03);
        --border-soft: rgba(255, 255, 255, 0.08);
        /* Memes valeurs que Palette dans app/tabs/_styles.py (Material Design
           3, variantes 400) - a garder synchronise si l'une des deux change. */
        --color-crit: #EF5350;
        --color-warn: #FFA726;
        --color-ok: #66BB6A;
        --color-info: #CC785C;
    }

    /* Typographie : Inter pour le corps (lisibilite), serif chaleureuse pour
       les titres (registre editorial soigne, pas juste du gras) */
    html, body, [class*="css"] { font-family: "Inter", sans-serif; }
    h1, h2, h3 { font-family: "Source Serif 4", Georgia, serif !important; letter-spacing: -0.01em; }
    h1 { font-weight: 700 !important; }
    h2, h3 { font-weight: 600 !important; }

    /* Onglets : espacement, coins arrondis, etat actif marque par la couleur
       d'accent plutot qu'un simple soulignement fin */
    .stTabs [data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid var(--border-soft); }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        padding: 10px 18px;
        font-weight: 500;
        transition: background-color 0.15s ease;
    }
    .stTabs [data-baseweb="tab"]:hover { background-color: rgba(255, 255, 255, 0.04); }
    .stTabs [aria-selected="true"] {
        background-color: var(--accent-soft);
        border-bottom: 2px solid var(--accent);
        color: var(--accent) !important;
    }

    /* Metriques cle en haut : effet carte avec accent au survol - hierarchie
       visuelle claire entre le chiffre (gros, blanc) et le libelle (petit, attenue) */
    [data-testid="stMetric"] {
        background-color: var(--surface);
        border: 1px solid var(--border-soft);
        border-radius: 12px;
        padding: 16px 18px;
        transition: border-color 0.15s ease;
    }
    [data-testid="stMetric"]:hover { border-color: var(--accent); }
    [data-testid="stMetricLabel"] { font-size: 0.8rem; opacity: 0.7; text-transform: uppercase; letter-spacing: 0.03em; }
    [data-testid="stMetricValue"] { font-family: "Source Serif 4", serif; }

    /* Conteneurs/expanders : cartes coherentes avec les metriques, separation
       visuelle nette entre sections sans avoir besoin de titres partout */
    [data-testid="stExpander"] {
        border-radius: 12px;
        border: 1px solid var(--border-soft);
    }
    div[data-testid="stForm"] {
        border-radius: 12px;
        border: 1px solid var(--border-soft);
        background-color: var(--surface);
        padding: 4px 4px 0 4px;
    }

    /* Boutons primaires (soumission formulaires, palette machine) : accent
       chaud coherent avec le theme plutot que le bleu Streamlit par defaut */
    .stButton button, .stFormSubmitButton button {
        border-radius: 8px;
        border: 1px solid var(--border-soft);
        transition: border-color 0.15s ease, color 0.15s ease;
    }
    .stButton button:hover, .stFormSubmitButton button:hover {
        border-color: var(--accent);
        color: var(--accent);
    }

    /* Alertes (st.info/success/warning/error) : Streamlit les colore par
       defaut en bleu/vert/orange/rouge "web generique", en rupture avec la
       palette chaude du reste du dashboard. Meme logique que les boutons
       ci-dessus - fond sombre uniforme + liseret gauche de la couleur
       semantique (Palette dans app/tabs/_styles.py), pas un bloc colore
       plein qui jure a cote des cartes/onglets terracotta. */
    [data-testid="stAlertContainer"] {
        background-color: var(--surface);
        border: 1px solid var(--border-soft);
        border-radius: 10px;
    }
    [data-testid="stAlertContentInfo"] { border-left: 3px solid var(--color-info); padding-left: 12px; }
    [data-testid="stAlertContentSuccess"] { border-left: 3px solid var(--color-ok); padding-left: 12px; }
    [data-testid="stAlertContentWarning"] { border-left: 3px solid var(--color-warn); padding-left: 12px; }
    [data-testid="stAlertContentError"] { border-left: 3px solid var(--color-crit); padding-left: 12px; }
    </style>
    """
    ),
)

st.title("Suivi maintenance predictive")

engine = get_engine()

with get_session(engine) as session:
    machines = session.query(Machine).all()
    machines_data = [
        {
            "id": m.id,
            "source": m.source,
            "application_type": m.application_type.label if m.application_type else None,
            "iso_reference": m.application_type.iso_reference if m.application_type else None,
            "name": m.name,
        }
        for m in machines
    ]
    assets = session.query(Asset).all()
    asset_ids = [a.id for a in assets]
    assets_df = pd.DataFrame(
        [
            {
                "id": a.id,
                "machine": a.machine_id,
                "type": a.asset_type,
                "code": a.code,
                "health_state": a.health_state,
                "defect_origin": a.bearing_attributes.defect_origin if a.bearing_attributes else None,
                "defect_location": a.bearing_attributes.defect_location if a.bearing_attributes else None,
                "defect_method": a.bearing_attributes.defect_method if a.bearing_attributes else None,
            }
            for a in assets
        ]
    )

if not machines:
    st.warning("Base vide. Lancer `python scripts/init_db.py` pour seeder machines/assets.")
    st.stop()

signal_counts = pd.read_sql("select count(*) as n from signal", engine)
feature_counts = pd.read_sql("select count(*) as n from feature", engine)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Machines", len(machines))
col2.metric("Assets", len(assets_df))
col3.metric("Signaux", int(signal_counts["n"].iloc[0]))
col4.metric("Features calculees", int(feature_counts["n"].iloc[0]))

(tab_factory, tab_assets, tab_features, tab_speed, tab_temporal, tab_alerts,
 tab_maintenance, tab_baseline, tab_glossaire, tab_factory_twin) = st.tabs(
    ["\U0001F3ED Mon usine", "\U0001F527 Equipements", "\U0001F4CA Indicateurs", "\U0001F300 Vitesse",
     "\U0001F4C8 Historique", "\U0001F6A8 Alertes", "\U0001F4DD Journal maintenance", "\U0001F3AF Resultats modeles",
     "\U00002753 Comprendre", "\U0001F3D7\uFE0F Factory Twin"]
)

def _slug(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_") or "item"
    return f"{base}_{uuid.uuid4().hex[:6]}"


with tab_factory:
    st.caption(
        "Modelisez votre propre installation (site -> zone -> machine -> asset). "
        "Cree de vrais enregistrements en base, reutilisables plus tard quand une "
        "source de donnees reelle sera branchee dessus (voir "
        "docs/plan_bearing_catalog_and_ingestion.md Partie B). "
        "Aucune donnee generee : un asset fraichement cree n'a ni signal ni feature, "
        "et c'est affiche explicitement comme tel, pas simule."
    )

    with get_session(engine) as fsession:
        sites = fsession.query(Site).all()
        zones = fsession.query(Zone).all()
        app_types = fsession.query(ApplicationType).all()
        user_machines = fsession.query(Machine).filter(Machine.site_id.isnot(None)).all()
        sites_data = [{"id": s.id, "name": s.name, "location": s.location} for s in sites]
        zones_data = [{"id": z.id, "site_id": z.site_id, "name": z.name} for z in zones]
        app_types_data = {a.code: a.label for a in app_types}
        machines_data_factory = [
            {"id": m.id, "name": m.name, "site_id": m.site_id, "zone_id": m.zone_id,
             "application_type": m.application_type.label if m.application_type else None}
            for m in user_machines
        ]

    col_new1, col_new2, col_new3 = st.columns(3)

    with col_new1:
        st.subheader("Nouveau site")
        with st.form("new_site"):
            site_name = st.text_input("Nom du site")
            site_location = st.text_input("Localisation (optionnel)")
            if st.form_submit_button("Creer le site") and site_name:
                with get_session(engine) as ws:
                    ws.add(Site(id=_slug(site_name), name=site_name, location=site_location or None))
                    ws.commit()
                st.success(f"Site '{site_name}' cree.")
                st.rerun()

    with col_new2:
        st.subheader("Nouvelle zone")
        if not sites_data:
            st.info("Creer un site d'abord.")
        else:
            with st.form("new_zone"):
                zone_site = st.selectbox("Site", [s["id"] for s in sites_data], format_func=lambda i: next(s["name"] for s in sites_data if s["id"] == i))
                zone_name = st.text_input("Nom de la zone")
                if st.form_submit_button("Creer la zone") and zone_name:
                    with get_session(engine) as ws:
                        ws.add(Zone(id=_slug(zone_name), site_id=zone_site, name=zone_name))
                        ws.commit()
                    st.success(f"Zone '{zone_name}' creee.")
                    st.rerun()

    with col_new3:
        st.subheader("Placer une machine")
        if not sites_data:
            st.info("Creer un site d'abord.")
        else:
            st.caption("Choisir le site/zone actif, puis cliquer un type pour le poser.")
            active_site = st.selectbox(
                "Site actif", [s["id"] for s in sites_data],
                format_func=lambda i: next(s["name"] for s in sites_data if s["id"] == i),
                key="active_site",
            )
            zones_for_active = [z for z in zones_data if z["site_id"] == active_site]
            zone_options = [None] + [z["id"] for z in zones_for_active]
            active_zone = st.selectbox(
                "Zone active (optionnel)", zone_options,
                format_func=lambda i: "—" if i is None else next(z["name"] for z in zones_for_active if z["id"] == i),
                key="active_zone",
            )

            # Palette : un bouton par type d'application - clic = placement
            # immediat (nom auto-genere "{Type} N", renommable ensuite), pas
            # de vrai drag-depuis-panneau (streamlit-flow-component ne le
            # supporte pas, verifie le 2026-09-01 - voir docs/scaling_path.md).
            _ICONS = {
                "electric_motor": "⚙️", "centrifugal_pump": "\U0001F4A7",
                "fan_blower": "\U0001F300", "centrifugal_compressor": "\U0001F5DC️",
                "gear_unit": "⚙️⚙️", "bearing_test_rig": "\U0001F52C",
            }
            palette_cols = st.columns(3)
            for idx, (code, label) in enumerate(app_types_data.items()):
                icon = _ICONS.get(code, "\U0001F4E6")
                button_label = f"{icon} {label}"
                with palette_cols[idx % 3]:
                    if st.button(button_label, key=f"place_{code}", width="stretch"):
                        with get_session(engine) as ws:
                            n_existing = ws.query(Machine).filter(Machine.application_type_code == code).count()
                            auto_name = f"{label} {n_existing + 1}"
                            zone_obj = ws.get(Zone, active_zone) if active_zone else None
                            add_machine(
                                ws, _slug(auto_name), zone=zone_obj,
                                site_id=active_site if zone_obj is None else None,
                                source="user_defined", application_type_code=code,
                                name=auto_name,
                            )
                            ws.commit()
                        st.success(f"'{auto_name}' posee sur le canvas.")
                        st.rerun()

    st.subheader("Nouvel asset (capteur/composant surveille)")
    if not machines_data_factory:
        st.info("Creer une machine d'abord.")
    else:
        with st.form("new_factory_asset"):
            asset_machine = st.selectbox(
                "Machine", [m["id"] for m in machines_data_factory],
                format_func=lambda i: next(m["name"] for m in machines_data_factory if m["id"] == i),
            )
            asset_type_input = st.selectbox(
                "Type d'asset", ["bearing", "pump", "compressor", "motor", "fan", "gear_unit", "other"]
            )
            asset_code = st.text_input("Code/reference")
            if st.form_submit_button("Creer l'asset") and asset_code:
                with get_session(engine) as ws:
                    ws.add(Asset(
                        id=_slug(f"{asset_machine}_{asset_code}"),
                        machine_id=asset_machine, asset_type=asset_type_input,
                        code=asset_code, health_state="unknown",
                    ))
                    ws.commit()
                st.success(f"Asset '{asset_code}' cree (etat : unknown, aucun diagnostic encore etabli).")
                st.rerun()

    st.subheader("Hierarchie actuelle (votre usine) — glisser pour reorganiser")
    if not sites_data:
        st.info("Aucun site cree. Utilisez les formulaires ci-dessus pour commencer.")
    else:
        flow_nodes = []
        flow_edges = []
        with get_session(engine) as fsession2:
            x_counters = {0: 0, 1: 0, 2: 0, 3: 0}
            for site in fsession2.query(Site).all():
                sx = x_counters[0] * 260
                x_counters[0] += 1
                flow_nodes.append(StreamlitFlowNode(
                    id=site.id, pos=(sx, 0), data={"content": f"\U0001F3ED {site.name}"},
                    node_type="input", style={"backgroundColor": "#2b3a55", "color": "white"},
                ))
                for zone in site.zones:
                    zx = x_counters[1] * 220
                    x_counters[1] += 1
                    flow_nodes.append(StreamlitFlowNode(
                        id=zone.id, pos=(zx, 150), data={"content": f"\U0001F4CD {zone.name}"},
                        style={"backgroundColor": "#3a4a6b", "color": "white"},
                    ))
                    flow_edges.append(StreamlitFlowEdge(id=f"{site.id}-{zone.id}", source=site.id, target=zone.id))
                    for machine in zone.machines:
                        mx = x_counters[2] * 190
                        x_counters[2] += 1
                        flow_nodes.append(StreamlitFlowNode(
                            id=machine.id, pos=(mx, 300), data={"content": f"⚙️ {machine.name}"},
                            style={"backgroundColor": "#4a5a7b", "color": "white"},
                        ))
                        flow_edges.append(StreamlitFlowEdge(id=f"{zone.id}-{machine.id}", source=zone.id, target=machine.id))
                        for asset in machine.assets:
                            ax = x_counters[3] * 170
                            x_counters[3] += 1
                            has_data = asset.signals and len(asset.signals) > 0
                            icon = "\U0001F7E2" if has_data else "⚪"
                            flow_nodes.append(StreamlitFlowNode(
                                id=asset.id, pos=(ax, 450),
                                data={"content": f"{icon} {asset.code}"},
                                node_type="output",
                                style={"backgroundColor": "#5a6a8b", "color": "white"},
                            ))
                            flow_edges.append(StreamlitFlowEdge(id=f"{machine.id}-{asset.id}", source=machine.id, target=asset.id))
                machines_direct = [m for m in site.machines if m.zone_id is None]
                for machine in machines_direct:
                    mx = x_counters[2] * 190
                    x_counters[2] += 1
                    flow_nodes.append(StreamlitFlowNode(
                        id=machine.id, pos=(mx, 300), data={"content": f"⚙️ {machine.name}"},
                        style={"backgroundColor": "#4a5a7b", "color": "white"},
                    ))
                    flow_edges.append(StreamlitFlowEdge(id=f"{site.id}-{machine.id}", source=site.id, target=machine.id))
                    for asset in machine.assets:
                        ax = x_counters[3] * 170
                        x_counters[3] += 1
                        has_data = asset.signals and len(asset.signals) > 0
                        icon = "\U0001F7E2" if has_data else "⚪"
                        flow_nodes.append(StreamlitFlowNode(
                            id=asset.id, pos=(ax, 450),
                            data={"content": f"{icon} {asset.code}"},
                            node_type="output",
                            style={"backgroundColor": "#5a6a8b", "color": "white"},
                        ))
                        flow_edges.append(StreamlitFlowEdge(id=f"{machine.id}-{asset.id}", source=machine.id, target=asset.id))

        st.caption(
            "\U0001F7E2 = asset avec au moins un signal reel en base. "
            "⚪ = asset cree, aucune donnee (etat honnete, pas un placeholder simule)."
        )
        flow_state = StreamlitFlowState(flow_nodes, flow_edges)
        streamlit_flow("factory_flow", flow_state, fit_view=True, height=500)

with tab_assets:
    st.subheader("Machines")
    st.dataframe(pd.DataFrame(machines_data), width="stretch")

    st.subheader("Assets")
    machine_filter = st.multiselect("Machine", sorted(assets_df["machine"].unique()))
    health_filter = st.multiselect("Etat", sorted(assets_df["health_state"].unique()))
    filtered = assets_df.copy()
    if machine_filter:
        filtered = filtered[filtered["machine"].isin(machine_filter)]
    if health_filter:
        filtered = filtered[filtered["health_state"].isin(health_filter)]
    st.dataframe(filtered, width="stretch")

with tab_features:
    st.caption(
        "Indicateurs temporels (canal vibration) par etat de sante. "
        "Voir docs/known_issues.md : sur ce dataset, sain > faulty pour ces "
        "3 features - contre-intuitif, verifie et documente, pas un bug."
    )
    feat_df = pd.read_sql(
        """
        select a.health_state, f.feature_name, f.value, f.unit
        from feature f join asset a on a.id = f.asset_id
        where f.channel = 'vibration'
          and f.feature_name in ('rms', 'kurtosis', 'crest_factor')
        """,
        engine,
    )
    if feat_df.empty:
        st.info("Aucune feature en base. Lancer scripts/build_dataset.py.")
    else:
        st.caption(
            "Unite : rms en g (acceleration brute, capteur PCB 336C04 - PAS en "
            "mm/s, voir docs/known_issues.md 'Unites capteurs Paderborn'). "
            "kurtosis et crest_factor sont des ratios sans dimension."
        )
        fig, axes = plt.subplots(1, 3, figsize=(14, 4))
        for ax, name in zip(axes, ["rms", "kurtosis", "crest_factor"]):
            subset = feat_df[feat_df["feature_name"] == name]
            unit = subset["unit"].dropna().iloc[0] if subset["unit"].notna().any() else None
            subset.boxplot(column="value", by="health_state", ax=ax, **BOXPLOT_PROPS)
            ax.set_title(f"{name} ({unit})" if unit else name)
            ax.set_xlabel("")
        plt.suptitle("")
        style_figure(fig, *axes)
        st.pyplot(fig)

with tab_speed:
    st.caption(
        "Vitesse reelle mesuree (canal tachymetrique 'speed', Paderborn) par mesure. "
        "is_variable_speed = coefficient de variation > 1% sur la duree de la mesure "
        "(voir src/features/speed.py). Pour les sources sans canal vitesse dedie "
        "(ex. XJTU-SY), seule la vitesse nominale de config (test_session) existe - "
        "pas de detection automatique possible, saisie manuelle a prevoir le cas echeant."
    )
    speed_df = pd.read_sql(
        """
        select a.code, a.machine_id, f.feature_name, f.value
        from feature f join asset a on a.id = f.asset_id
        where f.channel = 'speed'
        """,
        engine,
    )
    if speed_df.empty:
        st.info("Aucune feature de vitesse en base.")
    else:
        wide_speed = speed_df.pivot_table(
            index=["code", "machine_id"], columns="feature_name", values="value", aggfunc="mean"
        ).reset_index()
        n_variable = int((speed_df[speed_df["feature_name"] == "is_variable_speed"]["value"] > 0).sum())
        col_a, col_b = st.columns(2)
        col_a.metric("Mesures a vitesse variable detectee", n_variable)
        col_b.metric("Mesures totales avec canal vitesse", int(speed_df["code"].count() / 3))
        st.dataframe(wide_speed, width="stretch")

with tab_alerts:
    render_alertes(engine)

with tab_maintenance:
    st.caption(
        "Journal d'evenements par asset (defaut signale, remplacement de roulement, "
        "remplacement/deplacement de capteur, modification systeme...), horodate pour "
        "correlation avec la derive des features (onglet 'Derive temporelle')."
    )

    with st.form("new_maintenance_event"):
        ev_asset = st.selectbox("Asset", sorted(asset_ids))
        ev_type = st.selectbox(
            "Type d'evenement",
            ["fault_detected", "bearing_replacement", "sensor_replacement", "sensor_relocation", "system_modification", "other"],
        )
        ev_date = st.date_input("Date")
        ev_time = st.time_input("Heure")
        ev_desc = st.text_area("Description")
        ev_by = st.text_input("Rapporte par")
        submitted = st.form_submit_button("Enregistrer")
        if submitted:
            with get_session(engine) as write_session:
                write_session.add(
                    MaintenanceEvent(
                        asset_id=ev_asset,
                        timestamp=datetime.combine(ev_date, ev_time),
                        event_type=ev_type,
                        description=ev_desc or None,
                        reported_by=ev_by or None,
                    )
                )
                write_session.commit()
            st.success("Evenement enregistre.")
            st.rerun()

    events_df = pd.read_sql(
        "select asset_id, timestamp, event_type, description, reported_by "
        "from maintenance_event order by timestamp desc",
        engine,
    )
    if events_df.empty:
        st.info("Aucun evenement enregistre.")
    else:
        st.dataframe(events_df, width="stretch")

with tab_temporal:
    st.caption(
        "Chaque asset Paderborn est teste sur UN SEUL jour calendaire : "
        "asset_id, date d'essai et defect_origin sont largement confondus "
        "(real = juin-aout 2014 pour l'essentiel, healthy = mars-oct 2015 "
        "uniquement). Un boxplot par health_state ne peut pas separer un "
        "effet defaut d'un effet date/banc - voir docs/known_issues.md."
    )
    feature_choice = st.selectbox(
        "Feature", ["kurtosis", "rms", "crest_factor"], index=0,
        help=help_text("kurtosis"),
    )
    ts_df = load_asset_level_series(engine, feature_choice, channel="vibration")

    if ts_df.empty:
        st.info("Aucune feature en base. Lancer scripts/build_dataset.py.")
    else:
        st.subheader("Valeur moyenne par asset, dans l'ordre chronologique reel")
        fig, ax = plt.subplots(figsize=(10, 4))
        for origin, sub in ts_df.groupby("defect_origin"):
            ax.scatter(
                sub["test_date"], sub["mean_value"],
                label=origin, color=DEFECT_ORIGIN_COLOR.get(origin, PALETTE.neutral), s=40,
            )
        ax.set_xlabel("Date d'essai reelle")
        ax.set_ylabel(feature_choice)
        ax.legend(title="defect_origin")
        fig.autofmt_xdate()
        style_figure(fig, ax)
        st.pyplot(fig)

        st.subheader("Correlation (valeur moyenne asset vs date d'essai), par groupe")
        st.caption("n petit (6-14 assets par groupe) - indicatif, pas une preuve statistique.")
        st.dataframe(correlation_by_group(ts_df, "defect_origin"), width="stretch")

        st.subheader("Paires d'assets testes le meme jour")
        st.caption(
            "Seul levier du dataset pour separer 'effet jour d'essai' de "
            "'effet roulement individuel' : si deux assets du meme jour et du "
            "meme defaut divergent autant que deux assets de jours differents, "
            "la variance inter-roulement domine sur la derive temporelle."
        )
        pairs_df = same_day_pairs(ts_df)
        if pairs_df.empty:
            st.info("Aucune paire (feature pas encore alignee avec un jour partage).")
        else:
            st.dataframe(
                pairs_df.sort_values("ratio", ascending=False), width="stretch"
            )

        st.subheader("Repartition defect_origin x defect_method x defect_location")
        st.caption(
            "defect_method determine quasiment defect_origin sur Paderborn "
            "(real = fatigue_pitting/plastic_deform, artificial = "
            "drilling/edm/engraving) - la generalisation artificiel->reel "
            "(Phase 3) teste peut-etre 'endommagement net -> usure diffuse' "
            "autant que 'artificiel -> reel'."
        )
        st.dataframe(defect_type_crosstab(ts_df), width="stretch")

with tab_baseline:
    st.caption(
        "Validation croisee StratifiedGroupKFold (5 folds, groupe=asset_id) - "
        "moyenne +/- ecart-type, pas un split unique (voir docs/results_phase2.md : "
        "un split unique donnait un classement different a chaque seed teste)."
    )

    def show_experiment(exp_name: str, rename: dict) -> None:
        exp = mlflow.get_experiment_by_name(exp_name)
        if exp is None:
            st.info(f"Aucun run pour '{exp_name}'.")
            return
        runs = mlflow.search_runs(experiment_ids=[exp.experiment_id])
        cols = list(rename.keys())
        display_df = runs[[c for c in cols if c in runs.columns]].rename(columns=rename)
        st.dataframe(display_df, width="stretch")

    try:
        mlflow.set_tracking_uri("http://mlflow:5000")

        st.subheader("Baseline seuil (temporel, canal vibration)")
        show_experiment(
            "baseline_threshold_cv",
            {
                "tags.mlflow.runName": "run",
                "params.feature": "feature",
                "metrics.f1_macro_mean": "F1 macro (moy. CV)",
                "metrics.f1_macro_std": "ecart-type",
            },
        )

        st.subheader("Gradient boosting - vibration vs courant vs fusion")
        show_experiment(
            "gbm_sensor_comparison_cv",
            {
                "tags.mlflow.runName": "run",
                "params.sensor_set": "sensor_set",
                "params.n_features": "n_features",
                "metrics.f1_macro_mean": "F1 macro (moy. CV)",
                "metrics.f1_macro_std": "ecart-type",
            },
        )
    except Exception as e:
        st.warning(f"mlflow indisponible : {e}")

with tab_glossaire:
    render_glossaire()

with tab_factory_twin:
    render_factory_twin()
