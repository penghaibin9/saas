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

verify_object "$db_file" "$db_hash"
gzip -t "$db_file"

# mysqldump contains DROP/CREATE for every pre-release table. Extra tables created only by a failed
# candidate may remain, but every pre-existing table is restored to its previous schema+data, which
# is the compatibility requirement for restarting the previous application release.
echo "[$(date -Is)] restoring database from governed backup: $(basename "$db_file")"
gzip -cd "$db_file" | MYSQL_PWD="$DB_PASSWORD" mysql \
  -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" --binary-mode=1 "$DB_NAME"

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
