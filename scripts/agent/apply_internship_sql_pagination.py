from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHANGED: list[str] = []


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    old = path.read_text(encoding="utf-8")
    if old != text:
        path.write_text(text, encoding="utf-8")
        CHANGED.append(rel)


def replace_function(text: str, name: str, block: str) -> str:
    match = re.search(rf"(?ms)^def {re.escape(name)}\(.*?(?=^def |\Z)", text)
    if not match:
        raise RuntimeError(f"function not found: {name}")
    return text[:match.start()] + block.rstrip() + "\n\n\n" + text[match.end():].lstrip("\n")


def patch_import(text: str, old: str, new: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"import anchor missing: {old}")
    return text.replace(old, new, 1)


def patch_leave() -> None:
    rel = "backend/app/modules/internship/services/internship_leave_service.py"
    text = read(rel)
    text = patch_import(text, "from sqlalchemy import select", "from sqlalchemy import func, or_, select")

    row_block = '''def _row(lv: InternshipLeave, rec, stu, *, db=None, user=None,
         previous=None, evidence_viewed=None, preloaded: bool = False) -> dict:
    if not preloaded:
        previous = _previous_rejection(db, lv) if db is not None else None
        evidence_viewed = _evidence_viewed(db, lv, user) if db is not None and user else False
    return {
        "id": str(lv.id), "internId": str(lv.internship_id),
        "studentName": stu.real_name if stu else "-", "studentNo": stu.student_no if stu else "-",
        "advisorName": rec.advisor_name if rec else "",
        "leaveType": lv.leave_type, "leaveTypeLabel": TYPE_LABEL.get(lv.leave_type, lv.leave_type),
        "startDate": lv.start_date, "endDate": lv.end_date, "days": lv.days,
        "reason": lv.reason, "status": lv.status, "statusLabel": STATUS_LABEL.get(lv.status, lv.status),
        "applyBy": lv.apply_by_name or "", "reviewBy": lv.review_by_name or "",
        "reviewComment": lv.review_comment or "", "reviewAt": _iso(lv.review_at) or "",
        "returnedAt": _iso(lv.returned_at) or "", "returnNote": lv.return_note or "",
        "returnFileId": lv.return_file_id or "", "overdue": lv.status == "OVERDUE",
        "version": int(lv.version or 0),
        "createdAt": _iso(lv.created_at) or "", "submittedAt": _iso(lv.created_at) or "",
        "evidenceFileId": lv.file_id or "", "hasEvidence": bool(lv.file_id),
        "evidenceRequired": _evidence_required(lv.leave_type, lv.days),
        "evidenceRequirementLabel": _evidence_requirement_label(lv.leave_type, lv.days),
        "evidenceViewed": bool(evidence_viewed),
        "previousReviewComment": previous.review_comment or "" if previous else "",
        "previousReviewAt": _iso(previous.review_at) or "" if previous else "",
    }
'''
    text = replace_function(text, "_row", row_block)

    list_block = '''def list_leaves(page, page_size, status=None, keyword=None, batch_id=None, user=None) -> tuple[list[dict], int]:
    from app.modules.internship.services.internship_batch_context import resolve_batch
    from app.modules.internship.services.internship_scope import apply_internship_record_scope

    with session() as db:
        batch = resolve_batch(db, batch_id)
        scoped = apply_internship_record_scope(
            select(InternshipRecord.id).where(
                InternshipRecord.tenant_id == _tid(),
                InternshipRecord.batch_id == batch.id,
                InternshipRecord.is_deleted.is_(False)), user).subquery()
        query = select(InternshipLeave, InternshipRecord, StudentProfile).join(
            InternshipRecord, InternshipRecord.id == InternshipLeave.internship_id
        ).join(
            StudentProfile, StudentProfile.id == InternshipLeave.student_id
        ).where(
            InternshipLeave.tenant_id == _tid(),
            InternshipLeave.is_deleted.is_(False),
            InternshipLeave.internship_id.in_(select(scoped.c.id)),
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.batch_id == batch.id,
            InternshipRecord.is_deleted.is_(False),
            StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False),
        )
        if status:
            query = query.where(InternshipLeave.status == status)
        term = str(keyword or "").strip()
        if term:
            like = f"%{term}%"
            query = query.where(or_(
                StudentProfile.real_name.like(like),
                StudentProfile.student_no.like(like),
            ))
        total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
        size = max(0, int(page_size or 0))
        if size == 0:
            return [], total
        rows = db.execute(
            query.order_by(InternshipLeave.id.desc())
            .offset((max(1, int(page or 1)) - 1) * size).limit(size)
        ).all()
        leaves = [item[0] for item in rows]
        ids = [item.id for item in leaves]
        previous_map = {}
        if leaves:
            internship_ids = {item.internship_id for item in leaves}
            rejected = db.scalars(select(InternshipLeave).where(
                InternshipLeave.tenant_id == _tid(),
                InternshipLeave.internship_id.in_(internship_ids),
                InternshipLeave.status == "REJECTED",
                InternshipLeave.is_deleted.is_(False),
            ).order_by(InternshipLeave.id.desc())).all()
            for item in rejected:
                key = (item.internship_id, item.leave_type, item.start_date, item.end_date)
                previous_map.setdefault(key, item)
        viewed_ids = set()
        if ids and user:
            actor_id = _actor_id(user)
            operator = _op_name(user)
            trails = db.scalars(select(InternshipAuditTrail).where(
                InternshipAuditTrail.tenant_id == _tid(),
                InternshipAuditTrail.target_type == "LEAVE",
                InternshipAuditTrail.target_id.in_(ids),
                InternshipAuditTrail.action == "EVIDENCE_VIEW",
            ).order_by(InternshipAuditTrail.id.desc())).all()
            by_id = {item.id: item for item in leaves}
            for trail in trails:
                leave = by_id.get(trail.target_id)
                if not leave or not leave.file_id:
                    continue
                detail = trail.detail_json or {}
                try:
                    same_version = int(detail.get("version")) == int(leave.version or 0)
                except (TypeError, ValueError):
                    same_version = False
                same_file = str(detail.get("evidenceFileId") or "") == str(leave.file_id)
                same_actor = (
                    str(detail.get("operatorUserId") or "") == actor_id
                    if actor_id else (trail.operator_name or "") == operator
                )
                if same_version and same_file and same_actor:
                    viewed_ids.add(leave.id)
        result = []
        for leave, record, student in rows:
            key = (leave.internship_id, leave.leave_type, leave.start_date, leave.end_date)
            previous = previous_map.get(key)
            if previous and previous.id == leave.id:
                previous = None
            result.append(_row(
                leave, record, student, db=db, user=user,
                previous=previous, evidence_viewed=leave.id in viewed_ids,
                preloaded=True,
            ))
        return result, total
'''
    text = replace_function(text, "list_leaves", list_block)
    write(rel, text)


def patch_makeup() -> None:
    rel = "backend/app/modules/internship/services/internship_makeup_service.py"
    text = read(rel)
    text = patch_import(text, "from sqlalchemy import select", "from sqlalchemy import func, select")

    row_block = '''def _row(m: InternshipMakeup, rec, stu, *, db=None, user=None,
         evidence_file_id=None, previous=None, evidence_viewed=None,
         preloaded: bool = False) -> dict:
    if not preloaded:
        evidence_file_id = _evidence_file_id(db, m) if db is not None else ""
        previous = _previous_rejection(db, m) if db is not None else None
        evidence_viewed = (
            _evidence_viewed(db, m, user, evidence_file_id)
            if db is not None and user else False)
    evidence_file_id = str(evidence_file_id or "")
    return {
        "id": str(m.id), "internId": str(m.internship_id),
        "studentName": stu.real_name if stu else "-", "studentNo": stu.student_no if stu else "-",
        "advisorName": rec.advisor_name if rec else "", "checkinDate": m.checkin_date,
        "makeupType": m.makeup_type, "makeupTypeLabel": TYPE_LABEL.get(m.makeup_type, m.makeup_type),
        "reason": m.reason, "status": m.status, "statusLabel": STATUS_LABEL.get(m.status, m.status),
        "applyBy": m.apply_by_name or "", "reviewBy": m.review_by_name or "",
        "reviewComment": m.review_comment or "", "reviewAt": _iso(m.review_at) or "",
        "version": int(m.version or 0),
        "createdAt": _iso(m.created_at) or "", "submittedAt": _iso(m.created_at) or "",
        "evidenceFileId": evidence_file_id, "hasEvidence": bool(evidence_file_id),
        "evidenceRequired": _evidence_required(m.makeup_type),
        "evidenceRequirementLabel": _evidence_requirement_label(m.makeup_type),
        "evidenceViewed": bool(evidence_viewed),
        "previousReviewComment": previous.review_comment or "" if previous else "",
        "previousReviewAt": _iso(previous.review_at) or "" if previous else "",
    }
'''
    text = replace_function(text, "_row", row_block)

    list_block = '''def list_makeups(page, page_size, status=None, batch_id=None, user=None) -> tuple[list[dict], int]:
    from app.modules.internship.services.internship_batch_context import resolve_batch
    from app.modules.internship.services.internship_scope import apply_internship_record_scope

    with session() as db:
        batch = resolve_batch(db, batch_id)
        scoped = apply_internship_record_scope(
            select(InternshipRecord.id).where(
                InternshipRecord.tenant_id == _tid(),
                InternshipRecord.batch_id == batch.id,
                InternshipRecord.is_deleted.is_(False)), user).subquery()
        query = select(InternshipMakeup, InternshipRecord, StudentProfile).join(
            InternshipRecord, InternshipRecord.id == InternshipMakeup.internship_id
        ).join(
            StudentProfile, StudentProfile.id == InternshipMakeup.student_id
        ).where(
            InternshipMakeup.tenant_id == _tid(),
            InternshipMakeup.is_deleted.is_(False),
            InternshipMakeup.internship_id.in_(select(scoped.c.id)),
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.batch_id == batch.id,
            InternshipRecord.is_deleted.is_(False),
            StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False),
        )
        if status:
            query = query.where(InternshipMakeup.status == status)
        total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
        size = max(0, int(page_size or 0))
        if size == 0:
            return [], total
        rows = db.execute(
            query.order_by(InternshipMakeup.id.desc())
            .offset((max(1, int(page or 1)) - 1) * size).limit(size)
        ).all()
        makeups = [item[0] for item in rows]
        ids = [item.id for item in makeups]
        evidence_map = {}
        viewed_ids = set()
        if ids:
            trails = db.scalars(select(InternshipAuditTrail).where(
                InternshipAuditTrail.tenant_id == _tid(),
                InternshipAuditTrail.target_type == "MAKEUP",
                InternshipAuditTrail.target_id.in_(ids),
                InternshipAuditTrail.action.in_((*_EVIDENCE_ACTIONS, "EVIDENCE_VIEW")),
            ).order_by(InternshipAuditTrail.id.desc())).all()
            actor_id = _actor_id(user) if user else ""
            operator = _op_name(user) if user else ""
            by_id = {item.id: item for item in makeups}
            for trail in trails:
                detail = trail.detail_json or {}
                if trail.action in _EVIDENCE_ACTIONS:
                    file_id = str(detail.get("evidenceFileId") or detail.get("fileId") or "").strip()
                    if file_id:
                        evidence_map.setdefault(trail.target_id, file_id)
            for trail in trails:
                if trail.action != "EVIDENCE_VIEW" or not user:
                    continue
                makeup = by_id.get(trail.target_id)
                file_id = evidence_map.get(trail.target_id, "")
                if not makeup or not file_id:
                    continue
                detail = trail.detail_json or {}
                try:
                    same_version = int(detail.get("version")) == int(makeup.version or 0)
                except (TypeError, ValueError):
                    same_version = False
                same_file = str(detail.get("evidenceFileId") or "") == file_id
                same_actor = (
                    str(detail.get("operatorUserId") or "") == actor_id
                    if actor_id else (trail.operator_name or "") == operator
                )
                if same_version and same_file and same_actor:
                    viewed_ids.add(makeup.id)
        previous_map = {}
        if makeups:
            internship_ids = {item.internship_id for item in makeups}
            rejected = db.scalars(select(InternshipMakeup).where(
                InternshipMakeup.tenant_id == _tid(),
                InternshipMakeup.internship_id.in_(internship_ids),
                InternshipMakeup.status == "REJECTED",
                InternshipMakeup.is_deleted.is_(False),
            ).order_by(InternshipMakeup.id.desc())).all()
            for item in rejected:
                key = (item.internship_id, item.checkin_date, item.makeup_type)
                previous_map.setdefault(key, item)
        result = []
        for makeup, record, student in rows:
            key = (makeup.internship_id, makeup.checkin_date, makeup.makeup_type)
            previous = previous_map.get(key)
            if previous and previous.id == makeup.id:
                previous = None
            result.append(_row(
                makeup, record, student, db=db, user=user,
                evidence_file_id=evidence_map.get(makeup.id, ""),
                previous=previous, evidence_viewed=makeup.id in viewed_ids,
                preloaded=True,
            ))
        return result, total
'''
    text = replace_function(text, "list_makeups", list_block)
    write(rel, text)


def patch_insurance() -> None:
    rel = "backend/app/modules/internship/services/internship_insurance_service.py"
    text = read(rel)
    text = patch_import(text, "from sqlalchemy import select", "from sqlalchemy import func, or_, select")
    block = '''def list_insurances(page, page_size, status=None, keyword=None, batch_id=None, user=None):
    from app.modules.internship.services.internship_batch_context import resolve_batch
    from app.modules.internship.services.internship_scope import apply_internship_record_scope

    with session() as db:
        batch = resolve_batch(db, batch_id)
        scoped = apply_internship_record_scope(
            select(InternshipRecord.id).where(
                InternshipRecord.tenant_id == _tid(),
                InternshipRecord.batch_id == batch.id,
                InternshipRecord.is_deleted.is_(False)), user).subquery()
        query = select(InternshipInsurance, InternshipRecord, StudentProfile).join(
            InternshipRecord, InternshipRecord.id == InternshipInsurance.internship_id
        ).join(
            StudentProfile, StudentProfile.id == InternshipInsurance.student_id
        ).where(
            InternshipInsurance.tenant_id == _tid(),
            InternshipInsurance.is_deleted.is_(False),
            InternshipInsurance.internship_id.in_(select(scoped.c.id)),
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.batch_id == batch.id,
            InternshipRecord.is_deleted.is_(False),
            StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False),
        )
        if status:
            query = query.where(InternshipInsurance.status == status)
        term = str(keyword or "").strip()
        if term:
            like = f"%{term}%"
            query = query.where(or_(
                StudentProfile.real_name.like(like),
                StudentProfile.student_no.like(like),
                InternshipInsurance.policy_no.like(like),
            ))
        total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
        size = max(0, int(page_size or 0))
        if size == 0:
            return [], total
        rows = db.execute(
            query.order_by(InternshipInsurance.id.desc())
            .offset((max(1, int(page or 1)) - 1) * size).limit(size)
        ).all()
        return [_row(insurance, record, student)
                for insurance, record, student in rows], total
'''
    text = replace_function(text, "list_insurances", block)
    write(rel, text)


def patch_application() -> None:
    rel = "backend/app/modules/internship/services/internship_application_service.py"
    text = read(rel)
    text = patch_import(text, "from sqlalchemy import select", "from sqlalchemy import func, or_, select")

    row_block = '''def _row(db, app: InternshipApplication, rec=None, stu=None, *,
         pos=None, company=None, preloaded: bool = False) -> dict:
    rec = rec or db.get(InternshipRecord, app.record_id)
    stu = stu or db.get(StudentProfile, app.student_id)
    if not preloaded:
        pos = db.get(InternshipPosition, app.position_id) if app.position_id else None
        company = db.get(EmpCompany, pos.company_id) if pos else None
    return {
        "id": str(app.id), "recordId": str(app.record_id), "studentId": str(app.student_id),
        "studentName": stu.real_name if stu else "-", "studentNo": stu.student_no if stu else "-",
        "advisorName": rec.advisor_name if rec else "", "applicationType": app.application_type,
        "applicationTypeLabel": TYPE_LABEL.get(app.application_type, app.application_type),
        "volunteerNo": app.volunteer_no, "positionId": str(app.position_id) if app.position_id else "",
        "companyName": app.company_name or (company.name if company else ""),
        "positionName": app.position_name or (pos.title if pos else ""),
        "workAddress": app.work_address or (pos.work_location if pos else "") or "",
        "contactName": app.contact_name or "", "contactPhone": app.contact_phone or "",
        "evidenceFileId": app.evidence_file_id or "", "applicationNote": app.application_note or "",
        "status": app.status, "statusLabel": STATUS_LABEL.get(app.status, app.status),
        "submittedAt": _iso(app.submitted_at) or "", "reviewedBy": app.reviewed_by_name or "",
        "reviewedAt": _iso(app.reviewed_at) or "", "reviewComment": app.review_comment or "",
        "version": int(app.version or 0),
        "recordVersion": int(rec.version or 0) if rec else None,
        "createdAt": _iso(app.created_at) or "",
    }
'''
    text = replace_function(text, "_row", row_block)

    list_block = '''def list_applications(page: int, page_size: int, status=None, application_type=None, keyword=None,
                      batch_id=None, user: dict | None = None) -> tuple[list[dict], int]:
    from app.modules.internship.services.internship_batch_context import resolve_batch
    from app.modules.internship.services.internship_scope import apply_internship_record_scope

    with session() as db:
        batch = resolve_batch(db, batch_id)
        scoped = apply_internship_record_scope(
            select(InternshipRecord.id).where(
                InternshipRecord.tenant_id == _tid(),
                InternshipRecord.batch_id == batch.id,
                InternshipRecord.is_deleted.is_(False)), user).subquery()
        query = select(
            InternshipApplication, InternshipRecord, StudentProfile,
            InternshipPosition, EmpCompany,
        ).join(
            InternshipRecord, InternshipRecord.id == InternshipApplication.record_id
        ).join(
            StudentProfile, StudentProfile.id == InternshipApplication.student_id
        ).outerjoin(
            InternshipPosition, InternshipPosition.id == InternshipApplication.position_id
        ).outerjoin(
            EmpCompany, EmpCompany.id == InternshipPosition.company_id
        ).where(
            InternshipApplication.tenant_id == _tid(),
            InternshipApplication.is_deleted.is_(False),
            InternshipApplication.record_id.in_(select(scoped.c.id)),
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.batch_id == batch.id,
            InternshipRecord.is_deleted.is_(False),
            StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False),
        )
        if status:
            query = query.where(InternshipApplication.status == status)
        if application_type:
            query = query.where(InternshipApplication.application_type == application_type)
        term = str(keyword or "").strip()
        if term:
            like = f"%{term}%"
            query = query.where(or_(
                StudentProfile.real_name.like(like),
                StudentProfile.student_no.like(like),
                InternshipApplication.company_name.like(like),
                InternshipApplication.position_name.like(like),
            ))
        total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
        size = max(0, int(page_size or 0))
        if size == 0:
            return [], total
        rows = db.execute(
            query.order_by(
                InternshipApplication.submitted_at.desc(),
                InternshipApplication.id.desc(),
            ).offset((max(1, int(page or 1)) - 1) * size).limit(size)
        ).all()
        return [
            _row(db, application, record, student,
                 pos=position, company=company, preloaded=True)
            for application, record, student, position, company in rows
        ], total
'''
    text = replace_function(text, "list_applications", list_block)
    write(rel, text)


def add_tests() -> None:
    rel = "backend/tests/test_internship_sql_pagination_static.py"
    path = ROOT / rel
    content = '''from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _function(path, name, next_name):
    text = (ROOT / path).read_text(encoding="utf-8")
    return text[text.index(f"def {name}"):text.index(f"def {next_name}")]


def test_management_ledgers_paginate_in_mysql():
    cases = (
        ("backend/app/modules/internship/services/internship_leave_service.py", "list_leaves", "get_leave"),
        ("backend/app/modules/internship/services/internship_makeup_service.py", "list_makeups", "get_makeup"),
        ("backend/app/modules/internship/services/internship_insurance_service.py", "list_insurances", "student_submit"),
        ("backend/app/modules/internship/services/internship_application_service.py", "list_applications", "get_application"),
    )
    for path, name, next_name in cases:
        block = _function(path, name, next_name)
        assert "apply_internship_record_scope" in block
        assert ".offset(" in block and ".limit(" in block
        assert "select(func.count())" in block
        assert "items[start:start + page_size]" not in block


def test_leave_and_makeup_page_rows_batch_prefetch_evidence():
    leave = _function(
        "backend/app/modules/internship/services/internship_leave_service.py",
        "list_leaves", "get_leave")
    makeup = _function(
        "backend/app/modules/internship/services/internship_makeup_service.py",
        "list_makeups", "get_makeup")
    assert "target_id.in_(ids)" in leave
    assert "target_id.in_(ids)" in makeup
    assert "preloaded=True" in leave and "preloaded=True" in makeup


def test_application_list_joins_position_and_company():
    block = _function(
        "backend/app/modules/internship/services/internship_application_service.py",
        "list_applications", "get_application")
    assert "outerjoin(" in block
    assert "InternshipPosition" in block and "EmpCompany" in block
    assert "preloaded=True" in block
'''
    if not path.exists() or path.read_text(encoding="utf-8") != content:
        path.write_text(content, encoding="utf-8")
        CHANGED.append(rel)


def main() -> None:
    patch_leave()
    patch_makeup()
    patch_insurance()
    patch_application()
    add_tests()
    for rel in CHANGED:
        if rel.endswith(".py"):
            ast.parse(read(rel), filename=rel)
    print("changed files:")
    for rel in CHANGED:
        print(f" - {rel}")
    if not CHANGED:
        print("SQL pagination patch already applied")


if __name__ == "__main__":
    main()
