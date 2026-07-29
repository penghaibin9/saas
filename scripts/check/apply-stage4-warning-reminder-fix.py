from __future__ import annotations

from pathlib import Path


OUTBOX = Path("backend/app/services/message_event_outbox_service.py")
WARNING = Path("backend/app/modules/academic_affairs/services/academic_affairs_warning_service.py")
SMOKE = Path("backend/tests/test_aa_stage4_real_smoke.py")


def patch_outbox() -> None:
    text = OUTBOX.read_text(encoding="utf-8")
    created = '''    "WARNING.CREATED": {
        "source_module": "academic-affairs",
        "category": "WARNING",
        "priority": "IMPORTANT",
        "message_type": "ACAD_WARNING_NEW",
        "title": "学业预警通知",
        "require_ack": False,
    },
'''
    reminded = '''    "WARNING.REMINDED": {
        "source_module": "academic-affairs",
        "category": "REMINDER",
        "priority": "IMPORTANT",
        "message_type": "ACAD_WARNING_REMIND",
        "title": "学业预警再次提醒",
        "require_ack": False,
    },
'''
    if '"WARNING.REMINDED"' in text:
        return
    if text.count(created) != 1:
        raise SystemExit("未唯一找到 WARNING.CREATED 模板，拒绝盲改")
    OUTBOX.write_text(text.replace(created, created + reminded, 1), encoding="utf-8")


def patch_warning_service() -> None:
    text = WARNING.read_text(encoding="utf-8")
    event_line = '    event_code = "WARNING.REMINDED" if is_remind else "WARNING.CREATED"\n'
    if event_line not in text:
        marker = '    remind_n = int(warning.remind_count or 0) if is_remind else 0\n    sent = 0\n'
        if text.count(marker) != 1:
            raise SystemExit("未唯一找到预警通知场景标记，拒绝盲改")
        text = text.replace(
            marker,
            marker.replace("    sent = 0\n", event_line + "    sent = 0\n"),
            1,
        )
    old = 'event_code="WARNING.CREATED"'
    count = text.count(old)
    if count:
        if count != 2:
            raise SystemExit(f"WARNING.CREATED 调用数量异常：{count}")
        text = text.replace(old, "event_code=event_code")
    if text.count("event_code=event_code") != 2:
        raise SystemExit("预警学生与辅导员两条消息未全部切换到场景事件码")
    WARNING.write_text(text, encoding="utf-8")


def patch_real_smoke() -> None:
    text = SMOKE.read_text(encoding="utf-8")
    test_name = "test_stage4_warning_reminder_persists_real_message_type"
    if test_name in text:
        return
    text += r'''


def test_stage4_warning_reminder_persists_real_message_type(db_mode):
    """接口报告已通知时，学生与辅导员提醒必须真实按 ACAD_WARNING_REMIND 落库。"""
    from sqlalchemy import select
    from app.models import (
        AcademicGrade,
        AcademicStudent,
        AcademicWarning,
        SchoolClass,
        StudentProfile,
        UnifiedMessage,
    )

    db = get_sessionmaker()()
    try:
        school_class = SchoolClass(
            tenant_id=TID,
            major_id=1,
            class_name="第四阶段预警验收班",
            grade="2026",
            status="ACTIVE",
            counselor_id=98533,
        )
        db.add(school_class)
        db.flush()
        student = StudentProfile(
            tenant_id=TID,
            student_no="STAGE4-WARNING-001",
            real_name="第四阶段预警学生",
            class_id=school_class.id,
            current_stage="ON_CAMPUS",
            student_status="REGISTERED",
            status="ACTIVE",
        )
        db.add(student)
        db.flush()
        academic_student = AcademicStudent(
            tenant_id=TID,
            student_id=student.id,
            student_no=student.student_no,
            name=student.real_name,
            class_name=school_class.class_name,
        )
        db.add(academic_student)
        db.flush()
        for course_name in ("第四阶段高等数学", "第四阶段大学英语"):
            db.add(AcademicGrade(
                tenant_id=TID,
                acad_student_id=academic_student.id,
                course_name=course_name,
                term="2026-2027-1",
                nature="REQUIRED",
                credit_value=4,
                score=45,
                pass_status="FAILED",
                exam_type="FINAL",
                record_status="ACTIVE",
            ))
        db.commit()
        student_id = int(student.id)
        academic_student_id = int(academic_student.id)
    finally:
        db.close()

    admin = _headers("ACADEMIC_ADMIN", login_name="academic-warning-stage4")
    with TestClient(app) as client:
        scan = _assert_ok(
            client.post("/api/v1/academic-affairs/warnings/scan", headers=admin),
            "预警扫描",
        )
        assert int(scan.get("created") or 0) >= 1

        db = get_sessionmaker()()
        try:
            warning = db.scalar(select(AcademicWarning).where(
                AcademicWarning.tenant_id == TID,
                AcademicWarning.acad_student_id == academic_student_id,
                AcademicWarning.source_code == "EXAM_FAIL",
                AcademicWarning.is_deleted.is_(False),
            ))
            assert warning is not None
            warning_id = int(warning.id)
        finally:
            db.close()

        reminded = _assert_ok(
            client.post(f"/api/v1/academic-affairs/warnings/{warning_id}/remind", headers=admin),
            "预警提醒",
        )
        assert reminded["remindCount"] == 1
        assert reminded["notified"] == 2

    db = get_sessionmaker()()
    try:
        rows = db.scalars(select(UnifiedMessage).where(
            UnifiedMessage.tenant_id == TID,
            UnifiedMessage.source_module == "academic-affairs",
            UnifiedMessage.source_biz_id == warning_id,
            UnifiedMessage.message_type == "ACAD_WARNING_REMIND",
            UnifiedMessage.is_deleted.is_(False),
        )).all()
        assert {int(row.receiver_id) for row in rows} == {student_id, 98533}
        assert all("提醒" in row.title for row in rows)
    finally:
        db.close()
'''
    SMOKE.write_text(text, encoding="utf-8")


def main() -> None:
    patch_outbox()
    patch_warning_service()
    patch_real_smoke()


if __name__ == "__main__":
    main()
