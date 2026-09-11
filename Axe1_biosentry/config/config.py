# ============================================================
#  Bio-Sentry — Axe 1 Configuration
#  Modifie ce fichier selon ton environnement
# ============================================================

# --- MongoDB ---
MONGO_URI = "mongodb://localhost:27017/"
DATABASE_NAME = "biosentry"         # Nom de ta base de données
COLLECTION_NAME = "posts"           # Nom de ta collection principale
REPORT_COLLECTION = "axe1_report"   # Collection pour les rapports agrégés

# --- Modèles NLP ---
# Modèle principal BioBERT NER (téléchargé automatiquement depuis HuggingFace)
NER_MODEL = "d4data/biomedical-ner-all"

# Modèle pour la classification de relations (zero-shot NLI)
RELATION_MODEL = "facebook/bart-large-mnli"

# Device : -1 = CPU, 0 = GPU (si CUDA disponible)
DEVICE = -1

# --- Seuils de confiance ---
NER_MIN_SCORE = 0.75        # Score minimum pour garder une entité NER
RELATION_MIN_SCORE = 0.60   # Score minimum pour valider une relation

# --- Filtres MongoDB ---
# Filtrer uniquement les documents non traités en anglais
MONGO_FILTER = {
    "processed": False,
    "language": "en"
}

# Nombre max de documents par batch (None = tous)
BATCH_SIZE = None

# --- Labels d'entités à chercher ---
DRUG_LABELS = ["DRUG", "Chemical", "CHEMICAL", "medication"]
SYMPTOM_LABELS = ["SYMPTOM", "DISEASE", "ADR", "Sign_symptom",
                  "Disease_disorder", "ADVERSE_EFFECT"]

# --- Labels de relations ---
RELATION_LABELS = [
    "adverse drug effect",
    "symptom of underlying disease",
    "treatment response",
    "unrelated"
]

# --- Sortie ---
OUTPUT_DIR = "output"
