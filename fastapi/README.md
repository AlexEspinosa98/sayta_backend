# FastAPI - Traductor Espanol a Ette

Proyecto independiente de FastAPI que replica la logica del endpoint de traduccion (`/traducir`) usando embeddings + FAISS.

## Estructura

```text
fastapi/
  app/
    main.py
    config.py
    schemas.py
    services/
      pipeline.py
      search_engine.py
  embeddings/
    metadata.json
    faiss_index.bin
    embeddings.npy
    ...
  requirements.txt
```

## Instalacion

```bash
cd fastapi
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Ejecucion

```bash
cd fastapi
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

## Endpoint unico

- `GET /traducir`: ayuda rapida.
- `POST /traducir`: recibe `{ "frase": "..." }` o `{ "sentence": "..." }`.

Ejemplo:

```bash
curl -X POST "http://127.0.0.1:8001/traducir" \
  -H "Content-Type: application/json" \
  -d '{"frase":"hola mundo"}'
```

## Configuracion opcional

- `ETTE_EMBEDDINGS_DIR`: ruta de embeddings (por defecto `fastapi/embeddings`).
- `ETTE_MODEL_NAME`: modelo de sentence-transformers (por defecto `intfloat/multilingual-e5-base`).
- `ETTE_TOP_K`: cantidad de candidatos por token (por defecto `5`).
