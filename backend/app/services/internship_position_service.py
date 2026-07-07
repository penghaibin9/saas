"""岗位实习中心 · 岗位库服务（DB_ENABLED=true 走本模块）。

复用共享企业主档 t_emp_company（不重复造企业表）：岗位关联 company_id；
上架强约束——黑名单企业 / 非「合作中」企业不能上架。
状态机：DRAFT→PENDING→PUBLISHED↔OFFLINE↔SUSPENDED，PUBLISHED→FULL，任意→RISK / →ARCHIVED。
横切：租户隔离 + is_deleted 软删 + 审计到 t_internship_audit_trail(target_type=POSITION)。
batch_id 仅预留（nullable），本模块不依赖实习批次模块已完成。

隔离：本文件不引用批次表/服务；企业校验直接读 EmpCompany（不改企业库服务写逻辑）。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, or_, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.models import (EmpCompany, InternshipAuditTrail, InternshipEnterpriseContact,
                        InternshipPosition)
from app.services.db_service import _iso, _tid, session

STATUS_LABEL = {"DRAFT": "草稿", "PENDING": "待审核", "PUBLISHED": "已上架", "OFFLINE": "已下架",
                "SUSPENDED": "已暂停", "FULL": "已满员", "RISK": "风险岗位", "ARCHIVED": "已归档"}
STATUS_TONE = {"DRAFT": "default", "PENDING": "warning", "PUBLISHED": "success", "OFFLINE": "default",
               "SUSPENDED": "warning", "FULL": "primary", "RISK": "danger", "ARCHIVED": "default"}
COOP_LABEL = {"PENDING": "待审核", "ACTIVE": "合作中", "REJECTED": "已驳回",
              "SUSPENDED": "已暂停", "BLACKLIST": "黑名单", "ARCHIVED": "已归档"}


def _op_name() -> str:
    u = get_current_user_ctx() or {}
    return u.get("realName") or "系统"


def _trail(db, pos_id: int, action: str, detail: dict | None = None):
    db.add(InternshipAuditTrail(tenant_id=_tid(), target_id=pos_id, target_type="POSITION",
                                action=action, operator_name=_op_name(), detail_json=detail or {},
                                occurred_at=datetime.utcnow()))


def _company(db, company_id) -> EmpCompany:
    c = db.get(EmpCompany, int(company_id))
    if not c or c.is_deleted or c.tenant_id != _tid():
        raise not_found("企业不存在或不在当前数据范围内")
    return c


def _get(db, pos_id) -> InternshipPosition:
    p = db.get(InternshipPosition, int(pos_id))
    if not p or p.is_deleted or p.tenant_id != _tid():
        raise not_found("岗位不存在或不在当前数据范围内")
    return p


def _row(p: InternshipPosition) -> dict:
    return {
        "id": str(p.id), "companyId": str(p.company_id), "companyName": p.company_name or "",
        "batchId": str(p.batch_id) if p.batch_id else "",
        "title": p.title, "category": p.category or "",
        "majorRequirement": p.major_requirement or "", "gradeRequirement": p.grade_requirement or "",
        "workLocation": p.work_location or "", "salaryRange": p.salary_range or "",
        "subsidy": p.subsidy or "", "headcount": p.headcount, "allocatedCount": p.allocated_count,
        "remaining": max(0, p.headcount - p.allocated_count),
        "mentorContactId": str(p.mentor_contact_id) if p.mentor_contact_id else "",
        "mentorName": p.mentor_name or "",
        "riskFlag": bool(p.risk_flag), "riskNote": p.risk_note or "",
        "status": p.status, "statusLabel": STATUS_LABEL.get(p.status, p.status),
        "statusTone": STATUS_TONE.get(p.status, "default"),
        "remark": p.remark or "", "publishAt": _iso(p.publish_at),
        "archivedAt": _iso(p.archived_at), "archivedBy": p.archived_by or "",
        "updatedAt": _iso(p.updated_at),
    }


# ═══════════ 列表 / 详情 ═══════════

def list_positions(page: int, page_size: int, keyword=None, status=None,
                   company_id=None, risk=None) -> tuple[list[dict], int]:
    with session() as db:
        q = select(InternshipPosition).where(InternshipPosition.tenant_id == _tid(),
                                             InternshipPosition.is_deleted.is_(False))
        if keyword:
            like = f"%{keyword.strip()}%"
            q = q.where(or_(InternshipPosition.title.like(like),
                            InternshipPosition.company_name.like(like),
                            InternshipPosition.major_requirement.like(like)))
        if status:
            q = q.where(InternshipPosition.status == status)
        if company_id:
            q = q.where(InternshipPosition.company_id == int(company_id))
        if risk is not None:
            q = q.where(InternshipPosition.risk_flag.is_(bool(risk)))
        total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
        rows = db.scalars(q.order_by(InternshipPosition.id.desc())
                          .offset((max(1, page) - 1) * page_size).limit(page_size)).all()
        return [_row(p) for p in rows], total


def get_position(pos_id) -> dict:
    with session() as db:
        p = _get(db, pos_id)
        c = db.get(EmpCompany, p.company_id)
        trail = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == _tid(),
            InternshipAuditTrail.target_type == "POSITION",
            InternshipAuditTrail.target_id == p.id).order_by(
            InternshipAuditTrail.occurred_at.desc()).limit(30)).all()
        company = None
        if c and not c.is_deleted:
            company = {"id": str(c.id), "name": c.name, "coopStatus": c.coop_status,
                       "coopStatusLabel": COOP_LABEL.get(c.coop_status, c.coop_status),
                       "blacklist": bool(c.blacklist)}
        return {
            **_row(p),
            "company": company,
            "auditTrail": [{"action": a.action, "operator": a.operator_name or "",
                            "detail": a.detail_json or {}, "occurredAt": _iso(a.occurred_at)}
                           for a in trail],
        }


# ═══════════ 增 / 改 ═══════════

def _resolve_mentor(db, company_id: int, mentor_contact_id) -> tuple[int | None, str | None]:
    if not mentor_contact_id:
        return None, None
    t = db.get(InternshipEnterpriseContact, int(mentor_contact_id))
    if not t or t.is_deleted or t.tenant_id != _tid() or t.company_id != company_id:
        raise AppException("VALIDATION_ERROR", "企业导师不存在或不属于该企业")
    return t.id, t.name


def create_position(body) -> dict:
    with session() as db:
        title = (getattr(body, "title", "") or "").strip()
        if not title:
            raise AppException("VALIDATION_ERROR", "岗位名称必填")
        c = _company(db, body.companyId)  # 岗位必须关联企业
        mentor_id, mentor_name = _resolve_mentor(db, c.id, getattr(body, "mentorContactId", None))
        p = InternshipPosition(
            tenant_id=_tid(), company_id=c.id, company_name=c.name,
            batch_id=int(body.batchId) if getattr(body, "batchId", None) else None,
            title=title, category=getattr(body, "category", None),
            major_requirement=getattr(body, "majorRequirement", None),
            grade_requirement=getattr(body, "gradeRequirement", None),
            work_location=getattr(body, "workLocation", None),
            salary_range=getattr(body, "salaryRange", None), subsidy=getattr(body, "subsidy", None),
            headcount=getattr(body, "headcount", 1) or 1,
            mentor_contact_id=mentor_id, mentor_name=mentor_name,
            remark=getattr(body, "remark", None), status="DRAFT")
        db.add(p)
        db.flush()
        _trail(db, p.id, "CREATE", {"title": title, "companyId": str(c.id)})
        db.commit()
        db.refresh(p)
        return _row(p)


def update_position(pos_id, body) -> dict:
    with session() as db:
        p = _get(db, pos_id)
        if p.status == "ARCHIVED":
            raise AppException("DATA_CONFLICT", "已归档岗位不可编辑")
        for src, col in [("title", "title"), ("category", "category"),
                         ("majorRequirement", "major_requirement"),
                         ("gradeRequirement", "grade_requirement"),
                         ("workLocation", "work_location"), ("salaryRange", "salary_range"),
                         ("subsidy", "subsidy"), ("remark", "remark")]:
            v = getattr(body, src, None)
            if v is not None:
                setattr(p, col, v)
        hc = getattr(body, "headcount", None)
        if hc is not None:
            if hc < p.allocated_count:
                raise AppException("VALIDATION_ERROR", f"容量不能小于已分配人数（{p.allocated_count}）")
            p.headcount = hc
        bid = getattr(body, "batchId", None)
        if bid is not None:
            p.batch_id = int(bid) if bid else None
        mc = getattr(body, "mentorContactId", None)
        if mc is not None:
            p.mentor_contact_id, p.mentor_name = _resolve_mentor(db, p.company_id, mc) if mc else (None, None)
        p.version += 1
        _trail(db, p.id, "UPDATE", {"title": p.title})
        db.commit()
        db.refresh(p)
        return _row(p)


# ═══════════ 状态机 ═══════════

def set_status(pos_id, action: str, reason: str = "") -> dict:
    """SUBMIT / PUBLISH / OFFLINE / SUSPEND / ARCHIVE。上架强约束黑名单/停用企业。"""
    with session() as db:
        p = _get(db, pos_id)
        if p.status == "ARCHIVED":
            raise AppException("DATA_CONFLICT", "已归档岗位不可再变更状态")
        if action == "SUBMIT":
            if p.status != "DRAFT":
                raise AppException("DATA_CONFLICT", "仅「草稿」可提交审核")
            p.status = "PENDING"
        elif action == "PUBLISH":
            if p.status not in ("PENDING", "OFFLINE", "SUSPENDED"):
                raise AppException("DATA_CONFLICT", "仅待审核/已下架/已暂停岗位可上架")
            c = _company(db, p.company_id)
            if c.blacklist or c.coop_status == "BLACKLIST":
                raise AppException("DATA_CONFLICT", "黑名单企业不能发布岗位")
            if c.coop_status != "ACTIVE":
                raise AppException("DATA_CONFLICT",
                                   f"仅「合作中」企业可上架岗位（当前企业：{COOP_LABEL.get(c.coop_status)}）")
            if p.allocated_count >= p.headcount:
                raise AppException("DATA_CONFLICT", "岗位已满员，不能上架")
            p.status = "PUBLISHED"
            p.publish_at = datetime.utcnow()
        elif action == "OFFLINE":
            if p.status not in ("PUBLISHED", "SUSPENDED", "FULL"):
                raise AppException("DATA_CONFLICT", "仅上架/暂停/满员岗位可下架")
            p.status = "OFFLINE"
        elif action == "SUSPEND":
            if p.status != "PUBLISHED":
                raise AppException("DATA_CONFLICT", "仅「已上架」岗位可暂停")
            p.status = "SUSPENDED"
        elif action == "ARCHIVE":
            p.status = "ARCHIVED"
            p.archived_at = datetime.utcnow()
            p.archived_by = _op_name()
        else:
            raise AppException("VALIDATION_ERROR", "非法状态动作")
        _trail(db, p.id, f"STATUS_{action}", {"reason": reason, "to": p.status})
        db.commit()
        db.refresh(p)
        return _row(p)


def mark_risk(pos_id, on: bool, note: str = "") -> dict:
    with session() as db:
        p = _get(db, pos_id)
        if p.status == "ARCHIVED":
            raise AppException("DATA_CONFLICT", "已归档岗位不可标记风险")
        if on:
            if not (note or "").strip():
                raise AppException("VALIDATION_ERROR", "标记风险岗位必须填写风险说明")
            p.risk_flag = True
            p.risk_note = note.strip()
            p.status = "RISK"
        else:
            p.risk_flag = False
            p.risk_note = None
            p.status = "OFFLINE"  # 解除风险后回到已下架，需重新上架
        _trail(db, p.id, "RISK_ON" if on else "RISK_OFF", {"note": note})
        db.commit()
        db.refresh(p)
        return _row(p)


# ═══════════ 统计 ═══════════

def position_stats() -> dict:
    with session() as db:
        base = [InternshipPosition.tenant_id == _tid(), InternshipPosition.is_deleted.is_(False)]
        total = int(db.scalar(select(func.count()).select_from(InternshipPosition).where(*base)) or 0)
        by_status = []
        for st in STATUS_LABEL:
            by_status.append({"status": st, "label": STATUS_LABEL[st],
                              "count": int(db.scalar(select(func.count()).select_from(
                                  InternshipPosition).where(*base, InternshipPosition.status == st)) or 0)})
        risk = int(db.scalar(select(func.count()).select_from(InternshipPosition).where(
            *base, InternshipPosition.risk_flag.is_(True))) or 0)
        cap = db.execute(select(func.coalesce(func.sum(InternshipPosition.headcount), 0),
                                func.coalesce(func.sum(InternshipPosition.allocated_count), 0)).where(
            *base, InternshipPosition.status == "PUBLISHED")).first()
        return {
            "total": total, "byStatus": by_status, "riskCount": risk,
            "publishedCapacity": int(cap[0] or 0), "publishedAllocated": int(cap[1] or 0),
        }


def count_for_enterprise(company_id) -> dict:
    """企业库反向补：某企业岗位数摘要（不含软删）。"""
    with session() as db:
        base = [InternshipPosition.tenant_id == _tid(), InternshipPosition.is_deleted.is_(False),
                InternshipPosition.company_id == int(company_id)]
        total = int(db.scalar(select(func.count()).select_from(InternshipPosition).where(*base)) or 0)
        published = int(db.scalar(select(func.count()).select_from(InternshipPosition).where(
            *base, InternshipPosition.status == "PUBLISHED")) or 0)
        return {"total": total, "published": published}


# ═══════════ 导入 / 导出（CSV 真导入导出）═══════════

def import_dry_run(rows: list[dict]) -> dict:
    """逐行预校验：title 必填；company（信用码或名称）必须能匹配到已有企业。"""
    with session() as db:
        companies = db.scalars(select(EmpCompany).where(
            EmpCompany.tenant_id == _tid(), EmpCompany.is_deleted.is_(False))).all()
        by_code = {c.credit_code: c for c in companies if c.credit_code}
        by_name = {c.name: c for c in companies}
        errors, valid = [], 0
        for i, r in enumerate(rows or []):
            row_no = i + 1
            title = (r.get("title") or "").strip()
            key = (r.get("company") or "").strip()
            if not title:
                errors.append({"rowNo": row_no, "field": "title", "message": "岗位名称必填"})
                continue
            if not key or (key not in by_code and key not in by_name):
                errors.append({"rowNo": row_no, "field": "company",
                               "message": f"未匹配到企业（信用码/名称）：{key or '空'}"})
                continue
            valid += 1
        return {"total": len(rows or []), "validRows": valid,
                "invalidRows": len(errors), "errors": errors}


def import_confirm(rows: list[dict]) -> dict:
    pre = import_dry_run(rows)
    if pre["invalidRows"] > 0:
        raise AppException("DATA_CONFLICT", "存在未通过预校验的行，禁止确认导入")
    with session() as db:
        companies = db.scalars(select(EmpCompany).where(
            EmpCompany.tenant_id == _tid(), EmpCompany.is_deleted.is_(False))).all()
        by_code = {c.credit_code: c for c in companies if c.credit_code}
        by_name = {c.name: c for c in companies}
        created = 0
        for r in rows or []:
            key = (r.get("company") or "").strip()
            c = by_code.get(key) or by_name.get(key)
            p = InternshipPosition(
                tenant_id=_tid(), company_id=c.id, company_name=c.name,
                title=(r.get("title") or "").strip(),
                major_requirement=r.get("major") or None, work_location=r.get("location") or None,
                headcount=int(r.get("headcount") or 1), status="DRAFT")
            db.add(p)
            db.flush()
            _trail(db, p.id, "IMPORT", {"title": p.title})
            created += 1
        db.commit()
        return {"created": created}


def export_positions(keyword=None, status=None, company_id=None) -> dict:
    items, _ = list_positions(1, 100000, keyword=keyword, status=status, company_id=company_id)
    header = ["岗位名称", "所属企业", "专业要求", "年级要求", "工作地点", "薪资", "容量", "已分配",
              "状态", "风险"]
    lines = [",".join(header)]
    for it in items:
        lines.append(",".join(str(x).replace(",", "，") for x in [
            it["title"], it["companyName"], it["majorRequirement"], it["gradeRequirement"],
            it["workLocation"], it["salaryRange"], it["headcount"], it["allocatedCount"],
            it["statusLabel"], "是" if it["riskFlag"] else "否"]))
    return {"filename": "岗位库导出.csv", "content": "\n".join(lines), "rowCount": len(items)}
