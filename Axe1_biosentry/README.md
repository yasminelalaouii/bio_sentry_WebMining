# Bio-Sentry — Axe 1 : NLP Biomédical
## Web Content Mining — Extraction Sémantique & Pharmacovigilance

---

## Structure du projet

```
biosentry_axe1/
│
├── README.md                  ← Ce fichier
├── requirements.txt           ← Dépendances Python
├── config/
│   └── config.py              ← Configuration MongoDB, modèles, seuils
│
├── src/
│   ├── 01_load_data.py        ← Chargement depuis MongoDB
│   ├── 02_preprocess.py       ← Préparation du texte
│   ├── 03_ner_biobert.py      ← NER avec BioBERT (BIO tagging)
│   ├── 04_ner_comparison.py   ← Comparaison 3 approches NER
│   ├── 05_relation_classifier.py ← Classification Drug→Symptom
│   ├── 06_save_results.py     ← Sauvegarde MongoDB
│   ├── 07_report.py           ← Génération rapport statistique
│   └── pipeline.py            ← Pipeline complet (run tout en 1)
│
├── docs/
│   └── BIO_tagging_explained.md  ← Explication détaillée BIO
│
└── output/                    ← Résultats générés automatiquement
    └── (axe1_report.json, comparaison.csv...)
```

---

## Installation

### 1. Prérequis
- Python 3.9+
- MongoDB en cours d'exécution (local ou distant)
- 8 GB RAM minimum (16 GB recommandé pour les modèles)
- GPU optionnel (CUDA) pour accélérer BioBERT

### 2. Installer les dépendances

```bash
pip install -r requirements.txt
```

Pour scispaCy (Approche 2 de la comparaison) :
```bash
pip install scispacy
pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.3/en_core_sci_sm-0.5.3.tar.gz
```

### 3. Configurer MongoDB

Édite `config/config.py` et modifie :
```python
MONGO_URI = "mongodb://localhost:27017/"   # ton URI MongoDB
DATABASE_NAME = "biosentry"                # ton nom de base
COLLECTION_NAME = "posts"                  # ton nom de collection
```

---

## Utilisation

### Option A — Lancer le pipeline complet (recommandé)

```bash
cd biosentry_axe1
python src/pipeline.py
```

Cela exécute toutes les étapes dans l'ordre et sauvegarde les résultats dans MongoDB.

### Option B — Exécuter étape par étape

```bash
python src/01_load_data.py          # Vérifier la connexion et les données
python src/02_preprocess.py         # Tester le preprocessing
python src/03_ner_biobert.py        # Tester la NER sur quelques exemples
python src/04_ner_comparison.py     # Comparer les 3 approches
python src/05_relation_classifier.py # Tester la classification de relations
python src/06_save_results.py       # Sauvegarder dans MongoDB
python src/07_report.py             # Générer le rapport final
```

---

## Résultats attendus dans MongoDB

Après exécution, chaque document aura ce champ ajouté :

```json
{
  "processed": true,
  "nlp_results": {
    "entities": [...],
    "entity_count": 12,
    "relations": [...],
    "adverse_effects": [...],
    "adverse_effects_count": 3,
    "processed_at": "2026-05-08T...",
    "model_used": "d4data/biomedical-ner-all"
  }
}
```

Et une collection `axe1_report` contiendra les statistiques agrégées.

---

## Première fois ? Tester avec un exemple

```bash
python src/03_ner_biobert.py
```

Cela lancera une démo sur cette phrase :
> "I took ibuprofen 400mg for 3 days and developed severe nausea and dizziness."

Tu verras les entités BIO extraites avec leurs scores.

---

## Notes importantes

- Le premier lancement télécharge les modèles HuggingFace (~1.5 GB). Assure-toi d'avoir une connexion internet.
- Les modèles sont mis en cache localement (dans `~/.cache/huggingface/`), les lancements suivants sont instantanés.
- Si tu n'as pas de GPU, mets `DEVICE = -1` dans `config/config.py` (CPU mode).
- Le seuil de confiance NER est à 0.75 par défaut — tu peux l'abaisser à 0.60 pour plus de rappel.
