"""新学校开局向导测试（P13-A）：dry-run 不落库 / confirm 落库 / 行号错误 /
跨租户拒绝 / 重复跳过 / atomic 回滚 / 空数据不 500 / 学生教师 403 / 教师初始密码。"""
from __future__ import annotations

MAIN = 1000000000000000001
DEMO = 1000000000000000003


def _token(user_type, tenant_id=MAIN, role="SCHOOL_ADMIN"):
    from app.core.security import create_access_token
    return {"Authorization": "Bearer " + create_access_token({
        "userId": "u-op", "realName": "王管理", "userType": user_type,
        "tid": "demo", "tenantId": str(tenant_id), "activeContextId": "ctx",
        "currentRoleCode": role, "clientType": "PC"})}


def _admin(tenant_id=MAIN):
    return _token("SCHOOL_ADMIN", tenant_id)


def _platform():
    return _token("PLATFORM_OP", MAIN, role="PLATFORM_OP")


def _stu():
    return _token("STUDENT", MAIN, role="STUDENT")


_GOOD_BODY = {
    "tenantId": str(MAIN),
    "colleges": [{"name": "软件学院", "code": "RJ"}],
    "majors": [{"collegeName": "软件学院", "name": "软件工程"}],
    "classes": [{"majorName": "软件工程", "name": "软工2401班", "grade": "2024"}],
    "students": [
        {"studentNo": "ONB0001", "name": "钱一", "gender": "男", "className": "软工2401班", "grade": "2024"},
        {"studentNo": "ONB0002", "name": "孙二", "className": "软工2401班"},
    ],
    "teachers": [
        {"loginName": "onb_t1", "name": "周老师", "roleCode": "COUNSELOR",
         "scopeType": "CLASS", "scopeRef": "软工2401班"},
    ],
}


def _count(model_name):
    from app.db.session import get_sessionmaker
    from sqlalchemy import func, select
    import app.models as m
    model = getattr(m, model_name)
    db = get_sessionmaker()()
    try:
        return db.scalar(select(func.count()).select_from(model).where(model.tenant_id == MAIN)) or 0
    finally:
        db.close()


def test_dry_run_not_persisted(client, db_mode):
    before = _count("College")
    r = client.post("/api/v1/onboarding/validate", headers=_admin(), json=_GOOD_BODY).json()
    assert r["code"] == 0 and r["data"]["dryRun"] is True
    assert r["data"]["entities"]["colleges"]["created"] == 1
    assert r["data"]["entities"]["students"]["created"] == 2
    assert _count("College") == before  # 未落库


def test_confirm_persists(client, db_mode):
    r = client.post("/api/v1/onboarding/confirm", headers=_admin(), json=_GOOD_BODY).json()
    assert r["code"] == 0 and r["data"]["dryRun"] is False
    assert r["data"]["entities"]["colleges"]["created"] == 1
    assert r["data"]["entities"]["majors"]["created"] == 1
    assert r["data"]["entities"]["classes"]["created"] == 1
    assert r["data"]["entities"]["students"]["created"] == 2
    assert r["data"]["entities"]["teachers"]["created"] == 1
    assert _count("College") >= 1 and _count("StudentProfile") >= 2
    # 教师初始密码只随响应返回
    assert len(r["data"]["teacherCredentials"]) == 1
    assert r["data"]["teacherCredentials"][0]["loginName"] == "onb_t1"
    assert r["data"]["teacherCredentials"][0]["initialPassword"]


def test_row_level_errors_with_lineno(client, db_mode):
    bad = {"tenantId": str(MAIN), "colleges": [{"name": ""}, {"name": "有效学院"}],
           "students": [{"studentNo": "", "name": "无学号"}]}
    r = client.post("/api/v1/onboarding/validate", headers=_admin(), json=bad).json()
    assert r["code"] == 0
    errs = r["data"]["errors"]
    assert any(e.get("row") == 1 and e.get("entity") == "college" for e in errs)
    assert any(e.get("entity") == "student" and e.get("field") == "studentNo" for e in errs)


def test_cross_tenant_denied(client, db_mode):
    body = dict(_GOOD_BODY)
    body["tenantId"] = str(DEMO)  # 学校管理员在 MAIN，却想写 DEMO
    r = client.post("/api/v1/onboarding/confirm", headers=_admin(tenant_id=MAIN), json=body).json()
    assert r["code"] == 403001


def test_duplicate_import_skipped(client, db_mode):
    client.post("/api/v1/onboarding/confirm", headers=_admin(), json=_GOOD_BODY)
    again = client.post("/api/v1/onboarding/confirm", headers=_admin(), json=_GOOD_BODY).json()
    assert again["code"] == 0
    e = again["data"]["entities"]
    assert e["colleges"]["skipped"] == 1 and e["students"]["skipped"] == 2 and e["teachers"]["skipped"] == 1


def test_atomic_rollback_on_error(client, db_mode):
    before_stu = _count("StudentProfile")
    bad = {"tenantId": str(MAIN), "atomic": True,
           "colleges": [{"name": "回滚学院"}],
           "students": [{"studentNo": "RB1", "name": "有效"}, {"studentNo": "", "name": "缺学号"}]}
    r = client.post("/api/v1/onboarding/confirm", headers=_admin(), json=bad).json()
    assert r["code"] == 422001  # 有错整批回滚
    assert _count("StudentProfile") == before_stu  # 一行都没写


def test_empty_body_not_500(client, db_mode):
    r = client.post("/api/v1/onboarding/validate", headers=_admin(), json={"tenantId": str(MAIN)}).json()
    assert r["code"] == 0
    assert r["data"]["entities"]["colleges"]["created"] == 0


def test_student_and_teacher_forbidden(client, db_mode):
    assert client.post("/api/v1/onboarding/validate", headers=_stu(),
                       json=_GOOD_BODY).json()["code"] == 403001
    t = _token("TEACHER", MAIN, role="COUNSELOR")
    assert client.post("/api/v1/onboarding/confirm", headers=t,
                       json=_GOOD_BODY).json()["code"] == 403001


def test_report_has_success_fail_skip(client, db_mode):
    r = client.post("/api/v1/onboarding/validate", headers=_admin(), json=_GOOD_BODY).json()
    for ent in ("colleges", "majors", "classes", "students", "teachers"):
        keys = r["data"]["entities"][ent]
        assert set(keys.keys()) == {"created", "skipped", "failed"}


def test_requires_login(client):
    assert client.post("/api/v1/onboarding/validate", json=_GOOD_BODY).json()["code"] == 401001
