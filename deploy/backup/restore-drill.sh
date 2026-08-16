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
MIN_RESTORED_LOCAL_FILE_OBJECTS="${MIN_RESTORED_LOCAL_FILE_OBJECTS:-0}"
MIN_RESTORED_HASHED_FILE_OBJECTS="${MIN_RESTORED_HASHED_FILE_OBJECTS:-0}"
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
for numeric_name in MIN_RESTORED_LOCAL_FILE_OBJECTS MIN_RESTORED_HASHED_FILE_OBJECTS; do
  numeric_value="${!numeric_name}"
  if [[ ! "$numeric_value" =~ ^[0-9]+$ ]]; then
    echo "$numeric_name must be a non-negative integer" >&2
    exit 2
  fi
done
if [ "$MIN_RESTORED_HASHED_FILE_OBJECTS" -gt "$MIN_RESTORED_LOCAL_FILE_OBJECTS" ]; then
  echo "MIN_RESTORED_HASHED_FILE_OBJECTS cannot exceed MIN_RESTORED_LOCAL_FILE_OBJECTS" >&2
  exit 2
fi

test -s "$manifest_file"
backup_dir="$(cd "$(dirname "$manifest_file")" && pwd)"
if [ ! -f "${manifest_file}.sha256" ]; then
  echo "restore drill requires manifest checksum sidecar: ${manifest_file}.sha256" >&2
  exit 1
fi
(
  cd "$backup_dir"
  sha256sum -c "$(basename "${manifest_file}.sha256")"
)
manifest_sha256="$(sha256sum "$manifest_file" | awk '{print $1}')"

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

print(m.get("backupSetId") or "")
print(int(m["createdAtEpoch"]))
print(safe_name(m["database"]["file"]))
print(m["database"]["sha256"])
print(safe_name(m["uploads"].get("file")))
print(m["uploads"].get("sha256") or "")
print("true" if m["uploads"].get("required") else "false")
PY
)

backup_set_id="${fields[0]}"
created_epoch="${fields[1]}"
db_name="${fields[2]}"
db_hash="${fields[3]}"
upload_name="${fields[4]}"
upload_hash="${fields[5]}"
upload_required="${fields[6]}"
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
upload_archive_root=""
upload_restored_root=""
if [ -n "$upload_name" ]; then
  verify_object "$upload_name" "$upload_hash"
  upload_archive_root="$(python3 - "$backup_dir/$upload_name" <<'PY'
import sys
import tarfile
from pathlib import PurePosixPath

archive_path = sys.argv[1]
roots = set()
with tarfile.open(archive_path, "r:gz") as archive:
    members = archive.getmembers()
    if not members:
        raise SystemExit("upload archive is empty")
    for member in members:
        path = PurePosixPath(member.name)
        parts = tuple(part for part in path.parts if part not in {"", "."})
        if not parts or path.is_absolute() or ".." in parts:
            raise SystemExit(f"unsafe upload archive member path: {member.name!r}")
        if not (member.isfile() or member.isdir()):
            raise SystemExit(f"unsafe upload archive member type: {member.name!r}")
        roots.add(parts[0])
if len(roots) != 1:
    raise SystemExit(f"upload archive must contain exactly one top-level root, got {sorted(roots)!r}")
print(next(iter(roots)))
PY
)"
  upload_restore_dir="$(mktemp -d "${TMPDIR:-/tmp}/school-lifecycle-upload-restore.XXXXXX")"
  trap 'rm -rf -- "$upload_restore_dir"' EXIT
  tar --no-same-owner --no-same-permissions -xzf "$backup_dir/$upload_name" -C "$upload_restore_dir"
  upload_restored_root="$upload_restore_dir/$upload_archive_root"
  if [ ! -d "$upload_restored_root" ]; then
    echo "upload archive root was not restored: $upload_archive_root" >&2
    exit 1
  fi
  upload_entry_count="$(find "$upload_restored_root" -mindepth 1 -print | wc -l | tr -d ' ')"
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

local_file_object_count=0
local_file_object_hashed_count=0
if [ "$MIN_RESTORED_LOCAL_FILE_OBJECTS" -gt 0 ] || [ "$MIN_RESTORED_HASHED_FILE_OBJECTS" -gt 0 ]; then
  if [ -z "$upload_restored_root" ]; then
    echo "FileObject verification requires a restored upload archive" >&2
    exit 1
  fi
  file_table_exists="$("${MYSQL[@]}" -Nse "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='${drill_db}' AND table_name='t_file_object'")"
  if [ "$file_table_exists" != "1" ]; then
    echo "FileObject verification requires restored t_file_object" >&2
    exit 1
  fi
  file_object_rows="$upload_restore_dir/fileobjects.tsv"
  "${MYSQL[@]}" --batch --raw --skip-column-names -e "
    SELECT id, file_key, COALESCE(size_bytes, ''), COALESCE(sha256, '')
      FROM \`${drill_db}\`.t_file_object
     WHERE is_deleted=0
       AND LOWER(COALESCE(NULLIF(storage_backend, ''), 'local'))='local'
     ORDER BY id
  " > "$file_object_rows"
  read -r local_file_object_count local_file_object_hashed_count < <(
    python3 - "$upload_restored_root" "$file_object_rows" "$MIN_RESTORED_LOCAL_FILE_OBJECTS" "$MIN_RESTORED_HASHED_FILE_OBJECTS" <<'PY'
import hashlib
import re
import sys
from pathlib import Path, PurePosixPath

root = Path(sys.argv[1]).resolve()
rows_file = Path(sys.argv[2])
min_local = int(sys.argv[3])
min_hashed = int(sys.argv[4])
count = 0
hashed = 0
for line_no, raw in enumerate(rows_file.read_text(encoding="utf-8").splitlines(), start=1):
    parts = raw.split("\t")
    if len(parts) != 4:
        raise SystemExit(f"invalid FileObject row at line {line_no}")
    file_id, key, expected_size, expected_sha = parts
    if not key or "\\" in key:
        raise SystemExit(f"unsafe FileObject file_key id={file_id}: {key!r}")
    posix = PurePosixPath(key)
    if posix.is_absolute() or ".." in posix.parts or "." in posix.parts:
        raise SystemExit(f"unsafe FileObject file_key id={file_id}: {key!r}")
    target = root.joinpath(*posix.parts).resolve()
    if target == root or root not in target.parents:
        raise SystemExit(f"FileObject escaped restored upload root id={file_id}: {key!r}")
    if not target.is_file():
        raise SystemExit(f"restored FileObject bytes missing id={file_id}: {key!r}")
    actual_size = target.stat().st_size
    if expected_size:
        try:
            size_value = int(expected_size)
        except ValueError as exc:
            raise SystemExit(f"invalid FileObject size id={file_id}: {expected_size!r}") from exc
        if actual_size != size_value:
            raise SystemExit(
                f"restored FileObject size mismatch id={file_id}: expected={size_value} actual={actual_size}"
            )
    if expected_sha:
        expected_sha = expected_sha.lower()
        if not re.fullmatch(r"[0-9a-f]{64}", expected_sha):
            raise SystemExit(f"invalid FileObject sha256 id={file_id}: {expected_sha!r}")
        digest = hashlib.sha256()
        with target.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        actual_sha = digest.hexdigest()
        if actual_sha != expected_sha:
            raise SystemExit(
                f"restored FileObject sha256 mismatch id={file_id}: expected={expected_sha} actual={actual_sha}"
            )
        hashed += 1
    count += 1
if count < min_local:
    raise SystemExit(f"restored local FileObject count below contract: expected>={min_local} actual={count}")
if hashed < min_hashed:
    raise SystemExit(f"restored hashed FileObject count below contract: expected>={min_hashed} actual={hashed}")
print(count, hashed)
PY
  )
fi

if [ -n "$RESTORE_EVIDENCE_FILE" ]; then
  mkdir -p "$(dirname "$RESTORE_EVIDENCE_FILE")"
  cat > "$RESTORE_EVIDENCE_FILE" <<EVIDENCE
backup_set_id=$backup_set_id
manifest=$(basename "$manifest_file")
manifest_sha256=$manifest_sha256
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
local_file_object_count=$local_file_object_count
local_file_object_hashed_count=$local_file_object_hashed_count
recovery_host=$(hostname)
recovery_operator=${RECOVERY_OPERATOR:-${USER:-unknown}}
source_commit=${GITHUB_SHA:-unknown}
workflow_run_id=${GITHUB_RUN_ID:-manual}
completed_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EVIDENCE
  (
    cd "$(dirname "$RESTORE_EVIDENCE_FILE")"
    sha256sum "$(basename "$RESTORE_EVIDENCE_FILE")" > "$(basename "$RESTORE_EVIDENCE_FILE").sha256"
  )
fi

unset MYSQL_PWD
echo "restore drill complete: db=${drill_db} tables=${table_count} indexes=${index_count} foreign_keys=${foreign_key_count} tenants=${tenant_rows} uploads=${upload_entry_count} local_file_objects=${local_file_object_count} hashed_file_objects=${local_file_object_hashed_count} restore_seconds=${restore_seconds} backup_age_seconds=${backup_age_seconds}"
