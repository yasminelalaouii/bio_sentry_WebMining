"""
ÉTAPE 5 — Classification des Relations Drug → Symptom/Effect
=============================================================
Après la NER, on identifie les paires (DRUG, SYMPTOM) dans
la même phrase et on classifie la nature de la relation :

  - "adverse drug effect"           → effet indésirable (signal pharmacovigilance)
  - "symptom of underlying disease" → manifestation de la pathologie
  - "treatment response"            → réponse thérapeutique normale
  - "unrelated"                     → non lié au médicament

Méthode : Zero-shot classification (NLI) avec BART-large-mnli.
  Avantage : pas besoin de dataset annoté, généraliste.

Usage : python src/05_relation_classifier.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from transformers import pipeline as hf_pipeline
from config.config import (RELATION_MODEL, DEVICE, RELATION_MIN_SCORE,
                           DRUG_LABELS, SYMPTOM_LABELS, RELATION_LABELS)
from tqdm import tqdm


def load_relation_classifier():
    """
    Charge le modèle de classification de relations (NLI zero-shot).
    
    NLI = Natural Language Inference : étant donné une prémisse et
    une hypothèse, le modèle prédit si l'hypothèse est vraie (entailment),
    fausse (contradiction) ou neutre (neutral).
    
    En zero-shot : on formule chaque label comme une hypothèse,
    et le score d'entailment donne la probabilité du label.
    """
    print(f"\n🤖 Chargement classificateur de relations : {RELATION_MODEL}")
    classifier = hf_pipeline(
        "zero-shot-classification",
        model=RELATION_MODEL,
        device=DEVICE
    )
    print("   ✓ Classificateur chargé")
    return classifier


def classify_relation(drug: str, symptom: str, sentence: str,
                       classifier) -> dict:
    """
    Classifie la relation entre un médicament et un symptôme
    dans le contexte d'une phrase donnée.
    
    Exemple :
      drug     = "ibuprofen"
      symptom  = "nausea"
      sentence = "I took ibuprofen and developed nausea after 3 days"
      
      → predicted_relation = "adverse drug effect" (conf: 0.82)
    """
    # Construire l'hypothèse de classification
    hypothesis_template = (
        f"The symptom '{symptom}' mentioned in relation to '{drug}' is a {{}}."
    )

    try:
        result = classifier(
            sequences=sentence,
            candidate_labels=RELATION_LABELS,
            hypothesis_template=hypothesis_template
        )

        return {
            "drug": drug,
            "symptom": symptom,
            "predicted_relation": result["labels"][0],
            "confidence": round(result["scores"][0], 4),
            "all_scores": {
                label: round(score, 4)
                for label, score in zip(result["labels"], result["scores"])
            },
            "sentence": sentence
        }

    except Exception as e:
        return {
            "drug": drug,
            "symptom": symptom,
            "predicted_relation": "error",
            "confidence": 0.0,
            "error": str(e),
            "sentence": sentence
        }


def extract_drug_symptom_pairs(entities: list) -> list:
    """
    Trouve toutes les paires (DRUG, SYMPTOM/DISEASE) dans la même phrase.
    
    Logique : deux entités sont candidates à une relation si elles
    apparaissent dans la même phrase (même sentence_idx).
    """
    pairs = []

    # Regrouper par phrase
    by_sentence = {}
    for ent in entities:
        idx = ent["sentence_idx"]
        by_sentence.setdefault(idx, []).append(ent)

    # Pour chaque phrase, créer le produit cartésien DRUG × SYMPTOM
    for sent_idx, ents in by_sentence.items():
        drugs = [e for e in ents if any(
            k.upper() in e["label"].upper() for k in ["DRUG", "CHEMICAL", "MEDICATION"]
        )]
        symptoms = [e for e in ents if any(
            k.upper() in e["label"].upper()
            for k in ["SYMPTOM", "DISEASE", "ADR", "SIGN", "DISORDER", "ADVERSE"]
        )]

        for drug in drugs:
            for symptom in symptoms:
                # Éviter les doublons (même texte)
                if drug["text"].lower() != symptom["text"].lower():
                    pairs.append({
                        "sentence_idx": sent_idx,
                        "sentence": drug["sentence"],
                        "drug_entity": drug["text"],
                        "drug_label": drug["label"],
                        "symptom_entity": symptom["text"],
                        "symptom_label": symptom["label"]
                    })

    return pairs


def classify_relations_for_doc(doc: dict, classifier) -> dict:
    """
    Classifie toutes les relations Drug→Symptom d'un document.
    
    Ajoute au document :
      - relations           : toutes les relations classifiées
      - adverse_effects     : filtrées sur predicted_relation == "adverse drug effect"
    """
    entities = doc.get("entities_extracted", [])
    pairs = extract_drug_symptom_pairs(entities)

    classified_relations = []
    for pair in pairs:
        relation = classify_relation(
            drug=pair["drug_entity"],
            symptom=pair["symptom_entity"],
            sentence=pair["sentence"],
            classifier=classifier
        )
        relation["drug_label"] = pair["drug_label"]
        relation["symptom_label"] = pair["symptom_label"]
        relation["sentence_idx"] = pair["sentence_idx"]
        classified_relations.append(relation)

    # Filtrer les effets indésirables confirmés
    adverse_effects = [
        r for r in classified_relations
        if r["predicted_relation"] == "adverse drug effect"
        and r["confidence"] >= RELATION_MIN_SCORE
    ]

    doc["relations"] = classified_relations
    doc["adverse_effects_detected"] = adverse_effects

    return doc


def classify_all_documents(documents: list, classifier) -> list:
    """Lance la classification de relations sur tous les documents."""
    print(f"\n🔗 Classification des relations sur {len(documents)} documents...")

    for doc in tqdm(documents, desc="Relations Drug→Symptom"):
        classify_relations_for_doc(doc, classifier)

    total_relations = sum(len(d.get("relations", [])) for d in documents)
    total_adverse = sum(len(d.get("adverse_effects_detected", [])) for d in documents)

    print(f"   ✓ Total relations analysées    : {total_relations}")
    print(f"   ✓ Effets indésirables détectés : {total_adverse}")

    return documents


# ── Démonstration standalone ─────────────────────────────────────────────────
if __name__ == "__main__":
    classifier = load_relation_classifier()

    test_cases = [
        {
            "drug": "ibuprofen",
            "symptom": "nausea",
            "sentence": "I took ibuprofen 400mg and after 3 days developed severe nausea."
        },
        {
            "drug": "metformin",
            "symptom": "fatigue",
            "sentence": "I have diabetes and I started metformin, but I still feel fatigue from the disease itself."
        },
        {
            "drug": "prednisone",
            "symptom": "weight gain",
            "sentence": "The prednisone is helping my inflammation but I've noticed significant weight gain."
        },
        {
            "drug": "sertraline",
            "symptom": "insomnia",
            "sentence": "Since starting sertraline two weeks ago I can't sleep at all, the insomnia is unbearable."
        }
    ]

    print("\n" + "="*70)
    print("DÉMONSTRATION : CLASSIFICATION DE RELATIONS DRUG → SYMPTOM")
    print("="*70)

    for case in test_cases:
        result = classify_relation(
            case["drug"], case["symptom"], case["sentence"], classifier
        )
        print(f"\n  💊 Drug    : {case['drug']}")
        print(f"  🤒 Symptom : {case['symptom']}")
        print(f"  📝 Sentence: {case['sentence'][:80]}...")
        print(f"  ✅ Relation: {result['predicted_relation']} (conf: {result['confidence']})")
        print(f"     Scores : {result['all_scores']}")

    print("\n✓ Étape 5 — Classification de relations OK")
