import fitz
import pytesseract
import cv2
import numpy as np
import json
from pathlib import Path
from tqdm import tqdm

# Ajuste explícito de tesseract (Windows)
pytesseract.pytesseract.tesseract_cmd = r"C:/Users/DILAN CABAS/AppData/Local/Programs/Tesseract-OCR/tesseract.exe"

BASE_DIR = Path(__file__).resolve().parents[2]


def ocr_pdf_by_page(pdf_path: Path, output_path: Path):
    doc = fitz.open(pdf_path)
    pages_data = []

    for page_number in tqdm(range(len(doc)), desc="OCR páginas"):
        page = doc[page_number]

        pix = page.get_pixmap(dpi=300)
        img = np.frombuffer(pix.samples, dtype=np.uint8)
        img = img.reshape(pix.height, pix.width, pix.n)

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)[1]

        text = pytesseract.image_to_string(
            gray,
            lang="spa",
            config="--psm 6"
        )

        pages_data.append({
            "page": page_number + 1,
            "text": text
        })

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(pages_data, f, ensure_ascii=False, indent=2)

    print(f"[OK] OCR guardado en: {output_path}")


if __name__ == "__main__":
    pdf_path = BASE_DIR / "data" / "raw" / "diccionario_ette.pdf"
    output_path = BASE_DIR / "data" / "interim" / "pages_text_ocr.json"

    ocr_pdf_by_page(pdf_path, output_path)
