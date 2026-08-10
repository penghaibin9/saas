#!/usr/bin/env bash
# Prepare and atomically switch a release on a Linux host. Runs only with --apply.
set -euo pipefail

if [ "${1:-}" = "--check" ]; then
  SOURCE_ROOT="${SOURCE_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
  ENV_FILE="${ENV_FILE:-/etc/school-lifecycle/backend.env}"
  ENV_FILE="$ENV_FILE" SOURCE_ROOT="$SOURCE_ROOT" bash "$SOURCE_ROOT/scripts/deploy/preflight-linux.sh"
  exit $?
fi

if [ "${1:-}" != "--apply" ]; then
  echo "Dry guard: no changes made. Run with --apply after preflight and backup approval."
  exit 0
fi
[ "$(id -u)" -eq 0 ] || { echo "Run as root." >&2; exit 1; }

SOURCE_ROOT="${SOURCE_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
APP_ROOT="${APP_ROOT:-/opt/school-lifecycle}"
ENV_FILE="${ENV_FILE:-/etc/school-lifecycle/backend.env}"
SERVICE_USER="${SERVICE_USER:-schoolapp}"
RELEASE_ID="${RELEASE_ID:-$(date +%Y%m%d_%H%M%S)}"
RELEASE_DIR="$APP_ROOT/releases/$RELEASE_ID"
BACKUP_DIR="$APP_ROOT/backups"

ENV_FILE="$ENV_FILE" SOURCE_ROOT="$SOURCE_ROOT" bash "$SOURCE_ROOT/scripts/deploy/preflight-linux.sh"
id "$SERVICE_USER" >/dev/null 2>&1 || useradd --system --home "$APP_ROOT" --shell /usr/sbin/nologin "$SERVICE_USER"
install -d -o "$SERVICE_USER" -g "$SERVICE_USER" "$APP_ROOT/releases" "$APP_ROOT/shared/uploads" \
  "$APP_ROOT/shared/exports" "$BACKUP_DIR" /var/www/school-lifecycle
install -d -m 700 /etc/school-lifecycle

# Load root-owned deployment secrets without printing them, then take a verified DB backup.
set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a
backup_file="$BACKUP_DIR/pre_release_${RELEASE_ID}.sql.gz"
MYSQL_PWD="$DB_PASSWORD" mysqldump -h"${DB_HOST:-127.0.0.1}" -P"${DB_PORT:-3306}" \
  -u"$DB_USER" --single-transaction --quick --routines --events --triggers --hex-blob \
  --default-character-set=utf8mb4 "$DB_NAME" | gzip -9 > "$backup_file.partial"
gzip -t "$backup_file.partial"
mv "$backup_file.partial" "$backup_file"
sha256sum "$backup_file" > "$backup_file.sha256"

install -d -o "$SERVICE_USER" -g "$SERVICE_USER" "$RELEASE_DIR"
# tmp/ 不排除：国标同步脚本仍读取仓库内 tmp/moe-* 源文件。
rsync -a --delete --exclude '.git' --exclude '.venv' --exclude 'node_modules' --exclude '.env*' \
  --exclude 'dist' "$SOURCE_ROOT/" "$RELEASE_DIR/"
python3 -m venv "$RELEASE_DIR/backend/.venv"
"$RELEASE_DIR/backend/.venv/bin/pip" install --disable-pip-version-check -r "$RELEASE_DIR/backend/requirements.txt"

# 三个客户端必须属于同一个 release；禁止只更新管理端/小程序而漏掉学生 PC。
if command -v npm >/dev/null 2>&1; then
  (cd "$RELEASE_DIR/frontend" && NODE_OPTIONS=--max-old-space-size=1536 npm ci && npm run build)
  (cd "$RELEASE_DIR/miniapp" && NODE_OPTIONS=--max-old-space-size=1536 npm ci && npm run build:h5)
  (cd "$RELEASE_DIR/student-portal" && NODE_OPTIONS=--max-old-space-size=1536 npm ci \
    && VITE_BASE=/portal/ VITE_API_BASE_URL= npm run build)
else
  [ -f "$SOURCE_ROOT/frontend/dist/index.html" ] \
    && [ -f "$SOURCE_ROOT/miniapp/dist/build/h5/index.html" ] \
    && [ -f "$SOURCE_ROOT/student-portal/dist/index.html" ] \
    || { echo "Node missing and one or more prebuilt dist outputs are missing" >&2; exit 1; }
  rsync -a "$SOURCE_ROOT/frontend/dist/" "$RELEASE_DIR/frontend/dist/"
  rsync -a "$SOURCE_ROOT/miniapp/dist/build/h5/" "$RELEASE_DIR/miniapp/dist/build/h5/"
  rsync -a "$SOURCE_ROOT/student-portal/dist/" "$RELEASE_DIR/student-portal/dist/"
fi

(cd "$RELEASE_DIR/backend" && "$RELEASE_DIR/backend/.venv/bin/python" -m alembic upgrade head)
# 动态校验仓库唯一 head 与数据库 current；禁止任何部署脚本写死具体 revision。
(cd "$RELEASE_DIR/backend" && "$RELEASE_DIR/backend/.venv/bin/python" scripts/check_alembic_current.py)

previous="$(readlink -f "$APP_ROOT/current" 2>/dev/null || true)"
if [ -e "$APP_ROOT/current" ] && [ ! -L "$APP_ROOT/current" ]; then
  legacy_current="$APP_ROOT/releases/legacy_current_${RELEASE_ID}"
  mv -- "$APP_ROOT/current" "$legacy_current"
  previous="$legacy_current"
fi
ln -sfnT "$RELEASE_DIR" "$APP_ROOT/current.next"
mv -Tf "$APP_ROOT/current.next" "$APP_ROOT/current"

for static_path in \
  /var/www/school-lifecycle/pc \
  /var/www/school-lifecycle/miniapp \
  /var/www/school-lifecycle/portal; do
  if [ -e "$static_path" ] && [ ! -L "$static_path" ]; then
    mv -- "$static_path" "${static_path}.pre_systemd_${RELEASE_ID}"
  fi
done
ln -sfnT "$APP_ROOT/current/frontend/dist" /var/www/school-lifecycle/pc
ln -sfnT "$APP_ROOT/current/miniapp/dist/build/h5" /var/www/school-lifecycle/miniapp
ln -sfnT "$APP_ROOT/current/student-portal/dist" /var/www/school-lifecycle/portal
chown -R "$SERVICE_USER:$SERVICE_USER" "$RELEASE_DIR" "$APP_ROOT/shared"

install -m 644 "$SOURCE_ROOT/deploy/systemd/school-lifecycle-backend.service" /etc/systemd/system/
install -m 644 "$SOURCE_ROOT/deploy/systemd/school-lifecycle-scheduler.service" /etc/systemd/system/
install -m 644 "$SOURCE_ROOT/deploy/systemd/school-lifecycle-file-scan.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable school-lifecycle-backend school-lifecycle-scheduler school-lifecycle-file-scan
systemctl restart school-lifecycle-backend school-lifecycle-scheduler school-lifecycle-file-scan

if ! APP_ROOT="$APP_ROOT" ENV_FILE="$ENV_FILE" bash "$SOURCE_ROOT/scripts/deploy/verify-systemd-release.sh"; then
  if [ -n "$previous" ] && [ -d "$previous" ]; then
    ln -sfnT "$previous" "$APP_ROOT/current.rollback"
    mv -Tf "$APP_ROOT/current.rollback" "$APP_ROOT/current"
    systemctl restart school-lifecycle-backend school-lifecycle-scheduler school-lifecycle-file-scan
    echo "Application symlink rolled back to $previous; database migration was intentionally not downgraded." >&2
  fi
  exit 1
fi

echo "Release $RELEASE_ID installed. Backup: $backup_file"
