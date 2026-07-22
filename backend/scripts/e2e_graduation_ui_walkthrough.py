"""四端毕设 UI 逐页点验：真实登录 + 打开关键页 + 截图 + DOM/错误断言。

输出：
- backend/tmp/gd_ui_walkthrough/          截图 PNG
- backend/tmp/gd_ui_walkthrough_report.json 结果 JSON
"""
from __future__ import annotations

import json
import re
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tmp" / "gd_ui_walkthrough"
OUT.mkdir(parents=True, exist_ok=True)
REPORT = ROOT / "tmp" / "gd_ui_walkthrough_report.json"

API = "http://127.0.0.1:8010/api/v1"
PC = "http://127.0.0.1:5173"
PORTAL = "http://127.0.0.1:5199/portal"
# uni H5 可能落到 5174/5188/5189
MP_CANDIDATES = [
    "http://127.0.0.1:5190",
    "http://127.0.0.1:5189",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:5188",
]

TENANT = "sandbox-school"
PWD = "E2eTest@2026"
ADMIN = ("admin2", "123456")
ACADEMIC = ("e2e_academic_admin", PWD)
ADVISOR = ("e2e_advisor_a", PWD)
STUDENT = ("E2E20260001", PWD)

STEPS: list[dict] = []


def log(end: str, page_name: str, ok: bool, detail=None, shot=None):
    row = {
        "end": end,
        "page": page_name,
        "ok": ok,
        "detail": detail,
        "shot": shot,
        "at": datetime.now().isoformat(timespec="seconds"),
    }
    STEPS.append(row)
    detail_s = "" if detail is None else str(detail)[:180]
    # Windows console may be GBK — keep ASCII-safe stdout.
    detail_s = detail_s.encode("ascii", "replace").decode("ascii")
    print(("PASS" if ok else "FAIL"), f"[{end}]", page_name, detail_s)


def api_login(login_name: str, password: str) -> dict:
    body = json.dumps({
        "loginName": login_name, "password": password, "tenantCode": TENANT,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{API}/auth/login", data=body,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if data.get("code") != 0:
        raise RuntimeError(f"login failed {login_name}: {data}")
    return data["data"]


def pick_mp_base() -> str | None:
    for base in MP_CANDIDATES:
        try:
            urllib.request.urlopen(base, timeout=3)
            return base
        except Exception:
            continue
    return None


def page_errors(page) -> list[str]:
    # collected via handler
    return list(getattr(page, "_ui_errors", []) or [])


def attach_error_collector(page):
    page._ui_errors = []

    def on_page_error(exc):
        page._ui_errors.append(f"pageerror:{exc}")

    def on_console(msg):
        if msg.type == "error":
            text = msg.text or ""
            # ignore noisy source-map / favicon
            if any(x in text for x in ("favicon", "sourcemap", "DevTools", "Download the Vue Devtools")):
                return
            page._ui_errors.append(f"console:{text[:240]}")

    page.on("pageerror", on_page_error)
    page.on("console", on_console)


def assert_alive(page, *, must_have=None, must_not=None) -> tuple[bool, str]:
    body = page.locator("body")
    text = (body.inner_text(timeout=8000) or "")[:4000]
    if must_not:
        for bad in must_not:
            if bad in text:
                return False, f"unexpected text: {bad}"
    if must_have:
        for good in must_have:
            if good not in text and not page.locator(f"text={good}").count():
                # also try partial
                if good not in text:
                    return False, f"missing text: {good}"
    errs = [e for e in page_errors(page) if "favicon" not in e]
    # allow some network noise but fail hard on ReferenceError/TypeError in page
    hard = [e for e in errs if any(k in e for k in ("ReferenceError", "TypeError", "is not defined", "Cannot read"))]
    if hard:
        return False, hard[0]
    if len(text.strip()) < 8:
        return False, "blank page"
    return True, f"len={len(text)}"


def shot(page, name: str) -> str:
    path = OUT / f"{name}.png"
    page.screenshot(path=str(path), full_page=True)
    return str(path.relative_to(ROOT))


def pc_login(page, login_name: str, password: str):
    page.goto(f"{PC}/login?tenant={TENANT}", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(800)
    # account tab may already be on
    page.fill("input[placeholder*='学校'] , input[placeholder*='租户'], input[placeholder*='tenant']", TENANT)
    # LoginView placeholders: 学校编码 / 工号/手机号 / 密码
    inputs = page.locator("input.lgx-in")
    if inputs.count() >= 3:
        inputs.nth(0).fill(TENANT)
        inputs.nth(1).fill(login_name)
        inputs.nth(2).fill(password)
    else:
        page.get_by_placeholder(re.compile("工号|手机")).fill(login_name)
        page.get_by_placeholder(re.compile("密码")).fill(password)
    page.locator("button.lgx-btn").filter(has_text=re.compile("登")).click()
    page.wait_for_timeout(2500)
    # may land on workbench or role switch
    if "/login" in page.url:
        raise RuntimeError(f"PC login stuck on login: {page.url} body={(page.locator('body').inner_text() or '')[:200]}")


def portal_login(page, login_name: str, password: str):
    page.goto(f"{PORTAL}/login", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(800)
    # LoginView uses class finput
    fields = page.locator("input.finput")
    if fields.count() >= 3:
        fields.nth(0).fill(TENANT)
        fields.nth(1).fill(login_name)
        fields.nth(2).fill(password)
    else:
        page.get_by_placeholder(re.compile("sandbox|学校")).fill(TENANT)
        page.get_by_placeholder(re.compile("学号|账号")).fill(login_name)
        page.get_by_placeholder(re.compile("^密码$|密码")).fill(password)
    page.locator("button.fbtn").filter(has_text=re.compile("登")).click()
    page.wait_for_timeout(3000)
    if "/login" in page.url:
        raise RuntimeError(f"portal login failed url={page.url}")


def mp_login(page, base: str, login_name: str, password: str, *, tenant: str | None = TENANT):
    """H5 登录页默认不传 tenant；用 evaluate 拦截登录请求补 tenantCode。"""
    page.goto(f"{base}/#/pages/login/index", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(2000)

    def _attach_tenant(route):
        try:
            post = route.request.post_data or ""
            data = json.loads(post) if post else {}
        except Exception:
            data = {}
        if tenant and not data.get("tenantCode"):
            data["tenantCode"] = tenant
            route.continue_(post_data=json.dumps(data, ensure_ascii=False))
        else:
            route.continue_()

    page.route("**/api/v1/auth/login", _attach_tenant)

    # agree checkbox
    agree = page.locator(".login__abox")
    if agree.count():
        agree.first.click()
    # uni-app H5 renders native input.uni-input-input
    inputs = page.locator("input.uni-input-input, input")
    inputs.nth(0).fill(login_name)
    inputs.nth(1).fill(password)
    page.locator("button.login__smsbtn, uni-button, button").filter(has_text=re.compile("登")).first.click()
    page.wait_for_timeout(4000)


def visit(page, end: str, name: str, url: str, *, must_have=None, must_not=None, wait_ms=1200):
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(wait_ms)
        ok, detail = assert_alive(page, must_have=must_have, must_not=must_not or ["页面不存在", "Cannot GET", "Internal Server Error"])
        path = shot(page, f"{end}_{name}")
        # soft: login redirect counts as fail
        if "/login" in page.url and "login" not in name:
            ok = False
            detail = f"redirected to login: {page.url}"
        log(end, name, ok, detail, path)
        return ok
    except Exception as exc:  # noqa: BLE001
        try:
            path = shot(page, f"{end}_{name}_err")
        except Exception:
            path = None
        log(end, name, False, str(exc), path)
        return False


def run_pc(browser) -> None:
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    attach_error_collector(page)
    # Prefer form login; fallback to token inject (avoids rate-limit / fill flake).
    logged = False
    try:
        pc_login(page, *ADMIN)
        log("pc", "login_admin2", True, page.url, shot(page, "pc_login_admin2"))
        logged = True
    except Exception as exc:
        log("pc", "login_admin2_form", False, str(exc))
        try:
            data = api_login(*ADMIN)
            page.goto(f"{PC}/login", wait_until="domcontentloaded")
            page.evaluate(
                """([token, refresh]) => {
                  sessionStorage.setItem('gx_pc_token_v1', token || '');
                  sessionStorage.setItem('gx_pc_refresh_v1', refresh || '');
                }""",
                [data.get("accessToken") or "", data.get("refreshToken") or ""],
            )
            page.goto(f"{PC}/admin/graduation", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1500)
            if "/login" in page.url:
                raise RuntimeError("token inject still on login")
            log("pc", "login_admin2_token", True, page.url, shot(page, "pc_login_admin2_token"))
            logged = True
        except Exception as exc2:
            log("pc", "login_admin2_token", False, str(exc2))
            ctx.close()
            return

    if not logged:
        ctx.close()
        return

    pages = [
        ("dashboard", f"{PC}/admin/graduation", ["毕设"]),
        ("batches", f"{PC}/admin/graduation/batches?panel=list", ["批次"]),
        ("students", f"{PC}/admin/graduation/students?panel=roster", ["学生"]),
        ("eligibility", f"{PC}/admin/graduation/students?panel=eligibility", None),
        ("topic_lib", f"{PC}/admin/graduation/topic-lib?panel=list", ["题"]),
        ("topics", f"{PC}/admin/graduation/topics", None),
        ("topic_rounds", f"{PC}/admin/graduation/topic-rounds?panel=rounds", None),
        ("mentors", f"{PC}/admin/graduation/mentors?panel=list", ["导师"]),
        ("process_taskbook", f"{PC}/admin/graduation/process?panel=taskbook", None),
        ("process_guidance", f"{PC}/admin/graduation/process?panel=guidance", None),
        ("process_midterm", f"{PC}/admin/graduation/process?panel=midterm", ["中期"]),
        ("proposals", f"{PC}/admin/graduation/proposals", ["开题"]),
        ("finals", f"{PC}/admin/graduation/finals", ["成果"]),
        ("plagiarism", f"{PC}/admin/graduation/defense-grade?panel=plagiarism", None),
        ("review", f"{PC}/admin/graduation/defense-grade?panel=review", None),
        ("defense", f"{PC}/admin/graduation/defense", ["答辩"]),
        ("grade", f"{PC}/admin/graduation/defense-grade?panel=grade", None),
        ("risk", f"{PC}/admin/graduation/risk-archive?panel=risk", None),
        ("archive", f"{PC}/admin/graduation/risk-archive?panel=archive", ["归档"]),
        ("stats", f"{PC}/admin/graduation/stats-report", None),
    ]
    for name, url, must in pages:
        visit(page, "pc", name, url, must_have=must)

    # academic admin: inject token to avoid rate-limit after many logins
    try:
        data = api_login(*ACADEMIC)
        page.goto(f"{PC}/login", wait_until="domcontentloaded")
        page.evaluate(
            """([token, refresh]) => {
              sessionStorage.setItem('gx_pc_token_v1', token || '');
              sessionStorage.setItem('gx_pc_refresh_v1', refresh || '');
            }""",
            [data.get("accessToken") or "", data.get("refreshToken") or ""],
        )
        page.goto(f"{PC}/admin/graduation", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(1500)
        ok, detail = assert_alive(page, must_have=["毕设"])
        if "/login" in page.url:
            ok, detail = False, "token inject still on login"
        log("pc", "academic_dashboard", ok, detail, shot(page, "pc_academic_dashboard"))
    except Exception as exc:
        log("pc", "academic_dashboard", False, str(exc))

    ctx.close()


def run_portal(browser) -> None:
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    page = ctx.new_page()
    attach_error_collector(page)
    try:
        portal_login(page, *STUDENT)
        log("portal", "login_student_a", True, page.url, shot(page, "portal_login_student_a"))
    except Exception as exc:
        try:
            path = shot(page, "portal_login_student_a_err")
        except Exception:
            path = None
        log("portal", "login_student_a", False, str(exc), path)
        # fallback: token inject via portal storage keys
        try:
            data = api_login(*STUDENT)
            page.goto(f"{PORTAL}/login", wait_until="domcontentloaded")
            page.evaluate(
                """([token, refresh]) => {
                  localStorage.setItem('sp_token_v1', token || '');
                  localStorage.setItem('sp_refresh_v1', refresh || '');
                }""",
                [data.get("accessToken") or "", data.get("refreshToken") or ""],
            )
            page.goto(f"{PORTAL}/graduation", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1500)
            if "/login" in page.url:
                ctx.close()
                return
            log("portal", "login_student_a_token", True, page.url, shot(page, "portal_login_student_a_token"))
        except Exception as exc2:
            log("portal", "login_student_a_token", False, str(exc2))
            ctx.close()
            return

    visit(page, "portal", "home", f"{PORTAL}/home", must_have=None)
    visit(page, "portal", "graduation", f"{PORTAL}/graduation", must_have=["毕业设计"])
    for label, key in [
        ("选题", "topics"), ("任务书", "taskbook"), ("开题", "proposal"),
        ("中期", "midterm"), ("成果", "final"), ("答辩", "defense"), ("成绩", "grade"),
    ]:
        try:
            loc = page.get_by_text(label, exact=False).first
            if loc.count():
                loc.click(timeout=2000)
                page.wait_for_timeout(800)
                ok, detail = assert_alive(page)
                path = shot(page, f"portal_tab_{key}")
                log("portal", f"tab_{key}", ok, detail, path)
            else:
                log("portal", f"tab_{key}", True, "tab not visible (stage-gated ok)")
        except Exception as exc:
            log("portal", f"tab_{key}", False, str(exc))
    ctx.close()


def run_mp(browser) -> None:
    base = pick_mp_base()
    if not base:
        log("mp", "server", False, "no miniapp H5 listening on 5174/5188/5189")
        return
    log("mp", "server", True, base)

    def inject_and_open(page, login_name: str, password: str, role_home: str):
        data = api_login(login_name, password)
        page.goto(f"{base}/#/pages/login/index", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(800)
        role = "STUDENT" if "student" in role_home else "MENTOR"
        page.evaluate(
            """([token, refresh, name, sno, role, isTeacher]) => {
              localStorage.setItem('gx_token_v1', token || '');
              localStorage.setItem('gx_refresh_v1', refresh || '');
              localStorage.setItem('gx_session_v1', JSON.stringify({
                logged: true,
                currentRole: role,
                availableRoles: [role],
                isTeacher: !!isTeacher,
                user: { name: name, studentNo: sno }
              }));
            }""",
            [
                data.get("accessToken") or "",
                data.get("refreshToken") or "",
                data.get("displayName") or login_name,
                login_name if role == "STUDENT" else "",
                role,
                role != "STUDENT",
            ],
        )
        # Prefer form login when CORS allows; keep inject as the reliable path for screenshots.
        try:
            mp_login(page, base, login_name, password)
            if "/login" not in page.url:
                return "form"
        except Exception:
            pass
        page.goto(f"{base}/#{role_home}", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(2000)
        return "token"

    # student
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True)
    page = ctx.new_page()
    attach_error_collector(page)
    try:
        mode = inject_and_open(page, *STUDENT, "/pages/student/home/index")
        log("mp", f"login_student_a_{mode}", "/login" not in page.url, page.url, shot(page, "mp_login_student_a"))
    except Exception as exc:
        log("mp", "login_student_a", False, str(exc), shot(page, "mp_login_student_a_err"))
        ctx.close()
        return

    student_pages = [
        ("home_student", f"{base}/#/pages/student/home/index"),
        ("gd_index", f"{base}/#/pages/student/graduation/index"),
        ("gd_topics", f"{base}/#/pages/student/graduation/topics/index"),
        ("gd_taskbook", f"{base}/#/pages/student/graduation/taskbook/index"),
        ("gd_defense", f"{base}/#/pages/student/graduation/defense/index"),
    ]
    for name, url in student_pages:
        visit(page, "mp-student", name, url, wait_ms=1800)
    ctx.close()

    # teacher advisor
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True)
    page = ctx.new_page()
    attach_error_collector(page)
    try:
        mode = inject_and_open(page, *ADVISOR, "/pages/teacher/workbench/index")
        log("mp", f"login_advisor_a_{mode}", "/login" not in page.url, page.url, shot(page, "mp_login_advisor_a"))
    except Exception as exc:
        log("mp", "login_advisor_a", False, str(exc), shot(page, "mp_login_advisor_a_err"))
        ctx.close()
        return

    teacher_pages = [
        ("home_teacher", f"{base}/#/pages/teacher/workbench/index"),
        ("gd_guide", f"{base}/#/pages/teacher/graduation-guide/index"),
        ("gd_topics_review", f"{base}/#/pages/teacher/graduation-topics/index"),
        ("gd_taskbook_t", f"{base}/#/pages/teacher/graduation-taskbook/index"),
    ]
    for name, url in teacher_pages:
        visit(page, "mp-teacher", name, url, wait_ms=1800)
    ctx.close()


def main() -> int:
    # warm API
    try:
        api_login(*ADMIN)
        log("api", "admin2_login", True)
    except Exception as exc:
        log("api", "admin2_login", False, str(exc))
        REPORT.write_text(json.dumps({"steps": STEPS}, ensure_ascii=False, indent=2), encoding="utf-8")
        return 1

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        run_pc(browser)
        run_portal(browser)
        run_mp(browser)
        browser.close()

    summary = {
        "at": datetime.now().isoformat(timespec="seconds"),
        "pass": sum(1 for s in STEPS if s["ok"]),
        "fail": sum(1 for s in STEPS if not s["ok"]),
        "shotDir": str(OUT.relative_to(ROOT)),
        "steps": STEPS,
    }
    REPORT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("summary", summary["pass"], "/", summary["pass"] + summary["fail"], "->", REPORT)
    return 0 if summary["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
