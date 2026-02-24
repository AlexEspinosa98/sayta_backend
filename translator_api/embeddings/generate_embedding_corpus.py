import json

INPUT_JSON = "dataset_clean.json"
OUTPUT_CORPUS = "corpus_embeddings.txt"

with open(INPUT_JSON, "r", encoding="utf-8") as f:
    data = json.load(f)

corpus = []

for entry in data:
    lemma = entry["lemma"]
    definicion = entry["definicion"]
    sinonimos = entry["sinonimos"]

    if not definicion:
        continue

    # 1️⃣ Frase principal
    corpus.append(f"{lemma} {definicion}")

    # 2️⃣ Lemma solo
    corpus.append(lemma)

    # 3️⃣ Definición sola
    corpus.append(definicion)

    # 4️⃣ Sinonimias
    for s in sinonimos:
        corpus.append(f"{lemma} {s}")
        corpus.append(f"{s} {lemma}")

# Guardar
with open(OUTPUT_CORPUS, "w", encoding="utf-8") as f:
    for line in corpus:
        f.write(line.strip() + "\n")

print("Corpus generado.")
print("Total líneas:", len(corpus))