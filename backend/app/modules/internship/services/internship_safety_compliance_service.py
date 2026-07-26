"""安全教育合规事实源：当前批次全部 ACTIVE 课程均须按当前版本通过。"""
from __future__ import annotations

from sqlalchemy import select

from app.models import InternshipSafetyCompletion, InternshipSafetyCourse
from app.services.db_service import _tid


def evaluate_required_courses(db, *, batch_id, internship_id) -> dict:
    courses = db.scalars(select(InternshipSafetyCourse).where(
        InternshipSafetyCourse.tenant_id == _tid(),
        InternshipSafetyCourse.batch_id == batch_id,
        InternshipSafetyCourse.status == "ACTIVE",
        InternshipSafetyCourse.is_deleted.is_(False),
    ).order_by(InternshipSafetyCourse.id.asc())).all()
    if not courses:
        return {
            "status": "CONFIG_ERROR",
            "reason": "批次要求安全教育，但未配置任何有效课程",
            "evidenceId": None,
            "evidenceVersion": None,
            "requiredCount": 0,
            "passedCount": 0,
            "missingCourses": [],
        }

    completions = db.scalars(select(InternshipSafetyCompletion).where(
        InternshipSafetyCompletion.tenant_id == _tid(),
        InternshipSafetyCompletion.internship_id == internship_id,
        InternshipSafetyCompletion.course_id.in_([course.id for course in courses]),
        InternshipSafetyCompletion.is_deleted.is_(False),
    )).all()
    completion_map = {row.course_id: row for row in completions}
    missing = []
    passed_rows = []
    pending = False
    for course in courses:
        row = completion_map.get(course.id)
        valid = bool(
            row and row.status == "PASSED" and row.passed and
            str(row.course_version or "") == str(course.course_version or "") and
            (not course.require_commitment or row.commitment_confirmed)
        )
        if valid:
            passed_rows.append(row)
            continue
        if row and row.status in ("IN_PROGRESS", "PENDING", "PENDING_REVIEW", "NOT_STARTED"):
            pending = True
        reason = "未开始"
        if row:
            if str(row.course_version or "") != str(course.course_version or ""):
                reason = f"已完成版本 {row.course_version or '-'}，当前要求 {course.course_version or '-'}"
            elif row.status == "FAILED":
                reason = "未通过"
            elif row.status == "PENDING_REVIEW":
                reason = "待教师审核"
            elif row.status == "IN_PROGRESS":
                reason = "学习中"
            elif course.require_commitment and not row.commitment_confirmed:
                reason = "安全承诺未确认"
            else:
                reason = row.status or "未完成"
        missing.append({
            "courseId": str(course.id), "title": course.title,
            "courseVersion": course.course_version, "reason": reason,
        })

    if not missing:
        newest = passed_rows[-1] if passed_rows else None
        return {
            "status": "VALID", "reason": "",
            "evidenceId": newest.id if newest else None,
            "evidenceVersion": int(newest.version or 0) if newest else None,
            "requiredCount": len(courses), "passedCount": len(passed_rows),
            "missingCourses": [],
        }
    names = "、".join(f"{item['title']}（{item['reason']}）" for item in missing[:5])
    if len(missing) > 5:
        names += f"等{len(missing)}门"
    return {
        "status": "PENDING" if pending else "MISSING",
        "reason": f"须完成当前批次全部安全课程：{names}",
        "evidenceId": None, "evidenceVersion": None,
        "requiredCount": len(courses), "passedCount": len(passed_rows),
        "missingCourses": missing,
    }
