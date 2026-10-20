#!/usr/bin/env bash
# Verified backup wrapper: MySQL, uploads, root-only configuration snapshot and version marker.
set -euo pipefail
[[ $(id -u) -eq 0 ]] || { echo "Run with sudo." >&2; exit 1; }
APP_ROOT="${APP_ROOT:-/opt/school-lifecycle}"
ENV_FILE="${ENV_FILE:-/etc/school-lifecycle/backend.env}"
BACKUP_ENV_FILE="${BACKUP_ENV_FILE:-/etc/school-lifecycle/backup.env}"
current="$(readlink -f "$APP_ROOT/current")"
[[ -d "$current" ]] || { echo "No active school-lifecycle release." >&2; exit 1; }
runner="$current/scripts/deploy/run-with-envfile.py"
[[ -x "$current/deploy/backup/backup-runner.sh" && -f "$runner" && -r "$ENV_FILE" && -r "$BACKUP_ENV_FILE" ]] || { echo "Backup prerequisites are incomplete." >&2; exit 1; }
backup_dir="$(python3 "$runner" --get "$BACKUP_ENV_FILE" BACKUP_DIR)"; backup_dir="${backup_dir:-/var/lib/school-lifecycle-backup}"
python3 "$runner" "$BACKUP_ENV_FILE" -- python3 "$runner" "$ENV_FILE" -- env BACKUP_DIR="$backup_dir" REQUIRE_UPLOAD_BACKUP=true bash "$current/deploy/backup/backup-runner.sh"
id="$(date -u +%Y%m%d_%H%M%S)"; marker="$backup_dir/release_${id}.json"
install -d -m 700 "$backup_dir"
version="$(cat "$current/.release-commit" 2>/dev/null || basename "$current")"
umask 077
env_dir="$(dirname "$ENV_FILE")"
tar -C "$env_dir" -czf "$backup_dir/config_${id}.tar.gz" "$(basename "$ENV_FILE")"
sha256sum "$backup_dir/config_${id}.tar.gz" > "$backup_dir/config_${id}.tar.gz.sha256"
printf '{"createdAtUtc":"%s","version":"%s","configArchive":"%s"}\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$version" "config_${id}.tar.gz" > "$marker"
sha256sum "$marker" > "$marker.sha256"
echo "backup_success version=$version manifest=$(find "$backup_dir" -maxdepth 1 -name 'manifest_*.json' -printf '%T@ %p\n' | sort -nr | head -n1 | cut -d' ' -f2-)"
