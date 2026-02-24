import json
import pandas as pd
from pathlib import Path
import re

# -----------------------------
# Rutas
# -----------------------------
BASE_DIR = Path(__file__).resolve().parents[2]

INPUT_PATH = BASE_DIR / "data" / "interim" / "ette_es_entries.json"
OUTPUT_PATH = BASE_DIR / "data" / "processed" / "ette_es_diccionario_por_letras.xlsx"

# -----------------------------
# Utilidades
# -----------------------------
def clean_sheet_name(name: str) -> str:
    name = re.sub(r'[:\\/?*\[\]]', '_', name)
    return name[:31]

def definition_score(row) -> int:
    """
    Heurística de completitud de definición
    """
    score = len(row.get("definition_es", ""))
    if row.get("pos"):
        score += 50
    return score

# -----------------------------
# Lectura del JSON
# -----------------------------
with open(INPUT_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

df = pd.DataFrame(data)

if "lemma_ette" not in df.columns:
    raise ValueError("El JSON no contiene 'lemma_ette'")

# -----------------------------
# Detectar conflictos (antes de deduplicar)
# -----------------------------
conflicts = df.groupby("lemma_ette").filter(lambda x: len(x) > 1)

# -----------------------------
# Deduplicación
# -----------------------------
df["_score"] = df.apply(definition_score, axis=1)

df = df.sort_values(
    by=["lemma_ette", "_score", "page"],
    ascending=[True, False, True]
)

df_unique = df.drop_duplicates(subset=["lemma_ette"], keep="first")
df_unique = df_unique.drop(columns=["_score"])

# -----------------------------
# Agrupación por letra inicial
# -----------------------------
df_unique["initial_letter"] = df_unique["lemma_ette"].str[0].str.upper()

# -----------------------------
# Escritura del Excel
# -----------------------------
with pd.ExcelWriter(OUTPUT_PATH, engine="openpyxl") as writer:

    # Hojas por letra
    for letter, group in df_unique.groupby("initial_letter"):
        group_sorted = group.sort_values(by="lemma_ette")
        group_out = group_sorted.drop(columns=["initial_letter"])

        sheet_name = clean_sheet_name(letter)

        group_out.to_excel(
            writer,
            sheet_name=sheet_name,
            index=False
        )

    # Hoja de conflictos
    if not conflicts.empty:
        conflicts_sorted = conflicts.sort_values(
            by=["lemma_ette", "page"]
        )

        conflicts_sorted.to_excel(
            writer,
            sheet_name="CONFLICTOS",
            index=False
        )

# -----------------------------
# Reporte
# -----------------------------
print(f"[OK] Excel generado: {OUTPUT_PATH}")
print(f"[INFO] Lemas únicos finales: {len(df_unique)}")
print(f"[INFO] Lemas con conflicto: {conflicts['lemma_ette'].nunique()}")
