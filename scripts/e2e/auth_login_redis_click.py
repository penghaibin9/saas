"""真实浏览器登录验收：管理 PC、平台 PC、学生 PC → FastAPI/MySQL/Redis。"""
from __future__ import annotations

import json
import os
import re
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


def page_error(page: Page) -> str:
    alerts = page.locator('[role="alert"]')
    if alerts.count() and alerts.first.is_visible():
        return (alerts.first.text_content() or "").strip()
    return ""


def click_login(page: Page, label: str, artifact_prefix: str) -> dict:
    button = page.get_by_role("button", name=label, exact=True)
    expect(button).to_be_visible(timeout=10_000)
    expect(button).to_be_enabled(timeout=10_000)
    try:
        with page.expect_response(is_login, timeout=15_000) as info:
            button.click()
        return payload(info.value)
    except Exception as exc:
        page.screenshot(path=str(ARTIFACT_DIR / f"{artifact_prefix}-submit-failure.png"), full_page=True)
        raise AssertionError(
            f"点击“{label}”后未收到登录响应；页面错误={page_error(page)!r}；"
            f"按钮禁用={button.is_disabled()}；当前地址={page.url}"
        ) from exc


def wait_captcha_ready(page: Page, trigger) -> None:
    expect(trigger).to_be_visible(timeout=10_000)
    # 自适应验证码出现后，页面会先自动签发一次；等该次签发彻底结束，
    # 再手动换一张并读取测试环境 devCode，避免两个请求交错覆盖组件状态。
    expect(trigger).to_be_enabled(timeout=10_000)
    image = trigger.locator("img")
    if image.count():
        expect(image).to_be_visible(timeout=10_000)
        expect(image).to_have_attribute("src", re.compile(r"^data:image/png;base64,"), timeout=10_000)


def fresh_captcha(page: Page, trigger, redis_client) -> tuple[str, str]:
    wait_captcha_ready(page, trigger)
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
    # 网络响应到达后，给 Vue/uni-app 一个事件循环把 captchaId 写入组件状态。
    page.wait_for_timeout(150)
    return captcha_id, code


def fill_and_sync(page: Page, selector: str, value: str) -> None:
    field = page.locator(selector)
    field.fill(value)
    expect(field).to_have_value(value)
    field.press("Tab")
    page.wait_for_timeout(150)


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
        result = click_login(page, "进入教师工作台", "teacher-pc-wrong")
        if result.get("code") == 0:
            raise AssertionError("管理 PC 错误密码被接受")
        wrong.append(result.get("bizCode"))

    captcha_input = page.locator("#login-captcha")
    expect(captcha_input).to_be_visible(timeout=10_000)
    trigger = page.locator('button[title="点击换一张"]')
    captcha_id, code = fresh_captcha(page, trigger, redis_client)
    fill_and_sync(page, "#login-captcha", code)
    fill_and_sync(page, "#staff-password", "123456")
    page.screenshot(path=str(ARTIFACT_DIR / "teacher-pc-before-submit.png"), full_page=True)

    result = click_login(page, "进入教师工作台", "teacher-pc")
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
    fill_and_sync(page, 'input[autocomplete="current-password"]', "123456")
    trigger = page.locator('button[title="点击换一张"]')
    captcha_id, code = fresh_captcha(page, trigger, redis_client)
    fill_and_sync(page, "#platform-captcha", code)
    page.screenshot(path=str(ARTIFACT_DIR / "platform-pc-before-submit.png"), full_page=True)

    result = click_login(page, "登录运营平台", "platform-pc")
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
        result = click_login(page, "进入学生服务门户", "student-pc-wrong")
        if result.get("code") == 0:
            raise AssertionError("学生 PC 错误密码被接受")
        wrong.append(result.get("bizCode"))

    captcha_input = page.locator("#student-login-captcha")
    expect(captcha_input).to_be_visible(timeout=10_000)
    trigger = page.locator('button[title="点击换一张"]')
    captcha_id, code = fresh_captcha(page, trigger, redis_client)
    fill_and_sync(page, "#student-login-captcha", code)
    fill_and_sync(page, "#student-password", "123456")
    page.screenshot(path=str(ARTIFACT_DIR / "student-pc-before-submit.png"), full_page=True)

    result = click_login(page, "进入学生服务门户", "student-pc")
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
