import json
import re
from pathlib import Path

# =========================
# Configuración de rutas
# =========================
BASE_DIR = Path(__file__).resolve().parents[2]

INPUT_PATH = BASE_DIR / "data" / "interim" / "ette_es_pages.json"
OUTPUT_PATH = BASE_DIR / "data" / "processed" / "ette_es_clean.json"


# =========================
# Limpieza de texto OCR
# =========================
def clean_text(text: str) -> str:
    text = text.lower()

    # eliminar encabezados repetidos del diccionario
    text = re.sub(r"diccionario ette[-–]español.*?", "", text)

    # eliminar números de página sueltos
    text = re.sub(r"\b\d{1,4}\b", " ", text)

    # unir líneas
    text = text.replace("\n", " ")

    # eliminar símbolos típicos de OCR
    text = re.sub(r"[•■◆▪◦]", "", text)

    # normalizar espacios
    text = re.sub(r"\s{2,}", " ", text)

    return text.strip()


# =========================
# Main
# =========================
def main():
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"No existe el archivo: {INPUT_PATH}")

    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        pages = json.load(f)

    cleaned_pages = []

    for page in pages:
        page_num = page.get("page")

        left = page.get("left", "")
        right = page.get("right", "")

        # unir columnas: izquierda → derecha
        full_text = f"{left}\n{right}".strip()

        cleaned_pages.append({
            "page": page_num,
            "text": clean_text(full_text)
        })

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(cleaned_pages, f, ensure_ascii=False, indent=2)

    print(f"[OK] Páginas limpiadas: {len(cleaned_pages)}")
    print(f"[OK] Archivo generado: {OUTPUT_PATH}")

    # chequeo rápido
    print("\n[CHECK] Ejemplo real:")
    for p in cleaned_pages[:3]:
        print(f"Página {p['page']}: {p['text'][:150]}...")


if __name__ == "__main__":
    main()
