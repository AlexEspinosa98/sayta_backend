import json
from pathlib import Path


# =========================
# Configuración de rutas
# =========================
BASE_DIR = Path(__file__).resolve().parents[2]

INPUT_JSON = BASE_DIR / "data" / "interim" / "pages_columns_text.json"
OUTPUT_DIR = BASE_DIR / "data" / "interim"

ETTE_ES_OUT = OUTPUT_DIR / "ette_es_pages.json"
ES_ETTE_OUT = OUTPUT_DIR / "es_ette_pages.json"


# =========================
# Carga de datos
# =========================
def load_pages(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"No existe el archivo: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("El JSON no contiene una lista de páginas")

    return data


# =========================
# Segmentación del diccionario
# =========================
def split_dictionary_sections(pages: list[dict]):
    """
    Segmenta el diccionario usando números de página reales del libro.

    - Ette → Español: páginas 45 a 356
    - Español → Ette: páginas 357 en adelante
    """

    ette_es_pages = []
    es_ette_pages = []

    for page in pages:
        page_num = page.get("page")

        if not isinstance(page_num, int):
            continue

        left = page.get("left", "")
        right = page.get("right", "")

        # Reconstrucción correcta del texto
        text = f"{left}\n{right}".strip()

        if not text:
            continue

        # Diccionario Ette → Español
        if 45 <= page_num < 357:
            ette_es_pages.append({
                "page": page_num,
                "left": left,
                "right": right
            })

        # Diccionario Español → Ette
        elif page_num >= 357:
            es_ette_pages.append({
                "page": page_num,
                "left": left,
                "right": right
            })

    return ette_es_pages, es_ette_pages


# =========================
# Validaciones básicas
# =========================
def sanity_check(pages: list[dict], label: str, n: int = 5) -> None:
    print(f"\n[CHECK] Muestra de {label}:")
    for p in pages[:n]:
        preview = f"{p['left']}\n{p['right']}"
        preview = preview[:120].replace("\n", " ")
        print(f"  Página {p['page']}: {preview}...")


# =========================
# Guardado
# =========================
def save_json(data: list[dict], path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# =========================
# Main
# =========================
def main():
    print("[INFO] Cargando páginas OCR...")
    pages = load_pages(INPUT_JSON)

    print("[INFO] Separando secciones del diccionario...")
    ette_es_pages, es_ette_pages = split_dictionary_sections(pages)

    if not ette_es_pages:
        raise RuntimeError("No se detectaron páginas Ette → Español")

    if not es_ette_pages:
        raise RuntimeError("No se detectaron páginas Español → Ette")

    print("[INFO] Guardando resultados...")
    save_json(ette_es_pages, ETTE_ES_OUT)
    save_json(es_ette_pages, ES_ETTE_OUT)

    print(f"[OK] Ette → Español: {len(ette_es_pages)} páginas")
    print(f"[OK] Español → Ette: {len(es_ette_pages)} páginas")

    sanity_check(ette_es_pages, "Ette → Español")
    sanity_check(es_ette_pages, "Español → Ette")


if __name__ == "__main__":
    main()
