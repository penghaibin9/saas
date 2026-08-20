#!/usr/bin/env bash
# Execute the existing isolated restore drill and persist its signed-by-hash MACHINE evidence.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
manifest="${1:?usage: machine-restore-drill.sh <manifest.json> <drill_db_name>}"
drill_db="${2:?usage: machine-restore-drill.sh <manifest.json> <drill_db_name>}"
evidence_dir="${RECOVERY_EVIDENCE_DIR:-${TMPDIR:-/tmp}/school-lifecycle-recovery-evidence}"
mkdir -p "$evidence_dir"
chmod 700 "$evidence_dir" 2>/dev/null || true
run_stamp="$(date -u +%Y%m%dT%H%M%SZ)-$$"
evidence_file="$evidence_dir/restore-${run_stamp}.env"

RESTORE_EVIDENCE_FILE="$evidence_file" \
RESTORE_SOURCE_COMMIT="${RECOVERY_SOURCE_COMMIT:-${GITHUB_SHA:-unknown}}" \
bash "$SCRIPT_DIR/restore-drill.sh" "$manifest" "$drill_db"

PYTHONPATH="$REPO_ROOT/backend${PYTHONPATH:+:$PYTHONPATH}" \
python3 "$REPO_ROOT/backend/scripts/record_recovery_evidence.py" restore-env \
  --evidence "$evidence_file"

echo "machine restore evidence recorded: $evidence_file"
