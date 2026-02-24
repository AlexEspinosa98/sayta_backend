import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]

INPUT_PATH = BASE_DIR / "data" / "interim" / "pages_columns_text.json"
OUTPUT_PATH = BASE_DIR / "data" / "interim" / "es_ette_entries.json"

START_PAGE = 288

# lema español en inicio de línea
ENTRY_PATTERN = re.compile(
    r"""
    ^\s*
    (?P<lemma>[a-záéíóúñü]+)      # lema español (una palabra)
    \s*
    (?P<rest>.+)                 # resto del bloque
    """,
    re.IGNORECASE | re.MULTILINE | re.VERBOSE
)

def main():
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        pages = json.load(f)

    entries = []

    for page in pages:
        if page["page"] < START_PAGE:
            continue

        # concatenamos columnas
        text = ""
        if "left" in page:
            text += page["left"] + "\n"
        if "right" in page:
            text += page["right"]

        for m in ENTRY_PATTERN.finditer(text):
            lemma = m.group("lemma").lower().strip()
            rest = m.group("rest").strip()

            # filtros básicos
            if len(lemma) < 3:
                continue
            if lemma.isupper():
                continue

            entries.append({
                "lemma_es": lemma,
                "raw_text": rest,
                "page": page["page"]
            })

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    print(f"[OK] Entradas Español → Ette segmentadas: {len(entries)}")

    if entries:
        print("\n[CHECK] Primeras 5:")
        for e in entries[:5]:
            print(e)

if __name__ == "__main__":
    main()
