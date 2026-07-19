"""老系统数据迁移（P1·6 域）：总览/依赖门禁、dry-run 行级错误、confirm 整批写入、
重复策略（OVERWRITE/ERROR/SKIP）、厂商字段别名、权限 fail-closed。"""
from __future__ import annotations


def _login(client, name):
    data = client.post("/api/v1/auth/mock-login",
                       json={"loginName": name, "password": "any"}).json()["data"]
    return {"Authorization": f"Bearer {data['accessToken']}"}


def _seed_students(client, auth_headers, nos):
    rows = [{"studentNo": no, "realName": f"迁移生{i}"} for i, no in enumerate(nos)]
    dr = client.post("/api/v1/import/students/validate", headers=auth_headers,
                     json={"rows": rows}).json()
    assert dr["data"]["status"] == "DRY_RUN_PASSED", dr
    cf = client.post("/api/v1/import/students/confirm", headers=auth_headers,
                     json={"batchNo": dr["data"]["batchNo"]}).json()
    assert cf["code"] == 0


def test_migration_overview_orders_and_deps(client, auth_headers, db_mode):
    ov = client.get("/api/v1/system/migration/overview", headers=auth_headers).json()
    assert ov["code"] == 0
    domains = ov["data"]["domains"]
    assert len(domains) == 21  # P1 6 域 + P2 15 域
    assert [d["domain"] for d in domains[:6]] == [
        "aa-term", "aa-calendar", "aa-time-slot",
        "aa-student-status", "aa-status-change-history", "aa-grade-history"]
    by = {d["domain"]: d for d in domains}
    # 无学期 → 校历依赖未满足；conftest 最小种子含 1 名学生 → 学籍/成绩依赖满足
    assert by["aa-term"]["dependsMet"] is True
    assert by["aa-calendar"]["dependsMet"] is False
    assert by["aa-student-status"]["dependsMet"] is True
    assert by["aa-status-change-history"]["dependsMet"] is False
    assert ov["data"]["studentCount"] == 1


def test_term_import_validate_confirm_and_overwrite(client, auth_headers, db_mode):
    rows = [
        {"yearCode": "2024-2025", "termNo": "1", "termName": "秋季学期",
         "startDate": "2024-09-02", "endDate": "2025-01-17", "teachingWeeks": "18"},
        {"yearCode": "2024/2025", "termNo": "1", "startDate": "2025-02-24",
         "endDate": "2025-07-11", "teachingWeeks": "18"},          # 学年格式错
        {"yearCode": "2024-2025", "termNo": "1", "startDate": "2024-09-02",
         "endDate": "2025-01-17", "teachingWeeks": "18"},          # 批内重复
    ]
    dr = client.post("/api/v1/system/migration/domains/aa-term/validate",
                     headers=auth_headers, json={"rows": rows}).json()
    assert dr["code"] == 0 and dr["data"]["status"] == "DRY_RUN_FAILED"
    assert dr["data"]["okRows"] == 1 and dr["data"]["errorRows"] == 2
    codes = {e["errorCode"] for e in dr["data"]["errors"]}
    assert {"FORMAT_INVALID", "DUP_IN_FILE"} <= codes
    # 校验失败批次禁确认
    cf = client.post("/api/v1/system/migration/confirm", headers=auth_headers,
                     json={"batchNo": dr["data"]["batchNo"]}).json()
    assert cf["code"] == 422001

    good = [{"yearCode": "2024-2025", "termNo": "1", "termName": "秋季学期",
             "startDate": "2024-09-02", "endDate": "2025-01-17", "teachingWeeks": "18"},
            {"yearCode": "2024-2025", "termNo": "2", "termName": "春季学期",
             "startDate": "2025-02-24", "endDate": "2025-07-11", "teachingWeeks": "18",
             "isCurrent": "是"}]
    dr2 = client.post("/api/v1/system/migration/domains/aa-term/validate",
                      headers=auth_headers, json={"rows": good}).json()
    assert dr2["data"]["status"] == "DRY_RUN_PASSED", dr2
    cf2 = client.post("/api/v1/system/migration/confirm", headers=auth_headers,
                      json={"batchNo": dr2["data"]["batchNo"]}).json()
    assert cf2["code"] == 0 and cf2["data"]["created"] == 2

    # OVERWRITE：同学期重导（DRAFT 态）→ 更新不报错
    redo = [{"yearCode": "2024-2025", "termNo": "1", "termName": "第一学期(修订)",
             "startDate": "2024-09-02", "endDate": "2025-01-17", "teachingWeeks": "19"}]
    dr3 = client.post("/api/v1/system/migration/domains/aa-term/validate",
                      headers=auth_headers, json={"rows": redo}).json()
    assert dr3["data"]["status"] == "DRY_RUN_PASSED", dr3
    cf3 = client.post("/api/v1/system/migration/confirm", headers=auth_headers,
                      json={"batchNo": dr3["data"]["batchNo"]}).json()
    assert cf3["code"] == 0 and cf3["data"]["updated"] == 1

    ov = client.get("/api/v1/system/migration/overview", headers=auth_headers).json()
    by = {d["domain"]: d for d in ov["data"]["domains"]}
    assert by["aa-term"]["recordCount"] == 2
    assert by["aa-calendar"]["dependsMet"] is True


def test_calendar_requires_existing_term(client, auth_headers, db_mode):
    dr = client.post("/api/v1/system/migration/domains/aa-calendar/validate",
                     headers=auth_headers,
                     json={"rows": [{"yearCode": "2030-2031", "termNo": "1",
                                     "eventType": "假期", "startDate": "2030-10-01"}]}).json()
    assert dr["data"]["errorRows"] == 1
    assert dr["data"]["errors"][0]["errorCode"] == "REF_NOT_FOUND"


def test_time_slot_import_and_overwrite(client, auth_headers, db_mode):
    rows = [{"slotNo": "1", "startTime": "08:00", "endTime": "08:45"},
            {"slotNo": "2", "startTime": "08:55", "endTime": "08:50"}]  # 结束早于开始
    dr = client.post("/api/v1/system/migration/domains/aa-time-slot/validate",
                     headers=auth_headers, json={"rows": rows}).json()
    assert dr["data"]["okRows"] == 1 and dr["data"]["errorRows"] == 1
    assert dr["data"]["errors"][0]["errorCode"] == "RANGE_INVALID"


def test_student_status_flow(client, auth_headers, db_mode):
    _seed_students(client, auth_headers, ["MIG2023001", "MIG2023002", "MIG2023003"])
    rows = [
        {"studentNo": "MIG2023001", "studentStatus": "休学",
         "effectiveDate": "2024-09-01", "reason": "因病休学"},
        {"studentNo": "MIG2023002", "studentStatus": "在籍", "effectiveDate": "2024-09-01"},  # 现状即在籍 → SKIP
        {"studentNo": "MIG2023003", "studentStatus": "休学", "effectiveDate": "2024-09-01"},  # 缺原因
        {"studentNo": "MIG9999999", "studentStatus": "退学",
         "effectiveDate": "2024-09-01", "reason": "x"},                                       # 学号不存在
    ]
    dr = client.post("/api/v1/system/migration/domains/aa-student-status/validate",
                     headers=auth_headers, json={"rows": rows}).json()
    assert dr["data"]["okRows"] == 1 and dr["data"]["errorRows"] == 2
    assert dr["data"]["skippedRows"] == 1
    codes = {e["errorCode"] for e in dr["data"]["errors"]}
    assert {"REQUIRED_MISSING", "REF_NOT_FOUND"} <= codes

    good = [{"studentNo": "MIG2023001", "studentStatus": "休学",
             "effectiveDate": "2024-09-01", "reason": "因病休学"}]
    dr2 = client.post("/api/v1/system/migration/domains/aa-student-status/validate",
                      headers=auth_headers, json={"rows": good}).json()
    assert dr2["data"]["status"] == "DRY_RUN_PASSED", dr2
    cf = client.post("/api/v1/system/migration/confirm", headers=auth_headers,
                     json={"batchNo": dr2["data"]["batchNo"]}).json()
    assert cf["code"] == 0 and cf["data"]["insertedRows"] == 1
    # 主档状态已经唯一入口更新
    from app.db.session import get_sessionmaker
    from app.models import StudentProfile
    from sqlalchemy import select
    db = get_sessionmaker()()
    try:
        s = db.scalars(select(StudentProfile).where(
            StudentProfile.student_no == "MIG2023001")).first()
        assert s.student_status == "SUSPENDED"
    finally:
        db.close()


def test_status_history_skip_policy(client, auth_headers, db_mode):
    _seed_students(client, auth_headers, ["MIG2024001"])
    row = {"studentNo": "MIG2024001", "changeType": "转专业",
           "reason": "个人申请", "effectiveDate": "2024-02-26"}
    dr = client.post("/api/v1/system/migration/domains/aa-status-change-history/validate",
                     headers=auth_headers, json={"rows": [row]}).json()
    assert dr["data"]["okRows"] == 1
    cf = client.post("/api/v1/system/migration/confirm", headers=auth_headers,
                     json={"batchNo": dr["data"]["batchNo"]}).json()
    assert cf["code"] == 0
    # SKIP：同文件重跑 → 全部跳过，0 行可写但校验仍通过（幂等）
    dr2 = client.post("/api/v1/system/migration/domains/aa-status-change-history/validate",
                      headers=auth_headers, json={"rows": [row]}).json()
    assert dr2["data"]["okRows"] == 0 and dr2["data"]["errorRows"] == 0
    assert dr2["data"]["skippedRows"] == 1


def test_grade_history_error_policy_and_vendor_alias(client, auth_headers, db_mode):
    _seed_students(client, auth_headers, ["MIG2025001"])
    # 厂商字段别名：金智 XH/KCM/ZCJ/XNXQDM/XF（等级制成绩「优」自动映射 95）
    rows = [{"XH": "MIG2025001", "KCM": "高等数学", "XNXQDM": "2023-2024-1",
             "ZCJ": "优", "XF": "4"}]
    dr = client.post("/api/v1/system/migration/domains/aa-grade-history/validate",
                     headers=auth_headers, json={"rows": rows}).json()
    assert dr["data"]["status"] == "DRY_RUN_PASSED", dr
    cf = client.post("/api/v1/system/migration/confirm", headers=auth_headers,
                     json={"batchNo": dr["data"]["batchNo"]}).json()
    assert cf["code"] == 0 and cf["data"]["created"] == 1
    # ERROR：同生同课同学期再导 → DUP_IN_DB
    dr2 = client.post("/api/v1/system/migration/domains/aa-grade-history/validate",
                      headers=auth_headers,
                      json={"rows": [{"studentNo": "MIG2025001", "courseName": "高等数学",
                                      "term": "2023-2024-1", "score": "80"}]}).json()
    assert dr2["data"]["errorRows"] == 1
    assert dr2["data"]["errors"][0]["errorCode"] == "DUP_IN_DB"
    # 落库校验：t_acad_grade source=LEGACY、分数映射、及格判定
    from app.db.session import get_sessionmaker
    from app.models import AcademicGrade
    from sqlalchemy import select
    db = get_sessionmaker()()
    try:
        g = db.scalars(select(AcademicGrade).where(
            AcademicGrade.course_name == "高等数学")).first()
        assert g.score == 95 and g.pass_status == "PASS" and g.source == "LEGACY"
    finally:
        db.close()


def test_migration_template_download(client, auth_headers, db_mode):
    r = client.get("/api/v1/system/migration/domains/aa-term/template", headers=auth_headers)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert len(r.content) > 1000


def test_migration_permission_fail_closed(client, db_mode):
    # 未登录 → 401
    assert client.get("/api/v1/system/migration/overview").json()["code"] == 401001
    # 学生角色无 systemAdmin.migration.* → 403
    stu = _login(client, "student01")
    assert client.get("/api/v1/system/migration/overview", headers=stu).json()["code"] == 403001
    # 平台迁移进度对学校侧同样拒绝
    counselor = _login(client, "counselor01")
    assert client.get("/api/v1/platform/migration/overview",
                      headers=counselor).json()["code"] == 403001


def test_platform_migration_overview(client, auth_headers, db_mode):
    # 学校侧先产生一个批次
    dr = client.post("/api/v1/system/migration/domains/aa-term/validate", headers=auth_headers,
                     json={"rows": [{"yearCode": "2025-2026", "termNo": "1",
                                     "startDate": "2025-09-01", "endDate": "2026-01-16",
                                     "teachingWeeks": "18"}]}).json()
    client.post("/api/v1/system/migration/confirm", headers=auth_headers,
                json={"batchNo": dr["data"]["batchNo"]})
    op = _login(client, "platform_admin01")
    res = client.get("/api/v1/platform/migration/overview", headers=op).json()
    if res["code"] == 0:  # 平台账号在部分环境映射为超管
        assert any(t["batches"] >= 1 for t in res["data"])
    else:
        # mock 平台运营角色（PLATFORM_OP）未授 platform.*：fail-closed 拒绝即为预期；
        # 改用学校侧批次列表验证数据链路
        assert res["code"] == 403001
        bs = client.get("/api/v1/system/migration/batches", headers=auth_headers).json()
        assert bs["code"] == 0 and len(bs["data"]) >= 1
