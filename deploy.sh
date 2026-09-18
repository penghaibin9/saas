#!/usr/bin/env bash
# One-command production release wrapper.  It deliberately delegates the irreversible
# migration/restore guard to scripts/deploy/install-systemd-release.sh.
set -euo pipefail

usage() { echo "Usage: sudo ./deploy.sh <release-directory-or-tar.gz>" >&2; exit 2; }
[[ $# -eq 1 ]] || usage
[[ $(id -u) -eq 0 ]] || { echo "Run with sudo; production files and systemd units require root." >&2; exit 1; }

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE="$1"
APP_ROOT="${APP_ROOT:-/opt/school-lifecycle}"
ENV_FILE="${ENV_FILE:-/etc/school-lifecycle/backend.env}"
BACKUP_ENV_FILE="${BACKUP_ENV_FILE:-/etc/school-lifecycle/backup.env}"
LOCK_FILE="${DEPLOY_LOCK_FILE:-/run/lock/school-lifecycle-release.lock}"
stage=""

cleanup() { [[ -z "$stage" ]] || rm -rf -- "$stage"; }
trap cleanup EXIT

release_root="$PACKAGE"
if [[ -f "$PACKAGE" ]]; then
  stage="$(mktemp -d /var/tmp/school-lifecycle-release.XXXXXX)"
  python3 - "$PACKAGE" <<'PY'
import sys, tarfile
from pathlib import PurePosixPath
with tarfile.open(sys.argv[1], "r:*") as archive:
    for item in archive.getmembers():
        path = PurePosixPath(item.name)
        if path.is_absolute() or ".." in path.parts or item.issym() or item.islnk() or item.isdev():
            raise SystemExit(f"unsafe release archive member: {item.name}")
PY
  tar -xf "$PACKAGE" -C "$stage" --no-same-owner --no-same-permissions
  mapfile -t roots < <(find "$stage" -mindepth 1 -maxdepth 1 -type d -print)
  [[ ${#roots[@]} -eq 1 ]] || { echo "Release archive must contain exactly one top-level directory." >&2; exit 1; }
  release_root="${roots[0]}"
fi

[[ -d "$release_root/backend" && -d "$release_root/frontend" && -f "$release_root/scripts/deploy/install-systemd-release.sh" ]] || {
  echo "Release package is missing the formal backend/frontend/deploy layout." >&2; exit 1;
}
[[ -r "$ENV_FILE" && -r "$BACKUP_ENV_FILE" ]] || { echo "Production env/backup env is missing or unreadable." >&2; exit 1; }

commit=""
snapshot_sha256=""
if [[ -f "$release_root/.release-commit" ]]; then commit="$(tr -d '[:space:]' < "$release_root/.release-commit")"; fi
if [[ -f "$release_root/.release-source-sha256" ]]; then snapshot_sha256="$(tr -d '[:space:]' < "$release_root/.release-source-sha256")"; fi
if [[ -z "$commit" ]] && git -C "$release_root" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  [[ -z "$(git -C "$release_root" status --porcelain --untracked-files=all)" ]] || { echo "Refusing dirty git release source." >&2; exit 1; }
  commit="$(git -C "$release_root" rev-parse HEAD)"
fi
[[ "$commit" =~ ^[0-9a-f]{40}$ ]] || { echo "Release must carry .release-commit or be a clean git checkout." >&2; exit 1; }
if ! git -C "$release_root" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  [[ "$snapshot_sha256" =~ ^[0-9a-f]{64}$ ]] || {
    echo "Offline release must carry a checked .release-source-sha256 marker." >&2; exit 1;
  }
fi

old="$(readlink -f "$APP_ROOT/current" 2>/dev/null || true)"
echo "release_start=$(date -u +%Y-%m-%dT%H:%M:%SZ) previous=${old:-none} commit=$commit"

# The guarded installer performs: verified MySQL+uploads backup, migration, atomic
# current switch, service restart, nginx/health/readiness and production acceptance.
SOURCE_ROOT="$release_root" RELEASE_COMMIT="$commit" RELEASE_SNAPSHOT_SHA256="$snapshot_sha256" APP_ROOT="$APP_ROOT" ENV_FILE="$ENV_FILE" BACKUP_ENV_FILE="$BACKUP_ENV_FILE" \
  bash "$release_root/scripts/deploy/install-systemd-release.sh" --apply

new="$(readlink -f "$APP_ROOT/current")"
echo "release_success=$(date -u +%Y-%m-%dT%H:%M:%SZ) version=$(basename "$new") commit=$(cat "$new/.release-commit") snapshot=${snapshot_sha256:-git-archive}"
