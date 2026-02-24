import json
import re
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path(__file__).resolve().parents[2]

INPUT_PATH = BASE_DIR / "data" / "processed" / "ette_es_parallel.json"
OUTPUT_PATH = BASE_DIR / "data" / "processed" / "ette_es_parallel_clean.json"


def clean_spanish(text: str) -> str | None:
    """
    Limpia ruido común del OCR y devuelve una definición corta válida.
    """
    text = text.lower()

    # eliminar referencias internas y restos
    text = re.sub(r"véase.*", "", text)
    text = re.sub(r"figura\s*\d+", "", text)
    text = re.sub(r"[^a-záéíóúñü\s]", " ", text)

    # colapsar espacios
    text = re.sub(r"\s+", " ", text).strip()

    # descartar basura corta o gramatical
    if len(text) < 3:
        return None

    if text in {"e", "o", "y", "de", "la", "el"}:
        return None

    return text


def normalize(pairs):
    grouped = defaultdict(set)

    for pair in pairs:
        src = pair["source"].strip().lower()
        tgt = clean_spanish(pair["target"])

        if not src or not tgt:
            continue

        grouped[src].add(tgt)

    return [
        {"source": src, "targets": sorted(list(tgts))}
        for src, tgts in sorted(grouped.items())
    ]


if __name__ == "__main__":
    print("[INFO] Cargando pares paralelos...")
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        pairs = json.load(f)

    print("[INFO] Normalizando y limpiando...")
    cleaned = normalize(pairs)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)

    print(f"[OK] Entradas normalizadas: {len(cleaned)}")

    print("\n[CHECK] Ejemplos:")
    for e in cleaned[:5]:
        print(e)
