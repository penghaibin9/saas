"""岗位实习 · 实习变更申请（换岗/换单位/自主实习）。

对标工学云「中途变更实习单位」：学生发起 → 指导教师审核 → 落岗/更新冗余字段。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import AppException, no_permission, not_found
from app.core.tenant_scoped import tenant_get
from app.models import (EmpCompany, InternshipAgreement, InternshipAuditTrail,
                        InternshipBatch, InternshipChangeRequest, InternshipPosition,
                        InternshipRecord, StudentProfile)
from app.modules.internship.services import internship_student_service as stu_svc
from app.services.db_service import _as_id, _iso, _tid, session

# 对标成熟实习变更：换岗 / 换单位 / 转自主 / 退岗（结束岗位）分类型，不混为一谈
TYPE_LABEL = {
    "CHANGE_POSITION": "换岗",
    "CHANGE_ENTERPRISE": "换实习单位",
    "SELF_ARRANGED": "转自主实习",
    "WITHDRAW_POST": "退岗",
}
STATUS_LABEL = {"PENDING": "待审核", "APPROVED": "已通过", "REJECTED": "已驳回", "WITHDRAWN": "已撤回"}
#: 串行查重与并发唯一索引兜底必须给出同一句提示，否则老师会以为遇到了两种不同的故障
_DUP_PENDING_MSG = "已有待审核的变更申请，请等待处理或撤回"


def _op_name(user=None) -> str:
    if user:
        return user.get("realName") or "系统"
    from app.core.context import get_current_user_ctx
    return (get_current_user_ctx() or {}).get("realName") or "系统"


def _trail(db, cid, action, detail=None, operator="系统"):
    db.add(InternshipAuditTrail(tenant_id=_tid(), target_id=cid, target_type="CHANGE_REQ",
                                action=action, operator_name=operator, detail_json=detail or {},
                                occurred_at=datetime.utcnow()))


def _scope(user):
    from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
    return _current_scope(user), _rec_in_scope


def _scope_check(db, record, student, user):
    from app.modules.internship.services.internship_batch_context import resolve_batch
    if (not record or not student or record.is_deleted or student.is_deleted
            or record.tenant_id != _tid() or student.tenant_id != _tid()
            or record.student_id != student.id):
        raise not_found("变更申请关联的学生或批次不存在")
    resolve_batch(db, record.batch_id)
    scope, in_scope = _scope(user)
    if not in_scope(scope, db, record, student):
        raise no_permission("不在数据范围内")


def _next_record_status(record: InternshipRecord | None) -> str:
    return "READY" if record and record.eligibility_status == "QUALIFIED" else "PREPARING"


def _impact_preview(change: InternshipChangeRequest, record: InternshipRecord | None) -> dict:
    next_status = _next_record_status(record)
    if change.change_type == "WITHDRAW_POST":
        relationship = "释放当前岗位名额并结束原单位、岗位与企业导师关系"
        destination = "退岗后不保留当前实习去向，重新落实去向后方可上岗"
    elif change.change_type == "SELF_ARRANGED":
        relationship = "释放当前岗位名额并结束原单位、岗位与企业导师关系"
        destination = "实习去向切换为学生自主联系的单位与岗位"
    else:
        relationship = "冻结原岗位关系、释放原名额，并以目标岗位建立新的关系快照"
        destination = "目标岗位将在审批事务内再次校验批次、准入、劳动权益与剩余名额"
    return {
        "requiresReonboard": True,
        "nextRecordStatus": next_status,
        "nextRecordStatusLabel": stu_svc.STATUS_LABEL.get(next_status, next_status),
        "impactItems": [
            {"label": "原关系", "detail": relationship},
            {"label": "目标去向", "detail": destination},
            {"label": "合规与协议", "detail": "原知情确认失效，办理中的协议和已生效协议作废，须按新去向重新办理"},
            {"label": "重新上岗", "detail": f"主记录回退为“{stu_svc.STATUS_LABEL.get(next_status, next_status)}”，重新满足合规前置后才能上岗与打卡"},
            {"label": "4+1 关系", "detail": "学生、教师、企业、学校与数据端均按审批后的当前关系重新计算权限和展示"},
        ],
        "nextStep": "完成新去向的知情确认、协议与合规核验后，由学校重新办理上岗",
    }


def _approved_history(change, trails):
    """Only an atomic approval for this request can establish its historical route."""
    if change.status != "APPROVED":
        return None
    for trail in trails:
        if (trail.tenant_id != change.tenant_id or trail.target_id != change.id
                or trail.target_type != "CHANGE_REQ" or trail.action != "APPROVE"):
            continue
        detail = trail.detail_json
        if not isinstance(detail, dict) or detail.get("atomic") is not True:
            continue
        snapshots = [detail.get("recordBefore"), detail.get("recordAfter")]
        if not all(isinstance(item, dict)
                   and type(item.get("recordVersion")) is int and item["recordVersion"] >= 0
                   and all(isinstance(item.get(key), str) for key in
                           ("enterpriseId", "positionId", "enterpriseName", "positionName"))
                   and all(not item[key] or (item[key].isascii() and item[key].isdigit()
                                            and int(item[key]) > 0)
                           for key in ("enterpriseId", "positionId"))
                   for item in snapshots):
            continue
        before, after = snapshots
        if after["recordVersion"] != before["recordVersion"] + 1:
            continue
        keys = ("enterpriseId", "positionId", "enterpriseName", "positionName", "recordVersion")
        return {
            "auditId": str(trail.id),
            "before": {key: before[key] for key in keys},
            "after": {key: after[key] for key in keys},
            "applicationBasisMatched": before["recordVersion"] == change.record_version_snapshot,
        }
    return None


def _approved_histories(db, changes):
    approved = {change.id: change for change in changes if change.status == "APPROVED"}
    if not approved:
        return {}
    trails = db.scalars(select(InternshipAuditTrail).where(
        InternshipAuditTrail.tenant_id == _tid(), InternshipAuditTrail.target_type == "CHANGE_REQ",
        InternshipAuditTrail.action == "APPROVE", InternshipAuditTrail.target_id.in_(approved)
    ).order_by(InternshipAuditTrail.id.desc())).all()
    grouped = {}
    for trail in trails:
        grouped.setdefault(trail.target_id, []).append(trail)
    return {cid: _approved_history(change, grouped.get(cid, [])) for cid, change in approved.items()}


def _row(c, rec, stu, approved_history=None):
    impact = _impact_preview(c, rec)
    return {
        "id": str(c.id), "internId": str(c.internship_id),
        "studentName": stu.real_name if stu else "-", "studentNo": stu.student_no if stu else "-",
        "changeType": c.change_type, "changeTypeLabel": TYPE_LABEL.get(c.change_type, c.change_type),
        "reason": c.reason,
        "targetEnterpriseId": str(c.target_enterprise_id) if c.target_enterprise_id else "",
        "targetPositionId": str(c.target_position_id) if c.target_position_id else "",
        "targetEnterpriseName": c.target_enterprise_name or "",
        "targetPositionName": c.target_position_name or "",
        "currentEnterprise": rec.enterprise_name if rec else "",
        "currentPosition": rec.position_name if rec else "",
        "approvedHistory": approved_history,
        "recordStatus": rec.status if rec else "",
        "recordStatusLabel": stu_svc.STATUS_LABEL.get(rec.status, rec.status) if rec else "",
        "status": c.status, "statusLabel": STATUS_LABEL.get(c.status, c.status),
        "reviewComment": c.review_comment or "",
        "reviewedBy": c.reviewed_by_name or "",
        "reviewedAt": _iso(c.reviewed_at) or "",
        "version": int(c.version or 0),
        "recordVersion": int(rec.version or 0) if rec else None,
        "recordVersionSnapshot": int(c.record_version_snapshot or 0),
        "createdAt": _iso(c.created_at) or "",
        **impact,
    }


def _target_position_truth(db, change, record=None, student=None) -> dict | None:
    if not change.target_position_id:
        return None
    position = db.get(InternshipPosition, change.target_position_id)
    if not position or position.is_deleted or position.tenant_id != _tid():
        return {
            "id": str(change.target_position_id), "exists": False,
            "title": change.target_position_name or "", "companyName": change.target_enterprise_name or "",
            "status": "MISSING", "remaining": 0, "capacityAvailable": False,
            "sameBatch": False, "rightsPassed": False, "blockers": ["目标岗位不存在或已删除"],
        }
    company = db.get(EmpCompany, position.company_id)
    batch = db.get(InternshipBatch, record.batch_id) if record and record.batch_id else None
    rights = {"passed": False, "blockers": [], "unknowns": []}
    if company and not company.is_deleted and company.tenant_id == _tid():
        from app.modules.internship.services.internship_position_rights import evaluate_position_publishability
        rights = evaluate_position_publishability(
            position, company, batch, student, operation="CHANGE_REVIEW", db=db)
    remaining = max(0, int(position.headcount or 0) - int(position.allocated_count or 0))
    same_batch = bool(record and position.batch_id and int(position.batch_id) == int(record.batch_id))
    issues = list(rights.get("blockers") or []) + list(rights.get("unknowns") or [])
    return {
        "id": str(position.id), "exists": True, "title": position.title,
        "companyId": str(position.company_id),
        "companyName": (company.name if company and not company.is_deleted and company.tenant_id == _tid() else None) or position.company_name or "",
        "status": position.status, "headcount": int(position.headcount or 0),
        "allocatedCount": int(position.allocated_count or 0), "remaining": remaining,
        "capacityAvailable": bool(position.status == "PUBLISHED" and remaining > 0 and rights.get("passed")),
        "sameBatch": same_batch, "rightsPassed": bool(rights.get("passed")),
        "blockers": [item.get("reason") or item.get("label") or item.get("code") for item in issues],
        "ruleVersion": rights.get("ruleVersion") or "",
    }


def validate_target_position(db, record: InternshipRecord, student: StudentProfile,
                             target_position_id, *, change_type: str = "CHANGE_POSITION"):
    """Validate a student-selected target now; approval validates again under row locks."""
    position = db.get(InternshipPosition, _as_id(target_position_id))
    if not position or position.is_deleted or position.tenant_id != _tid():
        raise not_found("目标岗位不存在或不在当前数据范围内")
    if record.position_id == position.id:
        raise AppException("DATA_CONFLICT", "目标岗位不能与当前岗位相同", http_status=409)
    if not record.batch_id or not position.batch_id or int(record.batch_id) != int(position.batch_id):
        raise AppException("DATA_CONFLICT", "目标岗位不属于当前实习批次", http_status=409)
    company = db.get(EmpCompany, position.company_id)
    if not company or company.is_deleted or company.tenant_id != _tid():
        raise not_found("目标岗位所属企业不存在")
    if change_type == "CHANGE_ENTERPRISE" and record.enterprise_id and int(record.enterprise_id) == int(company.id):
        raise AppException("DATA_CONFLICT", "换实习单位必须选择不同企业的目标岗位", http_status=409)
    batch = tenant_get(db, InternshipBatch, record.batch_id)
    from app.modules.internship.services.internship_position_rights import evaluate_position_publishability
    rights = evaluate_position_publishability(
        position, company, batch, student, operation="CHANGE_APPLY", db=db)
    if position.status != "PUBLISHED" or not rights["passed"]:
        issues = list(rights.get("blockers") or []) + list(rights.get("unknowns") or [])
        reasons = [item.get("reason") or item.get("label") or item.get("code") for item in issues]
        raise AppException(
            "DATA_CONFLICT",
            "目标岗位当前不可申请" + ("：" + "；".join(reasons) if reasons else ""),
            http_status=409,
        )
    return position, company


def list_changes(page, page_size, status=None, keyword=None, batch_id=None, user=None, *, change_id=None):
    from app.modules.internship.services.internship_batch_context import resolve_batch
    from app.modules.internship.services.internship_scope import apply_internship_record_scope

    with session() as db:
        batch = resolve_batch(db, batch_id)
        scoped_records = apply_internship_record_scope(
            select(InternshipRecord.id).where(
                InternshipRecord.tenant_id == _tid(),
                InternshipRecord.batch_id == batch.id,
                InternshipRecord.is_deleted.is_(False)), user).subquery()
        query = select(InternshipChangeRequest, InternshipRecord, StudentProfile).join(
            InternshipRecord,
            InternshipRecord.id == InternshipChangeRequest.internship_id,
        ).join(
            StudentProfile,
            StudentProfile.id == InternshipChangeRequest.student_id,
        ).where(
            InternshipChangeRequest.tenant_id == _tid(),
            InternshipChangeRequest.is_deleted.is_(False),
            InternshipChangeRequest.internship_id.in_(select(scoped_records.c.id)),
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.batch_id == batch.id,
            InternshipRecord.is_deleted.is_(False),
            StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False),
            InternshipChangeRequest.student_id == InternshipRecord.student_id,
        )
        if change_id is not None:
            query = query.where(InternshipChangeRequest.id == _as_id(change_id))
        status_value = str(status or "ALL").strip().upper()
        if status_value == "REVIEWED":
            query = query.where(InternshipChangeRequest.status.in_(("APPROVED", "REJECTED")))
        elif status_value in STATUS_LABEL:
            query = query.where(InternshipChangeRequest.status == status_value)
        elif status_value != "ALL":
            raise AppException("VALIDATION_ERROR", "不支持的实习变更审核状态")
        term = str(keyword or "").strip()
        if term:
            query = query.where(or_(
                StudentProfile.real_name.contains(term, autoescape=True),
                StudentProfile.student_no.contains(term, autoescape=True),
            ))
        total = int(db.scalar(select(func.count()).select_from(query.subquery())) or 0)
        size = max(0, int(page_size or 0))
        if size == 0:
            return [], total
        rows = db.execute(
            query.order_by(InternshipChangeRequest.id.desc())
            .offset((max(1, int(page or 1)) - 1) * size)
            .limit(size)
        ).all()
        histories = _approved_histories(db, [change for change, _, _ in rows])
        return [_row(change, record, student, histories.get(change.id))
                for change, record, student in rows], total


def export_changes(*, status=None, keyword=None, batch_id=None, user=None):
    from app.modules.internship.services.internship_export_util import load_export_rows, write_export_audit
    from app.modules.internship.services.internship_report_quality_service import format_report_time
    from app.services import xlsx_util

    items, total = load_export_rows(
        list_changes, status=status, keyword=keyword, batch_id=batch_id, user=user)
    headers = [
        "申请编号", "学号", "姓名", "变更类型", "状态", "申请时间", "申请原因",
        "申请目标单位", "申请目标岗位", "本次变更前单位", "本次变更前岗位",
        "本次变更后单位", "本次变更后岗位", "历史依据说明", "当前实习单位", "当前实习岗位",
        "审核人", "审核时间", "审核意见",
    ]
    rows = []
    for item in items:
        history = item.get("approvedHistory")
        before, after = (history["before"], history["after"]) if history else ({}, {})
        if history:
            explanation = ("审批前去向与本申请依据的实习记录版本一致" if history["applicationBasisMatched"]
                           else "仅记录本次审批前后去向，不能确认申请时去向")
        else:
            explanation = ("历史去向未记录，无法核实本次审批前后去向" if item["status"] == "APPROVED"
                           else "尚未通过审批，无变更生效记录")
        rows.append([
            item["id"], item["studentNo"], item["studentName"], item["changeTypeLabel"],
            item["statusLabel"], format_report_time(item["createdAt"]), item["reason"],
            item["targetEnterpriseName"], item["targetPositionName"],
            before.get("enterpriseName", ""), before.get("positionName", ""),
            after.get("enterpriseName", ""), after.get("positionName", ""), explanation,
            item["currentEnterprise"], item["currentPosition"], item.get("reviewedBy", ""),
            format_report_time(item.get("reviewedAt")), item["reviewComment"],
        ])
    content = xlsx_util.build_ledger_xlsx(
        "实习变更台账", headers, rows,
        watermark=f"岗位实习中心·实习变更台账 · {_op_name(user)} · {datetime.now():%Y-%m-%d %H:%M}")
    with session() as db:
        write_export_audit(db, "实习变更台账", total, user=user, filters={
            "batchId": str(batch_id or ""), "status": str(status or "ALL").strip().upper(),
            "keyword": str(keyword or "").strip(),
        })
        db.commit()
    return xlsx_util.pack_xlsx_result(content, "实习变更台账.xlsx", total)


def get_change(cid, user=None):
    with session() as db:
        c = db.get(InternshipChangeRequest, _as_id(cid))
        if not c or c.is_deleted or c.tenant_id != _tid():
            raise not_found("变更申请不存在")
        rec = db.get(InternshipRecord, c.internship_id)
        stu = db.get(StudentProfile, c.student_id)
        _scope_check(db, rec, stu, user)
        trail = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == _tid(), InternshipAuditTrail.target_type == "CHANGE_REQ",
            InternshipAuditTrail.target_id == c.id).order_by(InternshipAuditTrail.id)).all()
        return {
            **_row(c, rec, stu, _approved_history(c, reversed(trail))),
            "targetPosition": _target_position_truth(db, c, rec, stu),
            "reviewComment": c.review_comment or "",
            "auditTrail": [{"action": t.action, "operator": t.operator_name or "",
                            "detail": t.detail_json or {}, "occurredAt": _iso(t.occurred_at)}
                           for t in trail],
        }


def list_my_changes(rec, stu):
    with session() as db:
        rows = db.scalars(select(InternshipChangeRequest).where(
            InternshipChangeRequest.tenant_id == _tid(), InternshipChangeRequest.internship_id == rec.id,
            InternshipChangeRequest.student_id == stu.id, InternshipChangeRequest.is_deleted.is_(False)
        ).order_by(InternshipChangeRequest.id.desc())).all()
        histories = _approved_histories(db, rows)
        return [_row(c, rec, stu, histories.get(c.id)) for c in rows]


def student_apply(rec, stu, body) -> dict:
    b = body or {}
    ctype = (b.get("changeType") or "").upper()
    if ctype not in TYPE_LABEL:
        raise AppException("VALIDATION_ERROR", "变更类型无效")
    reason = (b.get("reason") or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "变更原因必填且不少于 5 字")
    if ctype in ("CHANGE_POSITION", "CHANGE_ENTERPRISE") and not b.get("targetPositionId"):
        label = "换单位" if ctype == "CHANGE_ENTERPRISE" else "换岗"
        raise AppException("VALIDATION_ERROR", f"{label}必须选择目标岗位")
    with session() as db:
        pending = db.scalars(select(InternshipChangeRequest).where(
            InternshipChangeRequest.tenant_id == _tid(), InternshipChangeRequest.internship_id == rec.id,
            InternshipChangeRequest.status == "PENDING", InternshipChangeRequest.is_deleted.is_(False))).first()
        if pending:
            raise AppException("DATA_CONFLICT", _DUP_PENDING_MSG)
        target_position = target_company = None
        if ctype in ("CHANGE_POSITION", "CHANGE_ENTERPRISE"):
            target_position, target_company = validate_target_position(
                db, rec, stu, b.get("targetPositionId"), change_type=ctype)
        c = InternshipChangeRequest(
            tenant_id=_tid(), internship_id=rec.id, student_id=stu.id, change_type=ctype, reason=reason,
            target_enterprise_id=(target_company.id if target_company else
                                  (int(b["targetEnterpriseId"]) if b.get("targetEnterpriseId") else None)),
            target_position_id=target_position.id if target_position else None,
            target_enterprise_name=(target_company.name if target_company else
                                    ((b.get("targetEnterpriseName") or "").strip() or None)),
            target_position_name=(target_position.title if target_position else
                                  ((b.get("targetPositionName") or "").strip() or None)),
            record_version_snapshot=int(rec.version or 0),
            status="PENDING")
        db.add(c)
        try:
            db.flush()
        except IntegrityError as exc:
            # 唯一索引在 flush 这一步就会拒绝（INSERT 此时已发出），不是等到 commit。
            db.rollback()
            raise AppException("DATA_CONFLICT", _DUP_PENDING_MSG) from exc
        _trail(db, c.id, "APPLY", {"changeType": ctype})
        from app.modules.internship.services import internship_todo_helper as ix_todo
        ix_todo.push_change_todo(db, c, rec)
        try:
            db.commit()
        except IntegrityError as exc:
            # 上面那次查重是无锁读，两个并发请求会同时看到「没有待审核」。真正的不变量由
            # uk_ix_change_active_pending 兜底（迁移 20260814_ix_first_create）；输家在这里
            # 转成业务冲突，拿到的提示与串行重复申请完全一致，而不是一个 500。
            db.rollback()
            raise AppException("DATA_CONFLICT", _DUP_PENDING_MSG) from exc
        return _row(c, rec, stu)


def withdraw_change(cid, rec, stu) -> dict:
    with session() as db:
        c = db.get(InternshipChangeRequest, _as_id(cid))
        if not c or c.is_deleted or c.tenant_id != _tid():
            raise not_found("变更申请不存在")
        if c.internship_id != rec.id or c.student_id != stu.id:
            raise no_permission("只能撤回本人的变更申请")
        if c.status != "PENDING":
            raise AppException("DATA_CONFLICT", "仅待审核申请可撤回")
        c.status = "WITHDRAWN"
        _trail(db, c.id, "WITHDRAW", {})
        from app.modules.internship.services import internship_todo_helper as ix_todo
        ix_todo.todo_done(db, biz_id=c.id, todo_type=ix_todo.change_todo_type(c))
        db.commit()
        return {"id": str(c.id), "status": "WITHDRAWN"}


def _void_prior_compliance(db, record: InternshipRecord, change: InternshipChangeRequest,
                           user=None) -> None:
    """A destination change invalidates prior consent and active agreements in the same transaction."""
    from app.modules.internship.services.internship_consent_service import supersede_for_major_change

    supersede_for_major_change(db, record.id)
    agreements = db.scalars(select(InternshipAgreement).where(
        InternshipAgreement.tenant_id == _tid(),
        InternshipAgreement.internship_id == record.id,
        InternshipAgreement.status.in_((
            "DRAFT", "PENDING_STUDENT", "PENDING_ENTERPRISE", "PENDING_SCHOOL", "EFFECTIVE")),
        InternshipAgreement.is_deleted.is_(False),
    ).with_for_update()).all()
    for agreement in agreements:
        before = agreement.status
        agreement.status = "VOIDED"
        agreement.reject_reason = f"实习变更单 {change.id} 已通过，原协议失效并须重新办理"
        agreement.version = int(agreement.version or 0) + 1
        db.add(InternshipAuditTrail(
            tenant_id=_tid(), target_id=agreement.id, target_type="AGREEMENT",
            action="VOID_BY_CHANGE", operator_name=_op_name(user),
            detail_json={"changeId": str(change.id), "beforeStatus": before},
            occurred_at=datetime.utcnow()))


def review_change(cid, action: str, comment: str = "", user=None, *, expected_version=None,
                  record_expected_version=None, expected_batch_id=None) -> dict:
    from app.modules.internship.services.internship_version import (
        extract_expected_version, versioned_update,
    )

    action = str(action or "").upper()
    if action not in ("APPROVE", "REJECT"):
        raise AppException("VALIDATION_ERROR", "action 必须是 APPROVE/REJECT")
    review_comment = str(comment or "").strip()
    if action == "REJECT" and len(review_comment) < 5:
        raise AppException("VALIDATION_ERROR", "驳回原因必填且不少于 5 字")
    change_version = extract_expected_version({"expectedVersion": expected_version})

    with session() as db:
        change = db.scalar(select(InternshipChangeRequest).where(
            InternshipChangeRequest.id == _as_id(cid),
            InternshipChangeRequest.tenant_id == _tid(),
            InternshipChangeRequest.is_deleted.is_(False)))
        if not change:
            raise not_found("变更申请不存在")
        if change.status != "PENDING":
            raise AppException("DATA_CONFLICT", "仅待审核申请可处理")
        record = db.scalar(select(InternshipRecord).where(
            InternshipRecord.id == change.internship_id,
            InternshipRecord.tenant_id == _tid(),
            InternshipRecord.is_deleted.is_(False)).with_for_update())
        if not record:
            raise not_found("实习主记录不存在")
        # 学生提交、撤回、补正和教师办理统一先锁主记录，再锁变更单。
        change = db.scalar(select(InternshipChangeRequest).where(
            InternshipChangeRequest.id == change.id,
            InternshipChangeRequest.tenant_id == _tid(),
            InternshipChangeRequest.is_deleted.is_(False),
        ).with_for_update().execution_options(populate_existing=True))
        if not change or change.status != "PENDING":
            raise AppException("DATA_CONFLICT", "申请状态已变化，请刷新后重试")
        student = db.scalar(select(StudentProfile).where(
            StudentProfile.id == change.student_id,
            StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False)))
        _scope_check(db, record, student, user)
        if expected_batch_id is not None and int(record.batch_id or 0) != int(_as_id(expected_batch_id)):
            raise AppException("DATA_CONFLICT", "申请已不属于当前所选批次，请刷新批次后重试")

        snapshot = int(change.record_version_snapshot or 0)
        if action == "APPROVE":
            expected_record = snapshot if record_expected_version is None else extract_expected_version(
                {"expectedVersion": record_expected_version})
            if expected_record != snapshot:
                raise AppException("DATA_CONFLICT", "页面实习记录版本与申请快照不一致，请刷新")
            if int(record.version or 0) != snapshot:
                raise AppException(
                    "DATA_CONFLICT",
                    "学生实习主记录在申请后已变化，请退回申请并由学生基于最新数据重新提交",
                )
        before = {
            "recordVersion": int(record.version or 0),
            "positionId": str(record.position_id or ""),
            "enterpriseId": str(record.enterprise_id or ""),
            "positionName": record.position_name or "",
            "enterpriseName": record.enterprise_name or "",
            "mentorContactId": str(record.mentor_contact_id or ""),
            "destinationType": record.destination_type,
            "status": record.status,
        }
        if action == "APPROVE":
            change_type = change.change_type
            if change_type in ("CHANGE_POSITION", "CHANGE_ENTERPRISE"):
                if not change.target_position_id:
                    label = "换单位" if change_type == "CHANGE_ENTERPRISE" else "换岗"
                    raise AppException("DATA_CONFLICT", f"{label}申请缺少目标岗位编号，不可通过")
                validate_target_position(
                    db, record, student, change.target_position_id, change_type=change_type)
                stu_svc.assign_position_in_tx(
                    db, record, change.target_position_id, snapshot, user=user)
                record.status = _next_record_status(record)
                record.intern_start_date = None
            elif change_type == "WITHDRAW_POST":
                next_status = _next_record_status(record)
                stu_svc.unassign_position_in_tx(
                    db, record, snapshot, change.reason or "退岗审核通过",
                    user=user, next_status=next_status)
                record.intern_start_date = None
            elif change_type == "SELF_ARRANGED":
                enterprise_name = str(change.target_enterprise_name or "").strip()
                position_name = str(change.target_position_name or "").strip()
                if len(enterprise_name) < 2 or len(position_name) < 2:
                    raise AppException("DATA_CONFLICT", "转自主实习必须填写完整的目标单位和岗位")
                if record.position_id:
                    stu_svc.unassign_position_in_tx(
                        db, record, snapshot, change.reason or "转自主实习",
                        user=user, next_status=_next_record_status(record))
                else:
                    record.version = snapshot + 1
                record.enterprise_id = None
                record.position_id = None
                record.mentor_contact_id = None
                record.enterprise_name = enterprise_name
                record.position_name = position_name
                record.enterprise_mentor_name = None
                record.destination_type = "SELF_ARRANGED"
                record.current_placement_snapshot_id = None
                record.current_application_id = None
                record.status = _next_record_status(record)
                record.intern_start_date = None
                stu_svc._trail(db, record.id, "SET_SELF_ARRANGED_BY_CHANGE", {
                    "changeId": str(change.id), "recordVersion": int(record.version or 0),
                })
            else:
                raise AppException("VALIDATION_ERROR", "未知实习变更类型")
            _void_prior_compliance(db, record, change, user=user)

        status = "APPROVED" if action == "APPROVE" else "REJECTED"
        new_version = versioned_update(
            db, InternshipChangeRequest, entity_id=change.id, tenant_id=_tid(),
            expected_version=change_version, expected_status="PENDING",
            values={
                "status": status,
                "review_comment": review_comment or None,
                "reviewed_by_name": _op_name(user),
                "reviewed_at": datetime.utcnow(),
            },
        )
        _trail(db, change.id, action, {
            "comment": review_comment,
            "recordBefore": before,
            "recordAfter": {
                "recordVersion": int(record.version or 0),
                "positionId": str(record.position_id or ""),
                "enterpriseId": str(record.enterprise_id or ""),
                "positionName": record.position_name or "",
                "enterpriseName": record.enterprise_name or "",
                "mentorContactId": str(record.mentor_contact_id or ""),
                "destinationType": record.destination_type,
                "status": record.status,
            } if action == "APPROVE" else before,
            "atomic": True,
        }, operator=_op_name(user))
        from app.modules.internship.services import internship_todo_helper as ix_todo
        ix_todo.todo_done(db, biz_id=change.id, todo_type=ix_todo.change_todo_type(change))
        db.commit()
        receipt_impact = _impact_preview(change, record) if action == "APPROVE" else {
            "requiresReonboard": False,
            "nextRecordStatus": record.status,
            "nextRecordStatusLabel": stu_svc.STATUS_LABEL.get(record.status, record.status),
            "impactItems": [],
            "nextStep": "等待学生根据驳回意见补充信息或重新提交变更申请",
        }
        return {
            "id": str(change.id), "status": status,
            "statusLabel": STATUS_LABEL.get(status), "version": new_version,
            "recordVersion": int(record.version or 0),
            "recordStatus": record.status,
            "recordStatusLabel": stu_svc.STATUS_LABEL.get(record.status, record.status),
            **receipt_impact,
        }
