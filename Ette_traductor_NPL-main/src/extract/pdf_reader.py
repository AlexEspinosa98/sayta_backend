import fitz
import json
from pathlib import Path
from tqdm import tqdm


BASE_DIR = Path(__file__).resolve().parents[2]


def extract_pdf_by_page(pdf_path: Path, output_path: Path):
    doc = fitz.open(pdf_path)
    pages_data = []

    for page_number in tqdm(range(len(doc)), desc="Extrayendo páginas"):
        page = doc[page_number]
        text = page.get_text("text")

        pages_data.append({
            "page": page_number + 1,
            "text": text
        })

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(pages_data, f, ensure_ascii=False, indent=2)

    print(f"[OK] Texto extraído en: {output_path}")


if __name__ == "__main__":
    pdf_path = BASE_DIR / "data" / "raw" / "diccionario_ette.pdf"
    output_path = BASE_DIR / "data" / "interim" / "pages_text.json"

    extract_pdf_by_page(pdf_path, output_path)
