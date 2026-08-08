#!/usr/bin/env bash
# MySQL full backup. Credentials come only from environment variables.
set -euo pipefail

DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-3306}"
DB_USER="${DB_USER:-saas_user}"
DB_NAME="${DB_NAME:-saas_lifecycle}"
: "${DB_PASSWORD:?DB_PASSWORD must be set}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/school-lifecycle}"
KEEP_DAYS="${KEEP_DAYS:-14}"
UPLOAD_DIR="${UPLOAD_DIR:-/var/www/school-lifecycle/uploads}"
REQUIRE_UPLOAD_BACKUP="${REQUIRE_UPLOAD_BACKUP:-0}"

mkdir -p -- "$BACKUP_DIR"
test -d "$BACKUP_DIR"
timestamp="$(date +%Y%m%d_%H%M%S)"
backup_file="$BACKUP_DIR/db_${DB_NAME}_${timestamp}.sql.gz"
temp_file="${backup_file}.partial"
trap 'rm -f -- "$temp_file"' EXIT

echo "[$(date -Is)] starting MySQL backup: ${DB_NAME}@${DB_HOST}:${DB_PORT}"
MYSQL_PWD="$DB_PASSWORD" mysqldump \
  -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" \
  --single-transaction --quick --routines --events --triggers \
  --hex-blob --default-character-set=utf8mb4 --source-data=2 \
  "$DB_NAME" | gzip -9 > "$temp_file"

test -s "$temp_file"
gzip -t "$temp_file"
mv -- "$temp_file" "$backup_file"
sha256sum "$backup_file" > "${backup_file}.sha256"
trap - EXIT

if [ -d "$UPLOAD_DIR" ]; then
  upload_file="$BACKUP_DIR/uploads_${timestamp}.tar.gz"
  tar -czf "$upload_file" -C "$(dirname "$UPLOAD_DIR")" "$(basename "$UPLOAD_DIR")"
  test -s "$upload_file"
  sha256sum "$upload_file" > "${upload_file}.sha256"
elif [ "$REQUIRE_UPLOAD_BACKUP" = "1" ] || [ "$REQUIRE_UPLOAD_BACKUP" = "true" ]; then
  echo "required upload directory is missing: $UPLOAD_DIR" >&2
  exit 1
else
  echo "[$(date -Is)] WARN: upload directory not present; upload archive skipped: $UPLOAD_DIR" >&2
fi

# BACKUP_DIR is an explicit, validated directory; only known backup patterns expire.
find "$BACKUP_DIR" -maxdepth 1 -type f \
  \( -name 'db_*.sql.gz' -o -name 'db_*.sql.gz.sha256' -o \
     -name 'uploads_*.tar.gz' -o -name 'uploads_*.tar.gz.sha256' \) \
  -mtime "+$KEEP_DAYS" -delete

echo "[$(date -Is)] backup complete: $backup_file"
