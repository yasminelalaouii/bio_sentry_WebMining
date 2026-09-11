"""
ÉTAPE 3 — NER Biomédicale avec BioBERT (BIO Tagging)
======================================================
Ce script charge le modèle BioBERT fine-tuné pour la NER
et extrait les entités médicales (DRUG, SYMPTOM, DISEASE...)
depuis chaque phrase des documents.

Concepts clés :
  - BIO Tagging : B-DRUG = début d'un médicament, I-DRUG = suite, O = rien
  - aggregation_strategy="simple" : fusionne les sous-tokens WordPiece
  - Score de confiance : filtrage des entités peu sûres

Usage : python src/03_ner_biobert.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from transformers import (pipeline, AutoTokenizer,
                          AutoModelForTokenClassification)
from config.config import NER_MODEL, DEVICE, NER_MIN_SCORE
from tqdm import tqdm


def load_ner_model(model_name: str = NER_MODEL, device: int = DEVICE):
    """
    Charge le modèle BioBERT NER depuis HuggingFace.
    
    Premier lancement : télécharge ~400 MB.
    Lancements suivants : utilise le cache local.
    
    aggregation_strategy="simple" :
      BioBERT tokenise en sous-tokens WordPiece.
      Ex : "ibuprofen" → ["ib", "##up", "##ro", "##fen"]
      Sans agrégation : 4 entités distinctes avec labels B/I
      Avec "simple"   : 1 entité "ibuprofen" avec label DRUG
    """
    print(f"\n🤖 Chargement du modèle NER : {model_name}")
    print("   (Premier lancement = téléchargement ~400 MB, patiente...)")

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForTokenClassification.from_pretrained(model_name)

    # Pipeline avec agrégation des sous-tokens BIO → entité complète
    ner_pipeline = pipeline(
        "ner",
        model=model,
        tokenizer=tokenizer,
        aggregation_strategy="simple",
        device=device
    )

    print(f"   ✓ Modèle chargé (device={'CPU' if device == -1 else f'GPU:{device}'})")
    return ner_pipeline, tokenizer, model


def demonstrate_bio_tagging(ner_pipeline, tokenizer, model):
    """
    Démonstration visuelle du BIO tagging sur un exemple concret.
    Montre la différence entre tokens bruts (BIO) et entités agrégées.
    """
    from transformers import pipeline as hf_pipeline

    demo = "I took ibuprofen 400mg for back pain and developed severe nausea and dizziness."

    print("\n" + "="*60)
    print("DÉMONSTRATION DU BIO TAGGING")
    print("="*60)
    print(f"\nPhrase : \"{demo}\"\n")

    # --- Tokens BIO bruts ---
    raw_pipe = hf_pipeline(
        "ner", model=model, tokenizer=tokenizer,
        aggregation_strategy=None, device=DEVICE
    )
    raw_results = raw_pipe(demo)

    print("1. Tokens BIO bruts (avant agrégation) :")
    print(f"   {'Token':<20} {'Label':<20} {'Score'}")
    print(f"   {'-'*20} {'-'*20} {'-'*5}")
    for tok in raw_results:
        if tok['entity'] != 'O':
            print(f"   {tok['word']:<20} {tok['entity']:<20} {tok['score']:.3f}")

    print()

    # --- Entités agrégées ---
    agg_results = ner_pipeline(demo)
    print("2. Entités agrégées (après aggregation_strategy='simple') :")
    print(f"   {'Entité':<20} {'Type':<20} {'Score'}")
    print(f"   {'-'*20} {'-'*20} {'-'*5}")
    for ent in agg_results:
        print(f"   {ent['word']:<20} {ent['entity_group']:<20} {ent['score']:.3f}")

    print("\n→ Les sous-tokens [ib, ##up, ##ro, ##fen] sont fusionnés en 'ibuprofen'")
    print("→ Les labels B-DRUG + I-DRUG deviennent un seul label 'DRUG'")
    print("="*60)


def extract_entities_from_sentence(sentence: str, ner_pipeline,
                                   sentence_idx: int,
                                   min_score: float = NER_MIN_SCORE) -> list:
    """
    Applique la NER sur une seule phrase.
    
    Retourne une liste de dicts avec :
      - text         : le texte de l'entité
      - label        : le type (DRUG, SYMPTOM, DISEASE...)
      - score        : confiance du modèle (0 à 1)
      - sentence_idx : index de la phrase dans le document
      - sentence     : la phrase source
      - start/end    : positions caractères dans la phrase
    """
    try:
        entities = ner_pipeline(sentence)
    except Exception as e:
        print(f"   ⚠️  Erreur NER sur phrase {sentence_idx}: {e}")
        return []

    result = []
    for ent in entities:
        if ent["score"] >= min_score:
            result.append({
                "text": ent["word"].strip(),
                "label": ent["entity_group"],
                "score": round(float(ent["score"]), 4),
                "sentence_idx": sentence_idx,
                "sentence": sentence,
                "start": ent["start"],
                "end": ent["end"]
            })

    return result


def extract_entities_from_doc(doc: dict, ner_pipeline) -> list:
    """
    Extrait toutes les entités NER d'un document (toutes ses phrases).
    
    Retourne la liste complète des entités du document.
    """
    all_entities = []

    for sent_idx, sentence in enumerate(doc.get("sentences", [])):
        entities = extract_entities_from_sentence(
            sentence, ner_pipeline, sent_idx
        )
        all_entities.extend(entities)

    return all_entities


def run_ner_on_documents(documents: list, ner_pipeline) -> list:
    """
    Lance la NER sur tous les documents.
    
    Enrichit chaque document avec :
      - entities_extracted : liste des entités trouvées
      - entity_count       : nombre d'entités
    """
    print(f"\n🔍 Extraction NER sur {len(documents)} documents...")

    for doc in tqdm(documents, desc="NER BioBERT"):
        entities = extract_entities_from_doc(doc, ner_pipeline)
        doc["entities_extracted"] = entities
        doc["entity_count"] = len(entities)

    total = sum(d["entity_count"] for d in documents)
    print(f"   ✓ Total entités extraites : {total}")
    print(f"   ✓ Moyenne par document    : {total/len(documents):.1f}")

    return documents


# ── Démonstration standalone ─────────────────────────────────────────────────
if __name__ == "__main__":
    ner_pipeline, tokenizer, model = load_ner_model()

    # Démonstration BIO
    demonstrate_bio_tagging(ner_pipeline, tokenizer, model)

    # Test sur document exemple
    print("\n\n=== TEST SUR DOCUMENT EXEMPLE ===\n")
    sample_sentences = [
        "I took ibuprofen 400mg twice a day for back pain.",
        "After three days I developed severe nausea and dizziness.",
        "My doctor diagnosed me with gastritis and prescribed omeprazole.",
        "The omeprazole helped but I still felt fatigue and headaches."
    ]

    print(f"{'Phrase':<50} {'Entité':<20} {'Type':<20} {'Score'}")
    print("-" * 100)
    for i, sent in enumerate(sample_sentences):
        entities = extract_entities_from_sentence(sent, ner_pipeline, i)
        if entities:
            for ent in entities:
                phrase_display = sent[:48] + ".." if len(sent) > 50 else sent
                print(f"{phrase_display:<50} {ent['text']:<20} {ent['label']:<20} {ent['score']}")
        else:
            print(f"{sent[:48]:<50} (aucune entité détectée)")

    print("\n✓ Étape 3 — NER BioBERT OK")
