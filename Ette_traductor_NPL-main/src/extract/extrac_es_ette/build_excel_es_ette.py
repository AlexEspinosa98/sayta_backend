import json
import pandas as pd
from pathlib import Path
import re

# -----------------------------
# Rutas
# -----------------------------
BASE_DIR = Path(__file__).resolve().parents[3]

INPUT_PATH = BASE_DIR / "data" / "processed" / "es_ette_entries_normalize.json"
OUTPUT_PATH = BASE_DIR / "data" / "processed" / "es_ette_diccionario_por_letras.xlsx"

# -----------------------------
# Utilidades
# -----------------------------
def clean_sheet_name(name: str) -> str:
    name = re.sub(r'[:\\/?*\[\]]', '_', name)
    return name[:31]


def entry_score(row) -> int:
    """
    Heurística simple de completitud:
    - más texto = más información
    """
    score = len(row.get("raw_text", ""))
    return score


# -----------------------------
# Lectura del JSON
# -----------------------------
with open(INPUT_PATH, "r", encoding="utf-8") as f:
    data = json.load(f)

df = pd.DataFrame(data)

required_cols = {"lemma_es", "raw_text", "page"}
if not required_cols.issubset(df.columns):
    raise ValueError(f"El JSON debe contener {required_cols}")

# -----------------------------
# Detectar conflictos
# -----------------------------
conflicts = df.groupby("lemma_es").filter(lambda x: len(x) > 1)

# -----------------------------
# Deduplicación
# -----------------------------
df["_score"] = df.apply(entry_score, axis=1)

df = df.sort_values(
    by=["lemma_es", "_score", "page"],
    ascending=[True, False, True]
)

df_unique = df.drop_duplicates(subset=["lemma_es"], keep="first")
df_unique = df_unique.drop(columns=["_score"])

# -----------------------------
# Agrupación por letra inicial
# -----------------------------
df_unique["initial_letter"] = df_unique["lemma_es"].str[0].str.upper()

# -----------------------------
# Escritura del Excel
# -----------------------------
with pd.ExcelWriter(OUTPUT_PATH, engine="openpyxl") as writer:

    # Hojas por letra
    for letter, group in df_unique.groupby("initial_letter"):
        group_sorted = group.sort_values(by="lemma_es")
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
            by=["lemma_es", "page"]
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
print(f"[INFO] Lemas españoles únicos finales: {len(df_unique)}")
print(f"[INFO] Lemas con conflicto: {conflicts['lemma_es'].nunique()}")
