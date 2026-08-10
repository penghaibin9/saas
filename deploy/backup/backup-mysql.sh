#!/usr/bin/env bash
# Create one verified backup set: MySQL + uploads + SHA-256 sidecars + manifest.
# Credentials are read only from environment variables.
set -euo pipefail

DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-3306}"
DB_USER="${DB_USER:-saas_user}"
DB_NAME="${DB_NAME:-saas_lifecycle}"
: "${DB_PASSWORD:?DB_PASSWORD must be set}"
BACKUP_DIR="${BACKUP_DIR:-/var/lib/school-lifecycle-backup}"
KEEP_DAYS="${KEEP_DAYS:-14}"
UPLOAD_DIR="${UPLOAD_DIR:-/opt/school-lifecycle/shared/uploads}"
REQUIRE_UPLOAD_BACKUP="${REQUIRE_UPLOAD_BACKUP:-0}"

mkdir -p -- "$BACKUP_DIR"
test -d "$BACKUP_DIR"

timestamp="$(date -u +%Y%m%d_%H%M%S)"
created_epoch="$(date +%s)"
db_file="$BACKUP_DIR/db_${DB_NAME}_${timestamp}.sql.gz"
db_temp="${db_file}.partial"
upload_file="$BACKUP_DIR/uploads_${timestamp}.tar.gz"
upload_temp="${upload_file}.partial"
manifest_file="$BACKUP_DIR/manifest_${timestamp}.json"
manifest_temp="${manifest_file}.partial"

cleanup_partial() {
  rm -f -- "$db_temp" "$upload_temp" "$manifest_temp"
}
trap cleanup_partial EXIT

write_sidecar() {
  local file="$1"
  local base
  base="$(basename "$file")"
  (
    cd "$BACKUP_DIR"
    sha256sum "$base" > "${base}.sha256"
  )
}

echo "[$(date -Is)] starting MySQL backup: ${DB_NAME}@${DB_HOST}:${DB_PORT}"
MYSQL_PWD="$DB_PASSWORD" mysqldump \
  -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" \
  --single-transaction --quick --routines --events --triggers \
  --hex-blob --default-character-set=utf8mb4 --source-data=2 \
  "$DB_NAME" | gzip -9 > "$db_temp"

test -s "$db_temp"
gzip -t "$db_temp"
mv -- "$db_temp" "$db_file"
write_sidecar "$db_file"

db_hash="$(sha256sum "$db_file" | awk '{print $1}')"
db_size="$(stat -c '%s' "$db_file")"
upload_name=""
upload_hash=""
upload_size=0

if [ -d "$UPLOAD_DIR" ]; then
  tar -czf "$upload_temp" -C "$(dirname "$UPLOAD_DIR")" "$(basename "$UPLOAD_DIR")"
  test -s "$upload_temp"
  tar -tzf "$upload_temp" >/dev/null
  mv -- "$upload_temp" "$upload_file"
  write_sidecar "$upload_file"
  upload_name="$(basename "$upload_file")"
  upload_hash="$(sha256sum "$upload_file" | awk '{print $1}')"
  upload_size="$(stat -c '%s' "$upload_file")"
elif [ "$REQUIRE_UPLOAD_BACKUP" = "1" ] || [ "$REQUIRE_UPLOAD_BACKUP" = "true" ]; then
  echo "required upload directory is missing: $UPLOAD_DIR" >&2
  exit 1
else
  echo "[$(date -Is)] WARN: upload directory not present; upload archive skipped: $UPLOAD_DIR" >&2
fi

DB_FILE_NAME="$(basename "$db_file")" \
DB_HASH="$db_hash" \
DB_SIZE="$db_size" \
UPLOAD_FILE_NAME="$upload_name" \
UPLOAD_HASH="$upload_hash" \
UPLOAD_SIZE="$upload_size" \
REQUIRE_UPLOAD_BACKUP="$REQUIRE_UPLOAD_BACKUP" \
CREATED_EPOCH="$created_epoch" \
TIMESTAMP="$timestamp" \
DB_NAME="$DB_NAME" \
python3 - "$manifest_temp" <<'PY'
import json
import os
import sys
from datetime import datetime, timezone

path = sys.argv[1]
upload_name = os.environ["UPLOAD_FILE_NAME"]
required = os.environ["REQUIRE_UPLOAD_BACKUP"].lower() in {"1", "true"}
payload = {
    "schemaVersion": 1,
    "backupSetId": os.environ["TIMESTAMP"],
    "createdAtUtc": datetime.now(timezone.utc).isoformat(),
    "createdAtEpoch": int(os.environ["CREATED_EPOCH"]),
    "databaseName": os.environ["DB_NAME"],
    "database": {
        "file": os.environ["DB_FILE_NAME"],
        "sha256": os.environ["DB_HASH"],
        "sizeBytes": int(os.environ["DB_SIZE"]),
    },
    "uploads": {
        "required": required,
        "file": upload_name or None,
        "sha256": os.environ["UPLOAD_HASH"] or None,
        "sizeBytes": int(os.environ["UPLOAD_SIZE"]),
    },
}
with open(path, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
    handle.write("\n")
PY

test -s "$manifest_temp"
mv -- "$manifest_temp" "$manifest_file"

# Only complete manifests are valid backup-set commit markers. Orphaned partial data can exist
# after a failed run, but it is never selected for restore and will age out with retention.
find "$BACKUP_DIR" -maxdepth 1 -type f \
  \( -name 'db_*.sql.gz' -o -name 'db_*.sql.gz.sha256' -o \
     -name 'uploads_*.tar.gz' -o -name 'uploads_*.tar.gz.sha256' -o \
     -name 'manifest_*.json' \) \
  -mtime "+$KEEP_DAYS" -delete

trap - EXIT
echo "[$(date -Is)] backup set complete: $manifest_file"
