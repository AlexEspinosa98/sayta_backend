import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DICT_PATH = BASE_DIR / "data" / "processed" / "ette_es_dictionary_index.json"

if not DICT_PATH.exists():
    raise FileNotFoundError(f"No se encontró el diccionario: {DICT_PATH}")

with open(DICT_PATH, "r", encoding="utf-8") as f:
    DICT = json.load(f)

def translate(word: str):
    key = word.strip().lower()
    entry = DICT.get(key)

    if not entry:
        return None

    return {
        "lemma": key,
        "pos": entry.get("pos", []),
        "translations": entry.get("translations", []),
        "pages": entry.get("pages", [])
    }

if __name__ == "__main__":
    print("Traductor Ette → Español (enter vacío para salir)\n")

    while True:
        w = input("Ette > ").strip()
        if not w:
            break

        result = translate(w)

        if result:
            print("  POS:", ", ".join(result["pos"]))
            print("  Esp:", ", ".join(result["translations"]))
            print("  Pág:", ", ".join(map(str, result["pages"])))
        else:
            print("  [No encontrado]")
