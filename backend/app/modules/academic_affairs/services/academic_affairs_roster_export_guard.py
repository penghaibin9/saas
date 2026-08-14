"""PR #101 roster export production hardening.

The interactive roster stays capped at 200 rows per request; the XLSX export gets its own
full SQL query so a 20k-student school is neither truncated nor forced through an oversized
public pageSize.
"""
from __future__ import annotations

import importlib
from datetime import datetime

from sqlalchemy import or_, select

from app.core.affairs_security import build_affairs_context
from app.core.exceptions import AppException


def export_roster_xlsx(user, purpose="", keyword=None, status=None) -> bytes:
    legacy = importlib.import_module(".academic_affairs_service", package=__package__)
    from app.core.field_crypto import mask_id_card_encrypted
    from app.models import SchoolClass, StudentProfile
    from app.modules.academic_affairs.services.academic_affairs_status_service import is_enrolled
    from app.services.xlsx_util import build_ledger_xlsx

    purpose = str(purpose or "").strip()
    if len(purpose) < 5:
        raise AppException("VALIDATION_ERROR", "导出用途必填（≥5 字）")

    with legacy.session() as db:
        ctx = build_affairs_context(user, db)
        conditions = [
            StudentProfile.tenant_id == legacy._tid(),
            StudentProfile.is_deleted.is_(False),
        ]
        if status:
            conditions.append(StudentProfile.student_status == status)
        allowed = ctx.allowed_class_ids(db)
        if allowed is not None:
            conditions.append(
                StudentProfile.class_id.in_(sorted(allowed)) if allowed else StudentProfile.id == -1
            )
        term = str(keyword or "").strip()
        if term:
            conditions.append(or_(
                StudentProfile.real_name.contains(term, autoescape=True),
                StudentProfile.student_no.contains(term, autoescape=True),
            ))
        students = db.scalars(
            select(StudentProfile).where(*conditions).order_by(StudentProfile.id.desc())
        ).all()
        class_ids = {int(student.class_id) for student in students if student.class_id}
        class_rows = db.scalars(select(SchoolClass).where(
            SchoolClass.tenant_id == legacy._tid(),
            SchoolClass.id.in_(sorted(class_ids)) if class_ids else SchoolClass.id == -1,
            SchoolClass.is_deleted.is_(False),
        )).all()
        class_names = {int(row.id): row.class_name for row in class_rows}

    operator_name, _role, _uid = legacy._op()
    watermark = (
        f"导出人：{operator_name or '-'}  时间：{datetime.utcnow().strftime('%Y-%m-%d %H:%M')}  "
        f"用途：{purpose}"
    )
    headers = ["学号", "姓名", "班级", "学籍状态", "是否在籍", "身份证（脱敏）"]
    rows = [
        [
            student.student_no,
            student.real_name,
            class_names.get(int(student.class_id), str(student.class_id or "")) if student.class_id else "",
            legacy._STATUS_LABEL.get(student.student_status, student.student_status),
            "在籍" if is_enrolled(student.student_status) else "非在籍",
            mask_id_card_encrypted(student.id_card_encrypted) or "",
        ]
        for student in students
    ]
    content = build_ledger_xlsx("学籍名册", headers, rows, watermark=watermark)
    with legacy.session() as db:
        legacy._audit(db, "AA_ROSTER", None, "EXPORT", f"用途={purpose[:100]} rows={len(rows)}")
        db.commit()
    return content


def install() -> None:
    legacy = importlib.import_module(".academic_affairs_service", package=__package__)
    public = importlib.import_module(".academic_affairs_dashboard_scope_facade", package=__package__)
    legacy.export_roster_xlsx = export_roster_xlsx
    public.export_roster_xlsx = export_roster_xlsx
