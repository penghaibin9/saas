"""教务统计（/academic-affairs/stats/*）端点测试：主流程 + 越权(学生403) + 数据范围(学院跨范围403) + 导出用途校验。

MySQL-only：依赖 db_mode 夹具（TEST_DATABASE_URL）。多 worktree 共用测试库时由总控合并后统一跑。
口径核对施工包 §9 / 融合设计 §4。
"""
from __future__ import annotations

BASE = "/api/v1/academic-affairs"
TID = 1000000000000000001


def _hdr(client, login_name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": login_name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed(db_mode):
    """在 db_mode 干净库上补种教务统计所需数据，返回关键 id。"""
    from app.db.session import get_sessionmaker
    from app.models import (AaRegistration, AaRegistrationBatch, AcademicGrade, AcademicStudent,
                            AcademicWarning, College, Major, StudentProfile, TeacherStudentScope)
    db = get_sessionmaker()()
    soft = College(tenant_id=TID, college_name="软件学院", status="ACTIVE")
    other = College(tenant_id=TID, college_name="机械学院", status="ACTIVE")
    db.add_all([soft, other]); db.flush()
    major = Major(tenant_id=TID, college_id=soft.id, major_name="软件技术", status="ACTIVE")
    db.add(major); db.flush()
    s1 = StudentProfile(tenant_id=TID, student_no="2024001", real_name="钱二",
                        college_id=soft.id, major_id=major.id, student_status="NORMAL", status="ACTIVE")
    s2 = StudentProfile(tenant_id=TID, student_no="2024002", real_name="孙三",
                        college_id=soft.id, major_id=major.id, student_status="NORMAL", status="ACTIVE")
    db.add_all([s1, s2]); db.flush()
    batch = AaRegistrationBatch(tenant_id=TID, batch_name="2024入学注册", register_type="ENROLL",
                               status="OPEN")
    db.add(batch); db.flush()
    db.add_all([
        AaRegistration(tenant_id=TID, batch_id=batch.id, student_id=s1.id, status="REGISTERED"),
        AaRegistration(tenant_id=TID, batch_id=batch.id, student_id=s2.id, status="PENDING_REGISTER"),
    ])
    a1 = AcademicStudent(tenant_id=TID, student_id=s1.id, student_no="2024001", name="钱二",
                         class_name="软件2401", college_name="软件学院")
    db.add(a1); db.flush()
    db.add_all([
        AcademicGrade(tenant_id=TID, acad_student_id=a1.id, course_name="高数", credit_value=4,
                      score=45, pass_status="FAILED", record_status="ACTIVE"),
        AcademicGrade(tenant_id=TID, acad_student_id=a1.id, course_name="英语", credit_value=3,
                      score=80, pass_status="PASSED", record_status="ACTIVE"),
        AcademicWarning(tenant_id=TID, acad_student_id=a1.id, warn_type="MULTI_FAIL", level="HIGH",
                        status="PENDING_HANDLE", record_status="ACTIVE"),
    ])
    # college_admin01 → 软件学院 数据范围
    db.add(TeacherStudentScope(tenant_id=TID, teacher_key="college_admin01", role_code="COLLEGE_ADMIN",
                              scope_type="COLLEGE", ref_value="软件学院", status="ACTIVE"))
    db.commit()
    ids = {"soft": soft.id, "other": other.id, "major": major.id, "s1": s1.id, "s2": s2.id}
    db.close()
    return ids


def _seed_tier1(db_mode):
    """在 `_seed` 基础上补种 Tier1 10 项三级模块（02/03/04/05/06/10/11/12/13/15 号卡）所需数据：
    学籍异动 / 课程 / 教学任务 / 课表冲突 / 毕业资格预审结果。不改动 `_seed` 本身，避免影响既有用例。"""
    import json

    from app.db.session import get_sessionmaker
    from app.models import (AaCourse, AaGraduationAuditBatch, AaGraduationAuditResult,
                            AaScheduleBatch, AaScheduleItem, AaStatusChange, AaTeachingTask)
    ids = _seed(db_mode)
    db = get_sessionmaker()()
    db.add(AaStatusChange(tenant_id=TID, student_id=ids["s1"], change_type="TRANSFER_MAJOR",
                          from_status="NORMAL", to_status="NORMAL", term_code="2025-2026",
                          status="EFFECTIVE"))
    c1 = AaCourse(tenant_id=TID, course_code="TC001", course_name="测试课程A", category="MAJOR_CORE",
                 credit=4, hours_total=64, owner_college_id=ids["soft"], status="ENABLED")
    db.add(c1)
    db.flush()
    db.add(AaTeachingTask(tenant_id=TID, batch_id=1, course_id=c1.id, course_name=c1.course_name,
                          teaching_class_name="测试班", teacher_key="TT001", teacher_name="测试教师",
                          weekly_hours=4, total_hours=64, confirm_at=None, status="ASSIGNED"))
    sb = AaScheduleBatch(tenant_id=TID, term_id=1, batch_name="测试课表批次",
                         college_id=ids["soft"], status="PUBLISHED")
    db.add(sb)
    db.flush()
    db.add(AaScheduleItem(tenant_id=TID, batch_id=sb.id, course_name="测试课程A", class_id=1,
                          class_name="测试班", teacher_key="TT001", teacher_name="测试教师",
                          weekday=1, slot_no=1, week_parity="ALL", status="EFFECTIVE"))
    db.add(AaScheduleItem(tenant_id=TID, batch_id=sb.id, course_name="测试课程B", class_id=1,
                          class_name="测试班", teacher_key="TT002", teacher_name="测试教师2",
                          weekday=1, slot_no=1, week_parity="ALL", status="EFFECTIVE"))
    gb = AaGraduationAuditBatch(tenant_id=TID, batch_name="测试预审批次", grade_year="2026",
                                status="PRECHECKED")
    db.add(gb)
    db.flush()
    db.add(AaGraduationAuditResult(tenant_id=TID, batch_id=gb.id, student_id=ids["s1"],
                                   overall="SYSTEM_ABNORMAL", status="SYSTEM_ABNORMAL",
                                   item_results_json=json.dumps([{"item": "CREDIT", "result": "FAIL"}])))
    db.add(AaGraduationAuditResult(tenant_id=TID, batch_id=gb.id, student_id=ids["s2"],
                                   overall="SYSTEM_PASSED", conclusion="GRADUATED", status="SYSTEM_PASSED",
                                   item_results_json=json.dumps([{"item": "CREDIT", "result": "PASS"}])))
    db.commit()
    ids.update({"course": c1.id, "scheduleBatch": sb.id, "gradBatch": gb.id})
    db.close()
    return ids


# ═══════════ Tier1 10 项三级模块（02/03/04/05/06/10/11/12/13/15 号卡）══════════
# 既有 `/stats/status-change`、`/stats/registration`、`/stats/warning` 三个路径已是总览下钻明细，
# 聚合端点改 `/summary` 后缀，不破坏以上既有用例；其余为全新路径。


def test_tier1_status_change_summary_ok(client, db_mode):
    _seed_tier1(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/stats/status-change/summary", headers=hdr).json()
    assert r["code"] == 0
    assert r["data"]["total"] == 1
    assert any(g["key"] == "TRANSFER_MAJOR" and g["count"] == 1 for g in r["data"]["byType"])


def test_tier1_registration_summary_ok(client, db_mode):
    _seed_tier1(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/stats/registration/summary", headers=hdr).json()
    assert r["code"] == 0
    assert r["data"]["registered"] == 1 and r["data"]["expected"] == 2 and r["data"]["rate"] == 50.0


def test_tier1_course_ok(client, db_mode):
    _seed_tier1(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/stats/course", headers=hdr).json()
    assert r["code"] == 0 and r["data"]["total"] == 1
    assert any(g["key"] == "MAJOR_CORE" for g in r["data"]["byCategory"])
    d = client.get(f"{BASE}/stats/course/detail", headers=hdr).json()
    assert d["code"] == 0 and d["data"]["total"] == 1
    assert d["data"]["items"][0]["courseName"] == "测试课程A"


def test_tier1_teaching_task_ok(client, db_mode):
    _seed_tier1(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/stats/teaching-task", headers=hdr).json()
    assert r["code"] == 0 and r["data"]["expected"] == 1 and r["data"]["confirmed"] == 0
    d = client.get(f"{BASE}/stats/teaching-task/pending", headers=hdr).json()
    assert d["code"] == 0 and d["data"]["total"] == 1


def test_tier1_schedule_conflict_ok(client, db_mode):
    _seed_tier1(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/stats/schedule", headers=hdr).json()
    assert r["code"] == 0 and r["data"]["unresolvedConflicts"] == 1
    d = client.get(f"{BASE}/stats/schedule/conflicts", headers=hdr).json()
    assert d["code"] == 0 and d["data"]["total"] == 1
    assert len(d["data"]["items"][0]["courses"]) == 2


def test_tier1_grade_ok(client, db_mode):
    _seed_tier1(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/stats/grade", headers=hdr).json()
    assert r["code"] == 0 and r["data"]["failRate"] == 50.0
    d = client.get(f"{BASE}/stats/grade/detail", headers=hdr).json()
    assert d["code"] == 0 and d["data"]["total"] == 1
    assert d["data"]["items"][0]["studentNo"] != "2024001"   # 学号脱敏


def test_tier1_warning_summary_ok(client, db_mode):
    _seed_tier1(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/stats/warning/summary", headers=hdr).json()
    assert r["code"] == 0
    assert r["data"]["total"] == 1
    assert any(g["key"] == "HIGH" for g in r["data"]["byLevel"])


def test_tier1_graduation_ok(client, db_mode):
    _seed_tier1(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/stats/graduation", headers=hdr).json()
    assert r["code"] == 0 and r["data"]["passed"] == 1 and r["data"]["expected"] == 2
    assert any(g["key"] == "CREDIT" for g in r["data"]["byAbnormalItem"])
    d = client.get(f"{BASE}/stats/graduation/abnormal", headers=hdr).json()
    assert d["code"] == 0 and d["data"]["total"] == 1
    assert "CREDIT" in d["data"]["items"][0]["abnormalItems"]


def test_tier1_workload_ok(client, db_mode):
    _seed_tier1(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/stats/workload", headers=hdr).json()
    assert r["code"] == 0
    assert any(t["teacherKey"] == "TT001" and t["totalHours"] == 64 for t in r["data"]["ranking"])
    assert "非学校正式工作量核算结果" in r["data"]["disclaimer"]
    d = client.get(f"{BASE}/stats/workload/detail", headers=hdr, params={"teacherKey": "TT001"}).json()
    assert d["code"] == 0 and d["data"]["total"] == 1


def test_tier1_course_college_scope(client, db_mode):
    """04 号卡跨范围测试：学院教务员只能查本院，越院 403（依赖既有 `build_affairs_context` 数据范围解析器）。"""
    ids = _seed_tier1(db_mode)
    hdr = _hdr(client, "college_admin01")
    ok = client.get(f"{BASE}/stats/course", headers=hdr, params={"collegeId": ids["soft"]}).json()
    assert ok["code"] == 0
    denied = client.get(f"{BASE}/stats/course", headers=hdr, params={"collegeId": ids["other"]})
    assert denied.status_code == 403 or denied.json().get("code") == "NO_DATA_SCOPE"


def test_tier1_export_domains_ok(client, db_mode):
    """15 号卡导出报表：domain 选择器覆盖全部 10 项新增维度，均产出真实 xlsx（PK 魔数）。"""
    _seed_tier1(db_mode)
    hdr = _hdr(client, "school_admin01")
    for domain in ("statusChange", "registration", "course", "teachingTask", "schedule",
                   "grade", "warning", "graduation", "workload"):
        r = client.post(f"{BASE}/stats/export", headers=hdr,
                        json={"domain": domain, "purpose": "自动化回归导出测试"})
        assert r.status_code == 200, f"domain={domain} 导出失败：{r.status_code} {r.text[:200]}"
        assert r.content[:2] == b"PK", f"domain={domain} 未产出合法 xlsx"


def test_tier1_student_forbidden(client, db_mode):
    _seed_tier1(db_mode)
    hdr = _hdr(client, "student01")
    for path in ("/stats/course", "/stats/teaching-task", "/stats/schedule", "/stats/grade",
                "/stats/graduation", "/stats/workload", "/stats/status-change/summary",
                "/stats/registration/summary", "/stats/warning/summary"):
        assert client.get(f"{BASE}{path}", headers=hdr).status_code == 403


def test_overview_ok(client, db_mode):
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/stats/overview", headers=hdr).json()
    assert r["code"] == 0
    d = r["data"]
    assert len(d["indicators"]) == 15
    by_key = {i["key"]: i for i in d["indicators"]}
    # 原 4 项占位已核销（2026-07-16）：模块均已建成，指标必须是真实聚合而非"未启用"
    for k in ("scheduleChange", "courseSelection", "exam", "resource"):
        assert by_key[k]["status"] == "OK", f"{k} 不应再返回占位"
        assert by_key[k]["value"] is not None
    # 注册完成率：1 已注册 / 2 应注册 = 50%
    reg = by_key["registration"]
    assert reg["numerator"] == 1 and reg["denominator"] == 2 and reg["rate"] == 50.0
    # 挂科率：1 FAILED / 2 有成绩 = 50%
    assert by_key["failRate"]["numerator"] == 1 and by_key["failRate"]["denominator"] == 2
    # 预警数 = 1
    assert by_key["warning"]["value"] == 1
    assert d["scope"]["all"] is True


def test_filters_ok(client, db_mode):
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/stats/filters", headers=hdr).json()
    assert r["code"] == 0
    assert isinstance(r["data"]["colleges"], list) and len(r["data"]["colleges"]) >= 2
    assert isinstance(r["data"]["majors"], list) and len(r["data"]["majors"]) >= 1


def test_registration_drill_ok(client, db_mode):
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/stats/registration", headers=hdr).json()
    assert r["code"] == 0
    names = [row["studentName"] for row in r["data"]["items"]]
    assert "孙三" in names            # 未注册（PENDING_REGISTER）
    assert "钱二" not in names        # 已注册不在未注册名单
    # 学号脱敏（非明文全串）
    for row in r["data"]["items"]:
        assert row["studentNo"] != "2024002"


def test_warning_drill_ok(client, db_mode):
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    r = client.get(f"{BASE}/stats/warning", headers=hdr).json()
    assert r["code"] == 0
    assert r["data"]["total"] == 1
    assert r["data"]["items"][0]["level"] == "HIGH"


def test_student_forbidden(client, db_mode):
    _seed(db_mode)
    hdr = _hdr(client, "student01")
    for path in ("/stats/overview", "/stats/registration", "/stats/warning"):
        assert client.get(f"{BASE}{path}", headers=hdr).status_code == 403


def test_college_admin_cross_scope_denied(client, db_mode):
    ids = _seed(db_mode)
    hdr = _hdr(client, "college_admin01")
    # 本院（软件学院）→ 允许
    ok = client.get(f"{BASE}/stats/overview", headers=hdr, params={"collegeId": ids["soft"]}).json()
    assert ok["code"] == 0
    # 越院（机械学院）→ 越权拒绝
    denied = client.get(f"{BASE}/stats/overview", headers=hdr, params={"collegeId": ids["other"]})
    body = denied.json()
    assert denied.status_code == 403 or body.get("code") == "NO_DATA_SCOPE"


def test_export_purpose_required(client, db_mode):
    _seed(db_mode)
    hdr = _hdr(client, "school_admin01")
    # 用途缺失 / 过短 → 400（本项目 pydantic 校验错误统一转 400）
    assert client.post(f"{BASE}/stats/export", headers=hdr, json={"purpose": "x"}).status_code == 400
    # 合法导出 → xlsx 字节（zip 魔数 PK）
    r = client.post(f"{BASE}/stats/export", headers=hdr, json={"purpose": "期末教务运行汇报"})
    assert r.status_code == 200
    assert r.content[:2] == b"PK"
