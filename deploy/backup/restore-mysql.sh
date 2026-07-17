#!/usr/bin/env bash
# Restore a gzip backup. Use a dedicated empty drill database whenever possible.
set -euo pipefail

backup_file="${1:?usage: restore-mysql.sh <backup.sql.gz>}"
DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-3306}"
DB_NAME="${DB_NAME:-saas_lifecycle}"
DB_USER="${DB_USER:-saas_user}"
: "${DB_PASSWORD:?DB_PASSWORD must be set}"

test -f "$backup_file"
gzip -t "$backup_file"
if [ -f "${backup_file}.sha256" ]; then
  (cd "$(dirname "$backup_file")" && sha256sum -c "$(basename "${backup_file}.sha256")")
fi

echo "[restore] target=${DB_NAME}@${DB_HOST}:${DB_PORT} file=${backup_file}"
read -r -p "[restore] type RESTORE-${DB_NAME} to continue: " confirmation
[ "$confirmation" = "RESTORE-${DB_NAME}" ] || { echo "[restore] cancelled"; exit 1; }

timestamp="$(date +%Y%m%d_%H%M%S)"
safety_copy="${TMPDIR:-/tmp}/${DB_NAME}_pre_restore_${timestamp}.sql.gz"
MYSQL_PWD="$DB_PASSWORD" mysqldump -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" \
  --single-transaction --quick --routines --events --triggers "$DB_NAME" | gzip -9 > "$safety_copy"
gzip -t "$safety_copy"
echo "[restore] pre-restore safety copy: $safety_copy"

gunzip -c "$backup_file" | MYSQL_PWD="$DB_PASSWORD" mysql \
  -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" "$DB_NAME"
MYSQL_PWD="$DB_PASSWORD" mysql -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" \
  -Nse "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='${DB_NAME}'"
echo "[restore] complete; verify /health/ready, login and tenant-isolation smoke tests"
