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
ENV_RUNNER="$SOURCE_ROOT/scripts/deploy/run-with-envfile.py"
LOCK_FILE="${DEPLOY_LOCK_FILE:-/run/lock/school-lifecycle-release.lock}"

# 生产证据必须能证明“验收的是哪个 commit”。源码目录有 .git 时自动取 HEAD；
# 离线发布包没有 .git 时必须由发布流水线显式传 RELEASE_COMMIT，禁止用时间戳冒充版本身份。
SOURCE_COMMIT="${RELEASE_COMMIT:-}"
if [ -z "$SOURCE_COMMIT" ] && command -v git >/dev/null 2>&1; then
  SOURCE_COMMIT="$(git -C "$SOURCE_ROOT" rev-parse HEAD 2>/dev/null || true)"
fi
[[ "$SOURCE_COMMIT" =~ ^[0-9a-f]{40}$ ]] || {
  echo "Cannot establish immutable release commit. Use a git checkout or set RELEASE_COMMIT to the 40-char candidate SHA." >&2
  exit 1
}

# 单机发布必须串行。两个终端同时跑 migration/symlink 会破坏“原子发布”的前提。
exec 9>"$LOCK_FILE"
flock -n 9 || { echo "Another school-lifecycle release is already running." >&2; exit 1; }

env_value() {
  python3 "$ENV_RUNNER" --get "$ENV_FILE" "$1"
}
run_with_env() {
  python3 "$ENV_RUNNER" "$ENV_FILE" -- "$@"
}

ENV_FILE="$ENV_FILE" SOURCE_ROOT="$SOURCE_ROOT" bash "$SOURCE_ROOT/scripts/deploy/preflight-linux.sh"
id "$SERVICE_USER" >/dev/null 2>&1 || useradd --system --home "$APP_ROOT" --shell /usr/sbin/nologin "$SERVICE_USER"
install -d -o "$SERVICE_USER" -g "$SERVICE_USER" "$APP_ROOT/releases" "$APP_ROOT/shared/uploads" \
  "$APP_ROOT/shared/exports" "$BACKUP_DIR" /var/www/school-lifecycle
install -d -m 700 /etc/school-lifecycle

PUBLIC_BASE_URL_VALUE="$(env_value PUBLIC_BASE_URL)"
[ -n "$PUBLIC_BASE_URL_VALUE" ] || { echo "PUBLIC_BASE_URL is required for production client builds." >&2; exit 1; }

# EnvironmentFile 是数据文件，不允许用 shell `source`。强密码含 &, $, 空格等字符也必须安全。
DB_PASSWORD_VALUE="$(env_value DB_PASSWORD)"
DB_HOST_VALUE="$(env_value DB_HOST)"; DB_HOST_VALUE="${DB_HOST_VALUE:-127.0.0.1}"
DB_PORT_VALUE="$(env_value DB_PORT)"; DB_PORT_VALUE="${DB_PORT_VALUE:-3306}"
DB_USER_VALUE="$(env_value DB_USER)"
DB_NAME_VALUE="$(env_value DB_NAME)"
[ -n "$DB_PASSWORD_VALUE" ] && [ -n "$DB_USER_VALUE" ] && [ -n "$DB_NAME_VALUE" ] \
  || { echo "Database backup settings are incomplete." >&2; exit 1; }

# 先在旧版本仍服务时完成所有耗时构建；真正停业务的窗口只包含备份、迁移、切换和启动。
install -d -o "$SERVICE_USER" -g "$SERVICE_USER" "$RELEASE_DIR"
# tmp/ 不排除：国标同步脚本仍读取仓库内 tmp/moe-* 源文件。
rsync -a --delete --exclude '.git' --exclude '.venv' --exclude 'node_modules' --exclude '.env*' \
  --exclude 'dist' "$SOURCE_ROOT/" "$RELEASE_DIR/"
printf '%s\n' "$SOURCE_COMMIT" > "$RELEASE_DIR/.release-commit"
chmod 444 "$RELEASE_DIR/.release-commit"
python3 -m venv "$RELEASE_DIR/backend/.venv"
"$RELEASE_DIR/backend/.venv/bin/pip" install --disable-pip-version-check -r "$RELEASE_DIR/backend/requirements.txt"

# 三个客户端必须属于同一个 release；禁止只更新管理端/小程序而漏掉学生 PC。
if command -v npm >/dev/null 2>&1; then
  (cd "$RELEASE_DIR/frontend" && NODE_OPTIONS=--max-old-space-size=1536 npm ci && npm run build)
  # miniapp/.env* 故意不复制进 release；生产 H5 必须由权威 PUBLIC_BASE_URL 显式注入，
  # 否则 env.js 会回退 http://localhost:8000，构建虽绿但学校浏览器实际不可用。
  (cd "$RELEASE_DIR/miniapp" && NODE_OPTIONS=--max-old-space-size=1536 npm ci \
    && VITE_API_BASE_URL="$PUBLIC_BASE_URL_VALUE" VITE_USE_MOCK=false npm run build:h5)
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

# 无论现场构建还是使用预构建产物，正式 H5 都不得携带 localhost API 地址。
if grep -RIlE 'https?://(localhost|127\.0\.0\.1)(:[0-9]+)?' "$RELEASE_DIR/miniapp/dist/build/h5" >/dev/null 2>&1; then
  echo "miniapp H5 contains a localhost API origin; release aborted." >&2
  exit 1
fi

previous="$(readlink -f "$APP_ROOT/current" 2>/dev/null || true)"
ACTIVE_OLD_SERVICES=()
for svc in school-lifecycle-backend school-lifecycle-scheduler school-lifecycle-file-scan; do
  if systemctl is-active --quiet "$svc" 2>/dev/null; then
    ACTIVE_OLD_SERVICES+=("$svc")
  fi
done
QUIESCED=0
ACTIVATED=0

release_failure_guard() {
  status=$?
  if [ "$status" -ne 0 ] && [ "$QUIESCED" = "1" ]; then
    if [ "$ACTIVATED" = "1" ] && [ -n "$previous" ] && [ -d "$previous" ]; then
      ln -sfnT "$previous" "$APP_ROOT/current.rollback" || true
      mv -Tf "$APP_ROOT/current.rollback" "$APP_ROOT/current" || true
    fi
    if [ "${#ACTIVE_OLD_SERVICES[@]}" -gt 0 ]; then
      systemctl start "${ACTIVE_OLD_SERVICES[@]}" >/dev/null 2>&1 || true
    fi
  fi
  exit "$status"
}
trap release_failure_guard EXIT

# 单机生产部署进入短暂静默窗口：先停 Web 和所有后台写入者，再在同一静默点取备份。
if [ "${#ACTIVE_OLD_SERVICES[@]}" -gt 0 ]; then
  systemctl stop "${ACTIVE_OLD_SERVICES[@]}"
fi
QUIESCED=1

backup_file="$BACKUP_DIR/pre_release_${RELEASE_ID}.sql.gz"
MYSQL_PWD="$DB_PASSWORD_VALUE" mysqldump -h"$DB_HOST_VALUE" -P"$DB_PORT_VALUE" \
  -u"$DB_USER_VALUE" --single-transaction --quick --routines --events --triggers --hex-blob \
  --default-character-set=utf8mb4 "$DB_NAME_VALUE" | gzip -9 > "$backup_file.partial"
gzip -t "$backup_file.partial"
mv "$backup_file.partial" "$backup_file"
sha256sum "$backup_file" > "$backup_file.sha256"
unset DB_PASSWORD_VALUE

(cd "$RELEASE_DIR/backend" && run_with_env "$RELEASE_DIR/backend/.venv/bin/python" -m alembic upgrade head)
(cd "$RELEASE_DIR/backend" && run_with_env "$RELEASE_DIR/backend/.venv/bin/python" scripts/check_alembic_current.py)

if [ -e "$APP_ROOT/current" ] && [ ! -L "$APP_ROOT/current" ]; then
  legacy_current="$APP_ROOT/releases/legacy_current_${RELEASE_ID}"
  mv -- "$APP_ROOT/current" "$legacy_current"
  previous="$legacy_current"
fi
ln -sfnT "$RELEASE_DIR" "$APP_ROOT/current.next"
mv -Tf "$APP_ROOT/current.next" "$APP_ROOT/current"
ACTIVATED=1

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
QUIESCED=0

if ! APP_ROOT="$APP_ROOT" ENV_FILE="$ENV_FILE" bash "$SOURCE_ROOT/scripts/deploy/verify-systemd-release.sh"; then
  if [ -n "$previous" ] && [ -d "$previous" ]; then
    ln -sfnT "$previous" "$APP_ROOT/current.rollback"
    mv -Tf "$APP_ROOT/current.rollback" "$APP_ROOT/current"
    systemctl restart school-lifecycle-backend school-lifecycle-scheduler school-lifecycle-file-scan
    echo "Application symlink rolled back to $previous; database migration was intentionally not downgraded." >&2
  fi
  exit 1
fi

# 生产主机证据不是 CI 截图：重新从已激活 release 自身执行预检+运行时验收，
# 并把 commit/主机指纹/备份校验写成 0600 JSON。任何一步失败都不产生 PASS 证据。
EXPECTED_RELEASE_COMMIT="$SOURCE_COMMIT" BACKUP_FILE="$backup_file" \
  APP_ROOT="$APP_ROOT" ENV_FILE="$ENV_FILE" \
  bash "$RELEASE_DIR/scripts/deploy/accept-production-release.sh"

trap - EXIT
echo "Release $RELEASE_ID installed. Commit: $SOURCE_COMMIT. Backup: $backup_file"
