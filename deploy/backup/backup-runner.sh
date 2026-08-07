#!/usr/bin/env bash
# Production backup orchestration: local verified backup + optional/required offsite copy + failure alert.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP_DIR="${BACKUP_DIR:-/var/lib/school-lifecycle-backup}"
DB_NAME="${DB_NAME:-saas_lifecycle}"
BACKUP_RCLONE_REMOTE="${BACKUP_RCLONE_REMOTE:-}"
BACKUP_REQUIRE_OFFSITE="${BACKUP_REQUIRE_OFFSITE:-false}"
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
  rclone copyto "$file" "${BACKUP_RCLONE_REMOTE%/}/$(basename "$file")" --checksum
}

if [ -n "$BACKUP_RCLONE_REMOTE" ]; then
  command -v rclone >/dev/null 2>&1 || {
    echo "BACKUP_RCLONE_REMOTE is configured but rclone is not installed" >&2
    exit 1
  }
  copy_offsite "$latest_db"
  copy_offsite "${latest_db}.sha256"

  latest_upload="$(find "$BACKUP_DIR" -maxdepth 1 -type f -name 'uploads_*.tar.gz' -printf '%T@ %p\n' \
    | sort -nr | head -n1 | cut -d' ' -f2- || true)"
  if [ -n "$latest_upload" ]; then
    copy_offsite "$latest_upload"
    copy_offsite "${latest_upload}.sha256"
  fi
  echo "[$(date -Is)] offsite copy complete: $BACKUP_RCLONE_REMOTE"
elif [ "$BACKUP_REQUIRE_OFFSITE" = "true" ]; then
  echo "BACKUP_REQUIRE_OFFSITE=true but BACKUP_RCLONE_REMOTE is empty" >&2
  exit 1
else
  echo "[$(date -Is)] offsite copy not configured; local verified backup retained"
fi

trap - ERR
echo "[$(date -Is)] backup runner complete: $latest_db"
