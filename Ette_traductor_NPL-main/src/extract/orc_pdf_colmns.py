import json
import pytesseract
from pdf2image import convert_from_path
from pathlib import Path
from PIL import Image

# RUTAS
BASE_DIR = Path(__file__).resolve().parents[2]

PDF_PATH = BASE_DIR / "data" / "raw" / "diccionario_ette.pdf"
OUTPUT_JSON = BASE_DIR / "data" / "interim" / "pages_columns_text.json"

POPPLER_PATH = r"C:\Release-25.12.0-0\poppler-25.12.0\Library\bin"
TESSERACT_PATH = r"C:\Users\DILAN CABAS\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"

pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH


def ocr_columns(image: Image.Image):
    width, height = image.size

    left_col = image.crop((0, 0, width // 2, height))
    right_col = image.crop((width // 2, 0, width, height))

    config = "--psm 4 -l spa"

    text_left = pytesseract.image_to_string(left_col, config=config)
    text_right = pytesseract.image_to_string(right_col, config=config)

    return (text_left + "\n" + text_right).strip()


def main():
    pages = convert_from_path(
        PDF_PATH,
        dpi=300,
        poppler_path=POPPLER_PATH
    )

    results = []

    for i, page in enumerate(pages, start=1):
        text = ocr_columns(page)

        results.append({
            "page": i,
            "text": text
        })

        if i == 1:
            page.save("debug_page_1.png")
            print("[DEBUG] Imagen guardada: debug_page_1.png")
            print("[DEBUG] Texto OCR (primeros 500 chars):")
            print(text[:500])

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"[OK] OCR por columnas completado: {len(results)} páginas")


if __name__ == "__main__":
    main()
