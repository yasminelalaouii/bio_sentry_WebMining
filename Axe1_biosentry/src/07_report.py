"""
ÉTAPE 7 — Génération du Rapport Statistique Axe 1
==================================================
Ce script agrège tous les résultats NLP stockés dans MongoDB
et génère un rapport JSON + CSV avec :

  - Distribution des types d'entités
  - Top médicaments mentionnés
  - Top symptômes détectés
  - Paires Drug→Effect les plus fréquentes (signaux pharmacovigilance)
  - Métriques de couverture du pipeline

Usage : python src/07_report.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import pandas as pd
from collections import Counter
from datetime import datetime, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.config import DATABASE_NAME, COLLECTION_NAME, REPORT_COLLECTION


def generate_axe1_report(db) -> dict:
    """
    Agrège les résultats NLP de tous les documents traités.
    Retourne un rapport complet sous forme de dict.
    """
    collection = db[COLLECTION_NAME]

    # Récupérer uniquement les documents traités par Axe 1
    processed_docs = list(collection.find(
        {"processed": True, "nlp_results.axe": 1},
        {"nlp_results": 1, "post_id": 1, "forum": 1, "source": 1}
    ))

    print(f"\n📊 Génération du rapport sur {len(processed_docs)} documents traités...")

    if not processed_docs:
        print("   ⚠️  Aucun document traité trouvé. Lance d'abord pipeline.py")
        return {}

    # Agréger toutes les entités et relations
    all_entities = []
    all_adverse = []
    all_relations = []
    forum_counts = Counter()
    source_counts = Counter()

    for doc in processed_docs:
        nlp = doc.get("nlp_results", {})
        all_entities.extend(nlp.get("entities", []))
        all_adverse.extend(nlp.get("adverse_effects", []))
        all_relations.extend(nlp.get("relations", []))
        forum_counts[doc.get("forum", "unknown")] += 1
        source_counts[doc.get("source", "unknown")] += 1

    # --- Statistiques entités ---
    entity_types = Counter(e.get("label", "UNKNOWN") for e in all_entities)
    top_drugs = Counter(
        e["text"].lower() for e in all_entities
        if any(k in e.get("label", "").upper() for k in ["DRUG", "CHEMICAL"])
    ).most_common(20)
    top_symptoms = Counter(
        e["text"].lower() for e in all_entities
        if any(k in e.get("label", "").upper()
               for k in ["SYMPTOM", "DISEASE", "SIGN", "DISORDER"])
    ).most_common(20)

    # --- Signaux pharmacovigilance ---
    drug_effect_pairs = Counter(
        (r.get("drug", "").lower(), r.get("symptom", "").lower())
        for r in all_adverse
    ).most_common(20)

    # Médicaments les plus impliqués dans des effets indésirables
    drugs_in_adverse = Counter(
        r.get("drug", "").lower() for r in all_adverse
    ).most_common(10)

    # Symptômes les plus signalés comme effets indésirables
    symptoms_in_adverse = Counter(
        r.get("symptom", "").lower() for r in all_adverse
    ).most_common(10)

    # --- Relations par type ---
    relation_types = Counter(
        r.get("predicted_relation", "unknown") for r in all_relations
    )

    # --- Rapport final ---
    report = {
        "_id": "axe1_latest",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_documents_processed": len(processed_docs),
            "total_entities_extracted": len(all_entities),
            "total_relations_classified": len(all_relations),
            "total_adverse_effects_detected": len(all_adverse),
            "avg_entities_per_doc": round(len(all_entities) / len(processed_docs), 2),
            "avg_adverse_per_doc": round(len(all_adverse) / len(processed_docs), 2)
        },
        "entity_distribution": dict(entity_types),
        "top_drugs_mentioned": top_drugs,
        "top_symptoms_mentioned": top_symptoms,
        "relation_distribution": dict(relation_types),
        "pharmacovigilance_signals": {
            "top_drug_effect_pairs": [
                {"drug": d, "effect": e, "count": c}
                for (d, e), c in drug_effect_pairs
            ],
            "most_implicated_drugs": drugs_in_adverse,
            "most_reported_adverse_symptoms": symptoms_in_adverse
        },
        "data_sources": {
            "by_forum": dict(forum_counts),
            "by_source": dict(source_counts)
        }
    }

    return report


def save_report(report: dict, db, output_dir: str = "output"):
    """Sauvegarde le rapport dans MongoDB et en JSON/CSV."""
    if not report:
        return

    # Créer le dossier de sortie
    os.makedirs(output_dir, exist_ok=True)

    # Sauvegarder dans MongoDB
    report_collection = db[REPORT_COLLECTION]
    report_collection.replace_one(
        {"_id": "axe1_latest"},
        report,
        upsert=True
    )
    print(f"   ✓ Rapport sauvegardé dans MongoDB collection '{REPORT_COLLECTION}'")

    # Export JSON
    json_path = os.path.join(output_dir, "axe1_report.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    print(f"   ✓ Rapport JSON exporté : {json_path}")

    # Export CSV — Top Drug-Effect pairs
    if report.get("pharmacovigilance_signals", {}).get("top_drug_effect_pairs"):
        pairs = report["pharmacovigilance_signals"]["top_drug_effect_pairs"]
        df_pairs = pd.DataFrame(pairs)
        csv_path = os.path.join(output_dir, "axe1_pharmacovigilance_signals.csv")
        df_pairs.to_csv(csv_path, index=False, encoding="utf-8")
        print(f"   ✓ Signaux pharmacovigilance CSV : {csv_path}")

    # Export CSV — Top entités
    summary_data = {
        "Médicaments les + mentionnés": report.get("top_drugs_mentioned", []),
        "Symptômes les + mentionnés": report.get("top_symptoms_mentioned", [])
    }
    for label, data in summary_data.items():
        if data:
            df = pd.DataFrame(data, columns=["entite", "count"])
            safe_label = label.replace(" ", "_").replace("+", "plus")
            path = os.path.join(output_dir, f"axe1_{safe_label}.csv")
            df.to_csv(path, index=False, encoding="utf-8")


def print_report_summary(report: dict):
    """Affiche un résumé lisible du rapport."""
    if not report:
        return

    s = report.get("summary", {})
    print("\n" + "="*60)
    print("RAPPORT FINAL — AXE 1 NLP BIOMÉDICAL")
    print("="*60)
    print(f"\n📌 Documents traités          : {s.get('total_documents_processed')}")
    print(f"📌 Entités extraites           : {s.get('total_entities_extracted')}")
    print(f"📌 Relations classifiées       : {s.get('total_relations_classified')}")
    print(f"📌 Effets indésirables détectés: {s.get('total_adverse_effects_detected')}")
    print(f"📌 Moy. entités / document     : {s.get('avg_entities_per_doc')}")

    print("\n📊 Distribution des entités :")
    for label, count in report.get("entity_distribution", {}).items():
        print(f"   {label:<30} : {count}")

    print("\n💊 Top 10 médicaments mentionnés :")
    for drug, count in report.get("top_drugs_mentioned", [])[:10]:
        print(f"   {drug:<25} : {count} fois")

    print("\n🤒 Top 10 symptômes mentionnés :")
    for sym, count in report.get("top_symptoms_mentioned", [])[:10]:
        print(f"   {sym:<25} : {count} fois")

    print("\n🚨 Top Signaux Pharmacovigilance (Drug → Adverse Effect) :")
    for pair in report.get("pharmacovigilance_signals", {}).get("top_drug_effect_pairs", [])[:10]:
        print(f"   {pair['drug']:<20} → {pair['effect']:<20} ({pair['count']} cas)")

    print("\n" + "="*60)


if __name__ == "__main__":
    from pymongo import MongoClient
    from config.config import MONGO_URI

    client = MongoClient(MONGO_URI)
    db = client[DATABASE_NAME]

    report = generate_axe1_report(db)
    save_report(report, db)
    print_report_summary(report)

    print("\n✓ Étape 7 — Rapport généré avec succès")
