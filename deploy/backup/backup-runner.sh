#!/usr/bin/env bash
# Production orchestration: encrypted local backup set + mandatory verified offsite copy.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="${BACKUP_DIR:-/var/lib/school-lifecycle-backup}"
DB_NAME="${DB_NAME:-saas_lifecycle}"
BACKUP_RCLONE_REMOTE="${BACKUP_RCLONE_REMOTE:-}"
RCLONE_CONFIG="${RCLONE_CONFIG:-/etc/school-lifecycle/rclone.conf}"
BACKUP_REQUIRE_OFFSITE="${BACKUP_REQUIRE_OFFSITE:-true}"
BACKUP_REQUIRE_IMMUTABLE_REMOTE="${BACKUP_REQUIRE_IMMUTABLE_REMOTE:-true}"
BACKUP_IMMUTABLE_REMOTE_CONFIRMED="${BACKUP_IMMUTABLE_REMOTE_CONFIRMED:-false}"
BACKUP_REQUIRE_ENCRYPTION="${BACKUP_REQUIRE_ENCRYPTION:-true}"
BACKUP_AGE_RECIPIENT="${BACKUP_AGE_RECIPIENT:-}"
BACKUP_ALERT_WEBHOOK_URL="${BACKUP_ALERT_WEBHOOK_URL:-}"
BACKUP_LOCK_FILE="${BACKUP_LOCK_FILE:-$BACKUP_DIR/.backup.lock}"

is_true() {
  case "${1,,}" in
    1|true|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}

mkdir -p -- "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR" 2>/dev/null || true
export BACKUP_DIR

alert_failure() {
  local status="$1"
  local message="school-lifecycle backup failed: db=${DB_NAME} host=$(hostname) status=${status}"
  echo "[$(date -Is)] ERROR: $message" >&2
  if [ -n "$BACKUP_ALERT_WEBHOOK_URL" ]; then
    python3 - "$message" <<'PY' | curl -fsS --max-time 10 -H 'Content-Type: application/json' -X POST --data-binary @- "$BACKUP_ALERT_WEBHOOK_URL" >/dev/null || true
import json, sys
print(json.dumps({"text": sys.argv[1]}, ensure_ascii=False))
PY
  fi
}

on_error() {
  local status=$?
  trap - ERR
  alert_failure "$status"
  exit "$status"
}
trap on_error ERR

command -v flock >/dev/null 2>&1 || { echo "flock is required" >&2; exit 1; }
exec 9>"$BACKUP_LOCK_FILE"
flock -n 9 || { echo "another backup run is already active" >&2; exit 1; }

if ! is_true "$BACKUP_REQUIRE_OFFSITE"; then
  echo "production backup runner requires BACKUP_REQUIRE_OFFSITE=true" >&2
  exit 1
fi
if [ -z "$BACKUP_RCLONE_REMOTE" ]; then
  echo "BACKUP_RCLONE_REMOTE must be configured for production backups" >&2
  exit 1
fi
if is_true "$BACKUP_REQUIRE_IMMUTABLE_REMOTE" && ! is_true "$BACKUP_IMMUTABLE_REMOTE_CONFIRMED"; then
  echo "immutable/versioned offsite storage must be operationally confirmed before backup can succeed" >&2
  exit 1
fi
if ! is_true "$BACKUP_REQUIRE_ENCRYPTION"; then
  echo "production backup runner requires BACKUP_REQUIRE_ENCRYPTION=true" >&2
  exit 1
fi
if [[ "$BACKUP_AGE_RECIPIENT" != age1* ]]; then
  echo "production backup runner requires BACKUP_AGE_RECIPIENT=age1..." >&2
  exit 1
fi
command -v age >/dev/null 2>&1 || { echo "age is required for encrypted production backups" >&2; exit 1; }
command -v rclone >/dev/null 2>&1 || { echo "rclone is required for offsite backups" >&2; exit 1; }

RCLONE_ARGS=()
if [[ "$BACKUP_RCLONE_REMOTE" == *:* ]]; then
  if [ ! -r "$RCLONE_CONFIG" ]; then
    echo "rclone config is not readable by the backup service: $RCLONE_CONFIG" >&2
    exit 1
  fi
  RCLONE_ARGS=(--config "$RCLONE_CONFIG")
fi

bash "$SCRIPT_DIR/backup-mysql.sh"

manifest="$(find "$BACKUP_DIR" -maxdepth 1 -type f -name 'manifest_*.json' -printf '%T@ %p\n' | sort -nr | head -n1 | cut -d' ' -f2-)"
test -n "$manifest"
test -s "$manifest"
test -f "${manifest}.sha256"
(
  cd "$BACKUP_DIR"
  sha256sum -c "$(basename "${manifest}.sha256")"
)

mapfile -t manifest_fields < <(python3 - "$manifest" <<'PY'
import json, sys
from pathlib import Path
m = json.load(open(sys.argv[1], encoding="utf-8"))
if m.get("schemaVersion") != 2:
    raise SystemExit("production runner requires manifest schemaVersion=2")
enc = m.get("encryption") or {}
if enc.get("format") != "age" or enc.get("dataEncrypted") is not True:
    raise SystemExit("production runner requires age-encrypted data artifacts")
for key in ("database", "uploads"):
    if key not in m:
        raise SystemExit(f"manifest missing {key}")

def safe_name(value):
    if value is None:
        return ""
    if not isinstance(value, str) or Path(value).name != value or value in {".", ".."}:
        raise SystemExit(f"unsafe manifest filename: {value!r}")
    return value

print(safe_name(m["database"]["file"]))
print(m["database"]["sha256"])
print(safe_name(m["uploads"].get("file")))
print(m["uploads"].get("sha256") or "")
print("true" if m["uploads"].get("required") else "false")
PY
)

db_name="${manifest_fields[0]}"
db_hash="${manifest_fields[1]}"
upload_name="${manifest_fields[2]}"
upload_hash="${manifest_fields[3]}"
upload_required="${manifest_fields[4]}"

if [[ "$db_name" != *.age ]]; then
  echo "database artifact is not encrypted with age: $db_name" >&2
  exit 1
fi
if [ -n "$upload_name" ] && [[ "$upload_name" != *.age ]]; then
  echo "upload artifact is not encrypted with age: $upload_name" >&2
  exit 1
fi

verify_local_object() {
  local name="$1" expected_hash="$2"
  local file="$BACKUP_DIR/$name"
  test -s "$file"
  test -f "${file}.sha256"
  (
    cd "$BACKUP_DIR"
    sha256sum -c "${name}.sha256"
  )
  test "$(sha256sum "$file" | awk '{print $1}')" = "$expected_hash"
}

verify_local_object "$db_name" "$db_hash"
if [ -n "$upload_name" ]; then
  verify_local_object "$upload_name" "$upload_hash"
elif [ "$upload_required" = "true" ]; then
  echo "manifest requires uploads but does not contain an upload archive" >&2
  exit 1
fi

copy_and_readback() {
  local file="$1"
  local remote_path="${BACKUP_RCLONE_REMOTE%/}/$(basename "$file")"
  rclone "${RCLONE_ARGS[@]}" copyto "$file" "$remote_path" --checksum

  local local_size remote_size local_hash remote_hash
  local_size="$(stat -c '%s' "$file")"
  remote_size="$(rclone "${RCLONE_ARGS[@]}" size "$remote_path" --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["bytes"])')"
  test "$remote_size" = "$local_size"
  local_hash="$(sha256sum "$file" | awk '{print $1}')"
  remote_hash="$(rclone "${RCLONE_ARGS[@]}" cat "$remote_path" | sha256sum | awk '{print $1}')"
  test "$remote_hash" = "$local_hash"
}

# Copy encrypted data and all checksum sidecars first. The manifest is copied last and acts as
# the remote commit marker; no restore tooling treats a set without that manifest as complete.
copy_and_readback "$BACKUP_DIR/$db_name"
copy_and_readback "$BACKUP_DIR/${db_name}.sha256"
if [ -n "$upload_name" ]; then
  copy_and_readback "$BACKUP_DIR/$upload_name"
  copy_and_readback "$BACKUP_DIR/${upload_name}.sha256"
fi
copy_and_readback "${manifest}.sha256"
copy_and_readback "$manifest"

echo "[$(date -Is)] offsite encrypted backup set verified by independent SHA-256 readback: $(basename "$manifest")"
trap - ERR
echo "[$(date -Is)] backup runner complete"
