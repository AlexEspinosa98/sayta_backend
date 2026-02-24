import faiss
import numpy as np
import json
from sentence_transformers import SentenceTransformer

MODEL_NAME = "intfloat/multilingual-e5-base"

print("🔎 Cargando modelo...")
model = SentenceTransformer(MODEL_NAME)

print("📦 Cargando índice...")
index = faiss.read_index("faiss_index.bin")

with open("metadata.json", "r", encoding="utf-8") as f:
    metadata = json.load(f)

while True:
    query_text = input("\nConsulta: ")
    if not query_text:
        break

    query = "query: " + query_text
    query_embedding = model.encode([query], normalize_embeddings=True)
    query_embedding = np.array(query_embedding).astype("float32")

    D, I = index.search(query_embedding, 5)

    print("\nResultados:")
    for idx in I[0]:
        print("-", metadata[idx]["lemma"], "→", metadata[idx]["definicion"])