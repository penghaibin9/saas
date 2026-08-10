#!/usr/bin/env bash
# Detect silently stale or incomplete production backups without touching application data.
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/lib/school-lifecycle-backup}"
MAX_BACKUP_AGE_SECONDS="${MAX_BACKUP_AGE_SECONDS:-21600}"
BACKUP_REQUIRE_OFFSITE="${BACKUP_REQUIRE_OFFSITE:-true}"
BACKUP_RCLONE_REMOTE="${BACKUP_RCLONE_REMOTE:-}"
RCLONE_CONFIG="${RCLONE_CONFIG:-/etc/school-lifecycle/rclone.conf}"
BACKUP_ALERT_WEBHOOK_URL="${BACKUP_ALERT_WEBHOOK_URL:-}"

alert_failure() {
  local reason="$1"
  local message="school-lifecycle backup watchdog failed: host=$(hostname) reason=${reason}"
  echo "[$(date -Is)] ERROR: $message" >&2
  if [ -n "$BACKUP_ALERT_WEBHOOK_URL" ]; then
    python3 - "$message" <<'PY' | curl -fsS --max-time 10 -H 'Content-Type: application/json' -X POST --data-binary @- "$BACKUP_ALERT_WEBHOOK_URL" >/dev/null || true
import json, sys
print(json.dumps({"text": sys.argv[1]}, ensure_ascii=False))
PY
  fi
}

fail() {
  alert_failure "$1"
  exit 1
}

if ! [[ "$MAX_BACKUP_AGE_SECONDS" =~ ^[0-9]+$ ]] || [ "$MAX_BACKUP_AGE_SECONDS" -lt 1 ]; then
  fail "MAX_BACKUP_AGE_SECONDS_must_be_positive"
fi
if [ ! -d "$BACKUP_DIR" ]; then
  fail "backup_directory_missing"
fi

manifest="$(find "$BACKUP_DIR" -maxdepth 1 -type f -name 'manifest_*.json' -printf '%T@ %p\n' | sort -nr | head -n1 | cut -d' ' -f2-)"
if [ -z "$manifest" ] || [ ! -s "$manifest" ]; then
  fail "no_completed_backup_manifest"
fi
if [ ! -s "${manifest}.sha256" ]; then
  fail "manifest_checksum_missing"
fi
if ! (cd "$BACKUP_DIR" && sha256sum -c "$(basename "${manifest}.sha256")" >/dev/null); then
  fail "manifest_checksum_invalid"
fi

mapfile -t fields < <(python3 - "$manifest" <<'PY'
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

print(int(m["createdAtEpoch"]))
print(safe_name(m["database"]["file"]))
print(m["database"]["sha256"])
print(safe_name(m["uploads"].get("file")))
print(m["uploads"].get("sha256") or "")
print("true" if m["uploads"].get("required") else "false")
PY
) || fail "manifest_parse_failed"

created_epoch="${fields[0]}"
db_name="${fields[1]}"
db_hash="${fields[2]}"
upload_name="${fields[3]}"
upload_hash="${fields[4]}"
upload_required="${fields[5]}"

now_epoch="$(date +%s)"
age_seconds="$((now_epoch - created_epoch))"
if [ "$age_seconds" -lt 0 ]; then
  fail "backup_timestamp_is_in_future"
fi
if [ "$age_seconds" -gt "$MAX_BACKUP_AGE_SECONDS" ]; then
  fail "backup_stale_age_${age_seconds}s"
fi

verify_local_object() {
  local name="$1" expected_hash="$2"
  local file="$BACKUP_DIR/$name"
  [ -s "$file" ] || fail "local_object_missing_${name}"
  [ -s "${file}.sha256" ] || fail "local_checksum_missing_${name}"
  if ! (cd "$BACKUP_DIR" && sha256sum -c "${name}.sha256" >/dev/null); then
    fail "local_checksum_invalid_${name}"
  fi
  if [ "$(sha256sum "$file" | awk '{print $1}')" != "$expected_hash" ]; then
    fail "manifest_hash_mismatch_${name}"
  fi
}

verify_local_object "$db_name" "$db_hash"
if [ -n "$upload_name" ]; then
  verify_local_object "$upload_name" "$upload_hash"
elif [ "$upload_required" = "true" ]; then
  fail "required_upload_archive_missing"
fi

offsite_checked=false
if [ "$BACKUP_REQUIRE_OFFSITE" = "true" ]; then
  [ -n "$BACKUP_RCLONE_REMOTE" ] || fail "offsite_remote_not_configured"
  command -v rclone >/dev/null 2>&1 || fail "rclone_missing"
  RCLONE_ARGS=()
  if [[ "$BACKUP_RCLONE_REMOTE" == *:* ]]; then
    [ -r "$RCLONE_CONFIG" ] || fail "rclone_config_unreadable"
    RCLONE_ARGS=(--config "$RCLONE_CONFIG")
  fi

  manifest_base="$(basename "$manifest")"
  remote_manifest="${BACKUP_RCLONE_REMOTE%/}/${manifest_base}"
  remote_sidecar="${remote_manifest}.sha256"
  local_manifest_hash="$(sha256sum "$manifest" | awk '{print $1}')"
  remote_manifest_hash="$(rclone "${RCLONE_ARGS[@]}" cat "$remote_manifest" 2>/dev/null | sha256sum | awk '{print $1}')" || fail "remote_manifest_missing"
  [ "$remote_manifest_hash" = "$local_manifest_hash" ] || fail "remote_manifest_hash_mismatch"

  local_sidecar_hash="$(sha256sum "${manifest}.sha256" | awk '{print $1}')"
  remote_sidecar_hash="$(rclone "${RCLONE_ARGS[@]}" cat "$remote_sidecar" 2>/dev/null | sha256sum | awk '{print $1}')" || fail "remote_manifest_checksum_missing"
  [ "$remote_sidecar_hash" = "$local_sidecar_hash" ] || fail "remote_manifest_checksum_mismatch"
  offsite_checked=true
fi

echo "backup_watchdog=PASS manifest=$(basename "$manifest") age_seconds=$age_seconds offsite_checked=$offsite_checked"
