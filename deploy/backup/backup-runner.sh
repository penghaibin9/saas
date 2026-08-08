#!/usr/bin/env bash
# Production backup orchestration: verified local backup + mandatory verified offsite copy + failure alert.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="${BACKUP_DIR:-/var/lib/school-lifecycle-backup}"
DB_NAME="${DB_NAME:-saas_lifecycle}"
BACKUP_RCLONE_REMOTE="${BACKUP_RCLONE_REMOTE:-}"
RCLONE_CONFIG="${RCLONE_CONFIG:-/etc/school-lifecycle/rclone.conf}"
# Fail closed by default. Production systemd also pins this to true so a missing/incorrect env
# file can never silently downgrade the job to local-only success.
BACKUP_REQUIRE_OFFSITE="${BACKUP_REQUIRE_OFFSITE:-true}"
BACKUP_REQUIRE_IMMUTABLE_REMOTE="${BACKUP_REQUIRE_IMMUTABLE_REMOTE:-true}"
BACKUP_IMMUTABLE_REMOTE_CONFIRMED="${BACKUP_IMMUTABLE_REMOTE_CONFIRMED:-false}"
BACKUP_ALERT_WEBHOOK_URL="${BACKUP_ALERT_WEBHOOK_URL:-}"

mkdir -p -- "$BACKUP_DIR"
export BACKUP_DIR

alert_failure() {
  local status="$1"
  local message="school-lifecycle backup failed: db=${DB_NAME} host=$(hostname) status=${status}"
  echo "[$(date -Is)] ERROR: $message" >&2
  if [ -n "$BACKUP_ALERT_WEBHOOK_URL" ]; then
    curl -fsS --max-time 10 \
      -H 'Content-Type: application/json' \
      -X POST \
      --data "{\"text\":\"${message}\"}" \
      "$BACKUP_ALERT_WEBHOOK_URL" >/dev/null || true
  fi
}

on_error() {
  local status=$?
  trap - ERR
  alert_failure "$status"
  exit "$status"
}
trap on_error ERR

if [ "$BACKUP_REQUIRE_OFFSITE" != "true" ]; then
  echo "Production backup runner requires BACKUP_REQUIRE_OFFSITE=true" >&2
  exit 1
fi
if [ -z "$BACKUP_RCLONE_REMOTE" ]; then
  echo "BACKUP_RCLONE_REMOTE must be configured for production backups" >&2
  exit 1
fi
if [ "$BACKUP_REQUIRE_IMMUTABLE_REMOTE" = "true" ] && [ "$BACKUP_IMMUTABLE_REMOTE_CONFIRMED" != "true" ]; then
  echo "Immutable/versioned offsite storage must be confirmed before production backup can succeed" >&2
  exit 1
fi
command -v rclone >/dev/null 2>&1 || {
  echo "BACKUP_RCLONE_REMOTE is configured but rclone is not installed" >&2
  exit 1
}

RCLONE_ARGS=()
# Named rclone remotes need credentials/configuration. Pin the config outside $HOME because the
# systemd unit intentionally uses ProtectHome=true. Plain local paths are used only by CI drills.
if [[ "$BACKUP_RCLONE_REMOTE" == *:* ]]; then
  if [ ! -r "$RCLONE_CONFIG" ]; then
    echo "rclone config is not readable by the backup service: $RCLONE_CONFIG" >&2
    exit 1
  fi
  RCLONE_ARGS=(--config "$RCLONE_CONFIG")
fi

# Use bash explicitly because the historical backup script may not carry the executable bit
# in older repository clones. The orchestration contract must not depend on that file mode.
bash "$SCRIPT_DIR/backup-mysql.sh"

latest_db="$(find "$BACKUP_DIR" -maxdepth 1 -type f -name "db_${DB_NAME}_*.sql.gz" -printf '%T@ %p\n' \
  | sort -nr | head -n1 | cut -d' ' -f2-)"
test -n "$latest_db"
test -s "$latest_db"
test -f "${latest_db}.sha256"
(
  cd "$BACKUP_DIR"
  sha256sum -c "$(basename "${latest_db}.sha256")"
)

copy_offsite() {
  local file="$1"
  [ -f "$file" ] || return 0
  local remote_path="${BACKUP_RCLONE_REMOTE%/}/$(basename "$file")"
  rclone "${RCLONE_ARGS[@]}" copyto "$file" "$remote_path" --checksum

  # A transfer is successful only after an independent read-back proves both byte size and
  # SHA-256 content equality. This catches truncated/corrupt remote objects even on backends
  # where provider checksums differ from local SHA-256 semantics.
  local local_size remote_size local_hash remote_hash
  local_size="$(stat -c '%s' "$file")"
  remote_size="$(rclone "${RCLONE_ARGS[@]}" size "$remote_path" --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["bytes"])')"
  test "$remote_size" = "$local_size"
  local_hash="$(sha256sum "$file" | awk '{print $1}')"
  remote_hash="$(rclone "${RCLONE_ARGS[@]}" cat "$remote_path" | sha256sum | awk '{print $1}')"
  test "$remote_hash" = "$local_hash"
}

copy_offsite "$latest_db"
copy_offsite "${latest_db}.sha256"

latest_upload="$(find "$BACKUP_DIR" -maxdepth 1 -type f -name 'uploads_*.tar.gz' -printf '%T@ %p\n' \
  | sort -nr | head -n1 | cut -d' ' -f2- || true)"
if [ -n "$latest_upload" ]; then
  copy_offsite "$latest_upload"
  copy_offsite "${latest_upload}.sha256"
fi

echo "[$(date -Is)] mandatory offsite copy verified by read-back SHA-256: $BACKUP_RCLONE_REMOTE"
trap - ERR
echo "[$(date -Is)] backup runner complete: $latest_db"
