import json
from pathlib import Path

p = Path("data/interim/pages_columns_text.json")

with open(p, "r", encoding="utf-8") as f:
    pages = json.load(f)

for i, page in enumerate(pages):
    text = page.get("text", "").lower()

    if "diccionario" in text:
        print(f"\n--- PÁGINA {i} ---")
        print(text[:500])
