"""本批正常导入的真实 MySQL 成绩身份、分页、GPA 与 xlsx 回归。"""
from io import BytesIO

import pytest
from openpyxl import load_workbook
from sqlalchemy import select


def test_transcript_consumers_share_effective_identity(db_mode):
    from app.core.context import set_current_user, set_tenant
    from app.db.session import get_sessionmaker
    from app.models import AcademicGrade, AcademicStudent
    from app.modules.academic_affairs.services import academic_affairs_grade_service as service

    tid = 1000000000000000001
    user = {"tenantId": str(tid), "userId": "81003", "realName": "成绩回归",
            "userType": "TEACHER", "currentRoleCode": "ACADEMIC_ADMIN",
            "permissions": ["academicAffairs.gradeViews.query"], "dataScope": "ALL"}
    set_tenant({"tenantId": str(tid)})
    set_current_user(user)
    db = get_sessionmaker()()
    try:
        student = AcademicStudent(tenant_id=tid, student_id=db_mode["student"], name="虚构成绩回归学生")
        db.add(student)
        db.flush()

        def grade(code, course_id, attempt, score, **extra):
            row = AcademicGrade(
                tenant_id=tid, acad_student_id=student.id, course_code=code,
                course_id=course_id, course_version=attempt, attempt_no=attempt,
                course_name="回归课程", credit_value=3, score=score,
                pass_status="PENDING" if score is None else "PASSED" if score >= 60 else "FAILED",
                record_status="ACTIVE", source="PUBLISH", term="2026-1",
                effective_attempt_strategy="LATEST_ATTEMPT",
                gpa_point=0 if score is None else 3, gpa_policy_code="FROZEN_TEST",
                gpa_policy_version=1,
            )
            for key, value in extra.items():
                setattr(row, key, value)
            db.add(row)
            return row

        old = grade("MATH01", 501, 1, 95)
        latest = grade(" math01 ", 501, 2, 80, source="MAKEUP")
        pending_old = grade("PENDING01", 601, 1, 90)
        pending = grade("PENDING01", 601, 2, None)
        retake_old = grade("RETAKE01", 701, 1, 50)
        retake = grade("RETAKE01", 701, 2, 85, source="RETAKE")
        withdrawn = grade("MATH01", 503, 3, 100, record_status="VOIDED")
        other_tenant = grade("MATH01", 504, 4, 100, tenant_id=tid + 1)
        db.commit()
        expected = {str(latest.id), str(pending.id), str(retake.id)}
        service._refresh_aggregates(db, student)
        db.commit()
        db.refresh(student)
        assert float(student.obtained_credits) == 6
        assert float(student.gpa) == 3
        # 被取代的分数及其冻结字段不应因读侧修复而改写。
        assert old.score == 95 and pending_old.score == 90 and retake_old.score == 50
        profile_id = student.student_id
        academic_id = student.id

        scoped = select(AcademicStudent.id).where(AcademicStudent.id == academic_id).subquery()
        filters = service._grade_analysis_filters(AcademicGrade, None)
        assert service._grade_analysis_has_competing_identity(db, AcademicGrade, scoped, filters)
        # 最新未评分记录必须仍参与正式选择，而非回捞旧的有分记录。
        selected = service.resolve_effective_grade(db.scalars(select(AcademicGrade).where(*filters)).all())
        assert {str(row.id) for row in selected} == expected
        db.close()

        whole = service.transcript(profile_id, user)
        pages = [service.transcript(profile_id, user, page=n, page_size=1) for n in range(1, 4)]
        assert {row["gradeId"] for row in whole["items"]} == expected
        assert [row for page in pages for row in page["items"]] == whole["items"]
        assert all(page["total"] == 3 and page["earnedCredits"] == whole["earnedCredits"] == 6
                   and page["gpa"] == whole["gpa"] == 3 for page in pages)
        assert service.transcript(profile_id, user, page=4, page_size=1)["items"] == []
        workbook = load_workbook(BytesIO(service.export_transcript_xlsx(user, profile_id, "成绩准确性回归验证")))
        rows = list(workbook.active.values)
        exported = [row for row in rows if row and str(row[0]).strip().upper() in {"MATH01", "PENDING01", "RETAKE01"}]
        assert len(exported) == 3
        assert sum(1 for row in exported if str(row[0]).strip().upper() == "MATH01") == 1
        assert service.transcript(profile_id, user)["items"] == whole["items"]
    finally:
        db.close()
        set_current_user(None)
        set_tenant(None)


@pytest.mark.parametrize("code,competing", [("ASCII01", False), ("数学01", True), ("A\t01", True)])
def test_mysql_guard_conservative_code_path(db_mode, code, competing):
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import AcademicGrade, AcademicStudent
    from app.modules.academic_affairs.services import academic_affairs_grade_service as service

    tid = 1000000000000000001
    set_tenant({"tenantId": str(tid)})
    db = get_sessionmaker()()
    try:
        student = AcademicStudent(tenant_id=tid, name="虚构字符路径学生")
        db.add(student)
        db.flush()
        db.add(AcademicGrade(tenant_id=tid, acad_student_id=student.id,
                            course_code=code, course_id=801, course_name="回归课程", score=80,
                            pass_status="PASSED", record_status="ACTIVE"))
        db.commit()
        scoped = select(AcademicStudent.id).where(AcademicStudent.id == student.id).subquery()
        assert service._grade_analysis_has_competing_identity(
            db, AcademicGrade, scoped, service._grade_analysis_filters(AcademicGrade, None)
        ) is competing
    finally:
        db.close()
        set_tenant(None)
