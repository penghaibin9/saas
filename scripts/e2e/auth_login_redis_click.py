"""真实浏览器登录验收：Vue 页面 → FastAPI → MySQL 密码校验 → Redis 验证码单次消费。"""
from __future__ import annotations

import json
import os
import traceback
from pathlib import Path

import redis
from playwright.sync_api import Page, expect, sync_playwright

BASE_URL = os.environ.get("E2E_BASE_URL", "http://127.0.0.1:5173").rstrip("/")
REDIS_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/15")
ARTIFACT_DIR = Path(os.environ.get("E2E_ARTIFACT_DIR", "artifacts/auth-login-e2e"))
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)


def _login_response(response) -> bool:
    return response.request.method == "POST" and response.url.endswith("/api/v1/auth/login")


def _captcha_response(response) -> bool:
    return response.request.method == "POST" and response.url.endswith("/api/v1/auth/captcha")


def _click_login(page: Page) -> dict:
    with page.expect_response(_login_response, timeout=10_000) as info:
        page.get_by_role("button", name="进入教师工作台").click()
    payload = info.value.json()
    if not isinstance(payload, dict) or "code" not in payload:
        raise AssertionError(f"登录接口响应结构异常：{payload!r}")
    return payload


def run() -> dict:
    redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    if redis_client.ping() is not True:
        raise AssertionError("Redis PING 失败")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        browser_errors: list[str] = []
        api_failures: list[str] = []
        page.on("pageerror", lambda error: browser_errors.append(str(error)))
        page.on(
            "console",
            lambda message: browser_errors.append(f"console:{message.type}:{message.text}")
            if message.type == "error" else None,
        )
        page.on(
            "response",
            lambda response: api_failures.append(f"{response.status} {response.request.method} {response.url}")
            if "/api/" in response.url and response.status >= 500 else None,
        )
        try:
            page.goto(f"{BASE_URL}/login", wait_until="networkidle", timeout=30_000)
            expect(page.get_by_role("heading", name="教师 / 管理人员登录")).to_be_visible()

            page.get_by_text("切换学校或填写学校编码", exact=True).click()
            page.locator("#staff-tenant").fill("demo-school")
            page.locator("#staff-account").fill("admin")
            page.locator("#staff-password").fill("wrong-password")
            page.get_by_label("我已阅读并同意学校提供的用户协议与隐私政策").check()

            wrong_results = []
            for _ in range(2):
                payload = _click_login(page)
                if payload.get("code") == 0:
                    raise AssertionError("错误密码被意外接受")
                wrong_results.append(payload.get("bizCode"))
                expect(page.get_by_role("alert")).to_be_visible()

            captcha_input = page.locator("#login-captcha")
            if not captcha_input.is_visible():
                payload = _click_login(page)
                if payload.get("bizCode") != "CAPTCHA_REQUIRED":
                    raise AssertionError(f"达到失败阈值后未要求验证码：{payload!r}")
            expect(captcha_input).to_be_visible(timeout=10_000)

            # 主动点击“换一张”，捕获测试环境专用 devCode；真实页面、接口、Redis 链路均不绕过。
            with page.expect_response(_captcha_response, timeout=10_000) as captcha_info:
                page.locator('button[title="点击换一张"]').click()
            captcha_payload = captcha_info.value.json()
            captcha_data = captcha_payload.get("data") if isinstance(captcha_payload, dict) else None
            if not isinstance(captcha_data, dict):
                raise AssertionError(f"验证码接口响应结构异常：{captcha_payload!r}")
            captcha_id = str(captcha_data.get("captchaId") or "")
            captcha_code = str(captcha_data.get("devCode") or "")
            if not captcha_id or len(captcha_code) != 6 or not captcha_code.isdigit():
                raise AssertionError("测试环境未返回可验收的 6 位 devCode")

            redis_keys = list(redis_client.scan_iter(match=f"*auth:captcha:{captcha_id}"))
            if len(redis_keys) != 1:
                raise AssertionError(f"验证码提交前 Redis 中应恰有 1 个挑战键，实际 {redis_keys!r}")

            # 前两次错误密码产生的 401 属于预期安全行为；从此处开始只审计成功登录后的错误。
            browser_errors.clear()
            api_failures.clear()
            captcha_input.fill(captcha_code)
            page.locator("#staff-password").fill("123456")
            success_payload = _click_login(page)
            if success_payload.get("code") != 0:
                raise AssertionError(f"正确账号密码与验证码登录失败：{success_payload!r}")

            page.wait_for_url("**/workbench**", timeout=15_000)
            expect(page.get_by_text("正在加载工作台…", exact=True)).to_be_hidden(timeout=20_000)
            expect(page.locator(".wb-v2")).to_be_visible(timeout=20_000)
            expect(page.get_by_text("工作台数据暂时未能加载", exact=True)).to_have_count(0)
            expect(page.get_by_text("无法加载工作台数据", exact=True)).to_have_count(0)
            page.wait_for_timeout(1_000)
            if api_failures:
                raise AssertionError(f"登录后出现服务端 5xx：{api_failures!r}")
            if browser_errors:
                raise AssertionError(f"登录后出现浏览器错误：{browser_errors!r}")

            token = page.evaluate("sessionStorage.getItem('gx_pc_token_v1') || ''")
            if not token or token.count(".") != 2:
                raise AssertionError("登录成功后 sessionStorage 未写入有效 access token")
            if list(redis_client.scan_iter(match=f"*auth:captcha:{captcha_id}")):
                raise AssertionError("验证码登录成功后仍可在 Redis 中找到，未完成单次消费")

            screenshot = ARTIFACT_DIR / "login-success.png"
            page.screenshot(path=str(screenshot), full_page=True)
            result = {
                "ok": True,
                "url": page.url,
                "wrongAttemptBizCodes": wrong_results,
                "captchaIdPrefix": captcha_id[:10],
                "redisChallengeCreated": True,
                "redisChallengeConsumed": True,
                "tokenStored": True,
                "workbenchReady": True,
                "browserErrors": browser_errors,
                "api5xx": api_failures,
                "screenshot": str(screenshot),
            }
            (ARTIFACT_DIR / "result.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            return result
        except Exception:
            page.screenshot(path=str(ARTIFACT_DIR / "login-failure.png"), full_page=True)
            (ARTIFACT_DIR / "traceback.txt").write_text(traceback.format_exc(), encoding="utf-8")
            raise
        finally:
            browser.close()
            redis_client.close()


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
