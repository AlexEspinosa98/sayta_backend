import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

INPUT_PATH = BASE_DIR / "data" / "processed" / "ette_es_dictionary_index.json"
OUTPUT_PATH = BASE_DIR / "data" / "processed" / "ette_es_dictionary_index_clean.json"

NOISE_PATTERNS = [
    r"\bequiv\b",
    r"\bfig\b",
    r"\bantig\b",
    r"\bvéase\b",
    r"\bcf\b",
    r"\blit\b",
]

NOISE_RE = re.compile("|".join(NOISE_PATTERNS), re.IGNORECASE)

POS_NORMALIZATION = {
    "vrb.intnt": "vrb.int",
    "vrb.trsrs": "vrb.trs",
}

def clean_translation(text: str) -> str:
    text = text.lower()
    text = NOISE_RE.sub("", text)
    text = re.sub(r"[;,]", " ", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()

def normalize_pos(pos_list):
    normalized = set()
    for p in pos_list:
        normalized.add(POS_NORMALIZATION.get(p, p))
    return sorted(normalized)

def main():
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        dictionary = json.load(f)

    cleaned = {}

    for lemma, data in dictionary.items():
        translations = []
        for t in data["translations"]:
            ct = clean_translation(t)
            if len(ct) >= 2:
                translations.append(ct)

        if not translations:
            continue

        cleaned[lemma] = {
            "pos": normalize_pos(data["pos"]),
            "translations": sorted(set(translations)),
            "pages": data["pages"]
        }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)

    print(f"[OK] Diccionario limpiado: {len(cleaned)} lemas")

    sample = list(cleaned.items())[:5]
    print("\n[CHECK] Ejemplo:")
    for k, v in sample:
        print(k, "→", v)

if __name__ == "__main__":
    main()
