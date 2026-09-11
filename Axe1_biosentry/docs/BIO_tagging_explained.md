# BIO Tagging — Explication Détaillée

## Qu'est-ce que le BIO Tagging ?

Le **schéma BIO** (aussi appelé IOB) est la méthode standard pour annoter
des séquences de texte en NLP, particulièrement pour la **Named Entity Recognition (NER)**.

Chaque token (mot ou sous-token) reçoit un label :
- **B-XXX** : *Beginning* — premier token d'une entité de type XXX
- **I-XXX** : *Inside* — token de continuation (à l'intérieur) d'une entité
- **O**     : *Outside* — token qui ne fait partie d'aucune entité

---

## Exemple concret avec BioBERT

### Phrase d'entrée :
> "I took ibuprofen 400mg twice daily and developed severe nausea."

### Annotation BIO attendue :

| Token       | Label BIO    | Signification                       |
|-------------|--------------|-------------------------------------|
| I           | O            | mot commun, pas une entité          |
| took        | O            | verbe, pas une entité               |
| ibuprofen   | **B-DRUG**   | début du médicament                 |
| 400mg       | **I-DRUG**   | continuation (posologie du médicament) |
| twice       | O            |                                     |
| daily       | O            |                                     |
| and         | O            |                                     |
| developed   | O            |                                     |
| severe      | **B-SEVERITY** | modificateur de sévérité          |
| nausea      | **B-SYMPTOM** | début du symptôme                  |
| .           | O            |                                     |

### Entités extraites après agrégation :
- `"ibuprofen 400mg"` → **DRUG**
- `"severe"` → **SEVERITY**  
- `"nausea"` → **SYMPTOM**

---

## Pourquoi sous-tokens avec BioBERT ?

BERT utilise la tokenisation **WordPiece** qui découpe les mots rares
en sous-mots. Par exemple :

```
"ibuprofen" → ["ib", "##up", "##ro", "##fen"]
"acetaminophen" → ["ace", "##tam", "##ino", "##phen"]
```

Le `##` signifie "continuation du mot précédent".

### Problème sans agrégation :
```
ib       → B-DRUG
##up     → I-DRUG
##ro     → I-DRUG
##fen    → I-DRUG
```
→ 4 entités séparées, difficile à utiliser

### Solution avec `aggregation_strategy="simple"` :
```
"ibuprofen" → DRUG (score = moyenne des scores des 4 sous-tokens)
```
→ 1 entité propre

---

## Types d'entités dans d4data/biomedical-ner-all

| Label          | Description                            | Exemples                         |
|----------------|----------------------------------------|----------------------------------|
| DRUG           | Médicament, substance active           | ibuprofen, metformin, aspirin    |
| DISEASE        | Maladie, pathologie diagnostiquée      | diabetes, gastritis, hypertension |
| SYMPTOM        | Symptôme rapporté par le patient       | nausea, dizziness, fatigue       |
| Sign_symptom   | Signe clinique observable              | fever, rash, swelling            |
| ADR            | Adverse Drug Reaction (direct)         | hepatotoxicity, bradycardia      |
| DOSAGE         | Posologie                              | 400mg, twice daily               |
| DURATION       | Durée du traitement                    | for 3 weeks, after 5 days        |
| ROUTE          | Voie d'administration                  | oral, intravenous, topical       |

---

## Pourquoi ce modèle pour Reddit/forums patients ?

Le modèle `d4data/biomedical-ner-all` est particulièrement adapté car :

1. **Entraîné sur du texte patient** (pas seulement des articles scientifiques)
2. **Reconnaît le vocabulaire profane** : "tummy ache" → SYMPTOM
3. **Multilabel** : gère simultanément DRUG + SYMPTOM + DISEASE dans une même phrase
4. **Adapté aux mentions informelles** de médicaments (noms commerciaux inclus)

---

## Flux complet dans Bio-Sentry

```
Texte Reddit brut
      ↓
Nettoyage (URLs, markdown)
      ↓
Tokenisation en phrases (NLTK)
      ↓
Tokenisation WordPiece (BioBERT tokenizer)
      ↓
Prédiction BIO token par token
  ["ib"→B-DRUG, "##up"→I-DRUG, "##ro"→I-DRUG, ...]
      ↓
Agrégation simple → entité complète
  "ibuprofen" → DRUG (score: 0.97)
      ↓
Filtrage par score ≥ 0.75
      ↓
Extraction paires (DRUG, SYMPTOM) co-occurrentes
      ↓
Classification relation (zero-shot NLI)
  "adverse drug effect" / "symptom of disease" / ...
      ↓
Signal pharmacovigilance → MongoDB
```
