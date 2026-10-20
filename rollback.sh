#!/usr/bin/env bash
# Code-only rollback. Database downgrade is intentionally forbidden.
set -euo pipefail
[[ $(id -u) -eq 0 ]] || { echo "Run with sudo." >&2; exit 1; }
APP_ROOT="${APP_ROOT:-/opt/school-lifecycle}"
ENV_FILE="${ENV_FILE:-/etc/school-lifecycle/backend.env}"
LOCK_FILE="${DEPLOY_LOCK_FILE:-/run/lock/school-lifecycle-release.lock}"
exec 9>"$LOCK_FILE"; flock -n 9 || { echo "A release/rollback is already in progress." >&2; exit 1; }
current="$(readlink -f "$APP_ROOT/current")"; [[ -d "$current" ]] || { echo "No active release to roll back." >&2; exit 1; }
candidate="$(find "$APP_ROOT/releases" -mindepth 1 -maxdepth 1 -type d ! -samefile "$current" -exec test -f '{}/.release-accepted.json' \; -printf '%T@ %p\n' | sort -nr | head -n1 | cut -d' ' -f2-)"
[[ -n "$candidate" && -f "$candidate/.release-commit" && -f "$candidate/.release-accepted.json" ]] || { echo "No previous accepted release is available." >&2; exit 1; }
echo "rollback_start from=$(basename "$current") to=$(basename "$candidate") database_action=NONE"
ln -sfnT "$candidate" "$APP_ROOT/current.next"; mv -Tf "$APP_ROOT/current.next" "$APP_ROOT/current"
for unit in school-lifecycle-backend.service school-lifecycle-scheduler.service school-lifecycle-file-scan.service; do
  install -m 644 "$candidate/deploy/systemd/$unit" "/etc/systemd/system/$unit"
done
systemctl daemon-reload
systemctl restart school-lifecycle-backend school-lifecycle-scheduler school-lifecycle-file-scan
if ! APP_ROOT="$APP_ROOT" ENV_FILE="$ENV_FILE" bash "$candidate/scripts/deploy/verify-systemd-release.sh"; then
  ln -sfnT "$current" "$APP_ROOT/current.failed-rollback"; mv -Tf "$APP_ROOT/current.failed-rollback" "$APP_ROOT/current"
  systemctl daemon-reload; systemctl restart school-lifecycle-backend school-lifecycle-scheduler school-lifecycle-file-scan
  echo "Rollback health check failed; code pointer restored to the pre-rollback version. Database was not changed." >&2
  exit 1
fi
echo "rollback_success version=$(cat "$candidate/.release-commit") database_action=NONE"
