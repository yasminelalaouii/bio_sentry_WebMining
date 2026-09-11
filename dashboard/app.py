"""
Bio-Sentry Dashboard
Axe 3 : Web Structure Mining (HITS + PageRank + Degree Centrality)
Axe 4 : Usage Mining (Anomalies Temporelles + Clustering)
ENSA Tetouan | Analyse de Web M242 | 2025-2026
"""

import json, os
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from PIL import Image

# ── Chemins ───────────────────────────────────────────────────────────────────
ROOT      = os.path.dirname(os.path.abspath(__file__))
ALERT_DIR = os.path.join(ROOT, "..", "alert")
AXE3_JSON = os.path.join(ROOT, "..", "axe3_graph_mining", "axe3_hits_results.json")

def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def load_img(filename):
    p = os.path.join(ALERT_DIR, filename)
    return Image.open(p) if os.path.exists(p) else None

# ── Configuration page ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Bio-Sentry | Pharmacovigilance Dashboard",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS professionnel ─────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Fond général */
    .main { background-color: #F4F6F9; }

    /* Barre latérale */
    section[data-testid="stSidebar"] {
        background-color: #1A2B4A;
    }
    section[data-testid="stSidebar"] * {
        color: #D0D9EC !important;
    }
    section[data-testid="stSidebar"] .stRadio label {
        color: #D0D9EC !important;
        font-size: 0.92rem;
    }

    /* Titre principal */
    .main-title {
        font-size: 1.9rem;
        font-weight: 700;
        color: #1A2B4A;
        letter-spacing: -0.02em;
        margin-bottom: 2px;
    }
    .main-subtitle {
        font-size: 0.92rem;
        color: #6B7280;
        margin-bottom: 1.4rem;
    }

    /* KPI cards */
    .kpi-card {
        background: #FFFFFF;
        border-radius: 8px;
        padding: 1.1rem 1.3rem;
        box-shadow: 0 1px 4px rgba(0,0,0,0.07);
        border-left: 4px solid #2563EB;
        margin-bottom: 0.8rem;
    }
    .kpi-card.red   { border-left-color: #DC2626; }
    .kpi-card.green { border-left-color: #16A34A; }
    .kpi-card.amber { border-left-color: #D97706; }

    .kpi-value {
        font-size: 1.75rem;
        font-weight: 700;
        color: #111827;
        line-height: 1.1;
    }
    .kpi-label {
        font-size: 0.75rem;
        color: #9CA3AF;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-bottom: 4px;
    }
    .kpi-sub {
        font-size: 0.78rem;
        color: #6B7280;
        margin-top: 2px;
    }

    /* Bandeaux d'alerte */
    .alert-critical {
        background: #FEF2F2;
        border-left: 4px solid #DC2626;
        border-radius: 6px;
        padding: 0.85rem 1rem;
        color: #7F1D1D;
        font-size: 0.88rem;
        margin-bottom: 0.5rem;
    }
    .alert-warning {
        background: #FFFBEB;
        border-left: 4px solid #D97706;
        border-radius: 6px;
        padding: 0.85rem 1rem;
        color: #78350F;
        font-size: 0.88rem;
        margin-bottom: 0.5rem;
    }
    .alert-ok {
        background: #F0FDF4;
        border-left: 4px solid #16A34A;
        border-radius: 6px;
        padding: 0.85rem 1rem;
        color: #14532D;
        font-size: 0.88rem;
        margin-bottom: 0.5rem;
    }

    /* En-têtes de section */
    .section-header {
        font-size: 1.05rem;
        font-weight: 600;
        color: #1A2B4A;
        border-bottom: 2px solid #2563EB;
        padding-bottom: 4px;
        margin: 1.2rem 0 0.8rem 0;
    }

    /* Séparateur */
    hr { border-color: #E5E7EB; margin: 1rem 0; }

    /* Supprimer padding inutile */
    .block-container { padding-top: 1.5rem; }
</style>
""", unsafe_allow_html=True)

# ── Chargement donnees ────────────────────────────────────────────────────────
@st.cache_data
def get_data():
    axe3      = load_json(AXE3_JSON)
    stats     = load_json(os.path.join(ALERT_DIR, "dashboard_stats.json"))
    synthese  = load_json(os.path.join(ALERT_DIR, "synthese_partie_a.json"))
    consensus = load_json(os.path.join(ALERT_DIR, "anomalies_consensus.json"))
    zscore    = load_json(os.path.join(ALERT_DIR, "anomalies_zscore.json"))
    ma        = load_json(os.path.join(ALERT_DIR, "anomalies_moving_average.json"))
    iso       = load_json(os.path.join(ALERT_DIR, "anomalies_isolation_forest.json"))
    hourly    = load_json(os.path.join(ALERT_DIR, "hourly_activity.json"))
    heatmaps  = load_json(os.path.join(ALERT_DIR, "heatmaps.json"))
    return axe3, stats, synthese, consensus, zscore, ma, iso, hourly, heatmaps

axe3, stats, synthese, consensus, zscore_data, ma_data, iso_data, hourly, heatmaps = get_data()

df_consensus = pd.DataFrame(consensus["data"])
df_zscore    = pd.DataFrame(zscore_data["data"])
df_ma        = pd.DataFrame(ma_data["data"])
df_iso       = pd.DataFrame(iso_data["data"])
df_hourly    = pd.DataFrame(hourly)
df_sources   = pd.DataFrame(axe3["source_summary"])
df_auth      = pd.DataFrame(axe3["top_authorities"])
df_hubs      = pd.DataFrame(axe3["top_hubs"])

# Palette couleurs sources
SRC_COLOR = {
    "openfda":     "#1D4ED8",
    "webmd":       "#15803D",
    "reddit":      "#B91C1C",
    "arctic_shift":"#C2410C",
    "drugs_forum": "#7C3AED",
    "reddit_rss":  "#BE185D",
    "reddit_api":  "#BE185D",   # même source, nommée différemment selon le pipeline
}

CHART_THEME = dict(
    plot_bgcolor="white",
    paper_bgcolor="white",
    font=dict(family="Inter, Arial, sans-serif", size=12, color="#374151"),
    margin=dict(t=30, b=40, l=10, r=10),
)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Bio-Sentry")
    st.markdown("Pharmacovigilance & Veille Epidemiologique")
    st.markdown("---")
    page = st.radio(
        "Navigation",
        [
            "Vue d'ensemble",
            "Axe 3 — Structure Mining",
            "Axe 4 — Anomalies Temporelles",
            "Axe 4 — Clustering Usage",
            "Synthese & Comparaison",
        ],
        label_visibility="collapsed",
    )
    st.markdown("---")
    st.markdown("**Sources de donnees**")
    st.markdown("Authority : OpenFDA, WebMD")
    st.markdown("Hub : Reddit, Arctic Shift, Drugs Forum")
    st.markdown("---")
    st.markdown("ENSA Tetouan — M242 — 2025-2026")


# ════════════════════════════════════════════════════════════════════════════
#  PAGE 1 — VUE D'ENSEMBLE
# ════════════════════════════════════════════════════════════════════════════
if page == "Vue d'ensemble":

    st.markdown('<p class="main-title">Bio-Sentry — Pharmacovigilance Dashboard</p>',
                unsafe_allow_html=True)
    st.markdown('<p class="main-subtitle">Systeme de detection precoce des effets secondaires medicamenteux | ENSA Tetouan | Analyse de Web M242</p>',
                unsafe_allow_html=True)
    st.markdown("---")

    # KPIs
    c1, c2, c3, c4, c5 = st.columns(5)
    kpis = [
        (c1, "Documents analyses", f"{synthese['dataset']['total_documents']:,}", "", ""),
        (c2, "Aretes dans le graphe", f"{axe3['graph']['edges']:,}", "", ""),
        (c3, "Medicaments distincts", f"{synthese['dataset']['distinct_drugs']:,}", "", ""),
        (c4, "Anomalie consensus", f"{synthese['anomalies']['consensus_2of3']}", "detectee a H17:00", "red"),
        (c5, "Heure de pic", f"H{synthese['dataset']['peak_hour']}:00", f"{synthese['dataset']['peak_posts']:,} posts", "amber"),
    ]
    for col, label, val, sub, color in kpis:
        col.markdown(f"""
        <div class="kpi-card {color}">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{val}</div>
            <div class="kpi-sub">{sub}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("---")
    col_a, col_b = st.columns([1.4, 1])

    # Timeline globale
    with col_a:
        st.markdown('<div class="section-header">Activite horaire globale</div>',
                    unsafe_allow_html=True)
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df_hourly["hour"], y=df_hourly["nb_posts"],
            name="Nombre de posts",
            marker_color="#93C5FD", marker_line_color="#2563EB",
            marker_line_width=0.5,
        ))
        anom = df_consensus[df_consensus["anomaly_2of3"]]
        fig.add_trace(go.Scatter(
            x=anom["hour"],
            y=df_hourly[df_hourly["hour"].isin(anom["hour"].values)]["nb_posts"],
            mode="markers", name="Anomalie consensus",
            marker=dict(color="#DC2626", size=13, symbol="diamond"),
        ))
        fig.update_layout(
            xaxis=dict(title="Heure", dtick=1),
            yaxis_title="Posts",
            height=310, legend=dict(orientation="h", y=1.12),
            **CHART_THEME,
        )
        st.plotly_chart(fig, use_container_width=True)

    # Top medicaments
    with col_b:
        st.markdown('<div class="section-header">Top 10 medicaments mentionnes</div>',
                    unsafe_allow_html=True)
        df_drugs = pd.DataFrame(synthese["top_drugs"])
        df_drugs.columns = ["Medicament", "Mentions"]
        fig2 = px.bar(df_drugs, x="Mentions", y="Medicament", orientation="h",
                      color_discrete_sequence=["#1D4ED8"], height=310)
        fig2.update_layout(showlegend=False, **CHART_THEME)
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")
    col_c, col_d = st.columns(2)

    # Fiabilite sources
    with col_c:
        st.markdown('<div class="section-header">Score de fiabilite par source (Score composite)</div>',
                    unsafe_allow_html=True)
        df_src = df_sources.sort_values("composite_avg", ascending=True)
        bar_colors = [SRC_COLOR.get(s, "#9CA3AF") for s in df_src["source"]]
        fig3 = go.Figure(go.Bar(
            x=df_src["composite_avg"], y=df_src["source"],
            orientation="h", marker_color=bar_colors,
            text=[f"{v:.4f}" for v in df_src["composite_avg"]],
            textposition="outside",
        ))
        fig3.update_layout(xaxis_title="Score composite", height=260, **CHART_THEME)
        st.plotly_chart(fig3, use_container_width=True)

    # Distribution par jour
    with col_d:
        st.markdown('<div class="section-header">Distribution par jour de la semaine</div>',
                    unsafe_allow_html=True)
        jours = {1: "Lundi", 2: "Mardi", 3: "Mercredi"}
        dow = stats["dayofweek_distribution"]
        df_dow = pd.DataFrame({
            "Jour":  [jours.get(int(k), k) for k in dow],
            "Posts": list(dow.values()),
        })
        fig4 = px.pie(df_dow, values="Posts", names="Jour",
                      color_discrete_sequence=["#1D4ED8", "#2563EB", "#93C5FD"],
                      height=260)
        fig4.update_layout(margin=dict(t=10, b=10), paper_bgcolor="white")
        fig4.update_traces(textinfo="label+percent")
        st.plotly_chart(fig4, use_container_width=True)

    st.markdown("---")
    st.markdown('<div class="section-header">Etat des alertes actives</div>',
                unsafe_allow_html=True)
    col_e, col_f, col_g = st.columns(3)
    with col_e:
        st.markdown("""<div class="alert-critical">
        <strong>Anomalie critique — H17:00</strong><br>
        6 066 posts (Z-score = 4.20 — seuil 2.0)<br>
        Detectee par 2 methodes sur 3 (Z-score + Isolation Forest)<br>
        Represents 32.1% de l'activite journaliere totale
        </div>""", unsafe_allow_html=True)
    with col_f:
        st.markdown("""<div class="alert-warning">
        <strong>Pic d'activite inhabituel</strong><br>
        Medicaments concernes : Trazodone, Sertraline<br>
        Ecart par rapport a la moyenne : +672%<br>
        Verifier les signalements FDA correspondants
        </div>""", unsafe_allow_html=True)
    with col_g:
        st.markdown("""<div class="alert-ok">
        <strong>Sources certifiees — Operationnelles</strong><br>
        OpenFDA : score authority 0.0863 (rang 1)<br>
        WebMD : score authority 0.0530 (rang 2)<br>
        Graphe : 24 444 noeuds, 2 501 423 aretes
        </div>""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
#  PAGE 2 — AXE 3 STRUCTURE MINING
# ════════════════════════════════════════════════════════════════════════════
elif page == "Axe 3 — Structure Mining":
    st.markdown('<p class="main-title">Axe 3 — Web Structure Mining</p>', unsafe_allow_html=True)
    st.markdown('<p class="main-subtitle">HITS · PageRank · Degree Centrality — Cartographie de la fiabilite des sources</p>', unsafe_allow_html=True)
    st.markdown("---")

    c1, c2, c3 = st.columns(3)
    c1.markdown("""<div class="kpi-card"><div class="kpi-label">Noeuds dans le graphe</div>
    <div class="kpi-value">24 444</div></div>""", unsafe_allow_html=True)
    c2.markdown("""<div class="kpi-card"><div class="kpi-label">Aretes (co-mentions)</div>
    <div class="kpi-value">2 501 423</div></div>""", unsafe_allow_html=True)
    c3.markdown("""<div class="kpi-card"><div class="kpi-label">Algorithmes compares</div>
    <div class="kpi-value">3</div><div class="kpi-sub">HITS · PageRank · Degree Centrality</div></div>""", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown('<div class="section-header">Comparaison des 3 algorithmes par source</div>',
                unsafe_allow_html=True)

    df_src = df_sources.copy()
    fig = go.Figure()
    fig.add_trace(go.Bar(name="HITS Authority", x=df_src["source"],
                         y=df_src["hits_auth_avg"], marker_color="#1D4ED8"))
    fig.add_trace(go.Bar(name="PageRank",       x=df_src["source"],
                         y=df_src["pagerank_avg"], marker_color="#3B82F6"))
    fig.add_trace(go.Bar(name="Degree Centrality", x=df_src["source"],
                         y=df_src["degree_in_avg"], marker_color="#93C5FD"))
    fig.update_layout(barmode="group", xaxis_title="Source",
                      yaxis_title="Score moyen", height=340,
                      legend=dict(orientation="h", y=1.1), **CHART_THEME)
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Les 3 algorithmes convergent : OpenFDA > WebMD > sources sociales. "
               "Reddit et Forums ont un score authority proche de 0 : ce sont des Hubs, pas des Authorities.")

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="section-header">Classement des sources par fiabilite</div>',
                    unsafe_allow_html=True)
        df_sorted = df_src.sort_values("composite_avg", ascending=True)
        colors = [SRC_COLOR.get(s, "#9CA3AF") for s in df_sorted["source"]]
        fig2 = go.Figure(go.Bar(
            x=df_sorted["composite_avg"], y=df_sorted["source"],
            orientation="h", marker_color=colors,
            text=[f"{v:.4f}" for v in df_sorted["composite_avg"]],
            textposition="outside",
        ))
        fig2.update_layout(xaxis_title="Score composite (HITS + PageRank + Degree) / 3",
                           height=290, **CHART_THEME)
        st.plotly_chart(fig2, use_container_width=True)
        st.caption("OpenFDA = 1.6x plus fiable que WebMD, 3x plus fiable que Reddit.")

    with col2:
        st.markdown('<div class="section-header">Positionnement Hub vs Authority (HITS)</div>',
                    unsafe_allow_html=True)
        fig3 = go.Figure()
        for _, row in df_src.iterrows():
            fig3.add_trace(go.Scatter(
                x=[row["hits_auth_avg"] * 10000],
                y=[row["composite_avg"]],
                mode="markers+text",
                name=row["source"],
                text=[row["source"]],
                textposition="top center",
                marker=dict(
                    size=max(10, row["doc_count"] / 200),
                    color=SRC_COLOR.get(row["source"], "#9CA3AF"),
                    line=dict(width=1.5, color="white"),
                ),
            ))
        fig3.update_layout(
            xaxis_title="HITS Authority (x10 000)",
            yaxis_title="Score composite",
            height=290, showlegend=False, **CHART_THEME,
        )
        st.plotly_chart(fig3, use_container_width=True)

    st.markdown("---")
    st.markdown('<div class="section-header">Top Authorities — Sources les plus fiables</div>',
                unsafe_allow_html=True)
    n_auth = st.slider("Nombre de documents a afficher", 5, 20, 10, label_visibility="visible")
    df_a = df_auth.head(n_auth)[["id","source","hits_authority","composite_authority","n_drugs"]].copy()
    df_a.columns = ["ID Document","Source","HITS Authority","Score Composite","Nb Medicaments"]
    df_a["HITS Authority"]   = df_a["HITS Authority"].map("{:.6f}".format)
    df_a["Score Composite"]  = df_a["Score Composite"].map("{:.4f}".format)
    st.dataframe(df_a, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown('<div class="section-header">Top Hubs — Meilleurs agregateurs de l\'information</div>',
                unsafe_allow_html=True)
    df_h_uniq = df_hubs.drop_duplicates(subset="hits_hub").head(10)
    col_h1, col_h2 = st.columns([1.2, 1])
    with col_h1:
        df_h = df_h_uniq[["id","source","hits_hub","n_drugs"]].copy()
        df_h.columns = ["ID Document","Source","Hub Score","Nb Medicaments"]
        df_h["Hub Score"] = df_h["Hub Score"].map("{:.6f}".format)
        st.dataframe(df_h, use_container_width=True, hide_index=True)
    with col_h2:
        fig_hub = go.Figure(go.Bar(
            x=df_h_uniq["hits_hub"], y=df_h_uniq["id"].str[:15],
            orientation="h", marker_color="#B91C1C",
            text=[f"{v:.5f}" for v in df_h_uniq["hits_hub"]],
            textposition="outside",
        ))
        fig_hub.update_layout(xaxis_title="Hub Score", height=280, **CHART_THEME)
        st.plotly_chart(fig_hub, use_container_width=True)

    st.markdown("---")
    st.markdown('<div class="section-header">Graphe de co-mentions (top 120 noeuds)</div>',
                unsafe_allow_html=True)
    axe3_graph_path = os.path.join(ROOT, "..", "axe3_graph_mining", "axe3_G7_graph.png")
    if os.path.exists(axe3_graph_path):
        st.image(Image.open(axe3_graph_path),
                 caption="Graphe HITS — Bleu/Vert : FDA/WebMD (cluster central). Rouge : Reddit (peripherie). Taille du noeud proportionnelle au score HITS.",
                 use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════
#  PAGE 3 — AXE 4 ANOMALIES TEMPORELLES
# ════════════════════════════════════════════════════════════════════════════
elif page == "Axe 4 — Anomalies Temporelles":
    st.markdown('<p class="main-title">Axe 4 — Anomalies Temporelles</p>', unsafe_allow_html=True)
    st.markdown('<p class="main-subtitle">Z-score · Moving Average · Isolation Forest — Detection d\'anomalies dans les flux temporels horaires</p>', unsafe_allow_html=True)
    st.markdown("---")

    c1, c2, c3, c4 = st.columns(4)
    cards = [
        (c1, "Z-score", f"{synthese['anomalies']['zscore_count']} anomalie", "Seuil Z = 2.0", ""),
        (c2, "Moving Average", f"{synthese['anomalies']['ma_count']} anomalie", "Fenetre = 3h, seuil 1.5σ", "green"),
        (c3, "Isolation Forest", f"{synthese['anomalies']['if_count']} anomalies", "contamination = 0.15", ""),
        (c4, "Consensus (2/3)", f"{synthese['anomalies']['consensus_2of3']} anomalie critique", "H17 — Z=4.20", "red"),
    ]
    for col, label, val, sub, color in cards:
        col.markdown(f"""<div class="kpi-card {color}">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{val}</div>
        <div class="kpi-sub">{sub}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("---")
    methode = st.selectbox(
        "Methode de detection a visualiser :",
        ["Toutes les methodes (vue consensus)",
         "Z-score uniquement",
         "Moving Average uniquement",
         "Isolation Forest uniquement"],
    )

    st.markdown('<div class="section-header">Timeline horaire — Detection d\'anomalies</div>',
                unsafe_allow_html=True)
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_hourly["hour"], y=df_hourly["nb_posts"],
        name="Nombre de posts",
        marker_color="#BFDBFE", marker_line_color="#3B82F6", marker_line_width=0.8,
    ))

    if "Z-score" in methode or "Toutes" in methode:
        z_upper = zscore_data["upper_bound"]
        fig.add_hline(y=z_upper, line_dash="dot", line_color="#1D4ED8",
                      annotation_text=f"Seuil Z-score ({z_upper:.0f} posts)",
                      annotation_position="top right",
                      annotation_font=dict(size=11))
        anom_z = df_zscore[df_zscore["anomaly_zscore"]]
        nh_z = df_hourly[df_hourly["hour"].isin(anom_z["hour"].values)]
        fig.add_trace(go.Scatter(
            x=nh_z["hour"], y=nh_z["nb_posts"],
            mode="markers", name="Anomalie Z-score",
            marker=dict(color="#1D4ED8", size=13, symbol="diamond",
                        line=dict(color="white", width=1)),
        ))

    if "Moving Average" in methode or "Toutes" in methode:
        fig.add_trace(go.Scatter(
            x=df_ma["hour"], y=df_ma["rolling_mean"],
            mode="lines", name="Moyenne glissante (MA)",
            line=dict(color="#16A34A", width=2),
        ))
        fig.add_trace(go.Scatter(
            x=df_ma["hour"].tolist() + df_ma["hour"].tolist()[::-1],
            y=df_ma["upper_band"].tolist() + df_ma["lower_band"].tolist()[::-1],
            fill="toself", fillcolor="rgba(22,163,74,0.08)",
            line=dict(color="rgba(0,0,0,0)"),
            name="Bande Moving Average",
        ))

    if "Isolation Forest" in methode or "Toutes" in methode:
        anom_if = df_iso[df_iso["anomaly_if"]]
        nh_if = df_hourly[df_hourly["hour"].isin(anom_if["hour"].values)]
        fig.add_trace(go.Scatter(
            x=nh_if["hour"], y=nh_if["nb_posts"],
            mode="markers", name="Anomalie Isolation Forest",
            marker=dict(color="#DC2626", size=11, symbol="x",
                        line=dict(color="#DC2626", width=2)),
        ))

    if "Toutes" in methode:
        anom_c = df_consensus[df_consensus["anomaly_2of3"]]
        for _, row in anom_c.iterrows():
            fig.add_vrect(
                x0=row["hour"] - 0.45, x1=row["hour"] + 0.45,
                fillcolor="rgba(220,38,38,0.1)", line_width=0,
                annotation_text="Anomalie consensus",
                annotation_position="top left",
                annotation_font=dict(size=10, color="#DC2626"),
            )

    fig.update_layout(
        xaxis=dict(title="Heure de la journee", dtick=1),
        yaxis_title="Nombre de posts",
        height=400, legend=dict(orientation="h", y=1.1), **CHART_THEME,
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    st.markdown('<div class="section-header">Analyse de l\'anomalie critique — H17:00</div>',
                unsafe_allow_html=True)
    col_a, col_b = st.columns([1, 1.6])

    with col_a:
        st.markdown("""<div class="alert-critical">
        <strong>Anomalie confirmee — Heure 17h</strong><br><br>
        Volume observe : 6 066 posts<br>
        Moyenne journaliere : 786 posts/heure<br>
        Ecart : +5 280 posts (+672%)<br>
        Z-score : 4.20 (seuil critique = 2.0)<br><br>
        Detectee par : Z-score + Isolation Forest<br>
        Statut consensus : confirme (2/3 methodes)
        </div>""", unsafe_allow_html=True)
        st.markdown("""<div class="alert-warning" style="margin-top:8px">
        <strong>Interpretation pharmacovigilance</strong><br><br>
        Pic en fin d'apres-midi coherent avec une prise
        medicamenteuse matinale et apparition d'effets secondaires
        quelques heures apres. A croiser avec les medicaments
        mentionnes specifiquement a H17 dans la base.
        </div>""", unsafe_allow_html=True)

    with col_b:
        fig_z = go.Figure()
        colors_z = [
            "#DC2626" if row["anomaly_zscore"] else
            "#F97316" if abs(row["zscore"]) > 1.5 else "#93C5FD"
            for _, row in df_zscore.iterrows()
        ]
        fig_z.add_trace(go.Bar(
            x=df_zscore["hour"], y=df_zscore["zscore"],
            marker_color=colors_z, name="Z-score",
        ))
        fig_z.add_hline(y=2.0, line_dash="dash", line_color="#DC2626",
                        annotation_text="Seuil +2.0 (critique)",
                        annotation_font=dict(color="#DC2626", size=10))
        fig_z.add_hline(y=-2.0, line_dash="dash", line_color="#DC2626")
        fig_z.update_layout(
            title="Z-score par heure — toutes heures",
            xaxis=dict(title="Heure", dtick=1),
            yaxis_title="Z-score",
            height=300, **CHART_THEME,
        )
        st.plotly_chart(fig_z, use_container_width=True)

    st.markdown("---")
    st.markdown('<div class="section-header">Heatmap — Activite par source et par heure</div>',
                unsafe_allow_html=True)
    hm = heatmaps["heatmap_source_hour"]
    matrix = np.array([s["values"] for s in hm["data"]])
    fig_hm = px.imshow(
        matrix,
        x=[f"H{h:02d}" for h in hm["hours"]],
        y=hm["sources"],
        color_continuous_scale="Blues",
        labels=dict(x="Heure", y="Source", color="Posts"),
        aspect="auto", height=280,
    )
    fig_hm.update_layout(paper_bgcolor="white", margin=dict(t=20, b=20))
    st.plotly_chart(fig_hm, use_container_width=True)
    st.caption("Arctic Shift concentre toute son activite a H22. Reddit domine a H02-H06 et H17. OpenFDA et WebMD ont une activite homogene sur la journee.")

    st.markdown("---")
    st.markdown('<div class="section-header">Tableau recapitulatif — Anomalies detectees</div>',
                unsafe_allow_html=True)
    df_recap = df_consensus[["hour","nb_posts","anomaly_zscore","anomaly_ma","anomaly_if",
                              "nb_methods","anomaly_2of3"]].copy()
    df_recap.columns = ["Heure","Nb posts","Z-score","MA","Isolation Forest",
                        "Nb methodes","Consensus (2/3)"]
    df_all = df_recap[df_recap["Nb methodes"] > 0]
    st.dataframe(df_all if not df_all.empty else df_recap.head(5),
                 use_container_width=True, hide_index=True)

    if "Toutes" in methode or "Z-score" in methode:
        st.markdown("---")
        st.markdown('<div class="section-header">Statistiques Z-score</div>',
                    unsafe_allow_html=True)
        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
        col_s1.metric("Moyenne posts/heure", f"{zscore_data['mean_posts']:.1f}")
        col_s2.metric("Ecart-type", f"{zscore_data['std_posts']:.1f}")
        col_s3.metric("Seuil superieur", f"{zscore_data['upper_bound']:.0f}")
        col_s4.metric("Seuil inferieur", f"{zscore_data['lower_bound']:.0f}")


# ════════════════════════════════════════════════════════════════════════════
#  PAGE 4 — CLUSTERING
# ════════════════════════════════════════════════════════════════════════════
elif page == "Axe 4 — Clustering Usage":
    st.markdown('<p class="main-title">Axe 4 — Clustering des Parcours Utilisateurs</p>',
                unsafe_allow_html=True)
    st.markdown('<p class="main-subtitle">K-Means clustering — Modelisation des trajectoires de soins virtuelles et des profils de signalement</p>',
                unsafe_allow_html=True)
    st.markdown("---")

    total = sum(stats["cluster_distribution"].values())
    cols = st.columns(5)
    for i, (col, (k, v)) in enumerate(zip(cols, stats["cluster_distribution"].items())):
        col.markdown(f"""<div class="kpi-card">
        <div class="kpi-label">Cluster {k}</div>
        <div class="kpi-value">{v:,}</div>
        <div class="kpi-sub">{round(v/total*100,1)}% des posts</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="section-header">Distribution des clusters</div>',
                    unsafe_allow_html=True)
        labels = [f"Cluster {k}" for k in stats["cluster_distribution"]]
        values = list(stats["cluster_distribution"].values())
        fig_pie = px.pie(values=values, names=labels, height=300,
                         color_discrete_sequence=["#1D4ED8","#2563EB","#3B82F6","#60A5FA","#93C5FD"])
        fig_pie.update_layout(paper_bgcolor="white", margin=dict(t=10,b=10))
        fig_pie.update_traces(textinfo="label+percent")
        st.plotly_chart(fig_pie, use_container_width=True)

    with col2:
        st.markdown('<div class="section-header">Taille de chaque cluster</div>',
                    unsafe_allow_html=True)
        cluster_colors = ["#1D4ED8","#2563EB","#3B82F6","#60A5FA","#93C5FD"]
        fig_bar = go.Figure(go.Bar(
            x=labels, y=values,
            marker_color=cluster_colors,
            text=values, textposition="outside",
        ))
        fig_bar.update_layout(yaxis_title="Nombre de posts", height=300, **CHART_THEME)
        st.plotly_chart(fig_bar, use_container_width=True)

    st.markdown("---")
    st.markdown('<div class="section-header">Visualisations du clustering</div>',
                unsafe_allow_html=True)
    tab1, tab2, tab3 = st.tabs(["K-Means t-SNE 2D", "Clusters par source", "Keywords par cluster"])

    with tab1:
        img = load_img("kmeans_vs_original.png")
        if img:
            st.image(img, caption="Projection t-SNE 2D des 5 clusters K-Means", use_container_width=True)
    with tab2:
        img2 = load_img("clusters_vs_source.png")
        if img2:
            st.image(img2, caption="Repartition des clusters par source de donnees", use_container_width=True)
    with tab3:
        img3 = load_img("keywords_par_cluster.png")
        if img3:
            st.image(img3, caption="Mots-cles caracteristiques de chaque cluster", use_container_width=True)

    st.markdown("---")
    st.markdown('<div class="section-header">Requetes de recherche les plus frequentes</div>',
                unsafe_allow_html=True)
    queries = {k: v for k, v in stats["top_search_queries"].items() if k}
    df_q = pd.DataFrame({"Requete": list(queries.keys()), "Frequence": list(queries.values())})
    df_q = df_q.sort_values("Frequence", ascending=False).head(15)

    col_q1, col_q2 = st.columns([1.6, 1])
    with col_q1:
        fig_q = go.Figure(go.Bar(
            x=df_q["Frequence"], y=df_q["Requete"],
            orientation="h", marker_color="#1D4ED8",
            text=df_q["Frequence"], textposition="outside",
        ))
        fig_q.update_layout(xaxis_title="Frequence", height=380, **CHART_THEME)
        st.plotly_chart(fig_q, use_container_width=True)
    with col_q2:
        st.dataframe(df_q, use_container_width=True, hide_index=True)
        st.caption("Les requetes 'side effects', 'drug reaction' et 'withdrawal symptoms' "
                   "dominent — les utilisateurs cherchent a signaler ou comprendre les "
                   "effets indesirables de leurs traitements.")

    st.markdown("---")
    st.markdown('<div class="section-header">Timeline medicaments par heure</div>',
                unsafe_allow_html=True)
    img_tl = load_img("timeline_medicaments_heure.png")
    if img_tl:
        st.image(img_tl,
                 caption="Activite horaire par medicament — les psychotropes (Xanax, Adderall) montrent des pics nocturnes specifiques",
                 use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════
#  PAGE 5 — SYNTHESE
# ════════════════════════════════════════════════════════════════════════════
elif page == "Synthese & Comparaison":
    st.markdown('<p class="main-title">Synthese — Bio-Sentry</p>', unsafe_allow_html=True)
    st.markdown('<p class="main-subtitle">Vue croisee Axe 3 x Axe 4 — Correlation fiabilite des sources et anomalies temporelles</p>', unsafe_allow_html=True)
    st.markdown("---")

    # Scatter croise fiabilite x volume
    st.markdown('<div class="section-header">Croisement : Fiabilite des sources (Axe 3) x Volume d\'activite (Axe 4)</div>',
                unsafe_allow_html=True)
    hm = heatmaps["heatmap_source_hour"]
    matrix = np.array([s["values"] for s in hm["data"]])
    total_per_src = matrix.sum(axis=1)
    vol_map = {s: total_per_src[i] for i, s in enumerate(hm["sources"])}
    # Alias : reddit_rss (axe3) == reddit_api (heatmaps)
    vol_map.setdefault("reddit_rss", vol_map.get("reddit_api", 0))
    df_cross = df_sources.copy()
    df_cross["volume_total"] = df_cross["source"].map(vol_map).fillna(0)

    fig_cross = go.Figure()
    for _, row in df_cross.iterrows():
        fig_cross.add_trace(go.Scatter(
            x=[row["composite_avg"]],
            y=[row["volume_total"]],
            mode="markers+text",
            name=row["source"],
            text=[row["source"]],
            textposition="top center",
            marker=dict(
                size=max(14, row["doc_count"] / 250),
                color=SRC_COLOR.get(row["source"], "#9CA3AF"),
                line=dict(width=2, color="white"),
            ),
        ))
    fig_cross.add_annotation(
        x=0.086, y=6000,
        text="OpenFDA : haute fiabilite, faible volume brut",
        showarrow=True, arrowhead=2, arrowcolor="#1D4ED8",
        font=dict(size=11, color="#1D4ED8"),
    )
    fig_cross.update_layout(
        xaxis_title="Score fiabilite composite — Axe 3",
        yaxis_title="Volume total de posts — Axe 4",
        height=380, showlegend=False, **CHART_THEME,
    )
    st.plotly_chart(fig_cross, use_container_width=True)
    st.caption("Reddit : volume massif, fiabilite faible → principale source d'anomalies a surveiller. "
               "OpenFDA : fiabilite maximale, volume modere → reference certifiee pour la pharmacovigilance.")

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="section-header">Tableau de synthese algorithmique</div>',
                    unsafe_allow_html=True)
        df_s = pd.DataFrame({
            "Axe":         ["Axe 3","Axe 3","Axe 3","Axe 4","Axe 4","Axe 4"],
            "Algorithme":  ["HITS","PageRank","Degree Centrality",
                            "Z-score","Moving Average","Isolation Forest"],
            "Type":        ["Structure","Structure","Structure",
                            "Temporel","Temporel","Temporel"],
            "Resultat cle":["OpenFDA > WebMD > Reddit",
                            "Resultats homogenes",
                            "Correle a HITS",
                            "1 anomalie — H17 (Z=4.20)",
                            "0 anomalie",
                            "4 heures suspectes"],
        })
        st.dataframe(df_s, use_container_width=True, hide_index=True)

    with col2:
        st.markdown('<div class="section-header">Metriques finales du systeme</div>',
                    unsafe_allow_html=True)
        metrics = [
            ("Documents analyses",        "24 444"),
            ("Aretes dans le graphe",     "2 501 423"),
            ("Source la plus fiable",     "OpenFDA — score 0.0863"),
            ("Source la moins fiable",    "Drugs Forum — score 0.0234"),
            ("Heure critique detectee",   "H17 — 6 066 posts"),
            ("Medicament le + signale",   "Trazodone — 863 mentions"),
            ("Clusters utilisateurs",     "5 clusters K-Means"),
            ("Anomalie consensus",        "1 — H17 (2/3 methodes)"),
        ]
        for label, val in metrics:
            st.markdown(f"**{label}** : {val}")

    st.markdown("---")
    st.markdown('<div class="section-header">Alertes pharmacovigilance priorisees</div>',
                unsafe_allow_html=True)
    df_alerts = pd.DataFrame({
        "Signal detecte":            ["Pic H17 — Trazodone/Sertraline",
                                       "Effets Sertraline (cross-source)",
                                       "Xanax/Adderall — pics nocturnes",
                                       "duloxetine hydrochloride"],
        "Source principale":         ["Reddit","Reddit + OpenFDA","Reddit","OpenFDA"],
        "Fiabilite structurelle":    ["Faible (hub, distance ~27.6)",
                                       "Elevee (cross-source confirme)",
                                       "Faible","Maximale (100% FDA)"],
        "Action recommandee":        ["Verifier dans OpenFDA/WebMD",
                                       "Alerte pharmacovigilance",
                                       "Surveillance renforcee",
                                       "Source de reference certifiee"],
        "Priorite":                  ["HAUTE","HAUTE","MOYENNE","BASSE"],
    })
    st.dataframe(df_alerts, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown('<div class="section-header">Visualisations comparatives Axe 4</div>',
                unsafe_allow_html=True)
    tab_a, tab_b, tab_c = st.tabs(["Timeline par source","Heatmap source x heure","Comparaison algorithmes"])
    with tab_a:
        img = load_img("timeline_par_source.png")
        if img: st.image(img, use_container_width=True)
    with tab_b:
        img = load_img("heatmap_source_heure.png")
        if img: st.image(img, use_container_width=True)
    with tab_c:
        img = load_img("comparaison_algorithmes.png")
        if img: st.image(img, use_container_width=True)
