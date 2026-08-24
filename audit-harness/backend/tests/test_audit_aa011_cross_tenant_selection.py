"""AA-011 audit-only negative: a neighbor tenant cannot inject a foreign selectionCourseId."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core.context import set_current_user, set_tenant
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.modules.academic_affairs.services import academic_affairs_selection_final_service as selection_final


_SUITE_PATH = Path(__file__).resolve().parents[3] / "backend" / "tests" / "test_aa_selection.py"
_SPEC = importlib.util.spec_from_file_location("_aa011_selection_suite", _SUITE_PATH)
_SUITE = importlib.util.module_from_spec(_SPEC)
assert _SPEC and _SPEC.loader
_SPEC.loader.exec_module(_SUITE)

TID = _SUITE.TID
NEIGHBOR_TID = TID + 910011


def _clear_context() -> None:
    set_current_user(None)
    set_tenant(None)


@pytest.mark.usefixtures("db_mode")
def test_aa011_neighbor_tenant_selection_course_id_injection_fails_closed(client, db_mode):
    from app.models import AaSelectionCourse, AaSelectionRecord, StudentProfile

    ids = _SUITE._seed(db_mode)
    admin = _SUITE._hdr(client, "school_admin01")
    _batch_id, selection_course_id = _SUITE._make_open_batch(
        client,
        admin,
        ids["course1"],
        capacity=1,
        teaching_task_id=ids["task1"],
        name="AA-011跨租户注入哨兵",
    )

    db = get_sessionmaker()()
    try:
        neighbor = StudentProfile(
            tenant_id=NEIGHBOR_TID,
            student_no="AA011-NEIGHBOR-001",
            real_name="AA011邻租户学生",
            college_id=int(ids["college"]),
            major_id=int(ids["major"]),
            class_id=int(ids["class"]),
            grade="2024",
            current_stage="ON_CAMPUS",
            student_status="NORMAL",
            status="ACTIVE",
        )
        db.add(neighbor)
        db.commit()
        neighbor_id = int(neighbor.id)
    finally:
        db.close()

    tenant = {"tenantId": str(NEIGHBOR_TID), "tenantCode": "aa011-neighbor-school"}
    user = {
        "studentId": str(neighbor_id),
        "studentNo": "AA011-NEIGHBOR-001",
        "loginName": "AA011-NEIGHBOR-001",
        "realName": "AA011邻租户学生",
        "userType": "STUDENT",
        "currentRoleCode": "STUDENT",
    }
    set_tenant(tenant)
    set_current_user(user)
    try:
        with pytest.raises(AppException) as exc_info:
            selection_final.student_enroll(
                user,
                SimpleNamespace(selectionCourseId=str(selection_course_id)),
            )
        exc = exc_info.value
        assert int(exc.http_status or 0) == 404
        assert "可选课程供给项不存在" in str(exc.message)
    finally:
        _clear_context()

    db = get_sessionmaker()()
    try:
        foreign_supply = db.query(AaSelectionCourse).filter(
            AaSelectionCourse.tenant_id == TID,
            AaSelectionCourse.id == int(selection_course_id),
        ).one()
        assert int(foreign_supply.selected_count or 0) == 0
        assert db.query(AaSelectionRecord).filter(
            AaSelectionRecord.tenant_id == NEIGHBOR_TID,
            AaSelectionRecord.selection_course_id == int(selection_course_id),
            AaSelectionRecord.is_deleted.is_(False),
        ).count() == 0
    finally:
        db.close()
