import pandas as pd
import re
import json
from collections import Counter

INPUT_FILE = "ette_es_diccionario_por_letras.xlsx"

OUTPUT_JSON = "dataset_clean.json"
OUTPUT_REPORT = "reporte_estadistico.txt"

# ======================================
# INVENTARIO OFICIAL POS
# ======================================

POS_VALIDAS = {
    "ADJ","ADV","AUX","CLS","CONJ","DTR","EXCL","FUN","IDEO",
    "IMP","INTG","INT","LOC","NOM","NUM","PL","PL1","PL2",
    "PL3","PL4","PL5","POS","PR","PRON","SUF","TRS","VRB"
}

POS_REGEX = r"(adj|adv|aux|cls|conj|dtr|excl|fun|ideo|imp|intg|int|loc|nom|num|pl[0-9]?|pos|pr|pron|suf|trs|vrb)"

# ======================================
# FUNCIONES
# ======================================

def normalizar_pos(texto):
    texto_lower = texto.lower()
    partes = re.split(r"[.\s]", texto_lower)
    etiquetas = []

    for p in partes:
        p_upper = p.upper()
        if p_upper in POS_VALIDAS:
            etiquetas.append(p_upper)

    if etiquetas:
        return "_".join(etiquetas)

    return None


def eliminar_pos_del_inicio(texto):
    patron = r"^([a-z]+(?:\.[a-z0-9]+)*)\s+"
    return re.sub(patron, "", texto, flags=re.IGNORECASE)


def extraer_sinonimos(texto):
    sinonimos = []
    match = re.search(r"(equiv\.|sinón\.)\s*([^\.;]+)", texto, re.IGNORECASE)

    if match:
        bloque = match.group(2)
        candidatos = re.split(r",|\s", bloque)
        for c in candidatos:
            c = c.strip()
            if c:
                sinonimos.append(c)

    return list(set(sinonimos))


def extraer_ejemplos(texto):
    ejemplos = []
    matches = re.findall(r"v\.g\.\s*([^.;]+)", texto, re.IGNORECASE)
    for m in matches:
        ejemplos.append(m.strip())
    return ejemplos


def limpiar_definicion(texto):
    texto = eliminar_pos_del_inicio(texto)

    texto = re.sub(r"(equiv\.|sinón\.).*", "", texto, flags=re.IGNORECASE)
    texto = re.sub(r"v\.g\..*", "", texto, flags=re.IGNORECASE)
    texto = re.sub(r"\s+\d+$", "", texto)
    texto = re.sub(r"\s+", " ", texto)

    return texto.strip(" ,.;")


def detectar_morfema(lemma):
    if lemma.startswith("-"):
        return "SUFIJO"
    if lemma.endswith("-"):
        return "PREFIJO"
    return None


# ======================================
# PROCESAMIENTO
# ======================================

xls = pd.ExcelFile(INPUT_FILE)

dataset = []
contador_pos = Counter()

print("Hojas detectadas:", xls.sheet_names)

for sheet in xls.sheet_names:
    df = pd.read_excel(INPUT_FILE, sheet_name=sheet, header=None)

    for _, row in df.iterrows():

        if pd.isna(row[0]):
            continue

        lemma = str(row[0]).strip()

        if not lemma or lemma.lower() == "lemma":
            continue

        texto_completo = " ".join(
            [str(x) for x in row[1:] if pd.notna(x)]
        ).strip()

        if not texto_completo:
            continue

        pos = normalizar_pos(texto_completo)
        sinonimos = extraer_sinonimos(texto_completo)
        ejemplos = extraer_ejemplos(texto_completo)
        definicion = limpiar_definicion(texto_completo)
        tipo_morfema = detectar_morfema(lemma)

        if pos:
            for p in pos.split("_"):
                contador_pos[p] += 1

        dataset.append({
            "lemma": lemma,
            "pos": pos,
            "definicion": definicion,
            "sinonimos": sinonimos,
            "ejemplos": ejemplos,
            "tipo_morfema": tipo_morfema
        })

# ======================================
# EXPORTAR
# ======================================

with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(dataset, f, ensure_ascii=False, indent=2)

with open(OUTPUT_REPORT, "w", encoding="utf-8") as f:
    f.write("===== REPORTE =====\n")
    f.write(f"Total entradas: {len(dataset)}\n\n")
    f.write("Distribución POS:\n")
    for pos, count in contador_pos.items():
        f.write(f"{pos}: {count}\n")

print("====================================")
print("Dataset limpio generado.")
print("Total entradas:", len(dataset))
print("====================================")