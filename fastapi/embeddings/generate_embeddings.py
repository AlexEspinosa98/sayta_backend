import json
import numpy as np
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

# ===============================
# CONFIG
# ===============================

JSON_PATH = "dataset_clean.json"
TXT_PATH = "corpus_embeddings.txt"
OUTPUT_EMBEDDINGS = "embeddings.npy"
OUTPUT_METADATA = "metadata.json"

MODEL_NAME = "intfloat/multilingual-e5-base"

# ===============================
# CARGAR MODELO
# ===============================

print("🔎 Cargando modelo...")
model = SentenceTransformer(MODEL_NAME)

# ===============================
# CARGAR JSON
# ===============================

with open(JSON_PATH, "r", encoding="utf-8") as f:
    dataset = json.load(f)

# ===============================
# CARGAR TXT
# ===============================

with open(TXT_PATH, "r", encoding="utf-8") as f:
    txt_lines = [line.strip() for line in f.readlines() if line.strip()]

txt_set = set(txt_lines)

# ===============================
# CONSTRUIR TEXTOS
# ===============================

def build_text(entry):
    parts = ["passage:"]

    lemma = entry.get("lemma", "")
    definicion = entry.get("definicion", "")
    pos = entry.get("pos", "")

    parts.append(f"palabra: {lemma}")
    parts.append(f"categoria: {pos}")
    parts.append(f"definicion: {definicion}")

    # Si existe en TXT, lo agregamos como refuerzo
    if lemma in txt_set:
        parts.append(f"contexto_adicional: {lemma}")

    return " | ".join(parts)

texts = [build_text(e) for e in dataset]

# ===============================
# GENERAR EMBEDDINGS
# ===============================

print("⚡ Generando embeddings...")
embeddings = model.encode(
    texts,
    batch_size=32,
    show_progress_bar=True,
    normalize_embeddings=True
)

embeddings = np.array(embeddings)

# ===============================
# GUARDAR
# ===============================

np.save(OUTPUT_EMBEDDINGS, embeddings)

with open(OUTPUT_METADATA, "w", encoding="utf-8") as f:
    json.dump(dataset, f, ensure_ascii=False, indent=2)

print("✅ Embeddings generados.")
print("Dimensión:", embeddings.shape[1])