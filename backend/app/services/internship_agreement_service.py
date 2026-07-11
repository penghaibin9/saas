"""岗位实习 · 三方协议签署实例（P2-A）。

三方确认流：DRAFT →(下发) PENDING_STUDENT →(学生确认) PENDING_ENTERPRISE
→(记录企业签署+扫描件) PENDING_SCHOOL →(学校确认) EFFECTIVE；旁支 REJECTED/VOIDED/ARCHIVED。
无电子签章时企业确认以「上传纸质三方协议签署扫描件 file_id」为准（不伪造电子签，esign_status 预留）。
owner：学生本人确认（mobile）；教师/管理员生成/下发/推进/作废/归档（PC，owner + 数据范围）。
审计 target_type=AGREEMENT。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, no_permission, not_found
from app.models import (InternshipAgreement, InternshipAgreementTemplate, InternshipAuditTrail,
                        InternshipRecord, StudentProfile)
from app.services.db_service import _iso, _tid, session

STATUS_LABEL = {"DRAFT": "草稿", "PENDING_STUDENT": "待学生确认", "PENDING_ENTERPRISE": "待企业确认",
                "PENDING_SCHOOL": "待学校确认", "EFFECTIVE": "已生效", "REJECTED": "已驳回",
                "VOIDED": "已作废", "ARCHIVED": "已归档"}
CONFIRM_LABEL = {"PENDING": "待确认", "CONFIRMED": "已确认", "REJECTED": "已驳回"}


def _op_name(user) -> str:
    return (user or {}).get("realName") or "系统"


def _trail(db, aid, action, detail=None, operator="系统"):
    db.add(InternshipAuditTrail(tenant_id=_tid(), target_id=aid, target_type="AGREEMENT",
                                action=action, operator_name=operator, detail_json=detail or {},
                                occurred_at=datetime.utcnow()))


def _get(db, aid) -> InternshipAgreement:
    a = db.get(InternshipAgreement, int(aid))
    if not a or a.is_deleted or a.tenant_id != _tid():
        raise not_found("协议不存在")
    return a


def _ctx(db, a):
    rec = db.get(InternshipRecord, a.internship_id)
    stu = db.get(StudentProfile, a.student_id)
    return rec, stu


def _scope_ctx(user):
    from app.services.internship_service import _current_scope, _rec_in_scope
    return _current_scope(user), _rec_in_scope


def _owner_or_403(db, a, user, msg):
    scope, in_scope = _scope_ctx(user)
    rec, stu = _ctx(db, a)
    if not in_scope(scope, db, rec, stu):
        raise no_permission(msg)
    return rec, stu


def _student_record(db, user):
    sno = (user or {}).get("studentNo")
    if not sno:
        return None, None
    stu = db.scalars(select(StudentProfile).where(
        StudentProfile.tenant_id == _tid(), StudentProfile.student_no == sno,
        StudentProfile.is_deleted.is_(False))).first()
    if not stu:
        return None, None
    rec = db.scalars(select(InternshipRecord).where(
        InternshipRecord.tenant_id == _tid(), InternshipRecord.student_id == stu.id,
        InternshipRecord.is_deleted.is_(False))).first()
    return rec, stu


def _row(a, rec, stu):
    return {
        "id": str(a.id), "internId": str(a.internship_id),
        "studentName": stu.real_name if stu else "-", "studentNo": stu.student_no if stu else "-",
        "advisorName": rec.advisor_name if rec else "",
        "enterpriseName": a.enterprise_name or (rec.enterprise_name if rec else ""),
        "positionName": a.position_name or (rec.position_name if rec else ""),
        "templateId": str(a.template_id) if a.template_id else "",
        "templateName": "",
        "studentConfirm": a.student_confirm_status, "studentConfirmLabel": CONFIRM_LABEL.get(a.student_confirm_status),
        "enterpriseConfirm": a.enterprise_confirm_status, "enterpriseConfirmLabel": CONFIRM_LABEL.get(a.enterprise_confirm_status),
        "schoolConfirm": a.school_confirm_status, "schoolConfirmLabel": CONFIRM_LABEL.get(a.school_confirm_status),
        "status": a.status, "statusLabel": STATUS_LABEL.get(a.status, a.status),
        "esignStatus": a.esign_status, "hasFile": bool(a.file_id),
        "esignProvider": getattr(a, "esign_provider", None) or "INTERNAL",
        "esignStudentSigned": bool(getattr(a, "esign_student_at", None)),
        "esignEnterpriseSigned": bool(getattr(a, "esign_enterprise_at", None)),
        "esignSchoolSigned": bool(getattr(a, "esign_school_at", None)),
        "createdAt": _iso(a.created_at) or "",
    }


def _validate_file(file_id, required=False, msg="签署扫描件"):
    fid = (file_id or "").strip()
    if not fid:
        if required:
            raise AppException("VALIDATION_ERROR", f"请先上传{msg}")
        return None
    from app.services import file_service
    if not file_service.get_file_meta(fid):
        raise AppException("VALIDATION_ERROR", f"{msg}不存在或无权访问，请重新上传")
    return fid


# ═══════════ 教师 / 管理员（PC，owner + 数据范围） ═══════════

def generate(user, body) -> dict:
    b = body or {}
    iid = b.get("internshipId") or b.get("internId")
    if not iid:
        raise AppException("VALIDATION_ERROR", "缺少实习记录 internshipId")
    tpl_id = b.get("templateId")
    scope, in_scope = _scope_ctx(user)
    with session() as db:
        rec = db.get(InternshipRecord, int(iid))
        if not rec or rec.is_deleted or rec.tenant_id != _tid():
            raise not_found("实习记录不存在")
        stu = db.get(StudentProfile, rec.student_id)
        if not in_scope(scope, db, rec, stu):
            raise no_permission("只能为本人指导学生生成协议")
        from app.services import internship_agreement_template_service as tpl_svc
        tpl = tpl_svc.resolve_template_for_record(db, rec, stu, tpl_id)
        rendered = ""
        if tpl:
            ctx = tpl_svc.build_agreement_context(db, rec, stu)
            rendered = tpl_svc.render_template_body(tpl.body, ctx)
            tpl_id = tpl.id
        exist = db.scalars(select(InternshipAgreement).where(
            InternshipAgreement.tenant_id == _tid(), InternshipAgreement.internship_id == rec.id,
            InternshipAgreement.status.notin_(["VOIDED", "REJECTED"]),
            InternshipAgreement.is_deleted.is_(False))).first()
        if exist:
            raise AppException("DATA_CONFLICT", "该实习记录已有进行中的协议，请勿重复生成")
        a = InternshipAgreement(
            tenant_id=_tid(), internship_id=rec.id, student_id=rec.student_id,
            template_id=int(tpl_id) if tpl_id else None, batch_id=rec.batch_id,
            enterprise_name=rec.enterprise_name, position_name=rec.position_name,
            rendered_body=rendered or None, status="DRAFT")
        db.add(a); db.flush()
        _trail(db, a.id, "GENERATE",
               {"templateId": str(tpl_id) if tpl_id else "", "hasRenderedBody": bool(rendered)},
               operator=_op_name(user))
        db.commit()
        return {"id": str(a.id), "status": a.status, "templateId": str(tpl_id) if tpl_id else "",
                "hasRenderedBody": bool(rendered)}


def issue(user, aid) -> dict:
    """下发：DRAFT → PENDING_STUDENT。"""
    with session() as db:
        a = _get(db, aid)
        _owner_or_403(db, a, user, "只能下发本人指导学生的协议")
        if a.status != "DRAFT":
            raise AppException("DATA_CONFLICT", "仅草稿协议可下发")
        a.status = "PENDING_STUDENT"
        a.version += 1
        _trail(db, a.id, "ISSUE", {}, operator=_op_name(user))
        db.commit()
        return {"id": str(a.id), "status": a.status, "statusLabel": STATUS_LABEL[a.status]}


def enterprise_confirm(user, aid, body) -> dict:
    """记录企业签署：PENDING_ENTERPRISE → PENDING_SCHOOL。电子签已签时可免扫描件。"""
    b = body or {}
    with session() as db:
        a = _get(db, aid)
        _owner_or_403(db, a, user, "只能推进本人指导学生的协议")
        if a.status != "PENDING_ENTERPRISE":
            raise AppException("DATA_CONFLICT", "当前状态不可记录企业确认")
        need_file = not getattr(a, "esign_enterprise_at", None)
        file_id = _validate_file(b.get("fileId"), required=need_file, msg="企业签署的三方协议扫描件")
        a.enterprise_confirm_status = "CONFIRMED"
        a.enterprise_confirm_at = datetime.utcnow()
        a.enterprise_confirm_by = (b.get("confirmBy") or "").strip() or None
        if file_id:
            a.file_id = file_id
        a.status = "PENDING_SCHOOL"
        a.version += 1
        _trail(db, a.id, "ENTERPRISE_CONFIRM", {"confirmBy": a.enterprise_confirm_by,
                                                  "hasFile": bool(file_id), "esignSigned": not need_file},
               operator=_op_name(user))
        db.commit()
        return {"id": str(a.id), "status": a.status, "statusLabel": STATUS_LABEL[a.status]}


def school_confirm(user, aid) -> dict:
    """学校确认：PENDING_SCHOOL → EFFECTIVE。"""
    with session() as db:
        a = _get(db, aid)
        _owner_or_403(db, a, user, "只能确认本人指导学生的协议")
        if a.status != "PENDING_SCHOOL":
            raise AppException("DATA_CONFLICT", "仅待学校确认的协议可确认生效")
        a.school_confirm_status = "CONFIRMED"
        a.school_confirm_at = datetime.utcnow()
        a.school_confirm_by = _op_name(user)
        a.status = "EFFECTIVE"
        a.version += 1
        _trail(db, a.id, "SCHOOL_CONFIRM", {}, operator=_op_name(user))
        db.commit()
        return {"id": str(a.id), "status": a.status, "statusLabel": STATUS_LABEL[a.status]}


def reject(user, aid, reason="") -> dict:
    if not (reason or "").strip() or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "驳回原因必填且不少于 5 字")
    with session() as db:
        a = _get(db, aid)
        _owner_or_403(db, a, user, "只能驳回本人指导学生的协议")
        if a.status not in ("PENDING_STUDENT", "PENDING_ENTERPRISE", "PENDING_SCHOOL"):
            raise AppException("DATA_CONFLICT", "当前状态不可驳回")
        a.status = "REJECTED"
        a.reject_reason = reason.strip()
        a.version += 1
        _trail(db, a.id, "REJECT", {"reason": reason.strip()}, operator=_op_name(user))
        db.commit()
        return {"id": str(a.id), "status": a.status}


def void(user, aid, reason="") -> dict:
    with session() as db:
        a = _get(db, aid)
        _owner_or_403(db, a, user, "只能作废本人指导学生的协议")
        if a.status in ("EFFECTIVE", "ARCHIVED", "VOIDED"):
            raise AppException("DATA_CONFLICT", "已生效/已归档/已作废协议不可作废")
        a.status = "VOIDED"
        a.is_deleted = False
        a.reject_reason = (reason or "").strip() or a.reject_reason
        a.version += 1
        _trail(db, a.id, "VOID", {"reason": (reason or "").strip()}, operator=_op_name(user))
        db.commit()
        return {"id": str(a.id), "status": a.status}


def archive(user, aid) -> dict:
    with session() as db:
        a = _get(db, aid)
        _owner_or_403(db, a, user, "只能归档本人指导学生的协议")
        if a.status != "EFFECTIVE":
            raise AppException("DATA_CONFLICT", "仅已生效协议可归档")
        a.status = "ARCHIVED"
        a.version += 1
        _trail(db, a.id, "ARCHIVE", {}, operator=_op_name(user))
        db.commit()
        return {"id": str(a.id), "status": a.status}


def list_agreements(page, page_size, status=None, keyword=None, user=None):
    scope, in_scope = _scope_ctx(user)
    with session() as db:
        q = select(InternshipAgreement).where(InternshipAgreement.tenant_id == _tid(),
                                              InternshipAgreement.is_deleted.is_(False))
        if status:
            q = q.where(InternshipAgreement.status == status)
        rows = db.scalars(q.order_by(InternshipAgreement.id.desc())).all()
        items = []
        for a in rows:
            rec, stu = _ctx(db, a)
            if keyword and (not stu or keyword.strip() not in (stu.real_name or "")):
                continue
            if not in_scope(scope, db, rec, stu):
                continue
            items.append(_row(a, rec, stu))
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


def get_agreement(aid, user=None) -> dict:
    from app.services import file_service
    scope, in_scope = _scope_ctx(user)
    with session() as db:
        a = _get(db, aid)
        rec, stu = _ctx(db, a)
        if not in_scope(scope, db, rec, stu):
            raise no_permission("该协议不在你的数据范围内")
        trail = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == _tid(), InternshipAuditTrail.target_type == "AGREEMENT",
            InternshipAuditTrail.target_id == a.id).order_by(InternshipAuditTrail.id)).all()
        tpl_name = ""
        if a.template_id:
            tpl = db.get(InternshipAgreementTemplate, a.template_id)
            tpl_name = tpl.name if tpl else ""
        return {**_row(a, rec, stu), "templateName": tpl_name,
                "renderedBody": a.rendered_body or "",
                "rejectReason": a.reject_reason or "",
                "attachment": file_service.attachment_view(a.file_id),
                "auditTrail": [{"action": t.action, "operator": t.operator_name or "",
                                "detail": t.detail_json or {}, "occurredAt": _iso(t.occurred_at)}
                               for t in trail]}


def export_agreements(status=None, keyword=None, user=None) -> dict:
    from app.services import xlsx_util
    items, _ = list_agreements(1, 100000, status=status, keyword=keyword, user=user)
    headers = ["学号", "姓名", "指导教师", "企业", "岗位", "学生确认", "企业确认", "学校确认", "协议状态"]
    rows = [[it["studentNo"], it["studentName"], it["advisorName"], it["enterpriseName"],
             it["positionName"], it["studentConfirmLabel"], it["enterpriseConfirmLabel"],
             it["schoolConfirmLabel"], it["statusLabel"]] for it in items]
    wm = f"岗位实习中心·三方协议台账 · 导出人：{_op_name(user)} · {datetime.now():%Y-%m-%d %H:%M} · 导出留痕"
    content = xlsx_util.build_ledger_xlsx("三方协议台账", headers, rows, watermark=wm)
    return xlsx_util.pack_xlsx_result(content, "三方协议台账.xlsx", len(items))


def export_agreement_pdf(aid, user=None) -> dict:
    """三方协议 PDF 套打：基于 rendered_body 快照生成可下载 PDF（含水印）。"""
    from app.services import pdf_util
    with session() as db:
        a = _get(db, aid)
        rec, stu = _ctx(db, a)
        _owner_or_403(db, a, user, "该协议不在你的数据范围内")
        body = (a.rendered_body or "").strip()
        if not body:
            raise AppException("VALIDATION_ERROR", "协议正文尚未生成，请先生成或重新下发协议")
        tpl_name = ""
        if a.template_id:
            tpl = db.get(InternshipAgreementTemplate, a.template_id)
            tpl_name = tpl.name if tpl else ""
        title = f"岗位实习三方协议 · {stu.real_name if stu else ''}（{stu.student_no if stu else ''}）"
        wm = (f"岗位实习中心·三方协议套打 · 导出人：{_op_name(user)} · "
              f"{datetime.now():%Y-%m-%d %H:%M} · 协议编号 {a.id}")
        content = pdf_util.build_text_pdf(title, body, watermark=wm)
        fname = f"三方协议_{stu.student_no if stu else a.id}_{tpl_name or '套打'}.pdf"
        return pdf_util.pack_pdf_result(content, fname)


# ═══════════ 学生本人（移动端） ═══════════

def _student_row(a, rec, stu, db):
    tpl_name = ""
    if a.template_id:
        tpl = db.get(InternshipAgreementTemplate, a.template_id)
        tpl_name = tpl.name if tpl else ""
    return {**_row(a, rec, stu), "templateName": tpl_name,
            "renderedBody": a.rendered_body or "",
            "rejectReason": a.reject_reason or ""}


def my_agreements(user) -> list[dict]:
    with session() as db:
        rec, stu = _student_record(db, user)
        if not rec:
            return []
        rows = db.scalars(select(InternshipAgreement).where(
            InternshipAgreement.tenant_id == _tid(), InternshipAgreement.internship_id == rec.id,
            InternshipAgreement.is_deleted.is_(False)).order_by(InternshipAgreement.id.desc())).all()
        return [_student_row(a, rec, stu, db) for a in rows]


def get_student_agreement(user, aid) -> dict:
    """学生本人协议详情（含渲染正文，供确认前阅读）。"""
    with session() as db:
        a = _get(db, aid)
        rec, stu = _student_record(db, user)
        if not rec or a.internship_id != rec.id:
            raise no_permission("只能查看本人的协议")
        trail = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == _tid(), InternshipAuditTrail.target_type == "AGREEMENT",
            InternshipAuditTrail.target_id == a.id).order_by(InternshipAuditTrail.id)).all()
        return {**_student_row(a, rec, stu, db),
                "auditTrail": [{"action": t.action, "operator": t.operator_name or "",
                                "occurredAt": _iso(t.occurred_at)} for t in trail]}


def student_confirm(user, aid, action: str, reason="") -> dict:
    """学生确认：PENDING_STUDENT →(CONFIRM) PENDING_ENTERPRISE /(REJECT) REJECTED。"""
    if action not in ("CONFIRM", "REJECT"):
        raise AppException("VALIDATION_ERROR", "action 必须是 CONFIRM/REJECT")
    if action == "REJECT" and (not reason or len(reason.strip()) < 5):
        raise AppException("VALIDATION_ERROR", "驳回原因必填且不少于 5 字")
    with session() as db:
        a = _get(db, aid)
        rec, _ = _student_record(db, user)
        if not rec or a.internship_id != rec.id:
            raise no_permission("只能确认本人的协议")
        if a.status != "PENDING_STUDENT":
            raise AppException("DATA_CONFLICT", "当前协议状态不可由学生确认")
        if action == "CONFIRM":
            a.student_confirm_status = "CONFIRMED"
            a.student_confirm_at = datetime.utcnow()
            a.status = "PENDING_ENTERPRISE"
        else:
            a.student_confirm_status = "REJECTED"
            a.status = "REJECTED"
            a.reject_reason = reason.strip()
        a.version += 1
        _trail(db, a.id, f"STUDENT_{action}", {"reason": (reason or "").strip()},
               operator=(user or {}).get("realName") or "学生")
        db.commit()
        return {"id": str(a.id), "status": a.status, "statusLabel": STATUS_LABEL[a.status]}


def _esign_complete(a) -> bool:
    return bool(getattr(a, "esign_student_at", None) and getattr(a, "esign_enterprise_at", None)
                and getattr(a, "esign_school_at", None))


def start_esign(user, aid) -> dict:
    """发起校内电子签流程（INTERNAL 提供方，留痕可审计；第三方 CA 预留 esign_provider=THIRD_PARTY）。"""
    with session() as db:
        a = _get(db, aid)
        _owner_or_403(db, a, user, "只能对本人指导学生的协议发起电子签")
        if a.status in ("REJECTED", "VOIDED", "ARCHIVED"):
            raise AppException("DATA_CONFLICT", "当前协议状态不可发起电子签")
        if a.esign_status == "SIGNED":
            raise AppException("DATA_CONFLICT", "电子签已完成")
        a.esign_status = "PENDING"
        a.esign_provider = "INTERNAL"
        a.esign_initiated_at = datetime.utcnow()
        a.esign_initiated_by = _op_name(user)
        _trail(db, a.id, "ESIGN_START", {"provider": a.esign_provider}, operator=_op_name(user))
        db.commit()
        return {"id": str(a.id), "esignStatus": a.esign_status, "message": "已发起电子签，请各方依次签署"}


def esign_sign(user, aid, party: str) -> dict:
    """电子签签署：STUDENT / ENTERPRISE / SCHOOL。"""
    party = (party or "").upper()
    if party not in ("STUDENT", "ENTERPRISE", "SCHOOL"):
        raise AppException("VALIDATION_ERROR", "party 必须是 STUDENT/ENTERPRISE/SCHOOL")
    with session() as db:
        a = _get(db, aid)
        if a.esign_status != "PENDING":
            raise AppException("DATA_CONFLICT", "电子签未发起或已完成")
        now = datetime.utcnow()
        op = _op_name(user)
        if party == "STUDENT":
            rec, stu = _student_record(db, user)
            if not rec or a.internship_id != rec.id:
                raise no_permission("只能签署本人的协议")
            if getattr(a, "esign_student_at", None):
                raise AppException("DATA_CONFLICT", "学生已电子签署")
            a.esign_student_at = now
            if a.status == "PENDING_STUDENT":
                a.student_confirm_status = "CONFIRMED"
                a.student_confirm_at = now
                a.status = "PENDING_ENTERPRISE"
        elif party == "ENTERPRISE":
            _owner_or_403(db, a, user, "只能代企业签署本人指导学生的协议")
            if getattr(a, "esign_enterprise_at", None):
                raise AppException("DATA_CONFLICT", "企业方已电子签署")
            a.esign_enterprise_at = now
            if a.status == "PENDING_ENTERPRISE":
                a.enterprise_confirm_status = "CONFIRMED"
                a.enterprise_confirm_at = now
                a.status = "PENDING_SCHOOL"
        else:
            _owner_or_403(db, a, user, "只能学校签署本人指导学生的协议")
            if getattr(a, "esign_school_at", None):
                raise AppException("DATA_CONFLICT", "学校方已电子签署")
            a.esign_school_at = now
            if a.status == "PENDING_SCHOOL":
                a.school_confirm_status = "CONFIRMED"
                a.school_confirm_at = now
                a.status = "EFFECTIVE"
        if _esign_complete(a):
            a.esign_status = "SIGNED"
        a.version += 1
        _trail(db, a.id, f"ESIGN_{party}", {}, operator=op)
        db.commit()
        return {
            "id": str(a.id), "status": a.status, "statusLabel": STATUS_LABEL.get(a.status),
            "esignStatus": a.esign_status, "esignComplete": _esign_complete(a),
        }
