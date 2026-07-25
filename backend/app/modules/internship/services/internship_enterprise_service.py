"""岗位实习中心 · 企业库服务（DB_ENABLED=true 走本模块）。

以全系统共享企业主档 t_emp_company 为底座（不重复造企业表），叠加实习侧企业库能力：
合作状态机 + 资质核验 + 黑名单 + 联系人/企业导师 + 统计 + 导入导出。
横切：租户隔离 + is_deleted 软删 + 联系电话脱敏 + 写审计到 t_internship_audit_trail(target_type=ENTERPRISE)。

数据范围（预留校验点）：企业库为校级主数据，默认按租户可见；
如需按学院限定（学院实习负责人只看本院合作企业），在 _scope_filter 处接入 resolve_teacher_scope。
"""
from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy import func, or_, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.core.field_crypto import encrypt_field
from app.models import EmpCompany, InternshipAuditTrail, InternshipEnterpriseContact
from app.services import excel  # 公共 Excel 导入导出底座（V1.1）
from app.services.db_service import _as_id, _iso, _mask_phone, _tid, session

# 统一社会信用代码：宽松校验——纯字母数字、8~20 位（拦截含空格/冒号/标签/纯符号的脏值）。
# 注：真实标准为 18 位固定字符集，待演示数据统一为真实码后可收紧为 ^[0-9A-HJ-NPQRTUWXY]{18}$。
_CREDIT_CODE_RE = re.compile(r"^[0-9A-Za-z]{8,20}$")
# 疑似"字段标签"前缀（用户把营业执照整段粘进来时每行会带标签）
_NAME_LABEL_RE = re.compile(
    r"^\s*(企业名称|公司名称|名称|单位名称|银行账户|开户银行|开户行|账户|账号|"
    r"单位地址|注册地址|地址|税号|纳税人识别号|电话|联系电话|手机|联系人|法人|法定代表人|"
    r"注册资本|经营范围|统一社会信用代码|信用代码|营业执照)\s*[:：]")


def _validate_credit_code(cc: str) -> str | None:
    """返回错误信息；合法或为空返回 None。"""
    if not cc:
        return None
    if not _CREDIT_CODE_RE.match(cc):
        return "统一社会信用代码格式不合法（应为 18 位数字+大写字母，不含 I/O/S/V/Z）"
    return None


def _validate_company_name(name: str) -> str | None:
    """企业名称合理性校验，拦截账号/地址/税号/纯数字等非企业名。合法返回 None。"""
    if not name:
        return "企业名称必填"
    if _NAME_LABEL_RE.match(name):
        return "企业名称疑似含字段标签（如 名称:/银行账户:/税号:），请只填企业全称"
    if len(name) < 4:
        return "企业名称过短（疑似无效，请填企业全称）"
    if re.fullmatch(r"[\d\W_]+", name):
        return "企业名称不能是纯数字/符号（疑似账号、税号或金额）"
    if not re.search(r"[一-鿿]", name) and not re.search(r"[A-Za-z]{2,}", name):
        return "企业名称格式不合法（缺少中文或字母）"
    return None

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
    row = db.get(EmpCompany, _as_id(company_id))
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
        from app.modules.internship.services import internship_position_service as _pos
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
        c.contact_phone_encrypted = encrypt_field(phone)


def create_enterprise(body) -> dict:
    with session() as db:
        name = (getattr(body, "name", "") or "").strip()
        name_err = _validate_company_name(name)
        if name_err:
            raise AppException("VALIDATION_ERROR", name_err)
        cc = (getattr(body, "creditCode", "") or "").strip()
        cc_err = _validate_credit_code(cc)
        if cc_err:
            raise AppException("VALIDATION_ERROR", cc_err)
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
    if action == "REJECT" and len((comment or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "驳回原因必填且不少于 5 个字")
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
            phone_encrypted=encrypt_field(getattr(body, "phone", None)),
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
    t = db.get(InternshipEnterpriseContact, _as_id(contact_id))
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
            t.phone_encrypted = encrypt_field(phone)
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


# ═══════════ 公共 Excel 底座接入（V1.1）═══════════
# 企业库改为「只写配置」，导入导出全部走 app.services.excel 底座。
# 模块自有严格校验器（信用码 / 企业名合理性）作为 ColumnSpec.validators 复用，行为与旧实现等价。

def _v_name(v: str, col) -> str | None:
    return _validate_company_name(v)


def _v_credit(v: str, col) -> str | None:
    return _validate_credit_code(v)


def _db_credit_dup(rows: list[dict]) -> dict:
    """库内查重扩展点：信用代码已在 t_emp_company 视为重复。返回 {1-based 行号: 原因}。"""
    with session() as db:
        existing = {c.credit_code for c in db.scalars(select(EmpCompany).where(
            EmpCompany.tenant_id == _tid(), EmpCompany.is_deleted.is_(False),
            EmpCompany.credit_code.is_not(None))).all()}
    out = {}
    for i, r in enumerate(rows or []):
        cc = (r.get("creditCode") or "").strip()
        if cc and cc in existing:
            out[i + 1] = f"信用代码库内已存在：{cc}"
    return out


def _persist_enterprises(rows: list[dict]) -> dict:
    """落库扩展点：整批事务写入 t_emp_company + 审计留痕（与旧 import_confirm 等价）。"""
    with session() as db:
        created = 0
        for r in rows or []:
            c = EmpCompany(
                tenant_id=_tid(), name=(r.get("name") or "").strip(),
                credit_code=(r.get("creditCode") or "").strip() or None,
                industry=r.get("industry") or None, region=r.get("region") or None,
                contact_person=r.get("contactPerson") or None,
                contact_phone_encrypted=encrypt_field((r.get("contactPhone") or "").strip() or None),
                remark=(r.get("remark") or "").strip() or None,
                status="ACTIVE", coop_status="PENDING", qualification_status="UNREVIEWED",
                source="SELF_BUILT")
            db.add(c)
            db.flush()
            _trail(db, c.id, "IMPORT", {"name": c.name})
            created += 1
        db.commit()
        return {"created": created}


def build_import_spec() -> excel.ImportSpec:
    C = excel.ColumnSpec
    return excel.ImportSpec(
        module_key="internship", biz_type="enterprise", template_name="企业库导入",
        columns=[
            C("name", "企业名称", required=True, validators=[_v_name],
              example="华信智能科技有限公司", help_text="填企业全称，勿填账号/税号/地址"),
            C("creditCode", "统一社会信用代码", required=True, unique_in_file=True,
              validators=[_v_credit], example="91310000MA1FL0001X",
              help_text="18 位数字+大写字母；文件内、库内不可重复"),
            C("industry", "行业", required=True, example="软件"),
            C("region", "地区", required=True, example="上海"),
            C("contactPerson", "联系人", example="王经理"),
            C("contactPhone", "联系电话", example="13800000000", help_text="敏感字段，列表默认脱敏"),
            C("coopStatus", "合作状态", help_text="仅供查阅，导入后默认「待审核」"),
            C("qualificationStatus", "资质状态", help_text="仅供查阅，导入后默认「未核验」"),
            C("remark", "备注"),
        ],
        notes=[
            "1. 只导入「导入模板」这一页；第一行表头请勿改动、勿删除。",
            "2. 带 * 为必填：企业名称、统一社会信用代码、行业、地区。",
            "3. 统一社会信用代码：18 位数字+大写字母；同一份文件内、系统库内不可重复。",
            "4. 合作状态/资质状态列仅供查阅，导入后默认为「待审核/未核验」。",
            "5. 联系电话为敏感字段，列表默认脱敏展示。",
            "6. 从第 2 行起逐行填写，一行一家企业；填完保存为 .xlsx 后上传。",
        ],
        duplicate_check=_db_credit_dup, persist_rows=_persist_enterprises,
        permission_key="internship.enterprise.import", audit_action="导入企业库",
    )


def build_export_spec() -> excel.ExportSpec:
    C = excel.ColumnSpec
    return excel.ExportSpec(
        module_key="internship", biz_type="enterprise", sheet_title="企业库台账",
        file_name="企业库台账.xlsx",
        columns=[
            C("name", "企业名称"), C("creditCode", "统一社会信用代码"),
            C("industry", "行业"), C("region", "地区"),
            C("coopStatusLabel", "合作状态"), C("qualificationLabel", "资质状态"),
            C("contactPerson", "联系人"), C("contactPhoneMasked", "联系电话(脱敏)"),
            C("internCount", "累计实习生"),
            C("blacklist", "是否黑名单", mask=lambda v: "是" if v else "否"),
            C("remark", "备注"),
        ],
    )


def import_template_bytes() -> bytes:
    """企业库导入 Excel 模板（底座生成）。"""
    return excel.build_template(build_import_spec())


def import_read(content: bytes) -> list[dict]:
    """上传 .xlsx → list[dict]（走底座表头映射）。"""
    return excel.read_upload(build_import_spec(), content)


def import_errors_pack(rows: list[dict], errors: list[dict]) -> dict:
    """错误行 Excel（底座生成，pack 后返回下载体）。"""
    return excel.build_error_rows(build_import_spec(), rows, errors)


def import_dry_run(rows: list[dict]) -> dict:
    """预校验（走底座统一管道）。返回结构含 total/validRows/invalidRows/errors（超集，向后兼容）。"""
    return excel.pre_validate(build_import_spec(), rows)


def import_confirm(rows: list[dict]) -> dict:
    """确认导入（走底座；底座强制再校验，全通过才落库）+ 登记通用导入记录。"""
    spec = build_import_spec()
    pre = excel.pre_validate(spec, rows)
    result = excel.confirm_import(spec, rows)
    excel.job_service.record_import(spec.module_key, spec.biz_type, pre=pre,
                                    result=result, status="IMPORTED")
    return {"created": result.get("created", 0)}


def export_enterprises(keyword=None, coop_status=None, industry=None, region=None) -> dict:
    """导出 Excel 台账（走底座；联系电话已在列表层脱敏，黑名单列由底座 mask 转「是/否」）。"""
    items, _ = list_enterprises(1, 100000, keyword=keyword, coop_status=coop_status,
                                industry=industry, region=region)
    user = get_current_user_ctx() or {}
    return excel.build_export(build_export_spec(), items, operator_name=user.get("realName", "-"))
