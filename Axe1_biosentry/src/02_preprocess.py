"""
ÉTAPE 2 — Préparation du texte pour le NLP médical
====================================================
Ce script prend les documents MongoDB bruts et les prépare
pour l'entrée dans BioBERT :
  - Combine title + text
  - Nettoie le bruit résiduel (URLs, newlines...)
  - Découpe en phrases (NLTK sent_tokenize)
  - Filtre les phrases trop courtes ou trop longues

Usage : python src/02_preprocess.py
"""

import re
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import nltk

# Télécharger les ressources NLTK si absentes
for resource in ['punkt', 'punkt_tab']:
    try:
        nltk.data.find(f'tokenizers/{resource}')
    except LookupError:
        print(f"Téléchargement NLTK : {resource}")
        nltk.download(resource, quiet=True)

from nltk.tokenize import sent_tokenize


# Longueurs de phrases (en mots)
MIN_SENTENCE_WORDS = 5    # Phrases trop courtes = bruit
MAX_SENTENCE_WORDS = 400  # Limite BERT 512 tokens ≈ 400 mots


def clean_text(text: str) -> str:
    """
    Nettoie le texte brut de Reddit/forum.
    
    Supprime :
      - URLs résiduelles
      - Sauts de ligne multiples
      - Espaces multiples
      - Caractères spéciaux Reddit (markdown basique)
    """
    if not text:
        return ""

    # Supprimer les URLs
    text = re.sub(r'http\S+|www\.\S+', '', text)

    # Supprimer le markdown Reddit simple (**bold**, *italic*, ~~strike~~)
    text = re.sub(r'\*{1,2}(.*?)\*{1,2}', r'\1', text)
    text = re.sub(r'~~(.*?)~~', r'\1', text)
    text = re.sub(r'#{1,6}\s', '', text)

    # Remplacer sauts de ligne par espace
    text = re.sub(r'\n+', ' ', text)

    # Supprimer espaces multiples
    text = re.sub(r'\s+', ' ', text)

    return text.strip()


def split_into_sentences(text: str) -> list:
    """
    Découpe le texte en phrases avec NLTK.
    
    Filtre les phrases trop courtes (bruit) ou trop longues (> limite BERT).
    Les phrases trop longues sont tronquées plutôt que supprimées.
    """
    if not text:
        return []

    sentences = sent_tokenize(text)
    result = []

    for sent in sentences:
        words = sent.split()
        n_words = len(words)

        # Ignorer les phrases trop courtes
        if n_words < MIN_SENTENCE_WORDS:
            continue

        # Tronquer les phrases trop longues pour BERT
        if n_words > MAX_SENTENCE_WORDS:
            sent = " ".join(words[:MAX_SENTENCE_WORDS])

        result.append(sent)

    return result


def prepare_document(doc: dict) -> dict:
    """
    Prépare un document MongoDB pour le pipeline NLP.
    
    Retourne le document enrichi avec :
      - full_text_clean : texte nettoyé
      - sentences       : liste de phrases
      - sentence_count  : nombre de phrases
    """
    title = doc.get("title", "") or ""
    text = doc.get("text", "") or ""

    # Combiner titre et corps
    if title and text:
        combined = f"{title}. {text}"
    elif title:
        combined = title
    else:
        combined = text

    # Nettoyer
    clean = clean_text(combined)

    # Découper en phrases
    sentences = split_into_sentences(clean)

    doc["full_text_clean"] = clean
    doc["sentences"] = sentences
    doc["sentence_count"] = len(sentences)

    return doc


def preprocess_documents(documents: list) -> list:
    """Applique la préparation sur toute la liste de documents."""
    print(f"\n🔧 Prétraitement de {len(documents)} documents...")

    processed = []
    empty_count = 0

    for doc in documents:
        doc = prepare_document(doc)
        if doc["sentence_count"] == 0:
            empty_count += 1
        processed.append(doc)

    total_sentences = sum(d["sentence_count"] for d in processed)
    avg_sentences = total_sentences / len(processed) if processed else 0

    print(f"   Total de phrases extraites : {total_sentences}")
    print(f"   Moyenne par document       : {avg_sentences:.1f} phrases")
    print(f"   Documents sans phrases     : {empty_count}")

    return processed


# ── Démonstration standalone ─────────────────────────────────────────────────
if __name__ == "__main__":
    sample_doc = {
        "post_id": "demo_001",
        "title": "Had a really weird experience in ER after taking ibuprofen",
        "text": (
            "I've been taking ibuprofen 400mg twice a day for about a week for "
            "my back pain. Yesterday I started feeling really dizzy and nauseous. "
            "My doctor said it might be gastritis. Has anyone else experienced this? "
            "https://somelink.com/removed\n\n"
            "The ER doctor prescribed omeprazole and told me to stop the ibuprofen."
        )
    }

    result = prepare_document(sample_doc)

    print("=== RÉSULTAT DU PRÉTRAITEMENT ===\n")
    print(f"Texte nettoyé :\n  {result['full_text_clean'][:200]}...\n")
    print(f"Nombre de phrases : {result['sentence_count']}\n")
    for i, s in enumerate(result["sentences"]):
        print(f"  [{i}] {s}")

    print("\n✓ Étape 2 — Prétraitement OK")
