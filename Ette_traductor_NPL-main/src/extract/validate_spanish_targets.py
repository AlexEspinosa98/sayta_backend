import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
INPUT = BASE_DIR / "data" / "processed" / "ette_es_parallel_final.json"
OUTPUT = BASE_DIR / "data" / "processed" / "ette_es_parallel_valid.json"

SPANISH_VOWELS = set("aeiouáéíóú")

def looks_spanish(word: str) -> bool:
    return any(v in word for v in SPANISH_VOWELS)

with open(INPUT, "r", encoding="utf-8") as f:
    data = json.load(f)

clean = [
    pair for pair in data
    if looks_spanish(pair["target"])
]

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(clean, f, ensure_ascii=False, indent=2)

print(f"[OK] Pares válidos finales: {len(clean)}")
