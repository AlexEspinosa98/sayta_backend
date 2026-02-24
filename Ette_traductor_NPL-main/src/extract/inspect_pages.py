import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
INPUT_PATH = BASE_DIR / "data" / "processed" / "ette_es_clean.json"

with open(INPUT_PATH, "r", encoding="utf-8") as f:
    pages = json.load(f)

print("TOTAL PÁGINAS:", len(pages))
print("\n=== TEXTO REAL (primeras 2 páginas) ===\n")

for page in pages[:2]:
    print(f"\n--- PÁGINA {page['page']} ---\n")
    print(page["text"][:1500])
