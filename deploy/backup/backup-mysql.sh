#!/usr/bin/env bash
# Create one verified backup set: MySQL + uploads + SHA-256 sidecars + manifest.
set -euo pipefail

DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-3306}"
DB_USER="${DB_USER:-saas_user}"
DB_NAME="${DB_NAME:-saas_lifecycle}"
: "${DB_PASSWORD:?DB_PASSWORD must be set}"
BACKUP_DIR="${BACKUP_DIR:-/var/lib/school-lifecycle-backup}"
KEEP_DAYS="${KEEP_DAYS:-14}"
MIN_LOCAL_BACKUP_SETS="${MIN_LOCAL_BACKUP_SETS:-8}"
UPLOAD_DIR="${UPLOAD_DIR:-/opt/school-lifecycle/shared/uploads}"
REQUIRE_UPLOAD_BACKUP="${REQUIRE_UPLOAD_BACKUP:-0}"

if ! [[ "$KEEP_DAYS" =~ ^[0-9]+$ ]] || [ "$KEEP_DAYS" -lt 1 ]; then
  echo "KEEP_DAYS must be a positive integer" >&2
  exit 2
fi
if ! [[ "$MIN_LOCAL_BACKUP_SETS" =~ ^[0-9]+$ ]] || [ "$MIN_LOCAL_BACKUP_SETS" -lt 1 ]; then
  echo "MIN_LOCAL_BACKUP_SETS must be a positive integer" >&2
  exit 2
fi

mkdir -p -- "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR" 2>/dev/null || true

timestamp="$(date -u +%Y%m%d_%H%M%S)"
created_epoch="$(date +%s)"
db_file="$BACKUP_DIR/db_${DB_NAME}_${timestamp}.sql.gz"
db_temp="${db_file}.partial"
upload_file="$BACKUP_DIR/uploads_${timestamp}.tar.gz"
upload_temp="${upload_file}.partial"
manifest_file="$BACKUP_DIR/manifest_${timestamp}.json"
manifest_temp="${manifest_file}.partial"
committed=0

cleanup_incomplete() {
  rm -f -- "$db_temp" "$upload_temp" "$manifest_temp"
  if [ "$committed" != "1" ]; then
    rm -f -- \
      "$db_file" "${db_file}.sha256" \
      "$upload_file" "${upload_file}.sha256" \
      "$manifest_file" "${manifest_file}.sha256"
  fi
}
trap cleanup_incomplete EXIT

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
  unsafe_upload_entry="$(find "$UPLOAD_DIR" \( -type l -o -type b -o -type c -o -type p -o -type s \) -print -quit)"
  if [ -n "$unsafe_upload_entry" ]; then
    echo "unsafe upload entry is not allowed in governed backups: $unsafe_upload_entry" >&2
    exit 1
  fi
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
write_sidecar "$manifest_file"
committed=1

# Prune complete backup sets together and always keep a minimum number of valid recovery points.
python3 - "$BACKUP_DIR" "$KEEP_DAYS" "$MIN_LOCAL_BACKUP_SETS" <<'PY'
import json
import sys
import time
from pathlib import Path

root = Path(sys.argv[1]).resolve()
keep_days = int(sys.argv[2])
min_sets = int(sys.argv[3])
cutoff = time.time() - keep_days * 86400
manifests = sorted(root.glob("manifest_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
protected = {p.resolve() for p in manifests[:min_sets]}

def safe_name(value):
    if value is None:
        return None
    if not isinstance(value, str) or Path(value).name != value or value in {".", ".."}:
        raise ValueError(f"unsafe manifest filename: {value!r}")
    return value

for manifest in manifests:
    if manifest.resolve() in protected or manifest.stat().st_mtime >= cutoff:
        continue
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        db_name = safe_name(payload["database"]["file"])
        upload_name = safe_name(payload.get("uploads", {}).get("file"))
    except Exception as exc:
        print(f"WARN: retention skipped malformed manifest {manifest.name}: {exc}", file=sys.stderr)
        continue
    names = [db_name, f"{db_name}.sha256", manifest.name, f"{manifest.name}.sha256"]
    if upload_name:
        names.extend([upload_name, f"{upload_name}.sha256"])
    for name in names:
        try:
            (root / name).unlink()
        except FileNotFoundError:
            pass
    print(f"retention_pruned_backup_set={manifest.name}")
PY

trap - EXIT
echo "[$(date -Is)] backup set complete: $manifest_file"
