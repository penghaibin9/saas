#!/usr/bin/env bash
# Restore one governed backup manifest (database + uploads) while application writers are stopped.
set -euo pipefail

manifest="${1:-}"
[ -n "$manifest" ] && [ -f "$manifest" ] || { echo "usage: restore-backup-set.sh <manifest.json>" >&2; exit 2; }

DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-3306}"
DB_USER="${DB_USER:-saas_user}"
DB_NAME="${DB_NAME:-saas_lifecycle}"
: "${DB_PASSWORD:?DB_PASSWORD must be set}"
UPLOAD_DIR="${UPLOAD_DIR:-/opt/school-lifecycle/shared/uploads}"
BACKUP_DIR="$(cd "$(dirname "$manifest")" && pwd)"
manifest="$(cd "$BACKUP_DIR" && pwd)/$(basename "$manifest")"

test -s "$manifest"
test -f "${manifest}.sha256"
(
  cd "$BACKUP_DIR"
  sha256sum -c "$(basename "${manifest}.sha256")"
)

mapfile -t fields < <(python3 - "$manifest" "$DB_NAME" <<'PY'
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
expected_db = sys.argv[2]
m = json.loads(p.read_text(encoding="utf-8"))
if m.get("schemaVersion") != 1:
    raise SystemExit("unsupported manifest schema")
if m.get("databaseName") != expected_db:
    raise SystemExit(f"manifest database mismatch: {m.get('databaseName')!r} != {expected_db!r}")

def safe_name(value):
    if value is None:
        return ""
    if not isinstance(value, str) or Path(value).name != value or value in {".", ".."}:
        raise SystemExit(f"unsafe manifest filename: {value!r}")
    return value

print(safe_name(m["database"]["file"]))
print(m["database"]["sha256"])
print(safe_name((m.get("uploads") or {}).get("file")))
print((m.get("uploads") or {}).get("sha256") or "")
print("true" if (m.get("uploads") or {}).get("required") else "false")
PY
)

db_file="$BACKUP_DIR/${fields[0]}"
db_hash="${fields[1]}"
upload_name="${fields[2]}"
upload_hash="${fields[3]}"
upload_required="${fields[4]}"

verify_object() {
  local file="$1" expected_hash="$2"
  test -s "$file"
  test -f "${file}.sha256"
  (
    cd "$BACKUP_DIR"
    sha256sum -c "$(basename "${file}.sha256")"
  )
  test "$(sha256sum "$file" | awk '{print $1}')" = "$expected_hash"
}

mysql_cmd=(mysql -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" --binary-mode=1 "$DB_NAME")

verify_object "$db_file" "$db_hash"
gzip -t "$db_file"

# A failed candidate may have created objects that do not exist in the pre-release dump. Importing
# mysqldump over the live schema only restores objects that existed before; candidate-only tables,
# views, routines or events would survive and can break the next Alembic upgrade. Writers are
# already stopped by the release guard, so reset the current database object set first and then
# import the governed full dump. This restores the exact pre-release schema/data boundary without
# requiring CREATE/DROP DATABASE privileges.
echo "[$(date -Is)] clearing candidate database objects before governed restore"
cleanup_sql="$({
  MYSQL_PWD="$DB_PASSWORD" "${mysql_cmd[@]}" -N -B -e \
    "SELECT CONCAT('DROP EVENT IF EXISTS \\`', REPLACE(EVENT_NAME,'\\`','\\`\\`'), '\\`;') FROM information_schema.EVENTS WHERE EVENT_SCHEMA=DATABASE() ORDER BY EVENT_NAME;"
  MYSQL_PWD="$DB_PASSWORD" "${mysql_cmd[@]}" -N -B -e \
    "SELECT CONCAT('DROP VIEW IF EXISTS \\`', REPLACE(TABLE_NAME,'\\`','\\`\\`'), '\\`;') FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_TYPE='VIEW' ORDER BY TABLE_NAME;"
  MYSQL_PWD="$DB_PASSWORD" "${mysql_cmd[@]}" -N -B -e \
    "SELECT CONCAT('DROP TABLE IF EXISTS \\`', REPLACE(TABLE_NAME,'\\`','\\`\\`'), '\\`;') FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME;"
  MYSQL_PWD="$DB_PASSWORD" "${mysql_cmd[@]}" -N -B -e \
    "SELECT CONCAT('DROP ', ROUTINE_TYPE, ' IF EXISTS \\`', REPLACE(ROUTINE_NAME,'\\`','\\`\\`'), '\\`;') FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA=DATABASE() ORDER BY ROUTINE_TYPE, ROUTINE_NAME;"
} || exit 1)"
{
  echo "SET FOREIGN_KEY_CHECKS=0;"
  printf '%s\n' "$cleanup_sql"
  echo "SET FOREIGN_KEY_CHECKS=1;"
} | MYSQL_PWD="$DB_PASSWORD" "${mysql_cmd[@]}"

# The dump is hash-verified immediately above and includes the pre-release table schema/data plus
# configured routines/events/triggers. After the reset, no candidate-only object can survive.
echo "[$(date -Is)] restoring database from governed backup: $(basename "$db_file")"
gzip -cd "$db_file" | MYSQL_PWD="$DB_PASSWORD" "${mysql_cmd[@]}"

if [ -n "$upload_name" ]; then
  upload_file="$BACKUP_DIR/$upload_name"
  verify_object "$upload_file" "$upload_hash"
  tar -tzf "$upload_file" >/dev/null
  tmp="$(mktemp -d)"
  trap 'rm -rf -- "$tmp"' EXIT
  tar -xzf "$upload_file" -C "$tmp"
  source_dir="$tmp/$(basename "$UPLOAD_DIR")"
  [ -d "$source_dir" ] || { echo "upload archive root mismatch" >&2; exit 1; }
  mkdir -p "$UPLOAD_DIR"
  rsync -a --delete "$source_dir/" "$UPLOAD_DIR/"
  rm -rf -- "$tmp"
  trap - EXIT
elif [ "$upload_required" = "true" ]; then
  echo "manifest requires uploads but archive is missing" >&2
  exit 1
fi

echo "[$(date -Is)] governed rollback restore complete: $(basename "$manifest")"
