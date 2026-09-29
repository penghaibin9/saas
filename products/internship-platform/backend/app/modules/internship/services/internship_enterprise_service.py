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
from app.core.exceptions import AppException, no_permission, not_found
from app.core.field_crypto import encrypt_field, mask_phone_encrypted
from app.models import (
    College, EmpCompany, InternshipAuditTrail, InternshipEnterpriseCollegeScope,
    InternshipEnterpriseContact, InternshipRecord, Major, SchoolClass, StudentProfile,
)
from app.services import excel  # 公共 Excel 导入导出底座（V1.1）
from app.services.db_service import _as_id, _iso, _tid, session

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


def _student_college_id(db, student) -> int | None:
    if student is None:
        return None
    college_id = getattr(student, "college_id", None)
    if college_id:
        return int(college_id)
    major_id = getattr(student, "major_id", None)
    if not major_id and getattr(student, "class_id", None):
        school_class = db.get(SchoolClass, student.class_id)
        major_id = school_class.major_id if school_class else None
    if major_id:
        major = db.get(Major, major_id)
        if major and not major.is_deleted and major.tenant_id == _tid() and major.college_id:
            return int(major.college_id)
    return None


def resolve_user_college_ids(db, user=None) -> set[int] | None:
    """Return None for tenant-wide admins; otherwise the exact colleges in current data scope."""
    from app.modules.internship.services.internship_service import _current_scope

    scope = _current_scope(user)
    if scope.get("mode") != "SCOPED":
        return None

    college_ids: set[int] = set()
    college_names = {str(v).strip() for v in scope.get("collegeNames") or set() if str(v).strip()}
    if college_names:
        college_ids.update(int(row.id) for row in db.scalars(select(College).where(
            College.tenant_id == _tid(),
            College.college_name.in_(college_names),
            College.is_deleted.is_(False),
        )).all())

    major_names = {str(v).strip() for v in scope.get("majorNames") or set() if str(v).strip()}
    if major_names:
        college_ids.update(int(row.college_id) for row in db.scalars(select(Major).where(
            Major.tenant_id == _tid(),
            Major.major_name.in_(major_names),
            Major.is_deleted.is_(False),
            Major.college_id.is_not(None),
        )).all() if row.college_id)

    class_names = {str(v).strip() for v in scope.get("classNames") or set() if str(v).strip()}
    if class_names:
        classes = db.scalars(select(SchoolClass).where(
            SchoolClass.tenant_id == _tid(),
            SchoolClass.class_name.in_(class_names),
            SchoolClass.is_deleted.is_(False),
        )).all()
        major_ids = {int(row.major_id) for row in classes if row.major_id}
        if major_ids:
            college_ids.update(int(row.college_id) for row in db.scalars(select(Major).where(
                Major.tenant_id == _tid(),
                Major.id.in_(major_ids),
                Major.is_deleted.is_(False),
                Major.college_id.is_not(None),
            )).all() if row.college_id)

    student_nos = {str(v).strip() for v in scope.get("studentNos") or set() if str(v).strip()}
    if student_nos:
        students = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == _tid(),
            StudentProfile.student_no.in_(student_nos),
            StudentProfile.is_deleted.is_(False),
        )).all()
        college_ids.update(cid for cid in (_student_college_id(db, student) for student in students) if cid)

    advisor_ids = {int(v) for v in scope.get("advisorUserIds") or set() if str(v).isdigit()}
    advisor_names = {str(v).strip() for v in scope.get("advisorNames") or set() if str(v).strip()}
    if advisor_ids or advisor_names:
        clauses = []
        if advisor_ids:
            clauses.append(InternshipRecord.advisor_user_id.in_(advisor_ids))
        if advisor_names:
            clauses.append(InternshipRecord.advisor_name.in_(advisor_names))
        records = db.scalars(select(InternshipRecord).where(
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.is_deleted.is_(False),
            or_(*clauses),
        )).all() if clauses else []
        student_ids = {int(row.student_id) for row in records if row.student_id}
        if student_ids:
            students = db.scalars(select(StudentProfile).where(
                StudentProfile.tenant_id == _tid(),
                StudentProfile.id.in_(student_ids),
                StudentProfile.is_deleted.is_(False),
            )).all()
            college_ids.update(cid for cid in (_student_college_id(db, student) for student in students) if cid)

    return college_ids


def _company_scope_map(db, company_ids) -> dict[int, list[dict]]:
    ids = {int(value) for value in company_ids or [] if value}
    if not ids:
        return {}
    rows = db.execute(select(
        InternshipEnterpriseCollegeScope.company_id,
        InternshipEnterpriseCollegeScope.college_id,
        College.college_name,
    ).join(
        College,
        (College.id == InternshipEnterpriseCollegeScope.college_id)
        & (College.tenant_id == InternshipEnterpriseCollegeScope.tenant_id)
        & (College.is_deleted.is_(False)),
    ).where(
        InternshipEnterpriseCollegeScope.tenant_id == _tid(),
        InternshipEnterpriseCollegeScope.company_id.in_(ids),
        InternshipEnterpriseCollegeScope.is_deleted.is_(False),
    ).order_by(
        InternshipEnterpriseCollegeScope.company_id,
        College.college_name,
    )).all()
    out: dict[int, list[dict]] = {}
    for company_id, college_id, college_name in rows:
        out.setdefault(int(company_id), []).append({
            "id": str(college_id),
            "name": college_name or "",
        })
    return out


def _company_scope_ids(db, company_id) -> set[int]:
    return {
        int(value) for value in db.scalars(select(
            InternshipEnterpriseCollegeScope.college_id
        ).where(
            InternshipEnterpriseCollegeScope.tenant_id == _tid(),
            InternshipEnterpriseCollegeScope.company_id == int(company_id),
            InternshipEnterpriseCollegeScope.is_deleted.is_(False),
        )).all()
    }


def apply_company_scope(query, company_column, db, user=None):
    """Apply AP04 enterprise applicability to any query carrying a company id column."""
    allowed = resolve_user_college_ids(db, user)
    if allowed is None:
        return query
    scoped_company_ids = select(InternshipEnterpriseCollegeScope.company_id).where(
        InternshipEnterpriseCollegeScope.tenant_id == _tid(),
        InternshipEnterpriseCollegeScope.is_deleted.is_(False),
    )
    if not allowed:
        return query.where(~company_column.in_(scoped_company_ids))
    allowed_company_ids = select(InternshipEnterpriseCollegeScope.company_id).where(
        InternshipEnterpriseCollegeScope.tenant_id == _tid(),
        InternshipEnterpriseCollegeScope.college_id.in_(allowed),
        InternshipEnterpriseCollegeScope.is_deleted.is_(False),
    )
    return query.where(or_(
        ~company_column.in_(scoped_company_ids),
        company_column.in_(allowed_company_ids),
    ))


def assert_company_visible(db, company_id, user=None) -> None:
    allowed = resolve_user_college_ids(db, user)
    if allowed is None:
        return
    scoped = _company_scope_ids(db, int(company_id))
    if scoped and scoped.isdisjoint(allowed):
        raise no_permission("该企业不在你的学院数据范围内")


def assert_company_writable(db, company_id, user=None) -> None:
    allowed = resolve_user_college_ids(db, user)
    if allowed is None:
        return
    scoped = _company_scope_ids(db, int(company_id))
    if not scoped:
        raise no_permission("全校通用企业仅校级管理员可维护；学院角色只能维护本院限定企业")
    if not scoped.issubset(allowed):
        raise no_permission("该企业同时属于其他学院范围，当前账号不能修改")


def enterprise_scope_options(user=None) -> dict:
    with session() as db:
        allowed = resolve_user_college_ids(db, user)
        q = select(College).where(
            College.tenant_id == _tid(),
            College.is_deleted.is_(False),
        )
        if allowed is not None:
            if not allowed:
                return {"mode": "SCOPED", "items": [], "schoolWideAllowed": False}
            q = q.where(College.id.in_(allowed))
        rows = db.scalars(q.order_by(College.college_name, College.id)).all()
        return {
            "mode": "ADMIN_TENANT" if allowed is None else "SCOPED",
            "items": [{"id": str(row.id), "name": row.college_name or ""} for row in rows],
            "schoolWideAllowed": allowed is None,
        }


def _validated_scope_ids(db, raw_ids, *, user=None, creating=False) -> set[int]:
    requested = set()
    for raw in raw_ids or []:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            raise AppException("VALIDATION_ERROR", "适用学院 ID 格式非法") from None
        if value > 0:
            requested.add(value)

    allowed = resolve_user_college_ids(db, user)
    if allowed is not None:
        if not requested and creating:
            requested = set(allowed)
        if not requested:
            raise no_permission("学院范围账号不能把企业设置为全校通用")
        if not requested.issubset(allowed):
            raise no_permission("不能把企业适用范围扩大到当前账号无权管理的学院")

    if requested:
        valid = set(db.scalars(select(College.id).where(
            College.tenant_id == _tid(),
            College.id.in_(requested),
            College.is_deleted.is_(False),
        )).all())
        valid = {int(value) for value in valid}
        if valid != requested:
            raise AppException("VALIDATION_ERROR", "存在无效或已停用的适用学院")
    return requested


def _sync_company_scope(db, company_id: int, raw_ids, *, user=None, creating=False) -> set[int]:
    requested = _validated_scope_ids(db, raw_ids, user=user, creating=creating)
    existing = db.scalars(select(InternshipEnterpriseCollegeScope).where(
        InternshipEnterpriseCollegeScope.tenant_id == _tid(),
        InternshipEnterpriseCollegeScope.company_id == int(company_id),
    ).with_for_update()).all()
    by_college = {int(row.college_id): row for row in existing}
    now = datetime.utcnow()
    for college_id, row in by_college.items():
        if college_id in requested:
            if row.is_deleted:
                row.is_deleted = False
                row.scope_source = "MANUAL"
                row.updated_at = now
                row.version = int(row.version or 0) + 1
        elif not row.is_deleted:
            row.is_deleted = True
            row.updated_at = now
            row.version = int(row.version or 0) + 1
    for college_id in requested - set(by_college):
        db.add(InternshipEnterpriseCollegeScope(
            tenant_id=_tid(),
            company_id=int(company_id),
            college_id=college_id,
            scope_source="MANUAL",
        ))
    return requested


def _row(c: EmpCompany, scope_items=None) -> dict:
    scope_items = list(scope_items or [])
    return {
        "id": str(c.id), "name": c.name, "creditCode": c.credit_code or "",
        "industry": c.industry or "", "nature": c.nature or "", "scale": c.scale or "",
        "region": c.region or "", "city": c.city or "", "address": c.address or "",
        "source": c.source or "", "sourceLabel": SOURCE_LABEL.get(c.source, c.source or "—"),
        "contactPerson": c.contact_person or "",
        "contactPhoneMasked": mask_phone_encrypted(c.contact_phone_encrypted),
        "cooperationLevel": c.cooperation_level or "",
        "coopStatus": c.coop_status, "coopStatusLabel": COOP_LABEL.get(c.coop_status, c.coop_status),
        "coopStatusTone": COOP_TONE.get(c.coop_status, "default"),
        "qualificationStatus": c.qualification_status,
        "accessValidUntil": c.access_valid_until.isoformat() + "Z" if c.access_valid_until else None,
        "qualificationLabel": QUAL_LABEL.get(c.qualification_status, c.qualification_status),
        "blacklist": bool(c.blacklist), "blacklistReason": c.blacklist_reason or "",
        "internCount": c.intern_count, "hiredCount": c.hired_count,
        "remark": c.remark or "",
        "collegeScopes": scope_items,
        "collegeScopeIds": [str(item["id"]) for item in scope_items],
        "collegeScopeNames": [item["name"] for item in scope_items],
        "schoolWide": len(scope_items) == 0,
        "reviewBy": c.review_by or "", "reviewAt": _iso(c.review_at), "reviewComment": c.review_comment or "",
        "archivedAt": _iso(c.archived_at), "archivedBy": c.archived_by or "",
        "updatedAt": _iso(c.updated_at), "version": int(c.version or 0),
    }


def _contact_row(t: InternshipEnterpriseContact) -> dict:
    return {
        "id": str(t.id), "companyId": str(t.company_id),
        "contactType": t.contact_type, "contactTypeLabel": CONTACT_TYPE_LABEL.get(t.contact_type, t.contact_type),
        "name": t.name, "title": t.title or "",
        "phoneMasked": mask_phone_encrypted(t.phone_encrypted),
        "email": t.email or "", "isPrimary": bool(t.is_primary),
        "remark": t.remark or "", "status": t.status, "version": int(t.version or 0),
    }


# ═══════════ 列表 / 详情 ═══════════

def list_enterprises(page: int, page_size: int, keyword=None, coop_status=None,
                     industry=None, region=None, blacklist=None, user=None) -> tuple[list[dict], int]:
    with session() as db:
        q = select(EmpCompany).where(
            EmpCompany.tenant_id == _tid(),
            EmpCompany.is_deleted.is_(False),
        )
        q = apply_company_scope(q, EmpCompany.id, db, user)
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
        scope_map = _company_scope_map(db, [row.id for row in rows])
        return [_row(row, scope_map.get(int(row.id), [])) for row in rows], total


def get_enterprise(company_id, user=None) -> dict:
    with session() as db:
        c = _get(db, company_id)
        assert_company_visible(db, c.id, user)
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
            **_row(c, _company_scope_map(db, [c.id]).get(int(c.id), [])),
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


def create_enterprise(body, user=None) -> dict:
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
        scope_ids = _sync_company_scope(
            db, c.id, getattr(body, "collegeScopeIds", None), user=user, creating=True)
        _trail(db, c.id, "CREATE", {
            "name": name, "source": c.source,
            "collegeScopeIds": [str(value) for value in sorted(scope_ids)],
            "schoolWide": len(scope_ids) == 0,
        })
        db.commit()
        db.refresh(c)
        return _row(c, _company_scope_map(db, [c.id]).get(int(c.id), []))


def update_enterprise(company_id, body, user=None) -> dict:
    with session() as db:
        c = db.scalar(select(EmpCompany).where(
            EmpCompany.id == _as_id(company_id), EmpCompany.tenant_id == _tid(),
            EmpCompany.is_deleted.is_(False)).with_for_update())
        if not c:
            raise not_found("企业不存在或不在当前数据范围内")
        assert_company_writable(db, c.id, user)
        expected = getattr(body, "expectedVersion", None)
        if expected is None:
            raise AppException("VALIDATION_ERROR", "必须提供 expectedVersion（企业乐观锁），请刷新后重试")
        if int(expected) != int(c.version or 0):
            raise AppException("DATA_CONFLICT", "企业信息已被其他用户修改，请刷新后重试")
        if c.coop_status == "ARCHIVED":
            raise AppException("DATA_CONFLICT", "已归档企业不可编辑")

        old_name = c.name or ""
        old_cc = c.credit_code or ""
        new_name = (getattr(body, "name", None) if "name" in body.model_fields_set else None)
        new_cc = (getattr(body, "creditCode", None) if "creditCode" in body.model_fields_set else None)
        if new_name is not None:
            normalized_name = (new_name or "").strip()
            err = _validate_company_name(normalized_name)
            if err:
                raise AppException("VALIDATION_ERROR", err)
            body.name = normalized_name
        if new_cc is not None:
            normalized_cc = (new_cc or "").strip()
            err = _validate_credit_code(normalized_cc)
            if err:
                raise AppException("VALIDATION_ERROR", err)
            body.creditCode = normalized_cc or None
            if normalized_cc and normalized_cc != old_cc:
                dup = db.scalars(select(EmpCompany).where(
                    EmpCompany.tenant_id == _tid(), EmpCompany.credit_code == normalized_cc,
                    EmpCompany.id != c.id, EmpCompany.is_deleted.is_(False))).first()
                if dup:
                    raise AppException("DATA_CONFLICT", f"统一社会信用代码已存在：{normalized_cc}")

        old_scope_ids = _company_scope_ids(db, c.id)
        _apply(c, body)
        new_scope_ids = old_scope_ids
        if "collegeScopeIds" in body.model_fields_set:
            new_scope_ids = _sync_company_scope(
                db, c.id, getattr(body, "collegeScopeIds", None), user=user, creating=False)
        identity_changed = (c.name or "") != old_name or (c.credit_code or "") != old_cc
        if identity_changed:
            c.qualification_status = "UNREVIEWED"
            c.review_by = None
            c.review_at = None
            c.review_comment = None
            if c.coop_status != "BLACKLIST":
                c.coop_status = "PENDING"
        c.version = int(c.version or 0) + 1
        _trail(db, c.id, "UPDATE", {
            "name": c.name, "identityInvalidated": identity_changed,
            "previousName": old_name if identity_changed else "",
            "previousCreditCode": old_cc if identity_changed else "",
            "collegeScopeBefore": [str(value) for value in sorted(old_scope_ids)],
            "collegeScopeAfter": [str(value) for value in sorted(new_scope_ids)],
        })
        db.commit()
        db.refresh(c)
        return _row(c, _company_scope_map(db, [c.id]).get(int(c.id), []))


def review_enterprise(company_id, action: str, comment: str = "", expected_version=None, user=None) -> dict:
    """资质审核：仅 PENDING 可审。APPROVE→ACTIVE+资质通过；REJECT→REJECTED+资质不通过。"""
    if action not in ("APPROVE", "REJECT"):
        raise AppException("VALIDATION_ERROR", "非法审核动作")
    if action == "REJECT" and len((comment or "").strip()) < 5:
        raise AppException("VALIDATION_ERROR", "驳回原因必填且不少于 5 个字")
    with session() as db:
        c = db.scalar(select(EmpCompany).where(
            EmpCompany.id == _as_id(company_id), EmpCompany.tenant_id == _tid(),
            EmpCompany.is_deleted.is_(False)).with_for_update())
        if not c:
            raise not_found("企业不存在或不在当前数据范围内")
        assert_company_writable(db, c.id, user)
        if expected_version is None:
            raise AppException("VALIDATION_ERROR", "必须提供 expectedVersion（企业乐观锁），请刷新后重试")
        if int(expected_version) != int(c.version or 0):
            raise AppException("DATA_CONFLICT", "企业资质状态已变化，请刷新后重试")
        if c.coop_status != "PENDING":
            raise AppException("DATA_CONFLICT",
                               f"仅「待审核」企业可审核，当前状态：{COOP_LABEL.get(c.coop_status)}")
        c.coop_status = "ACTIVE" if action == "APPROVE" else "REJECTED"
        c.qualification_status = "PASSED" if action == "APPROVE" else "FAILED"
        c.review_by = _op_name()
        c.review_at = datetime.utcnow()
        c.review_comment = comment or ""
        c.version = int(c.version or 0) + 1
        _trail(db, c.id, f"REVIEW_{action}", {"comment": comment})
        db.commit()
        db.refresh(c)
        return _row(c, _company_scope_map(db, [c.id]).get(int(c.id), []))


def set_cooperation(company_id, action: str, reason: str = "", expected_version=None, user=None) -> dict:
    """合作启停：SUSPEND(ACTIVE→SUSPENDED) / RESUME(SUSPENDED→ACTIVE) / ARCHIVE(→ARCHIVED)。"""
    with session() as db:
        c = db.scalar(select(EmpCompany).where(
            EmpCompany.id == _as_id(company_id), EmpCompany.tenant_id == _tid(),
            EmpCompany.is_deleted.is_(False)).with_for_update())
        if not c:
            raise not_found("企业不存在或不在当前数据范围内")
        if expected_version is None:
            raise AppException("VALIDATION_ERROR", "必须提供 expectedVersion（企业乐观锁），请刷新后重试")
        if int(expected_version) != int(c.version or 0):
            raise AppException("DATA_CONFLICT", "企业合作状态已变化，请刷新后重试")
        if action == "SUSPEND":
            if c.coop_status != "ACTIVE":
                raise AppException("DATA_CONFLICT", "仅「合作中」企业可暂停")
            c.coop_status = "SUSPENDED"
        elif action == "RESUME":
            if c.coop_status != "SUSPENDED":
                raise AppException("DATA_CONFLICT", "仅「已暂停」企业可恢复合作")
            if c.qualification_status != "PASSED":
                raise AppException("DATA_CONFLICT", "企业资质未通过，不能恢复合作")
            c.coop_status = "ACTIVE"
        elif action == "ARCHIVE":
            if c.coop_status in ("ARCHIVED", "BLACKLIST"):
                raise AppException("DATA_CONFLICT", "黑名单/已归档企业不可再归档")
            c.coop_status = "ARCHIVED"
            c.archived_at = datetime.utcnow()
            c.archived_by = _op_name()
        else:
            raise AppException("VALIDATION_ERROR", "非法合作动作")
        c.version = int(c.version or 0) + 1
        _trail(db, c.id, f"COOP_{action}", {"reason": reason})
        db.commit()
        db.refresh(c)
        return _row(c, _company_scope_map(db, [c.id]).get(int(c.id), []))


def set_blacklist(company_id, on: bool, reason: str = "", expected_version=None, user=None) -> dict:
    """拉黑 / 移出黑名单。移出时恢复拉黑前状态；缺历史证据则 fail-closed 回待审核。"""
    with session() as db:
        c = db.scalar(select(EmpCompany).where(
            EmpCompany.id == _as_id(company_id), EmpCompany.tenant_id == _tid(),
            EmpCompany.is_deleted.is_(False)).with_for_update())
        if not c:
            raise not_found("企业不存在或不在当前数据范围内")
        if expected_version is None:
            raise AppException("VALIDATION_ERROR", "必须提供 expectedVersion（企业乐观锁），请刷新后重试")
        if int(expected_version) != int(c.version or 0):
            raise AppException("DATA_CONFLICT", "企业黑名单状态已变化，请刷新后重试")
        if on:
            if not (reason or "").strip():
                raise AppException("VALIDATION_ERROR", "拉黑必须填写原因")
            if c.coop_status == "ARCHIVED":
                raise AppException("DATA_CONFLICT", "已归档企业不可拉黑")
            previous = c.coop_status
            c.blacklist = True
            c.blacklist_reason = reason.strip()
            c.coop_status = "BLACKLIST"
            detail = {"reason": reason, "previousCoopStatus": previous}
        else:
            if not c.blacklist:
                raise AppException("DATA_CONFLICT", "该企业不在黑名单中")
            trail = db.scalars(select(InternshipAuditTrail).where(
                InternshipAuditTrail.tenant_id == _tid(),
                InternshipAuditTrail.target_type == "ENTERPRISE",
                InternshipAuditTrail.target_id == c.id,
                InternshipAuditTrail.action == "BLACKLIST_ON",
            ).order_by(InternshipAuditTrail.id.desc())).first()
            previous = str(((trail.detail_json or {}).get("previousCoopStatus") if trail else "") or "").upper()
            if previous not in {"PENDING", "ACTIVE", "REJECTED", "SUSPENDED"}:
                previous = "PENDING"
            if previous == "ACTIVE" and c.qualification_status != "PASSED":
                previous = "PENDING"
            c.blacklist = False
            c.blacklist_reason = None
            c.coop_status = previous
            detail = {"reason": reason, "restoredCoopStatus": previous}
        c.version = int(c.version or 0) + 1
        _trail(db, c.id, "BLACKLIST_ON" if on else "BLACKLIST_OFF", detail)
        db.commit()
        db.refresh(c)
        return _row(c, _company_scope_map(db, [c.id]).get(int(c.id), []))


# ═══════════ 联系人 / 企业导师 ═══════════

def list_contacts(company_id, user=None) -> list[dict]:
    with session() as db:
        c = _get(db, company_id)
        assert_company_visible(db, c.id, user)
        rows = db.scalars(select(InternshipEnterpriseContact).where(
            InternshipEnterpriseContact.tenant_id == _tid(),
            InternshipEnterpriseContact.company_id == c.id,
            InternshipEnterpriseContact.is_deleted.is_(False)).order_by(
            InternshipEnterpriseContact.is_primary.desc(), InternshipEnterpriseContact.id)).all()
        return [_contact_row(t) for t in rows]


def add_contact(company_id, body, user=None) -> dict:
    with session() as db:
        c = _get(db, company_id)
        assert_company_writable(db, c.id, user)
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


def update_contact(company_id, contact_id, body, user=None) -> dict:
    with session() as db:
        c = _get(db, company_id)
        assert_company_writable(db, c.id, user)
        t = db.scalar(select(InternshipEnterpriseContact).where(
            InternshipEnterpriseContact.id == _as_id(contact_id),
            InternshipEnterpriseContact.tenant_id == _tid(),
            InternshipEnterpriseContact.company_id == c.id,
            InternshipEnterpriseContact.is_deleted.is_(False)).with_for_update())
        if not t:
            raise not_found("联系人不存在")
        expected = getattr(body, "expectedVersion", None)
        if expected is None:
            raise AppException("VALIDATION_ERROR", "必须提供 expectedVersion（联系人乐观锁），请刷新后重试")
        if int(expected) != int(t.version or 0):
            raise AppException("DATA_CONFLICT", "联系人已被其他用户修改，请刷新后重试")
        old_contact_type = t.contact_type
        was_primary = bool(t.is_primary)
        if "name" in body.model_fields_set:
            name = (getattr(body, "name", None) or "").strip()
            if not name:
                raise AppException("VALIDATION_ERROR", "姓名必填")
            body.name = name
        if "contactType" in body.model_fields_set:
            ctype = getattr(body, "contactType", None)
            if ctype not in CONTACT_TYPE_LABEL:
                raise AppException("VALIDATION_ERROR", "非法联系人类型")
        for src, col in [("name", "name"), ("title", "title"), ("email", "email"),
                         ("remark", "remark"), ("contactType", "contact_type")]:
            if src in body.model_fields_set:
                setattr(t, col, getattr(body, src))
        if "phone" in body.model_fields_set:
            t.phone_encrypted = encrypt_field(getattr(body, "phone", None))
        if "isPrimary" in body.model_fields_set:
            is_primary = getattr(body, "isPrimary", None)
            if is_primary:
                _unset_primary(db, c.id, t.contact_type)
                t.is_primary = True
            else:
                t.is_primary = False
        elif "contactType" in body.model_fields_set and t.contact_type != old_contact_type and was_primary:
            # 主联系人换类型时仍保持“主联系人”语义，但新类型原主联系人必须被降级，
            # 否则同一企业同一联系人类型会出现两个主联系人。
            _unset_primary(db, c.id, t.contact_type)
            t.is_primary = True
        t.version = int(t.version or 0) + 1
        _trail(db, c.id, "CONTACT_UPDATE", {"contactId": str(t.id)})
        db.commit()
        db.refresh(t)
        return _contact_row(t)


def delete_contact(company_id, contact_id, user=None) -> dict:
    with session() as db:
        c = _get(db, company_id)
        assert_company_writable(db, c.id, user)
        t = _get_contact(db, c.id, contact_id)
        t.is_deleted = True
        _trail(db, c.id, "CONTACT_DELETE", {"contactId": str(t.id), "name": t.name})
        db.commit()
        return {"id": str(contact_id), "deleted": True}


# ═══════════ 统计 ═══════════

def enterprise_stats(user=None) -> dict:
    with session() as db:
        query = select(EmpCompany).where(
            EmpCompany.tenant_id == _tid(),
            EmpCompany.is_deleted.is_(False),
        )
        query = apply_company_scope(query, EmpCompany.id, db, user)
        scoped = query.subquery()
        total = int(db.scalar(select(func.count()).select_from(scoped)) or 0)
        by_status = {}
        for st in COOP_LABEL:
            by_status[st] = int(db.scalar(select(func.count()).select_from(scoped).where(
                scoped.c.coop_status == st)) or 0)
        black = int(db.scalar(select(func.count()).select_from(scoped).where(
            scoped.c.blacklist.is_(True))) or 0)
        ind_rows = db.execute(select(scoped.c.industry, func.count()).group_by(
            scoped.c.industry)).all()
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


def export_enterprises(keyword=None, coop_status=None, industry=None, region=None, user=None) -> dict:
    """导出 Excel 台账（走底座；联系电话已在列表层脱敏，黑名单列由底座 mask 转「是/否」）。"""
    from app.modules.internship.services.internship_export_util import load_export_rows
    items, _ = load_export_rows(
        list_enterprises, keyword=keyword, coop_status=coop_status,
        industry=industry, region=region, user=user)
    user = get_current_user_ctx() or {}
    return excel.build_export(build_export_spec(), items, operator_name=user.get("realName", "-"))
