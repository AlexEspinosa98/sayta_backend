import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]

INPUT_PATH = BASE_DIR / "data" / "processed" / "es_ette_entries_normalize.json"
OUTPUT_PATH = BASE_DIR / "data" / "processed" / "es_ette_parallel.json"

# -----------------------------
# Heurísticas Ette
# -----------------------------

ETTE_TOKEN = re.compile(
    r"[a-záéíóúñü']{3,}",
    re.IGNORECASE
)

EXCLUDE_SPANISH = re.compile(
    r"(persona|objeto|fig|antig|sentido|forma|refiri|emplea|especie|planta|animal)",
    re.IGNORECASE
)

def normalize_ette(token: str) -> str:
    token = token.lower().strip()
    token = re.sub(r"[^a-záéíóúñü']", "", token)
    return token


def extract_ette_equivalents(text: str):
    candidates = ETTE_TOKEN.findall(text)
    results = []

    for c in candidates:
        if EXCLUDE_SPANISH.search(c):
            continue
        if len(c) < 3:
            continue
        results.append(normalize_ette(c))

    return list(set(results))


def main():
    print("[INFO] Cargando entradas Español → Ette...")
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        entries = json.load(f)

    pairs = []

    for e in entries:
        lemma_es = e["lemma_es"].lower().strip()
        raw_text = e["raw_text"]

        ettes = extract_ette_equivalents(raw_text)

        for et in ettes:
            pairs.append({
                "source": lemma_es,
                "target": et
            })

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(pairs, f, ensure_ascii=False, indent=2)

    print(f"[OK] Pares Español–Ette generados: {len(pairs)}")

    if pairs:
        print("\n[CHECK] Ejemplos:")
        for p in pairs[:5]:
            print(p)


if __name__ == "__main__":
    main()
