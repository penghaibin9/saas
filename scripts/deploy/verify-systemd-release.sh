#!/usr/bin/env bash
# Post-release checks. No credentials are printed and no business data is changed.
set -u
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
APP_ROOT="${APP_ROOT:-/opt/school-lifecycle}"
fail=0
pass() { printf '  [PASS] %s\n' "$1"; }
failure() { printf '  [FAIL] %s\n' "$1"; fail=$((fail + 1)); }

systemctl is-active --quiet school-lifecycle-backend && pass "backend systemd active" || failure "backend 未运行"
systemctl is-active --quiet school-lifecycle-scheduler && pass "scheduler systemd active" || failure "scheduler 未运行"
nginx -t >/dev/null 2>&1 && pass "nginx -t" || failure "nginx 配置错误"

health="$(curl -fsS --max-time 5 "$BASE_URL/health" 2>/dev/null || true)"
ready="$(curl -fsS --max-time 10 "$BASE_URL/health/ready" 2>/dev/null || true)"
printf '%s' "$health" | grep -q '"status":"UP"' && pass "/health UP" || failure "/health 异常"
printf '%s' "$ready" | grep -q '"status":"READY"' && pass "/health/ready READY" || failure "/health/ready 未就绪"

if [ -x "$APP_ROOT/current/backend/.venv/bin/python" ] && [ -d "$APP_ROOT/current/backend" ]; then
  current="$(cd "$APP_ROOT/current/backend" && "$APP_ROOT/current/backend/.venv/bin/python" -m alembic current 2>/dev/null || true)"
  printf '%s' "$current" | grep -q '0111_immutable_acceptance_summary' && pass "数据库迁移=0111" || failure "数据库迁移未到 0111"
else
  failure "发布目录或共享 venv 不存在"
fi

docs_code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 5 "$BASE_URL/docs" 2>/dev/null || true)"
[ "$docs_code" = "404" ] && pass "生产文档端点关闭" || failure "/docs HTTP=$docs_code"
unauth="$(curl -fsS --max-time 5 "$BASE_URL/api/v1/mobile/me/overview" 2>/dev/null || true)"
printf '%s' "$unauth" | grep -q '401001' && pass "未登录访问被拒绝" || failure "鉴权冒烟失败"

printf '== 发布验收：FAIL=%s ==\n' "$fail"
[ "$fail" -eq 0 ]
