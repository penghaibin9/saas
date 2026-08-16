"""B-W6-4 Selection↔TeachingRoster reconciliation and neighbor-tenant isolation.

The tests reuse the canonical Selection LOCK flow and then validate only the missing
production contracts: LOCKED student set, roster members, member_count and roster_hash
must agree; a different tenant's SelectionRecord must never contaminate the resolver.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from app.core.context import set_current_user, set_tenant
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.modules.academic_affairs.services import (
    academic_affairs_roster_consumer_service as roster_consumer,
    academic_affairs_teaching_class_service as teaching_class_service,
)


_suite_path = Path(__file__).with_name("test_aa_selection.py")
_spec = importlib.util.spec_from_file_location("_w6_roster_selection_suite", _suite_path)
_suite = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_suite)

TID = _suite.TID
NEIGHBOR_TID = TID + 700001


def _activate_tenant(tenant_id: int) -> None:
    set_tenant({"tenantId": str(tenant_id), "tenantCode": f"academic-b-w6-{tenant_id}"})
    set_current_user({
        "userId": "w6-roster-auditor",
        "loginName": "w6-roster-auditor",
        "realName": "W6名单对账",
        "userType": "ADMIN",
        "currentRoleCode": "ACADEMIC_ADMIN",
    })


def _clear_context() -> None:
    set_current_user(None)
    set_tenant(None)


def _lock_one_student(client, db_mode, *, label: str):
    ids = _suite._seed(db_mode)
    admin = _suite._hdr(client, "school_admin01")
    task_id, _ = _suite._ready_tasks(ids)
    batch_id, selection_course_id = _suite._make_open_batch(
        client,
        admin,
        ids["course1"],
        capacity=5,
        teaching_task_id=task_id,
        name=f"W6名单对账-{label}",
    )
    student = _suite._stu_token("选甲", "SEL2401")
    enrolled = client.post(
        f"{_suite.BASE}/selection/student/enroll",
        headers=student,
        json={"selectionCourseId": str(selection_course_id)},
    )
    assert enrolled.status_code == 200, enrolled.text
    closed = client.post(
        f"{_suite.BASE}/selection/batches/{batch_id}/close",
        headers=admin,
    )
    assert closed.status_code == 200, closed.text
    locked = client.post(
        f"{_suite.BASE}/selection/batches/{batch_id}/lock",
        headers=admin,
    )
    assert locked.status_code == 200, locked.text
    assert locked.json()["data"]["status"] == "LOCKED"
    return ids, int(task_id), int(batch_id), int(selection_course_id)


def _selection_locked_ids(db, batch_id: int, selection_course_id: int) -> list[int]:
    from app.models import AaSelectionRecord

    return sorted({
        int(value)
        for (value,) in db.query(AaSelectionRecord.student_id).filter(
            AaSelectionRecord.tenant_id == TID,
            AaSelectionRecord.batch_id == int(batch_id),
            AaSelectionRecord.selection_course_id == int(selection_course_id),
            AaSelectionRecord.status == "LOCKED",
            AaSelectionRecord.is_deleted.is_(False),
        ).all()
    })


def test_w6_selection_lock_roster_hash_count_set_reconcile_fail_closed(client, db_mode):
    ids, task_id, batch_id, selection_course_id = _lock_one_student(
        client, db_mode, label="摘要一致性"
    )
    _activate_tenant(TID)
    db = get_sessionmaker()()
    try:
        from app.models import AaTeachingClassRosterVersion

        locked_ids = _selection_locked_ids(db, batch_id, selection_course_id)
        assert locked_ids == [int(ids["s1"])]
        resolved = roster_consumer.resolve_versioned_roster(db, task_id)
        assert resolved["source"] == "SELECTION_LOCK"
        assert resolved["studentIds"] == locked_ids
        assert int(resolved["memberCount"]) == len(locked_ids)
        assert resolved["rosterHash"] == roster_consumer.roster_hash(locked_ids)

        version = db.query(AaTeachingClassRosterVersion).filter(
            AaTeachingClassRosterVersion.id == int(resolved["rosterVersionId"]),
            AaTeachingClassRosterVersion.tenant_id == TID,
            AaTeachingClassRosterVersion.is_deleted.is_(False),
        ).one()
        assert int(version.member_count or 0) == len(locked_ids)
        assert version.roster_hash == roster_consumer.roster_hash(locked_ids)

        version.member_count = int(version.member_count or 0) + 1
        version.roster_hash = "0" * 64
        db.commit()

        with pytest.raises(AppException) as exc_info:
            roster_consumer.resolve_versioned_roster(db, task_id)
        exc = exc_info.value
        assert exc.code == "APPROVAL_VERSION_CONFLICT"
        assert exc.http_status == 409
        assert "摘要与成员事实不一致" in exc.message
    finally:
        db.close()
        _clear_context()


def test_w6_neighbor_tenant_selection_record_cannot_contaminate_roster(client, db_mode):
    ids, task_id, batch_id, selection_course_id = _lock_one_student(
        client, db_mode, label="邻租户隔离"
    )

    _activate_tenant(TID)
    db = get_sessionmaker()()
    try:
        baseline = teaching_class_service.resolve_teaching_task_roster(db, task_id)
        assert baseline["ready"] is True
        assert baseline["source"] == "SELECTION_LOCK"
        assert baseline["studentIds"] == [int(ids["s1"])]
        baseline = dict(baseline)
    finally:
        db.close()
        _clear_context()

    _activate_tenant(NEIGHBOR_TID)
    db = get_sessionmaker()()
    try:
        from app.models import AaSelectionRecord, StudentProfile

        neighbor = StudentProfile(
            tenant_id=NEIGHBOR_TID,
            student_no="W6-NEIGHBOR-001",
            real_name="邻租户学生",
            college_id=int(ids["college"]),
            major_id=int(ids["major"]),
            class_id=int(ids["class"]),
            grade="2024",
            student_status="NORMAL",
            status="ACTIVE",
        )
        db.add(neighbor)
        db.flush()
        db.add(AaSelectionRecord(
            tenant_id=NEIGHBOR_TID,
            batch_id=int(batch_id),
            selection_course_id=int(selection_course_id),
            course_id=int(ids["course1"]),
            course_name="邻租户污染哨兵",
            credit=2,
            student_id=int(neighbor.id),
            student_no=neighbor.student_no,
            student_name=neighbor.real_name,
            status="LOCKED",
        ))
        db.commit()
        neighbor_id = int(neighbor.id)
    finally:
        db.close()
        _clear_context()

    _activate_tenant(TID)
    db = get_sessionmaker()()
    try:
        after = teaching_class_service.resolve_teaching_task_roster(db, task_id)
        assert after == baseline, {"baseline": baseline, "after": after, "neighborId": neighbor_id}
        resolved = roster_consumer.resolve_versioned_roster(db, task_id)
        assert resolved["studentIds"] == [int(ids["s1"])]
        assert int(resolved["memberCount"]) == 1
        assert resolved["rosterHash"] == roster_consumer.roster_hash([int(ids["s1"])])
        assert neighbor_id not in resolved["studentIds"]
    finally:
        db.close()
        _clear_context()
