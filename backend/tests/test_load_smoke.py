"""1000 人级试点基础并发冒烟（TestClient + 线程池，无重依赖）。
目标：发现 500 / 越权 / 并发冲突 / 明显慢接口——不伪造正式压测报告。
运行：cd backend && pytest tests/test_load_smoke.py -q
"""
from __future__ import annotations

import statistics
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

MAIN = 1000000000000000001
DEMO = 1000000000000000003
WORKERS = 12  # 普通开发机可承受的并发


# ═══════════ 夹具：模块级种子库（≈220 学生 + 六域数据 + 教师范围） ═══════════

@pytest.fixture(scope="module")
def smoke(tmp_path_factory):
    from app.core.config import settings
    from app.db.session import reset_state
    url = f"sqlite+pysqlite:///{(tmp_path_factory.mktemp('smoke') / 'smoke.db').as_posix()}"
    old_enabled, old_url = settings.DB_ENABLED, settings.DATABASE_URL
    settings.DB_ENABLED, settings.DATABASE_URL = True, url
    reset_state()
    from app.db.base import metadata
    from app.db.session import get_engine, get_sessionmaker
    metadata.create_all(bind=get_engine())

    from datetime import datetime
    from app.models import (AcademicStudent, AcademicWarning, CsLeave, CsServiceStudent,
                            InternshipRecord, StudentContact, StudentProfile,
                            TeacherStudentScope, UnifiedMessage, UnifiedTodo, WeeklyReport)
    db = get_sessionmaker()()
    stu_main = None
    for i in range(1, 221):
        s = StudentProfile(tenant_id=MAIN, student_no=f"LS{i:05d}", real_name=f"冒烟学生{i}",
                           grade="2023", current_stage="INTERNSHIP" if i % 3 == 0 else "ON_CAMPUS",
                           student_status="NORMAL", status="ACTIVE")
        db.add(s)
        if i == 1:
            db.flush()
            stu_main = s
    db.flush()
    db.add(StudentContact(tenant_id=MAIN, student_id=stu_main.id, contact_type="PHONE",
                          contact_value_encrypted="13800009999", is_primary=True))
    cs = CsServiceStudent(tenant_id=MAIN, student_no="LS00001", student_id=stu_main.id,
                          name="冒烟学生1", class_name="软件2301班", risk_level="HIGH",
                          record_status="ACTIVE")
    db.add(cs)
    db.flush()
    db.add(CsLeave(tenant_id=MAIN, cs_student_id=cs.id, leave_type="PERSONAL",
                   reason="冒烟请假", status="PENDING_REVIEW"))
    rec = InternshipRecord(tenant_id=MAIN, student_id=stu_main.id, enterprise_name="冒烟企业",
                           position_name="实习生", advisor_name="冒烟导师", status="ONBOARD",
                           risk_level="MEDIUM")
    db.add(rec)
    db.flush()
    db.add(WeeklyReport(tenant_id=MAIN, internship_id=rec.id, week_number=1,
                        work_content="第一周内容" * 5, status="PENDING_REVIEW"))
    a = AcademicStudent(tenant_id=MAIN, name="冒烟学生1", student_no="LS00001",
                        class_name="软件2301班", gpa=2.1, academic_status="WARNING",
                        warning_level="HIGH")
    db.add(a)
    db.flush()
    db.add(AcademicWarning(tenant_id=MAIN, acad_student_id=a.id, warn_type="GPA", level="HIGH",
                           reason="冒烟预警", status="PENDING_HANDLE", record_status="ACTIVE"))
    db.add(UnifiedTodo(tenant_id=MAIN, source_module="internship", source_biz_id=1,
                       todo_type="SUBMIT", assignee_id=1, student_id=stu_main.id,
                       title="冒烟待办", status="PENDING"))
    db.add(UnifiedMessage(tenant_id=MAIN, receiver_id=1, title="冒烟消息", status="UNREAD"))
    db.add(TeacherStudentScope(tenant_id=MAIN, teacher_key="smokeCounselor", teacher_name="冒烟辅导员",
                               role_code="COUNSELOR", scope_type="CLASS", ref_value="软件2301班",
                               status="ACTIVE"))
    db.commit()
    sid = stu_main.id
    db.close()
    yield {"studentId": sid, "internshipId": rec.id}
    settings.DB_ENABLED, settings.DATABASE_URL = old_enabled, old_url
    reset_state()


def _tok(user_id, name, role, user_type="TEACHER", tenant_id=MAIN, tid="demo", student_no=None):
    from app.core.security import create_access_token
    claims = {"userId": user_id, "realName": name, "userType": user_type, "tid": tid,
              "tenantId": str(tenant_id), "activeContextId": "ctx",
              "currentRoleCode": role, "clientType": "MP"}
    if student_no:
        claims["studentNo"] = student_no
    return {"Authorization": "Bearer " + create_access_token(claims)}


def _stu():
    return _tok("u-smoke-stu", "冒烟学生1", "STUDENT", user_type="STUDENT", student_no="LS00001")


def _teacher():
    return _tok("u-smoke-tea", "王辅导", "COUNSELOR")


def _admin():
    return _tok("u-smoke-adm", "陈校", "SCHOOL_ADMIN", user_type="ADMIN")


def _run(client, jobs, workers=WORKERS):
    """并发执行 [(method, path, headers, json), ...]；返回 (状态计数, 耗时ms列表)。
    非 2xx 时按 path 记录明细，便于定位问题端点。"""
    codes, times, bad = {}, [], {}

    def one(job):
        m, path, headers, body = job
        t0 = time.perf_counter()
        if m == "GET":
            r = client.get(path, headers=headers)
        else:
            r = client.post(path, headers=headers, json=body or {})
        dt = (time.perf_counter() - t0) * 1000
        return r.status_code, dt, path

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for code, dt, path in ex.map(one, jobs):
            codes[code] = codes.get(code, 0) + 1
            times.append(dt)
            if code >= 300:
                bad[f"{code} {path}"] = bad.get(f"{code} {path}", 0) + 1
    if bad:
        print(f"\n[smoke] 非 2xx 明细: {bad}")
    return codes, times


def _report(label, codes, times):
    p50 = statistics.median(times)
    p95 = sorted(times)[int(len(times) * 0.95) - 1]
    print(f"\n[smoke] {label}: n={len(times)} codes={codes} "
          f"p50={p50:.1f}ms p95={p95:.1f}ms max={max(times):.1f}ms")


# ═══════════ 1. 1000 次组合读（学生/教师/管理员真实端点） ═══════════

def test_read_mix_1000(client, smoke):
    stu, tea, adm = _stu(), _teacher(), _admin()
    endpoints = [
        ("GET", "/api/v1/mobile/me/overview", stu, None),
        ("GET", "/api/v1/mobile/orientation/my", stu, None),
        ("GET", "/api/v1/mobile/campus-service/my", stu, None),
        ("GET", "/api/v1/mobile/academic/my", stu, None),
        ("GET", "/api/v1/mobile/internship/my", stu, None),
        ("GET", "/api/v1/mobile/graduation/my", stu, None),
        ("GET", "/api/v1/mobile/employment/my", stu, None),
        ("GET", "/api/v1/mobile/teacher/overview", tea, None),
        ("GET", "/api/v1/mobile/teacher/todos", tea, None),
        ("GET", "/api/v1/mobile/teacher/risk-students", tea, None),
        ("GET", "/api/v1/stats/overview", adm, None),
    ]
    jobs = [endpoints[i % len(endpoints)] for i in range(1000)]
    codes, times = _run(client, jobs)
    _report("read-mix-1000", codes, times)
    assert all(c < 500 for c in codes), f"读请求出现 5xx：{codes}"
    assert codes.get(200, 0) == 1000, f"读请求非全 200：{codes}"


# ═══════════ 2-4. 并发登录 / 学生首页 / 教师工作台 ═══════════

def test_concurrent_login_100(client, smoke):
    jobs = [("POST", "/api/v1/auth/mock-login", None,
             {"loginName": "student01", "password": "demo"}) for _ in range(100)]
    codes, times = _run(client, jobs)
    _report("login-100", codes, times)
    assert all(c < 500 for c in codes), f"登录出现 5xx：{codes}"
    # 登录限流（10 次/分/IP）生效属正确行为：只允许 200 / 429
    assert set(codes) <= {200, 429}, f"登录出现异常状态：{codes}"
    assert codes.get(200, 0) >= 10


def test_concurrent_student_home_100(client, smoke):
    stu = _stu()
    jobs = [("GET", "/api/v1/mobile/me/overview", stu, None) for _ in range(100)]
    codes, times = _run(client, jobs)
    _report("student-home-100", codes, times)
    assert codes == {200: 100}, f"学生首页并发异常：{codes}"


def test_concurrent_teacher_workbench_50(client, smoke):
    tea = _teacher()
    jobs = [("GET", "/api/v1/mobile/teacher/overview", tea, None) for _ in range(50)]
    codes, times = _run(client, jobs)
    _report("teacher-workbench-50", codes, times)
    assert codes == {200: 50}, f"教师工作台并发异常：{codes}"


# ═══════════ 5-6. 并发写：服务申请 / 周报重复提交 ═══════════

def test_concurrent_service_apply_20(client, smoke):
    stu = _stu()
    jobs = [("POST", "/api/v1/mobile/campus-service/apply", stu,
             {"serviceKey": "证明开具", "reason": f"并发冒烟申请事由编号{i}，用于开具证明"})
            for i in range(20)]
    codes, times = _run(client, jobs)
    _report("service-apply-20", codes, times)
    assert all(c < 500 for c in codes), f"服务申请出现 5xx：{codes}"
    assert set(codes) <= {200, 409}, f"服务申请异常状态：{codes}"


def test_concurrent_weekly_duplicate_20(client, smoke):
    stu = _stu()
    body = {"weekNo": 9, "workContent": "并发重复提交冒烟测试周报工作内容，超过十个汉字以通过校验。",
           "harvestContent": "并发重复提交冒烟测试周报收获内容，超过十个汉字以通过校验。"}
    jobs = [("POST", "/api/v1/mobile/internship/weekly", stu, body) for _ in range(20)]
    codes, times = _run(client, jobs)
    _report("weekly-dup-20", codes, times)
    assert all(c < 500 for c in codes), f"周报重复提交出现 5xx：{codes}"
    assert set(codes) <= {200, 409}, f"周报重复提交异常状态：{codes}"
    assert codes.get(200, 0) <= 1, f"同周周报被写入多条：{codes}"
    # 落库校验：第 9 周只允许 1 条
    from app.db.session import get_sessionmaker
    from sqlalchemy import func, select
    from app.models import WeeklyReport
    db = get_sessionmaker()()
    n = db.scalar(select(func.count()).select_from(WeeklyReport).where(
        WeeklyReport.tenant_id == MAIN, WeeklyReport.internship_id == smoke["internshipId"],
        WeeklyReport.week_number == 9, WeeklyReport.is_deleted.is_(False))) or 0
    db.close()
    assert n <= 1, f"第 9 周周报入库 {n} 条（应 ≤1）"


# ═══════════ 7-9. 越权稳定性：401 / 403 / 跨租户 ═══════════

def test_no_token_100(client, smoke):
    jobs = [("GET", "/api/v1/mobile/me/overview", None, None) for _ in range(100)]
    codes, times = _run(client, jobs)
    _report("no-token-100", codes, times)
    assert codes == {401: 100}, f"无令牌访问应稳定 401：{codes}"


def test_student_hits_teacher_50(client, smoke):
    stu = _stu()
    jobs = [("GET", "/api/v1/mobile/teacher/todos", stu, None) for _ in range(50)]
    codes, times = _run(client, jobs)
    _report("student-403-50", codes, times)
    assert codes == {403: 50}, f"学生访问教师接口应稳定 403：{codes}"


def test_cross_tenant_50(client, smoke):
    demo_tea = _tok("u-demo-tea", "演示教师", "COUNSELOR", tenant_id=DEMO, tid="demo-school")
    sid = smoke["studentId"]
    jobs = [("GET", f"/api/v1/mobile/teacher/student/{sid}", demo_tea, None) for _ in range(50)]
    codes, times = _run(client, jobs)
    _report("cross-tenant-50", codes, times)
    assert set(codes) <= {403, 404}, f"跨租户访问应 403/404：{codes}"
    # demo 租户教师的风险学生列表看不到主租户数据
    r = client.get("/api/v1/mobile/teacher/risk-students", headers=demo_tea).json()
    assert r["code"] == 0 and r["data"]["total"] == 0


# ═══════════ 10. 导出限制（限流 + 行数上限存在） ═══════════

def test_export_rate_limit(client, smoke):
    adm = _admin()
    codes = {}
    for i in range(8):
        r = client.post("/api/v1/export/domain/internship", headers=adm,
                        json={"purpose": "并发冒烟导出限制检查"})
        codes[r.status_code] = codes.get(r.status_code, 0) + 1
    print(f"\n[smoke] export-8: codes={codes}")
    assert all(c < 500 for c in codes), f"导出出现 5xx：{codes}"
    assert codes.get(429, 0) >= 3, f"导出限流未生效（每分钟 5 次）：{codes}"
