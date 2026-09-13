# Bio-Sentry — Early Adverse Drug Reaction Detection System

**Web Mining project**

Bio-Sentry is a pharmacovigilance system that mines the web (health forums, social media, and official drug databases) to detect early signals of drug side effects not yet officially documented; combining **Web Content Mining**, **Web Structure Mining**, and **Web Usage Mining**.

## Overview

Traditional pharmacovigilance struggles to quickly catch rare or emerging adverse drug reactions reported informally by patients online. Bio-Sentry addresses this by automatically collecting, structuring, and analyzing unstructured, subjective text from health forums and social networks to extract weak toxicity signals; enabling earlier detection than official health alerts.

The project is built around three complementary mining axes:

- **Axe 1 — Web Content Mining**: biomedical NLP pipeline (BioBERT-based NER) to extract drugs, symptoms, and drug→symptom relations from raw text.
- **Axe 2 — Web Structure Mining**: graph analysis (HITS, PageRank, Degree Centrality) over the source network to score source reliability and authority.
- **Axe 3 — Web Usage Mining**: temporal anomaly detection and clustering to spot emerging outbreaks of adverse effect reports.

Results are served through an interactive Streamlit dashboard.

## Data Collection — `biosentry_scraper/`

Multi-source scraper collecting raw pharmacovigilance-relevant text, stored in MongoDB.

**Sources:**
- **Reddit** (r/AskDocs, r/medicine, r/sideeffects, r/pharmacology) via Selenium and RSS/Arctic Shift
- **WebMD** — user drug reviews
- **DrugsForum** — patient discussion threads
- **OpenFDA** — official adverse event reports (API)

**Stack:** Python, Selenium (`undetected-chromedriver`), BeautifulSoup, PyMongo, Streamlit (local monitoring dashboard)

## Axe 1 — Web Content Mining (`Axe1_biosentry/`)

Biomedical NLP pipeline for named entity recognition and relation extraction.

**Pipeline:**
1. Load raw documents from MongoDB
2. Text preprocessing
3. Named Entity Recognition with **BioBERT** (BIO tagging)
4. Comparison of 3 NER approaches (including scispaCy)
5. Drug → Symptom relation classification
6. Save structured results back to MongoDB
7. Statistical report generation

**Key results** (from `axe1_report.json`):
- 1,005 documents processed
- 324,388 entities extracted (avg. ~323 per document)
- 24,586 drug–symptom relations classified
- 11,048 adverse effects detected
- Most frequent symptoms detected: anxiety, pain, among others

**Stack:** Python, Transformers (BioBERT), PyTorch, spaCy, scispaCy, scikit-learn, NLTK, PyMongo

## Axe 2 — Web Structure Mining (`axe2_graph_mining/`)

Models the source network as a graph and applies link analysis to quantify source reliability, distinguishing well-established "Authorities" (peer-reviewed / official sources) from "Hubs" (discussion / awareness sources).

**Algorithms compared:** HITS, PageRank, Degree Centrality

**Graph scale:** 24,444 nodes, 2,501,423 edges

**Source classification (sample):**
| Source | Type | Documents | Composite Score |
|---|---|---|---|
| OpenFDA | Authority | 5,809 | 0.086 |
| WebMD | Authority | 6,670 | 0.053 |
| Reddit | Hub | 10,807 | 0.029 |
| Arctic Shift | Hub | 824 | 0.029 |
| DrugsForum | Hub | 333 | 0.023 |

**Stack:** Python, NetworkX, PyMongo, pandas, SciPy, Matplotlib

## Axe 3 — Web Usage Mining (`axe3_alert/`)

Detects temporal anomalies in report volume to flag emerging outbreaks of adverse effect signals, and clusters user report trajectories to model virtual care pathways.

**Anomaly detection methods (compared):** Z-score, Moving Average, Isolation Forest, and a consensus of all three

**Clustering:** K-Means, with 2D visualization via t-SNE

**Outputs:** hourly/source activity heatmaps, keyword-per-cluster analysis, drug-mention timelines, algorithm comparison charts

**Stack:** Python, scikit-learn, pandas, NumPy, Matplotlib, MongoDB

## Dashboard (`dashboard/` & `deploy/`)

Interactive Streamlit dashboard presenting results from all three axes: HITS/PageRank source reliability, anomaly timelines, cluster visualizations, and key pharmacovigilance statistics.

**Stack:** Streamlit, Plotly, pandas, Pillow

## Tech Stack Summary

| Category | Tools |
|---|---|
| NLP / Biomedical AI | BioBERT, spaCy, scispaCy, Transformers, PyTorch |
| Graph Mining | NetworkX (HITS, PageRank, Degree Centrality) |
| Machine Learning | scikit-learn (Isolation Forest, K-Means), SciPy |
| Database | MongoDB (NoSQL) |
| Scraping | Selenium, BeautifulSoup, OpenFDA API |
| Visualization / Dashboard | Streamlit, Plotly, Matplotlib |
| Language | Python |

## Installation

Each module has its own `requirements.txt`. General setup:

```bash
git clone <YOUR_REPO_URL>
cd WebMiningCCF

# Per-module setup, e.g. for Axe 1:
cd Axe1_biosentry
pip install -r requirements.txt
```

MongoDB connection settings are read from environment variables (`.env`, not committed) — see each module's config file for the expected variable names.

### Running the pipeline

```bash
# 1. Collect data
cd biosentry_scraper && python main.py

# 2. Run NLP extraction (Axe 1)
cd ../Axe1_biosentry && python src/pipeline.py

# 3. Run graph mining (Axe 2)
cd ../axe2_graph_mining && python hits_pipeline_v2.py

# 4. Run usage mining / anomaly detection (Axe 3)
cd ../axe3_alert  # see notebook / scripts

# 5. Launch the dashboard
cd ../deploy && streamlit run app.py
```

## Ethics & Compliance

- All scraped data collection respects source `robots.txt` policies
- Data is anonymized before analysis
- Project developed for academic purposes as part of the Web Mining module 

## Disclaimer

This project is an academic exercise. It is not a validated pharmacovigilance tool and should never replace official drug safety monitoring systems or medical professional advice.
