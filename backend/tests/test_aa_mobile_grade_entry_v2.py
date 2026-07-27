"""V2 R5 教师微信成绩录入闭环回归。"""
from pathlib import Path

import pytest

from app.core.exceptions import AppException


def _mobile():
    from app.modules.academic_affairs import services

    return services.mobile_academic_affairs_service


def test_mobile_grade_normalization_accepts_zero_and_rejects_bad_values():
    normalize_mobile_grade_row = _mobile().normalize_mobile_grade_row

    row = normalize_mobile_grade_row({
        "studentId": "9",
        "usualScore": 0,
        "midtermScore": "80",
        "finalScore": 100,
        "exceptionFlag": "normal",
    })
    assert row == {
        "studentId": 9,
        "usualScore": 0,
        "midtermScore": 80,
        "finalScore": 100,
        "exceptionFlag": "NORMAL",
    }

    special = normalize_mobile_grade_row({
        "studentId": 9,
        "usualScore": 99,
        "finalScore": 99,
        "exceptionFlag": "ABSENT",
    })
    assert special["usualScore"] is None
    assert special["finalScore"] is None

    for bad in (-1, 101, 60.5, True, "abc"):
        with pytest.raises(AppException):
            normalize_mobile_grade_row({"studentId": 9, "usualScore": bad})


def test_quality_report_explains_missing_incomplete_special_and_outside_roster():
    report = _mobile().build_grade_quality_report(
        [
            {"studentId": "1", "studentNo": "S001", "realName": "甲"},
            {"studentId": "2", "studentNo": "S002", "realName": "乙"},
            {"studentId": "3", "studentNo": "S003", "realName": "丙"},
        ],
        [
            {"studentId": "1", "usualScore": 80, "midtermScore": 70, "finalScore": 90,
             "totalScore": 84, "passStatus": "PASSED", "exceptionFlag": "NORMAL"},
            {"studentId": "2", "usualScore": None, "midtermScore": None, "finalScore": None,
             "totalScore": None, "passStatus": None, "exceptionFlag": "ABSENT"},
            {"studentId": "99", "usualScore": 60, "midtermScore": 60, "finalScore": 60,
             "totalScore": 60, "passStatus": "PASSED", "exceptionFlag": "NORMAL"},
        ],
        usual_ratio=30,
        midterm_ratio=20,
        final_ratio=50,
        status="INPUTTING",
    )

    assert report["rosterCount"] == 3
    assert report["recordedCount"] == 2
    assert report["specialCount"] == 1
    assert report["missingCount"] == 1
    assert report["outsideRosterCount"] == 1
    assert report["ready"] is False
    assert report["canSubmit"] is False
    assert {item["code"] for item in report["issues"]} == {"NOT_RECORDED", "OUTSIDE_ROSTER"}


def test_quality_report_ready_requires_all_required_parts():
    build_grade_quality_report = _mobile().build_grade_quality_report
    incomplete = build_grade_quality_report(
        [{"studentId": "1", "studentNo": "S001", "realName": "甲"}],
        [{"studentId": "1", "usualScore": 80, "midtermScore": None, "finalScore": 90,
          "totalScore": None, "exceptionFlag": "NORMAL"}],
        usual_ratio=30,
        midterm_ratio=20,
        final_ratio=50,
        status="INPUTTING",
    )
    assert incomplete["incompleteCount"] == 1
    assert incomplete["ready"] is False
    assert "期中分" in incomplete["issues"][0]["message"]

    ready = build_grade_quality_report(
        [{"studentId": "1", "studentNo": "S001", "realName": "甲"}],
        [{"studentId": "1", "usualScore": 80, "midtermScore": 70, "finalScore": 90,
          "totalScore": 84, "passStatus": "PASSED", "exceptionFlag": "NORMAL"}],
        usual_ratio=30,
        midterm_ratio=20,
        final_ratio=50,
        status="RETURNED",
    )
    assert ready["ready"] is True
    assert ready["canSubmit"] is True


def test_public_mobile_service_and_router_use_one_explicit_entry():
    from app.modules.academic_affairs.routers import academic_affairs

    mobile = _mobile()
    assert mobile.__name__.endswith("mobile_academic_affairs_facade")
    for name in (
        "schedule_my", "teacher_schedule_my", "teacher_attendance_class_options",
        "makeup_options_my", "retake_apply_my", "exemption_apply_my",
        "teacher_grade_batch_save", "teacher_grade_quality_report",
        "teacher_grade_submit_task",
    ):
        assert callable(getattr(mobile, name))

    routes = {
        (route.path, tuple(sorted(route.methods or set())))
        for route in academic_affairs.router.routes
    }
    assert ("/mobile/teacher/academic/grade-tasks/{task_id}/batch-save", ("POST",)) in routes
    assert ("/mobile/teacher/academic/grade-tasks/{task_id}/quality-report", ("GET",)) in routes


def test_old_mobile_wrappers_do_not_patch_other_modules():
    root = Path(__file__).resolve().parents[1]
    for filename in (
        "mobile_academic_grade_identity_facade.py",
        "mobile_academic_grade_entry_closure_service.py",
        "mobile_academic_exam_safety_facade.py",
    ):
        source = (root / "app/modules/academic_affairs/services" / filename).read_text(encoding="utf-8")
        assert " = retake_apply_my" not in source
        assert " = exemption_apply_my" not in source
        assert " = recognition_submit_my" not in source
        assert "_gaps.makeup_options_my" not in source


def test_teacher_wechat_page_contains_local_draft_guard_batch_save_and_quality_report():
    root = Path(__file__).resolve().parents[2]
    page = (root / "miniapp/src/pages/teacher/academic-affairs/grade-entry.vue").read_text(encoding="utf-8")
    nav = (root / "miniapp/src/components/MobileNavBar.vue").read_text(encoding="utf-8")
    api = (root / "miniapp/src/services/academicGradeEntryApi.js").read_text(encoding="utf-8")

    assert "uni.setStorageSync" in page
    assert "restoreDraft" in page
    assert ":before-back=\"beforePageBack\"" in page
    assert "qualityReport" in page
    assert "academicGradeEntryApi.batchSave" in page
    assert "academicGradeEntryApi.qualityReport" in page
    assert "beforeBack" in nav
    assert "/batch-save" in api
    assert "/quality-report" in api
