"""
ÉTAPE 6 — Sauvegarde des résultats dans MongoDB
================================================
Après le traitement NLP complet (NER + relations), ce script
met à jour chaque document MongoDB avec :
  - nlp_results.entities        : entités extraites
  - nlp_results.relations       : relations classifiées
  - nlp_results.adverse_effects : effets indésirables détectés
  - processed = True            : marque le document comme traité

Utilise bulk_write pour les performances (une seule requête groupée).

Usage : python src/06_save_results.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import UpdateOne
from datetime import datetime, timezone
from config.config import NER_MODEL


def save_documents_to_mongodb(documents: list, collection) -> dict:
    """
    Sauvegarde les résultats NLP dans MongoDB en bulk.
    
    Pour chaque document traité :
      - Met à jour nlp_results avec entités + relations
      - Passe processed = True pour ne pas le retraiter
    
    Retourne les statistiques de la sauvegarde.
    """
    if not documents:
        print("⚠️  Aucun document à sauvegarder")
        return {}

    print(f"\n💾 Sauvegarde de {len(documents)} documents dans MongoDB...")

    operations = []
    now = datetime.now(timezone.utc)

    for doc in documents:
        entities = doc.get("entities_extracted", [])
        relations = doc.get("relations", [])
        adverse_effects = doc.get("adverse_effects_detected", [])

        # Nettoyage des objets non-sérialisables MongoDB
        # (les scores float numpy → float natif)
        entities_clean = _clean_for_mongo(entities)
        relations_clean = _clean_for_mongo(relations)
        adverse_clean = _clean_for_mongo(adverse_effects)

        update = {
            "$set": {
                "processed": True,
                "nlp_results": {
                    "entities": entities_clean,
                    "entity_count": len(entities_clean),
                    "relations": relations_clean,
                    "relation_count": len(relations_clean),
                    "adverse_effects": adverse_clean,
                    "adverse_effects_count": len(adverse_clean),
                    "processed_at": now,
                    "model_used": NER_MODEL,
                    "axe": 1
                }
            }
        }

        operations.append(
            UpdateOne({"post_id": doc["post_id"]}, update, upsert=False)
        )

    # Exécution en bulk (une seule requête réseau)
    result = collection.bulk_write(operations, ordered=False)

    stats = {
        "matched": result.matched_count,
        "modified": result.modified_count,
        "errors": len(result.bulk_api_result.get("writeErrors", []))
    }

    print(f"   ✓ Documents matchés  : {stats['matched']}")
    print(f"   ✓ Documents modifiés : {stats['modified']}")
    if stats["errors"]:
        print(f"   ⚠️  Erreurs           : {stats['errors']}")

    return stats


def _clean_for_mongo(obj):
    """
    Convertit récursivement les types numpy/non-sérialisables
    en types Python natifs pour MongoDB.
    """
    if isinstance(obj, list):
        return [_clean_for_mongo(item) for item in obj]
    elif isinstance(obj, dict):
        return {k: _clean_for_mongo(v) for k, v in obj.items()}
    elif hasattr(obj, 'item'):  # numpy scalar
        return obj.item()
    else:
        return obj


def verify_saved_documents(collection, post_ids: list, n_sample: int = 3):
    """
    Vérifie que les documents ont bien été sauvegardés en
    récupérant quelques exemples depuis MongoDB.
    """
    print(f"\n🔎 Vérification de {min(n_sample, len(post_ids))} documents...")

    for post_id in post_ids[:n_sample]:
        doc = collection.find_one(
            {"post_id": post_id},
            {"post_id": 1, "processed": 1, "nlp_results": 1}
        )
        if doc:
            nlp = doc.get("nlp_results", {})
            print(f"\n  post_id : {post_id}")
            print(f"    processed          : {doc.get('processed')}")
            print(f"    entity_count       : {nlp.get('entity_count', 0)}")
            print(f"    adverse_effects    : {nlp.get('adverse_effects_count', 0)}")
            print(f"    model_used         : {nlp.get('model_used', 'N/A')}")

            # Afficher les effets indésirables détectés
            adverse = nlp.get("adverse_effects", [])
            if adverse:
                print(f"    Effets indésirables :")
                for ae in adverse[:3]:
                    print(f"      💊 {ae['drug']} → 🤒 {ae['symptom']} "
                          f"(conf: {ae['confidence']})")
        else:
            print(f"  ⚠️  post_id {post_id} non trouvé dans MongoDB")


# ── Démonstration standalone ─────────────────────────────────────────────────
if __name__ == "__main__":
    from src.load_data import connect_mongodb, load_documents

    client = connect_mongodb()
    documents, collection = load_documents(client)

    if documents:
        # Simuler des résultats NLP pour la démo
        for doc in documents[:2]:
            doc["entities_extracted"] = [
                {"text": "ibuprofen", "label": "DRUG", "score": 0.95,
                 "sentence_idx": 0, "sentence": "I took ibuprofen."}
            ]
            doc["relations"] = []
            doc["adverse_effects_detected"] = []

        stats = save_documents_to_mongodb(documents[:2], collection)
        post_ids = [d["post_id"] for d in documents[:2]]
        verify_saved_documents(collection, post_ids)
    else:
        print("Aucun document à traiter pour la démo.")

    print("\n✓ Étape 6 — Sauvegarde MongoDB OK")
