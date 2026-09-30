#!/usr/bin/env bash
set -euo pipefail
APP_ROOT="${APP_ROOT:-/opt/school-lifecycle}"
ENV_FILE="${ENV_FILE:-/etc/school-lifecycle/backend.env}"
current="$(readlink -f "$APP_ROOT/current")"
[[ -d "$current" ]] || { echo "No active school-lifecycle release." >&2; exit 1; }
APP_ROOT="$APP_ROOT" ENV_FILE="$ENV_FILE" bash "$current/scripts/deploy/verify-systemd-release.sh"
echo "health_check_success version=$(cat "$current/.release-commit" 2>/dev/null || basename "$current")"
