from pathlib import Path
import re
from collections import Counter, defaultdict

BASE_DIR = Path(__file__).resolve().parents[2]

INPUT_PATH = BASE_DIR / "data" / "processed" / "ette_es_clean_lexical.tsv"
OUTPUT_PATH = BASE_DIR / "data" / "processed" / "ette_es_trainable_freq.tsv"

# -----------------------------
# Configuración avanzada
# -----------------------------

VALID_CHARS_RE = re.compile(r"^[a-záéíóúñü\s]+$", re.IGNORECASE)
CATEGORY_PREFIXES = {"per", "mor", "bee"}

SPANISH_STOPWORDS = {
    "yo","tú","él","ella","nosotros","ustedes","está","están",
    "estuvo","los","las","del","de","la","el","en","por","con",
    "para","se","le","lo","una","un"
}

MAX_WORDS_TARGET = 5
MAX_WORD_LENGTH = 30
MIN_WORD_LENGTH = 2

# -----------------------------
# Utilidades
# -----------------------------

def clean_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def remove_category_prefix(text: str) -> str:
    words = text.split()
    if words and words[0] in CATEGORY_PREFIXES:
        return " ".join(words[1:]).strip()
    return text

def is_valid_text(text: str) -> bool:
    if not text or len(text) < 2:
        return False
    if not VALID_CHARS_RE.match(text):
        return False
    return True

def has_spanish_stopwords(text: str) -> bool:
    return any(w in SPANISH_STOPWORDS for w in text.split())

def is_valid_target(text: str) -> bool:
    words = text.split()
    if not is_valid_text(text):
        return False
    if has_spanish_stopwords(text):
        return False
    if len(words) > MAX_WORDS_TARGET:
        return False
    if any(len(w) > MAX_WORD_LENGTH or len(w) < MIN_WORD_LENGTH for w in words):
        return False
    short_words = sum(1 for w in words if len(w) < 3)
    if len(words) > 1 and short_words / len(words) > 0.5:
        return False
    return True

# -----------------------------
# Proceso principal
# -----------------------------

def main():
    kept = 0
    skipped = 0
    source_to_targets = defaultdict(list)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Leemos y limpiamos líneas
    with open(INPUT_PATH, "r", encoding="utf-8") as fin:
        for line in fin:
            line = line.strip()
            if not line:
                skipped += 1
                continue

            try:
                source, target = line.split("\t")
            except ValueError:
                skipped += 1
                continue

            source = clean_text(source)
            target = clean_text(target)
            target = remove_category_prefix(target)

            if not is_valid_text(source) or not is_valid_target(target):
                skipped += 1
                continue

            source_to_targets[source].append(target)
            kept += 1

    # Elegimos el target más frecuente por palabra ETTE
    final_pairs = []
    for source, targets in source_to_targets.items():
        counter = Counter(targets)
        max_freq = max(counter.values())
        # Tomamos todos los targets con frecuencia máxima
        most_common_targets = [t for t, f in counter.items() if f == max_freq]
        # Los combinamos en una sola cadena separados por ";"
        combined_target = "; ".join(sorted(most_common_targets))
        final_pairs.append((source, combined_target))

    # Ordenamos alfabéticamente por palabra ETTE
    final_pairs.sort(key=lambda x: x[0])

    # Escribimos el archivo final
    with open(OUTPUT_PATH, "w", encoding="utf-8") as fout:
        for source, target in final_pairs:
            fout.write(f"{source}\t{target}\n")

    print(f"[OK] Pares finales entrenables (frecuencia): {len(final_pairs)}")
    print(f"[SKIP] Pares descartados: {skipped}")
    print(f"[OUT] Archivo generado: {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
