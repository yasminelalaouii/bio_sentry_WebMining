"""
PIPELINE COMPLET — Axe 1 Bio-Sentry NLP Biomédical
====================================================
Ce script orchestre toutes les étapes dans l'ordre :

  1. Connexion MongoDB + chargement des données
  2. Prétraitement du texte (nettoyage + tokenisation en phrases)
  3. Chargement du modèle BioBERT NER
  4. Extraction NER (BIO tagging → entités médicales)
  5. Classification des relations Drug → Symptom (zero-shot NLI)
  6. Sauvegarde des résultats dans MongoDB (processed=True)
  7. Génération du rapport statistique final

Usage :
  python src/pipeline.py
  python src/pipeline.py --demo       (test sur 5 documents)
  python src/pipeline.py --skip-rel   (sauter la classification de relations)
"""

import sys
import os
import argparse
import time

# Assure que les imports relatifs fonctionnent
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import MongoClient

from config.config import (MONGO_URI, DATABASE_NAME, COLLECTION_NAME)
from src.load_data import connect_mongodb, load_documents, print_sample
from src.preprocess import preprocess_documents
from src.ner_biobert import load_ner_model, run_ner_on_documents
from src.relation_classifier import load_relation_classifier, classify_all_documents
from src.save_results import save_documents_to_mongodb, verify_saved_documents
from src.report import generate_axe1_report, save_report, print_report_summary


# Renommer les modules pour les imports (correspondance nom fichier → import)
import importlib
import types

def _import_module(filepath, name):
    spec = importlib.util.spec_from_file_location(name, filepath)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

base = os.path.dirname(os.path.abspath(__file__))

_load     = _import_module(os.path.join(base, "01_load_data.py"), "load_data")
_prep     = _import_module(os.path.join(base, "02_preprocess.py"), "preprocess")
_ner      = _import_module(os.path.join(base, "03_ner_biobert.py"), "ner_biobert")
_rel      = _import_module(os.path.join(base, "05_relation_classifier.py"), "relation_classifier")
_save     = _import_module(os.path.join(base, "06_save_results.py"), "save_results")
_report   = _import_module(os.path.join(base, "07_report.py"), "report")


def run_pipeline(demo_mode: bool = False, skip_relations: bool = False):
    """
    Exécute le pipeline Axe 1 complet.
    
    Args:
        demo_mode      : si True, traite seulement 5 documents (test rapide)
        skip_relations : si True, saute la classification de relations (plus rapide)
    """
    start_total = time.time()

    print("\n" + "="*70)
    print("  BIO-SENTRY — AXE 1 : NLP BIOMÉDICAL")
    print("  Pipeline complet : NER + Relations + Pharmacovigilance")
    print("="*70)
    if demo_mode:
        print("  ⚡ MODE DÉMO : traitement limité à 5 documents")
    print()

    # ── ÉTAPE 1 : Chargement MongoDB ─────────────────────────────────────────
    print("━━━ ÉTAPE 1/7 : Connexion MongoDB & Chargement ━━━")
    client = _load.connect_mongodb()
    documents, collection = _load.load_documents(client)

    if not documents:
        print("\n❌ Aucun document à traiter. Pipeline arrêté.")
        return

    if demo_mode:
        documents = documents[:5]
        print(f"   Mode démo : {len(documents)} documents sélectionnés")

    _load.print_sample(documents, n=1)
    t1 = time.time()

    # ── ÉTAPE 2 : Prétraitement ───────────────────────────────────────────────
    print(f"\n━━━ ÉTAPE 2/7 : Prétraitement du texte ━━━")
    documents = _prep.preprocess_documents(documents)
    t2 = time.time()
    print(f"   ⏱️  Durée : {t2-t1:.1f}s")

    # ── ÉTAPE 3 : Chargement du modèle NER ───────────────────────────────────
    print(f"\n━━━ ÉTAPE 3/7 : Chargement BioBERT NER ━━━")
    ner_pipeline, tokenizer, model = _ner.load_ner_model()
    t3 = time.time()
    print(f"   ⏱️  Durée : {t3-t2:.1f}s")

    # ── ÉTAPE 4 : Extraction NER ──────────────────────────────────────────────
    print(f"\n━━━ ÉTAPE 4/7 : Extraction NER (BIO Tagging) ━━━")
    documents = _ner.run_ner_on_documents(documents, ner_pipeline)
    t4 = time.time()
    print(f"   ⏱️  Durée : {t4-t3:.1f}s")

    # ── ÉTAPE 5 : Classification des relations ────────────────────────────────
    if not skip_relations:
        print(f"\n━━━ ÉTAPE 5/7 : Classification Relations Drug→Symptom ━━━")
        relation_classifier = _rel.load_relation_classifier()
        documents = _rel.classify_all_documents(documents, relation_classifier)
        t5 = time.time()
        print(f"   ⏱️  Durée : {t5-t4:.1f}s")
    else:
        print(f"\n━━━ ÉTAPE 5/7 : Classification Relations [SKIPPED] ━━━")
        for doc in documents:
            doc["relations"] = []
            doc["adverse_effects_detected"] = []
        t5 = time.time()

    # ── ÉTAPE 6 : Sauvegarde MongoDB ──────────────────────────────────────────
    print(f"\n━━━ ÉTAPE 6/7 : Sauvegarde dans MongoDB ━━━")
    stats = _save.save_documents_to_mongodb(documents, collection)
    post_ids = [d["post_id"] for d in documents]
    _save.verify_saved_documents(collection, post_ids, n_sample=2)
    t6 = time.time()
    print(f"   ⏱️  Durée : {t6-t5:.1f}s")

    # ── ÉTAPE 7 : Rapport ─────────────────────────────────────────────────────
    print(f"\n━━━ ÉTAPE 7/7 : Génération du rapport ━━━")
    db = client[DATABASE_NAME]
    report = _report.generate_axe1_report(db)
    _report.save_report(report, db)
    _report.print_report_summary(report)
    t7 = time.time()

    # ── Résumé ────────────────────────────────────────────────────────────────
    total_time = round(time.time() - start_total, 1)
    print(f"\n{'='*70}")
    print(f"  ✅ PIPELINE AXE 1 TERMINÉ EN {total_time}s")
    print(f"{'='*70}")
    print(f"  Documents traités : {len(documents)}")
    print(f"  Résultats dans MongoDB collection '{COLLECTION_NAME}' (champ nlp_results)")
    print(f"  Rapport dans : output/axe1_report.json")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Bio-Sentry Axe 1 — Pipeline NLP Biomédical"
    )
    parser.add_argument(
        "--demo", action="store_true",
        help="Mode démo : traite seulement 5 documents"
    )
    parser.add_argument(
        "--skip-rel", action="store_true",
        help="Sauter la classification de relations (plus rapide)"
    )
    args = parser.parse_args()

    run_pipeline(demo_mode=args.demo, skip_relations=args.skip_rel)
