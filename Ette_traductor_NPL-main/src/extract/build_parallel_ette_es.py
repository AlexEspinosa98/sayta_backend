import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

INPUT_PATH = BASE_DIR / "data" / "processed" / "ette_es_normalized.json"
OUTPUT_PATH = BASE_DIR / "data" / "processed" / "ette_es_parallel.json"

QUOTE_PATTERN = re.compile(r"[“\"]([^”\"]+)[”\"]")
CLEAN_PATTERN = re.compile(r"[^a-zA-ZáéíóúñüÁÉÍÓÚÑÜ\s,;]")

def normalize_text(text: str) -> str:
    text = text.lower()
    text = CLEAN_PATTERN.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def extract_translations(definition: str):
    matches = QUOTE_PATTERN.findall(definition)
    if matches:
        return matches

    # fallback: primera frase española
    parts = re.split(r"\.|;", definition)
    if parts:
        return [parts[0]]
    return []

def build_parallel(entries):
    pairs = []

    for e in entries:
        lemma = e["lemma_ette"].strip().lower()
        definition = e["definition_es"]

        translations = extract_translations(definition)

        for t in translations:
            clean_t = normalize_text(t)
            if len(clean_t) < 2:
                continue

            pairs.append({
                "source": lemma,
                "target": clean_t
            })

    return pairs

if __name__ == "__main__":
    print("[INFO] Cargando entradas Ette → Español...")
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        entries = json.load(f)

    print("[INFO] Construyendo dataset paralelo...")
    parallel = build_parallel(entries)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(parallel, f, ensure_ascii=False, indent=2)

    print(f"[OK] Pares Ette–Español generados: {len(parallel)}")

    print("\n[CHECK] Ejemplos:")
    for p in parallel[:5]:
        print(p)
