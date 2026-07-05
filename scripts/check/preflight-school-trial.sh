#!/usr/bin/env bash
# 学校试点上线前 · 静态预检（不需要服务运行）
# 用法：bash scripts/check/preflight-school-trial.sh [backend/.env路径]
# 检查：生产开关/密钥强度/CORS/mock-login/前端与小程序 API 地址/nginx 配置/磁盘。
# 不写死任何真实 IP、密码、密钥；只读 .env 与仓库文件。
set -u
ENV_FILE="${1:-backend/.env}"
FAIL=0; WARN=0
pass(){ echo "  [PASS] $1"; }
warn(){ echo "  [WARN] $1"; WARN=$((WARN+1)); }
fail(){ echo "  [FAIL] $1"; FAIL=$((FAIL+1)); }
getv(){ grep -E "^$1=" "$ENV_FILE" 2>/dev/null | tail -1 | cut -d= -f2- | tr -d '\r'; }

echo "== 预检开始：$ENV_FILE =="
if [ ! -f "$ENV_FILE" ]; then
  fail "未找到 $ENV_FILE（生产必须提供 .env）"
else
  [ "$(getv APP_ENV)" = "production" ] && pass "APP_ENV=production" || warn "APP_ENV 非 production"
  DBG="$(getv DEBUG)"; { [ "$DBG" = "false" ] || [ -z "$DBG" ]; } && pass "DEBUG 关闭" || fail "DEBUG 应为 false"
  JS="$(getv JWT_SECRET)$(getv JWT_SECRET_KEY)"
  if echo "$JS" | grep -qi "change-me\|dev-secret"; then fail "JWT_SECRET 仍是默认弱密钥"; \
    elif [ "${#JS}" -ge 32 ]; then pass "JWT_SECRET 长度充足"; else warn "JWT_SECRET 建议≥32位"; fi
  CORS="$(getv CORS_ORIGINS)"
  if [ -z "$CORS" ] || [ "$CORS" = "*" ]; then fail "CORS_ORIGINS 不能为空或 *（生产收敛到真实域名）"; else pass "CORS 已收敛"; fi
  ML="$(getv MOCK_LOGIN_ENABLED)"
  if [ "$ML" = "true" ]; then fail "MOCK_LOGIN_ENABLED=true（正式客户前必须关闭）"; else pass "mock-login 未开启"; fi
  SMS="$(getv SMS_ENABLED)"
  [ "$SMS" = "true" ] && { getv SMS_ACCESS_KEY_ID | grep -q . && pass "SMS 已配置" || warn "SMS_ENABLED=true 但未配密钥"; } || pass "SMS 默认关闭（占位）"
fi

# 前端/小程序 API 地址不应指向 localhost（构建产物或 env 文件）
grep -RIl "localhost:8000\|127.0.0.1:8000" frontend/.env* miniapp/.env* 2>/dev/null | while read -r f; do warn "API 地址仍是 localhost：$f"; done

# nginx 配置存在
ls deploy/nginx/*.conf* >/dev/null 2>&1 && pass "存在 nginx 配置模板" || warn "未见 nginx 配置模板"

# 磁盘空间
AVAIL=$(df -Pk . 2>/dev/null | awk 'NR==2{print int($4/1024/1024)}')
[ -n "$AVAIL" ] && { [ "$AVAIL" -ge 5 ] && pass "磁盘可用 ${AVAIL}GB" || warn "磁盘可用不足 5GB（${AVAIL}GB）"; }

echo "== 预检结束：FAIL=$FAIL WARN=$WARN =="
[ "$FAIL" -eq 0 ] || { echo "存在 FAIL 项，禁止上线"; exit 1; }
exit 0
