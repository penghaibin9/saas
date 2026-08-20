"""Teacher Miniapp V3 T4 Student360 read projection.

This is a read-only mobile projection over existing domain facts. It deliberately does not
create new workflow/state-machine authority: talk/family/mental/employment/internship commands
remain in their mature services. The projection owns only one-student read composition,
object-action context, sensitive-summary minimisation and freshness metadata.

Scale contract:
- object visibility is compiled to SQL before the StudentProfile row is returned;
- one Student360 request reads at most one row per domain plus the last 10 stage events;
- no per-card/N+1 query and no shared cache of sensitive detail;
- projectionVersion consumes Student V3 shared freshness when that handoff exists, otherwise
  degrades to a build-time token without inventing a second Redis version authority.
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import aliased

from app.core.exceptions import AppException
from app.services import mobile_teacher_service as teacher_guard
from app.services.db_service import _iso, _tid, session
from app.services.teacher_student_visibility_service import compile_teacher_student_visibility

_STUDENT360_PROJECTIONS = ("todo", "internship", "graduation", "case")
_ACTIVE_WARNING_STATUSES = ("PENDING_HANDLE", "PROCESSING", "ESCALATED")


def _projection_version(user: dict, student_id: int) -> str:
    """Consume Student V3 shared freshness only when present; never duplicate its counters."""
    try:
        from app.services import mobile_freshness_service as freshness

        scoped = dict(user or {})
        scoped["studentId"] = str(student_id)
        return freshness.projection_version(scoped, _STUDENT360_PROJECTIONS)
    except (ImportError, AttributeError):
        # Before T8 handoff there is no shared freshness module on this branch. The page reloads
        # onShow, so a second-level build token is truthful and cannot preserve stale cache.
        return f"t{int(time.time())}"


def _student_lookup_condition(StudentProfile, raw_student_id: Any):
    """Student360 object route accepts only canonical StudentProfile.id.

    Numeric student numbers are common. Treating the same path value as both profile id and
    student_no makes ``/students/123/projection`` ambiguous and can select a different authorised
    student depending on query order. MyStudents already carries the canonical profile id, so the
    object route is intentionally strict and fail-closed.
    """
    raw = str(raw_student_id or "").strip()
    if not raw.isdigit() or int(raw) <= 0:
        raise AppException("VALIDATION_ERROR", "studentId 必须是有效学生主档ID", http_status=400)
    return StudentProfile.id == int(raw)


def _risk_level(*, warning_count: int, internship_risk: str, affairs_risk: str) -> str:
    internship = str(internship_risk or "").upper()
    affairs = str(affairs_risk or "").upper()
    if internship in {"HIGH", "URGENT", "CRITICAL"} or affairs in {"HIGH", "URGENT", "CRITICAL"}:
        return "HIGH"
    if warning_count or internship == "MEDIUM" or affairs == "MEDIUM":
        return "MEDIUM"
    return "LOW"


def _section(key: str, title: str, *, has_data: bool, status: str = "",
             summary: str = "", abnormal: bool = False, action_key: str | None = None,
             record_id: str | None = None) -> dict[str, Any]:
    return {
        "key": key,
        "title": title,
        "hasData": bool(has_data),
        "status": status or "",
        "summary": summary or "",
        "abnormal": bool(abnormal),
        "actionKey": action_key,
        "recordId": record_id,
    }


def get_projection(user: dict, student_id: Any) -> dict[str, Any]:
    """Build one authorised Student360 projection with object-action context."""
    teacher_guard._require_teacher(user)

    from app.models import (
        AcademicStudent,
        AcademicWarning,
        CsDiscipline,
        CsServiceStudent,
        EmpStudent,
        GraduationStudent,
        InternshipRecord,
        SchoolClass,
        StudentProfile,
        StudentStageEvent,
    )

    student = aliased(StudentProfile, name="student360_student")
    school_class = aliased(SchoolClass, name="student360_class")
    visibility = compile_teacher_student_visibility(user, student.id)
    as_of = datetime.utcnow()

    with session() as db:
        row = db.execute(
            select(student, school_class.class_name)
            .outerjoin(
                school_class,
                and_(
                    school_class.id == student.class_id,
                    school_class.tenant_id == _tid(),
                    school_class.is_deleted.is_(False),
                ),
            )
            .where(
                student.tenant_id == _tid(),
                student.is_deleted.is_(False),
                _student_lookup_condition(student, student_id),
                visibility,
            )
            .limit(1)
        ).first()
        if not row:
            # Do not distinguish missing from out-of-scope; object enumeration fails closed.
            raise AppException("DATA_NOT_FOUND", "学生不存在或不在你的负责范围内", http_status=404)
        stu, class_name = row

        academic = db.scalars(select(AcademicStudent).where(
            AcademicStudent.tenant_id == _tid(),
            AcademicStudent.is_deleted.is_(False),
            AcademicStudent.record_status == "ACTIVE",
            AcademicStudent.student_no == stu.student_no,
        ).order_by(AcademicStudent.id.desc()).limit(1)).first()
        warning_count = 0
        if academic:
            warning_count = int(db.scalar(
                select(func.count()).select_from(AcademicWarning).where(
                    AcademicWarning.tenant_id == _tid(),
                    AcademicWarning.is_deleted.is_(False),
                    AcademicWarning.acad_student_id == academic.id,
                    AcademicWarning.record_status == "ACTIVE",
                    AcademicWarning.status.in_(_ACTIVE_WARNING_STATUSES),
                )
            ) or 0)

        internship = db.scalars(select(InternshipRecord).where(
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.is_deleted.is_(False),
            InternshipRecord.student_id == stu.id,
        ).order_by(InternshipRecord.id.desc()).limit(1)).first()

        graduation = db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(),
            GraduationStudent.is_deleted.is_(False),
            GraduationStudent.record_status == "ACTIVE",
            GraduationStudent.student_no == stu.student_no,
        ).order_by(GraduationStudent.id.desc()).limit(1)).first()

        employment = db.scalars(select(EmpStudent).where(
            EmpStudent.tenant_id == _tid(),
            EmpStudent.is_deleted.is_(False),
            EmpStudent.record_status == "ACTIVE",
            or_(EmpStudent.student_id == stu.id, EmpStudent.student_no == stu.student_no),
        ).order_by(EmpStudent.id.desc()).limit(1)).first()

        affairs = db.scalars(select(CsServiceStudent).where(
            CsServiceStudent.tenant_id == _tid(),
            CsServiceStudent.is_deleted.is_(False),
            CsServiceStudent.record_status == "ACTIVE",
            or_(CsServiceStudent.student_id == stu.id, CsServiceStudent.student_no == stu.student_no),
        ).order_by(CsServiceStudent.id.desc()).limit(1)).first()

        discipline = None
        if affairs:
            discipline = db.scalars(select(CsDiscipline).where(
                CsDiscipline.tenant_id == _tid(),
                CsDiscipline.is_deleted.is_(False),
                CsDiscipline.cs_student_id == affairs.id,
                CsDiscipline.record_status == "ACTIVE",
            ).order_by(CsDiscipline.id.desc()).limit(1)).first()

        events = db.scalars(select(StudentStageEvent).where(
            StudentStageEvent.tenant_id == _tid(),
            StudentStageEvent.student_id == stu.id,
        ).order_by(StudentStageEvent.id.desc()).limit(10)).all()

    risk_level = _risk_level(
        warning_count=warning_count,
        internship_risk=getattr(internship, "risk_level", ""),
        affairs_risk=getattr(affairs, "risk_level", ""),
    )

    internship_status = str(getattr(internship, "status", "") or "")
    academic_status = str(getattr(academic, "academic_status", "") or "")
    graduation_stage = str(getattr(graduation, "stage", "") or "")
    employment_status = str(getattr(employment, "destination_type", "") or "")
    affairs_status = str(getattr(affairs, "record_status", "") or "")

    sections = [
        _section(
            "academic", "学业",
            has_data=bool(academic), status=academic_status,
            summary=(f"GPA {float(academic.gpa or 0):.2f} · {warning_count} 条在办预警" if academic else "暂无学业摘要"),
            abnormal=warning_count > 0,
            action_key="ACADEMIC_WARNING" if warning_count else None,
            record_id=str(academic.id) if academic else None,
        ),
        _section(
            "internship", "岗位实习",
            has_data=bool(internship), status=internship_status,
            summary=(f"{internship.enterprise_name or '未登记企业'} · {internship.position_name or '未登记岗位'}" if internship else "暂无实习记录"),
            abnormal=str(getattr(internship, "risk_level", "") or "").upper() in {"MEDIUM", "HIGH", "URGENT", "CRITICAL"},
            action_key="INTERNSHIP_GUIDANCE" if internship else None,
            record_id=str(internship.id) if internship else None,
        ),
        _section(
            "graduation", "毕业设计",
            has_data=bool(graduation), status=graduation_stage,
            summary=(graduation.topic_title or "已进入毕业设计流程") if graduation else "暂无毕业设计记录",
            abnormal=False,
            action_key="GRADUATION_GUIDANCE" if graduation else None,
            record_id=str(graduation.id) if graduation else None,
        ),
        _section(
            "employment", "就业",
            has_data=bool(employment), status=employment_status,
            summary=((employment.company_name or employment.unemployed_reason or "待继续跟进") if employment else "暂无就业记录"),
            abnormal=bool(employment and employment.destination_type == "UNEMPLOYED"),
            action_key="EMPLOYMENT_FOLLOWUP" if employment else None,
            record_id=str(employment.id) if employment else None,
        ),
        _section(
            "affairs", "学工",
            has_data=bool(affairs), status=affairs_status,
            summary=(f"关怀 {affairs.care_level or 'NORMAL'} · 风险 {affairs.risk_level or 'LOW'}" if affairs else "暂无学工摘要"),
            abnormal=str(getattr(affairs, "risk_level", "") or "").upper() in {"MEDIUM", "HIGH", "URGENT", "CRITICAL"},
            action_key="STUDENT_AFFAIRS" if affairs else None,
            record_id=str(affairs.id) if affairs else None,
        ),
    ]
    sections.sort(key=lambda item: (not item["abnormal"], item["key"]))

    # Sensitive zone is summary-only. mental_flag and active discipline projection reveal no
    # diagnosis/reason/note/document content; detailed reads remain behind their mature audit gates.
    sensitive = {
        "mental": {
            "exists": bool(getattr(affairs, "mental_flag", False)),
            "status": "ATTENTION" if getattr(affairs, "mental_flag", False) else "NONE",
            "detailRestricted": True,
        },
        "discipline": {
            "exists": bool(discipline),
            "status": str(getattr(discipline, "status", "") or "NONE"),
            "detailRestricted": True,
        },
    }

    actions = [
        {"key": "RECORD_CONTACT", "label": "记录联系", "enabled": True},
        {"key": "NEW_TALK", "label": "新建谈话", "enabled": True},
        {"key": "FAMILY_CONTACT", "label": "家校联系", "enabled": True},
        {"key": "EMPLOYMENT_FOLLOWUP", "label": "创建跟进", "enabled": bool(employment)},
    ]

    return {
        "hasData": True,
        "asOf": _iso(as_of),
        "projectionVersion": _projection_version(user, int(stu.id)),
        "studentId": str(stu.id),
        "base": {
            "name": stu.real_name or "",
            "studentNo": stu.student_no or "",
            "className": class_name or "",
            "stage": stu.current_stage or "",
            "status": stu.student_status or "",
        },
        "risk": {
            "level": risk_level,
            "warningCount": warning_count,
            "internshipRisk": str(getattr(internship, "risk_level", "") or "NONE"),
            "affairsRisk": str(getattr(affairs, "risk_level", "") or "LOW"),
        },
        "actions": actions,
        "sections": sections,
        "sensitive": sensitive,
        # Stage-event free text can contain operator notes or sensitive reasons.  Student360 only
        # exposes structural lifecycle facts; detailed stage evidence remains behind its source gate.
        "timeline": [
            {
                "id": str(event.id),
                "stage": event.to_stage or "",
                "time": _iso(event.occurred_at),
                "actionKey": None,
            }
            for event in events
        ],
        "context": {
            "internshipId": str(internship.id) if internship else None,
            "graduationStudentId": str(graduation.id) if graduation else None,
            "employmentStudentId": str(employment.id) if employment else None,
            "affairsStudentId": str(affairs.id) if affairs else None,
        },
    }
