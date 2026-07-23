"""岗位实习 · 三方协议签署实例（P2-A）。

三方确认流：DRAFT →(下发) PENDING_STUDENT →(学生确认) PENDING_ENTERPRISE
→(记录企业签署+扫描件) PENDING_SCHOOL →(学校确认) EFFECTIVE；旁支 REJECTED/VOIDED/ARCHIVED。
无电子签章时企业确认以「上传纸质三方协议签署扫描件 file_id」为准（不伪造电子签，esign_status 预留）。
owner：学生本人确认（mobile）；教师/管理员生成/下发/推进/作废/归档（PC，owner + 数据范围）。
审计 target_type=AGREEMENT。
"""
from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, no_permission, not_found
from app.models import (InternshipAgreement, InternshipAgreementTemplate, InternshipAuditTrail,
                        InternshipRecord, Major, SchoolClass, StudentProfile, Tenant)
from app.services.db_service import _as_id, _iso, _tid, session

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
    a = db.get(InternshipAgreement, _as_id(aid))
    if not a or a.is_deleted or a.tenant_id != _tid():
        raise not_found("协议不存在")
    return a


def _cn_date(v) -> str:
    """正式文书日期格式（BUG-011）：2026-03-02T00:00:00 → 2026年3月2日。空值返回空串。"""
    s = _iso(v) or ""
    if len(s) < 10:
        return ""
    try:
        y, m, d = int(s[0:4]), int(s[5:7]), int(s[8:10])
    except ValueError:
        return s[:10]
    return f"{y}年{m}月{d}日"


_ISO_DT_IN_TEXT = re.compile(r"(\d{4})-(\d{2})-(\d{2})T\d{2}:\d{2}(?::\d{2})?")


def _normalize_body_dates(text: str | None) -> str:
    """把正文里的 ISO 时间戳规范成中文日期（只影响展示/打印，不改写库中快照）。"""
    if not text:
        return ""
    return _ISO_DT_IN_TEXT.sub(lambda m: f"{int(m.group(1))}年{int(m.group(2))}月{int(m.group(3))}日", text)


def _render_body(db, tpl: "InternshipAgreementTemplate | None", rec, stu, a) -> str:
    """协议正文渲染：有模板按 {{变量}} 替换（支持模板变量预设全集，见
    internship_agreement_template_service.VARIABLE_PRESETS）；无模板/变量缺失时用
    结构化字段兜底，保证 rendered_body 永不为空——学生小程序确认按钮以 renderedBody
    是否存在作为可点击前提。db 为 None（历史协议只读兜底）时班级/学院/专业/学校名留空，
    不影响兜底文案（兜底文案不用这几个变量）。"""
    class_name = college_name = major_name = school_name = ""
    if db is not None:
        if stu is not None:
            from app.modules.internship.services.internship_service import (
                resolve_student_class_college_names)
            class_name, college_name = resolve_student_class_college_names(db, stu)
            class_name = class_name or ""
            college_name = college_name or ""
            if getattr(stu, "major_id", None):
                maj = db.get(Major, stu.major_id)
                major_name = (maj.major_name if maj else "") or ""
            elif getattr(stu, "class_id", None):
                c = db.get(SchoolClass, stu.class_id)
                if c and c.major_id:
                    maj = db.get(Major, c.major_id)
                    major_name = (maj.major_name if maj else "") or ""
        t = db.get(Tenant, _tid())
        school_name = (t.school_name if t else "") or ""
    advisor_name = (rec.advisor_name if rec else "") or ""
    ctx = {
        "studentName": (stu.real_name if stu else "") or "",
        "studentNo": (stu.student_no if stu else "") or "",
        "className": class_name,
        "collegeName": college_name,
        "majorName": major_name,
        "companyName": a.enterprise_name or (rec.enterprise_name if rec else "") or "",
        "enterpriseName": a.enterprise_name or (rec.enterprise_name if rec else "") or "",
        "positionName": a.position_name or (rec.position_name if rec else "") or "",
        "mentorName": (rec.enterprise_mentor_name if rec else "") or "",
        # teacherName 是模板变量预设里的对外命名，advisorName 是历史 key，两者同值同存，
        # 正文里写哪个都能替换，避免前端变量清单 key 与渲染 key 对不上。
        "teacherName": advisor_name,
        "advisorName": advisor_name,
        "internPeriod": (f"{_cn_date(rec.intern_start_date)} 至 {_cn_date(rec.intern_end_date)}"
                         if rec and (rec.intern_start_date or rec.intern_end_date) else ""),
        "internStartDate": _cn_date(rec.intern_start_date) if rec else "",
        "internEndDate": _cn_date(rec.intern_end_date) if rec else "",
        "schoolName": school_name,
        "signDate": _cn_date(datetime.utcnow()),
    }
    if tpl and (tpl.body or "").strip():
        text = tpl.body
        for k, v in ctx.items():
            text = text.replace("{{" + k + "}}", v).replace("{{ " + k + " }}", v)
        return text
    return (
        f"三方实习协议\n\n学生：{ctx['studentName']}（学号 {ctx['studentNo']}）\n"
        f"实习企业：{ctx['companyName']}\n岗位：{ctx['positionName']}\n"
        f"实习期间：{ctx['internPeriod']}\n指导教师：{ctx['advisorName']}\n\n"
        f"本协议由学生、实习企业、学校三方确认后生效，各方权利义务以学校实习管理规定为准。"
    )


def _ctx(db, a):
    rec = db.get(InternshipRecord, a.internship_id)
    stu = db.get(StudentProfile, a.student_id)
    return rec, stu


def _scope_ctx(user):
    from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
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


def _row(db, a, rec, stu):
    return {
        "id": str(a.id), "internId": str(a.internship_id),
        "studentName": stu.real_name if stu else "-", "studentNo": stu.student_no if stu else "-",
        "advisorName": rec.advisor_name if rec else "",
        "enterpriseName": a.enterprise_name or (rec.enterprise_name if rec else ""),
        "positionName": a.position_name or (rec.position_name if rec else ""),
        "templateId": str(a.template_id) if a.template_id else "",
        "studentConfirm": a.student_confirm_status, "studentConfirmLabel": CONFIRM_LABEL.get(a.student_confirm_status),
        "enterpriseConfirm": a.enterprise_confirm_status, "enterpriseConfirmLabel": CONFIRM_LABEL.get(a.enterprise_confirm_status),
        "schoolConfirm": a.school_confirm_status, "schoolConfirmLabel": CONFIRM_LABEL.get(a.school_confirm_status),
        "status": a.status, "statusLabel": STATUS_LABEL.get(a.status, a.status),
        "esignStatus": a.esign_status, "hasFile": bool(a.file_id),
        "createdAt": _iso(a.created_at) or "",
        # 历史协议（本次修复前生成）rendered_body 为空时按结构化字段兜底渲染，不写库、只读时补齐
        # BUG-011：历史快照里遗留的 ISO 时间戳（2026-03-02T00:00:00）在展示/打印时规范为中文日期
        "renderedBody": _normalize_body_dates(a.rendered_body or _render_body(db, None, rec, stu, a)),
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
        rec = db.get(InternshipRecord, _as_id(iid))
        if not rec or rec.is_deleted or rec.tenant_id != _tid():
            raise not_found("实习记录不存在")
        stu = db.get(StudentProfile, rec.student_id)
        if not in_scope(scope, db, rec, stu):
            raise no_permission("只能为本人指导学生生成协议")
        tpl = None
        if tpl_id:
            tpl = db.get(InternshipAgreementTemplate, _as_id(tpl_id))
            if not tpl or tpl.is_deleted or tpl.tenant_id != _tid():
                raise not_found("协议模板不存在")
        exist = db.scalars(select(InternshipAgreement).where(
            InternshipAgreement.tenant_id == _tid(), InternshipAgreement.internship_id == rec.id,
            InternshipAgreement.status.notin_(["VOIDED", "REJECTED"]),
            InternshipAgreement.is_deleted.is_(False))).first()
        if exist:
            raise AppException("DATA_CONFLICT", "该实习记录已有进行中的协议，请勿重复生成")
        a = InternshipAgreement(
            tenant_id=_tid(), internship_id=rec.id, student_id=rec.student_id,
            template_id=int(tpl_id) if tpl_id else None, batch_id=rec.batch_id,
            enterprise_name=rec.enterprise_name, position_name=rec.position_name, status="DRAFT")
        a.rendered_body = _render_body(db, tpl, rec, stu, a)
        db.add(a); db.flush()
        _trail(db, a.id, "GENERATE", {"templateId": str(tpl_id) if tpl_id else ""}, operator=_op_name(user))
        db.commit()
        return {"id": str(a.id), "status": a.status}


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
    """记录企业签署：PENDING_ENTERPRISE → PENDING_SCHOOL。要求上传纸质签署扫描件(file_id)。"""
    b = body or {}
    file_id = _validate_file(b.get("fileId"), required=True, msg="企业签署的三方协议扫描件")
    with session() as db:
        a = _get(db, aid)
        _owner_or_403(db, a, user, "只能推进本人指导学生的协议")
        if a.status != "PENDING_ENTERPRISE":
            raise AppException("DATA_CONFLICT", "当前状态不可记录企业确认")
        a.enterprise_confirm_status = "CONFIRMED"
        a.enterprise_confirm_at = datetime.utcnow()
        a.enterprise_confirm_by = (b.get("confirmBy") or "").strip() or None
        a.file_id = file_id
        a.status = "PENDING_SCHOOL"
        a.version += 1
        _trail(db, a.id, "ENTERPRISE_CONFIRM", {"confirmBy": a.enterprise_confirm_by, "hasFile": True},
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


# ═══════════ 电子签流转（P3；三方齐签 → EFFECTIVE，无第三方签章时以平台内部签署时间线为准） ═══════════
_ESIGN_PARTIES = ("STUDENT", "ENTERPRISE", "SCHOOL")


def esign_start(user, aid) -> dict:
    """发起电子签：记录发起人/时间，esign_status → PENDING。协议须处于三方确认流转中。"""
    with session() as db:
        a = _get(db, aid)
        _owner_or_403(db, a, user, "只能对本人指导学生的协议发起电子签")
        if a.status not in ("PENDING_STUDENT", "PENDING_ENTERPRISE", "PENDING_SCHOOL"):
            raise AppException("DATA_CONFLICT", "仅待确认流转中的协议可发起电子签")
        a.esign_status = "PENDING"
        a.esign_initiated_at = datetime.utcnow()
        a.esign_initiated_by = _op_name(user)
        a.version += 1
        _trail(db, a.id, "ESIGN_START", {"provider": a.esign_provider}, operator=_op_name(user))
        db.commit()
        return {"id": str(a.id), "esignStatus": a.esign_status, "status": a.status}


def esign_sign(user, aid, party: str) -> dict:
    """某一方电子签署。STUDENT 由学生本人(mobile)；ENTERPRISE/SCHOOL 由教师/管理员(PC，owner)。
    三方齐签 → esign_status SIGNED + 协议 EFFECTIVE。"""
    party = (party or "").upper()
    if party not in _ESIGN_PARTIES:
        raise AppException("VALIDATION_ERROR", "签署方无效（STUDENT/ENTERPRISE/SCHOOL）")
    with session() as db:
        a = _get(db, aid)
        if a.esign_status not in ("PENDING", "SIGNED"):
            raise AppException("DATA_CONFLICT", "请先发起电子签")
        if party == "STUDENT":
            _, stu = _student_record(db, user)
            if not stu or stu.id != a.student_id:
                raise no_permission("只能签署本人的三方协议")
            a.esign_student_at = datetime.utcnow()
            a.student_confirm_status = "CONFIRMED"
            a.student_confirm_at = a.student_confirm_at or datetime.utcnow()
        else:
            _owner_or_403(db, a, user, "只能签署本人指导学生的协议")
            if party == "ENTERPRISE":
                # 企业方电子签不可由学校教师代签；正式路径为纸质扫描件确认
                raise AppException(
                    "VALIDATION_ERROR",
                    "企业方请走纸质三方协议扫描件确认，不可由教师代签企业电子签")
            a.esign_school_at = datetime.utcnow()
            a.school_confirm_status = "CONFIRMED"
            a.school_confirm_at = a.school_confirm_at or datetime.utcnow()
            a.school_confirm_by = _op_name(user)
        all_signed = bool(a.esign_student_at and a.esign_enterprise_at and a.esign_school_at)
        if all_signed:
            a.esign_status = "SIGNED"
            a.status = "EFFECTIVE"
        a.version += 1
        _trail(db, a.id, "ESIGN_SIGN", {"party": party, "allSigned": all_signed}, operator=_op_name(user))
        db.commit()
        return {"id": str(a.id), "esignStatus": a.esign_status, "status": a.status, "party": party}


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
            items.append(_row(db, a, rec, stu))
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
        return {**_row(db, a, rec, stu), "rejectReason": a.reject_reason or "",
                "attachment": file_service.attachment_view(a.file_id),
                "auditTrail": [{"action": t.action, "operator": t.operator_name or "",
                                "detail": t.detail_json or {}, "occurredAt": _iso(t.occurred_at)}
                               for t in trail]}


def get_student_agreement(user, aid) -> dict:
    """学生本人查看协议详情（含渲染正文）。此前路由调用的同名函数不存在（必现500），
    且误用教师端 get_agreement() 的教师数据范围校验对学生本人也不适用——改为按
    my_agreements() 同款的本人实习记录关联校验。"""
    from app.services import file_service
    with session() as db:
        a = _get(db, aid)
        rec, stu = _student_record(db, user)
        if not rec or a.internship_id != rec.id:
            raise no_permission("只能查看本人的协议")
        trail = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == _tid(), InternshipAuditTrail.target_type == "AGREEMENT",
            InternshipAuditTrail.target_id == a.id).order_by(InternshipAuditTrail.id)).all()
        return {**_row(db, a, rec, stu), "rejectReason": a.reject_reason or "",
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


# ═══════════ 学生本人（移动端） ═══════════

def my_agreements(user) -> list[dict]:
    with session() as db:
        rec, stu = _student_record(db, user)
        if not rec:
            return []
        rows = db.scalars(select(InternshipAgreement).where(
            InternshipAgreement.tenant_id == _tid(), InternshipAgreement.internship_id == rec.id,
            InternshipAgreement.is_deleted.is_(False)).order_by(InternshipAgreement.id.desc())).all()
        return [_row(db, a, rec, stu) for a in rows]


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
