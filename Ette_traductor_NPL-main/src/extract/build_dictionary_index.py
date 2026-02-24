import json
from pathlib import Path
from collections import defaultdict

BASE_DIR = Path(__file__).resolve().parents[2]

INPUT_LEXICAL = BASE_DIR / "data" / "processed" / "ette_es_lexical.json"
INPUT_ENTRIES = BASE_DIR / "data" / "processed" / "ette_es_clean.json"
OUTPUT_INDEX = BASE_DIR / "data" / "processed" / "ette_es_dictionary_index.json"


def load_entries_metadata():
    """
    Carga POS y páginas desde las entradas limpias
    """
    meta = defaultdict(lambda: {"pos": set(), "pages": set()})

    with open(INPUT_ENTRIES, "r", encoding="utf-8") as f:
        entries = json.load(f)

    for e in entries:
        lemma = e["lemma_ette"].strip().lower()
        if e.get("pos"):
            meta[lemma]["pos"].add(e["pos"])
        if e.get("page"):
            meta[lemma]["pages"].add(e["page"])

    return meta


def build_index(pairs, meta):
    index = defaultdict(lambda: {
        "pos": set(),
        "translations": set(),
        "pages": set()
    })

    for p in pairs:
        lemma = p["source"]
        translation = p["target"]

        index[lemma]["translations"].add(translation)

        if lemma in meta:
            index[lemma]["pos"].update(meta[lemma]["pos"])
            index[lemma]["pages"].update(meta[lemma]["pages"])

    # serialización final
    final_index = {}
    for lemma, data in index.items():
        final_index[lemma] = {
            "pos": sorted(data["pos"]),
            "translations": sorted(data["translations"]),
            "pages": sorted(data["pages"])
        }

    return final_index


def main():
    if not INPUT_LEXICAL.exists():
        raise FileNotFoundError(f"No se encontró {INPUT_LEXICAL}")
    if not INPUT_ENTRIES.exists():
        raise FileNotFoundError(f"No se encontró {INPUT_ENTRIES}")

    print("[INFO] Cargando pares léxicos...")
    with open(INPUT_LEXICAL, "r", encoding="utf-8") as f:
        pairs = json.load(f)

    print("[INFO] Cargando metadatos (POS / páginas)...")
    meta = load_entries_metadata()

    print("[INFO] Construyendo índice del diccionario...")
    dictionary_index = build_index(pairs, meta)

    OUTPUT_INDEX.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_INDEX, "w", encoding="utf-8") as f:
        json.dump(dictionary_index, f, ensure_ascii=False, indent=2)

    print(f"[OK] Lemas indexados: {len(dictionary_index)}")

    print("\n[CHECK] Ejemplo:")
    for k in list(dictionary_index.keys())[:3]:
        print(k, "→", dictionary_index[k])


if __name__ == "__main__":
    main()
