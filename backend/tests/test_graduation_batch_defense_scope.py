"""第3批：答辩组 batch_id 隔离 + 学生同批唯一 + 跨批关系拒绝。"""
from __future__ import annotations

from conftest import make_org_class

import uuid

from sqlalchemy import inspect

DG = "/api/v1/graduation/defense-groups"
GD_STU = "/api/v1/graduation/gd-students"
GD_TOPIC = "/api/v1/graduation/gd-topics"
STU = "/api/v1/students"
BATCH = "/api/v1/graduation/batches"


def _uniq(prefix="B3"):
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _batch(graduation_client, h, name=None):
    body = {
        "batchName": name or _uniq("答辩批次"),
        "batchNo": _uniq("BN"),
        "gradeYear": "2026届",
        "plannedCount": 20,
    }
    return graduation_client.post(BATCH, headers=h, json=body).json()["data"]["id"]


def _student(graduation_client, h, no=None, name="生"):
    return graduation_client.post(STU, headers=h, json={
        "studentNo": no or _uniq("S"), "realName": name, "classId": make_org_class(),
    }).json()["data"]["id"]


def _record(graduation_client, h, sid, bid):
    return graduation_client.post(GD_STU, headers=h, json={"studentId": sid, "batchId": bid}).json()["data"]["id"]


def _group(graduation_client, h, bid, name=None, **extra):
    body = {
        "groupName": name or _uniq("组"),
        "batchId": bid,
        "chair": "组长",
        "location": "A101",
        "members": ["评委1"],
        "secretary": "秘书",
    }
    body.update(extra)
    return graduation_client.post(DG, headers=h, params={"batchId": bid}, json=body)


def test_create_requires_batch_id(graduation_client, auth_headers, db_mode):
    h = auth_headers
    bad = graduation_client.post(DG, headers=h, json={"groupName": _uniq("无批组")})
    assert bad.json()["code"] != 0
    assert "批次" in (bad.json().get("message") or "")


def test_same_name_ok_across_batches_dup_in_batch(graduation_client, auth_headers, db_mode):
    h = auth_headers
    b1, b2 = _batch(graduation_client, h), _batch(graduation_client, h)
    name = "第一答辩组"
    a = _group(graduation_client, h, b1, name=name)
    assert a.json()["code"] == 0, a.json()
    b = _group(graduation_client, h, b2, name=name)
    assert b.json()["code"] == 0, b.json()
    dup = _group(graduation_client, h, b1, name=name)
    assert dup.json()["code"] != 0


def test_empty_group_only_shows_in_own_batch(graduation_client, auth_headers, db_mode):
    h = auth_headers
    b1, b2 = _batch(graduation_client, h), _batch(graduation_client, h)
    g1 = _group(graduation_client, h, b1, name=_uniq("空一组")).json()["data"]["id"]
    g2 = _group(graduation_client, h, b2, name=_uniq("空二组")).json()["data"]["id"]

    lst1 = graduation_client.get(DG, headers=h, params={"batchId": b1, "pageSize": 100}).json()
    ids1 = {x["id"] for x in lst1["data"]["items"]}
    assert g1 in ids1
    assert g2 not in ids1

    lst2 = graduation_client.get(DG, headers=h, params={"batchId": b2, "pageSize": 100}).json()
    ids2 = {x["id"] for x in lst2["data"]["items"]}
    assert g2 in ids2
    assert g1 not in ids2


def test_cross_batch_assign_rejected(graduation_client, auth_headers, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import GraduationStudent

    h = auth_headers
    b1, b2 = _batch(graduation_client, h), _batch(graduation_client, h)
    gid = _group(graduation_client, h, b1).json()["data"]["id"]
    sid = _record(graduation_client, h, _student(graduation_client, h, name="跨批生"), b2)

    db = get_sessionmaker()()
    try:
        stu = db.get(GraduationStudent, int(sid))
        stu.stage = "FINAL_CHECK"
        db.commit()
    finally:
        db.close()

    bad = graduation_client.post(f"{DG}/{gid}/assign", headers=h, params={"batchId": b1}, json={"studentIds": [sid]})
    assert bad.json()["code"] != 0
    assert "批次" in (bad.json().get("message") or "")


def test_export_only_current_batch(graduation_client, auth_headers, db_mode):
    h = auth_headers
    b1, b2 = _batch(graduation_client, h), _batch(graduation_client, h)
    _group(graduation_client, h, b1, name=_uniq("导一组"))
    _group(graduation_client, h, b2, name=_uniq("导二组"))
    exp = graduation_client.post(f"{DG}/export", headers=h, params={"batchId": b1}).json()
    assert exp["code"] == 0, exp
    lst = graduation_client.get(DG, headers=h, params={"batchId": b1, "pageSize": 100}).json()
    assert exp["data"]["rowCount"] == lst["data"]["total"]
    assert exp["data"].get("batchId") == str(b1)


def test_same_student_same_batch_once_different_batches_ok(graduation_client, auth_headers, db_mode):
    h = auth_headers
    b1, b2 = _batch(graduation_client, h), _batch(graduation_client, h)
    sid = _student(graduation_client, h, name="多届生")
    r1 = graduation_client.post(GD_STU, headers=h, json={"studentId": sid, "batchId": b1})
    assert r1.json()["code"] == 0, r1.json()
    dup = graduation_client.post(GD_STU, headers=h, json={"studentId": sid, "batchId": b1})
    assert dup.json()["code"] != 0
    r2 = graduation_client.post(GD_STU, headers=h, json={"studentId": sid, "batchId": b2})
    assert r2.json()["code"] == 0, r2.json()


def test_cross_batch_topic_assign_rejected(graduation_client, auth_headers, db_mode):
    h = auth_headers
    b1, b2 = _batch(graduation_client, h), _batch(graduation_client, h)
    sid = _record(graduation_client, h, _student(graduation_client, h, name="选题跨批"), b1)
    tid = graduation_client.post(GD_TOPIC, headers=h, json={
        "title": _uniq("跨批题"), "sourceType": "TEACHER", "advisorName": "李老师",
        "capacity": 1, "submitReview": True, "batchId": b2,
    }).json()["data"]["id"]
    graduation_client.post(f"{GD_TOPIC}/{tid}/review", headers=h, json={"action": "APPROVE"})
    bad = graduation_client.post(f"{GD_STU}/{sid}/assign-topic", headers=h, json={"topicId": tid})
    assert bad.json()["code"] != 0
    assert "批次" in (bad.json().get("message") or "")


def test_schema_has_defense_batch_and_student_uk(graduation_client, auth_headers, db_mode):
    """db_mode create_all 后模型约束已落地（batch_id 列 + 两处唯一约束）。"""
    from app.db.session import get_engine

    insp = inspect(get_engine())
    cols = {c["name"] for c in insp.get_columns("t_gd_defense_group")}
    assert "batch_id" in cols
    def_uks = insp.get_unique_constraints("t_gd_defense_group")
    assert any(
        uk.get("name") == "uk_gd_defense_tenant_batch_name"
        or set(uk.get("column_names") or []) >= {"tenant_id", "batch_id", "group_name"}
        for uk in def_uks
    )
    stu_uks = insp.get_unique_constraints("t_gd_student")
    assert any(
        uk.get("name") == "uk_gd_student_tenant_batch_sid"
        or set(uk.get("column_names") or []) >= {"tenant_id", "batch_id", "student_id"}
        for uk in stu_uks
    )
