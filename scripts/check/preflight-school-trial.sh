#!/usr/bin/env bash
# 学校试点上线前 · 静态准入预检（不需要服务运行，不改数据）。
# 用法：bash scripts/check/preflight-school-trial.sh [backend/.env路径]
set -u
ENV_FILE="${1:-backend/.env}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FAIL=0; WARN=0
pass(){ echo "  [PASS] $1"; }
warn(){ echo "  [WARN] $1"; WARN=$((WARN+1)); }
fail(){ echo "  [FAIL] $1"; FAIL=$((FAIL+1)); }
getv(){ grep -E "^$1=" "$ENV_FILE" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '\r'; }

echo "== 学校试点静态准入预检：$ENV_FILE =="
if [ ! -f "$ENV_FILE" ]; then
  fail "未找到 $ENV_FILE（生产必须提供 .env/EnvironmentFile）"
else
  APP_ENV_V="$(getv APP_ENV)"
  DEPLOY_V="$(getv DEPLOYMENT_MODE)"
  DEBUG_V="$(getv DEBUG)"
  MOCK_V="$(getv MOCK_LOGIN_ENABLED)"
  DB_ENABLED_V="$(getv DB_ENABLED)"
  DB_DRIVER_V="$(getv DB_DRIVER)"
  CORS_V="$(getv CORS_ORIGINS)"
  JWT_V="$(getv JWT_SECRET)"; [ -n "$JWT_V" ] || JWT_V="$(getv JWT_SECRET_KEY)"
  FIELD_V="$(getv FIELD_ENCRYPTION_KEY)"
  REDIS_V="$(getv REDIS_URL)"
  OPS_V="$(getv INTERNAL_OPS_TOKEN)"
  SCHED_V="$(getv SCHEDULER_MODE)"
  WEB_V="$(getv WEB_CONCURRENCY)"
  MULTI_V="$(getv MULTI_INSTANCE)"
  CLAM_V="$(getv CLAMAV_ENABLED)"

  [ "$APP_ENV_V" = "production" ] && pass "APP_ENV=production" || fail "APP_ENV 必须为 production"
  [ "$DEPLOY_V" = "production" ] && pass "DEPLOYMENT_MODE=production" || fail "DEPLOYMENT_MODE 必须为 production"
  [ "$DEBUG_V" = "false" ] && pass "DEBUG=false" || fail "DEBUG 必须为 false"
  [ "$MOCK_V" = "false" ] && pass "mock-login 已关闭" || fail "MOCK_LOGIN_ENABLED 必须为 false"
  [ "$DB_ENABLED_V" = "true" ] && [ "$DB_DRIVER_V" = "mysql" ] && pass "真实 MySQL 已启用" || fail "试点必须 DB_ENABLED=true + DB_DRIVER=mysql"
  [ -n "$CORS_V" ] && [ "$CORS_V" != "*" ] && [[ "$CORS_V" == https://* ]] && pass "CORS 为 HTTPS 白名单" || fail "CORS 必须收敛到 HTTPS 域名"
  [ "${#JWT_V}" -ge 32 ] && [[ "$JWT_V" != *'change-me'* ]] && [[ "$JWT_V" != *'dev-secret'* ]] && [[ "$JWT_V" != *'替换'* ]] \
    && pass "JWT_SECRET 已替换" || fail "JWT_SECRET 未替换或过短"

  default_field_key="jxd5OL3YvyF335hh52bntwYmmA7ZJ_BXWxyZt4CcGd4="
  [ "${#FIELD_V}" -ge 32 ] && [ "$FIELD_V" != "$default_field_key" ] && [[ "$FIELD_V" != *'替换'* ]] \
    && pass "FIELD_ENCRYPTION_KEY 已独立配置" || fail "FIELD_ENCRYPTION_KEY 仍是默认/占位值"
  [ -n "$REDIS_V" ] && [[ "$REDIS_V" != *'替换'* ]] && pass "Redis 已配置" || fail "正式多 worker 必须配置 Redis"
  [ "${#OPS_V}" -ge 24 ] && [[ "$OPS_V" != *'替换'* ]] && pass "INTERNAL_OPS_TOKEN 已配置" || fail "运维探针令牌未配置"
  [ "$SCHED_V" = "external" ] && pass "调度使用独立进程" || fail "正式 2 worker 部署必须 SCHEDULER_MODE=external"
  if [ "${WEB_V:-1}" -gt 1 ] 2>/dev/null || [ "$MULTI_V" = "true" ]; then
    [ -n "$REDIS_V" ] && pass "多 worker Redis 合同满足" || fail "多 worker/多实例缺 Redis"
  fi
  [ "$CLAM_V" = "true" ] && pass "ClamAV 文件扫描已启用" || fail "正式试点必须 CLAMAV_ENABLED=true"

  STORAGE_V="$(getv FILE_STORAGE_BACKEND)"
  if [ "$STORAGE_V" = "cos" ]; then
    COS_REGION_V="$(getv COS_REGION)"; COS_BUCKET_V="$(getv COS_BUCKET)"
    COS_ID_V="$(getv COS_SECRET_ID)"; COS_KEY_V="$(getv COS_SECRET_KEY)"
    [ -n "$COS_REGION_V" ] && [ -n "$COS_BUCKET_V" ] && [ -n "$COS_ID_V" ] && [ -n "$COS_KEY_V" ] \
      && pass "COS 配置字段完整" || fail "FILE_STORAGE_BACKEND=cos 但 COS 参数不完整"
  else
    warn "当前文件后端=${STORAGE_V:-local}；试点若用本地盘，必须验证 uploads 备份+恢复"
  fi

  SMS_V="$(getv SMS_ENABLED)"
  if [ "$SMS_V" = "true" ]; then
    getv SMS_ACCESS_KEY_ID | grep -q . && getv SMS_TEMPLATE_PASSWORD_RESET | grep -q . \
      && pass "短信基础配置已填写" || fail "SMS_ENABLED=true 但短信密钥/找回密码模板不完整"
  else
    warn "SMS_ENABLED=false；若学校要求短信找回密码/通知，试点前需开通并实发验收"
  fi
fi

# 三端生产 API 地址不得硬编码本机地址。
for dir in frontend student-portal miniapp; do
  if grep -RIl "localhost:8000\|127.0.0.1:8000" "$ROOT/$dir"/.env* 2>/dev/null | grep -q .; then
    fail "$dir 构建环境仍含 localhost:8000/127.0.0.1:8000"
  else
    pass "$dir 未发现生产 env 硬编码 localhost API"
  fi
done

for path in \
  deploy/systemd/school-lifecycle-backend.service \
  deploy/systemd/school-lifecycle-scheduler.service \
  deploy/systemd/school-lifecycle-file-scan.service \
  backend/scripts/check_production_file_scan.py \
  backend/scripts/check_alembic_current.py \
  student-portal/package.json \
  deploy/nginx/school-lifecycle.systemd.conf.example; do
  [ -f "$ROOT/$path" ] && pass "$path" || fail "缺少 $path"
done

grep -q 'student-portal' "$ROOT/scripts/deploy/install-systemd-release.sh" \
  && pass "发布脚本已收编学生 PC" || fail "发布脚本未收编 student-portal"
grep -q 'school-lifecycle-file-scan' "$ROOT/scripts/deploy/install-systemd-release.sh" \
  && pass "发布脚本已收编 file-scan worker" || fail "发布脚本未收编 file-scan worker"
grep -Eq 'location[[:space:]]+\^~[[:space:]]+/portal/' "$ROOT/deploy/nginx/school-lifecycle.systemd.conf.example" \
  && pass "Nginx 模板包含 /portal/" || fail "Nginx 模板缺 /portal/"
grep -Eq 'location[[:space:]]+/uploads/' "$ROOT/deploy/nginx/school-lifecycle.systemd.conf.example" \
  && grep -Eq 'location[[:space:]]+/exports/' "$ROOT/deploy/nginx/school-lifecycle.systemd.conf.example" \
  && pass "Nginx 模板禁止静态附件/导出直读" || fail "Nginx 模板缺 uploads/exports 保护"

# 动态计算 Alembic head；只要求唯一，不写死具体版本号。
heads="$(python3 - "$ROOT/backend/alembic/versions" <<'PY'
import ast, pathlib, sys
revisions, parents = set(), set()
for path in pathlib.Path(sys.argv[1]).glob('*.py'):
    tree = ast.parse(path.read_text(encoding='utf-8-sig'))
    values = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id in {'revision', 'down_revision'}:
                try: values[node.targets[0].id] = ast.literal_eval(node.value)
                except Exception: pass
    rev, down = values.get('revision'), values.get('down_revision')
    if rev: revisions.add(rev)
    if isinstance(down, str): parents.add(down)
    elif isinstance(down, (tuple, list)): parents.update(x for x in down if x)
print('\n'.join(sorted(revisions - parents)))
PY
)"
head_count="$(printf '%s\n' "$heads" | sed '/^$/d' | wc -l | tr -d ' ')"
[ "$head_count" = "1" ] && pass "Alembic 唯一 head=$heads" || fail "Alembic head 数量=$head_count，禁止试点"

echo "== 预检结束：FAIL=$FAIL WARN=$WARN =="
[ "$FAIL" -eq 0 ] || { echo "存在 FAIL 项，禁止导入真实学校数据"; exit 1; }
exit 0
