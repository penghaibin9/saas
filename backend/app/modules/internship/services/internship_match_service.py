"""岗位实习中心 · 岗位匹配服务。

意向收集 → 规则评分匹配（专业/企业/手动/批量）→ 冲突检测 → 确认落岗（复用 assign_position）。
评分：专业命中+60 · 意向城市+15 · 意向企业+15 · 有余量+10。
超额/已分配标 conflict，不得自动 confirm。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, or_, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.models import (EmpCompany, InternshipAuditTrail, InternshipIntention, InternshipMatch,
                        InternshipPosition, InternshipRecord, Major, StudentProfile)
from app.modules.internship.services import internship_student_service as student_svc
from app.services import xlsx_util
from app.services.db_service import _as_id, _iso, _tid, session

INTENTION_LABEL = {"DRAFT": "草稿", "SUBMITTED": "已提交", "WITHDRAWN": "已撤回"}
MATCH_STATUS_LABEL = {
    "RECOMMENDED": "已推荐", "PENDING_CONFIRM": "待确认", "CONFIRMED": "已确认",
    "REJECTED": "已驳回", "CONFLICT": "冲突", "CANCELLED": "已取消",
}
MATCH_STATUS_TONE = {
    "RECOMMENDED": "info", "PENDING_CONFIRM": "warning", "CONFIRMED": "success",
    "REJECTED": "default", "CONFLICT": "danger", "CANCELLED": "default",
}
MATCH_TYPE_LABEL = {
    "AUTO_MAJOR": "专业匹配", "AUTO_ENTERPRISE": "企业匹配",
    "MANUAL": "手动匹配", "BATCH": "批量匹配",
}
ACTIVE_MATCH = ("RECOMMENDED", "PENDING_CONFIRM", "CONFLICT")


def _op_name() -> str:
    u = get_current_user_ctx() or {}
    return u.get("realName") or "系统"


def _trail(db, target_id: int, action: str, detail: dict | None = None):
    db.add(InternshipAuditTrail(
        tenant_id=_tid(), target_id=target_id, target_type="MATCH",
        action=action, operator_name=_op_name(), detail_json=detail or {},
        occurred_at=datetime.utcnow()))


def _get_intention(db, iid) -> InternshipIntention:
    row = db.get(InternshipIntention, _as_id(iid))
    if not row or row.is_deleted or row.tenant_id != _tid():
        raise not_found("意向不存在或不在当前数据范围内")
    return row


def _get_match(db, mid) -> InternshipMatch:
    row = db.get(InternshipMatch, _as_id(mid))
    if not row or row.is_deleted or row.tenant_id != _tid():
        raise not_found("匹配记录不存在或不在当前数据范围内")
    return row


def _get_record(db, rid) -> InternshipRecord:
    r = db.get(InternshipRecord, _as_id(rid))
    if not r or r.is_deleted or r.tenant_id != _tid():
        raise not_found("实习学生记录不存在或不在当前数据范围内")
    return r


def _major_name(db, student: StudentProfile | None) -> str:
    if not student or not student.major_id:
        return ""
    m = db.get(Major, student.major_id)
    return (m.major_name if m and not m.is_deleted else "") or ""


def _major_hit(major_name: str, requirement: str) -> bool:
    maj = (major_name or "").strip()
    req = (requirement or "").strip()
    if not req:
        return True  # 岗位不限专业 → 可匹配
    if not maj:
        return False
    return maj in req or req in maj


def _score(intent: InternshipIntention | None, student_major: str,
           pos: InternshipPosition, company: EmpCompany | None) -> tuple[int, bool, bool]:
    major_hit = _major_hit(student_major, pos.major_requirement or "")
    enterprise_hit = False
    score = 0
    if major_hit:
        score += 60
    if intent:
        city = (intent.preferred_city or "").strip()
        if city and (city in (pos.work_location or "") or (pos.work_location or "") in city):
            score += 15
        if intent.preferred_company_id and int(intent.preferred_company_id) == pos.company_id:
            score += 15
            enterprise_hit = True
    remaining = max(0, (pos.headcount or 0) - (pos.allocated_count or 0))
    if remaining > 0 and pos.status == "PUBLISHED":
        score += 10
    return min(100, score), major_hit, enterprise_hit


def _conflict_of(db, record: InternshipRecord, pos: InternshipPosition) -> tuple[bool, str]:
    reasons = []
    if record.position_id:
        reasons.append("学生已分配岗位")
    rem = max(0, (pos.headcount or 0) - (pos.allocated_count or 0))
    if pos.status != "PUBLISHED":
        reasons.append(f"岗位非已上架({pos.status})")
    elif rem <= 0:
        reasons.append("岗位已满员")
    pending = db.scalars(select(InternshipMatch).where(
        InternshipMatch.tenant_id == _tid(), InternshipMatch.is_deleted.is_(False),
        InternshipMatch.record_id == record.id,
        InternshipMatch.status.in_(ACTIVE_MATCH))).all()
    other = [m for m in pending]
    if len(other) >= 1:
        # 调用方写入前若已有其他待确认，标冲突（同一岗位去重在 upsert）
        pass
    return (bool(reasons), "；".join(reasons) if reasons else "")


def _intention_row(db, it: InternshipIntention) -> dict:
    stu = db.get(StudentProfile, it.student_id)
    company_name = ""
    if it.preferred_company_id:
        c = db.get(EmpCompany, it.preferred_company_id)
        company_name = c.name if c else ""
    position_title = ""
    if it.preferred_position_id:
        p = db.get(InternshipPosition, it.preferred_position_id)
        position_title = p.title if p else ""
    return {
        "id": str(it.id), "recordId": str(it.record_id), "studentId": str(it.student_id),
        "studentName": stu.real_name if stu else "-", "studentNo": stu.student_no if stu else "-",
        "majorName": _major_name(db, stu), "batchId": str(it.batch_id) if it.batch_id else "",
        "preferredCity": it.preferred_city or "", "preferredIndustry": it.preferred_industry or "",
        "preferredCompanyId": str(it.preferred_company_id) if it.preferred_company_id else "",
        "preferredCompanyName": company_name,
        "preferredPositionId": str(it.preferred_position_id) if it.preferred_position_id else "",
        "preferredPositionTitle": position_title,
        "intentionNote": it.intention_note or "",
        "status": it.status, "statusLabel": INTENTION_LABEL.get(it.status, it.status),
        "updatedAt": _iso(it.updated_at),
    }


def _match_row(db, m: InternshipMatch) -> dict:
    stu = db.get(StudentProfile, m.student_id)
    pos = db.get(InternshipPosition, m.position_id)
    company = db.get(EmpCompany, m.company_id)
    rec = db.get(InternshipRecord, m.record_id)
    return {
        "id": str(m.id), "recordId": str(m.record_id), "studentId": str(m.student_id),
        "studentName": stu.real_name if stu else "-", "studentNo": stu.student_no if stu else "-",
        "majorName": _major_name(db, stu),
        "positionId": str(m.position_id), "positionTitle": pos.title if pos else "-",
        "majorRequirement": (pos.major_requirement or "") if pos else "",
        "remaining": max(0, (pos.headcount or 0) - (pos.allocated_count or 0)) if pos else 0,
        "companyId": str(m.company_id), "companyName": company.name if company else "-",
        "matchType": m.match_type, "matchTypeLabel": MATCH_TYPE_LABEL.get(m.match_type, m.match_type),
        "score": m.score, "majorHit": bool(m.major_hit), "enterpriseHit": bool(m.enterprise_hit),
        "conflictFlag": bool(m.conflict_flag), "conflictReason": m.conflict_reason or "",
        "status": m.status, "statusLabel": MATCH_STATUS_LABEL.get(m.status, m.status),
        "statusTone": MATCH_STATUS_TONE.get(m.status, "default"),
        "assignedPositionId": str(rec.position_id) if rec and rec.position_id else "",
        "confirmedBy": m.confirmed_by or "", "confirmedAt": _iso(m.confirmed_at),
        "remark": m.remark or "", "updatedAt": _iso(m.updated_at),
    }


# ═══════════ 意向 ═══════════

# ═══════════ 数据范围（P0-D：与 internship_service 同一机制） ═══════════

def _current_scope(user: dict | None = None) -> dict:
    from app.services.mobile_teacher_service import resolve_teacher_scope
    return resolve_teacher_scope(user or get_current_user_ctx() or {})


def _rec_in_scope(scope: dict, db, rec, stu) -> bool:
    """与 internship_service._rec_in_scope 同口径（含缺 college_id 时学院推导）。"""
    from app.modules.internship.services.internship_service import _rec_in_scope as _base
    return _base(scope, db, rec, stu)


def _filter_scope(db, rows, scope):
    """按记录数据范围过滤 意向/匹配 行（二者均有 record_id + student_id）。"""
    if scope.get("mode") != "SCOPED":
        return rows
    out = []
    for r in rows:
        rec = db.get(InternshipRecord, r.record_id)
        stu = db.get(StudentProfile, r.student_id)
        if _rec_in_scope(scope, db, rec, stu):
            out.append(r)
    return out


def list_intentions(page: int, page_size: int, keyword=None, status=None,
                    user=None) -> tuple[list[dict], int]:
    with session() as db:
        q = select(InternshipIntention).where(
            InternshipIntention.tenant_id == _tid(), InternshipIntention.is_deleted.is_(False))
        if status:
            q = q.where(InternshipIntention.status == status)
        rows = db.scalars(q.order_by(InternshipIntention.id.desc())).all()
        rows = _filter_scope(db, rows, _current_scope(user))  # P0-D
        items = [_intention_row(db, r) for r in rows]
        if keyword:
            kw = keyword.strip().lower()
            items = [x for x in items if kw in (x["studentName"] + x["studentNo"]
                                               + x["preferredCity"] + x["preferredIndustry"]).lower()]
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


def create_intention(body, user=None, self_service: bool = False) -> dict:
    with session() as db:
        rec = _get_record(db, body.recordId)
        # self_service=True：学生小程序端已校验本人归属，跳过教师数据范围校验
        if not self_service:
            from app.modules.internship.services.internship_service import assert_student_in_scope
            assert_student_in_scope(db, rec.student_id, user, "该实习学生不在你的数据范围内")
        exists = db.scalars(select(InternshipIntention).where(
            InternshipIntention.tenant_id == _tid(), InternshipIntention.is_deleted.is_(False),
            InternshipIntention.record_id == rec.id,
            InternshipIntention.status.in_(("DRAFT", "SUBMITTED")))).first()
        if exists:
            raise AppException("DATA_CONFLICT", "该学生已有进行中的意向，请先撤回或编辑")
        it = InternshipIntention(
            tenant_id=_tid(), record_id=rec.id, student_id=rec.student_id,
            batch_id=rec.batch_id,
            preferred_city=getattr(body, "preferredCity", None),
            preferred_industry=getattr(body, "preferredIndustry", None),
            preferred_company_id=int(body.preferredCompanyId) if getattr(body, "preferredCompanyId", None) else None,
            preferred_position_id=int(body.preferredPositionId) if getattr(body, "preferredPositionId", None) else None,
            intention_note=getattr(body, "intentionNote", None),
            status="DRAFT",
        )
        db.add(it)
        db.flush()
        _trail(db, it.id, "INTENTION_CREATE", {"recordId": str(rec.id)})
        db.commit()
        db.refresh(it)
        return _intention_row(db, it)


def update_intention(iid, body, user=None, self_service: bool = False) -> dict:
    with session() as db:
        it = _get_intention(db, iid)
        # self_service=True：学生小程序端已校验本人归属，跳过教师数据范围校验
        if not self_service:
            from app.modules.internship.services.internship_service import assert_student_in_scope
            assert_student_in_scope(db, it.student_id, user, "该实习学生不在你的数据范围内")
        if it.status == "WITHDRAWN":
            raise AppException("DATA_CONFLICT", "已撤回意向不可编辑")
        for attr, col in (("preferredCity", "preferred_city"), ("preferredIndustry", "preferred_industry"),
                          ("intentionNote", "intention_note")):
            val = getattr(body, attr, None)
            if val is not None:
                setattr(it, col, val)
        if getattr(body, "preferredCompanyId", None) is not None:
            it.preferred_company_id = int(body.preferredCompanyId) if body.preferredCompanyId else None
        if getattr(body, "preferredPositionId", None) is not None:
            it.preferred_position_id = int(body.preferredPositionId) if body.preferredPositionId else None
        _trail(db, it.id, "INTENTION_UPDATE", {})
        db.commit()
        db.refresh(it)
        return _intention_row(db, it)


def submit_intention(iid, user=None, self_service: bool = False) -> dict:
    with session() as db:
        it = _get_intention(db, iid)
        # self_service=True：学生小程序端已校验本人归属，跳过教师数据范围校验
        if not self_service:
            from app.modules.internship.services.internship_service import assert_student_in_scope
            assert_student_in_scope(db, it.student_id, user, "该实习学生不在你的数据范围内")
        if it.status not in ("DRAFT", "WITHDRAWN"):
            raise AppException("DATA_CONFLICT", f"当前状态不可提交（{it.status}）")
        it.status = "SUBMITTED"
        _trail(db, it.id, "INTENTION_SUBMIT", {})
        db.commit()
        db.refresh(it)
        return _intention_row(db, it)


def withdraw_intention(iid, user=None, self_service: bool = False) -> dict:
    with session() as db:
        it = _get_intention(db, iid)
        # self_service=True：学生小程序端已校验本人归属，跳过教师数据范围校验
        if not self_service:
            from app.modules.internship.services.internship_service import assert_student_in_scope
            assert_student_in_scope(db, it.student_id, user, "该实习学生不在你的数据范围内")
        if it.status != "SUBMITTED":
            raise AppException("DATA_CONFLICT", "仅已提交意向可撤回")
        it.status = "WITHDRAWN"
        _trail(db, it.id, "INTENTION_WITHDRAW", {})
        db.commit()
        db.refresh(it)
        return _intention_row(db, it)


def intention_import_dry_run(rows: list[dict]) -> dict:
    with session() as db:
        errors, valid = [], 0
        for i, r in enumerate(rows or []):
            row_no = i + 1
            sno = (r.get("studentNo") or "").strip()
            if not sno:
                errors.append({"rowNo": row_no, "field": "studentNo", "message": "学号必填"})
                continue
            stu = db.scalars(select(StudentProfile).where(
                StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
                StudentProfile.student_no == sno)).first()
            if not stu:
                errors.append({"rowNo": row_no, "field": "studentNo", "message": "学生主档不存在"})
                continue
            rec = db.scalars(select(InternshipRecord).where(
                InternshipRecord.tenant_id == _tid(), InternshipRecord.is_deleted.is_(False),
                InternshipRecord.student_id == stu.id)).first()
            if not rec:
                errors.append({"rowNo": row_no, "field": "studentNo", "message": "无实习学生记录，请先建档"})
                continue
            valid += 1
        return {"total": len(rows or []), "validRows": valid, "invalidRows": len(errors), "errors": errors}


def intention_import_confirm(rows: list[dict], user=None) -> dict:
    from app.modules.internship.services.internship_service import assert_admin_tenant
    assert_admin_tenant(user, "意向批量导入")
    dry = intention_import_dry_run(rows)
    if dry["invalidRows"]:
        raise AppException("VALIDATION_ERROR", "存在校验失败行，请先修正")
    created = 0
    with session() as db:
        for r in rows or []:
            sno = (r.get("studentNo") or "").strip()
            stu = db.scalars(select(StudentProfile).where(
                StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
                StudentProfile.student_no == sno)).first()
            rec = db.scalars(select(InternshipRecord).where(
                InternshipRecord.tenant_id == _tid(), InternshipRecord.is_deleted.is_(False),
                InternshipRecord.student_id == stu.id)).first()
            company_id = None
            cname = (r.get("company") or "").strip()
            if cname:
                c = db.scalars(select(EmpCompany).where(
                    EmpCompany.tenant_id == _tid(), EmpCompany.is_deleted.is_(False),
                    EmpCompany.name == cname)).first()
                company_id = c.id if c else None
            active = db.scalars(select(InternshipIntention).where(
                InternshipIntention.tenant_id == _tid(), InternshipIntention.is_deleted.is_(False),
                InternshipIntention.record_id == rec.id,
                InternshipIntention.status.in_(("DRAFT", "SUBMITTED")))).first()
            if active:
                active.preferred_city = (r.get("city") or "").strip() or active.preferred_city
                active.preferred_industry = (r.get("industry") or "").strip() or active.preferred_industry
                if company_id:
                    active.preferred_company_id = company_id
                active.intention_note = (r.get("note") or "").strip() or active.intention_note
                active.status = "SUBMITTED"
            else:
                it = InternshipIntention(
                    tenant_id=_tid(), record_id=rec.id, student_id=stu.id, batch_id=rec.batch_id,
                    preferred_city=(r.get("city") or "").strip() or None,
                    preferred_industry=(r.get("industry") or "").strip() or None,
                    preferred_company_id=company_id,
                    intention_note=(r.get("note") or "").strip() or None,
                    status="SUBMITTED",
                )
                db.add(it)
                created += 1
        db.commit()
    return {"created": created, "total": len(rows or [])}


def export_intentions(keyword=None, status=None) -> dict:
    items, _ = list_intentions(1, 5000, keyword=keyword, status=status)
    headers = ["学号", "姓名", "专业", "意向城市", "意向行业", "意向企业", "状态", "备注"]
    rows = [[x["studentNo"], x["studentName"], x["majorName"], x["preferredCity"],
             x["preferredIndustry"], x["preferredCompanyName"], x["statusLabel"],
             x["intentionNote"]] for x in items]
    content = xlsx_util.build_ledger_xlsx("实习意向台账", headers, rows)
    return xlsx_util.pack_xlsx_result(content, "实习意向台账.xlsx", len(rows))


# ═══════════ 匹配引擎 ═══════════

def _upsert_match(db, record: InternshipRecord, pos: InternshipPosition,
                  match_type: str, intent: InternshipIntention | None,
                  student_major: str, status_if_ok: str = "RECOMMENDED") -> InternshipMatch | None:
    company = db.get(EmpCompany, pos.company_id)
    score, major_hit, enterprise_hit = _score(intent, student_major, pos, company)
    conflict, reason = _conflict_of(db, record, pos)
    # 同一学生+岗位活跃态复用
    existing = db.scalars(select(InternshipMatch).where(
        InternshipMatch.tenant_id == _tid(), InternshipMatch.is_deleted.is_(False),
        InternshipMatch.record_id == record.id, InternshipMatch.position_id == pos.id,
        InternshipMatch.status.in_(ACTIVE_MATCH + ("CONFIRMED",)))).first()
    if existing and existing.status == "CONFIRMED":
        return None
    status = "CONFLICT" if conflict else status_if_ok
    if existing:
        existing.match_type = match_type
        existing.score = score
        existing.major_hit = major_hit
        existing.enterprise_hit = enterprise_hit
        existing.conflict_flag = conflict
        existing.conflict_reason = reason or None
        existing.status = status
        existing.company_id = pos.company_id
        return existing
    # 若该生已有其他待确认，新的也标冲突提示（一人多岗）
    others = db.scalars(select(InternshipMatch).where(
        InternshipMatch.tenant_id == _tid(), InternshipMatch.is_deleted.is_(False),
        InternshipMatch.record_id == record.id,
        InternshipMatch.status.in_(ACTIVE_MATCH))).all()
    if others and not conflict:
        conflict = True
        reason = "该学生已有其他待确认匹配"
        status = "CONFLICT"
        for o in others:
            if not o.conflict_flag:
                o.conflict_flag = True
                o.conflict_reason = (o.conflict_reason or "") + ("；一人多岗" if o.conflict_reason else "一人多岗")
                if o.status != "CONFLICT":
                    o.status = "CONFLICT"
    m = InternshipMatch(
        tenant_id=_tid(), record_id=record.id, student_id=record.student_id,
        position_id=pos.id, company_id=pos.company_id, match_type=match_type,
        score=score, major_hit=major_hit, enterprise_hit=enterprise_hit,
        conflict_flag=conflict, conflict_reason=reason or None, status=status,
    )
    db.add(m)
    db.flush()
    return m


def run_major_match(user=None) -> dict:
    """未分配学生 × 已上架岗位 · 专业规则推荐。"""
    from app.modules.internship.services.internship_service import assert_admin_tenant
    assert_admin_tenant(user, "专业自动匹配")
    created = 0
    with session() as db:
        records = db.scalars(select(InternshipRecord).where(
            InternshipRecord.tenant_id == _tid(), InternshipRecord.is_deleted.is_(False),
            InternshipRecord.position_id.is_(None),
            InternshipRecord.status != "ARCHIVED")).all()
        positions = db.scalars(select(InternshipPosition).where(
            InternshipPosition.tenant_id == _tid(), InternshipPosition.is_deleted.is_(False),
            InternshipPosition.status == "PUBLISHED")).all()
        intent_map = {it.record_id: it for it in db.scalars(select(InternshipIntention).where(
            InternshipIntention.tenant_id == _tid(), InternshipIntention.is_deleted.is_(False),
            InternshipIntention.status == "SUBMITTED")).all()}
        for rec in records:
            stu = db.get(StudentProfile, rec.student_id)
            maj = _major_name(db, stu)
            intent = intent_map.get(rec.id)
            # 优先：专业命中岗位；岗位不限专业也可被推（弱）
            candidates = []
            for p in positions:
                hit = _major_hit(maj, p.major_requirement or "")
                if hit and max(0, p.headcount - p.allocated_count) > 0:
                    candidates.append(p)
            # 每生最多推 3 个最高分岗位
            scored = []
            for p in candidates:
                sc, _, _ = _score(intent, maj, p, None)
                scored.append((sc, p))
            scored.sort(key=lambda x: -x[0])
            for _, p in scored[:3]:
                m = _upsert_match(db, rec, p, "AUTO_MAJOR", intent, maj, "RECOMMENDED")
                if m:
                    created += 1
        _trail(db, 0, "RUN_MAJOR_MATCH", {"created": created})
        db.commit()
    return {"created": created}


def run_enterprise_match(user=None) -> dict:
    """按意向 preferred_company_id 推荐该企业下上架岗位。"""
    from app.modules.internship.services.internship_service import assert_admin_tenant
    assert_admin_tenant(user, "企业自动匹配")
    created = 0
    with session() as db:
        intents = db.scalars(select(InternshipIntention).where(
            InternshipIntention.tenant_id == _tid(), InternshipIntention.is_deleted.is_(False),
            InternshipIntention.status == "SUBMITTED",
            InternshipIntention.preferred_company_id.is_not(None))).all()
        for it in intents:
            rec = db.get(InternshipRecord, it.record_id)
            if not rec or rec.is_deleted or rec.position_id:
                continue
            stu = db.get(StudentProfile, rec.student_id)
            maj = _major_name(db, stu)
            positions = db.scalars(select(InternshipPosition).where(
                InternshipPosition.tenant_id == _tid(), InternshipPosition.is_deleted.is_(False),
                InternshipPosition.status == "PUBLISHED",
                InternshipPosition.company_id == it.preferred_company_id)).all()
            for p in positions:
                if max(0, p.headcount - p.allocated_count) <= 0:
                    continue
                m = _upsert_match(db, rec, p, "AUTO_ENTERPRISE", it, maj, "RECOMMENDED")
                if m:
                    created += 1
        _trail(db, 0, "RUN_ENTERPRISE_MATCH", {"created": created})
        db.commit()
    return {"created": created}


def manual_match(record_id, position_id, remark: str = "", user=None) -> dict:
    with session() as db:
        rec = _get_record(db, record_id)
        from app.modules.internship.services.internship_service import assert_student_in_scope
        assert_student_in_scope(db, rec.student_id, user, "该实习学生不在你的数据范围内")
        pos = db.get(InternshipPosition, _as_id(position_id))
        if not pos or pos.is_deleted or pos.tenant_id != _tid():
            raise not_found("岗位不存在")
        stu = db.get(StudentProfile, rec.student_id)
        maj = _major_name(db, stu)
        intent = db.scalars(select(InternshipIntention).where(
            InternshipIntention.tenant_id == _tid(), InternshipIntention.is_deleted.is_(False),
            InternshipIntention.record_id == rec.id,
            InternshipIntention.status == "SUBMITTED")).first()
        m = _upsert_match(db, rec, pos, "MANUAL", intent, maj, "PENDING_CONFIRM")
        if not m:
            raise AppException("DATA_CONFLICT", "该匹配已确认或无法创建")
        if remark:
            m.remark = remark
        _trail(db, m.id, "MANUAL_MATCH", {"positionId": str(pos.id)})
        db.commit()
        db.refresh(m)
        return _match_row(db, m)


def batch_match(pairs: list[dict], user=None) -> dict:
    from app.modules.internship.services.internship_service import assert_admin_tenant
    assert_admin_tenant(user, "批量匹配")
    ok, fail = 0, []
    for i, pair in enumerate(pairs or []):
        try:
            manual_match(pair.get("recordId"), pair.get("positionId"), pair.get("remark") or "", user=user)
            # 批量覆盖 match_type
            with session() as db:
                rec = _get_record(db, pair.get("recordId"))
                m = db.scalars(select(InternshipMatch).where(
                    InternshipMatch.tenant_id == _tid(), InternshipMatch.is_deleted.is_(False),
                    InternshipMatch.record_id == rec.id,
                    InternshipMatch.position_id == int(pair.get("positionId")),
                    InternshipMatch.status.in_(ACTIVE_MATCH))).first()
                if m:
                    m.match_type = "BATCH"
                    db.commit()
            ok += 1
        except Exception as e:  # noqa: BLE001
            fail.append({"rowNo": i + 1, "message": getattr(e, "message", None) or str(e)})
    return {"success": ok, "failed": len(fail), "errors": fail}


def list_matches(page: int, page_size: int, keyword=None, status=None,
                 match_type=None, conflict_only=False, user=None) -> tuple[list[dict], int]:
    with session() as db:
        q = select(InternshipMatch).where(
            InternshipMatch.tenant_id == _tid(), InternshipMatch.is_deleted.is_(False))
        if status:
            q = q.where(InternshipMatch.status == status)
        if match_type:
            q = q.where(InternshipMatch.match_type == match_type)
        if conflict_only:
            q = q.where(or_(InternshipMatch.conflict_flag.is_(True),
                            InternshipMatch.status == "CONFLICT"))
        rows = db.scalars(q.order_by(InternshipMatch.score.desc(), InternshipMatch.id.desc())).all()
        rows = _filter_scope(db, rows, _current_scope(user))  # P0-D
        items = [_match_row(db, r) for r in rows]
        if keyword:
            kw = keyword.strip().lower()
            items = [x for x in items if kw in (
                x["studentName"] + x["studentNo"] + x["positionTitle"] + x["companyName"]).lower()]
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


def list_conflicts(page: int, page_size: int, keyword=None, user=None) -> tuple[list[dict], int]:
    return list_matches(page, page_size, keyword=keyword, conflict_only=True, user=user)


def confirm_match(mid, user=None) -> dict:
    """确认匹配 → 调用已有 assign_position 落岗。"""
    with session() as db:
        m = _get_match(db, mid)
        if m.status not in ("RECOMMENDED", "PENDING_CONFIRM", "CONFLICT"):
            raise AppException("DATA_CONFLICT", f"当前状态不可确认（{m.status}）")
        if m.conflict_flag and m.status == "CONFLICT":
            # 允许人工确认冲突项，但岗位满员/非上架仍由 assign 拦截
            pass
        record_id, position_id = m.record_id, m.position_id
        match_id = m.id
    # assign 使用独立 session；成功后再更新 match（数据范围校验在 assign_position 内部执行）
    student_svc.assign_position(record_id, position_id, user=user)
    with session() as db:
        m = _get_match(db, match_id)
        m.status = "CONFIRMED"
        m.conflict_flag = False
        m.conflict_reason = None
        m.confirmed_by = _op_name()
        m.confirmed_at = datetime.utcnow()
        # 取消同学生其他待确认
        others = db.scalars(select(InternshipMatch).where(
            InternshipMatch.tenant_id == _tid(), InternshipMatch.is_deleted.is_(False),
            InternshipMatch.record_id == m.record_id,
            InternshipMatch.id != m.id,
            InternshipMatch.status.in_(ACTIVE_MATCH))).all()
        for o in others:
            o.status = "CANCELLED"
        _trail(db, m.id, "MATCH_CONFIRM", {"positionId": str(m.position_id)})
        db.commit()
        db.refresh(m)
        return _match_row(db, m)


def reject_match(mid, reason: str = "", user=None) -> dict:
    with session() as db:
        m = _get_match(db, mid)
        from app.modules.internship.services.internship_service import assert_student_in_scope
        assert_student_in_scope(db, m.student_id, user, "该实习学生不在你的数据范围内")
        if m.status not in ("RECOMMENDED", "PENDING_CONFIRM", "CONFLICT"):
            raise AppException("DATA_CONFLICT", f"当前状态不可驳回（{m.status}）")
        m.status = "REJECTED"
        if reason:
            m.remark = reason
        _trail(db, m.id, "MATCH_REJECT", {"reason": reason})
        db.commit()
        db.refresh(m)
        return _match_row(db, m)


def match_stats() -> dict:
    with session() as db:
        base = [InternshipMatch.tenant_id == _tid(), InternshipMatch.is_deleted.is_(False)]
        total = int(db.scalar(select(func.count()).select_from(InternshipMatch).where(*base)) or 0)
        by_status = []
        for st, label in MATCH_STATUS_LABEL.items():
            by_status.append({
                "status": st, "label": label,
                "count": int(db.scalar(select(func.count()).select_from(InternshipMatch).where(
                    *base, InternshipMatch.status == st)) or 0),
            })
        by_type = []
        for mt, label in MATCH_TYPE_LABEL.items():
            by_type.append({
                "matchType": mt, "label": label,
                "count": int(db.scalar(select(func.count()).select_from(InternshipMatch).where(
                    *base, InternshipMatch.match_type == mt)) or 0),
            })
        conflict = int(db.scalar(select(func.count()).select_from(InternshipMatch).where(
            *base, or_(InternshipMatch.conflict_flag.is_(True), InternshipMatch.status == "CONFLICT"))) or 0)
        confirmed = int(db.scalar(select(func.count()).select_from(InternshipMatch).where(
            *base, InternshipMatch.status == "CONFIRMED")) or 0)
        intent_submitted = int(db.scalar(select(func.count()).select_from(InternshipIntention).where(
            InternshipIntention.tenant_id == _tid(), InternshipIntention.is_deleted.is_(False),
            InternshipIntention.status == "SUBMITTED")) or 0)
        return {
            "total": total, "byStatus": by_status, "byType": by_type,
            "conflictCount": conflict, "confirmedCount": confirmed,
            "intentionSubmitted": intent_submitted,
        }


def export_matches(keyword=None, status=None, match_type=None) -> dict:
    items, _ = list_matches(1, 5000, keyword=keyword, status=status, match_type=match_type)
    headers = ["学号", "姓名", "专业", "岗位", "企业", "匹配方式", "得分", "专业命中",
               "冲突", "状态", "备注"]
    rows = [[x["studentNo"], x["studentName"], x["majorName"], x["positionTitle"],
             x["companyName"], x["matchTypeLabel"], x["score"],
             "是" if x["majorHit"] else "否",
             x["conflictReason"] if x["conflictFlag"] else "",
             x["statusLabel"], x["remark"]] for x in items]
    content = xlsx_util.build_ledger_xlsx("岗位匹配台账", headers, rows)
    return xlsx_util.pack_xlsx_result(content, "岗位匹配台账.xlsx", len(rows))
