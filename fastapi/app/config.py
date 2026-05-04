from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
EMBEDDINGS_DIR = Path(os.getenv("ETTE_EMBEDDINGS_DIR", BASE_DIR / "embeddings"))
MODEL_NAME = os.getenv("ETTE_MODEL_NAME", "intfloat/multilingual-e5-base")
DEFAULT_TOP_K = int(os.getenv("ETTE_TOP_K", "5"))
