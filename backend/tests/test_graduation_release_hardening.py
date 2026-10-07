"""毕业设计上线前 P0/P1/P2 硬化关键合同（MySQL/API）。"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

MAIN_TID = 1000000000000000001


def _token(role: str, *, login_name: str = "", college_ids=None, major_ids=None):
    from app.core.security import create_access_token
    payload = {"userId": f"gd-release-{role}-{uuid4().hex[:8]}", "realName": login_name or role, "userType": "TEACHER", "tid": "demo", "tenantId": str(MAIN_TID), "activeContextId": "ctx", "currentRoleCode": role, "clientType": "PC"}
    if login_name: payload["loginName"] = login_name
    if college_ids is not None: payload["collegeIds"] = list(college_ids)
    if major_ids is not None: payload["majorIds"] = list(major_ids)
    return {"Authorization": "Bearer " + create_access_token(payload)}


def _seed_batch_and_mentor(_db_mode, *, teacher_no: str | None = None):
    from app.db.session import get_sessionmaker
    from app.models import GraduationBatch, GraduationMentor
    suffix = uuid4().hex[:10]
    db = get_sessionmaker()()
    try:
        batch = GraduationBatch(tenant_id=MAIN_TID, batch_name=f"release-{suffix}", batch_no=f"REL-{suffix}", grade_year="2026届", planned_count=500, status="ACTIVE")
        db.add(batch); mentor = None
        if teacher_no:
            mentor = GraduationMentor(tenant_id=MAIN_TID, teacher_no=teacher_no, teacher_name=f"导师-{suffix}", college_id="REL-COL-A", college_name="信息工程学院", major_name="软件技术", qualification_status="QUALIFIED", max_capacity=500)
            db.add(mentor)
        db.commit(); db.refresh(batch)
        if mentor: db.refresh(mentor)
        return batch, mentor
    finally: db.close()


def test_approved_topic_sensitive_update_invalidates_review(graduation_client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import GraduationTopic
    batch, _ = _seed_batch_and_mentor(db_mode); db = get_sessionmaker()()
    try:
        topic = GraduationTopic(tenant_id=MAIN_TID, batch_id=batch.id, title="已审核题目", source_type="ADMIN", source="管理员录入", review_status="APPROVED", status="CONFIRMED", requirements="旧要求", capacity=2, selected=0)
        db.add(topic); db.commit(); db.refresh(topic); topic_id = str(topic.id)
    finally: db.close()
    res = graduation_client.put(f"/api/v1/graduation/gd-topics/{topic_id}", headers=_token("GRADUATION_ADMIN"), json={"requirements": "关键事实已变化"})
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["reviewStatus"] == "PENDING_REVIEW" and data["status"] == "PENDING_CONFIRM" and data["assignable"] is False


def test_rejected_mentor_topic_has_formal_resubmit_path(graduation_client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import GraduationTopic
    teacher_no = f"REL-M-{uuid4().hex[:8]}"; batch, mentor = _seed_batch_and_mentor(db_mode, teacher_no=teacher_no); db = get_sessionmaker()()
    try:
        topic = GraduationTopic(tenant_id=MAIN_TID, batch_id=batch.id, title="被驳回题目", source_type="TEACHER", source="教师申报", advisor_name=mentor.teacher_name, advisor_mentor_id=mentor.id, college_id=mentor.college_id, review_status="REJECTED", status="PENDING_CONFIRM", capacity=1, selected=0)
        db.add(topic); db.commit(); db.refresh(topic); topic_id = str(topic.id)
    finally: db.close()
    res = graduation_client.post(f"/api/v1/graduation/gd-topics/{topic_id}/submit-review", headers=_token("GD_MENTOR", login_name=teacher_no))
    assert res.status_code == 200 and res.json()["data"]["reviewStatus"] == "PENDING_REVIEW"


def test_topic_history_is_object_scoped(graduation_client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import GraduationAuditTrail, GraduationTopic
    teacher_no = f"REL-H-{uuid4().hex[:8]}"; batch, mentor = _seed_batch_and_mentor(db_mode, teacher_no=teacher_no); db = get_sessionmaker()()
    try:
        own = GraduationTopic(tenant_id=MAIN_TID, batch_id=batch.id, title="本人题目", source_type="TEACHER", source="教师申报", advisor_name=mentor.teacher_name, advisor_mentor_id=mentor.id, college_id="REL-COL-A", review_status="DRAFT", status="PENDING_CONFIRM", capacity=1)
        other = GraduationTopic(tenant_id=MAIN_TID, batch_id=batch.id, title="他人题目", source_type="ADMIN", source="管理员录入", college_id="REL-COL-B", review_status="DRAFT", status="PENDING_CONFIRM", capacity=1)
        db.add_all([own, other]); db.flush(); db.add_all([GraduationAuditTrail(tenant_id=MAIN_TID, biz_type="TOPIC", biz_id=str(own.id), action="UPDATE", operator="A", occurred_at=datetime.now(timezone.utc)), GraduationAuditTrail(tenant_id=MAIN_TID, biz_type="TOPIC", biz_id=str(other.id), action="UPDATE", operator="B", occurred_at=datetime.now(timezone.utc))]); db.commit(); own_id, other_id = str(own.id), str(other.id)
    finally: db.close()
    res = graduation_client.get("/api/v1/graduation/gd-topics/history", headers=_token("GD_MENTOR", login_name=teacher_no), params={"page": 1, "pageSize": 50})
    assert res.status_code == 200
    ids = {row["topicId"] for row in res.json()["data"]["items"]}
    assert own_id in ids and other_id not in ids


def test_topic_export_is_not_truncated_at_200(graduation_client, db_mode):
    from app.db.session import get_sessionmaker
    from app.models import GraduationTopic
    batch, _ = _seed_batch_and_mentor(db_mode); db = get_sessionmaker()()
    try:
        rows = [GraduationTopic(tenant_id=MAIN_TID, batch_id=batch.id, title=f"批量题目-{i}", source_type="ADMIN", source="管理员录入", review_status="DRAFT", status="PENDING_CONFIRM", capacity=1, selected=0) for i in range(205)]
        db.add_all(rows); db.commit()
    finally: db.close()
    res = graduation_client.post("/api/v1/graduation/gd-topics/export", headers=_token("GRADUATION_ADMIN"), params={"batchId": str(batch.id)})
    assert res.status_code == 200 and res.json()["data"]["rowCount"] == 205


def test_topic_submit_permission_is_exposed_from_existing_create_entitlement(db_mode):
    from app.modules.graduation import routers as _routers  # noqa: F401
    from app.core.graduation_permissions import GRADUATION_PERMISSION_CODES
    from app.core.permissions import has_permission, get_effective_permission_patterns
    user = {"currentRoleCode": "GD_MENTOR", "userType": "TEACHER"}
    assert "graduationDesign.topic.submit" in GRADUATION_PERMISSION_CODES
    assert has_permission(user, "graduationDesign.topic.submit")
    assert "graduationDesign.topic.submit" in get_effective_permission_patterns(user)
