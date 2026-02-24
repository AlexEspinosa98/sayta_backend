import faiss
import numpy as np
import json
from sentence_transformers import SentenceTransformer
from rapidfuzz import fuzz

MODEL_NAME = "intfloat/multilingual-e5-base"

print(" Cargando modelo...")
model = SentenceTransformer(MODEL_NAME)

print(" Cargando índice...")
index = faiss.read_index("faiss_index.bin")

with open("metadata.json", "r", encoding="utf-8") as f:
    metadata = json.load(f)

def hybrid_score(query, candidate, semantic_score):
    lemma = candidate["lemma"]

    # 1️⃣ Exact match
    exact_match = 1.0 if query == lemma else 0.0

    # 2️⃣ Similaridad léxica normalizada (0–1)
    levenshtein_sim = fuzz.ratio(query, lemma) / 100.0

    # 3️⃣ Bonus por prefijo
    prefix_bonus = 1.0 if lemma.startswith(query) else 0.0

    # 4️⃣ Score final ponderado
    final_score = (
        0.60 * semantic_score +
        0.25 * exact_match +
        0.10 * levenshtein_sim +
        0.05 * prefix_bonus
    )

    return final_score

while True:
    query_text = input("\nConsulta: ").strip()
    if not query_text:
        break

    query_embedding = model.encode(
        ["query: " + query_text],
        normalize_embeddings=True
    ).astype("float32")

    # Traemos más candidatos para re-ranking
    D, I = index.search(query_embedding, 20)

    candidates = []
    for rank, idx in enumerate(I[0]):
        semantic_score = 1 - D[0][rank]  # porque usamos vectores normalizados
        entry = metadata[idx]
        score = hybrid_score(query_text, entry, semantic_score)
        candidates.append((score, entry))

    # Ordenar por score híbrido
    candidates.sort(key=lambda x: x[0], reverse=True)

    print("\n Resultados híbridos:")
    for score, entry in candidates[:5]:
        print(f"- {entry['lemma']} → {entry['definicion']} (score={score:.4f})")