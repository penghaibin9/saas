from __future__ import annotations

from pathlib import Path
import textwrap


def replace_once(path: str, old: str, new: str, label: str) -> None:
    file_path = Path(path)
    text = file_path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"{label} target not found")
    file_path.write_text(text.replace(old, new, 1), encoding="utf-8")


def repair_student_401() -> None:
    replace_once(
        "student-portal/src/services/request.js",
        """function authError(message = '登录已失效，请重新登录') {
  const e = new Error(message)
  e.status = 401
  e.code = 401001
  e.biz = true
  return e
}""",
        """function authError(message = '登录已失效，请重新登录', payload = null, status = 401) {
  const e = new Error(message)
  e.status = status
  e.code = 401001
  e.biz = true
  if (payload && typeof payload === 'object') {
    e.bizCode = payload.bizCode
    e.details = payload.details
    e.traceId = payload.traceId
  }
  return e
}""",
        "student authError",
    )
    replace_once(
        "student-portal/src/services/request.js",
        """  if (isUnauthorized(res, payload)) {
    if (auth && !_retried && !path.startsWith('/auth/')) {
      await refreshOnce()
      return request(path, { method, body, auth, params, query, _retried: true })
    }
    clearSession()
    throw authError((payload && payload.message) || undefined)
  }""",
        """  if (isUnauthorized(res, payload)) {
    if (auth && !_retried && !path.startsWith('/auth/')) {
      await refreshOnce()
      return request(path, { method, body, auth, params, query, _retried: true })
    }
    if (auth) clearSession()
    throw authError((payload && payload.message) || undefined, payload, res.status)
  }""",
        "student 401 branch",
    )
    Path("student-portal/tests/auth-error-details.test.mjs").write_text(
        """import test from 'node:test'
import assert from 'node:assert/strict'

test('public login 401 preserves captcha bizCode and details', async () => {
  const previousFetch = globalThis.fetch
  globalThis.fetch = async () => ({
    status: 401,
    json: async () => ({
      code: 401001,
      bizCode: 'CAPTCHA_REQUIRED',
      message: '请输入验证码',
      details: { captchaRequired: true, scene: 'PASSWORD_LOGIN' },
      traceId: 'trace-captcha'
    })
  })
  try {
    const mod = await import(`../src/services/request.js?captcha-test=${Date.now()}`)
    await assert.rejects(
      () => mod.request('/auth/login', { method: 'POST', auth: false, body: { loginName: 'student' } }),
      (error) => {
        assert.equal(error.code, 401001)
        assert.equal(error.bizCode, 'CAPTCHA_REQUIRED')
        assert.deepEqual(error.details, { captchaRequired: true, scene: 'PASSWORD_LOGIN' })
        assert.equal(error.traceId, 'trace-captcha')
        return true
      }
    )
  } finally {
    globalThis.fetch = previousFetch
  }
})
""",
        encoding="utf-8",
    )


def add_platform_seed() -> None:
    path = Path("backend/scripts/_seed_login_accounts_only.py")
    text = path.read_text(encoding="utf-8")
    if "PLATFORM_TID = " not in text:
        text = text.replace(
            "DEMO_TID = 1000000000000000003\n",
            "PLATFORM_TID = 1000000000000000001\n"
            "PLATFORM_CODE = \"platform\"\n"
            "PLATFORM_NAME = \"跃科 SaaS 运营平台\"\n"
            "PLATFORM_SHORT_NAME = \"运营平台\"\n"
            "DEMO_TID = 1000000000000000003\n",
            1,
        )
    if '"platform_admin"' not in text:
        text = text.replace(
            "ACCOUNTS = [\n",
            "ACCOUNTS = [\n"
            "    (PLATFORM_TID, PLATFORM_CODE, PLATFORM_NAME, PLATFORM_SHORT_NAME, "
            "\"platform_admin\", \"平台管理员\", \"PLATFORM_SUPER_ADMIN\"),\n",
            1,
        )
    path.write_text(text, encoding="utf-8")


def write_e2e() -> None:
    content = r'''"""真实浏览器登录验收：管理 PC、平台 PC、学生 PC → FastAPI/MySQL/Redis。"""
from __future__ import annotations

import json
import os
import traceback
from pathlib import Path

import redis
from playwright.sync_api import Page, expect, sync_playwright

BASE_URL = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:5173").rstrip("/")
STUDENT_BASE_URL = os.environ.get("E2E_STUDENT_BASE_URL", "http://127.0.0.1:5199").rstrip("/")
REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/15")
ARTIFACT_DIR = Path(os.environ.get("E2E_ARTIFACT_DIR", "artifacts/auth-login-e2e"))
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)


def is_login(response) -> bool:
    return response.request.method == "POST" and response.url.endswith("/api/v1/auth/login")


def is_captcha(response) -> bool:
    return response.request.method == "POST" and response.url.endswith("/api/v1/auth/captcha")


def payload(response) -> dict:
    value = response.json()
    if not isinstance(value, dict) or "code" not in value:
        raise AssertionError(f"接口响应结构异常：{value!r}")
    return value


def click_login(page: Page, label: str) -> dict:
    with page.expect_response(is_login, timeout=15_000) as info:
        page.get_by_text(label, exact=True).click()
    return payload(info.value)


def fresh_captcha(page: Page, trigger, redis_client) -> tuple[str, str]:
    with page.expect_response(is_captcha, timeout=15_000) as info:
        trigger.click()
    data = payload(info.value).get("data")
    if not isinstance(data, dict):
        raise AssertionError("验证码接口 data 异常")
    captcha_id = str(data.get("captchaId") or "")
    code = str(data.get("devCode") or "")
    if not captcha_id or len(code) != 6 or not code.isdigit():
        raise AssertionError("测试环境未返回 6 位 devCode")
    keys = list(redis_client.scan_iter(match=f"*auth:captcha:{captcha_id}"))
    if len(keys) != 1:
        raise AssertionError(f"验证码提交前 Redis 挑战键异常：{keys!r}")
    return captcha_id, code


def assert_consumed(redis_client, captcha_id: str) -> None:
    if list(redis_client.scan_iter(match=f"*auth:captcha:{captcha_id}")):
        raise AssertionError("验证码提交后仍存在于 Redis")


def teacher_pc(browser, redis_client) -> dict:
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.goto(f"{BASE_URL}/login", wait_until="networkidle", timeout=30_000)
    expect(page.get_by_role("heading", name="教师 / 管理人员登录")).to_be_visible()
    page.get_by_text("切换学校或填写学校编码", exact=True).click()
    page.locator("#staff-tenant").fill("demo-school")
    page.locator("#staff-account").fill("admin")
    page.locator("#staff-password").fill("wrong-password")
    page.get_by_label("我已阅读并同意学校提供的用户协议与隐私政策").check()
    wrong = []
    for _ in range(2):
        result = click_login(page, "进入教师工作台")
        if result.get("code") == 0:
            raise AssertionError("管理 PC 错误密码被接受")
        wrong.append(result.get("bizCode"))
    captcha_input = page.locator("#login-captcha")
    expect(captcha_input).to_be_visible(timeout=10_000)
    captcha_id, code = fresh_captcha(page, page.locator('button[title="点击换一张"]'), redis_client)
    captcha_input.fill(code)
    page.locator("#staff-password").fill("123456")
    result = click_login(page, "进入教师工作台")
    if result.get("code") != 0:
        raise AssertionError(f"管理 PC 登录失败：{result!r}")
    page.wait_for_url("**/workbench**", timeout=15_000)
    token = page.evaluate("sessionStorage.getItem('gx_pc_token_v1') || ''")
    if token.count(".") != 2:
        raise AssertionError("管理 PC 未写入 access token")
    assert_consumed(redis_client, captcha_id)
    page.screenshot(path=str(ARTIFACT_DIR / "teacher-pc-success.png"), full_page=True)
    page.close()
    return {"ok": True, "wrongAttemptBizCodes": wrong}


def platform_pc(browser, redis_client) -> dict:
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.goto(f"{BASE_URL}/platform-login", wait_until="networkidle", timeout=30_000)
    expect(page.get_by_role("heading", name="进入 SaaS 运营平台")).to_be_visible()
    username = page.locator('input[autocomplete="username"]')
    username.fill("platform_admin")
    username.press("Tab")
    expect(page.locator("#platform-captcha")).to_be_visible(timeout=10_000)
    page.locator('input[autocomplete="current-password"]').fill("123456")
    captcha_id, code = fresh_captcha(page, page.locator('button[title="点击换一张"]'), redis_client)
    page.locator("#platform-captcha").fill(code)
    result = click_login(page, "登录运营平台")
    if result.get("code") != 0:
        raise AssertionError(f"平台 PC 登录失败：{result!r}")
    page.wait_for_url("**/admin/platform/overview**", timeout=15_000)
    token = page.evaluate("sessionStorage.getItem('gx_pc_token_v1') || ''")
    if token.count(".") != 2:
        raise AssertionError("平台 PC 未写入 access token")
    assert_consumed(redis_client, captcha_id)
    page.screenshot(path=str(ARTIFACT_DIR / "platform-pc-success.png"), full_page=True)
    page.close()
    return {"ok": True}


def student_pc(browser, redis_client) -> dict:
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.goto(f"{STUDENT_BASE_URL}/portal/login", wait_until="networkidle", timeout=30_000)
    expect(page.get_by_role("heading", name="学生登录")).to_be_visible()
    page.locator("#student-account").fill("student")
    page.locator("#student-password").fill("wrong-password")
    page.get_by_text("切换学校或填写学校编码", exact=True).click()
    page.locator("#student-tenant").fill("demo-school")
    page.get_by_label("我已阅读并同意学校提供的用户协议与隐私政策").check()
    wrong = []
    for _ in range(2):
        result = click_login(page, "进入学生服务门户")
        if result.get("code") == 0:
            raise AssertionError("学生 PC 错误密码被接受")
        wrong.append(result.get("bizCode"))
    captcha_input = page.locator("#student-login-captcha")
    expect(captcha_input).to_be_visible(timeout=10_000)
    captcha_id, code = fresh_captcha(page, page.locator('button[title="点击换一张"]'), redis_client)
    captcha_input.fill(code)
    page.locator("#student-password").fill("123456")
    result = click_login(page, "进入学生服务门户")
    if result.get("code") != 0:
        raise AssertionError(f"学生 PC 登录失败：{result!r}")
    page.wait_for_url("**/portal/home**", timeout=20_000)
    token = page.evaluate("localStorage.getItem('sp_token_v1') || ''")
    if token.count(".") != 2:
        raise AssertionError("学生 PC 未写入 access token")
    assert_consumed(redis_client, captcha_id)
    page.screenshot(path=str(ARTIFACT_DIR / "student-pc-success.png"), full_page=True)
    page.close()
    return {"ok": True, "wrongAttemptBizCodes": wrong}


def run() -> dict:
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    if redis_client.ping() is not True:
        raise AssertionError("Redis PING 失败")
    result = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            result["teacherPc"] = teacher_pc(browser, redis_client)
            result["platformPc"] = platform_pc(browser, redis_client)
            result["studentPc"] = student_pc(browser, redis_client)
        except Exception:
            (ARTIFACT_DIR / "traceback.txt").write_text(traceback.format_exc(), encoding="utf-8")
            raise
        finally:
            browser.close()
            redis_client.close()
    result["ok"] = True
    (ARTIFACT_DIR / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
'''
    Path("scripts/e2e/auth_login_redis_click.py").write_text(textwrap.dedent(content), encoding="utf-8")


def write_workflow() -> None:
    content = r'''name: Auth Login Redis E2E

on:
  push:
    branches: ["**"]
    paths:
      - "backend/app/api/v1/auth.py"
      - "backend/app/services/auth_challenge_service.py"
      - "backend/app/services/auth_service_db.py"
      - "backend/app/core/token_store.py"
      - "backend/scripts/check_production_redis.py"
      - "backend/scripts/_seed_login_accounts_only.py"
      - "backend/tests/test_auth_challenge_service.py"
      - "backend/tests/test_auth_captcha_redis_fail_closed.py"
      - "frontend/src/views/LoginView.vue"
      - "frontend/src/views/PlatformLoginView.vue"
      - "frontend/src/components/auth/LoginCaptcha.vue"
      - "frontend/src/services/http/client.js"
      - "student-portal/src/views/login/LoginView.vue"
      - "student-portal/src/services/request.js"
      - "student-portal/tests/auth-error-details.test.mjs"
      - "scripts/e2e/auth_login_redis_click.py"
      - "deploy/auth-redis.production.env.example"
      - "deploy/start-backend-production.sh"
      - ".github/workflows/auth-login-redis-e2e.yml"
  pull_request:
    branches: ["**"]
    paths:
      - "backend/app/api/v1/auth.py"
      - "backend/app/services/auth_challenge_service.py"
      - "backend/app/services/auth_service_db.py"
      - "backend/app/core/token_store.py"
      - "backend/scripts/check_production_redis.py"
      - "backend/scripts/_seed_login_accounts_only.py"
      - "backend/tests/test_auth_challenge_service.py"
      - "backend/tests/test_auth_captcha_redis_fail_closed.py"
      - "frontend/src/views/LoginView.vue"
      - "frontend/src/views/PlatformLoginView.vue"
      - "frontend/src/components/auth/LoginCaptcha.vue"
      - "frontend/src/services/http/client.js"
      - "student-portal/src/views/login/LoginView.vue"
      - "student-portal/src/services/request.js"
      - "student-portal/tests/auth-error-details.test.mjs"
      - "scripts/e2e/auth_login_redis_click.py"
      - "deploy/auth-redis.production.env.example"
      - "deploy/start-backend-production.sh"
      - ".github/workflows/auth-login-redis-e2e.yml"
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: auth-login-redis-${{ github.event.pull_request.number || github.ref }}
  cancel-in-progress: true

jobs:
  auth-login-redis-e2e:
    name: 三入口真实登录点击 + Redis 单次消费
    runs-on: ubuntu-latest
    timeout-minutes: 40
    services:
      mysql:
        image: mysql:8.0
        env:
          MYSQL_ROOT_PASSWORD: root
          MYSQL_DATABASE: auth_login_e2e
        ports:
          - 3306:3306
        options: >-
          --health-cmd="mysqladmin ping -h 127.0.0.1 -uroot -proot --silent"
          --health-interval=10s
          --health-timeout=5s
          --health-retries=15
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
        options: >-
          --health-cmd="redis-cli ping"
          --health-interval=5s
          --health-timeout=3s
          --health-retries=20
    env:
      APP_ENV: test
      DEPLOYMENT_MODE: local
      DEBUG: "false"
      DB_ENABLED: "true"
      DB_DRIVER: mysql
      DB_HOST: 127.0.0.1
      DB_PORT: "3306"
      DB_NAME: auth_login_e2e
      DB_USER: root
      DB_PASSWORD: root
      TEST_DATABASE_URL: mysql+pymysql://root:root@127.0.0.1:3306/auth_login_e2e?charset=utf8mb4
      REDIS_URL: redis://127.0.0.1:6379/15
      REDIS_KEY_PREFIX: auth-login-e2e
      REDIS_CONNECT_TIMEOUT: "2"
      REDIS_SOCKET_TIMEOUT: "2"
      SCHEDULER_MODE: external
      MOCK_LOGIN_ENABLED: "false"
      JWT_SECRET: auth-login-e2e-only-secret-20260805-at-least-32
      CORS_ORIGINS: http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:5199,http://localhost:5199
      VITE_PROXY_TARGET: http://127.0.0.1:8000
      VITE_API_BASE_URL: http://127.0.0.1:8000
      E2E_BASE_URL: http://127.0.0.1:5173
      E2E_STUDENT_BASE_URL: http://127.0.0.1:5199
      E2E_ARTIFACT_DIR: artifacts/auth-login-e2e
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip
          cache-dependency-path: backend/requirements.txt
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm
          cache-dependency-path: |
            frontend/package-lock.json
            student-portal/package-lock.json
      - name: 安装后端与浏览器依赖
        run: |
          python -m pip install --upgrade pip
          pip install -r backend/requirements.txt
          pip install playwright
          python -m playwright install --with-deps chromium
      - name: 认证、Redis 与学生错误合同专项测试
        run: |
          cd backend
          pytest tests/test_auth_challenge_service.py tests/test_auth_captcha_redis_fail_closed.py -q -p no:warnings
          cd ../student-portal
          npm ci
          npm test
      - name: 验证生产 Redis 缺失时拒绝启动
        run: |
          if env -u REDIS_URL APP_ENV=production DEPLOYMENT_MODE=production python backend/scripts/check_production_redis.py; then
            echo "❌ 未配置 REDIS_URL 时生产闸门错误放行"
            exit 1
          fi
      - name: 验证生产 Redis 启动闸门
        env:
          APP_ENV: production
          DEPLOYMENT_MODE: production
          ALLOW_LOCAL_REDIS_IN_PRODUCTION: "true"
        run: python backend/scripts/check_production_redis.py
      - name: 初始化真实 MySQL 登录账号
        run: |
          python backend/scripts/init_mysql_db.py
          python backend/scripts/_seed_login_accounts_only.py
      - name: 启动 FastAPI
        run: |
          cd backend
          nohup python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 > /tmp/auth-backend.log 2>&1 &
          for i in {1..60}; do
            if curl -fsS http://127.0.0.1:8000/health >/dev/null; then exit 0; fi
            sleep 1
          done
          cat /tmp/auth-backend.log
          exit 1
      - name: 启动管理 PC 与学生 PC
        run: |
          cd frontend
          npm ci
          nohup npm run dev -- --host 127.0.0.1 --port 5173 > /tmp/auth-frontend.log 2>&1 &
          cd ../student-portal
          nohup npm run dev -- --host 127.0.0.1 --port 5199 > /tmp/auth-student.log 2>&1 &
          for target in http://127.0.0.1:5173/login http://127.0.0.1:5199/portal/login; do
            ready=false
            for i in {1..90}; do
              if curl -fsS "$target" >/dev/null; then ready=true; break; fi
              sleep 1
            done
            if [ "$ready" != true ]; then
              cat /tmp/auth-frontend.log || true
              cat /tmp/auth-student.log || true
              exit 1
            fi
          done
      - name: 三入口浏览器真实输入并点击登录
        run: python scripts/e2e/auth_login_redis_click.py
      - name: 失败时输出服务日志
        if: failure()
        run: |
          cat /tmp/auth-backend.log || true
          cat /tmp/auth-frontend.log || true
          cat /tmp/auth-student.log || true
      - name: 上传点击验收证据
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: auth-login-redis-e2e-${{ github.run_id }}
          path: artifacts/auth-login-e2e
          if-no-files-found: warn
          retention-days: 14
'''
    Path(".github/workflows/auth-login-redis-e2e.yml").write_text(textwrap.dedent(content), encoding="utf-8")


def main() -> None:
    repair_student_401()
    add_platform_seed()
    write_e2e()
    write_workflow()
    Path(".github/workflows/_auth-review-repair-once.yml").unlink(missing_ok=True)
    Path("scripts/_auth_review_repair_once.py").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
