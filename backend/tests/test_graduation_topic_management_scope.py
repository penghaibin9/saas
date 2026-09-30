"""GD-P0-01 · 题目管理对象级范围 RED 回归（MySQL 真库）。

基线预期：至少导师跨题修改、学院跨域修改、专业跨域归档、公开题池 PII 投影会失败（RED）。
修复后：全部转 GREEN，且 403 请求前后数据库字段保持不变。
"""
from __future__ import annotations

MAIN_TID = 1000000000000000001
GD_TOPIC = "/api/v1/graduation/gd-topics"


def _role_token(role: str, *, login_name: str = "", college_ids=None, major_ids=None):
    from app.core.security import create_access_token

    payload = {
        "userId": f"gd-p0-01-{role}-{login_name or 'user'}",
        "realName": login_name or role,
        "userType": "TEACHER",
        "tid": "demo",
        "tenantId": str(MAIN_TID),
        "activeContextId": "ctx",
        "currentRoleCode": role,
        "clientType": "PC",
    }
    if login_name:
        payload["loginName"] = login_name
    if college_ids is not None:
        payload["collegeIds"] = list(college_ids)
    if major_ids is not None:
        payload["majorIds"] = list(major_ids)
    return {"Authorization": "Bearer " + create_access_token(payload)}


def _seed_scope_topics(_db_mode):
    from app.db.session import get_sessionmaker
    from app.models import GraduationBatch, GraduationMentor, GraduationTopic

    db = get_sessionmaker()()
    try:
        batch = GraduationBatch(
            tenant_id=MAIN_TID,
            batch_name="GD-P0-01 范围测试批次",
            batch_no="GD-P0-01-SCOPE",
            grade_year="2026届",
            planned_count=20,
            status="ACTIVE",
        )
        mentor_a = GraduationMentor(
            tenant_id=MAIN_TID,
            teacher_no="GD-P0-M-A",
            teacher_name="范围导师A",
            qualification_status="QUALIFIED",
        )
        mentor_b = GraduationMentor(
            tenant_id=MAIN_TID,
            teacher_no="GD-P0-M-B",
            teacher_name="范围导师B",
            qualification_status="QUALIFIED",
        )
        db.add_all([batch, mentor_a, mentor_b])
        db.flush()

        topic_a = GraduationTopic(
            tenant_id=MAIN_TID,
            batch_id=batch.id,
            title="A范围题目",
            source="教师申报",
            source_type="TEACHER",
            advisor_name=mentor_a.teacher_name,
            advisor_mentor_id=mentor_a.id,
            college_id="GD-COL-A",
            major_id="GD-MAJ-A",
            major_name="软件技术A",
            capacity=2,
            selected=0,
            review_status="DRAFT",
            status="PENDING_CONFIRM",
            students_json=[{"name": "隐私学生甲", "studentNo": "GD-PII-001"}],
        )
        topic_b = GraduationTopic(
            tenant_id=MAIN_TID,
            batch_id=batch.id,
            title="B范围题目",
            source="教师申报",
            source_type="TEACHER",
            advisor_name=mentor_b.teacher_name,
            advisor_mentor_id=mentor_b.id,
            college_id="GD-COL-B",
            major_id="GD-MAJ-B",
            major_name="软件技术B",
            capacity=2,
            selected=0,
            review_status="DRAFT",
            status="PENDING_CONFIRM",
        )
        db.add_all([topic_a, topic_b])
        db.commit()
        db.refresh(batch)
        db.refresh(topic_a)
        db.refresh(topic_b)
        return {"batch": str(batch.id), "a": str(topic_a.id), "b": str(topic_b.id)}
    finally:
        db.close()


def _topic_state(topic_id: str):
    from app.db.session import get_sessionmaker
    from app.models import GraduationTopic

    db = get_sessionmaker()()
    try:
        row = db.get(GraduationTopic, int(topic_id))
        return {
            "title": row.title,
            "status": row.status,
            "version": int(row.version or 0),
            "collegeId": str(row.college_id or ""),
            "majorId": str(row.major_id or ""),
            "advisorMentorId": int(row.advisor_mentor_id) if row.advisor_mentor_id else None,
        }
    finally:
        db.close()


def _deep_keys(value):
    if isinstance(value, dict):
        keys = set(value)
        for child in value.values():
            keys.update(_deep_keys(child))
        return keys
    if isinstance(value, list):
        keys = set()
        for child in value:
            keys.update(_deep_keys(child))
        return keys
    return set()


def test_gd_mentor_management_list_and_update_are_owner_scoped(graduation_client, db_mode):
    ids = _seed_scope_topics(db_mode)
    h = _role_token("GD_MENTOR", login_name="GD-P0-M-A")

    listed = graduation_client.get(
        GD_TOPIC,
        headers=h,
        params={"batchId": ids["batch"], "pageSize": 50},
    )
    assert listed.status_code == 200
    listed_ids = {row["id"] for row in listed.json()["data"]["items"]}
    assert ids["a"] in listed_ids
    assert ids["b"] not in listed_ids, "导师管理列表不得看到其他导师题目"

    before = _topic_state(ids["b"])
    denied = graduation_client.put(
        f"{GD_TOPIC}/{ids['b']}",
        headers=h,
        params={"batchId": ids["batch"]},
        json={"title": "导师A越权修改B题目"},
    )
    assert denied.status_code == 403
    assert denied.json().get("code") in (403001, 403002, "NO_PERMISSION", "NO_DATA_SCOPE")
    assert _topic_state(ids["b"]) == before, "403 后题目数据库状态必须完全不变"


def test_gd_college_admin_cannot_update_other_college_topic(graduation_client, db_mode):
    ids = _seed_scope_topics(db_mode)
    h = _role_token("GD_COLLEGE_ADMIN", college_ids=["GD-COL-A"])
    before = _topic_state(ids["b"])

    denied = graduation_client.put(
        f"{GD_TOPIC}/{ids['b']}",
        headers=h,
        params={"batchId": ids["batch"]},
        json={"title": "学院A越权修改学院B题目"},
    )

    assert denied.status_code == 403
    assert _topic_state(ids["b"]) == before


def test_gd_major_admin_cannot_archive_other_major_topic(graduation_client, db_mode):
    ids = _seed_scope_topics(db_mode)
    h = _role_token("GD_MAJOR_ADMIN", major_ids=["GD-MAJ-A"])
    before = _topic_state(ids["b"])

    denied = graduation_client.post(
        f"{GD_TOPIC}/{ids['b']}/archive",
        headers=h,
        params={"batchId": ids["batch"]},
        json={"reason": "跨专业归档应被拒绝"},
    )

    assert denied.status_code == 403
    assert _topic_state(ids["b"]) == before


def test_public_topic_pool_remains_broad_but_contains_no_student_identity(graduation_client, db_mode):
    ids = _seed_scope_topics(db_mode)
    h = _role_token("GD_MENTOR", login_name="GD-P0-M-A")

    response = graduation_client.get("/api/v1/graduation/topics", headers=h)
    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == 0

    rows = payload["data"]["items"]
    row_ids = {row["id"] for row in rows}
    assert ids["a"] in row_ids and ids["b"] in row_ids, "公开题池必须保持跨导师广读"

    forbidden = {"students", "studentNames", "assignedStudents", "studentNo", "userId"}
    for row in rows:
        assert not (_deep_keys(row) & forbidden), f"公开题池出现学生身份字段：{_deep_keys(row) & forbidden}"


def test_graduation_admin_can_manage_cross_owner_topic(graduation_client, db_mode):
    ids = _seed_scope_topics(db_mode)
    h = _role_token("GRADUATION_ADMIN")

    changed = graduation_client.put(
        f"{GD_TOPIC}/{ids['b']}",
        headers=h,
        params={"batchId": ids["batch"]},
        json={"title": "全量管理员合法修改B题目"},
    )

    assert changed.status_code == 200
    assert changed.json()["code"] == 0
    assert _topic_state(ids["b"])["title"] == "全量管理员合法修改B题目"
