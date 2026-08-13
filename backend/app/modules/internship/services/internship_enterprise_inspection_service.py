"""企业考察：考察结论通过后直接改写企业准入事实，因此归属与并发都必须锁死。

审核通过会写 `EmpCompany.access_valid_until`，也就是「这家企业还能不能继续接收实习生」。
两条硬约束：
1. 企业必须属于当前租户——路由只查权限不查归属，归属校验只能在这里做，且创建和审核两处都要做
   （只在创建处校验的话，归属校验上线前的历史脏数据仍能在下一次审核时改掉他校准入）。
2. 审核走条件更新——两个管理员同时 APPROVE/REJECT 不能双双成功，否则回执与准入事实会分叉。
"""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import select
from app.core.exceptions import AppException, no_permission, not_found
from app.core.tenant_scoped import tenant_get
from app.models import EmpCompany, InternshipAuditTrail, InternshipEnterpriseInspection
from app.services.db_service import _as_id, _tid, session

def _op(user): return (user or {}).get("realName") or "系统"
def _row(x): return {"id": str(x.id), "companyId": str(x.company_id), "batchId": str(x.batch_id or ""), "status": x.status, "validUntil": x.valid_until.isoformat() if x.valid_until else None, "conclusion": x.conclusion or ""}
def _audit(db,x,a,u): db.add(InternshipAuditTrail(tenant_id=_tid(),target_id=x.id,target_type="ENTERPRISE_INSPECTION",action=a,operator_name=_op(u),occurred_at=datetime.utcnow()))

def list_by_company(company_id):
    with session() as db: return [_row(x) for x in db.scalars(select(InternshipEnterpriseInspection).where(InternshipEnterpriseInspection.tenant_id==_tid(),InternshipEnterpriseInspection.company_id==_as_id(company_id),InternshipEnterpriseInspection.is_deleted.is_(False)).order_by(InternshipEnterpriseInspection.id.desc())).all()]
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
        x=InternshipEnterpriseInspection(tenant_id=_tid(),company_id=company.id,batch_id=batch_id,inspection_type=b.get("inspectionType") or "DOCUMENT",inspection_date=b.get("inspectionDate"),inspectors=b.get("inspectors"),conclusion=b.get("conclusion"),risk_items=b.get("riskItems"),rectification_items=b.get("rectificationItems"),file_ids=b.get("fileIds"),valid_until=b.get("validUntil"),status="DRAFT")
        db.add(x);db.flush();_audit(db,x,"CREATE",user);db.commit();return _row(x)
def _own_inspection(db, iid):
    x = tenant_get(db, InternshipEnterpriseInspection, _as_id(iid))
    if not x or x.is_deleted:
        raise not_found("企业考察不存在")
    return x


def submit(iid,user=None):
    from app.modules.internship.services.internship_version import versioned_update
    with session() as db:
        x=_own_inspection(db,iid)
        if x.status!="DRAFT": raise AppException("DATA_CONFLICT","仅草稿可提交")
        current_version=int(x.version or 0)
        versioned_update(
            db, InternshipEnterpriseInspection,
            entity_id=x.id, tenant_id=_tid(),
            expected_version=current_version, values={"status": "SUBMITTED"},
            expected_status="DRAFT",
        )
        _audit(db,x,"SUBMIT",user);db.commit();db.refresh(x);return _row(x)
def review(iid,action,comment="",valid_until=None,user=None):
    """审核并同事务改写企业准入事实。

    条件更新保证两个管理员并发时只有一个能赢；企业归属在这里二次确认，
    这样即使库里存在归属校验上线之前的历史脏数据，也改不动他校的准入日期。
    """
    from app.modules.internship.services.internship_version import versioned_update
    if action not in ("APPROVE","REJECT"): raise AppException("VALIDATION_ERROR","action 必须是 APPROVE/REJECT")
    with session() as db:
        x=_own_inspection(db,iid)
        if x.status!="SUBMITTED": raise AppException("DATA_CONFLICT","仅已提交记录可审核")
        company=tenant_get(db,EmpCompany,x.company_id)
        if not company or company.is_deleted:
            # 历史脏数据可能指向他校企业：审核必须停在这里，绝不能落到对方的准入字段上。
            raise no_permission("该考察记录关联的企业不在当前数据范围内，无法审核")
        if isinstance(valid_until, str):
            valid_until = datetime.fromisoformat(valid_until.replace("Z", ""))
        effective_until = valid_until or x.valid_until
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
            expected_version=current_version, values=values,
            expected_status="SUBMITTED",
        )
        if action=="APPROVE":
            # 与考察结论同一个事务：结论落库失败时准入事实必须一起回滚。
            company.access_valid_until=effective_until
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
