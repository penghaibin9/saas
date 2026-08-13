"""开题审核 SQL 读模型：真分页、统一批次/数据范围、NOT EXISTS 未提交派生。"""
from __future__ import annotations

from sqlalchemy import and_, exists, false, func, or_, select

from app.core.context import get_current_user_ctx
from app.models import (
    GraduationDefenseGroup,
    GraduationMentor,
    GraduationProposal,
    GraduationReview,
    GraduationStudent,
    StudentProfile,
)
from app.modules.graduation.services.graduation_scope_service import (
    COLLEGE_SCOPE_ROLES,
    FULL_SCOPE_ROLES,
    MAJOR_SCOPE_ROLES,
    _claim_id_set,
    _ctx,
    _login_name,
    _name_is_ambiguous,
    _student_self_identity,
)
from app.services.db_service import _iso

L_MAT = {"PENDING_REVIEW": "待审阅", "APPROVED": "已通过", "REJECTED": "已驳回", "NOT_SUBMITTED": "未提交"}


def _int_claims(values: set[str]) -> set[int]:
    out: set[int] = set()
    for value in values:
        try:
            out.add(int(value))
        except (TypeError, ValueError):
            continue
    return out


def student_scope_select(db, tenant_id: int, batch_id=None):
    """返回当前毕设身份可见 GraduationStudent.id 的 SQL SELECT；不 materialize 全批学生。"""
    tenant_id = int(tenant_id)
    user = get_current_user_ctx() or {}
    role, real_name = _ctx()
    base = [
        GraduationStudent.tenant_id == tenant_id,
        GraduationStudent.is_deleted.is_(False),
        GraduationStudent.record_status == "ACTIVE",
    ]
    if batch_id not in (None, ""):
        base.append(GraduationStudent.batch_id == int(batch_id))

    if role in FULL_SCOPE_ROLES:
        scope = and_(*base)
    elif role == "STUDENT":
        student_no, profile_id = _student_self_identity(db, tenant_id)
        if student_no:
            scope = and_(*base, GraduationStudent.student_no == student_no)
        elif profile_id is not None:
            scope = and_(*base, GraduationStudent.student_id == int(profile_id))
        else:
            scope = and_(*base, false())
    elif role in COLLEGE_SCOPE_ROLES:
        allowed_raw = _claim_id_set(user, "collegeId", "collegeIds")
        allowed_int = _int_claims(allowed_raw)
        if not allowed_raw:
            scope = and_(*base, false())
        else:
            profile_hit = exists(select(StudentProfile.id).where(
                StudentProfile.id == GraduationStudent.student_id,
                StudentProfile.tenant_id == tenant_id,
                StudentProfile.is_deleted.is_(False),
                StudentProfile.college_id.in_(allowed_int or [-1]),
            ))
            scope = and_(
                *base,
                or_(
                    GraduationStudent.college_id.in_(sorted(allowed_raw)),
                    and_(
                        or_(GraduationStudent.college_id.is_(None), GraduationStudent.college_id == ""),
                        profile_hit,
                    ),
                ),
            )
    elif role in MAJOR_SCOPE_ROLES:
        allowed_raw = _claim_id_set(user, "majorId", "majorIds")
        allowed_int = _int_claims(allowed_raw)
        if not allowed_raw:
            scope = and_(*base, false())
        else:
            profile_hit = exists(select(StudentProfile.id).where(
                StudentProfile.id == GraduationStudent.student_id,
                StudentProfile.tenant_id == tenant_id,
                StudentProfile.is_deleted.is_(False),
                StudentProfile.major_id.in_(allowed_int or [-1]),
            ))
            scope = and_(
                *base,
                or_(
                    GraduationStudent.major_id.in_(sorted(allowed_raw)),
                    and_(
                        or_(GraduationStudent.major_id.is_(None), GraduationStudent.major_id == ""),
                        profile_hit,
                    ),
                ),
            )
    elif role in {"GD_MENTOR", "COUNSELOR"}:
        login_name = _login_name()
        mentor_ids = select(GraduationMentor.id).where(
            GraduationMentor.tenant_id == tenant_id,
            GraduationMentor.teacher_no == login_name,
            GraduationMentor.is_deleted.is_(False),
        ) if login_name else select(GraduationMentor.id).where(false())
        stable = GraduationStudent.mentor_id.in_(mentor_ids)
        historical = false()
        if real_name and not _name_is_ambiguous(db, tenant_id, real_name):
            historical = and_(GraduationStudent.mentor_id.is_(None), GraduationStudent.advisor_name == real_name)
        scope = and_(*base, or_(stable, historical))
    elif role == "GD_REVIEWER":
        login_name = _login_name()
        if not login_name:
            scope = and_(*base, false())
        else:
            mentor_ids = select(GraduationMentor.id).where(
                GraduationMentor.tenant_id == tenant_id,
                GraduationMentor.teacher_no == login_name,
                GraduationMentor.is_deleted.is_(False),
            )
            review_hit = exists(select(GraduationReview.id).where(
                GraduationReview.tenant_id == tenant_id,
                GraduationReview.gd_student_id == GraduationStudent.id,
                GraduationReview.reviewer_mentor_id.in_(mentor_ids),
                GraduationReview.is_deleted.is_(False),
            ))
            scope = and_(*base, review_hit)
    elif role in {"GD_DEFENSE_SECRETARY", "GD_DEFENSE_EXPERT"}:
        login_name = _login_name()
        mentor_ids = select(GraduationMentor.id).where(
            GraduationMentor.tenant_id == tenant_id,
            GraduationMentor.teacher_no == login_name,
            GraduationMentor.is_deleted.is_(False),
        ) if login_name else select(GraduationMentor.id).where(false())
        group_base = [
            GraduationDefenseGroup.id == GraduationStudent.defense_group_id,
            GraduationDefenseGroup.tenant_id == tenant_id,
            GraduationDefenseGroup.is_deleted.is_(False),
        ]
        if role == "GD_DEFENSE_SECRETARY":
            relation = GraduationDefenseGroup.secretary_mentor_id.in_(mentor_ids)
        else:
            expert_id = str(user.get("expertId") or "").strip()
            relation_terms = [GraduationDefenseGroup.chair_mentor_id.in_(mentor_ids)]
            # members_json stores mentorId/expertId as strings; JSON_SEARCH is MySQL 8 authoritative.
            mentor = db.scalars(select(GraduationMentor).where(
                GraduationMentor.tenant_id == tenant_id,
                GraduationMentor.teacher_no == login_name,
                GraduationMentor.is_deleted.is_(False),
            ).limit(1)).first() if login_name else None
            if mentor is not None:
                relation_terms.append(func.json_search(
                    GraduationDefenseGroup.members_json, "one", str(mentor.id), None, "$[*].mentorId"
                ).is_not(None))
            if expert_id:
                relation_terms.append(func.json_search(
                    GraduationDefenseGroup.members_json, "one", expert_id, None, "$[*].expertId"
                ).is_not(None))
            relation = or_(*relation_terms)
        group_hit = exists(select(GraduationDefenseGroup.id).where(*group_base, relation))
        scope = and_(*base, group_hit)
    else:
        scope = and_(*base, false())

    return select(GraduationStudent.id).where(scope)


def _keyword_filter(keyword: str | None):
    kw = (keyword or "").strip()
    if not kw:
        return None
    return or_(
        GraduationStudent.name.contains(kw),
        GraduationStudent.student_no.contains(kw),
        GraduationStudent.topic_title.contains(kw),
    )


def _submitted_where(db, tenant_id: int, *, keyword=None, status=None, batch_id=None):
    scope = student_scope_select(db, tenant_id, batch_id=batch_id)
    conds = [
        GraduationProposal.tenant_id == int(tenant_id),
        GraduationProposal.is_deleted.is_(False),
        GraduationStudent.id.in_(scope),
    ]
    if status:
        conds.append(GraduationProposal.status == status)
    keyword_cond = _keyword_filter(keyword)
    if keyword_cond is not None:
        conds.append(keyword_cond)
    return conds


def _submitted_count(db, tenant_id: int, *, keyword=None, status=None, batch_id=None) -> int:
    conds = _submitted_where(db, tenant_id, keyword=keyword, status=status, batch_id=batch_id)
    return int(db.scalar(
        select(func.count()).select_from(GraduationProposal)
        .join(GraduationStudent, GraduationStudent.id == GraduationProposal.gd_student_id)
        .where(*conds)
    ) or 0)


def _proposal_row(p: GraduationProposal, stu: GraduationStudent) -> dict:
    return {
        "id": str(p.id), "projectId": str(p.gd_student_id), "studentName": stu.name,
        "className": stu.class_name or "", "topicTitle": stu.topic_title or "",
        "advisorName": stu.advisor_name or "", "version": p.version or "—",
        "isResubmit": p.is_resubmit, "submitAt": _iso(p.submit_at) or "",
        "attachments": len(p.attachments_json or []), "status": p.status,
        "statusLabel": L_MAT.get(p.status, p.status),
    }


def _submitted_page(db, tenant_id: int, *, offset: int, limit: int, keyword=None, status=None, batch_id=None):
    if limit <= 0:
        return []
    conds = _submitted_where(db, tenant_id, keyword=keyword, status=status, batch_id=batch_id)
    rows = db.execute(
        select(GraduationProposal, GraduationStudent)
        .join(GraduationStudent, GraduationStudent.id == GraduationProposal.gd_student_id)
        .where(*conds)
        .order_by(GraduationProposal.id.desc())
        .offset(max(0, int(offset))).limit(int(limit))
    ).all()
    return [_proposal_row(p, stu) for p, stu in rows]


def _not_submitted_where(db, tenant_id: int, *, keyword=None, batch_id=None):
    scope = student_scope_select(db, tenant_id, batch_id=batch_id)
    proposal_exists = exists(select(GraduationProposal.id).where(
        GraduationProposal.tenant_id == int(tenant_id),
        GraduationProposal.gd_student_id == GraduationStudent.id,
        GraduationProposal.is_deleted.is_(False),
    ))
    confirmed_topic = or_(
        GraduationStudent.topic_id.is_not(None),
        and_(GraduationStudent.stage.is_not(None), GraduationStudent.stage.not_in(("TOPIC_SELECTING", ""))),
    )
    conds = [GraduationStudent.id.in_(scope), confirmed_topic, ~proposal_exists]
    keyword_cond = _keyword_filter(keyword)
    if keyword_cond is not None:
        conds.append(keyword_cond)
    return conds


def count_not_submitted(db, tenant_id: int, *, keyword=None, batch_id=None) -> int:
    return int(db.scalar(
        select(func.count()).select_from(GraduationStudent).where(
            *_not_submitted_where(db, tenant_id, keyword=keyword, batch_id=batch_id)
        )
    ) or 0)


def _not_submitted_row(stu: GraduationStudent) -> dict:
    return {
        "id": f"S{stu.id}", "projectId": str(stu.id), "gdStudentId": str(stu.id),
        "studentName": stu.name, "className": stu.class_name or "",
        "topicTitle": stu.topic_title or "（未确认选题）", "advisorName": stu.advisor_name or "",
        "version": "—", "isResubmit": False, "submitAt": "", "attachments": 0,
        "status": "NOT_SUBMITTED", "statusLabel": L_MAT["NOT_SUBMITTED"],
    }


def _not_submitted_page(db, tenant_id: int, *, offset: int, limit: int, keyword=None, batch_id=None):
    if limit <= 0:
        return []
    rows = db.scalars(
        select(GraduationStudent)
        .where(*_not_submitted_where(db, tenant_id, keyword=keyword, batch_id=batch_id))
        .order_by(GraduationStudent.id)
        .offset(max(0, int(offset))).limit(int(limit))
    ).all()
    return [_not_submitted_row(stu) for stu in rows]


def status_count(db, tenant_id: int, status: str, *, batch_id=None) -> int:
    return _submitted_count(db, tenant_id, status=status, batch_id=batch_id)


def list_proposals(db, tenant_id: int, page: int, page_size: int, *, keyword=None, status=None, batch_id=None):
    page = max(1, int(page or 1))
    page_size = max(1, int(page_size or 20))
    offset = (page - 1) * page_size
    status = (status or "").strip().upper()

    if status == "NOT_SUBMITTED":
        total = count_not_submitted(db, tenant_id, keyword=keyword, batch_id=batch_id)
        return _not_submitted_page(
            db, tenant_id, offset=offset, limit=page_size, keyword=keyword, batch_id=batch_id
        ), total

    if status:
        total = _submitted_count(db, tenant_id, keyword=keyword, status=status, batch_id=batch_id)
        return _submitted_page(
            db, tenant_id, offset=offset, limit=page_size, keyword=keyword, status=status, batch_id=batch_id
        ), total

    submitted_total = _submitted_count(db, tenant_id, keyword=keyword, batch_id=batch_id)
    missing_total = count_not_submitted(db, tenant_id, keyword=keyword, batch_id=batch_id)
    total = submitted_total + missing_total
    rows: list[dict] = []
    if offset < submitted_total:
        take = min(page_size, submitted_total - offset)
        rows.extend(_submitted_page(
            db, tenant_id, offset=offset, limit=take, keyword=keyword, batch_id=batch_id
        ))
        remain = page_size - len(rows)
        if remain > 0:
            rows.extend(_not_submitted_page(
                db, tenant_id, offset=0, limit=remain, keyword=keyword, batch_id=batch_id
            ))
    elif offset < total:
        rows.extend(_not_submitted_page(
            db, tenant_id, offset=offset - submitted_total, limit=page_size,
            keyword=keyword, batch_id=batch_id,
        ))
    return rows, total


def proposal_stats(db, tenant_id: int, *, batch_id=None) -> dict:
    total = _submitted_count(db, tenant_id, batch_id=batch_id)
    by_status = [
        {"status": status, "label": L_MAT[status],
         "count": _submitted_count(db, tenant_id, status=status, batch_id=batch_id)}
        for status in ("PENDING_REVIEW", "APPROVED", "REJECTED")
    ]
    return {
        "total": total,
        "byStatus": by_status,
        "notSubmitted": count_not_submitted(db, tenant_id, batch_id=batch_id),
        "batchId": str(batch_id) if batch_id else None,
    }


def iter_proposals(db, tenant_id: int, *, keyword=None, status=None, batch_id=None, chunk_size: int = 200):
    page = 1
    written = 0
    total = None
    while True:
        rows, current_total = list_proposals(
            db, tenant_id, page, chunk_size, keyword=keyword, status=status, batch_id=batch_id
        )
        if total is None:
            total = current_total
        if not rows:
            break
        for row in rows:
            yield row
            written += 1
        if written >= current_total:
            break
        page += 1
