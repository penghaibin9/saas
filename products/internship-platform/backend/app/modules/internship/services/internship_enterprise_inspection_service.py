"""企业考察：考察结论通过后直接改写企业准入事实，因此归属与并发都必须锁死。

审核通过会写 `EmpCompany.access_valid_until`，也就是「这家企业还能不能继续接收实习生」。
两条硬约束：
1. 企业必须属于当前租户——路由只查权限不查归属，归属校验只能在这里做，且创建和审核两处都要做
   （只在创建处校验的话，归属校验上线前的历史脏数据仍能在下一次审核时改掉他校准入）。
2. 审核走条件更新——两个管理员同时 APPROVE/REJECT 不能双双成功，否则回执与准入事实会分叉。
"""
from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import select
from app.core.exceptions import AppException, no_permission, not_found
from app.core.tenant_scoped import tenant_get
from app.models import EmpCompany, InternshipAuditTrail, InternshipEnterpriseInspection
from app.services.db_service import _as_id, _tid, session
from app.core.context import get_current_user_ctx
from app.modules.internship.services.internship_version import extract_expected_version

def _op(user): return (user or {}).get("realName") or "系统"
#: 学校用的界面不该出现 DRAFT/SUBMITTED 这种英文枚举
STATUS_LABEL = {"DRAFT": "草稿", "SUBMITTED": "待审核", "APPROVED": "已通过",
                "REJECTED": "已驳回", "EXPIRED": "已过期"}
TYPE_LABEL = {"ONSITE": "实地考察", "REMOTE": "远程考察", "DOCUMENT": "书面审查"}
FILE_BIZ_TYPE = "INTERNSHIP_ENTERPRISE_INSPECTION"
TEXT_FIELDS = {
    "inspectors": ("inspectors", 200), "workplaceAddress": ("workplace_address", 300),
    "safetyCondition": ("safety_condition", 500), "accommodationCondition": ("accommodation_condition", 500),
    "mentorCondition": ("mentor_condition", 500), "remunerationCondition": ("remuneration_condition", 500),
    "conclusion": ("conclusion", 1000), "riskItems": ("risk_items", 10000),
    "rectificationItems": ("rectification_items", 10000),
}


def _date(value, name):
    if value in (None, ""):
        return None
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc).replace(tzinfo=None) if parsed.tzinfo else parsed
    except (ValueError, TypeError, OverflowError) as exc:
        raise AppException("VALIDATION_ERROR", f"{name} 日期格式不正确") from exc


def _fields(body):
    kind = body.get("inspectionType") or "DOCUMENT"
    if not isinstance(kind, str) or kind not in TYPE_LABEL:
        raise AppException("VALIDATION_ERROR", "考察方式不正确")
    values = {"inspection_type": kind}
    for key, (column, limit) in TEXT_FIELDS.items():
        value = body.get(key)
        if value is not None and (not isinstance(value, str) or len(value) > limit):
            raise AppException("VALIDATION_ERROR", f"{key} 必须是长度不超过 {limit} 的文字")
        values[column] = (value or "").strip() or None
    values["inspection_date"] = _date(body.get("inspectionDate"), "考察时间")
    values["valid_until"] = _date(body.get("validUntil"), "准入有效期")
    if values["inspection_date"] and values["valid_until"] and values["valid_until"] < values["inspection_date"]:
        raise AppException("VALIDATION_ERROR", "准入有效期不能早于考察时间")
    ids = body.get("fileIds") or []
    if not isinstance(ids, list) or len(ids) > 20 or any(not str(i).isascii() or not str(i).isdigit() for i in ids):
        raise AppException("VALIDATION_ERROR", "考察材料必须是最多 20 个有效文件编号")
    values["file_ids"] = list(dict.fromkeys(str(i) for i in ids))
    return values


def _bind_files(db, record, user):
    from app.services.file_business_binding_service import bind_file_to_business
    for fid in record.file_ids or []:
        bind_file_to_business(
            db, file_id=fid, biz_type=FILE_BIZ_TYPE, biz_id=str(record.id),
            actor=user or get_current_user_ctx() or {}, subject_type="ENTERPRISE", subject_id=str(record.company_id),
            module_code="INTERNSHIP", batch_id=str(record.batch_id) if record.batch_id else None,
            scope={"companyId": str(record.company_id)},
        )


def _iso(v):
    return v.replace(tzinfo=timezone.utc).isoformat() if v else None


def _row(x):
    """考察台账行。

    原实现只返回 6 个字段，页面要展示的考察方式/日期/考察人/审核人都没有——
    列表只能显示一排「—」，状态还是英文枚举。这些值模型里本来就有。
    """
    return {
        "id": str(x.id), "companyId": str(x.company_id), "batchId": str(x.batch_id or ""),
        "inspectionType": x.inspection_type or "",
        "inspectionTypeLabel": TYPE_LABEL.get(x.inspection_type, x.inspection_type or ""),
        "inspectionDate": _iso(x.inspection_date),
        "inspectors": x.inspectors or "",
        "status": x.status,
        "statusLabel": STATUS_LABEL.get(x.status, x.status),
        "validUntil": _iso(x.valid_until),
        "conclusion": x.conclusion or "",
        **{key: getattr(x, column) or "" for key, (column, _) in TEXT_FIELDS.items()},
        "fileIds": [str(fid) for fid in (x.file_ids or [])],
        "reviewComment": x.review_comment or "",
        "reviewedByName": x.reviewed_by_name or "",
        "reviewedAt": _iso(x.reviewed_at),
        "version": int(x.version or 0),
    }
def _audit(db,x,a,u): db.add(InternshipAuditTrail(tenant_id=_tid(),target_id=x.id,target_type="ENTERPRISE_INSPECTION",action=a,operator_name=_op(u),occurred_at=datetime.utcnow()))

def list_by_company(company_id):
    with session() as db:
        _own_company(db, company_id)
        return [_row(x) for x in db.scalars(select(InternshipEnterpriseInspection).where(InternshipEnterpriseInspection.tenant_id==_tid(),InternshipEnterpriseInspection.company_id==_as_id(company_id),InternshipEnterpriseInspection.is_deleted.is_(False)).order_by(InternshipEnterpriseInspection.id.desc())).all()]
def _own_company(db, company_id):
    """取本租户企业；他校企业一律当作不存在，不泄露其存在性。"""
    company = tenant_get(db, EmpCompany, _as_id(company_id))
    if not company or company.is_deleted:
        raise not_found("企业不存在或不在当前数据范围内")
    return company


def _own_batch_id(db, batch_id):
    if not batch_id:
        return None
    from app.models import InternshipBatch
    batch = tenant_get(db, InternshipBatch, _as_id(batch_id))
    if not batch or batch.is_deleted:
        raise not_found("实习批次不存在或不在当前数据范围内")
    return batch.id


def create(body,user=None):
    b=body or {}
    if not b.get("companyId"): raise AppException("VALIDATION_ERROR","companyId 必填")
    with session() as db:
        company=_own_company(db,b["companyId"])
        batch_id=_own_batch_id(db,b.get("batchId"))
        x=InternshipEnterpriseInspection(tenant_id=_tid(),company_id=company.id,batch_id=batch_id,**_fields(b),status="DRAFT")
        db.add(x);db.flush();_bind_files(db,x,user);_audit(db,x,"CREATE",user);db.commit();return _row(x)


def update(iid, body, user=None):
    from app.modules.internship.services.internship_version import versioned_update
    with session() as db:
        x = _own_inspection(db, iid)
        _own_company(db, x.company_id)
        if x.status != "DRAFT":
            raise AppException("DATA_CONFLICT", "仅草稿可编辑，已提交材料不可覆盖")
        b = body or {}
        if b.get("companyId") and str(b["companyId"]) != str(x.company_id):
            raise AppException("VALIDATION_ERROR", "考察所属企业不可更换")
        if "batchId" in b and str(b["batchId"] or "") != str(x.batch_id or ""):
            raise AppException("VALIDATION_ERROR", "考察所属批次不可更换")
        values = _fields({**_row(x), **b})
        versioned_update(db, InternshipEnterpriseInspection, entity_id=x.id, tenant_id=_tid(),
                         expected_version=extract_expected_version(b), expected_status="DRAFT", values=values)
        db.refresh(x)
        _bind_files(db, x, user)
        _audit(db, x, "UPDATE", user)
        db.commit()
        return _row(x)
def _own_inspection(db, iid):
    x = tenant_get(db, InternshipEnterpriseInspection, _as_id(iid))
    if not x or x.is_deleted:
        raise not_found("企业考察不存在")
    return x


def submit(iid,user=None,expected_version=None):
    from app.modules.internship.services.internship_version import versioned_update
    with session() as db:
        x=_own_inspection(db,iid)
        _own_company(db, x.company_id)
        if x.status!="DRAFT": raise AppException("DATA_CONFLICT","仅草稿可提交")
        if not (x.conclusion or "").strip():
            raise AppException("VALIDATION_ERROR", "请先填写考察结论")
        _bind_files(db, x, user)
        current_version=int(x.version or 0)
        versioned_update(
            db, InternshipEnterpriseInspection,
            entity_id=x.id, tenant_id=_tid(),
            expected_version=current_version if expected_version is None else extract_expected_version({"expectedVersion": expected_version}), values={"status": "SUBMITTED"},
            expected_status="DRAFT",
        )
        _audit(db,x,"SUBMIT",user);db.commit();db.refresh(x);return _row(x)
def review(iid,action,comment="",valid_until=None,user=None,expected_version=None):
    """审核并同事务改写企业准入事实。

    条件更新保证两个管理员并发时只有一个能赢；企业归属在这里二次确认，
    这样即使库里存在归属校验上线之前的历史脏数据，也改不动他校的准入日期。
    """
    from app.modules.internship.services.internship_version import versioned_update
    if action not in ("APPROVE","REJECT"): raise AppException("VALIDATION_ERROR","action 必须是 APPROVE/REJECT")
    if not isinstance(comment, str) or len(comment) > 500:
        raise AppException("VALIDATION_ERROR", "审核意见应为不超过 500 字的文字")
    if action == "REJECT" and not comment.strip():
        raise AppException("VALIDATION_ERROR", "请填写驳回原因")
    with session() as db:
        x=_own_inspection(db,iid)
        if x.status!="SUBMITTED": raise AppException("DATA_CONFLICT","仅已提交记录可审核")
        company=db.scalar(select(EmpCompany).where(
            EmpCompany.id == x.company_id, EmpCompany.tenant_id == _tid(), EmpCompany.is_deleted.is_(False),
        ).with_for_update())
        if not company or company.is_deleted:
            # 历史脏数据可能指向他校企业：审核必须停在这里，绝不能落到对方的准入字段上。
            raise no_permission("该考察记录关联的企业不在当前数据范围内，无法审核")
        valid_until = _date(valid_until, "准入有效期")
        effective_until = valid_until or x.valid_until
        if effective_until and x.inspection_date and effective_until < x.inspection_date:
            raise AppException("VALIDATION_ERROR", "准入有效期不能早于考察时间")
        if action == "APPROVE":
            _bind_files(db, x, user)
        current_version=int(x.version or 0)
        values={
            "status": "APPROVED" if action=="APPROVE" else "REJECTED",
            "review_comment": comment or None,
            "reviewed_by_name": _op(user),
            "reviewed_at": datetime.utcnow(),
        }
        if valid_until:
            values["valid_until"]=valid_until
        versioned_update(
            db, InternshipEnterpriseInspection,
            entity_id=x.id, tenant_id=_tid(),
            expected_version=current_version if expected_version is None else extract_expected_version({"expectedVersion": expected_version}), values=values,
            expected_status="SUBMITTED",
        )
        if action=="APPROVE":
            # 与考察结论同一个事务：结论落库失败时准入事实必须一起回滚。
            # 与准入读取器按最新考察 ID 取已通过记录的规则一致；旧考察晚审批不覆盖新考察。
            latest=db.scalar(select(InternshipEnterpriseInspection).where(
                InternshipEnterpriseInspection.tenant_id == _tid(),
                InternshipEnterpriseInspection.company_id == company.id,
                InternshipEnterpriseInspection.status == "APPROVED",
                InternshipEnterpriseInspection.is_deleted.is_(False),
            ).order_by(InternshipEnterpriseInspection.id.desc()).limit(1).with_for_update())
            company.access_valid_until=latest.valid_until if latest else effective_until
            company.version=int(company.version or 0)+1
        _audit(db,x,"REVIEW_"+action,user);db.commit();db.refresh(x);return _row(x)
def is_enterprise_access_valid(db,company_id,rules):
    c=db.get(EmpCompany,_as_id(company_id))
    if not c or c.tenant_id!=_tid(): return False,"企业不存在"
    if c.blacklist or c.coop_status in ("BLACKLIST","SUSPENDED","ARCHIVED"): return False,"企业合作状态不可准入"
    ea=(rules or {}).get("enterpriseAccess") or {}
    # 未要求考察时：仅校验主体与黑名单/合作状态
    if not ea.get("required") and not ea.get("requireOnsiteInspection"):
        if c.access_valid_until and c.access_valid_until < datetime.utcnow():
            return False,"企业准入有效期已过"
        return True,""
    x=db.scalars(select(InternshipEnterpriseInspection).where(InternshipEnterpriseInspection.tenant_id==_tid(),InternshipEnterpriseInspection.company_id==_as_id(company_id),InternshipEnterpriseInspection.status=="APPROVED",InternshipEnterpriseInspection.is_deleted.is_(False)).order_by(InternshipEnterpriseInspection.id.desc())).first()
    until=(x.valid_until if x else c.access_valid_until)
    if not x: return False,"缺少已通过的企业考察"
    if until and until < datetime.utcnow(): return False,"企业准入考察已过期"
    return True,""
