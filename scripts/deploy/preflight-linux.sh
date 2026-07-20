#!/usr/bin/env bash
# Read-only readiness check for the 2U4G systemd deployment.
set -u

ROOT="${SOURCE_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
ENV_FILE="${ENV_FILE:-/etc/school-lifecycle/backend.env}"
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
  command -v "$cmd" >/dev/null 2>&1 && pass "$cmd 已安装" || warning "$cmd 未安装；可改为在开发机上传已构建 dist"
done

cpu_count="$(getconf _NPROCESSORS_ONLN 2>/dev/null || printf 0)"
mem_kb="$(awk '/MemTotal/ {print $2}' /proc/meminfo 2>/dev/null || printf 0)"
disk_kb="$(df -Pk /opt 2>/dev/null | awk 'NR==2 {print $4}' || printf 0)"
[ "$cpu_count" -ge 2 ] && pass "CPU=${cpu_count} 核" || warning "CPU 少于 2 核"
[ "$mem_kb" -ge 3500000 ] && pass "内存满足 4G 档" || warning "可用物理内存低于 3.5GB"
[ "$disk_kb" -ge 10485760 ] && pass "/opt 可用磁盘不少于 10GB" || warning "/opt 可用磁盘不足 10GB"

if [ ! -f "$ENV_FILE" ]; then
  failure "缺少 $ENV_FILE"
else
  pass "生产环境文件存在"
  mode="$(stat -c '%a' "$ENV_FILE" 2>/dev/null || printf unknown)"
  [ "$mode" = "600" ] && pass "环境文件权限为 600" || warning "环境文件权限=$mode，建议 chmod 600"
  getv() { sed -n "s/^$1=//p" "$ENV_FILE" | tail -n 1; }
  app_env="$(getv APP_ENV)"
  debug="$(getv DEBUG)"
  mock="$(getv MOCK_LOGIN_ENABLED)"
  cors="$(getv CORS_ORIGINS)"
  jwt="$(getv JWT_SECRET_KEY)"
  db_password="$(getv DB_PASSWORD)"
  case "${app_env,,}" in prod|production) pass "APP_ENV=production" ;; *) failure "APP_ENV 必须为 production" ;; esac
  [ "${debug,,}" = "false" ] && pass "DEBUG=false" || failure "DEBUG 必须为 false"
  [ "${mock,,}" = "false" ] && pass "mock-login 已关闭" || failure "MOCK_LOGIN_ENABLED 必须为 false"
  [ -n "$cors" ] && [[ "$cors" != *'*'* ]] && [[ "$cors" == https://* ]] \
    && pass "CORS 为 HTTPS 白名单" || failure "CORS 必须是明确的 HTTPS 域名"
  [ "${#jwt}" -ge 32 ] && [[ "$jwt" != *'替换'* ]] && pass "JWT 密钥长度合格" || failure "JWT 密钥未替换或少于 32 位"
  [ -n "$db_password" ] && [[ "$db_password" != *'替换'* ]] && pass "数据库密码已配置" || failure "数据库密码未配置"
fi

for path in \
  backend/alembic/versions/0109_implementation_permissions.py \
  backend/alembic/versions/0110_change_impact_analysis.py \
  backend/alembic/versions/0111_immutable_acceptance_summary.py \
  deploy/systemd/school-lifecycle-backend.service \
  deploy/systemd/school-lifecycle-scheduler.service \
  deploy/nginx/school-lifecycle.systemd.conf.example; do
  [ -f "$ROOT/$path" ] && pass "$path" || failure "缺少 $path"
done

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
[ "$heads" = "0111_immutable_acceptance_summary" ] && pass "Alembic 唯一 head=0111" \
  || failure "Alembic head 异常：$heads"

printf '== 预检完成：FAIL=%s WARN=%s ==\n' "$fail" "$warn"
[ "$fail" -eq 0 ]
