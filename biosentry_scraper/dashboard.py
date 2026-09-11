import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import pymongo
from pymongo import MongoClient

# Must be the first Streamlit command
st.set_page_config(
    page_title="Bio-Sentry Dashboard",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── CUSTOM CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Global */
    html, body, [data-testid="stAppViewContainer"] {
        background-color: #f4f6f9;
        font-family: 'Inter', sans-serif;
    }
    [data-testid="stAppViewContainer"] > .main { padding-top: 0.5rem; }
    [data-testid="block-container"] { padding: 0.75rem 1.5rem 0.5rem 1.5rem; }

    /* Header */
    .dash-header {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 0.4rem 0 0.6rem 0;
        border-bottom: 2px solid #e0e4ef;
        margin-bottom: 0.75rem;
    }
    .dash-header h1 {
        font-size: 1.35rem;
        font-weight: 700;
        color: #1a1f36;
        margin: 0;
    }
    .dash-header span {
        font-size: 0.85rem;
        color: #6b7280;
        margin-left: auto;
    }

    /* KPI Cards */
    .kpi-row { display: flex; gap: 14px; margin-bottom: 0.75rem; }
    .kpi-card {
        flex: 1;
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 10px;
        padding: 14px 18px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    }
    .kpi-label {
        font-size: 0.72rem;
        font-weight: 600;
        color: #6b7280;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 4px;
    }
    .kpi-value {
        font-size: 1.8rem;
        font-weight: 700;
        line-height: 1.1;
    }
    .kpi-value.green  { color: #10b981; }
    .kpi-value.purple { color: #8b5cf6; }
    .kpi-value.blue   { color: #3b82f6; }
    .kpi-value.teal   { color: #06b6d4; }

    /* Chart Cards */
    .chart-card {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 10px;
        padding: 10px 14px 6px 14px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
        height: 100%;
    }
    .chart-title {
        font-size: 0.8rem;
        font-weight: 700;
        color: #1a1f36;
        margin-bottom: 2px;
    }
    .chart-sub {
        font-size: 0.68rem;
        color: #9ca3af;
        margin-bottom: 4px;
    }

    /* Remove default streamlit column gaps override */
    [data-testid="stHorizontalBlock"] { gap: 12px !important; }

    /* Tighten plotly padding */
    .js-plotly-plot { border-radius: 6px; }

    /* Divider */
    .section-divider { margin: 0.5rem 0; border: none; border-top: 1px solid #e5e7eb; }
</style>
""", unsafe_allow_html=True)

# Import config
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from config import MONGO_URI, MONGO_DATABASE
except ImportError:
    st.error("Could not import MONGO_URI or MONGO_DATABASE from config.py")
    st.stop()

MONGO_COLLECTION = "processed_unified"

# ─── MONGODB CONNECTION & DATA FETCHING ──────────────────────────────────────

@st.cache_resource
def init_connection():
    return MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)

client = init_connection()

@st.cache_data(ttl=600)
def fetch_data():
    db = client[MONGO_DATABASE]
    collection = db[MONGO_COLLECTION]
    cursor = collection.find({}, {"_id": 0, "text": 0})
    docs = list(cursor)
    if not docs:
        return pd.DataFrame()
    return pd.DataFrame(docs)

# ─── HEADER ──────────────────────────────────────────────────────────────────
st.markdown("""
<div class="dash-header">
    <h1>🧬 Bio-Sentry Pharmacovigilance Dashboard</h1>
    <span>Unified data from Reddit · OpenFDA · WebMD · Drugs-Forum · DrugLib · EMA</span>
</div>
""", unsafe_allow_html=True)

# ─── LOAD DATA ───────────────────────────────────────────────────────────────
with st.spinner("Connecting to MongoDB…"):
    try:
        df = fetch_data()
    except Exception as e:
        st.error(f"Error connecting to MongoDB: {e}")
        st.stop()

if df.empty:
    st.warning(f"No data found in {MONGO_DATABASE}.{MONGO_COLLECTION}")
    st.stop()

# ─── COMPUTED METRICS ────────────────────────────────────────────────────────
total_docs    = len(df)
total_sources = df['source'].nunique() if 'source' in df.columns else 0
total_drugs   = 0
top_source    = "N/A"

if 'drugs_mentioned' in df.columns:
    drugs_exploded = df.explode('drugs_mentioned').dropna(subset=['drugs_mentioned'])
    drugs_exploded = drugs_exploded[drugs_exploded['drugs_mentioned'] != ""]
    total_drugs = drugs_exploded['drugs_mentioned'].nunique()

if 'source' in df.columns:
    top_source = df['source'].value_counts().idxmax()

# ─── KPI CARDS ───────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="kpi-row">
    <div class="kpi-card">
        <div class="kpi-label">Total Documents</div>
        <div class="kpi-value green">{total_docs:,}</div>
    </div>
    <div class="kpi-card">
        <div class="kpi-label">Unique Sources</div>
        <div class="kpi-value purple">{total_sources}</div>
    </div>
    <div class="kpi-card">
        <div class="kpi-label">Unique Medications</div>
        <div class="kpi-value blue">{total_drugs:,}</div>
    </div>
    <div class="kpi-card">
        <div class="kpi-label">Top Source</div>
        <div class="kpi-value teal" style="font-size:1.3rem">{top_source}</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ─── CHART PALETTE ───────────────────────────────────────────────────────────
PALETTE = ["#8b5cf6", "#a78bfa", "#c4b5fd", "#7c3aed", "#6d28d9",
           "#06b6d4", "#3b82f6", "#10b981", "#f59e0b", "#ef4444"]

CHART_H = 270   # shared chart height (px) — keeps everything on one screen

# ─── ROW 1: Source Donut | Content Type Bar | Top Drugs ──────────────────────
r1c1, r1c2, r1c3 = st.columns([1, 1.4, 1.6])

# ── Donut: Source Distribution
with r1c1:
    st.markdown('<div class="chart-card"><div class="chart-title">Data by Source</div><div class="chart-sub">Share per platform</div>', unsafe_allow_html=True)
    if 'source' in df.columns:
        src = df['source'].value_counts().reset_index()
        src.columns = ['Source', 'Count']
        fig = px.pie(src, names='Source', values='Count', hole=0.45,
                     color_discrete_sequence=PALETTE)
        fig.update_traces(textposition='inside', textinfo='percent+label',
                          textfont_size=10)
        fig.update_layout(
            margin=dict(t=10, b=10, l=5, r=5), height=CHART_H,
            showlegend=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.markdown('</div>', unsafe_allow_html=True)

# ── Bar: Content Type
with r1c2:
    st.markdown('<div class="chart-card"><div class="chart-title">Data by Content Type</div><div class="chart-sub">Document categories</div>', unsafe_allow_html=True)
    if 'content_type' in df.columns:
        ct = df['content_type'].value_counts().reset_index()
        ct.columns = ['Content Type', 'Count']
        fig = px.bar(ct, x='Content Type', y='Count', color='Content Type',
                     text_auto=True, color_discrete_sequence=PALETTE)
        fig.update_layout(
            margin=dict(t=10, b=10, l=10, r=10), height=CHART_H,
            showlegend=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(tickfont=dict(size=10)), yaxis=dict(title='')
        )
        fig.update_traces(textfont_size=10)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.markdown('</div>', unsafe_allow_html=True)

# ── Bar: Top Medications
with r1c3:
    st.markdown('<div class="chart-card"><div class="chart-title">Top 10 Medications Mentioned</div><div class="chart-sub">Most frequent across all sources</div>', unsafe_allow_html=True)
    if 'drugs_mentioned' in df.columns:
        top = drugs_exploded['drugs_mentioned'].value_counts().head(10).reset_index()
        top.columns = ['Medication', 'Count']
        if not top.empty:
            fig = px.bar(top, x='Count', y='Medication', orientation='h',
                         color='Count', color_continuous_scale=['#c4b5fd', '#7c3aed'])
            fig.update_layout(
                margin=dict(t=10, b=10, l=10, r=10), height=CHART_H,
                coloraxis_showscale=False, paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                yaxis=dict(categoryorder='total ascending', tickfont=dict(size=10)),
                xaxis=dict(title='')
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.markdown('</div>', unsafe_allow_html=True)

st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

# ─── ROW 2: Timeline | Engagement Strip ──────────────────────────────────────
r2c1, r2c2 = st.columns([1.5, 1])

# ── Line: Documents Over Time
with r2c1:
    st.markdown('<div class="chart-card"><div class="chart-title">Documents Collected Over Time</div><div class="chart-sub">By source, daily totals</div>', unsafe_allow_html=True)
    if 'date_scraped' in df.columns and 'source' in df.columns:
        df_t = df.copy()
        df_t['date_scraped'] = pd.to_datetime(df_t['date_scraped'], errors='coerce')
        df_t = df_t.dropna(subset=['date_scraped'])
        if not df_t.empty:
            df_t['day'] = df_t['date_scraped'].dt.date
            daily = df_t.groupby(['day', 'source']).size().reset_index(name='Count')
            fig = px.line(daily, x='day', y='Count', color='source',
                          color_discrete_sequence=PALETTE)
            fig.update_traces(line_width=1.8)
            fig.update_layout(
                margin=dict(t=10, b=10, l=10, r=10), height=CHART_H,
                legend=dict(orientation='h', yanchor='top', y=-0.15,
                            font=dict(size=9), title=''),
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(title='', tickfont=dict(size=9)),
                yaxis=dict(title='', tickfont=dict(size=9))
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("No date data available.")
    else:
        st.info("'date_scraped' or 'source' column not found.")
    st.markdown('</div>', unsafe_allow_html=True)

# ── Strip / Box: Engagement by Source
with r2c2:
    st.markdown('<div class="chart-card"><div class="chart-title">Engagement per Post</div><div class="chart-sub">Comments distribution by source</div>', unsafe_allow_html=True)
    if 'num_comments' in df.columns and 'source' in df.columns:
        df_c = df[df['num_comments'] > 0]
        if not df_c.empty:
            fig = px.box(df_c, x='source', y='num_comments', color='source',
                         color_discrete_sequence=PALETTE,
                         points='outliers')
            fig.update_layout(
                margin=dict(t=10, b=10, l=10, r=10), height=CHART_H,
                showlegend=False, paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(title='', tickfont=dict(size=9)),
                yaxis=dict(title='Comments', tickfont=dict(size=9))
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("No engagement data with comments > 0.")
    else:
        st.info("'num_comments' column not found.")
    st.markdown('</div>', unsafe_allow_html=True)

# ─── RAW DATA EXPANDER ───────────────────────────────────────────────────────
with st.expander("🗂️ Raw Data Preview (latest 100 records)"):
    cols_to_show = [c for c in df.columns if c != 'text_length']
    sort_col = 'date_scraped' if 'date_scraped' in df.columns else df.columns[0]
    st.dataframe(
        df[cols_to_show].sort_values(by=sort_col, ascending=False).head(100),
        use_container_width=True,
        height=220
    )
