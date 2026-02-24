import json
import re
from pathlib import Path

# =========================
# PATHS
# =========================

BASE_DIR = Path(__file__).resolve().parents[2]

INPUT_PATH = BASE_DIR / "data" / "processed" / "ette_es_clean.json"
OUTPUT_PATH = BASE_DIR / "data" / "interim" / "ette_es_entries.json"

# =========================
# REGEX
# =========================

ENTRY_RE = re.compile(
    r"""
    (?P<lemma>[a-záéíóúñ']{3,})      # lema Ette
    \s*
    (?:-\s*)?
    (?P<pos>
        nom|vrb|adv|adj|aux|pron|
        intg|pos|pl|nc|pr
    )?
    \s*
    (?P<definition>.{10,}?)
    (?=(?:\s+[a-záéíóúñ']{3,}\s*(?:-|nom|vrb|adv|adj)|$))
    """,
    re.IGNORECASE | re.VERBOSE
)

LEMMA_POS_RE = re.compile(
    r"\b[a-záéíóúñ']{3,}\s*-\s*(nom|vrb|adj|adv|pron)\b",
    re.IGNORECASE
)

SUBPOS_RE = re.compile(r'^\.(pr|int|trs|aux|pl\d+)\b', re.IGNORECASE)

# =========================
# UTILIDADES
# =========================

def fix_ocr_hyphens(text: str) -> str:
    return re.sub(r'-\s+([a-záéíóúñ])', r'\1', text)

def clean_definition(text: str) -> str:
    text = fix_ocr_hyphens(text)
    text = re.sub(r'\s{2,}', ' ', text)
    return text.strip(" .;:-")

def normalize_pos_and_definition(pos: str, definition: str):
    pos = (pos or "").lower()
    definition = definition.strip()

    m = SUBPOS_RE.match(definition)
    if not m:
        return pos, clean_definition(definition)

    sub = m.group(1).lower()
    pos = f"{pos}.{sub}" if pos else sub
    definition = SUBPOS_RE.sub("", definition, count=1)

    return pos, clean_definition(definition)

# =========================
# DETECTAR INICIO DICCIONARIO
# =========================

def detect_dictionary_start(pages, min_hits=3):
    """
    Retorna el índice de la primera página que claramente
    contiene entradas léxicas Ette → Español
    """
    for i, page in enumerate(pages):
        text = page.get("text", "").lower()
        hits = len(LEMMA_POS_RE.findall(text))
        if hits >= min_hits:
            return i
    return 0

# =========================
# PARSER
# =========================

def parse_pages(pages):
    entries = []

    for page in pages:
        page_num = page.get("page")
        text = page.get("text", "").replace("\n", " ")

        for m in ENTRY_RE.finditer(text):
            lemma = m.group("lemma").lower().strip()
            pos = m.group("pos") or ""
            definition = m.group("definition") or ""

            pos, definition = normalize_pos_and_definition(pos, definition)

            if len(definition) < 8:
                continue

            entries.append({
                "lemma_ette": lemma,
                "pos": pos,
                "definition_es": definition,
                "page": page_num
            })

    return entries

# =========================
# MAIN
# =========================

def main():
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"No se encontró {INPUT_PATH}")

    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        pages = json.load(f)

    start_idx = detect_dictionary_start(pages)

    print(f"[INFO] Diccionario detectado desde la página {pages[start_idx]['page']}")

    pages = pages[start_idx:]

    entries = parse_pages(pages)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    print(f"[OK] Entradas Ette → Español segmentadas: {len(entries)}")

    if entries:
        print("\n[CHECK] Primeras 5:")
        for e in entries[:5]:
            print(e)

if __name__ == "__main__":
    main()

