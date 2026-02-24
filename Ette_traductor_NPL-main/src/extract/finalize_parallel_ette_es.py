import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

INPUT_PATH = BASE_DIR / "data" / "processed" / "ette_es_lexical.json"
OUTPUT_PATH = BASE_DIR / "data" / "processed" / "ette_es_parallel_final.json"


def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-záéíóúñü\s]", "", text)
    return text.strip()


def is_good_translation(t: str) -> bool:
    if len(t.split()) > 2:
        return False
    blacklist = {
        "ese", "esa", "eso", "este", "esta",
        "hablando", "suele", "vrb", "e"
    }
    return not any(b in t for b in blacklist)


if __name__ == "__main__":
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        entries = json.load(f)

    parallel = []

    for entry in entries:
        src = normalize_text(entry["source"])

        for t in entry["targets"]:
            tgt = normalize_text(t)
            if is_good_translation(tgt):
                parallel.append({
                    "source": src,
                    "target": tgt
                })

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(parallel, f, ensure_ascii=False, indent=2)

    print(f"[OK] Pares finales Ette–Español: {len(parallel)}")

    print("\n[CHECK] Ejemplos:")
    for p in parallel[:10]:
        print(p)
