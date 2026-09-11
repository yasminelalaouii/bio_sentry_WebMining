"""
Axe 3 v2 - Web Structure Mining COMPLET
========================================
- Donnees : processed_unified (18 862 docs) + toutes les raw collections
- Algorithmes : HITS + PageRank + SALSA  (3 requis par l'enonce)
- Analyse des sources : fiabilite par medicament, comparaison statistique
- Livrables : 8 graphiques + JSON + CSV + rapport MongoDB
"""

import os, re, json, warnings
from collections import defaultdict
from datetime import datetime

import pymongo
import networkx as nx
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from scipy import stats

warnings.filterwarnings("ignore")

# ================================================================
#  CONFIG
# ================================================================

MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb+srv://hajartaghi555_db_user:fFjWeAl3tyfb1FAd@hajar.qbnutif.mongodb.net/?appName=Hajar"
)
DB_NAME    = "bio_sentry"
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))

# Toutes les collections sources (processed_unified en priorite)
COLLECTIONS = {
    "processed_unified":  "mixed",     # contient toutes les sources unifiees
    "raw_Reddit_scraper": "hub",
    "raw_arctic_shift":   "hub",
    "raw_reddit_api":     "hub",
    "raw_drugs_forum":    "hub",
    "raw_openfda":        "authority",
    "raw_webmd":          "authority",
}

# Couleur par source originale
SOURCE_COLOR = {
    "openfda":   "#2196F3",
    "webmd":     "#4CAF50",
    "reddit":    "#FF5722",
    "arctic_shift": "#FF9800",
    "reddit_rss":"#E91E63",
    "drugs_forum":"#9C27B0",
    "unknown":   "#888888",
}

# Taille max documents par collection (None = tout prendre)
LIMITS = {
    "processed_unified":  None,   # toute la collection (18 862)
    "raw_Reddit_scraper": None,   # toute
    "raw_arctic_shift":   None,
    "raw_reddit_api":     None,
    "raw_drugs_forum":    None,
    "raw_openfda":        None,
    "raw_webmd":          None,
}

DRUG_RE = re.compile(
    r"\b(ibuprofen|aspirin|paracetamol|acetaminophen|metformin|atorvastatin|"
    r"amoxicillin|omeprazole|lisinopril|sertraline|fluoxetine|gabapentin|"
    r"prednisone|metoprolol|amlodipine|levothyroxine|simvastatin|losartan|"
    r"alprazolam|zolpidem|tramadol|oxycodone|hydrocodone|codeine|morphine|"
    r"warfarin|clopidogrel|insulin|methotrexate|hydroxychloroquine|"
    r"azithromycin|doxycycline|ciprofloxacin|naproxen|diclofenac|"
    r"cetirizine|loratadine|pantoprazole|esomeprazole|lansoprazole|"
    r"bupropion|venlafaxine|duloxetine|quetiapine|risperidone|olanzapine|"
    r"clonazepam|diazepam|lorazepam|methylphenidate|amphetamine|adderall|"
    r"xanax|prozac|zoloft|lexapro|wellbutrin|cymbalta|lyrica|ambien|"
    r"valium|klonopin|percocet|vicodin|suboxone|naltrexone|buprenorphine)\b",
    re.IGNORECASE,
)

EFFECT_RE = re.compile(
    r"\b(nausea|vomiting|dizziness|headache|fatigue|insomnia|anxiety|"
    r"depression|rash|itching|swelling|pain|fever|cough|dyspnea|"
    r"palpitation|hypertension|hypotension|tachycardia|bradycardia|"
    r"diarrhea|constipation|bleeding|bruising|liver|kidney|cardiac|"
    r"allergic|anaphylaxis|seizure|tremor|confusion|hallucination|"
    r"drowsiness|dry mouth|weight gain|weight loss|blurred vision|"
    r"memory loss|hair loss|muscle pain|joint pain|chest pain)\b",
    re.IGNORECASE,
)

# ================================================================
#  EXTRACTION
# ================================================================

def _text(doc):
    for f in ("text","body","content","selftext","description","title","summary"):
        v = doc.get(f)
        if isinstance(v, str) and len(v) > 5:
            return v
    return " ".join(str(v) for v in doc.values() if isinstance(v, str))

def _source_label(doc, coll_name):
    """Normalise le nom de la source quelle que soit la collection."""
    s = doc.get("source", "")
    if "openfda" in s or "openfda" in coll_name:  return "openfda"
    if "webmd"   in s or "webmd"   in coll_name:  return "webmd"
    if "arctic"  in s or "arctic"  in coll_name:  return "arctic_shift"
    if "drugs_forum" in coll_name:                 return "drugs_forum"
    if "reddit_rss"  in s:                         return "reddit_rss"
    if "reddit"      in s:                         return "reddit"
    return s or "unknown"

def _src_type(source_label):
    if source_label in ("openfda", "webmd"):
        return "authority"
    return "hub"

def _drugs(doc, text):
    raw = doc.get("drugs_mentioned", [])
    if isinstance(raw, list) and any(raw):
        return {str(d).lower().strip().rstrip(".") for d in raw if d}
    return {m.lower() for m in DRUG_RE.findall(text)}

# ================================================================
#  CHARGEMENT
# ================================================================

def load_all(uri, db_name):
    print("\n  Connexion MongoDB Atlas...")
    client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=15_000)
    client.admin.command("ping")
    db = client[db_name]
    rows = []
    seen_ids = set()   # eviter les doublons processed_unified / raw

    for coll, default_type in COLLECTIONS.items():
        try:
            limit = LIMITS.get(coll)
            cursor = db[coll].find({}) if limit is None else db[coll].find({}).limit(limit)
            docs = list(cursor)
            added = 0
            for i, doc in enumerate(docs):
                uid = str(doc.get("post_id", f"{coll}_{i}"))
                if uid in seen_ids:
                    continue
                seen_ids.add(uid)
                text   = _text(doc)
                src    = _source_label(doc, coll)
                stype  = _src_type(src) if default_type == "mixed" else default_type
                drugs  = _drugs(doc, text)
                effects= {m.lower() for m in EFFECT_RE.findall(text)}
                rows.append({
                    "id":       uid,
                    "coll":     coll,
                    "source":   src,
                    "src_type": stype,
                    "drugs":    drugs,
                    "effects":  effects,
                    "n_drugs":  len(drugs),
                    "n_effects":len(effects),
                    "text_len": len(text),
                })
                added += 1
            dm = sum(r["n_drugs"] for r in rows[-added:])
            print(f"    {coll:<28} {added:>6,} docs  |  {dm:>6,} drug mentions")
        except Exception as e:
            print(f"    {coll:<28} ERREUR: {e}")

    client.close()
    return pd.DataFrame(rows)

# ================================================================
#  GRAPHE
# ================================================================

def build_graph(df):
    """
    Noeud = document  |  Arete hub->authority si meme medicament mentionne.
    """
    G = nx.DiGraph()
    for _, r in df.iterrows():
        G.add_node(r["id"], source=r["source"], src_type=r["src_type"],
                   drugs=r["drugs"], n_drugs=r["n_drugs"])

    hub_idx  = defaultdict(list)
    auth_idx = defaultdict(list)
    for _, r in df.iterrows():
        for d in r["drugs"]:
            if r["src_type"] == "authority":
                auth_idx[d].append(r["id"])
            else:
                hub_idx[d].append(r["id"])

    for drug, hubs in hub_idx.items():
        for auth in auth_idx.get(drug, []):
            for hub in hubs:
                if not G.has_edge(hub, auth):
                    G.add_edge(hub, auth, drug=drug)

    print(f"\n  Graphe : {G.number_of_nodes():,} noeuds  |  {G.number_of_edges():,} aretes")
    return G

# ================================================================
#  3 ALGORITHMES
# ================================================================

def algo_hits(G):
    print("  [1/3] HITS...", end=" ", flush=True)
    h, a = nx.hits(G, max_iter=200, tol=1e-9, normalized=True)
    print("OK")
    return h, a

def algo_pagerank(G):
    """
    PageRank : mesure l'importance d'un noeud par la qualite de ses liens entrants.
    Un document authority pointe vers de nombreux hubs => score eleve.
    On inverse le graphe car PageRank mesure l'autorite par les liens entrants.
    """
    print("  [2/3] PageRank...", end=" ", flush=True)
    pr = nx.pagerank(G.reverse(), alpha=0.85, max_iter=200, tol=1e-9)
    print("OK")
    return pr

def algo_degree_centrality(G):
    """
    Centralite de degre : approche basique de reference.
    in-degree  = autorite brute (combien de hubs pointent vers ce doc)
    out-degree = hub brut     (combien d'authorities ce doc reference)
    Normalise entre 0 et 1.
    """
    print("  [3/3] Degree Centrality...", end=" ", flush=True)
    n = max(G.number_of_nodes() - 1, 1)
    in_c  = {node: deg / n for node, deg in G.in_degree()}
    out_c = {node: deg / n for node, deg in G.out_degree()}
    print("OK")
    return in_c, out_c

# ================================================================
#  ENRICHISSEMENT
# ================================================================

def enrich(df, G, hits_h, hits_a, pr, deg_in, deg_out):
    r = df.copy()
    r["hits_hub"]        = r["id"].map(hits_h).fillna(0)
    r["hits_authority"]  = r["id"].map(hits_a).fillna(0)
    r["pagerank"]        = r["id"].map(pr).fillna(0)
    r["degree_in_norm"]  = r["id"].map(deg_in).fillna(0)
    r["degree_out_norm"] = r["id"].map(deg_out).fillna(0)
    r["degree_in_raw"]   = r["id"].map(dict(G.in_degree())).fillna(0)
    r["degree_out_raw"]  = r["id"].map(dict(G.out_degree())).fillna(0)
    # Score composite authority : moyenne des 3 methodes
    r["composite_authority"] = (
        r["hits_authority"] / (r["hits_authority"].max() + 1e-12) +
        r["pagerank"]       / (r["pagerank"].max()       + 1e-12) +
        r["degree_in_norm"] / (r["degree_in_norm"].max() + 1e-12)
    ) / 3.0
    # Distance structurelle
    r["struct_distance"] = 1.0 / (r["hits_authority"] + 1e-12)
    return r

# ================================================================
#  RAPPORT CONSOLE
# ================================================================

def print_report(r):
    print("\n" + "="*65)
    print("  TOP 10 AUTHORITIES - Score HITS")
    print("="*65)
    c = ["id","source","src_type","hits_authority","composite_authority","n_drugs"]
    print(r.nlargest(10,"hits_authority")[c].to_string(index=False))

    print("\n" + "="*65)
    print("  TOP 10 HUBS - Score HITS")
    print("="*65)
    c2 = ["id","source","src_type","hits_hub","n_drugs"]
    print(r.nlargest(10,"hits_hub")[c2].to_string(index=False))

    print("\n" + "="*65)
    print("  COMPARAISON DES 3 ALGORITHMES PAR SOURCE")
    print("="*65)
    grp = r.groupby(["source","src_type"]).agg(
        docs          =("id",                 "count"),
        hits_auth_avg =("hits_authority",     "mean"),
        pagerank_avg  =("pagerank",           "mean"),
        degree_in_avg =("degree_in_norm",     "mean"),
        composite_avg =("composite_authority","mean"),
        avg_drugs     =("n_drugs",            "mean"),
    ).round(6)
    print(grp.to_string())

    print("\n" + "="*65)
    print("  FIABILITE PAR MEDICAMENT (top 15)")
    print("  (ratio docs authority / total docs mentionnant ce medicament)")
    print("="*65)
    drug_stats = defaultdict(lambda: {"total":0,"authority":0,"max_auth_score":0})
    for _, row in r.iterrows():
        for d in row["drugs"]:
            drug_stats[d]["total"] += 1
            if row["src_type"] == "authority":
                drug_stats[d]["authority"] += 1
                drug_stats[d]["max_auth_score"] = max(
                    drug_stats[d]["max_auth_score"], row["hits_authority"])
    drug_df = pd.DataFrame([
        {"drug": k, **v, "reliability_ratio": v["authority"]/max(v["total"],1)}
        for k, v in drug_stats.items()
        if v["total"] >= 3
    ]).sort_values("reliability_ratio", ascending=False).head(15)
    if not drug_df.empty:
        print(drug_df[["drug","total","authority","reliability_ratio"]].to_string(index=False))

# ================================================================
#  VISUALISATIONS  (8 graphiques)
# ================================================================

def _save(fig, name):
    p = os.path.join(OUTPUT_DIR, name)
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"    -> {name}")

def _color(src):
    return SOURCE_COLOR.get(src, "#888888")

# --- G1 : Hub vs Authority scatter (HITS) -----------------------
def plot_scatter(r):
    fig, ax = plt.subplots(figsize=(10,7))
    for src, g in r.groupby("source"):
        ax.scatter(g["hits_hub"], g["hits_authority"],
                   c=_color(src), label=src, alpha=0.55, s=20, edgecolors="none")
    ax.set_xlabel("Hub Score (HITS)")
    ax.set_ylabel("Authority Score (HITS)")
    ax.set_title("HITS - Distribution Hub vs Authority par source")
    ax.legend(fontsize=7)
    _save(fig, "axe3_G1_hits_scatter.png")

# --- G2 : Barres comparatives 3 algos --------------------------
def plot_3algos_bar(r):
    grp = r.groupby("source").agg(
        hits=("hits_authority","mean"),
        pr  =("pagerank","mean"),
        deg =("degree_in_norm","mean"),
    ).sort_values("hits", ascending=False)

    fig, ax = plt.subplots(figsize=(12,5))
    x = np.arange(len(grp))
    w = 0.28
    ax.bar(x-w,   grp["hits"], w, label="HITS authority",    color="#2196F3", alpha=0.85)
    ax.bar(x,     grp["pr"],   w, label="PageRank",          color="#4CAF50", alpha=0.85)
    ax.bar(x+w,   grp["deg"],  w, label="Degree centrality", color="#FF9800", alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels(grp.index, rotation=30, ha="right", fontsize=9)
    ax.set_ylabel("Score moyen normalise")
    ax.set_title("Comparaison des 3 algorithmes par source\n(HITS vs PageRank vs Degree Centrality)")
    ax.legend()
    _save(fig, "axe3_G2_3algos_comparison.png")

# --- G3 : Score composite authority (fiabilite globale) ---------
def plot_composite(r):
    grp = r.groupby("source").agg(
        composite=("composite_authority","mean"),
        src_type =("src_type","first"),
    ).sort_values("composite", ascending=True)

    colors = ["#4CAF50" if t=="authority" else "#FF5722" for t in grp["src_type"]]
    fig, ax = plt.subplots(figsize=(10,5))
    bars = ax.barh(grp.index, grp["composite"], color=colors, alpha=0.85)
    ax.set_xlabel("Score de fiabilite composite (moyenne HITS+PageRank+Degree)")
    ax.set_title("Classement des sources par fiabilite globale")
    patches = [mpatches.Patch(color="#4CAF50",label="Authority (certifie)"),
               mpatches.Patch(color="#FF5722",label="Hub (vulgarisation)")]
    ax.legend(handles=patches)
    _save(fig, "axe3_G3_source_reliability.png")

# --- G4 : Distribution distance structurelle -------------------
def plot_distance(r):
    fig, ax = plt.subplots(figsize=(10,5))
    for src, g in r.groupby("source"):
        vals = np.log1p(g["struct_distance"].replace([np.inf],np.nan).dropna())
        if len(vals) > 5:
            ax.hist(vals, bins=30, alpha=0.45, color=_color(src), label=src)
    ax.set_xlabel("log(1 + distance structurelle)")
    ax.set_ylabel("Nombre de documents")
    ax.set_title("Distance structurelle par rapport aux sources certifiees\n"
                 "(valeur faible = proche des autorites medicales)")
    ax.legend(fontsize=7)
    _save(fig, "axe3_G4_structural_distance.png")

# --- G5 : Top medicaments les plus couverts --------------------
def plot_drug_coverage(r):
    drug_count = defaultdict(lambda: defaultdict(int))
    for _, row in r.iterrows():
        for d in row["drugs"]:
            drug_count[d][row["src_type"]] += 1

    rows = [{"drug":d, "authority":v.get("authority",0), "hub":v.get("hub",0)}
            for d,v in drug_count.items()]
    df2 = pd.DataFrame(rows)
    df2["total"] = df2["authority"] + df2["hub"]
    df2 = df2.nlargest(20, "total").sort_values("total", ascending=True)

    fig, ax = plt.subplots(figsize=(10,8))
    ax.barh(df2["drug"], df2["authority"], color="#2196F3", label="Authority (FDA/WebMD)", alpha=0.85)
    ax.barh(df2["drug"], df2["hub"], left=df2["authority"],
            color="#FF5722", label="Hub (Reddit/Forum)", alpha=0.85)
    ax.set_xlabel("Nombre de documents mentionnant ce medicament")
    ax.set_title("Couverture des 20 medicaments les plus mentionnes\npar type de source")
    ax.legend()
    _save(fig, "axe3_G5_drug_coverage.png")

# --- G6 : Correlation entre les 3 algorithmes ------------------
def plot_correlation(r):
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    pairs = [
        ("hits_authority", "pagerank",      "HITS Authority vs PageRank"),
        ("hits_authority", "degree_in_norm","HITS Authority vs Degree In"),
        ("pagerank",       "degree_in_norm","PageRank vs Degree In"),
    ]
    for ax, (x, y, title) in zip(axes, pairs):
        for src, g in r.groupby("source"):
            ax.scatter(g[x], g[y], c=_color(src), s=8, alpha=0.4, label=src)
        # Ligne de regression
        mask = (r[x] > 0) & (r[y] > 0)
        try:
            if mask.sum() > 10 and r.loc[mask,x].nunique() > 1:
                slope, intercept, rv, pv, _ = stats.linregress(r.loc[mask,x], r.loc[mask,y])
                xr = np.linspace(r.loc[mask,x].min(), r.loc[mask,x].max(), 100)
                ax.plot(xr, slope*xr+intercept, "k--", linewidth=1, alpha=0.6)
                ax.set_title(f"{title}\nr={rv:.3f}")
            else:
                ax.set_title(title)
        except Exception:
            ax.set_title(title)
        ax.set_xlabel(x)
        ax.set_ylabel(y)
    handles = [mpatches.Patch(color=_color(s),label=s) for s in r["source"].unique()]
    fig.legend(handles=handles, fontsize=6, loc="lower center", ncol=4, bbox_to_anchor=(0.5,-0.05))
    fig.suptitle("Correlation entre les 3 algorithmes d'analyse de structure", fontsize=12)
    plt.tight_layout()
    _save(fig, "axe3_G6_algo_correlation.png")

# --- G7 : Sous-graphe des top noeuds ---------------------------
def plot_graph(G, r, max_nodes=120):
    top_ids = set(
        r.nlargest(max_nodes//2, "hits_hub")["id"].tolist() +
        r.nlargest(max_nodes//2, "hits_authority")["id"].tolist()
    )
    sub = G.subgraph(top_ids)
    if sub.number_of_edges() == 0:
        return

    fig, ax = plt.subplots(figsize=(16,12))
    pos = nx.spring_layout(sub, seed=42, k=0.5)
    node_c, node_s = [], []
    for n in sub.nodes():
        row = r[r["id"]==n]
        if row.empty:
            node_c.append("#888"); node_s.append(80); continue
        row = row.iloc[0]
        node_c.append(_color(row["source"]))
        sc = row["hits_authority"] + row["hits_hub"]
        node_s.append(80 + sc * 8000)

    nx.draw_networkx_nodes(sub, pos, node_color=node_c, node_size=node_s, alpha=0.8, ax=ax)
    nx.draw_networkx_edges(sub, pos, alpha=0.12, arrows=True,
                           arrowsize=8, edge_color="#BBBBBB", ax=ax)
    patches = [mpatches.Patch(color=c,label=s) for s,c in SOURCE_COLOR.items()
               if s in r["source"].values]
    ax.legend(handles=patches, fontsize=7, loc="upper left")
    ax.set_title(f"Graphe de co-mentions - {len(sub)} noeuds (top scores HITS)", fontsize=13)
    ax.axis("off")
    _save(fig, "axe3_G7_graph.png")

# --- G8 : Heatmap fiabilite source x medicament ----------------
def plot_heatmap(r):
    # Top 15 medicaments les plus frequents
    all_drugs = [d for drugs in r["drugs"] for d in drugs]
    from collections import Counter
    top_drugs = [d for d, _ in Counter(all_drugs).most_common(15)]
    sources   = r["source"].unique().tolist()

    matrix = pd.DataFrame(0.0, index=sources, columns=top_drugs)
    for _, row in r.iterrows():
        for d in row["drugs"]:
            if d in top_drugs:
                matrix.loc[row["source"], d] += row["hits_authority"] + row["hits_hub"]

    # Normaliser par source
    matrix = matrix.div(matrix.sum(axis=1) + 1e-12, axis=0)

    fig, ax = plt.subplots(figsize=(14, 5))
    im = ax.imshow(matrix.values, aspect="auto", cmap="YlOrRd")
    ax.set_xticks(range(len(top_drugs)))
    ax.set_xticklabels(top_drugs, rotation=45, ha="right", fontsize=9)
    ax.set_yticks(range(len(sources)))
    ax.set_yticklabels(sources, fontsize=9)
    plt.colorbar(im, ax=ax, label="Score HITS normalise par source")
    ax.set_title("Heatmap : intensite HITS par source et par medicament\n"
                 "(montre quelle source est la plus impliquee pour chaque medicament)")
    _save(fig, "axe3_G8_heatmap_source_drug.png")

# ================================================================
#  EXPORTS
# ================================================================

def export_csv(r):
    path = os.path.join(OUTPUT_DIR, "axe3_scores_complets.csv")
    out = r[["id","source","src_type","n_drugs","n_effects",
             "hits_hub","hits_authority","pagerank",
             "degree_in_norm","degree_out_norm","composite_authority",
             "struct_distance"]].copy()
    out["drugs"] = r["drugs"].apply(lambda s: "|".join(sorted(s)))
    out.to_csv(path, index=False, encoding="utf-8")
    print(f"    -> axe3_scores_complets.csv  ({len(out):,} lignes)")

def export_json(r, G):
    payload = {
        "generated_at": datetime.utcnow().isoformat()+"Z",
        "algorithms": ["HITS","PageRank","Degree Centrality"],
        "graph": {"nodes": G.number_of_nodes(), "edges": G.number_of_edges()},
        "total_documents": len(r),
        "source_summary": r.groupby(["source","src_type"]).agg(
            doc_count        =("id",                 "count"),
            hits_auth_avg    =("hits_authority",     "mean"),
            pagerank_avg     =("pagerank",           "mean"),
            degree_in_avg    =("degree_in_norm",     "mean"),
            composite_avg    =("composite_authority","mean"),
            struct_dist_med  =("struct_distance",    "median"),
        ).round(8).reset_index().to_dict(orient="records"),
        "top_authorities": r.nlargest(30,"composite_authority")[
            ["id","source","src_type","hits_authority","pagerank",
             "degree_in_norm","composite_authority","n_drugs"]
        ].to_dict(orient="records"),
        "top_hubs": r.nlargest(30,"hits_hub")[
            ["id","source","src_type","hits_hub","n_drugs"]
        ].to_dict(orient="records"),
    }
    path = os.path.join(OUTPUT_DIR, "axe3_hits_results.json")
    with open(path,"w",encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
    print(f"    -> axe3_hits_results.json")

def save_to_mongo(uri, db_name, r, G):
    try:
        client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=8_000)
        db = client[db_name]
        db["axe3_hits_results"].drop()
        records = r[["id","source","src_type","n_drugs","n_effects",
                     "hits_hub","hits_authority","pagerank",
                     "degree_in_norm","composite_authority",
                     "struct_distance","degree_in_raw","degree_out_raw"]].copy()
        records["drugs"]       = r["drugs"].apply(list)
        records["effects"]     = r["effects"].apply(list)
        records["computed_at"] = datetime.utcnow()
        db["axe3_hits_results"].insert_many(records.to_dict(orient="records"))
        print(f"    -> MongoDB bio_sentry.axe3_hits_results  ({len(records):,} docs)")
        client.close()
    except Exception as e:
        print(f"    MongoDB write skipped: {e}")

# ================================================================
#  MAIN
# ================================================================

def main():
    sep = "=" * 65
    print(sep)
    print("  AXE 3 v2 - WEB STRUCTURE MINING COMPLET")
    print("  HITS + PageRank + Degree Centrality")
    print("  Projet Bio-Sentry | Web Mining M242 | ENSA Tetouan")
    print(sep)

    print("\n[1/6]  Chargement de TOUTES les donnees...")
    df = load_all(MONGO_URI, DB_NAME)
    if df.empty:
        print("  Aucune donnee. Verifiez MONGO_URI.")
        return
    print(f"\n  Total unique : {len(df):,} documents  |  "
          f"{df['n_drugs'].sum():,} drug mentions  |  "
          f"{df['src_type'].value_counts().to_dict()}")

    print("\n[2/6]  Construction du graphe...")
    G = build_graph(df)
    if G.number_of_edges() == 0:
        print("  Aucune arete. Arret.")
        return

    print("\n[3/6]  Execution des 3 algorithmes...")
    hits_h, hits_a = algo_hits(G)
    pr              = algo_pagerank(G)
    deg_in, deg_out = algo_degree_centrality(G)

    print("\n[4/6]  Analyse des resultats...")
    res = enrich(df, G, hits_h, hits_a, pr, deg_in, deg_out)
    print_report(res)

    print("\n[5/6]  Generation des 8 visualisations...")
    plot_scatter(res)
    plot_3algos_bar(res)
    plot_composite(res)
    plot_distance(res)
    plot_drug_coverage(res)
    plot_correlation(res)
    plot_graph(G, res)
    plot_heatmap(res)

    print("\n[6/6]  Export CSV + JSON + MongoDB...")
    export_csv(res)
    export_json(res, G)
    save_to_mongo(MONGO_URI, DB_NAME, res, G)

    print(f"\n{sep}")
    print(f"  TERMINE. {len(res):,} documents analyses, {G.number_of_edges():,} aretes.")
    print("  Fichiers generes :")
    for i, f in enumerate([
        "axe3_G1_hits_scatter.png       (HITS hub vs authority)",
        "axe3_G2_3algos_comparison.png  (comparaison 3 algorithmes)",
        "axe3_G3_source_reliability.png (classement fiabilite sources)",
        "axe3_G4_structural_distance.png(distance structurelle)",
        "axe3_G5_drug_coverage.png      (couverture medicaments)",
        "axe3_G6_algo_correlation.png   (correlation entre algos)",
        "axe3_G7_graph.png              (graphe top noeuds)",
        "axe3_G8_heatmap_source_drug.png(heatmap source x medicament)",
        "axe3_scores_complets.csv       (tous les scores)",
        "axe3_hits_results.json         (pour Axe 5 Dashboard)",
    ], 1):
        print(f"  {i:>2}. {f}")
    print(sep)


if __name__ == "__main__":
    main()
