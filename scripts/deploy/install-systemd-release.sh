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
BACKUP_ENV_FILE="${BACKUP_ENV_FILE:-/etc/school-lifecycle/backup.env}"
SERVICE_USER="${SERVICE_USER:-schoolapp}"
RELEASE_ID="${RELEASE_ID:-$(date +%Y%m%d_%H%M%S)}"
RELEASE_DIR="$APP_ROOT/releases/$RELEASE_ID"
ENV_RUNNER="$SOURCE_ROOT/scripts/deploy/run-with-envfile.py"
LOCK_FILE="${DEPLOY_LOCK_FILE:-/run/lock/school-lifecycle-release.lock}"

# 生产证据必须证明“验收的是哪个 commit”，且 git 工作区内容必须真的等于该 commit。
# 过去仅把 `git rev-parse HEAD` 写进 marker、再 rsync 当前工作区，会把未提交改动/未跟踪文件
# 一起带进 release，形成“证据写 A，实际运行 B”的假不可变发布。git 来源现在只允许干净 checkout，
# 并直接用 git archive 从候选 commit 物化 release；离线发布包仍必须显式提供 RELEASE_COMMIT。
SOURCE_COMMIT="${RELEASE_COMMIT:-}"
SOURCE_IS_GIT=0
if command -v git >/dev/null 2>&1 && git -C "$SOURCE_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  SOURCE_IS_GIT=1
  GIT_COMMIT="$(git -C "$SOURCE_ROOT" rev-parse HEAD)"
  [[ "$GIT_COMMIT" =~ ^[0-9a-f]{40}$ ]] || { echo "Cannot resolve source git commit." >&2; exit 1; }
  if [ -n "$SOURCE_COMMIT" ] && [ "$SOURCE_COMMIT" != "$GIT_COMMIT" ]; then
    echo "RELEASE_COMMIT does not match source checkout HEAD." >&2
    exit 1
  fi
  if [ -n "$(git -C "$SOURCE_ROOT" status --porcelain --untracked-files=all)" ]; then
    echo "Source checkout is dirty; commit/stash/remove untracked release inputs before production deploy." >&2
    exit 1
  fi
  SOURCE_COMMIT="$GIT_COMMIT"
fi
[[ "$SOURCE_COMMIT" =~ ^[0-9a-f]{40}$ ]] || {
  echo "Cannot establish immutable release commit. Use a clean git checkout or set RELEASE_COMMIT for a trusted offline package." >&2
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
[ -r "$BACKUP_ENV_FILE" ] || { echo "Governed backup env is required: $BACKUP_ENV_FILE" >&2; exit 1; }
id "$SERVICE_USER" >/dev/null 2>&1 || useradd --system --home "$APP_ROOT" --shell /usr/sbin/nologin "$SERVICE_USER"
install -d -o "$SERVICE_USER" -g "$SERVICE_USER" "$APP_ROOT/releases" "$APP_ROOT/shared/uploads" \
  "$APP_ROOT/shared/exports" /var/www/school-lifecycle
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
  || { echo "Database settings are incomplete." >&2; exit 1; }

# 先在旧版本仍服务时完成所有耗时构建；真正停业务的窗口只包含受治理备份、迁移、切换和启动。
install -d -o "$SERVICE_USER" -g "$SERVICE_USER" "$RELEASE_DIR"
if [ "$SOURCE_IS_GIT" = "1" ]; then
  # 只从已确认的 commit tree 物化，绝不把工作区未提交/未跟踪内容混进生产 release。
  git -C "$SOURCE_ROOT" archive --format=tar "$SOURCE_COMMIT" | tar -xf - -C "$RELEASE_DIR"
else
  # 可信离线发布包没有 .git；调用方必须显式传 RELEASE_COMMIT，包自身不能靠时间戳冒充版本。
  # tmp/ 不排除：国标同步脚本仍读取仓库内 tmp/moe-* 源文件。
  rsync -a --delete --exclude '.git' --exclude '.venv' --exclude 'node_modules' --exclude '.env*' \
    --exclude 'dist' "$SOURCE_ROOT/" "$RELEASE_DIR/"
fi
printf '%s\n' "$SOURCE_COMMIT" > "$RELEASE_DIR/.release-commit"
chmod 444 "$RELEASE_DIR/.release-commit"
# 从这里开始，所有会影响运行态/迁移/服务单元的脚本都必须取自不可变 RELEASE_DIR，
# 不能再回到部署期间可能被更新的 SOURCE_ROOT。
ENV_RUNNER="$RELEASE_DIR/scripts/deploy/run-with-envfile.py"
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
  # git checkout 的 prebuilt dist 通常是未跟踪文件，无法证明属于 SOURCE_COMMIT，禁止拿来发布。
  [ "$SOURCE_IS_GIT" != "1" ] || { echo "Node/npm is required for git-backed production releases." >&2; exit 1; }
  [ -f "$SOURCE_ROOT/frontend/dist/index.html" ] \
    && [ -f "$SOURCE_ROOT/miniapp/dist/build/h5/index.html" ] \
    && [ -f "$SOURCE_ROOT/student-portal/dist/index.html" ] \
    || { echo "Node missing and one or more trusted offline prebuilt dist outputs are missing" >&2; exit 1; }
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
MIGRATION_STARTED=0
ROLLBACK_MANIFEST=""
backup_file=""
BACKUP_TIMER_UNIT="school-lifecycle-backup.timer"
BACKUP_SERVICE_UNIT="school-lifecycle-backup.service"
BACKUP_TIMER_WAS_ACTIVE=0
BACKUP_TIMER_QUIESCED=0

quiesce_scheduled_backup() {
  # The timer is release-external state: preserve whether it was actually active instead of
  # blindly enabling it later. Stop the timer first so it cannot launch a new oneshot while the
  # release drains an already-running backup service.
  if systemctl is-active --quiet "$BACKUP_TIMER_UNIT" 2>/dev/null; then
    BACKUP_TIMER_WAS_ACTIVE=1
  fi
  BACKUP_TIMER_QUIESCED=1
  if [ "$BACKUP_TIMER_WAS_ACTIVE" = "1" ]; then
    systemctl stop "$BACKUP_TIMER_UNIT"
  fi
  if systemctl is-active --quiet "$BACKUP_SERVICE_UNIT" 2>/dev/null; then
    systemctl stop "$BACKUP_SERVICE_UNIT"
  fi
}

restore_scheduled_backup_timer() {
  if [ "$BACKUP_TIMER_QUIESCED" != "1" ]; then
    return 0
  fi
  if [ "$BACKUP_TIMER_WAS_ACTIVE" = "1" ]; then
    systemctl start "$BACKUP_TIMER_UNIT"
  fi
  BACKUP_TIMER_QUIESCED=0
}

restore_previous_systemd_units() {
  if [ -z "$previous" ] || [ ! -d "$previous" ]; then
    return 0
  fi
  for unit in school-lifecycle-backend.service school-lifecycle-scheduler.service school-lifecycle-file-scan.service; do
    if [ -f "$previous/deploy/systemd/$unit" ]; then
      install -m 644 "$previous/deploy/systemd/$unit" "/etc/systemd/system/$unit"
    fi
  done
  systemctl daemon-reload >/dev/null 2>&1 || true
}

release_failure_guard() {
  status=$?
  trap - EXIT
  if [ "$status" -ne 0 ] && [ "$BACKUP_TIMER_QUIESCED" = "1" ]; then
    # Recovery itself must not race a timer event. A timer that was originally active is restored
    # only after rollback and the previous service set are healthy again.
    systemctl stop "$BACKUP_TIMER_UNIT" "$BACKUP_SERVICE_UNIT" >/dev/null 2>&1 || true
  fi
  if [ "$status" -ne 0 ] && [ "$QUIESCED" = "1" ]; then
    # 任何候选写入者都必须先停；数据库/文件恢复期间绝不能有并发业务写。
    systemctl stop school-lifecycle-backend school-lifecycle-scheduler school-lifecycle-file-scan \
      >/dev/null 2>&1 || true

    if [ "$MIGRATION_STARTED" = "1" ]; then
      if [ -z "$ROLLBACK_MANIFEST" ] || [ ! -f "$ROLLBACK_MANIFEST" ]; then
        echo "CRITICAL: migration started but governed rollback manifest is unavailable; old services remain stopped." >&2
        exit 90
      fi
      echo "[$(date -Is)] candidate failed after migration start; restoring governed pre-release backup" >&2
      if ! python3 "$ENV_RUNNER" "$BACKUP_ENV_FILE" -- \
        python3 "$ENV_RUNNER" "$ENV_FILE" -- \
        env BACKUP_DIR="$(dirname "$ROLLBACK_MANIFEST")" \
        bash "$RELEASE_DIR/deploy/backup/restore-backup-set.sh" "$ROLLBACK_MANIFEST"; then
        echo "CRITICAL: governed rollback restore failed; old services remain stopped for manual recovery." >&2
        exit 91
      fi
    fi

    if [ "$ACTIVATED" = "1" ]; then
      if [ -n "$previous" ] && [ -d "$previous" ]; then
        ln -sfnT "$previous" "$APP_ROOT/current.rollback" || true
        mv -Tf "$APP_ROOT/current.rollback" "$APP_ROOT/current" || true
      else
        # 首次安装没有可回滚 release：移除失败候选的 current 指针并保持服务停止。
        rm -f "$APP_ROOT/current" || true
      fi
    fi

    restore_previous_systemd_units
    if [ "${#ACTIVE_OLD_SERVICES[@]}" -gt 0 ] && [ -n "$previous" ] && [ -d "$previous" ]; then
      if ! systemctl start "${ACTIVE_OLD_SERVICES[@]}"; then
        echo "CRITICAL: data restored but previous services failed to restart." >&2
        exit 92
      fi
    fi
  fi
  if [ "$BACKUP_TIMER_QUIESCED" = "1" ]; then
    if ! restore_scheduled_backup_timer; then
      echo "CRITICAL: application state recovered but the scheduled backup timer could not be restored." >&2
      exit 93
    fi
  fi
  unset DB_PASSWORD_VALUE || true
  exit "$status"
}
trap release_failure_guard EXIT

# 单机生产部署进入短暂静默窗口：先停定时备份触发器，再停 Web 和所有后台写入者；
# 若定时备份已经在跑，先终止该 oneshot，随后由 release 自己在静默点重新取一份完整治理备份。
quiesce_scheduled_backup
if [ "${#ACTIVE_OLD_SERVICES[@]}" -gt 0 ]; then
  systemctl stop "${ACTIVE_OLD_SERVICES[@]}"
fi
QUIESCED=1

# 发布前备份不再维护第二套 DB-only 真值：直接使用 #66 治理链（DB + uploads + manifest + offsite readback）。
GOVERNED_BACKUP_DIR="$(python3 "$ENV_RUNNER" --get "$BACKUP_ENV_FILE" BACKUP_DIR)"
GOVERNED_BACKUP_DIR="${GOVERNED_BACKUP_DIR:-/var/lib/school-lifecycle-backup}"
python3 "$ENV_RUNNER" "$BACKUP_ENV_FILE" -- \
  python3 "$ENV_RUNNER" "$ENV_FILE" -- \
  env BACKUP_DIR="$GOVERNED_BACKUP_DIR" REQUIRE_UPLOAD_BACKUP=true \
  bash "$RELEASE_DIR/deploy/backup/backup-runner.sh"
ROLLBACK_MANIFEST="$(find "$GOVERNED_BACKUP_DIR" -maxdepth 1 -type f -name 'manifest_*.json' \
  -printf '%T@ %p\n' | sort -nr | head -n1 | cut -d' ' -f2-)"
[ -n "$ROLLBACK_MANIFEST" ] && [ -s "$ROLLBACK_MANIFEST" ] \
  || { echo "governed pre-release backup manifest not found" >&2; exit 1; }
backup_file="$(python3 - "$ROLLBACK_MANIFEST" "$GOVERNED_BACKUP_DIR" <<'PY'
import json, sys
from pathlib import Path
manifest = Path(sys.argv[1])
root = Path(sys.argv[2]).resolve()
payload = json.loads(manifest.read_text(encoding='utf-8'))
name = payload['database']['file']
if Path(name).name != name:
    raise SystemExit('unsafe database backup filename')
path = (root / name).resolve()
if path.parent != root:
    raise SystemExit('database backup escaped governed directory')
print(path)
PY
)"
[ -s "$backup_file" ] || { echo "governed database backup missing" >&2; exit 1; }

# 迁移一旦开始，任何后续失败都必须从 ROLLBACK_MANIFEST 恢复后才能重新启动 previous。
MIGRATION_STARTED=1
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

install -m 644 "$RELEASE_DIR/deploy/systemd/school-lifecycle-backend.service" /etc/systemd/system/
install -m 644 "$RELEASE_DIR/deploy/systemd/school-lifecycle-scheduler.service" /etc/systemd/system/
install -m 644 "$RELEASE_DIR/deploy/systemd/school-lifecycle-file-scan.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable school-lifecycle-backend school-lifecycle-scheduler school-lifecycle-file-scan
systemctl restart school-lifecycle-backend school-lifecycle-scheduler school-lifecycle-file-scan

# rollback guard 必须保持 armed，直到 verify + final production acceptance 全部成功。
APP_ROOT="$APP_ROOT" ENV_FILE="$ENV_FILE" bash "$RELEASE_DIR/scripts/deploy/verify-systemd-release.sh"

# 生产主机证据不是 CI 截图：重新从已激活 release 自身执行预检+运行时验收，
# 并把 commit/主机指纹/受治理备份校验写成 0600 JSON。任何一步失败都不产生 PASS 证据。
EXPECTED_RELEASE_COMMIT="$SOURCE_COMMIT" BACKUP_FILE="$backup_file" \
  APP_ROOT="$APP_ROOT" ENV_FILE="$ENV_FILE" \
  bash "$RELEASE_DIR/scripts/deploy/accept-production-release.sh"

# Final acceptance succeeded. Restore exactly the scheduled-backup timer state observed before the
# release. If that restoration fails, keep the rollback guard armed and fail the release.
restore_scheduled_backup_timer
MIGRATION_STARTED=0
QUIESCED=0
unset DB_PASSWORD_VALUE
trap - EXIT
echo "Release $RELEASE_ID installed. Commit: $SOURCE_COMMIT. Governed backup: $ROLLBACK_MANIFEST"
