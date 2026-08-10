#!/usr/bin/env bash
# Restore a manifest-committed backup set into a disposable local drill database only.
set -euo pipefail

manifest_file="${1:?usage: restore-drill.sh <manifest.json> <drill_db_name>}"
drill_db="${2:?usage: restore-drill.sh <manifest.json> <drill_db_name>}"
DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-3306}"
DB_USER="${DB_USER:-root}"
: "${DB_PASSWORD:?DB_PASSWORD must be set}"
MAX_BACKUP_AGE_SECONDS="${MAX_BACKUP_AGE_SECONDS:-21600}"
MAX_RESTORE_SECONDS="${MAX_RESTORE_SECONDS:-7200}"
EXPECTED_ALEMBIC_VERSION="${EXPECTED_ALEMBIC_VERSION:-}"
REQUIRED_RESTORE_TABLES="${REQUIRED_RESTORE_TABLES:-alembic_version,t_tenant}"
MIN_RESTORE_TABLES="${MIN_RESTORE_TABLES:-2}"
MIN_RESTORE_INDEXES="${MIN_RESTORE_INDEXES:-1}"
MIN_RESTORE_FOREIGN_KEYS="${MIN_RESTORE_FOREIGN_KEYS:-0}"
MIN_ACTIVE_TENANTS="${MIN_ACTIVE_TENANTS:-0}"
RESTORE_EVIDENCE_FILE="${RESTORE_EVIDENCE_FILE:-}"

case "$DB_HOST" in
  127.0.0.1|localhost|::1) ;;
  *) echo "restore drill refuses non-local DB_HOST=$DB_HOST" >&2; exit 2 ;;
esac
case "${APP_ENV:-test}" in
  production|prod) echo "restore drill refuses APP_ENV=${APP_ENV}" >&2; exit 2 ;;
esac
case "${DEPLOYMENT_MODE:-local}" in
  production) echo "restore drill refuses DEPLOYMENT_MODE=production" >&2; exit 2 ;;
esac
if [[ ! "$drill_db" =~ ^[A-Za-z0-9_]+(_drill|_restore_test|_e2e)$ ]]; then
  echo "restore drill database must end with _drill, _restore_test, or _e2e" >&2
  exit 2
fi

test -s "$manifest_file"
backup_dir="$(cd "$(dirname "$manifest_file")" && pwd)"

mapfile -t fields < <(python3 - "$manifest_file" <<'PY'
import json, sys
from pathlib import Path
m = json.load(open(sys.argv[1], encoding="utf-8"))
if m.get("schemaVersion") != 1:
    raise SystemExit("unsupported manifest schema")

def safe_name(value):
    if value is None:
        return ""
    if not isinstance(value, str) or Path(value).name != value or value in {".", ".."}:
        raise SystemExit(f"unsafe manifest filename: {value!r}")
    return value

print(int(m["createdAtEpoch"]))
print(safe_name(m["database"]["file"]))
print(m["database"]["sha256"])
print(safe_name(m["uploads"].get("file")))
print(m["uploads"].get("sha256") or "")
print("true" if m["uploads"].get("required") else "false")
PY
)

created_epoch="${fields[0]}"
db_name="${fields[1]}"
db_hash="${fields[2]}"
upload_name="${fields[3]}"
upload_hash="${fields[4]}"
upload_required="${fields[5]}"
db_file="$backup_dir/$db_name"

verify_object() {
  local name="$1" expected_hash="$2"
  local file="$backup_dir/$name"
  test -s "$file"
  test -f "${file}.sha256"
  (
    cd "$backup_dir"
    sha256sum -c "${name}.sha256"
  )
  test "$(sha256sum "$file" | awk '{print $1}')" = "$expected_hash"
}

verify_object "$db_name" "$db_hash"
gzip -t "$db_file"

upload_entry_count=0
if [ -n "$upload_name" ]; then
  verify_object "$upload_name" "$upload_hash"
  tar -tzf "$backup_dir/$upload_name" >/dev/null
  upload_restore_dir="$(mktemp -d "${TMPDIR:-/tmp}/school-lifecycle-upload-restore.XXXXXX")"
  trap 'rm -rf -- "$upload_restore_dir"' EXIT
  tar -xzf "$backup_dir/$upload_name" -C "$upload_restore_dir"
  upload_entry_count="$(find "$upload_restore_dir" -mindepth 1 -print | wc -l | tr -d ' ')"
  if [ "$upload_entry_count" -lt 1 ]; then
    echo "upload archive restored no entries" >&2
    exit 1
  fi
elif [ "$upload_required" = "true" ]; then
  echo "manifest requires uploads but no upload archive is present" >&2
  exit 1
fi

now_epoch="$(date +%s)"
backup_age_seconds="$((now_epoch - created_epoch))"
if [ "$backup_age_seconds" -lt 0 ] || [ "$backup_age_seconds" -gt "$MAX_BACKUP_AGE_SECONDS" ]; then
  echo "backup is outside the allowed RPO freshness window: age=${backup_age_seconds}s max=${MAX_BACKUP_AGE_SECONDS}s" >&2
  exit 1
fi

MYSQL=(mysql -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER")
export MYSQL_PWD="$DB_PASSWORD"
restore_started_epoch="$(date +%s)"
"${MYSQL[@]}" -e "DROP DATABASE IF EXISTS \`${drill_db}\`; CREATE DATABASE \`${drill_db}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
gunzip -c "$db_file" | "${MYSQL[@]}" "$drill_db"
restore_seconds="$(( $(date +%s) - restore_started_epoch ))"

if [ "$restore_seconds" -gt "$MAX_RESTORE_SECONDS" ]; then
  echo "restore exceeded RTO threshold: restore=${restore_seconds}s max=${MAX_RESTORE_SECONDS}s" >&2
  exit 1
fi

table_count="$("${MYSQL[@]}" -Nse "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='${drill_db}'")"
if [ "${table_count:-0}" -lt "$MIN_RESTORE_TABLES" ]; then
  echo "restore drill produced suspicious table count: $table_count" >&2
  exit 1
fi

IFS=',' read -r -a required_tables <<< "$REQUIRED_RESTORE_TABLES"
for table_name in "${required_tables[@]}"; do
  table_name="${table_name//[[:space:]]/}"
  [[ "$table_name" =~ ^[A-Za-z0-9_]+$ ]] || { echo "invalid required table name: $table_name" >&2; exit 2; }
  table_exists="$("${MYSQL[@]}" -Nse "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='${drill_db}' AND table_name='${table_name}'")"
  if [ "$table_exists" != "1" ]; then
    echo "restored database is missing required table: $table_name" >&2
    exit 1
  fi
done

alembic_version="$("${MYSQL[@]}" -Nse "SELECT version_num FROM \`${drill_db}\`.alembic_version LIMIT 1" 2>/dev/null || true)"
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

tenant_rows=0
if [ "$MIN_ACTIVE_TENANTS" -gt 0 ]; then
  tenant_rows="$("${MYSQL[@]}" -Nse "SELECT COUNT(*) FROM \`${drill_db}\`.t_tenant WHERE is_deleted=0")"
  if [ "${tenant_rows:-0}" -lt "$MIN_ACTIVE_TENANTS" ]; then
    echo "restore drill expected at least ${MIN_ACTIVE_TENANTS} active tenants; found $tenant_rows" >&2
    exit 1
  fi
fi

if [ -n "$RESTORE_EVIDENCE_FILE" ]; then
  mkdir -p "$(dirname "$RESTORE_EVIDENCE_FILE")"
  cat > "$RESTORE_EVIDENCE_FILE" <<EVIDENCE
manifest=$(basename "$manifest_file")
backup_age_seconds=$backup_age_seconds
max_backup_age_seconds=$MAX_BACKUP_AGE_SECONDS
restore_seconds=$restore_seconds
max_restore_seconds=$MAX_RESTORE_SECONDS
alembic_version=$alembic_version
table_count=$table_count
index_count=$index_count
foreign_key_count=$foreign_key_count
active_tenant_count=$tenant_rows
upload_entry_count=$upload_entry_count
EVIDENCE
fi

unset MYSQL_PWD
echo "restore drill complete: db=${drill_db} tables=${table_count} indexes=${index_count} foreign_keys=${foreign_key_count} tenants=${tenant_rows} uploads=${upload_entry_count} restore_seconds=${restore_seconds} backup_age_seconds=${backup_age_seconds}"
