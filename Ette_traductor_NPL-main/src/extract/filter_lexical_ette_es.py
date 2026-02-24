import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

INPUT_PATH = BASE_DIR / "data" / "processed" / "ette_es_parallel.json"
OUTPUT_PATH = BASE_DIR / "data" / "processed" / "ette_es_lexical.json"

# patrones de descarte léxico
DROP_PATTERNS = re.compile(
    r"""
    equiv|
    sin[oó]n|
    cf\.?|
    v[eé]ase|
    figura|
    verbo|
    pronombre|
    expresión|
    forma|
    persona|
    tiempo
    """,
    re.IGNORECASE | re.VERBOSE
)

# separadores léxicos frecuentes
SPLIT_PATTERN = re.compile(r",|;| y ")

def is_valid_target(text: str) -> bool:
    """Valida si el target es léxico y no definicional"""
    if len(text) < 2:
        return False
    if len(text.split()) > 4:
        return False
    if DROP_PATTERNS.search(text):
        return False
    return True


def normalize_target(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-záéíóúñü\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def filter_pairs(pairs):
    clean_pairs = []
    skipped = 0

    for p in pairs:
        source = p["source"].strip().lower()
        raw_target = p["target"]

        # dividir traducciones múltiples
        candidates = SPLIT_PATTERN.split(raw_target)

        for c in candidates:
            target = normalize_target(c)

            if not is_valid_target(target):
                skipped += 1
                continue

            clean_pairs.append({
                "source": source,
                "target": target
            })

    return clean_pairs, skipped


def main():
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"No se encontró {INPUT_PATH}")

    print("[INFO] Cargando pares Ette–Español...")
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        pairs = json.load(f)

    print("[INFO] Filtrando pares léxicos...")
    lexical_pairs, skipped = filter_pairs(pairs)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(lexical_pairs, f, ensure_ascii=False, indent=2)

    print(f"[OK] Pares léxicos finales: {len(lexical_pairs)}")
    print(f"[SKIP] Pares descartados: {skipped}")

    if lexical_pairs:
        print("\n[CHECK] Ejemplos:")
        for p in lexical_pairs[:5]:
            print(p)


if __name__ == "__main__":
    main()
