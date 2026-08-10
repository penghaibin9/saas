#!/usr/bin/env bash
# Read-only readiness check for the 2U4G systemd deployment.
# 不修改数据库/服务；任何生产红线失败都返回非零。
set -u

ROOT="${SOURCE_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
ENV_FILE="${ENV_FILE:-/etc/school-lifecycle/backend.env}"
ENV_RUNNER="$ROOT/scripts/deploy/run-with-envfile.py"
fail=0
warn=0
pass() { printf '  [PASS] %s\n' "$1"; }
warning() { printf '  [WARN] %s\n' "$1"; warn=$((warn + 1)); }
failure() { printf '  [FAIL] %s\n' "$1"; fail=$((fail + 1)); }

printf '== 2U4G 非容器部署预检（只读）==\n'

for cmd in python3 nginx mysql mysqldump redis-cli curl rsync gzip sha256sum systemctl; do
  command -v "$cmd" >/dev/null 2>&1 && pass "$cmd 已安装" || failure "$cmd 未安装"
done
for cmd in node npm; do
  command -v "$cmd" >/dev/null 2>&1 && pass "$cmd 已安装" || warning "$cmd 未安装；只能使用预先构建好的三端 dist"
done

cpu_count="$(getconf _NPROCESSORS_ONLN 2>/dev/null || printf 0)"
mem_kb="$(awk '/MemTotal/ {print $2}' /proc/meminfo 2>/dev/null || printf 0)"
disk_kb="$(df -Pk /opt 2>/dev/null | awk 'NR==2 {print $4}' || printf 0)"
[ "$cpu_count" -ge 2 ] && pass "CPU=${cpu_count} 核" || warning "CPU 少于 2 核"
[ "$mem_kb" -ge 3500000 ] && pass "内存满足 4G 档" || warning "可用物理内存低于 3.5GB"
[ "$disk_kb" -ge 10485760 ] && pass "/opt 可用磁盘不少于 10GB" || warning "/opt 可用磁盘不足 10GB"

if [ ! -f "$ENV_FILE" ]; then
  failure "缺少 $ENV_FILE"
elif [ ! -f "$ENV_RUNNER" ]; then
  failure "缺少安全 EnvironmentFile loader：$ENV_RUNNER"
else
  pass "生产环境文件存在"
  mode="$(stat -c '%a' "$ENV_FILE" 2>/dev/null || printf unknown)"
  [ "$mode" = "600" ] && pass "环境文件权限为 600" || warning "环境文件权限=$mode，建议 chmod 600"

  if python3 "$ENV_RUNNER" "$ENV_FILE" -- /usr/bin/true >/dev/null 2>&1; then
    pass "EnvironmentFile 语法可安全解析"
  else
    failure "EnvironmentFile 含不支持/不安全语法"
  fi
  getv() { python3 "$ENV_RUNNER" --get "$ENV_FILE" "$1" 2>/dev/null || true; }

  app_env="$(getv APP_ENV)"
  deployment_mode="$(getv DEPLOYMENT_MODE)"
  debug="$(getv DEBUG)"
  mock="$(getv MOCK_LOGIN_ENABLED)"
  cors="$(getv CORS_ORIGINS)"
  jwt="$(getv JWT_SECRET)"
  [ -n "$jwt" ] || jwt="$(getv JWT_SECRET_KEY)"
  db_enabled="$(getv DB_ENABLED)"
  db_driver="$(getv DB_DRIVER)"
  db_password="$(getv DB_PASSWORD)"
  redis_url="$(getv REDIS_URL)"
  internal_ops_token="$(getv INTERNAL_OPS_TOKEN)"
  field_key="$(getv FIELD_ENCRYPTION_KEY)"
  clamav_enabled="$(getv CLAMAV_ENABLED)"

  case "${app_env,,}" in prod|production) pass "APP_ENV=production" ;; *) failure "APP_ENV 必须为 production" ;; esac
  [ "${deployment_mode,,}" = "production" ] && pass "DEPLOYMENT_MODE=production" || failure "DEPLOYMENT_MODE 必须为 production"
  [ "${debug,,}" = "false" ] && pass "DEBUG=false" || failure "DEBUG 必须为 false"
  [ "${mock,,}" = "false" ] && pass "mock-login 已关闭" || failure "MOCK_LOGIN_ENABLED 必须为 false"
  [ "${db_enabled,,}" = "true" ] && pass "DB_ENABLED=true" || failure "DB_ENABLED 必须为 true"
  [ "${db_driver,,}" = "mysql" ] && pass "DB_DRIVER=mysql" || failure "正式试点只允许 MySQL"
  [ -n "$cors" ] && [[ "$cors" != *'*'* ]] && [[ "$cors" == https://* ]] \
    && pass "CORS 为 HTTPS 白名单" || failure "CORS 必须是明确的 HTTPS 域名"
  [ "${#jwt}" -ge 32 ] && [[ "$jwt" != *'替换'* ]] && [[ "$jwt" != *'dev-secret'* ]] \
    && pass "JWT 密钥长度合格" || failure "JWT 密钥未替换或少于 32 位"
  [ -n "$db_password" ] && [[ "$db_password" != *'替换'* ]] && pass "数据库密码已配置" || failure "数据库密码未配置"
  [ -n "$redis_url" ] && [[ "$redis_url" != *'替换'* ]] && pass "Redis 已配置" || failure "多 worker 正式部署必须配置 Redis"
  [ "${#internal_ops_token}" -ge 24 ] && [[ "$internal_ops_token" != *'替换'* ]] \
    && pass "运维探针令牌已配置" || failure "INTERNAL_OPS_TOKEN 未配置或过短"

  default_field_key="jxd5OL3YvyF335hh52bntwYmmA7ZJ_BXWxyZt4CcGd4="
  [ "${#field_key}" -ge 32 ] && [ "$field_key" != "$default_field_key" ] && [[ "$field_key" != *'替换'* ]] \
    && pass "敏感字段加密密钥已独立配置" || failure "FIELD_ENCRYPTION_KEY 仍为默认/占位值"

  [ "${clamav_enabled,,}" = "true" ] && pass "CLAMAV_ENABLED=true" || failure "正式试点必须启用 ClamAV 文件扫描"

  storage_backend="$(getv FILE_STORAGE_BACKEND)"
  if [ "${storage_backend,,}" = "cos" ]; then
    cos_region="$(getv COS_REGION)"; cos_bucket="$(getv COS_BUCKET)"
    cos_id="$(getv COS_SECRET_ID)"; cos_key="$(getv COS_SECRET_KEY)"
    [ -n "$cos_region" ] && [ -n "$cos_bucket" ] && [ -n "$cos_id" ] && [ -n "$cos_key" ] \
      && [[ "$cos_key" != *'替换'* ]] && pass "COS 参数已配置" || failure "FILE_STORAGE_BACKEND=cos 但 COS 参数不完整"
  else
    warning "FILE_STORAGE_BACKEND=${storage_backend:-local}；单机试点可用，但必须确认附件目录纳入备份"
  fi

  # 只做 ClamAV PING，不扫描业务文件，不输出主机/凭据。
  if [ "${clamav_enabled,,}" = "true" ]; then
    clam_host="$(getv CLAMAV_HOST)"; [ -n "$clam_host" ] || clam_host="127.0.0.1"
    clam_port="$(getv CLAMAV_PORT)"; [ -n "$clam_port" ] || clam_port="3310"
    clam_socket="$(getv CLAMAV_UNIX_SOCKET)"
    if python3 - "$clam_host" "$clam_port" "$clam_socket" <<'PY'
import socket, sys
host, port, unix_socket = sys.argv[1], int(sys.argv[2]), sys.argv[3]
try:
    if unix_socket:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect(unix_socket)
    else:
        s = socket.create_connection((host, port), timeout=2)
    with s:
        s.sendall(b'zPING\0')
        data = s.recv(64).rstrip(b'\0\r\n').upper()
    raise SystemExit(0 if data == b'PONG' else 1)
except OSError:
    raise SystemExit(1)
PY
    then pass "ClamAV clamd PING 正常"; else failure "ClamAV clamd 不可连接或未返回 PONG"; fi
  fi
fi

for path in \
  scripts/deploy/run-with-envfile.py \
  backend/scripts/check_alembic_current.py \
  backend/scripts/check_production_file_scan.py \
  backend/scripts/check_production_storage.py \
  deploy/systemd/school-lifecycle-backend.service \
  deploy/systemd/school-lifecycle-scheduler.service \
  deploy/systemd/school-lifecycle-file-scan.service \
  deploy/nginx/school-lifecycle.systemd.conf.example \
  student-portal/package.json; do
  [ -f "$ROOT/$path" ] && pass "$path" || failure "缺少 $path"
done

# 动态计算迁移图 head：只允许一个，但绝不把某个 revision 名写死在部署脚本里。
heads="$(python3 - "$ROOT/backend/alembic/versions" <<'PY'
import ast
import pathlib
import sys
revisions, parents = set(), set()
for path in pathlib.Path(sys.argv[1]).glob('*.py'):
    tree = ast.parse(path.read_text(encoding='utf-8-sig'))
    values = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id in ('revision', 'down_revision'):
                try:
                    values[node.targets[0].id] = ast.literal_eval(node.value)
                except Exception:
                    pass
    rev, down = values.get('revision'), values.get('down_revision')
    if rev:
        revisions.add(rev)
    if isinstance(down, str):
        parents.add(down)
    elif isinstance(down, (tuple, list)):
        parents.update(x for x in down if x)
print('\n'.join(sorted(revisions - parents)))
PY
)"
head_count="$(printf '%s\n' "$heads" | sed '/^$/d' | wc -l | tr -d ' ')"
if [ "$head_count" = "1" ]; then
  pass "Alembic 唯一 head=$heads"
else
  failure "Alembic 必须唯一 head；当前数量=$head_count"
fi

if nginx -t >/dev/null 2>&1; then
  pass "nginx -t"
  nginx_dump="$(nginx -T 2>/dev/null || true)"
  printf '%s' "$nginx_dump" | grep -Eq 'location[[:space:]]+(\^~[[:space:]]+)?/portal/' \
    && pass "Nginx 已启用学生 PC /portal/" || failure "Nginx 实际配置缺少 /portal/ 学生 PC 入口"
else
  failure "nginx -t 失败"
fi

printf '== 预检完成：FAIL=%s WARN=%s ==\n' "$fail" "$warn"
[ "$fail" -eq 0 ]
