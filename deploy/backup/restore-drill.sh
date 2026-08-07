#!/usr/bin/env bash
# Restore a verified backup into a local disposable drill database only.
set -euo pipefail

backup_file="${1:?usage: restore-drill.sh <backup.sql.gz> <drill_db_name>}"
drill_db="${2:?usage: restore-drill.sh <backup.sql.gz> <drill_db_name>}"
DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-3306}"
DB_USER="${DB_USER:-root}"
: "${DB_PASSWORD:?DB_PASSWORD must be set}"

case "$DB_HOST" in
  127.0.0.1|localhost|::1) ;;
  *) echo "restore drill refuses non-local DB_HOST=$DB_HOST" >&2; exit 2 ;;
esac

case "$drill_db" in
  *_drill|*_restore_test|*_e2e) ;;
  *) echo "restore drill database must end with _drill, _restore_test, or _e2e" >&2; exit 2 ;;
esac

case "${APP_ENV:-test}" in
  production|prod) echo "restore drill refuses APP_ENV=${APP_ENV}" >&2; exit 2 ;;
esac

case "${DEPLOYMENT_MODE:-local}" in
  production) echo "restore drill refuses DEPLOYMENT_MODE=production" >&2; exit 2 ;;
esac

test -f "$backup_file"
gzip -t "$backup_file"
if [ -f "${backup_file}.sha256" ]; then
  (cd "$(dirname "$backup_file")" && sha256sum -c "$(basename "${backup_file}.sha256")")
fi

MYSQL=(mysql -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER")
export MYSQL_PWD="$DB_PASSWORD"

"${MYSQL[@]}" -e "DROP DATABASE IF EXISTS \`${drill_db}\`; CREATE DATABASE \`${drill_db}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
gunzip -c "$backup_file" | "${MYSQL[@]}" "$drill_db"

table_count="$("${MYSQL[@]}" -Nse "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='${drill_db}'")"
if [ "${table_count:-0}" -lt 10 ]; then
  echo "restore drill produced suspicious table count: $table_count" >&2
  exit 1
fi

alembic_rows="$("${MYSQL[@]}" -Nse "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='${drill_db}' AND table_name='alembic_version'")"
if [ "$alembic_rows" != "1" ]; then
  echo "restored database is missing alembic_version" >&2
  exit 1
fi

tenant_rows="$("${MYSQL[@]}" -Nse "SELECT COUNT(*) FROM \`${drill_db}\`.t_tenant WHERE is_deleted=0" 2>/dev/null || echo 0)"
if [ "${tenant_rows:-0}" -lt 2 ]; then
  echo "restore drill expected at least two active tenants; found $tenant_rows" >&2
  exit 1
fi

unset MYSQL_PWD
echo "restore drill complete: db=${drill_db} tables=${table_count} tenants=${tenant_rows}"
