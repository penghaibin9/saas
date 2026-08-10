#!/usr/bin/env bash
# Post-release checks. No credentials are printed and no business data is changed.
set -u
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
APP_ROOT="${APP_ROOT:-/opt/school-lifecycle}"
ENV_FILE="${ENV_FILE:-/etc/school-lifecycle/backend.env}"
fail=0
pass() { printf '  [PASS] %s\n' "$1"; }
failure() { printf '  [FAIL] %s\n' "$1"; fail=$((fail + 1)); }

if [ ! -f "$ENV_FILE" ]; then
  failure "缺少生产环境文件 $ENV_FILE"
  ops_token=""
else
  # 与 systemd 使用同一 EnvironmentFile。只加载，不打印。
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
  ops_token="${INTERNAL_OPS_TOKEN:-}"
fi

for svc in school-lifecycle-backend school-lifecycle-scheduler school-lifecycle-file-scan; do
  systemctl is-active --quiet "$svc" && pass "$svc systemd active" || failure "$svc 未运行"
done
nginx -t >/dev/null 2>&1 && pass "nginx -t" || failure "nginx 配置错误"

nginx_dump="$(nginx -T 2>/dev/null || true)"
printf '%s' "$nginx_dump" | grep -Eq 'location[[:space:]]+(\^~[[:space:]]+)?/portal/' \
  && pass "Nginx 学生 PC /portal/ 已启用" || failure "Nginx 实际配置缺少 /portal/"
printf '%s' "$nginx_dump" | grep -Eq 'location[[:space:]]+(\^~[[:space:]]+)?/uploads/' \
  && pass "Nginx 包含 uploads 保护规则" || failure "Nginx 缺少 /uploads/ 保护规则"
printf '%s' "$nginx_dump" | grep -Eq 'location[[:space:]]+(\^~[[:space:]]+)?/exports/' \
  && pass "Nginx 包含 exports 保护规则" || failure "Nginx 缺少 /exports/ 保护规则"

health="$(curl -fsS --max-time 5 "$BASE_URL/health" 2>/dev/null || true)"
ready="$(curl -fsS --max-time 15 -H "X-Ops-Token: $ops_token" "$BASE_URL/health/ready" 2>/dev/null || true)"
printf '%s' "$health" | grep -q '"status":"UP"' && pass "/health UP" || failure "/health 异常"
printf '%s' "$ready" | grep -q '"status":"READY"' && pass "/health/ready READY" || failure "/health/ready 未就绪"

if [ -x "$APP_ROOT/current/backend/.venv/bin/python" ] && [ -d "$APP_ROOT/current/backend" ]; then
  if (cd "$APP_ROOT/current/backend" \
      && "$APP_ROOT/current/backend/.venv/bin/python" scripts/check_alembic_current.py >/dev/null); then
    pass "数据库迁移与仓库动态 head 一致"
  else
    failure "数据库迁移未到当前仓库唯一 head"
  fi
  if (cd "$APP_ROOT/current/backend" \
      && "$APP_ROOT/current/backend/.venv/bin/python" scripts/check_production_file_scan.py >/dev/null); then
    pass "ClamAV 文件扫描运行依赖正常"
  else
    failure "ClamAV 文件扫描运行依赖异常"
  fi
else
  failure "发布目录或共享 venv 不存在"
fi

for entry in \
  "$APP_ROOT/current/frontend/dist/index.html:管理 PC" \
  "$APP_ROOT/current/miniapp/dist/build/h5/index.html:小程序 H5" \
  "$APP_ROOT/current/student-portal/dist/index.html:学生 PC"; do
  path="${entry%%:*}"; name="${entry#*:}"
  [ -f "$path" ] && pass "$name 构建产物存在" || failure "$name 构建产物缺失"
done

for link in \
  /var/www/school-lifecycle/pc \
  /var/www/school-lifecycle/miniapp \
  /var/www/school-lifecycle/portal; do
  [ -L "$link" ] && [ -e "$link/index.html" ] && pass "$link 原子静态链接正常" || failure "$link 静态链接异常"
done

docs_code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 5 "$BASE_URL/docs" 2>/dev/null || true)"
[ "$docs_code" = "404" ] && pass "生产文档端点关闭" || failure "/docs HTTP=$docs_code"
unauth="$(curl -fsS --max-time 5 "$BASE_URL/api/v1/mobile/me/overview" 2>/dev/null || true)"
printf '%s' "$unauth" | grep -q '401001' && pass "未登录访问被拒绝" || failure "鉴权冒烟失败"

printf '== 发布验收：FAIL=%s ==\n' "$fail"
[ "$fail" -eq 0 ]
