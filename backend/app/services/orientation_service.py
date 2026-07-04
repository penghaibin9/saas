"""数字迎新域真实数据服务。租户过滤 + is_deleted + 脱敏 + 审计留痕。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.models import (GreenChannelApplication, OrientationAuditTrail, OrientationException,
                        OrientationExceptionFollowup, OrientationMaterial, OrientationStudent)
from app.services.db_service import _iso, _mask_id_card, _mask_phone, _tid, session

L_STAGE = {"ADMITTED": "已录取", "PRE_STUDENT_VERIFIED": "预报到已核验",
           "REGISTERED_PENDING_ENROLLMENT": "已报到待注册", "ENROLLED": "已入学",
           "DEFERRED": "延迟报到", "NO_SHOW": "未到校", "CANCELLED": "取消入学"}
L_REPORT = {"NOT_REPORTED": "未报到", "PREPARED": "预报到完成", "CHECKED_IN": "已现场报到",
            "COLLEGE_CONFIRMED": "学院已确认", "DELAYED": "延迟报到", "NO_SHOW": "未到校",
            "ABNORMAL": "报到异常"}
L_PAY = {"PAID": "已缴清", "PARTIAL": "部分缴费", "UNPAID": "未缴费", "DEFERRED": "已批准缓缴",
         "GREEN_CHANNEL": "绿色通道"}
L_GC = {"NOT_APPLIED": "未申请", "SUBMITTED": "已提交", "REVIEWING": "审核中", "APPROVED": "已通过",
        "RETURNED": "已退回", "REJECTED": "已驳回", "WITHDRAWN": "已撤回"}
L_MAT = {"NOT_UPLOADED": "未上传", "UPLOADED": "待审核", "APPROVED": "已通过", "RETURNED": "已退回",
         "REJECTED": "已驳回"}
L_MATTYPE = {"ID_CARD": "身份证明", "ADMISSION_LETTER": "录取通知书", "PHOTO": "证件照",
             "ARCHIVE": "纸质档案", "AID_PROOF": "资助证明材料"}
L_DORM = {"UNASSIGNED": "未分配", "ASSIGNED": "已分配", "CHECKED_IN": "已入住", "EXCEPTION": "入住异常"}
L_EXCTYPE = {"IDENTITY": "身份核验异常", "PAYMENT": "缴费异常", "MATERIAL": "材料异常",
             "DORM": "宿舍异常", "NO_SHOW": "未到校"}
L_EXCSTATUS = {"OPEN": "待处理", "PROCESSING": "处理中", "RESOLVED": "已处理", "ESCALATED": "已升级"}
L_RISK = {"LOW": "低风险", "MEDIUM": "中风险", "HIGH": "高风险"}

REGISTRATION_STEPS = [
    {"key": "ACTIVATE", "label": "账号激活"},
    {"key": "INFO", "label": "信息核对"},
    {"key": "MATERIAL", "label": "材料上传"},
    {"key": "PAYMENT", "label": "缴费/绿色通道"},
    {"key": "DORM", "label": "宿舍确认"},
    {"key": "CHECKIN", "label": "现场报到"},
    {"key": "CONFIRM", "label": "学院确认"},
]


def _default_steps_json() -> dict:
    return {s["key"]: "TODO" for s in REGISTRATION_STEPS}


def _merged_steps_json(raw: dict | None) -> dict:
    base = _default_steps_json()
    if raw:
        base.update(raw)
    return base


def _op():
    u = get_current_user_ctx() or {}
    return u.get("realName") or "系统", u.get("currentRoleCode") or ""


def _audit(db, biz_type, biz_id, action, detail="", before="", after=""):
    name, role = _op()
    db.add(OrientationAuditTrail(tenant_id=_tid(), biz_type=biz_type, biz_id=str(biz_id),
                                 action=action, operator=name, role_name=role, detail=detail,
                                 before_val=before, after_val=after, occurred_at=datetime.utcnow()))


def _get_student(db, sid) -> OrientationStudent:
    s = db.get(OrientationStudent, int(sid))
    if not s or s.is_deleted or s.tenant_id != _tid():
        raise not_found("新生记录不存在或不在当前数据范围内")
    return s


def _amt(v) -> float:
    return float(v or 0)


def _stu_row(s: OrientationStudent, *, detail: bool = False) -> dict:
    row = {
        "id": str(s.id), "studentId": str(s.student_id or s.id), "name": s.name,
        "admissionNo": s.admission_no, "gender": s.gender or "", "collegeName": s.college_name or "",
        "majorName": s.major_name or "", "classId": s.class_id or "", "className": s.class_name or "",
        "grade": s.grade or "", "phone": _mask_phone(s.phone_encrypted),
        "idCard": _mask_id_card(s.id_card_encrypted), "origin": s.origin or "",
        "stage": s.stage, "stageLabel": L_STAGE.get(s.stage, s.stage),
        "reportStatus": s.report_status, "reportStatusLabel": L_REPORT.get(s.report_status, s.report_status),
        "paymentStatus": s.payment_status, "paymentStatusLabel": L_PAY.get(s.payment_status, s.payment_status),
        "greenChannelStatus": s.green_channel_status, "greenChannelStatusLabel": L_GC.get(s.green_channel_status, s.green_channel_status),
        "materialStatus": s.material_status, "materialStatusLabel": L_MAT.get(s.material_status, s.material_status),
        "dormStatus": s.dorm_status, "dormStatusLabel": L_DORM.get(s.dorm_status, s.dorm_status),
        "building": s.building or "", "room": s.room or "",
        "riskLevel": s.risk_level, "riskLabel": L_RISK.get(s.risk_level, s.risk_level),
        "recordStatus": s.record_status, "counselor": s.counselor or "",
        "payableAmount": _amt(s.payable_amount), "paidAmount": _amt(s.paid_amount),
        "blockedStep": s.blocked_step or "", "blockedReason": s.blocked_reason or "",
        "updateTime": _iso(s.updated_at),
    }
    if detail:
        row["steps"] = _merged_steps_json(s.steps_json)
        row["voidReason"] = s.void_reason or ""
        row["checkinTime"] = _iso(s.checkin_time) or ""
        row["exceptionNote"] = s.exception_note or ""
    return row


def _page(items, page, page_size):
    total = len(items)
    start = (max(1, page) - 1) * page_size
    return items[start:start + page_size], total


# ═══ 学生台账 ═══

def list_students(page, page_size, keyword=None, class_id=None, stage=None, report_status=None,
                  payment_status=None, risk_level=None):
    with session() as db:
        q = select(OrientationStudent).where(OrientationStudent.tenant_id == _tid(),
                                             OrientationStudent.is_deleted.is_(False),
                                             OrientationStudent.record_status == "ACTIVE")
        if stage:
            q = q.where(OrientationStudent.stage == stage)
        if report_status:
            q = q.where(OrientationStudent.report_status == report_status)
        if payment_status:
            q = q.where(OrientationStudent.payment_status == payment_status)
        if risk_level:
            q = q.where(OrientationStudent.risk_level == risk_level)
        if class_id:
            q = q.where(OrientationStudent.class_id == class_id)
        rows = db.scalars(q.order_by(OrientationStudent.id)).all()
        if keyword:
            kw = keyword.strip()
            rows = [r for r in rows if kw in (r.name or "") or kw in (r.admission_no or "")]
        items, total = _page([_stu_row(r) for r in rows], page, page_size)
        return items, total


def get_student_detail(sid) -> dict:
    with session() as db:
        s = _get_student(db, sid)
        gcs = db.scalars(select(GreenChannelApplication).where(
            GreenChannelApplication.tenant_id == _tid(),
            GreenChannelApplication.ori_student_id == s.id).order_by(GreenChannelApplication.id)).all()
        mats = db.scalars(select(OrientationMaterial).where(
            OrientationMaterial.tenant_id == _tid(),
            OrientationMaterial.ori_student_id == s.id).order_by(OrientationMaterial.id)).all()
        excs = db.scalars(select(OrientationException).where(
            OrientationException.tenant_id == _tid(),
            OrientationException.ori_student_id == s.id).order_by(OrientationException.id)).all()
        logs = db.scalars(select(OrientationAuditTrail).where(
            OrientationAuditTrail.tenant_id == _tid(),
            OrientationAuditTrail.biz_id == str(s.id)).order_by(OrientationAuditTrail.id.desc()).limit(20)).all()
        return {
            "student": _stu_row(s, detail=True),
            "steps": [dict(x) for x in REGISTRATION_STEPS],
            "greenChannels": [_gc_row(g) for g in gcs],
            "materials": [_mat_row(m) for m in mats],
            "exceptions": [_exc_row(e) for e in excs],
            "auditLogs": [_log_row(x) for x in logs],
        }


def create_student(body: dict) -> dict:
    name = str(body.get("name") or "").strip()
    adm = str(body.get("admissionNo") or "").strip()
    if not name or not adm:
        raise AppException("VALIDATION_ERROR", "姓名与录取编号必填")
    with session() as db:
        dup = db.scalars(select(OrientationStudent).where(
            OrientationStudent.tenant_id == _tid(), OrientationStudent.admission_no == adm,
            OrientationStudent.is_deleted.is_(False))).first()
        if dup:
            raise AppException("DATA_CONFLICT", f"录取编号 {adm} 已存在")
        s = OrientationStudent(
            tenant_id=_tid(), name=name, admission_no=adm, major_name=body.get("majorName"),
            class_id=body.get("classId"), class_name=body.get("className"),
            phone_encrypted=body.get("phone"), id_card_encrypted=body.get("idCard"),
            origin=body.get("origin"), counselor=body.get("counselor"),
            stage="ADMITTED", report_status="NOT_REPORTED",
            steps_json=_default_steps_json())
        db.add(s)
        db.flush()
        _audit(db, "STUDENT", s.id, "新增新生记录", f"{name}（{adm}）")
        db.commit()
        return {"id": str(s.id)}


def update_student(sid, body: dict) -> dict:
    with session() as db:
        s = _get_student(db, sid)
        field_map = {
            "name": "name", "majorName": "major_name", "classId": "class_id",
            "className": "class_name", "origin": "origin", "counselor": "counselor",
            "reportStatus": "report_status", "building": "building", "room": "room",
        }
        for k, col in field_map.items():
            if body.get(k) is not None:
                setattr(s, col, body[k])
        phone = body.get("phone")
        if phone is not None and phone.strip() and "*" not in phone:
            s.phone_encrypted = phone.strip()
        s.version += 1
        _audit(db, "STUDENT", s.id, "编辑报到信息")
        db.commit()
        return {"id": str(s.id)}


def void_student(sid, reason: str) -> dict:
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "作废原因必填且不少于 5 字")
    with session() as db:
        s = _get_student(db, sid)
        s.record_status = "VOIDED"
        s.void_reason = reason.strip()
        s.is_deleted = True
        s.version += 1
        _audit(db, "STUDENT", s.id, "作废报到记录", reason.strip())
        db.commit()
        return {"id": str(s.id)}


# ═══ 报到进度 ═══

def list_progress(page, page_size, keyword=None, blocked_only="NO"):
    with session() as db:
        q = select(OrientationStudent).where(OrientationStudent.tenant_id == _tid(),
                                             OrientationStudent.is_deleted.is_(False),
                                             OrientationStudent.record_status == "ACTIVE")
        rows = db.scalars(q.order_by(OrientationStudent.id)).all()
        if keyword:
            kw = keyword.strip()
            rows = [r for r in rows if kw in (r.name or "") or kw in (r.admission_no or "")]
        if blocked_only == "YES":
            rows = [r for r in rows if r.blocked_step]
        items = []
        for r in rows:
            steps = r.steps_json or {}
            done = sum(1 for v in steps.values() if v == "DONE")
            items.append({"id": str(r.id), "name": r.name, "admissionNo": r.admission_no,
                          "className": r.class_name or "", "progress": f"{done}/{len(steps) or 7}",
                          "blockedStep": r.blocked_step or "", "blockedReason": r.blocked_reason or "",
                          "reportStatus": r.report_status,
                          "reportStatusLabel": L_REPORT.get(r.report_status, r.report_status)})
        page_items, total = _page(items, page, page_size)
        return page_items, total


def update_blocked(sid, blocked_step=None, blocked_reason=None) -> dict:
    if blocked_step and (not blocked_reason or len(str(blocked_reason).strip()) < 5):
        raise AppException("VALIDATION_ERROR", "卡点说明必填且不少于 5 字")
    with session() as db:
        s = _get_student(db, sid)
        steps = _merged_steps_json(s.steps_json)
        if blocked_step is not None:
            step_key = blocked_step or None
            s.blocked_step = step_key
            if step_key:
                steps[step_key] = "BLOCKED"
        if blocked_reason is not None:
            s.blocked_reason = blocked_reason or None
        s.steps_json = steps
        s.version += 1
        _audit(db, "PROGRESS", s.id, "编辑卡点事项", blocked_reason or "")
        db.commit()
        return {"id": str(s.id)}


def resolve_blocked(sid, note="") -> dict:
    with session() as db:
        s = _get_student(db, sid)
        prev = s.blocked_step or ""
        steps = _merged_steps_json(s.steps_json)
        if prev:
            steps[prev] = "DONE"
        s.steps_json = steps
        s.blocked_step = None
        s.blocked_reason = None
        s.version += 1
        _audit(db, "PROGRESS", s.id, "标记人工已处理", note)
        db.commit()
        return {"id": str(s.id)}


# ═══ 缴费 ═══

def list_payments(page, page_size, keyword=None, payment_status=None):
    with session() as db:
        q = select(OrientationStudent).where(OrientationStudent.tenant_id == _tid(),
                                             OrientationStudent.is_deleted.is_(False),
                                             OrientationStudent.record_status == "ACTIVE")
        if payment_status:
            q = q.where(OrientationStudent.payment_status == payment_status)
        rows = db.scalars(q.order_by(OrientationStudent.id)).all()
        if keyword:
            kw = keyword.strip()
            rows = [r for r in rows if kw in (r.name or "")]
        items = [{"id": str(r.id), "name": r.name, "className": r.class_name or "",
                  "payableAmount": f"¥{_amt(r.payable_amount):.0f}", "paidAmount": f"¥{_amt(r.paid_amount):.0f}",
                  "paymentStatus": r.payment_status, "paymentStatusLabel": L_PAY.get(r.payment_status, r.payment_status),
                  "phone": _mask_phone(r.phone_encrypted)} for r in rows]
        return _page(items, page, page_size)


# ═══ 绿色通道 ═══

def _gc_row(g: GreenChannelApplication, stu: OrientationStudent | None = None) -> dict:
    return {"id": str(g.id), "studentId": str(g.ori_student_id),
            "name": stu.name if stu else "", "className": stu.class_name if stu else "",
            "applyType": g.apply_type, "applyAmount": _amt(g.apply_amount),
            "submitTime": _iso(g.submit_time) or "", "status": g.status,
            "statusLabel": L_GC.get(g.status, g.status), "reviewer": g.reviewer or "",
            "reviewTime": _iso(g.review_time) or "", "rejectReason": g.reject_reason or "",
            "remark": g.remark or ""}


def list_green_channels(page, page_size, keyword=None, status=None):
    with session() as db:
        q = select(GreenChannelApplication).where(GreenChannelApplication.tenant_id == _tid(),
                                                  GreenChannelApplication.is_deleted.is_(False))
        if status:
            q = q.where(GreenChannelApplication.status == status)
        rows = db.scalars(q.order_by(GreenChannelApplication.id.desc())).all()
        items = []
        for g in rows:
            stu = db.get(OrientationStudent, g.ori_student_id)
            if keyword and (not stu or keyword.strip() not in (stu.name or "")):
                continue
            items.append(_gc_row(g, stu))
        return _page(items, page, page_size)


def _gc_act(gid, target_status, reason_field=None, reason=None, need_reason=False, action_label=""):
    if need_reason and (not reason or len(reason.strip()) < 5):
        raise AppException("VALIDATION_ERROR", "原因必填且不少于 5 字")
    with session() as db:
        g = db.get(GreenChannelApplication, int(gid))
        if not g or g.is_deleted or g.tenant_id != _tid():
            raise not_found("绿色通道申请不存在")
        if g.status in ("APPROVED", "REJECTED"):
            raise AppException("DATA_CONFLICT", "该申请已终审，请刷新")
        before = g.status
        name, _ = _op()
        g.status = target_status
        g.reviewer = name
        g.review_time = datetime.utcnow()
        if reason_field == "reject":
            g.reject_reason = (reason or "").strip()
        elif reason_field == "remark":
            g.remark = (reason or "").strip()
        g.version += 1
        stu = db.get(OrientationStudent, g.ori_student_id)
        audit_detail = reason or ""
        if stu:
            if target_status == "APPROVED":
                stu.green_channel_status = "APPROVED"
                if stu.payment_status in ("UNPAID", "PARTIAL"):
                    stu.payment_status = "GREEN_CHANNEL"
                steps = _merged_steps_json(stu.steps_json)
                if stu.blocked_step == "PAYMENT" or steps.get("PAYMENT") == "BLOCKED":
                    stu.blocked_step = None
                    stu.blocked_reason = None
                    steps["PAYMENT"] = "DONE"
                    stu.steps_json = steps
                    audit_detail = (audit_detail + "；绿色通道通过，缴费卡点自动解除").lstrip("；")
            elif target_status == "REJECTED":
                stu.green_channel_status = "REJECTED"
            elif target_status == "RETURNED":
                stu.green_channel_status = "RETURNED"
        _audit(db, "GREEN_CHANNEL", g.id, action_label, audit_detail or action_label, before, target_status)
        db.commit()
        return {"id": str(g.id), "status": target_status}


def approve_green_channel(gid, remark=""):
    return _gc_act(gid, "APPROVED", "remark", remark, False, "审核通过")


def reject_green_channel(gid, reason):
    return _gc_act(gid, "REJECTED", "reject", reason, True, "驳回申请")


def return_green_channel(gid, reason):
    return _gc_act(gid, "RETURNED", "reject", reason, True, "退回补充")


# ═══ 材料审核 ═══

def _mat_row(m: OrientationMaterial, stu: OrientationStudent | None = None) -> dict:
    return {"id": str(m.id), "studentId": str(m.ori_student_id),
            "name": stu.name if stu else "", "className": stu.class_name if stu else "",
            "materialType": m.material_type, "materialTypeLabel": L_MATTYPE.get(m.material_type, m.material_type),
            "fileName": m.file_name or "", "submitTime": _iso(m.submit_time) or "",
            "status": m.status, "statusLabel": L_MAT.get(m.status, m.status),
            "reviewer": m.reviewer or "", "reviewTime": _iso(m.review_time) or "",
            "returnReason": m.return_reason or ""}


def list_materials(page, page_size, keyword=None, status=None, material_type=None):
    with session() as db:
        q = select(OrientationMaterial).where(OrientationMaterial.tenant_id == _tid(),
                                              OrientationMaterial.is_deleted.is_(False))
        if status:
            q = q.where(OrientationMaterial.status == status)
        if material_type:
            q = q.where(OrientationMaterial.material_type == material_type)
        rows = db.scalars(q.order_by(OrientationMaterial.id.desc())).all()
        items = []
        for m in rows:
            stu = db.get(OrientationStudent, m.ori_student_id)
            if keyword and (not stu or keyword.strip() not in (stu.name or "")):
                continue
            items.append(_mat_row(m, stu))
        return _page(items, page, page_size)


def _refresh_material_status(db, stu):
    mats = db.scalars(select(OrientationMaterial).where(
        OrientationMaterial.tenant_id == _tid(),
        OrientationMaterial.ori_student_id == stu.id,
        OrientationMaterial.is_deleted.is_(False))).all()
    if mats and all(m.status == "APPROVED" for m in mats):
        stu.material_status = "APPROVED"
        if stu.blocked_step == "MATERIAL":
            stu.blocked_step = None
            stu.blocked_reason = None
            if stu.steps_json:
                stu.steps_json = {**stu.steps_json, "MATERIAL": "DONE"}


def approve_material(mid, comment=""):
    with session() as db:
        m = db.get(OrientationMaterial, int(mid))
        if not m or m.is_deleted or m.tenant_id != _tid():
            raise not_found("材料不存在")
        if m.status == "APPROVED":
            raise AppException("DATA_CONFLICT", "该材料已通过")
        before = m.status
        name, _ = _op()
        m.status = "APPROVED"
        m.reviewer = name
        m.review_time = datetime.utcnow()
        m.version += 1
        stu = db.get(OrientationStudent, m.ori_student_id)
        if stu:
            _refresh_material_status(db, stu)
        _audit(db, "MATERIAL", m.id, "审核通过", comment, before, "APPROVED")
        db.commit()
        return {"id": str(m.id), "status": "APPROVED"}


def return_material(mid, reason):
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "退回原因必填且不少于 5 字")
    with session() as db:
        m = db.get(OrientationMaterial, int(mid))
        if not m or m.is_deleted or m.tenant_id != _tid():
            raise not_found("材料不存在")
        before = m.status
        name, _ = _op()
        m.status = "RETURNED"
        m.reviewer = name
        m.review_time = datetime.utcnow()
        m.return_reason = reason.strip()
        m.version += 1
        stu = db.get(OrientationStudent, m.ori_student_id)
        if stu:
            stu.material_status = "RETURNED"
        _audit(db, "MATERIAL", m.id, "退回材料", reason.strip(), before, "RETURNED")
        db.commit()
        return {"id": str(m.id), "status": "RETURNED"}


# ═══ 宿舍 ═══

def list_dorms(page, page_size, keyword=None, dorm_status=None, building=None):
    with session() as db:
        q = select(OrientationStudent).where(OrientationStudent.tenant_id == _tid(),
                                             OrientationStudent.is_deleted.is_(False),
                                             OrientationStudent.record_status == "ACTIVE")
        if dorm_status:
            q = q.where(OrientationStudent.dorm_status == dorm_status)
        if building:
            q = q.where(OrientationStudent.building == building)
        rows = db.scalars(q.order_by(OrientationStudent.id)).all()
        if keyword:
            kw = keyword.strip()
            rows = [r for r in rows if kw in (r.name or "")]
        items = [{"id": str(r.id), "name": r.name, "className": r.class_name or "",
                  "building": r.building or "", "room": r.room or "",
                  "dormStatus": r.dorm_status, "dormStatusLabel": L_DORM.get(r.dorm_status, r.dorm_status),
                  "checkinTime": _iso(r.checkin_time) or "", "exceptionNote": r.exception_note or "",
                  "phone": _mask_phone(r.phone_encrypted)} for r in rows]
        return _page(items, page, page_size)


def update_dorm(sid, body: dict) -> dict:
    building = body.get("building")
    room = body.get("room")
    dorm_status = body.get("dormStatus")
    remark = body.get("remark")
    with session() as db:
        s = _get_student(db, sid)
        before = f"{s.building or ''} {s.room or ''}".strip()
        if building is not None:
            s.building = building
        if room is not None:
            s.room = room
        if dorm_status is not None:
            s.dorm_status = dorm_status
        elif (building or room) and s.dorm_status not in ("CHECKED_IN", "EXCEPTION"):
            s.dorm_status = "ASSIGNED"
        if remark is not None:
            s.exception_note = remark
        after = f"{s.building or ''} {s.room or ''}".strip()
        s.version += 1
        _audit(db, "DORM", s.id, "编辑宿舍信息", f"{before or '未分配'} → {after or '未分配'}")
        db.commit()
        return {"id": str(s.id)}


def batch_confirm_checkin(ids: list) -> dict:
    cnt = 0
    with session() as db:
        for sid in ids:
            s = db.get(OrientationStudent, int(sid))
            if not s or s.tenant_id != _tid() or s.dorm_status == "EXCEPTION":
                continue
            s.dorm_status = "CHECKED_IN"
            s.checkin_time = datetime.utcnow()
            if s.steps_json:
                s.steps_json = {**s.steps_json, "DORM": "DONE"}
            s.version += 1
            _audit(db, "DORM", s.id, "批量确认入住")
            cnt += 1
        db.commit()
        return {"count": cnt}


def mark_dorm_exception(sid, note) -> dict:
    if not note or len(note.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "异常说明必填且不少于 5 字")
    with session() as db:
        s = _get_student(db, sid)
        s.dorm_status = "EXCEPTION"
        s.exception_note = note.strip()
        s.version += 1
        db.add(OrientationException(tenant_id=_tid(), ori_student_id=s.id, exception_type="DORM",
                                    description=note.strip(), risk_level="MEDIUM", status="OPEN",
                                    handler=_op()[0]))
        _audit(db, "DORM", s.id, "标记入住异常", note.strip())
        db.commit()
        return {"id": str(s.id)}


# ═══ 异常 ═══

def _exc_row(e: OrientationException, stu: OrientationStudent | None = None) -> dict:
    return {"id": str(e.id), "studentId": str(e.ori_student_id),
            "name": stu.name if stu else "", "className": stu.class_name if stu else "",
            "exceptionType": e.exception_type, "exceptionTypeLabel": L_EXCTYPE.get(e.exception_type, e.exception_type),
            "description": e.description or "", "riskLevel": e.risk_level,
            "riskLabel": L_RISK.get(e.risk_level, e.risk_level), "status": e.status,
            "statusLabel": L_EXCSTATUS.get(e.status, e.status), "handler": e.handler or "",
            "lastFollowTime": _iso(e.last_follow_time) or ""}


def list_exceptions(page, page_size, keyword=None, exception_type=None, status=None, risk_level=None):
    with session() as db:
        q = select(OrientationException).where(OrientationException.tenant_id == _tid(),
                                               OrientationException.is_deleted.is_(False))
        if exception_type:
            q = q.where(OrientationException.exception_type == exception_type)
        if status:
            q = q.where(OrientationException.status == status)
        if risk_level:
            q = q.where(OrientationException.risk_level == risk_level)
        rows = db.scalars(q.order_by(OrientationException.id.desc())).all()
        items = []
        for e in rows:
            stu = db.get(OrientationStudent, e.ori_student_id)
            if keyword and (not stu or keyword.strip() not in (stu.name or "")):
                continue
            items.append(_exc_row(e, stu))
        return _page(items, page, page_size)


def get_exception_detail(eid) -> dict:
    with session() as db:
        e = db.get(OrientationException, int(eid))
        if not e or e.is_deleted or e.tenant_id != _tid():
            raise not_found("异常记录不存在")
        stu = db.get(OrientationStudent, e.ori_student_id)
        fus = db.scalars(select(OrientationExceptionFollowup).where(
            OrientationExceptionFollowup.tenant_id == _tid(),
            OrientationExceptionFollowup.exception_id == e.id).order_by(
            OrientationExceptionFollowup.id.desc())).all()
        row = _exc_row(e, stu)
        row["followUps"] = [{"id": str(f.id), "followTime": _iso(f.follow_time), "way": f.way,
                             "content": f.content or "", "operator": f.operator or "",
                             "status": f.status} for f in fus]
        return {"exception": row, "student": _stu_row(stu) if stu else None}


def add_followup(eid, content, way="PHONE") -> dict:
    if not content or not content.strip():
        raise AppException("VALIDATION_ERROR", "跟进内容必填")
    with session() as db:
        e = db.get(OrientationException, int(eid))
        if not e or e.is_deleted or e.tenant_id != _tid():
            raise not_found("异常记录不存在")
        f = OrientationExceptionFollowup(tenant_id=_tid(), exception_id=e.id, way=way,
                                         content=content.strip(), operator=_op()[0], status="ACTIVE",
                                         follow_time=datetime.utcnow())
        db.add(f)
        if e.status == "OPEN":
            e.status = "PROCESSING"
        e.last_follow_time = datetime.utcnow()
        e.version += 1
        _audit(db, "EXCEPTION", e.id, "新增跟进", content.strip())
        db.commit()
        db.refresh(f)
        return {"id": str(f.id)}


def resolve_exception(eid, note="") -> dict:
    with session() as db:
        e = db.get(OrientationException, int(eid))
        if not e or e.is_deleted or e.tenant_id != _tid():
            raise not_found("异常记录不存在")
        e.status = "RESOLVED"
        e.version += 1
        stu = db.get(OrientationStudent, e.ori_student_id)
        if stu and stu.risk_level == "HIGH":
            stu.risk_level = "MEDIUM"
        _audit(db, "EXCEPTION", e.id, "标记已处理", note)
        db.commit()
        return {"id": str(e.id), "status": "RESOLVED"}


def escalate_exception(eid, reason) -> dict:
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "升级原因必填且不少于 5 字")
    with session() as db:
        e = db.get(OrientationException, int(eid))
        if not e or e.is_deleted or e.tenant_id != _tid():
            raise not_found("异常记录不存在")
        e.status = "ESCALATED"
        e.risk_level = "HIGH"
        e.version += 1
        stu = db.get(OrientationStudent, e.ori_student_id)
        if stu:
            stu.risk_level = "HIGH"
        _audit(db, "EXCEPTION", e.id, "升级风险", reason.strip())
        db.commit()
        return {"id": str(e.id), "status": "ESCALATED"}


# ═══ 审计 ═══

def _log_row(x: OrientationAuditTrail) -> dict:
    return {"id": str(x.id), "time": _iso(x.occurred_at), "operator": x.operator or "",
            "roleName": x.role_name or "", "bizType": x.biz_type, "bizId": x.biz_id or "",
            "action": x.action, "detail": x.detail or "", "before": x.before_val or "",
            "after": x.after_val or ""}


def list_audit(page, page_size, biz_type=None, keyword=None):
    with session() as db:
        q = select(OrientationAuditTrail).where(OrientationAuditTrail.tenant_id == _tid())
        if biz_type:
            q = q.where(OrientationAuditTrail.biz_type == biz_type)
        rows = db.scalars(q.order_by(OrientationAuditTrail.id.desc())).all()
        if keyword:
            kw = keyword.strip()
            rows = [r for r in rows if kw in (r.action or "") or kw in (r.detail or "")]
        return _page([_log_row(r) for r in rows], page, page_size)


# ═══ 看板 ═══

def get_dashboard() -> dict:
    with session() as db:
        rows = db.scalars(select(OrientationStudent).where(
            OrientationStudent.tenant_id == _tid(), OrientationStudent.is_deleted.is_(False),
            OrientationStudent.record_status == "ACTIVE")).all()
        total = len(rows)
        paid = sum(1 for r in rows if r.payment_status in ("PAID", "GREEN_CHANNEL", "DEFERRED"))
        pending_gc = db.scalar(select(func.count()).select_from(GreenChannelApplication).where(
            GreenChannelApplication.tenant_id == _tid(),
            GreenChannelApplication.status.in_(["SUBMITTED", "REVIEWING"]),
            GreenChannelApplication.is_deleted.is_(False))) or 0
        pending_mat = db.scalar(select(func.count()).select_from(OrientationMaterial).where(
            OrientationMaterial.tenant_id == _tid(), OrientationMaterial.status == "UPLOADED",
            OrientationMaterial.is_deleted.is_(False))) or 0
        open_exc = db.scalar(select(func.count()).select_from(OrientationException).where(
            OrientationException.tenant_id == _tid(),
            OrientationException.status.in_(["OPEN", "PROCESSING", "ESCALATED"]),
            OrientationException.is_deleted.is_(False))) or 0
        rate = lambda a, b: f"{(a / b * 100):.1f}%" if b else "0%"  # noqa: E731
        prepared = sum(1 for r in rows if r.report_status in ("PREPARED", "CHECKED_IN", "COLLEGE_CONFIRMED"))
        checked_in = sum(1 for r in rows if r.report_status in ("CHECKED_IN", "COLLEGE_CONFIRMED"))
        gc_total = db.scalar(select(func.count()).select_from(GreenChannelApplication).where(
            GreenChannelApplication.tenant_id == _tid(),
            GreenChannelApplication.is_deleted.is_(False))) or 0
        step_funnel = []
        for step in REGISTRATION_STEPS:
            key = step["key"]
            done = sum(1 for r in rows if (_merged_steps_json(r.steps_json).get(key) == "DONE"))
            step_funnel.append({"key": key, "label": step["label"], "done": done})
        return {
            "batchName": "2026 级迎新批次", "batchPeriod": "2026-09-01 ~ 2026-09-15",
            "updateTime": _iso(datetime.now()),
            "kpis": [
                {"key": "total", "label": "新生总数", "value": str(total), "trend": "", "trendQuality": "neutral"},
                {"key": "prepared", "label": "预报到完成", "value": str(prepared),
                 "trend": rate(prepared, total), "trendQuality": "good"},
                {"key": "checkedIn", "label": "已现场报到", "value": str(checked_in),
                 "trend": f"已报到 {checked_in}", "trendQuality": "good"},
                {"key": "paidRate", "label": "缴费完成率", "value": rate(paid, total),
                 "trend": f"已完成 {paid}", "trendQuality": "good"},
                {"key": "greenChannel", "label": "绿色通道申请", "value": str(gc_total),
                 "trend": f"{pending_gc} 待审", "trendQuality": "neutral"},
                {"key": "exception", "label": "迎新异常", "value": str(open_exc),
                 "trend": f"待处理 {open_exc}", "trendQuality": "bad" if open_exc else "good"},
            ],
            "todos": [
                {"id": "t1", "label": "待审绿色通道", "value": pending_gc, "link": "/admin/orientation/payment"},
                {"id": "t2", "label": "待审材料", "value": pending_mat, "link": "/admin/orientation/materials"},
                {"id": "t3", "label": "待处理异常", "value": open_exc, "link": "/admin/orientation/exceptions"},
            ],
            "riskAlerts": [], "flow": [], "stepFunnel": step_funnel, "collegeRates": [],
        }
