#!/usr/bin/env bash
# Execute the isolated restore drill and persist MACHINE evidence only after
# proving every active local FileObject from the restored database has bytes + SHA.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PYTHON_BIN="${RECOVERY_PYTHON_BIN:-$REPO_ROOT/backend/.venv/bin/python}"
manifest="${1:?usage: machine-restore-drill.sh <manifest.json> <drill_db_name>}"
drill_db="${2:?usage: machine-restore-drill.sh <manifest.json> <drill_db_name>}"
evidence_dir="${RECOVERY_EVIDENCE_DIR:-${TMPDIR:-/tmp}/school-lifecycle-recovery-evidence}"
mkdir -p "$evidence_dir"
chmod 700 "$evidence_dir" 2>/dev/null || true
run_stamp="$(date -u +%Y%m%dT%H%M%SZ)-$$"
evidence_file="$evidence_dir/restore-${run_stamp}.env"

if [ ! -x "$PYTHON_BIN" ]; then
  echo "backend Python runtime is not executable: $PYTHON_BIN" >&2
  exit 1
fi

run_restore() {
  RESTORE_EVIDENCE_FILE="$evidence_file" \
  RESTORE_SOURCE_COMMIT="${RECOVERY_SOURCE_COMMIT:-${GITHUB_SHA:-unknown}}" \
  "$@" bash "$SCRIPT_DIR/restore-drill.sh" "$manifest" "$drill_db"
}

# First pass restores the exact backup and emits schema/RPO/RTO evidence.  The
# legacy drill's FileObject verification is threshold-driven, so with default
# thresholds it can legitimately report 0/0 without having inspected file rows.
run_restore

# Independently ask the restored database how many active local FileObjects it
# actually contains.  A missing table/query is a hard failure rather than a
# vacuous "zero files" success.
DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-3306}"
DB_USER="${DB_USER:-root}"
: "${DB_PASSWORD:?DB_PASSWORD must be set}"
case "$DB_HOST" in
  127.0.0.1|localhost|::1) ;;
  *) echo "machine restore verification refuses non-local DB_HOST=$DB_HOST" >&2; exit 2 ;;
esac
MYSQL=(mysql -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER")
export MYSQL_PWD="$DB_PASSWORD"
local_file_object_count="$("${MYSQL[@]}" -Nse "
  SELECT COUNT(*)
    FROM \`${drill_db}\`.t_file_object
   WHERE is_deleted=0
     AND LOWER(COALESCE(NULLIF(storage_backend, ''), 'local'))='local'
")"
unset MYSQL_PWD
if [[ ! "$local_file_object_count" =~ ^[0-9]+$ ]]; then
  echo "invalid restored local FileObject count: $local_file_object_count" >&2
  exit 1
fi

# If files exist, rerun the canonical drill with thresholds equal to the exact
# restored row count.  That reuses its path-safety, byte-size and SHA-256 checks
# and requires every local FileObject to carry and match a hash before GREEN.
if [ "$local_file_object_count" -gt 0 ]; then
  run_restore env \
    MIN_RESTORED_LOCAL_FILE_OBJECTS="$local_file_object_count" \
    MIN_RESTORED_HASHED_FILE_OBJECTS="$local_file_object_count"
fi

test -s "$evidence_file"
evidence_local_count="$(awk -F= '$1=="local_file_object_count" {print $2}' "$evidence_file" | tail -n1)"
evidence_hashed_count="$(awk -F= '$1=="local_file_object_hashed_count" {print $2}' "$evidence_file" | tail -n1)"
test "$evidence_local_count" = "$local_file_object_count"
if [ "$local_file_object_count" -gt 0 ]; then
  test "$evidence_hashed_count" = "$local_file_object_count"
else
  test "${evidence_hashed_count:-0}" = "0"
fi

# Make the proof explicit so the evidence converter can distinguish "verified
# zero FileObjects" from the historical default 0/0 values that skipped checks.
tmp_evidence="${evidence_file}.tmp.$$"
grep -v '^file_object_verification_executed=' "$evidence_file" > "$tmp_evidence"
printf 'file_object_verification_executed=true\n' >> "$tmp_evidence"
mv "$tmp_evidence" "$evidence_file"
(
  cd "$(dirname "$evidence_file")"
  sha256sum "$(basename "$evidence_file")" > "$(basename "$evidence_file").sha256"
)

PYTHONPATH="$REPO_ROOT/backend${PYTHONPATH:+:$PYTHONPATH}" \
"$PYTHON_BIN" "$REPO_ROOT/backend/scripts/record_recovery_evidence.py" restore-env \
  --evidence "$evidence_file"

echo "machine restore evidence recorded: $evidence_file"
