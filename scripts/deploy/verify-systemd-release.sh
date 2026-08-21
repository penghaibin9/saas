#!/usr/bin/env bash
# Post-release checks. No credentials are printed and no business data is changed.
set -u
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
APP_ROOT="${APP_ROOT:-/opt/school-lifecycle}"
ENV_FILE="${ENV_FILE:-/etc/school-lifecycle/backend.env}"
ENV_RUNNER="$APP_ROOT/current/scripts/deploy/run-with-envfile.py"
fail=0
pass() { printf '  [PASS] %s\n' "$1"; }
failure() { printf '  [FAIL] %s\n' "$1"; fail=$((fail + 1)); }

if [ ! -f "$ENV_FILE" ]; then
  failure "缺少生产环境文件 $ENV_FILE"
  ops_token=""
  public_base=""
elif [ ! -f "$ENV_RUNNER" ]; then
  failure "当前 release 缺少安全 EnvironmentFile loader"
  ops_token=""
  public_base=""
else
  # systemd EnvironmentFile 是数据文件，不可 shell source；这里只安全读取非业务运行参数。
  ops_token="$(python3 "$ENV_RUNNER" --get "$ENV_FILE" INTERNAL_OPS_TOKEN 2>/dev/null || true)"
  public_base="$(python3 "$ENV_RUNNER" --get "$ENV_FILE" PUBLIC_BASE_URL 2>/dev/null || true)"
  [ -n "$ops_token" ] && pass "运维探针令牌可安全读取" || failure "INTERNAL_OPS_TOKEN 无法读取"
  [ -n "$public_base" ] && pass "PUBLIC_BASE_URL 可安全读取" || failure "PUBLIC_BASE_URL 无法读取"
fi

for svc in school-lifecycle-backend school-lifecycle-scheduler school-lifecycle-file-scan; do
  systemctl is-active --quiet "$svc" && pass "$svc systemd active" || failure "$svc 未运行"
done
nginx -t >/dev/null 2>&1 && pass "nginx -t" || failure "nginx 配置错误"

nginx_dump="$(nginx -T 2>/dev/null || true)"
printf '%s' "$nginx_dump" | grep -Eq 'location[[:space:]]+(\^~[[:space:]]+)?/portal/' \
  && pass "Nginx 学生 PC /portal/ 已启用" || failure "Nginx 实际配置缺少 /portal/"
printf '%s' "$nginx_dump" | grep -Eq 'location[[:space:]]+(\^~[[:space:]]+)?/enterprise/' \
  && pass "Nginx 企业协同 /enterprise/ 已启用" || failure "Nginx 实际配置缺少 /enterprise/"
printf '%s' "$nginx_dump" | grep -Eq 'location[[:space:]]+(\^~[[:space:]]+)?/uploads/' \
  && pass "Nginx 包含 uploads 保护规则" || failure "Nginx 缺少 /uploads/ 保护规则"
printf '%s' "$nginx_dump" | grep -Eq 'location[[:space:]]+(\^~[[:space:]]+)?/exports/' \
  && pass "Nginx 包含 exports 保护规则" || failure "Nginx 缺少 /exports/ 保护规则"

# 后端本机探针：区分应用本身故障与 Nginx/TLS 故障。
health="$(curl -fsS --max-time 5 "$BASE_URL/health" 2>/dev/null || true)"
ready="$(curl -fsS --max-time 15 -H "X-Ops-Token: $ops_token" "$BASE_URL/health/ready" 2>/dev/null || true)"
printf '%s' "$health" | grep -q '"status":"UP"' && pass "/health UP" || failure "/health 异常"
printf '%s' "$ready" | grep -q '"status":"READY"' && pass "/health/ready READY" || failure "/health/ready 未就绪"

if [ -x "$APP_ROOT/current/backend/.venv/bin/python" ] && [ -d "$APP_ROOT/current/backend" ] && [ -f "$ENV_RUNNER" ]; then
  run_backend_check() {
    (cd "$APP_ROOT/current/backend" \
      && python3 "$ENV_RUNNER" "$ENV_FILE" -- \
        "$APP_ROOT/current/backend/.venv/bin/python" "$1" >/dev/null)
  }
  if run_backend_check scripts/check_alembic_current.py; then
    pass "数据库迁移与仓库动态 head 一致"
  else
    failure "数据库迁移未到当前仓库唯一 head"
  fi
  if run_backend_check scripts/check_production_file_scan.py; then
    pass "ClamAV 文件扫描运行依赖正常"
  else
    failure "ClamAV 文件扫描运行依赖异常"
  fi
  if run_backend_check scripts/check_production_storage.py; then
    pass "文件存储后端真实探针正常"
  else
    failure "文件存储后端真实探针失败"
  fi
else
  failure "发布目录、共享 venv 或安全 EnvironmentFile loader 不存在"
fi

for entry in \
  "$APP_ROOT/current/frontend/dist/index.html:管理 PC" \
  "$APP_ROOT/current/miniapp/dist/build/h5/index.html:小程序 H5" \
  "$APP_ROOT/current/student-portal/dist/index.html:学生 PC" \
  "$APP_ROOT/current/enterprise-portal/dist/index.html:企业协同 PC"; do
  path="${entry%%:*}"; name="${entry#*:}"
  [ -f "$path" ] && pass "$name 构建产物存在" || failure "$name 构建产物缺失"
done

for link in \
  /var/www/school-lifecycle/pc \
  /var/www/school-lifecycle/miniapp \
  /var/www/school-lifecycle/portal \
  /var/www/school-lifecycle/enterprise; do
  [ -L "$link" ] && [ -e "$link/index.html" ] && pass "$link 原子静态链接正常" || failure "$link 静态链接异常"
done

# 不能只看 nginx -T：真实 TLS 虚拟主机必须能返回四端页面、安全头和文件拒绝规则。
# --resolve 强制从本机 127.0.0.1 命中正式 server_name，同时仍按真实域名校验证书/SNI。
if [[ "$public_base" == https://* ]]; then
  read -r public_host public_port < <(python3 - "$public_base" <<'PY'
from urllib.parse import urlsplit
import sys
u = urlsplit(sys.argv[1])
if u.scheme != "https" or not u.hostname or (u.path not in ("", "/")) or u.query or u.fragment:
    raise SystemExit(1)
print(u.hostname, u.port or 443)
PY
  ) || true
  if [ -n "${public_host:-}" ] && [ -n "${public_port:-}" ]; then
    resolve_arg="${public_host}:${public_port}:127.0.0.1"
    for path in / /portal/ /miniapp/ /enterprise/; do
      code="$(curl -sS --max-time 10 --resolve "$resolve_arg" -o /dev/null -w '%{http_code}' "${public_base}${path}" 2>/dev/null || true)"
      [ "$code" = "200" ] && pass "公网 TLS ${path} HTTP 200" || failure "公网 TLS ${path} HTTP=$code"
    done

    for path in / /portal/index.html /enterprise/index.html; do
      headers="$(curl -sS --max-time 10 --resolve "$resolve_arg" -D - -o /dev/null "${public_base}${path}" 2>/dev/null || true)"
      for header in strict-transport-security content-security-policy x-frame-options x-content-type-options; do
        printf '%s\n' "$headers" | grep -qi "^${header}:" \
          && pass "${path} 包含 ${header}" || failure "${path} 缺少 ${header}"
      done
    done

    for path in /uploads/__release_probe__ /exports/__release_probe__; do
      code="$(curl -sS --max-time 10 --resolve "$resolve_arg" -o /dev/null -w '%{http_code}' "${public_base}${path}" 2>/dev/null || true)"
      [ "$code" = "404" ] && pass "公网 ${path} 被静态拒绝" || failure "公网 ${path} HTTP=$code，预期 404"
    done

    public_unauth="$(curl -sS --max-time 10 --resolve "$resolve_arg" "${public_base}/api/v1/mobile/me/overview" 2>/dev/null || true)"
    printf '%s' "$public_unauth" | grep -q '401001' && pass "公网 API 未登录访问被拒绝" || failure "公网 API 鉴权冒烟失败"
  else
    failure "PUBLIC_BASE_URL 无法解析为 HTTPS origin"
  fi
else
  failure "PUBLIC_BASE_URL 必须为 HTTPS origin"
fi

docs_code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 5 "$BASE_URL/docs" 2>/dev/null || true)"
[ "$docs_code" = "404" ] && pass "生产文档端点关闭" || failure "/docs HTTP=$docs_code"
# 401 本来就是期望结果，不能用 curl -f 吞掉响应体，否则永远匹配不到业务码 401001。
unauth="$(curl -sS --max-time 5 "$BASE_URL/api/v1/mobile/me/overview" 2>/dev/null || true)"
printf '%s' "$unauth" | grep -q '401001' && pass "后端本机未登录访问被拒绝" || failure "后端本机鉴权冒烟失败"

printf '== 发布验收：FAIL=%s ==\n' "$fail"
[ "$fail" -eq 0 ]
