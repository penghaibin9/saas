"""20K 沙箱核心六域的跨域安全只读验收。

`seed_school_domains_20k()` 在就业域写入前会用原始 validate_domain_facts() 做即时验收；
完整重建结束后还会新增就业老师 UnifiedTodo。此时不能再用“全表所有 PENDING Todo”冒充
“学生待办”，否则新增任何合法教师待办都会污染六域合同。

这里保持六域全部行数断言不变，只把 pendingStudentTodos 精确限定为本模块写入的
source_biz_type=STUDENT_TASK。就业教师待办由 sandbox_school_employment_seed 独立验收。
"""
from __future__ import annotations

from sqlalchemy import func, or_, select

from app.services.sandbox_school_domain_seed import (
    EXPECTED_ACADEMIC_STUDENTS,
    EXPECTED_CAMPUS_STUDENTS,
    EXPECTED_CHECKINS,
    EXPECTED_DORM_ROWS,
    EXPECTED_GRADE_ROWS,
    EXPECTED_GRADUATION_STUDENTS,
    EXPECTED_INTERNSHIP_RECORDS,
    EXPECTED_MESSAGES,
    EXPECTED_STUDENT_TODOS,
    EXPECTED_WEEKLY_REPORTS,
    GRADE_STUDENT_COUNTS,
)


def validate_core_domain_facts_20k(db, tenant_id: int) -> dict:
    from app.models import (
        AcademicGrade,
        AcademicStudent,
        CsDormRecord,
        CsServiceStudent,
        GraduationStudent,
        InternshipCheckin,
        InternshipRecord,
        OrientationStudent,
        UnifiedMessage,
        UnifiedTodo,
        WeeklyReport,
    )

    def count(model, *where) -> int:
        return int(db.scalar(select(func.count()).select_from(model).where(
            model.tenant_id == tenant_id,
            *where,
        )) or 0)

    report = {
        "orientationStudents": count(OrientationStudent, OrientationStudent.is_deleted.is_(False)),
        "academicStudents": count(AcademicStudent, AcademicStudent.is_deleted.is_(False)),
        "academicGrades": count(AcademicGrade, AcademicGrade.is_deleted.is_(False)),
        "campusStudents": count(CsServiceStudent, CsServiceStudent.is_deleted.is_(False)),
        "dormRecords": count(CsDormRecord, CsDormRecord.is_deleted.is_(False)),
        "internshipRecords": count(InternshipRecord, InternshipRecord.is_deleted.is_(False)),
        "internshipCheckins": count(InternshipCheckin, InternshipCheckin.is_deleted.is_(False)),
        "weeklyReports": count(WeeklyReport, WeeklyReport.is_deleted.is_(False)),
        "graduationStudents": count(GraduationStudent, GraduationStudent.is_deleted.is_(False)),
        # 六域基线消息由迎新、学业和实习各产生一条个人消息。后续学工风险扫描会
        # 依法追加 RISK_ALERT，不能把这些真实业务消息误判为 20K 基线污染。
        "messages": count(
            UnifiedMessage,
            UnifiedMessage.source_module.in_(("orientation", "academic", "internship")),
            or_(UnifiedMessage.remark.is_(None), UnifiedMessage.remark != "SALES_STORY_RESET"),
            UnifiedMessage.is_deleted.is_(False),
        ),
        "pendingStudentTodos": count(
            UnifiedTodo,
            UnifiedTodo.source_biz_type == "STUDENT_TASK",
            UnifiedTodo.status == "PENDING",
            UnifiedTodo.is_deleted.is_(False),
        ),
    }
    expected = {
        "orientationStudents": GRADE_STUDENT_COUNTS["2026"],
        "academicStudents": EXPECTED_ACADEMIC_STUDENTS,
        "academicGrades": EXPECTED_GRADE_ROWS,
        "campusStudents": EXPECTED_CAMPUS_STUDENTS,
        "dormRecords": EXPECTED_DORM_ROWS,
        "internshipRecords": EXPECTED_INTERNSHIP_RECORDS,
        "internshipCheckins": EXPECTED_CHECKINS,
        "weeklyReports": EXPECTED_WEEKLY_REPORTS,
        "graduationStudents": EXPECTED_GRADUATION_STUDENTS,
        "messages": EXPECTED_MESSAGES,
        "pendingStudentTodos": EXPECTED_STUDENT_TODOS,
    }
    mismatches = {
        key: {"expected": expected[key], "actual": report[key]}
        for key in expected
        if report[key] != expected[key]
    }
    if mismatches:
        raise RuntimeError(f"20K 沙箱核心六域验收失败: {mismatches}")
    report["passed"] = True
    return report
