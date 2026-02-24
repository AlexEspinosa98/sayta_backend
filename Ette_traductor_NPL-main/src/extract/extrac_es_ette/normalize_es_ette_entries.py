import json
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]

# Entrada: salida directa de parse_es_ette.py
INPUT_PATH = BASE_DIR / "data" / "interim" / "es_ette_entries.json"

# Salida: entradas normalizadas Español → Ette
OUTPUT_PATH = BASE_DIR / "data" / "processed" / "es_ette_entries_normalize.json"

# -----------------------------
# Heurísticas lingüísticas
# -----------------------------

# Patrones típicos del Ette (para descartar falsos lemas españoles)
ETTE_PATTERN = re.compile(
    r"(kw|gg|tt|ññ|aa|ee|ii|oo|uu|'|wi|ya|ka|kra|gwa)",
    re.IGNORECASE
)

# Palabras españolas mínimas válidas como lema
SPANISH_LEMMA_PATTERN = re.compile(r"^[a-záéíóúñü]{3,}$", re.IGNORECASE)

# Limpieza ligera de OCR
CLEAN_OCR = re.compile(r"\s{2,}")

def is_valid_spanish_lemma(token: str) -> bool:
    token = token.lower().strip()

    if not SPANISH_LEMMA_PATTERN.fullmatch(token):
        return False

    # descartar si parece Ette
    if ETTE_PATTERN.search(token):
        return False

    return True


def clean_raw_text(text: str) -> str:
    text = text.replace("\n", " ")
    text = CLEAN_OCR.sub(" ", text)
    return text.strip()


def main():
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        raw_entries = json.load(f)

    normalized = []
    skipped = 0

    current_lemma = None
    current_text = []
    current_page = None

    for entry in raw_entries:
        lemma = entry["lemma_es"].strip().lower()
        raw_text = entry.get("raw_text", "").strip()
        page = entry.get("page")

        if is_valid_spanish_lemma(lemma):
            # guardar bloque anterior
            if current_lemma and current_text:
                normalized.append({
                    "lemma_es": current_lemma,
                    "raw_text": clean_raw_text(" ".join(current_text)),
                    "page": current_page
                })

            # iniciar nuevo bloque
            current_lemma = lemma
            current_text = [raw_text] if raw_text else []
            current_page = page

        else:
            # no es lema español → continuar acumulando definición
            if current_lemma:
                current_text.append(raw_text)
            else:
                skipped += 1

    # guardar último bloque
    if current_lemma and current_text:
        normalized.append({
            "lemma_es": current_lemma,
            "raw_text": clean_raw_text(" ".join(current_text)),
            "page": current_page
        })

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2)

    print(f"[OK] Entradas Español → Ette normalizadas: {len(normalized)}")
    print(f"[SKIP] Bloques descartados: {skipped}")

    if normalized:
        print("\n[CHECK] Primeras 5:")
        for e in normalized[:5]:
            print(e)


if __name__ == "__main__":
    main()
