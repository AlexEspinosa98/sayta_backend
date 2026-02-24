import faiss
import numpy as np
import json

# ===============================
# CONFIG
# ===============================

EMBEDDINGS_PATH = "embeddings.npy"
INDEX_OUTPUT = "faiss_index.bin"
METADATA_PATH = "metadata.json"

# ===============================
# CARGAR EMBEDDINGS
# ===============================

print("📦 Cargando embeddings...")
embeddings = np.load(EMBEDDINGS_PATH).astype("float32")

dimension = embeddings.shape[1]
print("Dimensión:", dimension)
print("Total vectores:", embeddings.shape[0])

# ===============================
# CREAR ÍNDICE HNSW
# ===============================

print("🧠 Creando índice HNSW...")

M = 32  # conexiones por nodo (16-64 recomendado)
index = faiss.IndexHNSWFlat(dimension, M)

index.hnsw.efConstruction = 200
index.hnsw.efSearch = 64

index.add(embeddings)

# ===============================
# GUARDAR ÍNDICE
# ===============================

faiss.write_index(index, INDEX_OUTPUT)

print("✅ Índice FAISS guardado:", INDEX_OUTPUT)