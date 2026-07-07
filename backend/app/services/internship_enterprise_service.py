"""岗位实习中心 · 企业库服务（DB_ENABLED=true 走本模块）。

以全系统共享企业主档 t_emp_company 为底座（不重复造企业表），叠加实习侧企业库能力：
合作状态机 + 资质核验 + 黑名单 + 联系人/企业导师 + 统计 + 导入导出。
横切：租户隔离 + is_deleted 软删 + 联系电话脱敏 + 写审计到 t_internship_audit_trail(target_type=ENTERPRISE)。

数据范围（预留校验点）：企业库为校级主数据，默认按租户可见；
如需按学院限定（学院实习负责人只看本院合作企业），在 _scope_filter 处接入 resolve_teacher_scope。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, or_, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.models import EmpCompany, InternshipAuditTrail, InternshipEnterpriseContact
from app.services.db_service import _iso, _mask_phone, _tid, session

# ── 字典 ──
COOP_LABEL = {"PENDING": "待审核", "ACTIVE": "合作中", "REJECTED": "已驳回",
              "SUSPENDED": "已暂停", "BLACKLIST": "黑名单", "ARCHIVED": "已归档"}
COOP_TONE = {"PENDING": "warning", "ACTIVE": "success", "REJECTED": "default",
             "SUSPENDED": "warning", "BLACKLIST": "danger", "ARCHIVED": "default"}
QUAL_LABEL = {"UNREVIEWED": "未核验", "PASSED": "资质通过", "FAILED": "资质不通过"}
SOURCE_LABEL = {"SELF_BUILT": "自建", "SCHOOL_ENTERPRISE": "校企合作",
                "STUDENT_SELF": "学生自主", "RECOMMENDED": "推荐"}
CONTACT_TYPE_LABEL = {"CONTACT": "联系人", "MENTOR": "企业导师"}


def _op_name() -> str:
    u = get_current_user_ctx() or {}
    return u.get("realName") or "系统"


def _trail(db, company_id: int, action: str, detail: dict | None = None):
    db.add(InternshipAuditTrail(tenant_id=_tid(), target_id=company_id, target_type="ENTERPRISE",
                                action=action, operator_name=_op_name(), detail_json=detail or {},
                                occurred_at=datetime.utcnow()))


def _get(db, company_id) -> EmpCompany:
    row = db.get(EmpCompany, int(company_id))
    if not row or row.is_deleted or row.tenant_id != _tid():
        raise not_found("企业不存在或不在当前数据范围内")
    return row


def _row(c: EmpCompany) -> dict:
    return {
        "id": str(c.id), "name": c.name, "creditCode": c.credit_code or "",
        "industry": c.industry or "", "nature": c.nature or "", "scale": c.scale or "",
        "region": c.region or "", "city": c.city or "", "address": c.address or "",
        "source": c.source or "", "sourceLabel": SOURCE_LABEL.get(c.source, c.source or "—"),
        "contactPerson": c.contact_person or "",
        "contactPhoneMasked": _mask_phone(c.contact_phone_encrypted) if c.contact_phone_encrypted else "",
        "cooperationLevel": c.cooperation_level or "",
        "coopStatus": c.coop_status, "coopStatusLabel": COOP_LABEL.get(c.coop_status, c.coop_status),
        "coopStatusTone": COOP_TONE.get(c.coop_status, "default"),
        "qualificationStatus": c.qualification_status,
        "qualificationLabel": QUAL_LABEL.get(c.qualification_status, c.qualification_status),
        "blacklist": bool(c.blacklist), "blacklistReason": c.blacklist_reason or "",
        "internCount": c.intern_count, "hiredCount": c.hired_count,
        "remark": c.remark or "",
        "reviewBy": c.review_by or "", "reviewAt": _iso(c.review_at), "reviewComment": c.review_comment or "",
        "archivedAt": _iso(c.archived_at), "archivedBy": c.archived_by or "",
        "updatedAt": _iso(c.updated_at),
    }


def _contact_row(t: InternshipEnterpriseContact) -> dict:
    return {
        "id": str(t.id), "companyId": str(t.company_id),
        "contactType": t.contact_type, "contactTypeLabel": CONTACT_TYPE_LABEL.get(t.contact_type, t.contact_type),
        "name": t.name, "title": t.title or "",
        "phoneMasked": _mask_phone(t.phone_encrypted) if t.phone_encrypted else "",
        "email": t.email or "", "isPrimary": bool(t.is_primary),
        "remark": t.remark or "", "status": t.status,
    }


# ═══════════ 列表 / 详情 ═══════════

def list_enterprises(page: int, page_size: int, keyword=None, coop_status=None,
                     industry=None, region=None, blacklist=None) -> tuple[list[dict], int]:
    with session() as db:
        q = select(EmpCompany).where(EmpCompany.tenant_id == _tid(),
                                     EmpCompany.is_deleted.is_(False))
        if keyword:
            like = f"%{keyword.strip()}%"
            q = q.where(or_(EmpCompany.name.like(like), EmpCompany.credit_code.like(like),
                            EmpCompany.contact_person.like(like)))
        if coop_status:
            q = q.where(EmpCompany.coop_status == coop_status)
        if industry:
            q = q.where(EmpCompany.industry == industry)
        if region:
            q = q.where(EmpCompany.region == region)
        if blacklist is not None:
            q = q.where(EmpCompany.blacklist.is_(bool(blacklist)))
        total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
        rows = db.scalars(q.order_by(EmpCompany.id.desc())
                          .offset((max(1, page) - 1) * page_size).limit(page_size)).all()
        return [_row(c) for c in rows], total


def get_enterprise(company_id) -> dict:
    with session() as db:
        c = _get(db, company_id)
        contacts = db.scalars(select(InternshipEnterpriseContact).where(
            InternshipEnterpriseContact.tenant_id == _tid(),
            InternshipEnterpriseContact.company_id == c.id,
            InternshipEnterpriseContact.is_deleted.is_(False)).order_by(
            InternshipEnterpriseContact.is_primary.desc(), InternshipEnterpriseContact.id)).all()
        trail = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == _tid(),
            InternshipAuditTrail.target_type == "ENTERPRISE",
            InternshipAuditTrail.target_id == c.id).order_by(
            InternshipAuditTrail.occurred_at.desc()).limit(30)).all()
        # 反向补：企业岗位摘要（岗位库完成后接入；延迟导入避免循环）
        from app.services import internship_position_service as _pos
        position_summary = _pos.count_for_enterprise(c.id)
        return {
            **_row(c),
            "contacts": [_contact_row(t) for t in contacts],
            "mentorCount": sum(1 for t in contacts if t.contact_type == "MENTOR"),
            "contactCount": sum(1 for t in contacts if t.contact_type == "CONTACT"),
            "positionSummary": position_summary,
            "auditTrail": [{"action": a.action, "operator": a.operator_name or "",
                            "detail": a.detail_json or {}, "occurredAt": _iso(a.occurred_at)}
                           for a in trail],
        }


# ═══════════ 增 / 改 ═══════════

def _apply(c: EmpCompany, body) -> None:
    for src, col in [("name", "name"), ("creditCode", "credit_code"), ("industry", "industry"),
                     ("nature", "nature"), ("scale", "scale"), ("region", "region"),
                     ("city", "city"), ("address", "address"), ("source", "source"),
                     ("cooperationLevel", "cooperation_level"), ("contactPerson", "contact_person"),
                     ("remark", "remark")]:
        v = getattr(body, src, None)
        if v is not None:
            setattr(c, col, v)
    phone = getattr(body, "contactPhone", None)
    if phone is not None:
        # 演示环境：明文占位存入 *_encrypted 列（真实环境为密文，加解密在授权服务内完成）
        c.contact_phone_encrypted = phone or None


def create_enterprise(body) -> dict:
    with session() as db:
        name = (getattr(body, "name", "") or "").strip()
        if not name:
            raise AppException("VALIDATION_ERROR", "企业名称必填")
        cc = (getattr(body, "creditCode", "") or "").strip()
        if cc:
            dup = db.scalars(select(EmpCompany).where(
                EmpCompany.tenant_id == _tid(), EmpCompany.credit_code == cc,
                EmpCompany.is_deleted.is_(False))).first()
            if dup:
                raise AppException("DATA_CONFLICT", f"统一社会信用代码已存在：{cc}")
        c = EmpCompany(tenant_id=_tid(), name=name, status="ACTIVE",
                       coop_status="PENDING", qualification_status="UNREVIEWED")
        _apply(c, body)
        db.add(c)
        db.flush()
        _trail(db, c.id, "CREATE", {"name": name, "source": c.source})
        db.commit()
        db.refresh(c)
        return _row(c)


def update_enterprise(company_id, body) -> dict:
    with session() as db:
        c = _get(db, company_id)
        cc = (getattr(body, "creditCode", None) or "").strip()
        if cc and cc != (c.credit_code or ""):
            dup = db.scalars(select(EmpCompany).where(
                EmpCompany.tenant_id == _tid(), EmpCompany.credit_code == cc,
                EmpCompany.id != c.id, EmpCompany.is_deleted.is_(False))).first()
            if dup:
                raise AppException("DATA_CONFLICT", f"统一社会信用代码已存在：{cc}")
        _apply(c, body)
        c.version += 1
        _trail(db, c.id, "UPDATE", {"name": c.name})
        db.commit()
        db.refresh(c)
        return _row(c)


# ═══════════ 状态机：审核 / 合作启停 / 黑名单 ═══════════

def review_enterprise(company_id, action: str, comment: str = "") -> dict:
    """资质审核：仅 PENDING 可审。APPROVE→ACTIVE+资质通过；REJECT→REJECTED+资质不通过。"""
    if action not in ("APPROVE", "REJECT"):
        raise AppException("VALIDATION_ERROR", "非法审核动作")
    with session() as db:
        c = _get(db, company_id)
        if c.coop_status != "PENDING":
            raise AppException("DATA_CONFLICT",
                               f"仅「待审核」企业可审核，当前状态：{COOP_LABEL.get(c.coop_status)}")
        c.coop_status = "ACTIVE" if action == "APPROVE" else "REJECTED"
        c.qualification_status = "PASSED" if action == "APPROVE" else "FAILED"
        c.review_by = _op_name()
        c.review_at = datetime.utcnow()
        c.review_comment = comment or ""
        _trail(db, c.id, f"REVIEW_{action}", {"comment": comment})
        db.commit()
        db.refresh(c)
        return _row(c)


def set_cooperation(company_id, action: str, reason: str = "") -> dict:
    """合作启停：SUSPEND(ACTIVE→SUSPENDED) / RESUME(SUSPENDED→ACTIVE) / ARCHIVE(→ARCHIVED)。"""
    with session() as db:
        c = _get(db, company_id)
        if action == "SUSPEND":
            if c.coop_status != "ACTIVE":
                raise AppException("DATA_CONFLICT", "仅「合作中」企业可暂停")
            c.coop_status = "SUSPENDED"
        elif action == "RESUME":
            if c.coop_status != "SUSPENDED":
                raise AppException("DATA_CONFLICT", "仅「已暂停」企业可恢复合作")
            c.coop_status = "ACTIVE"
        elif action == "ARCHIVE":
            if c.coop_status in ("ARCHIVED", "BLACKLIST"):
                raise AppException("DATA_CONFLICT", "黑名单/已归档企业不可再归档")
            c.coop_status = "ARCHIVED"
            c.archived_at = datetime.utcnow()
            c.archived_by = _op_name()
        else:
            raise AppException("VALIDATION_ERROR", "非法合作动作")
        _trail(db, c.id, f"COOP_{action}", {"reason": reason})
        db.commit()
        db.refresh(c)
        return _row(c)


def set_blacklist(company_id, on: bool, reason: str = "") -> dict:
    """拉黑 / 移出黑名单。拉黑需原因；移出后恢复为合作中。"""
    with session() as db:
        c = _get(db, company_id)
        if on:
            if not (reason or "").strip():
                raise AppException("VALIDATION_ERROR", "拉黑必须填写原因")
            if c.coop_status == "ARCHIVED":
                raise AppException("DATA_CONFLICT", "已归档企业不可拉黑")
            c.blacklist = True
            c.blacklist_reason = reason.strip()
            c.coop_status = "BLACKLIST"
        else:
            if not c.blacklist:
                raise AppException("DATA_CONFLICT", "该企业不在黑名单中")
            c.blacklist = False
            c.blacklist_reason = None
            c.coop_status = "ACTIVE"
        _trail(db, c.id, "BLACKLIST_ON" if on else "BLACKLIST_OFF", {"reason": reason})
        db.commit()
        db.refresh(c)
        return _row(c)


# ═══════════ 联系人 / 企业导师 ═══════════

def list_contacts(company_id) -> list[dict]:
    with session() as db:
        c = _get(db, company_id)
        rows = db.scalars(select(InternshipEnterpriseContact).where(
            InternshipEnterpriseContact.tenant_id == _tid(),
            InternshipEnterpriseContact.company_id == c.id,
            InternshipEnterpriseContact.is_deleted.is_(False)).order_by(
            InternshipEnterpriseContact.is_primary.desc(), InternshipEnterpriseContact.id)).all()
        return [_contact_row(t) for t in rows]


def add_contact(company_id, body) -> dict:
    with session() as db:
        c = _get(db, company_id)
        name = (getattr(body, "name", "") or "").strip()
        if not name:
            raise AppException("VALIDATION_ERROR", "姓名必填")
        ctype = getattr(body, "contactType", None) or "CONTACT"
        if ctype not in CONTACT_TYPE_LABEL:
            raise AppException("VALIDATION_ERROR", "非法联系人类型")
        is_primary = bool(getattr(body, "isPrimary", False))
        if is_primary:
            _unset_primary(db, c.id, ctype)
        t = InternshipEnterpriseContact(
            tenant_id=_tid(), company_id=c.id, contact_type=ctype, name=name,
            title=getattr(body, "title", None), email=getattr(body, "email", None),
            phone_encrypted=getattr(body, "phone", None) or None,
            is_primary=is_primary, remark=getattr(body, "remark", None), status="ACTIVE")
        db.add(t)
        db.flush()
        _trail(db, c.id, "CONTACT_ADD", {"name": name, "type": ctype})
        db.commit()
        db.refresh(t)
        return _contact_row(t)


def _unset_primary(db, company_id: int, ctype: str) -> None:
    for t in db.scalars(select(InternshipEnterpriseContact).where(
            InternshipEnterpriseContact.tenant_id == _tid(),
            InternshipEnterpriseContact.company_id == company_id,
            InternshipEnterpriseContact.contact_type == ctype,
            InternshipEnterpriseContact.is_primary.is_(True))).all():
        t.is_primary = False


def _get_contact(db, company_id: int, contact_id) -> InternshipEnterpriseContact:
    t = db.get(InternshipEnterpriseContact, int(contact_id))
    if not t or t.is_deleted or t.tenant_id != _tid() or t.company_id != company_id:
        raise not_found("联系人不存在")
    return t


def update_contact(company_id, contact_id, body) -> dict:
    with session() as db:
        c = _get(db, company_id)
        t = _get_contact(db, c.id, contact_id)
        for src, col in [("name", "name"), ("title", "title"), ("email", "email"),
                         ("remark", "remark"), ("contactType", "contact_type")]:
            v = getattr(body, src, None)
            if v is not None:
                setattr(t, col, v)
        phone = getattr(body, "phone", None)
        if phone is not None:
            t.phone_encrypted = phone or None
        is_primary = getattr(body, "isPrimary", None)
        if is_primary:
            _unset_primary(db, c.id, t.contact_type)
            t.is_primary = True
        elif is_primary is False:
            t.is_primary = False
        _trail(db, c.id, "CONTACT_UPDATE", {"contactId": str(t.id)})
        db.commit()
        db.refresh(t)
        return _contact_row(t)


def delete_contact(company_id, contact_id) -> dict:
    with session() as db:
        c = _get(db, company_id)
        t = _get_contact(db, c.id, contact_id)
        t.is_deleted = True
        _trail(db, c.id, "CONTACT_DELETE", {"contactId": str(t.id), "name": t.name})
        db.commit()
        return {"id": str(contact_id), "deleted": True}


# ═══════════ 统计 ═══════════

def enterprise_stats() -> dict:
    with session() as db:
        base = [EmpCompany.tenant_id == _tid(), EmpCompany.is_deleted.is_(False)]
        total = int(db.scalar(select(func.count()).select_from(EmpCompany).where(*base)) or 0)
        by_status = {}
        for st in COOP_LABEL:
            by_status[st] = int(db.scalar(select(func.count()).select_from(EmpCompany).where(
                *base, EmpCompany.coop_status == st)) or 0)
        black = int(db.scalar(select(func.count()).select_from(EmpCompany).where(
            *base, EmpCompany.blacklist.is_(True))) or 0)
        ind_rows = db.execute(select(EmpCompany.industry, func.count()).where(*base).group_by(
            EmpCompany.industry)).all()
        return {
            "total": total,
            "byCoopStatus": [{"status": st, "label": COOP_LABEL[st], "count": by_status[st]}
                             for st in COOP_LABEL],
            "blacklistCount": black,
            "byIndustry": [{"industry": (r[0] or "未填"), "count": int(r[1])} for r in ind_rows],
        }


# ═══════════ 导入 / 导出（CSV 真导入导出）═══════════

_IMPORT_COLS = ["name", "creditCode", "industry", "region", "contactPerson", "contactPhone"]


def import_dry_run(rows: list[dict]) -> dict:
    """逐行预校验，不写库。name 必填；信用码批内 + 库内去重。"""
    with session() as db:
        existing = {c.credit_code for c in db.scalars(select(EmpCompany).where(
            EmpCompany.tenant_id == _tid(), EmpCompany.is_deleted.is_(False),
            EmpCompany.credit_code.is_not(None))).all()}
        errors, seen, valid = [], set(), 0
        for i, r in enumerate(rows or []):
            row_no = i + 1
            name = (r.get("name") or "").strip()
            cc = (r.get("creditCode") or "").strip()
            if not name:
                errors.append({"rowNo": row_no, "field": "name", "message": "企业名称必填"})
                continue
            if cc and cc in existing:
                errors.append({"rowNo": row_no, "field": "creditCode", "message": f"信用代码库内已存在：{cc}"})
                continue
            if cc and cc in seen:
                errors.append({"rowNo": row_no, "field": "creditCode", "message": f"文件内信用代码重复：{cc}"})
                continue
            if cc:
                seen.add(cc)
            valid += 1
        return {"total": len(rows or []), "validRows": valid,
                "invalidRows": len(errors), "errors": errors}


def import_confirm(rows: list[dict]) -> dict:
    """预校验全通过才允许确认；以整批为事务，任一行失败整批回滚。"""
    pre = import_dry_run(rows)
    if pre["invalidRows"] > 0:
        raise AppException("DATA_CONFLICT", "存在未通过预校验的行，禁止确认导入")
    with session() as db:
        created = 0
        for r in rows or []:
            c = EmpCompany(
                tenant_id=_tid(), name=(r.get("name") or "").strip(),
                credit_code=(r.get("creditCode") or "").strip() or None,
                industry=r.get("industry") or None, region=r.get("region") or None,
                contact_person=r.get("contactPerson") or None,
                contact_phone_encrypted=(r.get("contactPhone") or "").strip() or None,
                status="ACTIVE", coop_status="PENDING", qualification_status="UNREVIEWED",
                source="SELF_BUILT")
            db.add(c)
            db.flush()
            _trail(db, c.id, "IMPORT", {"name": c.name})
            created += 1
        db.commit()
        return {"created": created}


def export_enterprises(keyword=None, coop_status=None, industry=None, region=None) -> dict:
    """导出 CSV（联系电话脱敏；导出动作由调用方写安全审计）。"""
    items, _ = list_enterprises(1, 100000, keyword=keyword, coop_status=coop_status,
                                industry=industry, region=region)
    header = ["企业名称", "统一社会信用代码", "行业", "地区", "合作状态", "资质", "联系人",
              "联系电话(脱敏)", "累计实习生", "是否黑名单"]
    lines = [",".join(header)]
    for it in items:
        lines.append(",".join(str(x).replace(",", "，") for x in [
            it["name"], it["creditCode"], it["industry"], it["region"], it["coopStatusLabel"],
            it["qualificationLabel"], it["contactPerson"], it["contactPhoneMasked"],
            it["internCount"], "是" if it["blacklist"] else "否"]))
    return {"filename": "企业库导出.csv", "content": "\n".join(lines), "rowCount": len(items)}
