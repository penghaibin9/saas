#!/usr/bin/env bash
# Restore a verified backup into a local disposable drill database only.
set -euo pipefail

backup_file="${1:?usage: restore-drill.sh <backup.sql.gz> <drill_db_name>}"
drill_db="${2:?usage: restore-drill.sh <backup.sql.gz> <drill_db_name>}"
DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-3306}"
DB_USER="${DB_USER:-root}"
: "${DB_PASSWORD:?DB_PASSWORD must be set}"
# Production baseline from the release runbook: RPO <= 6h and RTO <= 2h.
# CI may override these with tighter thresholds for a small fixture database.
MAX_BACKUP_AGE_SECONDS="${MAX_BACKUP_AGE_SECONDS:-21600}"
MAX_RESTORE_SECONDS="${MAX_RESTORE_SECONDS:-7200}"
EXPECTED_ALEMBIC_VERSION="${EXPECTED_ALEMBIC_VERSION:-}"
REQUIRED_RESTORE_TABLES="${REQUIRED_RESTORE_TABLES:-alembic_version,t_tenant}"
MIN_RESTORE_INDEXES="${MIN_RESTORE_INDEXES:-10}"
MIN_RESTORE_FOREIGN_KEYS="${MIN_RESTORE_FOREIGN_KEYS:-1}"
RESTORE_EVIDENCE_FILE="${RESTORE_EVIDENCE_FILE:-}"

case "$DB_HOST" in
  127.0.0.1|localhost|::1) ;;
  *) echo "restore drill refuses non-local DB_HOST=$DB_HOST" >&2; exit 2 ;;
esac

if [[ ! "$drill_db" =~ ^[A-Za-z0-9_]+(_drill|_restore_test|_e2e)$ ]]; then
  echo "restore drill database must contain only letters/digits/underscore and end with _drill, _restore_test, or _e2e" >&2
  exit 2
fi

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
else
  echo "restore drill requires a SHA-256 sidecar: ${backup_file}.sha256" >&2
  exit 1
fi

now_epoch="$(date +%s)"
backup_mtime="$(stat -c '%Y' "$backup_file")"
backup_age_seconds="$((now_epoch - backup_mtime))"
if [ "$backup_age_seconds" -lt 0 ] || [ "$backup_age_seconds" -gt "$MAX_BACKUP_AGE_SECONDS" ]; then
  echo "backup is outside the allowed RPO freshness window: age=${backup_age_seconds}s max=${MAX_BACKUP_AGE_SECONDS}s" >&2
  exit 1
fi

MYSQL=(mysql -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER")
export MYSQL_PWD="$DB_PASSWORD"
restore_started_epoch="$(date +%s)"

"${MYSQL[@]}" -e "DROP DATABASE IF EXISTS \`${drill_db}\`; CREATE DATABASE \`${drill_db}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
gunzip -c "$backup_file" | "${MYSQL[@]}" "$drill_db"

restore_finished_epoch="$(date +%s)"
restore_seconds="$((restore_finished_epoch - restore_started_epoch))"
if [ "$restore_seconds" -gt "$MAX_RESTORE_SECONDS" ]; then
  echo "restore exceeded RTO threshold: restore=${restore_seconds}s max=${MAX_RESTORE_SECONDS}s" >&2
  exit 1
fi

table_count="$("${MYSQL[@]}" -Nse "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='${drill_db}'")"
if [ "${table_count:-0}" -lt 10 ]; then
  echo "restore drill produced suspicious table count: $table_count" >&2
  exit 1
fi

IFS=',' read -r -a required_tables <<< "$REQUIRED_RESTORE_TABLES"
for table_name in "${required_tables[@]}"; do
  table_name="${table_name//[[:space:]]/}"
  [[ "$table_name" =~ ^[A-Za-z0-9_]+$ ]] || {
    echo "invalid required table name: $table_name" >&2
    exit 2
  }
  table_exists="$("${MYSQL[@]}" -Nse "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='${drill_db}' AND table_name='${table_name}'")"
  if [ "$table_exists" != "1" ]; then
    echo "restored database is missing required table: $table_name" >&2
    exit 1
  fi
done

alembic_version="$("${MYSQL[@]}" -Nse "SELECT version_num FROM \`${drill_db}\`.alembic_version LIMIT 1")"
if [ -z "$alembic_version" ]; then
  echo "restored database has an empty alembic_version" >&2
  exit 1
fi
if [ -n "$EXPECTED_ALEMBIC_VERSION" ] && [ "$alembic_version" != "$EXPECTED_ALEMBIC_VERSION" ]; then
  echo "restored Alembic version mismatch: expected=$EXPECTED_ALEMBIC_VERSION actual=$alembic_version" >&2
  exit 1
fi

index_count="$("${MYSQL[@]}" -Nse "SELECT COUNT(*) FROM information_schema.statistics WHERE table_schema='${drill_db}'")"
if [ "${index_count:-0}" -lt "$MIN_RESTORE_INDEXES" ]; then
  echo "restore drill produced suspicious index count: $index_count" >&2
  exit 1
fi

foreign_key_count="$("${MYSQL[@]}" -Nse "SELECT COUNT(*) FROM information_schema.referential_constraints WHERE constraint_schema='${drill_db}'")"
if [ "${foreign_key_count:-0}" -lt "$MIN_RESTORE_FOREIGN_KEYS" ]; then
  echo "restore drill produced suspicious foreign-key count: $foreign_key_count" >&2
  exit 1
fi

tenant_rows="$("${MYSQL[@]}" -Nse "SELECT COUNT(*) FROM \`${drill_db}\`.t_tenant WHERE is_deleted=0" 2>/dev/null || echo 0)"
if [ "${tenant_rows:-0}" -lt 2 ]; then
  echo "restore drill expected at least two active tenants; found $tenant_rows" >&2
  exit 1
fi

if [ -n "$RESTORE_EVIDENCE_FILE" ]; then
  mkdir -p "$(dirname "$RESTORE_EVIDENCE_FILE")"
  cat > "$RESTORE_EVIDENCE_FILE" <<EOF
backup_file=$(basename "$backup_file")
backup_age_seconds=$backup_age_seconds
max_backup_age_seconds=$MAX_BACKUP_AGE_SECONDS
restore_seconds=$restore_seconds
max_restore_seconds=$MAX_RESTORE_SECONDS
alembic_version=$alembic_version
table_count=$table_count
index_count=$index_count
foreign_key_count=$foreign_key_count
active_tenant_count=$tenant_rows
EOF
fi

unset MYSQL_PWD
echo "restore drill complete: db=${drill_db} alembic=${alembic_version} tables=${table_count} indexes=${index_count} foreign_keys=${foreign_key_count} tenants=${tenant_rows} restore_seconds=${restore_seconds} backup_age_seconds=${backup_age_seconds}"
