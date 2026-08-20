#!/bin/sh
set -eu

case "${RUN_MIGRATIONS_ON_START:-false}" in
    true|TRUE|1|yes|YES)
        echo "RUN_MIGRATIONS_ON_START enabled; applying Alembic migrations"
        flask --app wsgi:app db upgrade
        ;;
    false|FALSE|0|no|NO|"")
        ;;
    *)
        echo "Invalid RUN_MIGRATIONS_ON_START value: ${RUN_MIGRATIONS_ON_START}" >&2
        exit 64
        ;;
esac

exec "$@"
