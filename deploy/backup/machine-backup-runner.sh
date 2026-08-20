#!/usr/bin/env bash
# Run the existing verified offsite backup, then persist MACHINE evidence locally.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKUP_DIR="${BACKUP_DIR:-/var/lib/school-lifecycle-backup}"
PYTHON_BIN="${PYTHON_BIN:-$REPO_ROOT/backend/.venv/bin/python}"

if [ ! -x "$PYTHON_BIN" ]; then
  echo "backend Python runtime is not executable: $PYTHON_BIN" >&2
  exit 1
fi

bash "$SCRIPT_DIR/backup-runner.sh"
manifest="$(find "$BACKUP_DIR" -maxdepth 1 -type f -name 'manifest_*.json' -printf '%T@ %p\n' | sort -nr | head -n1 | cut -d' ' -f2-)"
test -n "$manifest"
test -s "$manifest"

PYTHONPATH="$REPO_ROOT/backend${PYTHONPATH:+:$PYTHONPATH}" \
"$PYTHON_BIN" "$REPO_ROOT/backend/scripts/record_recovery_evidence.py" backup \
  --manifest "$manifest" \
  --source-commit "${RECOVERY_SOURCE_COMMIT:-${GITHUB_SHA:-unknown}}" \
  --runner-id "$(hostname)"
