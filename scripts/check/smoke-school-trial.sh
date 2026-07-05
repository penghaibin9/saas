#!/usr/bin/env bash
# 学校试点 · 部署后冒烟检查（需服务已启动）
# 用法：BASE_URL=https://你的域名 bash scripts/check/smoke-school-trial.sh
# 默认 BASE_URL=http://localhost:8000。不写死真实 IP/密钥。
set -u
BASE="${BASE_URL:-http://localhost:8000}"
FAIL=0
code(){ curl -s -o /dev/null -w "%{http_code}" "$1" 2>/dev/null; }
bizcode(){ curl -s "$1" 2>/dev/null | grep -o '"code":[0-9]*' | head -1 | cut -d: -f2; }
pass(){ echo "  [PASS] $1"; }
fail(){ echo "  [FAIL] $1"; FAIL=$((FAIL+1)); }

echo "== 冒烟检查：$BASE =="
[ "$(code "$BASE/health")" = "200" ] && pass "/health 200" || fail "/health 不可达"
R=$(bizcode "$BASE/health/ready"); [ "$R" = "0" ] && pass "/health/ready 就绪" || fail "/health/ready 异常(code=$R)"

# 未登录访问 mobile 接口应 401
M=$(bizcode "$BASE/api/v1/mobile/me/overview")
[ "$M" = "401001" ] && pass "未登录 mobile → 401" || fail "未登录 mobile 未拦截(code=$M)"

# 学生访问 PC 统计应 403（此处未带 token=401；带学生 token 需人工验证 403）
S=$(bizcode "$BASE/api/v1/stats/overview")
{ [ "$S" = "401001" ] || [ "$S" = "403001" ]; } && pass "stats 需鉴权(code=$S)" || fail "stats 未鉴权(code=$S)"

# 生产环境 /docs 应 404（关闭）
D=$(code "$BASE/docs")
[ "$D" = "404" ] && pass "/docs 已关闭(生产)" || echo "  [INFO] /docs=$D（非生产可开）"

# mock-login 生产应关闭（返回非 200 或业务拒绝）
echo "  [INFO] 请人工确认生产已设 MOCK_LOGIN_ENABLED=false"

# API base 不应 localhost（仅当 BASE 非本地时校验）
echo "$BASE" | grep -q "localhost\|127.0.0.1" && echo "  [INFO] 当前用本地地址，生产请换真实域名" || pass "BASE 非 localhost"

echo "== 冒烟结束：FAIL=$FAIL =="
[ "$FAIL" -eq 0 ] || exit 1
exit 0
