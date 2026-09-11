"""
ÉTAPE 1 — Chargement des données depuis MongoDB
================================================
Ce script se connecte à MongoDB et charge les documents
à traiter (processed=False, language="en").

Usage : python src/01_load_data.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pymongo import MongoClient
from config.config import (MONGO_URI, DATABASE_NAME, COLLECTION_NAME,
                           MONGO_FILTER, BATCH_SIZE)


def connect_mongodb():
    """Crée et retourne la connexion MongoDB."""
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        # Tester la connexion
        client.server_info()
        print(f"✓ Connecté à MongoDB : {MONGO_URI}")
        return client
    except Exception as e:
        print(f"✗ Erreur de connexion MongoDB : {e}")
        print("  Vérifie que MongoDB est démarré et que MONGO_URI est correct dans config/config.py")
        sys.exit(1)


def load_documents(client):
    """
    Charge les documents depuis MongoDB selon les filtres définis.
    
    Retourne une liste de documents avec uniquement les champs nécessaires.
    """
    db = client[DATABASE_NAME]
    collection = db[COLLECTION_NAME]

    # Champs à récupérer (projection)
    projection = {
        "post_id": 1,
        "title": 1,
        "text": 1,
        "drugs_mentioned": 1,
        "forum": 1,
        "source": 1,
        "date_scraped": 1,
        "language": 1,
        "num_comments": 1,
        "url": 1
    }

    cursor = collection.find(MONGO_FILTER, projection)

    if BATCH_SIZE:
        cursor = cursor.limit(BATCH_SIZE)

    documents = list(cursor)

    print(f"\n📦 Documents chargés : {len(documents)}")
    print(f"   Filtre appliqué : {MONGO_FILTER}")

    if len(documents) == 0:
        print("\n⚠️  Aucun document trouvé avec ce filtre.")
        print("   Possible raison : tous les documents ont déjà processed=True")
        print("   Pour re-traiter, fais : db.posts.updateMany({}, {$set: {processed: false}})")

    return documents, collection


def print_sample(documents, n=2):
    """Affiche un aperçu des premiers documents chargés."""
    print(f"\n--- Aperçu des {min(n, len(documents))} premiers documents ---")
    for doc in documents[:n]:
        print(f"\n  post_id      : {doc.get('post_id')}")
        print(f"  forum        : {doc.get('forum')}")
        print(f"  title        : {str(doc.get('title', ''))[:80]}...")
        print(f"  drugs_mentioned: {doc.get('drugs_mentioned', [])}")
        text_preview = str(doc.get('text', ''))[:120].replace('\n', ' ')
        print(f"  text (début) : {text_preview}...")


if __name__ == "__main__":
    client = connect_mongodb()
    documents, collection = load_documents(client)
    print_sample(documents)
    print("\n✓ Étape 1 terminée — données chargées avec succès.")
