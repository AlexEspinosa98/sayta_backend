# ============================================================
# Dockerfile - Sayta Backend (Django + Gunicorn)
# Traductor Ette-Español con búsqueda semántica FAISS
# ============================================================

# Etapa base: imagen Python slim para producción
FROM python:3.11-slim AS base

# Variables de entorno para Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Dependencias del sistema necesarias para numpy, faiss y compilación
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libopenblas-dev \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Directorio de trabajo
WORKDIR /app

# ============================================================
# Etapa de dependencias: instalar paquetes Python
# ============================================================
FROM base AS deps

COPY requirements.txt .

# Instalar dependencias.
# torch con CUDA 12.4 (cu124): el wheel trae su propio runtime CUDA;
# el driver NVIDIA del host se inyecta en runtime vía CDI (runtime: nvidia).
# Compatible con las RTX 3060 Ti (Ampere, sm_86) y driver 580.x.
RUN pip install --upgrade pip && \
    pip install \
        torch==2.5.1 --index-url https://download.pytorch.org/whl/cu124 && \
    pip install -r requirements.txt

# ============================================================
# Etapa final de producción
# ============================================================
FROM base AS production

# Copiar dependencias instaladas desde la etapa deps
COPY --from=deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# Copiar código fuente de la aplicación
COPY . /app/

# Entrypoint: aplica migraciones (como rol owner) antes de arrancar gunicorn.
# Ver entrypoint.sh para el porqué de las credenciales de migración separadas.
RUN chmod +x /app/entrypoint.sh
ENTRYPOINT ["/app/entrypoint.sh"]

# Puerto en el que escucha gunicorn
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

# Comando de inicio: gunicorn con workers para producción
# - 2 workers por núcleo (ajustar según carga)
# - timeout extendido por carga de modelos FAISS en primera petición
CMD ["gunicorn", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "2", \
     "--timeout", "180", \
     "--graceful-timeout", "60", \
     "--keep-alive", "5", \
     "--log-level", "info", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "sayta_backend.wsgi:application"]
