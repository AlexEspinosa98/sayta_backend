import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

INPUT_PATH = BASE_DIR / "data" / "processed" / "ette_es_dictionary_index_clean.json"
OUTPUT_PATH = BASE_DIR / "data" / "training" / "ette_es.tsv"

def main():
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        dictionary = json.load(f)

    pairs = []

    for lemma, data in dictionary.items():
        for t in data["translations"]:
            pairs.append(f"{lemma}\t{t}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        for line in pairs:
            f.write(line + "\n")

    print(f"[OK] Dataset paralelo generado: {len(pairs)} pares")
    print("[INFO] Archivo listo para entrenamiento NLP")

if __name__ == "__main__":
    main()
