#!/usr/bin/env bash
# ============================================================
# entrypoint.sh - Sayta Backend
#
# Aplica las migraciones de base de datos ANTES de arrancar la app.
#
# Las migraciones que crean claves foraneas hacia tablas de auth core
# (p.ej. authtoken_token -> auth_user) requieren el rol PROPIETARIO de
# esas tablas. En este despliegue la app corre con un rol sin privilegios
# (sayta_app), por lo que migrate fallaria con:
#     permission denied for table auth_user
# dejando la BD a medias (faltan authtoken_token, perfiles_usuario, ...).
#
# Solucion: si se definen POSTGRES_MIGRATION_USER / POSTGRES_MIGRATION_PASSWORD
# (rol owner, p.ej. sayta), migrate se ejecuta con esas credenciales. La app
# (gunicorn) sigue arrancando con el rol normal de POSTGRES_USER.
# ============================================================
set -euo pipefail

MIGRATE_USER="${POSTGRES_MIGRATION_USER:-${POSTGRES_USER:-}}"

echo "[entrypoint] Aplicando migraciones (rol: ${MIGRATE_USER})..."
POSTGRES_USER="${MIGRATE_USER}" \
POSTGRES_PASSWORD="${POSTGRES_MIGRATION_PASSWORD:-${POSTGRES_PASSWORD:-}}" \
    python manage.py migrate --noinput

echo "[entrypoint] Migraciones OK. Arrancando aplicacion: $*"
exec "$@"
