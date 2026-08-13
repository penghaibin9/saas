"""D6：LOCKED 人工调整必须在真实 MySQL 同步推进 TeachingRoster 版本。"""
from __future__ import annotations

import importlib.util
from pathlib import Path


_suite_path = Path(__file__).with_name("test_aa_selection.py")
_spec = importlib.util.spec_from_file_location("_d6_selection_suite", _suite_path)
_suite = importlib.util.module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_suite)


def _current_roster(task_id: int):
    from app.db.session import get_sessionmaker
    from app.models import AaTeachingClass, AaTeachingClassRosterVersion

    db = get_sessionmaker()()
    try:
        teaching_class = db.query(AaTeachingClass).filter(
            AaTeachingClass.tenant_id == _suite.TID,
            AaTeachingClass.teaching_task_id == int(task_id),
            AaTeachingClass.is_deleted.is_(False),
        ).one()
        version = db.query(AaTeachingClassRosterVersion).filter(
            AaTeachingClassRosterVersion.id == int(teaching_class.current_roster_version_id),
            AaTeachingClassRosterVersion.tenant_id == _suite.TID,
            AaTeachingClassRosterVersion.is_deleted.is_(False),
        ).one()
        return {
            "teachingClassId": int(teaching_class.id),
            "versionId": int(version.id),
            "versionNo": int(version.version_no),
            "status": str(version.status),
            "memberCount": int(version.member_count or 0),
            "sourceType": str(version.source_type),
        }
    finally:
        db.close()


def _version(version_id: int):
    from app.db.session import get_sessionmaker
    from app.models import AaTeachingClassRosterVersion

    db = get_sessionmaker()()
    try:
        row = db.query(AaTeachingClassRosterVersion).filter(
            AaTeachingClassRosterVersion.id == int(version_id),
            AaTeachingClassRosterVersion.tenant_id == _suite.TID,
            AaTeachingClassRosterVersion.is_deleted.is_(False),
        ).one()
        return {"status": str(row.status), "memberCount": int(row.member_count or 0)}
    finally:
        db.close()


def test_locked_adjustment_creates_new_empty_selection_roster_version(client, db_mode):
    ids = _suite._seed(db_mode)
    admin = _suite._hdr(client, "school_admin01")
    task_id, _ = _suite._ready_tasks(ids)
    batch_id, selection_course_id = _suite._make_open_batch(
        client,
        admin,
        ids["course1"],
        teaching_task_id=task_id,
        name="D6锁定名单调整回归",
    )
    student = _suite._stu_token("选甲", "SEL2401")
    record_id = client.post(
        f"{_suite.BASE}/selection/student/enroll",
        headers=student,
        json={"selectionCourseId": str(selection_course_id)},
    ).json()["data"]["recordId"]
    assert client.post(
        f"{_suite.BASE}/selection/batches/{batch_id}/close", headers=admin
    ).status_code == 200
    locked = client.post(
        f"{_suite.BASE}/selection/batches/{batch_id}/lock", headers=admin
    )
    assert locked.status_code == 200, locked.text

    before = _current_roster(task_id)
    assert before["status"] == "LOCKED"
    assert before["memberCount"] == 1
    assert before["sourceType"] == "SELECTION_LOCK"

    adjusted = client.post(
        f"{_suite.BASE}/selection/records/{record_id}/adjust",
        headers=admin,
        json={"reason": "学生转专业需调整正式名单"},
    )
    assert adjusted.status_code == 200, adjusted.text
    assert adjusted.json()["data"]["status"] == "DROPPED"

    after = _current_roster(task_id)
    assert after["teachingClassId"] == before["teachingClassId"]
    assert after["versionId"] != before["versionId"]
    assert after["versionNo"] == before["versionNo"] + 1
    assert after["status"] == "LOCKED"
    assert after["memberCount"] == 0
    assert after["sourceType"] == "SELECTION_LOCK"
    assert _version(before["versionId"])["status"] == "SUPERSEDED"
