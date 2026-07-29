"""课堂考勤只能按稳定教师工号授权，移动端详情不得串场。"""
from pathlib import Path
from types import SimpleNamespace

import pytest


def test_teacher_keys_exclude_real_name():
    from app.modules.academic_affairs.services import academic_affairs_attendance_service as service

    keys = service._teacher_keys({
        "userId": "u_T001",
        "loginName": "T001",
        "realName": "张伟",
        "activeContextId": "ctx_T001",
    })

    assert "T001" in keys
    assert "张伟" not in keys


def test_same_name_teacher_cannot_open_other_session():
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_attendance_service as service

    attendance = SimpleNamespace(teacher_key="T002")
    user = {
        "currentRoleCode": "ACADEMIC_TEACHER",
        "userId": "u_T001",
        "loginName": "T001",
        "realName": "张伟",
    }

    with pytest.raises(AppException) as exc:
        service._check_owner(attendance, user)

    assert exc.value.http_status == 403


def test_missing_teacher_key_is_fail_closed_for_teacher():
    from app.core.exceptions import AppException
    from app.modules.academic_affairs.services import academic_affairs_attendance_service as service

    with pytest.raises(AppException) as exc:
        service._check_owner(
            SimpleNamespace(teacher_key=None),
            {"currentRoleCode": "ACADEMIC_TEACHER", "loginName": "T001"},
        )

    assert exc.value.http_status == 403
    assert "归属待教务处修复" in exc.value.message


def test_admin_can_repair_legacy_session_without_teacher_key():
    from app.modules.academic_affairs.services import academic_affairs_attendance_service as service

    service._check_owner(
        SimpleNamespace(teacher_key=None),
        {"currentRoleCode": "ACADEMIC_ADMIN", "loginName": "aa_admin"},
    )


def test_primary_teacher_key_is_deterministic():
    from app.modules.academic_affairs.services import academic_affairs_attendance_service as service

    user = {
        "userId": "u_T001",
        "loginName": "T001",
        "realName": "张伟",
        "activeContextId": "ctx_other",
    }
    assert service._primary_teacher_key(user) == "T001"


def test_teacher_attendance_page_clears_previous_roster_before_loading_detail():
    root = Path(__file__).resolve().parents[2]
    page = (
        root / "miniapp/src/pages/teacher/academic-affairs/attendance.vue"
    ).read_text(encoding="utf-8")

    assert "this.active = { ...session }" in page
    assert "this.items = []" in page
    assert "this.detailLoading = true" in page
    assert "this.active = null" in page
    assert "名单加载失败，请稍后重试" in page
    assert "v-if=\"detailLoading\"" in page
    assert "提交后教师端不可直接修改" in page
    assert "const confirmed = await this.confirmModal" in page
    assert "classId: this.form.classId ? Number(this.form.classId) : undefined" in page


def test_teacher_attendance_page_serializes_row_writes_before_submit_or_back():
    root = Path(__file__).resolve().parents[2]
    page = (
        root / "miniapp/src/pages/teacher/academic-affairs/attendance.vue"
    ).read_text(encoding="utf-8")

    assert "marking: {}" in page
    assert "hasPendingMarks()" in page
    assert "this.marking[studentId]" in page
    assert "this.marking[studentId] = true" in page
    assert "this.marking[studentId] = false" in page
    assert "this.hasPendingMarks" in page
    assert "仍有考勤标记正在保存" in page
    assert "正在保存标记…" in page
    assert "at__seg.is-pending" in page
