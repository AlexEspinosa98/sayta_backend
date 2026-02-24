import json
import re
from pathlib import Path

# =========================
# Paths (MISMO ESQUEMA ANTERIOR)
# =========================

BASE_DIR = Path(__file__).resolve().parents[2]

INPUT_JSON = BASE_DIR / "data" / "interim" / "ette_es_entries.json"
OUTPUT_JSON = BASE_DIR / "data" / "processed" / "ette_es_normalized.json"

# =========================
# Reglas lingüísticas
# =========================

# POS válidos
VALID_POS = {
    "nom", "nom.pr", "adv", "adj",
    "vrb", "vrb.int", "vrb.trs",
    "intg", "pos"
}

# Lemas NO léxicos a eliminar
NON_LEXICAL_LEMMAS = {
    "intg", "coor", "pos", "pron", "dem",
    "adj", "adv", "nom", "vrb"
}

# =========================
# Funciones de normalización
# =========================

def normalize_pos(pos_raw: str) -> str:
    if not pos_raw:
        return ""

    pos = pos_raw.strip().lower()
    pos = pos.replace(" ", "")

    # Correcciones OCR básicas
    pos = pos.replace("vrb.i", "vrb.int")
    pos = pos.replace("vrb.t", "vrb.trs")
    pos = pos.replace("nom.prést", "nom")
    pos = pos.replace("nom.pr", "nom.pr")

    # Normalización por prefijo (clave)
    if pos.startswith("vrb.int"):
        pos = "vrb.int"
    elif pos.startswith("vrb.trs"):
        pos = "vrb.trs"
    elif pos.startswith("vrb"):
        pos = "vrb"
    elif pos.startswith("nom.pr"):
        pos = "nom.pr"
    elif pos.startswith("nom"):
        pos = "nom"
    elif pos.startswith("adv"):
        pos = "adv"
    elif pos.startswith("adj"):
        pos = "adj"
    elif pos.startswith("pron"):
        pos = "pron"
    elif pos.startswith("intg"):
        pos = "intg"

    return pos




def clean_definition(text: str) -> str:
    if not text:
        return ""

    text = text.strip()

    # Quitar puntos iniciales y residuos OCR
    text = re.sub(r"^[\.\-\s]+", "", text)

    # Quitar referencias a figuras
    text = re.sub(r"véase figura.*?$", "", text, flags=re.IGNORECASE)

    # Normalizar espacios
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def is_valid_entry(entry: dict) -> bool:
    lemma = entry.get("lemma_ette", "").strip().lower()

    # descartar entradas sin lema real
    if len(lemma) < 2:
        return False

    # descartar metalingüísticas
    if lemma in NON_LEXICAL_LEMMAS:
        return False

    return True


# =========================
# Main
# =========================

def main():
    if not INPUT_JSON.exists():
        raise FileNotFoundError(f"No se encontró {INPUT_JSON}")

    with INPUT_JSON.open(encoding="utf-8") as f:
        entries = json.load(f)

    normalized = []
    skipped = 0

    for e in entries:
        if not is_valid_entry(e):
            skipped += 1
            continue

        lemma = e.get("lemma_ette", "").strip()
        pos = normalize_pos(e.get("pos", ""))
        definition = clean_definition(e.get("definition_es", ""))
        page = e.get("page")

        if not lemma or not definition:
            skipped += 1
            continue

        normalized.append({
            "lemma_ette": lemma,
            "pos": pos,
            "definition_es": definition,
            "page": page
        })

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_JSON.open("w", encoding="utf-8") as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2)

    print(f"[OK] Entradas normalizadas: {len(normalized)}")
    print(f"[SKIP] Entradas descartadas: {skipped}")

    print("\n[CHECK] Primeras 5:")
    for e in normalized[:5]:
        print(e)


if __name__ == "__main__":
    main()
