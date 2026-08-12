#!/usr/bin/env bash
# Target-server runtime acceptance. Writes evidence only after real host checks succeed.
# This script must run on the actual Linux host; GitHub-hosted CI is intentionally not a substitute.
set -euo pipefail

[ "$(id -u)" -eq 0 ] || { echo "Run as root on the target server." >&2; exit 1; }

APP_ROOT="${APP_ROOT:-/opt/school-lifecycle}"
ENV_FILE="${ENV_FILE:-/etc/school-lifecycle/backend.env}"
CURRENT="$(readlink -f "$APP_ROOT/current" 2>/dev/null || true)"
EXPECTED_RELEASE_COMMIT="${EXPECTED_RELEASE_COMMIT:-}"
BACKUP_FILE="${BACKUP_FILE:-}"
EVIDENCE_DIR="${EVIDENCE_DIR:-$APP_ROOT/release-evidence}"

[ -n "$CURRENT" ] && [ -d "$CURRENT" ] || { echo "current release is missing" >&2; exit 1; }
[ -f "$CURRENT/.release-commit" ] || { echo "current release has no immutable commit marker" >&2; exit 1; }
ACTUAL_COMMIT="$(tr -d '[:space:]' < "$CURRENT/.release-commit")"
[[ "$ACTUAL_COMMIT" =~ ^[0-9a-f]{40}$ ]] || { echo "release commit marker is invalid" >&2; exit 1; }
[ -n "$EXPECTED_RELEASE_COMMIT" ] || { echo "EXPECTED_RELEASE_COMMIT is required" >&2; exit 1; }
[ "$ACTUAL_COMMIT" = "$EXPECTED_RELEASE_COMMIT" ] || {
  echo "candidate commit does not match the deployed release" >&2
  exit 1
}

# Use the deployed release's own scripts, never a mutable checkout beside it.
SOURCE_ROOT="$CURRENT" ENV_FILE="$ENV_FILE" bash "$CURRENT/scripts/deploy/preflight-linux.sh"
APP_ROOT="$APP_ROOT" ENV_FILE="$ENV_FILE" bash "$CURRENT/scripts/deploy/verify-systemd-release.sh"

# The exact pre-migration backup used by this release must still be present and checksum-valid.
if [ -z "$BACKUP_FILE" ]; then
  BACKUP_FILE="$(ls -1t "$APP_ROOT"/backups/pre_release_*.sql.gz 2>/dev/null | head -n 1 || true)"
fi
[ -n "$BACKUP_FILE" ] && [ -f "$BACKUP_FILE" ] || { echo "release backup is missing" >&2; exit 1; }
[ -f "$BACKUP_FILE.sha256" ] || { echo "release backup checksum file is missing" >&2; exit 1; }
(
  cd "$(dirname "$BACKUP_FILE")"
  sha256sum -c "$(basename "$BACKUP_FILE.sha256")" >/dev/null
)
gzip -t "$BACKUP_FILE"

install -d -m 700 "$EVIDENCE_DIR"
EVIDENCE_FILE="$EVIDENCE_DIR/${ACTUAL_COMMIT}.server-runtime.json"
HOST_FINGERPRINT="$(hostname | sha256sum | awk '{print $1}')"
BACKUP_SHA="$(sha256sum "$BACKUP_FILE" | awk '{print $1}')"
RELEASE_ID="$(basename "$CURRENT")"

python3 - "$EVIDENCE_FILE" "$ACTUAL_COMMIT" "$RELEASE_ID" "$HOST_FINGERPRINT" "$BACKUP_SHA" <<'PY'
from __future__ import annotations
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

out, commit, release_id, host_fp, backup_sha = sys.argv[1:]
payload = {
    "schemaVersion": 1,
    "evidenceType": "TARGET_SERVER_RUNTIME_ACCEPTANCE",
    "status": "PASS",
    "commit": commit,
    "releaseId": release_id,
    "hostFingerprintSha256": host_fp,
    "recordedAt": datetime.now(timezone.utc).isoformat(),
    "checks": {
        "deployedCommitMatchesCandidate": True,
        "linuxProductionPreflight": "PASS",
        "postReleaseRuntimeVerification": "PASS",
        "backupIntegrity": "PASS",
        "backupSha256": backup_sha,
    },
    "limitations": {
        "restoreDrill": "SEPARATE_EVIDENCE_REQUIRED",
        "realRoleBusinessSmoke": "SEPARATE_EVIDENCE_REQUIRED",
        "crossTenantNegativeSmoke": "SEPARATE_EVIDENCE_REQUIRED",
    },
}
path = Path(out)
tmp = path.with_suffix(path.suffix + ".tmp")
tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
os.chmod(tmp, 0o600)
os.replace(tmp, path)
PY

printf 'Target-server runtime acceptance PASS. Evidence: %s\n' "$EVIDENCE_FILE"
printf 'Restore drill and real-role/cross-tenant smoke remain separate mandatory evidence; this file never claims they passed.\n'
