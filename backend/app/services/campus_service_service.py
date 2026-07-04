"""在校服务域真实数据服务。租户过滤 + 脱敏 + 审计留痕。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.models import (CsAuditTrail, CsDiscipline, CsDormException, CsDormRecord, CsGrant, CsLeave,
                        CsMentalRecord, CsServiceStudent, CsWorkOrder)
from app.services.db_service import _iso, _mask_id_card, _mask_phone, _tid, session

L_LEAVE_T = {"SICK": "病假", "PERSONAL": "事假", "GOOUT": "外出报备"}
L_LEAVE_S = {"PENDING_REVIEW": "待审批", "APPROVED": "已通过", "RETURNED": "已退回", "CANCELLED": "已销假"}
L_GRANT_T = {"NATIONAL_GRANT": "国家助学金", "SCHOLARSHIP": "奖学金", "HARDSHIP": "临时困难补助",
             "TUITION_WAIVER": "学费减免"}
L_GRANT_S = {"PENDING_REVIEW": "待审核", "REVIEWING": "审核中", "APPROVED": "已通过",
             "RETURNED": "退回补充", "REJECTED": "不予通过"}
L_DORM_S = {"IN": "在住", "OUT": "已退宿", "CHANGED": "已调宿"}
L_DE_T = {"NIGHT_OUT": "晚归", "NO_RETURN": "夜不归宿", "FACILITY": "设施报修",
          "HYGIENE": "卫生不合格", "DISCIPLINE": "宿舍违纪"}
L_DE_S = {"PENDING_HANDLE": "待处理", "PROCESSING": "跟进中", "COMPLETED": "已办结"}
L_DIS_T = {"WARNING": "警告", "SERIOUS_WARNING": "严重警告", "DEMERIT": "记过", "PROBATION": "留校察看"}
L_DIS_S = {"EFFECTIVE": "生效中", "REVOKED": "已解除"}
L_WO_T = {"CONSULT": "咨询", "REPAIR": "报修", "COMPLAINT": "投诉建议", "CERT": "证明办理", "CARE": "关怀转介"}
L_WO_S = {"PENDING_HANDLE": "待处理", "PROCESSING": "处理中", "COMPLETED": "已办结", "CLOSED": "已关闭"}
L_CARE = {"NORMAL": "常规", "FOCUS": "重点关注", "KEY_CARE": "重点关怀"}
L_RISK = {"LOW": "低风险", "MEDIUM": "中风险", "HIGH": "高风险"}


def _op():
    u = get_current_user_ctx() or {}
    return u.get("realName") or "系统", u.get("currentRoleCode") or ""


def _audit(db, biz_type, biz_id, action, detail="", before="", after=""):
    n, r = _op()
    db.add(CsAuditTrail(tenant_id=_tid(), biz_type=biz_type, biz_id=str(biz_id), action=action,
                        operator=n, role_name=r, detail=detail, before_val=before, after_val=after,
                        occurred_at=datetime.utcnow()))


def _page(items, page, page_size):
    total = len(items)
    start = (max(1, page) - 1) * page_size
    return items[start:start + page_size], total


def _amt_range(v):
    v = float(v or 0)
    if v <= 0:
        return "—"
    lo = int(v // 1000) * 1000
    return f"{lo}-{lo + 1000} 元"


def _get_stu(db, sid) -> CsServiceStudent:
    s = db.get(CsServiceStudent, int(sid))
    if not s or s.is_deleted or s.tenant_id != _tid():
        raise not_found("学生服务记录不存在或不在当前数据范围内")
    return s


def _stu_of(db, csid):
    return db.get(CsServiceStudent, csid)


# ═══ 学生台账 ═══

def _stu_row(s: CsServiceStudent) -> dict:
    return {"id": str(s.id), "studentId": str(s.student_id or s.id), "name": s.name,
            "studentNo": s.student_no or "", "gender": s.gender or "", "collegeName": s.college_name or "",
            "majorName": s.major_name or "", "classId": s.class_id or "", "className": s.class_name or "",
            "grade": s.grade or "", "phone": _mask_phone(s.phone_encrypted),
            "idCard": _mask_id_card(s.id_card_encrypted), "counselor": s.counselor or "",
            "building": s.building or "", "room": s.room or "",
            "careLevel": s.care_level, "careLevelLabel": L_CARE.get(s.care_level, s.care_level),
            "riskLevel": s.risk_level, "riskLabel": L_RISK.get(s.risk_level, s.risk_level),
            "mentalFlag": s.mental_flag, "recordStatus": s.record_status, "updateTime": _iso(s.updated_at)}


def list_students(page, page_size, keyword=None, class_id=None, care_level=None, risk_level=None):
    with session() as db:
        q = select(CsServiceStudent).where(CsServiceStudent.tenant_id == _tid(),
                                           CsServiceStudent.is_deleted.is_(False),
                                           CsServiceStudent.record_status == "ACTIVE")
        if class_id:
            q = q.where(CsServiceStudent.class_id == class_id)
        if care_level:
            q = q.where(CsServiceStudent.care_level == care_level)
        if risk_level:
            q = q.where(CsServiceStudent.risk_level == risk_level)
        rows = db.scalars(q.order_by(CsServiceStudent.id)).all()
        if keyword:
            kw = keyword.strip()
            rows = [r for r in rows if kw in (r.name or "") or kw in (r.student_no or "")]
        return _page([_stu_row(r) for r in rows], page, page_size)


def get_student_detail(sid) -> dict:
    with session() as db:
        s = _get_stu(db, sid)
        leaves = db.scalars(select(CsLeave).where(CsLeave.tenant_id == _tid(),
                            CsLeave.cs_student_id == s.id).order_by(CsLeave.id.desc())).all()
        grants = db.scalars(select(CsGrant).where(CsGrant.tenant_id == _tid(),
                            CsGrant.cs_student_id == s.id).order_by(CsGrant.id.desc())).all()
        discs = db.scalars(select(CsDiscipline).where(CsDiscipline.tenant_id == _tid(),
                           CsDiscipline.cs_student_id == s.id).order_by(CsDiscipline.id.desc())).all()
        wos = db.scalars(select(CsWorkOrder).where(CsWorkOrder.tenant_id == _tid(),
                         CsWorkOrder.cs_student_id == s.id).order_by(CsWorkOrder.id.desc())).all()
        logs = db.scalars(select(CsAuditTrail).where(CsAuditTrail.tenant_id == _tid(),
                          CsAuditTrail.biz_id == str(s.id)).order_by(CsAuditTrail.id.desc()).limit(20)).all()
        return {"student": _stu_row(s),
                "leaves": [_leave_row(x, s) for x in leaves],
                "grants": [_grant_row(x, s) for x in grants],
                "disciplines": [_disc_row(x, s) for x in discs],
                "workOrders": [_wo_row(x, s) for x in wos],
                "auditLogs": [_log_row(x) for x in logs]}


def create_student(body: dict) -> dict:
    name = str(body.get("name") or "").strip()
    no = str(body.get("studentNo") or "").strip()
    if not name or not no:
        raise AppException("VALIDATION_ERROR", "姓名与学号必填")
    with session() as db:
        s = CsServiceStudent(tenant_id=_tid(), name=name, student_no=no,
                             class_id=body.get("classId"), class_name=body.get("className"),
                             care_level=body.get("careLevel") or "NORMAL", room=body.get("room"),
                             building=body.get("building"), counselor=body.get("counselor"),
                             phone_encrypted=body.get("phone"), record_status="ACTIVE")
        db.add(s)
        db.flush()
        _audit(db, "RECORD", s.id, "新增服务记录", f"{name}（{no}）")
        db.commit()
        return {"id": str(s.id)}


def update_student(sid, body: dict) -> dict:
    with session() as db:
        s = _get_stu(db, sid)
        for k, col in {"careLevel": "care_level", "building": "building", "room": "room",
                       "counselor": "counselor", "className": "class_name"}.items():
            if body.get(k) is not None:
                setattr(s, col, body[k])
        s.version += 1
        _audit(db, "RECORD", s.id, "编辑服务记录")
        db.commit()
        return {"id": str(s.id)}


def void_student(sid, reason) -> dict:
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "作废原因必填且不少于 5 字")
    with session() as db:
        s = _get_stu(db, sid)
        s.record_status = "VOIDED"
        s.void_reason = reason.strip()
        s.is_deleted = True
        s.version += 1
        _audit(db, "RECORD", s.id, "作废服务记录", reason.strip())
        db.commit()
        return {"id": str(s.id)}


# ═══ 请假 ═══

def _leave_row(x: CsLeave, stu=None) -> dict:
    return {"id": str(x.id), "code": x.code or "", "studentId": str(x.cs_student_id),
            "name": stu.name if stu else "", "className": stu.class_name if stu else "",
            "type": x.leave_type, "typeLabel": L_LEAVE_T.get(x.leave_type, x.leave_type),
            "startTime": _iso(x.start_time) or "", "endTime": _iso(x.end_time) or "",
            "duration": x.duration or "", "reason": x.reason or "",
            "status": x.status, "statusLabel": L_LEAVE_S.get(x.status, x.status),
            "applyTime": _iso(x.apply_time) or "", "reviewer": x.reviewer or "",
            "reviewTime": _iso(x.review_time) or "", "returnReason": x.return_reason or ""}


def list_leaves(page, page_size, keyword=None, type=None, status=None):
    with session() as db:
        q = select(CsLeave).where(CsLeave.tenant_id == _tid(), CsLeave.is_deleted.is_(False))
        if type:
            q = q.where(CsLeave.leave_type == type)
        if status:
            q = q.where(CsLeave.status == status)
        rows = db.scalars(q.order_by(CsLeave.id.desc())).all()
        items = []
        for x in rows:
            stu = _stu_of(db, x.cs_student_id)
            if keyword and (not stu or keyword.strip() not in (stu.name or "")):
                continue
            items.append(_leave_row(x, stu))
        return _page(items, page, page_size)


def get_leave_detail(lid) -> dict:
    with session() as db:
        x = db.get(CsLeave, int(lid))
        if not x or x.is_deleted or x.tenant_id != _tid():
            raise not_found("请假申请不存在")
        stu = _stu_of(db, x.cs_student_id)
        hist = db.scalars(select(CsLeave).where(CsLeave.tenant_id == _tid(),
                          CsLeave.cs_student_id == x.cs_student_id,
                          CsLeave.id != x.id).order_by(CsLeave.id.desc()).limit(5)).all()
        return {"leave": _leave_row(x, stu), "student": _stu_row(stu) if stu else None,
                "history": [_leave_row(h, stu) for h in hist]}


def _leave_act(lid, target, reviewer_comment=None, need_reason=False, reason=None, action=""):
    if need_reason and (not reason or len(reason.strip()) < 5):
        raise AppException("VALIDATION_ERROR", "退回原因必填且不少于 5 字")
    with session() as db:
        x = db.get(CsLeave, int(lid))
        if not x or x.is_deleted or x.tenant_id != _tid():
            raise not_found("请假申请不存在")
        if x.status in ("APPROVED", "RETURNED"):
            raise AppException("DATA_CONFLICT", "该请假已处理，请刷新")
        before = x.status
        n, _ = _op()
        x.status = target
        x.reviewer = n
        x.review_time = datetime.utcnow()
        if target == "RETURNED":
            x.return_reason = (reason or "").strip()
        x.version += 1
        _audit(db, "LEAVE", x.id, action, reason or reviewer_comment or "", before, target)
        db.commit()
        return {"id": str(x.id), "status": target}


def approve_leave(lid, comment=""):
    return _leave_act(lid, "APPROVED", comment, False, None, "审批通过")


def return_leave(lid, reason):
    return _leave_act(lid, "RETURNED", None, True, reason, "退回修改")


def batch_approve_leaves(ids):
    cnt = 0
    for lid in ids:
        try:
            _leave_act(lid, "APPROVED", "", False, None, "批量审批通过")
            cnt += 1
        except AppException:
            continue
    return {"count": cnt}


# ═══ 资助 ═══

def _grant_row(x: CsGrant, stu=None, mask=True) -> dict:
    row = {"id": str(x.id), "code": x.code or "", "studentId": str(x.cs_student_id),
           "name": stu.name if stu else "", "className": stu.class_name if stu else "",
           "type": x.grant_type, "typeLabel": L_GRANT_T.get(x.grant_type, x.grant_type),
           "amountRange": _amt_range(x.amount), "applyReason": x.apply_reason or "",
           "materialSensitive": x.material_sensitive, "status": x.status,
           "statusLabel": L_GRANT_S.get(x.status, x.status), "applyTime": _iso(x.apply_time) or "",
           "reviewer": x.reviewer or "", "reviewTime": _iso(x.review_time) or "",
           "returnReason": x.return_reason or "", "currentNode": x.current_node or ""}
    if not mask:
        row["amount"] = float(x.amount or 0)
    return row


def list_grants(page, page_size, keyword=None, type=None, status=None):
    with session() as db:
        q = select(CsGrant).where(CsGrant.tenant_id == _tid(), CsGrant.is_deleted.is_(False))
        if type:
            q = q.where(CsGrant.grant_type == type)
        if status:
            q = q.where(CsGrant.status == status)
        rows = db.scalars(q.order_by(CsGrant.id.desc())).all()
        items = []
        for x in rows:
            stu = _stu_of(db, x.cs_student_id)
            if keyword and (not stu or keyword.strip() not in (stu.name or "")):
                continue
            items.append(_grant_row(x, stu, mask=True))
        return _page(items, page, page_size)


def get_grant_detail(gid) -> dict:
    with session() as db:
        x = db.get(CsGrant, int(gid))
        if not x or x.is_deleted or x.tenant_id != _tid():
            raise not_found("资助申请不存在")
        stu = _stu_of(db, x.cs_student_id)
        return {"grant": _grant_row(x, stu, mask=False), "student": _stu_row(stu) if stu else None}


def _grant_act(gid, target, need_reason=False, reason=None, node="", action=""):
    if need_reason and (not reason or len(reason.strip()) < 5):
        raise AppException("VALIDATION_ERROR", "退回原因必填且不少于 5 字")
    with session() as db:
        x = db.get(CsGrant, int(gid))
        if not x or x.is_deleted or x.tenant_id != _tid():
            raise not_found("资助申请不存在")
        if x.status in ("APPROVED", "REJECTED"):
            raise AppException("DATA_CONFLICT", "该资助已终审，请刷新")
        before = x.status
        n, _ = _op()
        x.status = target
        x.reviewer = n
        x.review_time = datetime.utcnow()
        x.current_node = node
        if target == "RETURNED":
            x.return_reason = (reason or "").strip()
        x.version += 1
        _audit(db, "GRANT", x.id, action, reason or "", before, target)
        db.commit()
        return {"id": str(x.id), "status": target}


def approve_grant(gid, comment=""):
    return _grant_act(gid, "APPROVED", False, None, "已办结", "审批通过")


def return_grant(gid, reason):
    return _grant_act(gid, "RETURNED", True, reason, "学生补充材料", "退回补充")


def batch_approve_grants(ids):
    cnt = 0
    for gid in ids:
        try:
            _grant_act(gid, "APPROVED", False, None, "已办结", "批量审批通过")
            cnt += 1
        except AppException:
            continue
    return {"count": cnt}


# ═══ 宿舍 ═══

def _dorm_row(x: CsDormRecord, stu=None) -> dict:
    return {"id": str(x.id), "studentId": str(x.cs_student_id),
            "name": stu.name if stu else "", "className": stu.class_name if stu else "",
            "building": x.building or "", "room": x.room or "", "bed": x.bed or "",
            "checkinDate": _iso(x.checkin_date) or "", "status": x.status,
            "statusLabel": L_DORM_S.get(x.status, x.status)}


def list_dorm_records(page, page_size, keyword=None, status=None):
    with session() as db:
        q = select(CsDormRecord).where(CsDormRecord.tenant_id == _tid(),
                                       CsDormRecord.is_deleted.is_(False),
                                       CsDormRecord.record_status == "ACTIVE")
        if status:
            q = q.where(CsDormRecord.status == status)
        rows = db.scalars(q.order_by(CsDormRecord.id.desc())).all()
        items = []
        for x in rows:
            stu = _stu_of(db, x.cs_student_id)
            if keyword and (not stu or keyword.strip() not in (stu.name or "")):
                continue
            items.append(_dorm_row(x, stu))
        return _page(items, page, page_size)


def _de_row(x: CsDormException, stu=None) -> dict:
    return {"id": str(x.id), "code": x.code or "", "studentId": str(x.cs_student_id),
            "name": stu.name if stu else "", "className": stu.class_name if stu else "",
            "type": x.exc_type, "typeLabel": L_DE_T.get(x.exc_type, x.exc_type),
            "happenTime": _iso(x.happen_time) or "", "detail": x.detail or "",
            "status": x.status, "statusLabel": L_DE_S.get(x.status, x.status),
            "handler": x.handler or "", "handleNote": x.handle_note or "",
            "handleTime": _iso(x.handle_time) or ""}


def list_dorm_exceptions(page, page_size, keyword=None, type=None, status=None):
    with session() as db:
        q = select(CsDormException).where(CsDormException.tenant_id == _tid(),
                                          CsDormException.is_deleted.is_(False))
        if type:
            q = q.where(CsDormException.exc_type == type)
        if status:
            q = q.where(CsDormException.status == status)
        rows = db.scalars(q.order_by(CsDormException.id.desc())).all()
        items = []
        for x in rows:
            stu = _stu_of(db, x.cs_student_id)
            if keyword and (not stu or keyword.strip() not in (stu.name or "")):
                continue
            items.append(_de_row(x, stu))
        return _page(items, page, page_size)


def mark_dorm_exception(body: dict) -> dict:
    detail = str(body.get("detail") or "").strip()
    if len(detail) < 5:
        raise AppException("VALIDATION_ERROR", "情况说明必填且不少于 5 字")
    with session() as db:
        s = _get_stu(db, body.get("studentId"))
        n, _ = _op()
        code = f"DE-{datetime.now():%Y}-{db.scalar(select(func.count()).select_from(CsDormException).where(CsDormException.tenant_id == _tid())) + 1:04d}"
        e = CsDormException(tenant_id=_tid(), cs_student_id=s.id, exc_type=body.get("type") or "NIGHT_OUT",
                            happen_time=datetime.utcnow(), detail=detail, status="PENDING_HANDLE",
                            code=code, handler=n)
        db.add(e)
        db.flush()
        _audit(db, "DORM", e.id, "标记宿舍异常", detail)
        db.commit()
        return {"id": str(e.id)}


def handle_dorm_exception(eid, note, complete=False) -> dict:
    if not note or len(note.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "处理说明必填且不少于 5 字")
    with session() as db:
        e = db.get(CsDormException, int(eid))
        if not e or e.is_deleted or e.tenant_id != _tid():
            raise not_found("宿舍异常不存在")
        before = e.status
        e.status = "COMPLETED" if complete else "PROCESSING"
        e.handle_note = note.strip()
        e.handle_time = datetime.utcnow()
        e.version += 1
        _audit(db, "DORM", e.id, "处理宿舍异常", note.strip(), before, e.status)
        db.commit()
        return {"id": str(e.id), "status": e.status}


# ═══ 违纪 ═══

def _disc_row(x: CsDiscipline, stu=None) -> dict:
    return {"id": str(x.id), "code": x.code or "", "studentId": str(x.cs_student_id),
            "name": stu.name if stu else "", "className": stu.class_name if stu else "",
            "type": x.disc_type, "typeLabel": L_DIS_T.get(x.disc_type, x.disc_type),
            "reason": x.reason or "", "decideDate": _iso(x.decide_date) or "", "docNo": x.doc_no or "",
            "status": x.status, "statusLabel": L_DIS_S.get(x.status, x.status),
            "revokeDate": _iso(x.revoke_date) or "", "revokeReason": x.revoke_reason or "",
            "recordStatus": x.record_status}


def list_disciplines(page, page_size, keyword=None, type=None, status=None):
    with session() as db:
        q = select(CsDiscipline).where(CsDiscipline.tenant_id == _tid(),
                                       CsDiscipline.is_deleted.is_(False),
                                       CsDiscipline.record_status == "ACTIVE")
        if type:
            q = q.where(CsDiscipline.disc_type == type)
        if status:
            q = q.where(CsDiscipline.status == status)
        rows = db.scalars(q.order_by(CsDiscipline.id.desc())).all()
        items = []
        for x in rows:
            stu = _stu_of(db, x.cs_student_id)
            if keyword and (not stu or keyword.strip() not in (stu.name or "")):
                continue
            items.append(_disc_row(x, stu))
        return _page(items, page, page_size)


def create_discipline(body: dict) -> dict:
    reason = str(body.get("reason") or "").strip()
    if not body.get("studentId") or not body.get("type") or len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "学生、处分类型必填，事由不少于 5 字")
    with session() as db:
        s = _get_stu(db, body.get("studentId"))
        code = f"DIS-{datetime.now():%Y}-{db.scalar(select(func.count()).select_from(CsDiscipline).where(CsDiscipline.tenant_id == _tid())) + 1:04d}"
        d = CsDiscipline(tenant_id=_tid(), cs_student_id=s.id, disc_type=body["type"], reason=reason,
                         decide_date=datetime.utcnow(), doc_no=body.get("docNo"), code=code,
                         status="EFFECTIVE", record_status="ACTIVE")
        db.add(d)
        db.flush()
        _audit(db, "DISCIPLINE", d.id, "新增处分", reason)
        db.commit()
        return {"id": str(d.id)}


def update_discipline(did, body: dict) -> dict:
    with session() as db:
        d = db.get(CsDiscipline, int(did))
        if not d or d.is_deleted or d.tenant_id != _tid():
            raise not_found("处分记录不存在")
        if body.get("status") == "REVOKED":
            d.status = "REVOKED"
            d.revoke_date = datetime.utcnow()
            d.revoke_reason = body.get("revokeReason") or ""
        for k, col in {"type": "disc_type", "reason": "reason"}.items():
            if body.get(k) is not None:
                setattr(d, col, body[k])
        d.version += 1
        _audit(db, "DISCIPLINE", d.id, "更新处分")
        db.commit()
        return {"id": str(d.id)}


def void_discipline(did, reason) -> dict:
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "作废原因必填且不少于 5 字")
    with session() as db:
        d = db.get(CsDiscipline, int(did))
        if not d or d.is_deleted or d.tenant_id != _tid():
            raise not_found("处分记录不存在")
        d.record_status = "VOIDED"
        d.void_reason = reason.strip()
        d.is_deleted = True
        d.version += 1
        _audit(db, "DISCIPLINE", d.id, "作废处分", reason.strip())
        db.commit()
        return {"id": str(d.id)}


# ═══ 工单 ═══

def _wo_row(x: CsWorkOrder, stu=None) -> dict:
    return {"id": str(x.id), "code": x.code or "", "title": x.title, "studentId": str(x.cs_student_id),
            "name": stu.name if stu else "", "className": stu.class_name if stu else "",
            "type": x.wo_type, "typeLabel": L_WO_T.get(x.wo_type, x.wo_type),
            "priority": x.priority, "handler": x.handler or "",
            "status": x.status, "statusLabel": L_WO_S.get(x.status, x.status),
            "detail": x.detail or "", "createTime": _iso(x.created_at),
            "updateTime": _iso(x.updated_at), "closeTime": _iso(x.close_time) or ""}


def list_work_orders(page, page_size, keyword=None, type=None, status=None, priority=None):
    with session() as db:
        q = select(CsWorkOrder).where(CsWorkOrder.tenant_id == _tid(), CsWorkOrder.is_deleted.is_(False))
        if type:
            q = q.where(CsWorkOrder.wo_type == type)
        if status:
            q = q.where(CsWorkOrder.status == status)
        if priority:
            q = q.where(CsWorkOrder.priority == priority)
        rows = db.scalars(q.order_by(CsWorkOrder.id.desc())).all()
        items = []
        for x in rows:
            stu = _stu_of(db, x.cs_student_id)
            if keyword and (not stu or (keyword.strip() not in (stu.name or "") and keyword.strip() not in x.title)):
                continue
            items.append(_wo_row(x, stu))
        return _page(items, page, page_size)


def get_work_order_detail(wid) -> dict:
    with session() as db:
        x = db.get(CsWorkOrder, int(wid))
        if not x or x.is_deleted or x.tenant_id != _tid():
            raise not_found("工单不存在")
        stu = _stu_of(db, x.cs_student_id)
        row = _wo_row(x, stu)
        row["trail"] = x.trail_json or []
        return {"order": row, "student": _stu_row(stu) if stu else None}


def create_work_order(body: dict) -> dict:
    title = str(body.get("title") or "").strip()
    if not body.get("studentId") or not title or not body.get("type"):
        raise AppException("VALIDATION_ERROR", "学生、标题、类型必填")
    with session() as db:
        s = _get_stu(db, body.get("studentId"))
        code = f"WO-{datetime.now():%Y}-{db.scalar(select(func.count()).select_from(CsWorkOrder).where(CsWorkOrder.tenant_id == _tid())) + 1:04d}"
        w = CsWorkOrder(tenant_id=_tid(), cs_student_id=s.id, title=title, wo_type=body["type"],
                        priority=body.get("priority") or "MEDIUM", detail=body.get("detail"),
                        status="PENDING_HANDLE", code=code,
                        trail_json=[{"title": "工单创建", "desc": title, "time": _iso(datetime.utcnow()),
                                     "tone": "processing"}])
        db.add(w)
        db.flush()
        _audit(db, "WORKORDER", w.id, "新增工单", title)
        db.commit()
        return {"id": str(w.id)}


def assign_work_orders(ids, handler) -> dict:
    cnt = 0
    with session() as db:
        for wid in ids:
            w = db.get(CsWorkOrder, int(wid))
            if not w or w.tenant_id != _tid() or w.is_deleted:
                continue
            w.handler = handler or _op()[0]
            if w.status == "PENDING_HANDLE":
                w.status = "PROCESSING"
            w.trail_json = (w.trail_json or []) + [{"title": "工单分派", "desc": f"分派给 {w.handler}",
                                                    "time": _iso(datetime.utcnow()), "tone": "processing"}]
            w.version += 1
            _audit(db, "WORKORDER", w.id, "分派工单", w.handler)
            cnt += 1
        db.commit()
        return {"count": cnt}


def handle_work_order(wid, note, close=False) -> dict:
    if not note or len(note.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "处理说明必填且不少于 5 字")
    with session() as db:
        w = db.get(CsWorkOrder, int(wid))
        if not w or w.is_deleted or w.tenant_id != _tid():
            raise not_found("工单不存在")
        before = w.status
        w.status = "COMPLETED" if close else "PROCESSING"
        if close:
            w.close_time = datetime.utcnow()
        w.trail_json = (w.trail_json or []) + [{"title": "办结" if close else "处理中",
                                                "desc": note.strip(), "time": _iso(datetime.utcnow()),
                                                "tone": "success" if close else "processing"}]
        w.version += 1
        _audit(db, "WORKORDER", w.id, "处理工单", note.strip(), before, w.status)
        db.commit()
        return {"id": str(w.id), "status": w.status}


def close_work_order(wid, reason) -> dict:
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "关闭原因必填且不少于 5 字")
    with session() as db:
        w = db.get(CsWorkOrder, int(wid))
        if not w or w.is_deleted or w.tenant_id != _tid():
            raise not_found("工单不存在")
        w.status = "CLOSED"
        w.close_time = datetime.utcnow()
        w.version += 1
        _audit(db, "WORKORDER", w.id, "关闭工单", reason.strip())
        db.commit()
        return {"id": str(w.id), "status": "CLOSED"}


# ═══ 心理关怀 ═══

def list_mental(page, page_size, keyword=None):
    with session() as db:
        rows = db.scalars(select(CsMentalRecord).where(CsMentalRecord.tenant_id == _tid(),
                          CsMentalRecord.is_deleted.is_(False)).order_by(CsMentalRecord.id.desc())).all()
        items = []
        for x in rows:
            stu = _stu_of(db, x.cs_student_id)
            if keyword and (not stu or keyword.strip() not in (stu.name or "")):
                continue
            items.append({"id": str(x.id), "studentId": str(x.cs_student_id),
                          "name": stu.name if stu else "", "className": stu.class_name if stu else "",
                          "level": x.level, "levelLabel": "重点关注" if x.level == "FOCUS" else "常规关注",
                          "lastFollowTime": _iso(x.last_follow_time) or "",
                          "nextFollowTime": _iso(x.next_follow_time) or "", "summary": x.summary or "",
                          "counselorNote": x.counselor_note or "", "operator": x.operator or "",
                          "status": x.status})
        _audit_view_mental(db)
        return _page(items, page, page_size)


def _audit_view_mental(db):
    _audit(db, "MENTAL", "-", "查看心理关怀记录", "涉密访问留痕")
    db.commit()


# ═══ 审计 ═══

def _log_row(x: CsAuditTrail) -> dict:
    return {"id": str(x.id), "time": _iso(x.occurred_at), "operator": x.operator or "",
            "roleName": x.role_name or "", "bizType": x.biz_type, "bizId": x.biz_id or "",
            "action": x.action, "detail": x.detail or "", "before": x.before_val or "",
            "after": x.after_val or ""}


def list_audit(page, page_size, biz_type=None, keyword=None):
    with session() as db:
        q = select(CsAuditTrail).where(CsAuditTrail.tenant_id == _tid())
        if biz_type:
            q = q.where(CsAuditTrail.biz_type == biz_type)
        rows = db.scalars(q.order_by(CsAuditTrail.id.desc())).all()
        if keyword:
            kw = keyword.strip()
            rows = [r for r in rows if kw in (r.action or "") or kw in (r.detail or "")]
        return _page([_log_row(r) for r in rows], page, page_size)


# ═══ 看板 ═══

def get_dashboard() -> dict:
    with session() as db:
        stu = db.scalar(select(func.count()).select_from(CsServiceStudent).where(
            CsServiceStudent.tenant_id == _tid(), CsServiceStudent.is_deleted.is_(False),
            CsServiceStudent.record_status == "ACTIVE")) or 0
        pend_leave = db.scalar(select(func.count()).select_from(CsLeave).where(
            CsLeave.tenant_id == _tid(), CsLeave.status == "PENDING_REVIEW",
            CsLeave.is_deleted.is_(False))) or 0
        pend_grant = db.scalar(select(func.count()).select_from(CsGrant).where(
            CsGrant.tenant_id == _tid(), CsGrant.status.in_(["PENDING_REVIEW", "REVIEWING"]),
            CsGrant.is_deleted.is_(False))) or 0
        open_de = db.scalar(select(func.count()).select_from(CsDormException).where(
            CsDormException.tenant_id == _tid(), CsDormException.status.in_(["PENDING_HANDLE", "PROCESSING"]),
            CsDormException.is_deleted.is_(False))) or 0
        open_wo = db.scalar(select(func.count()).select_from(CsWorkOrder).where(
            CsWorkOrder.tenant_id == _tid(), CsWorkOrder.status.in_(["PENDING_HANDLE", "PROCESSING"]),
            CsWorkOrder.is_deleted.is_(False))) or 0
        return {"termName": "2026 春季学期", "termRange": "2026-02 ~ 2026-07",
                "updateTime": _iso(datetime.now()),
                "kpis": [
                    {"key": "students", "label": "在校学生", "value": str(stu), "trend": "", "trendQuality": "neutral"},
                    {"key": "leave", "label": "待审批请假", "value": str(pend_leave),
                     "trend": f"待处理 {pend_leave}", "trendQuality": "bad" if pend_leave else "good"},
                    {"key": "grant", "label": "待审核资助", "value": str(pend_grant),
                     "trend": f"待处理 {pend_grant}", "trendQuality": "neutral"},
                    {"key": "workorder", "label": "在办工单", "value": str(open_wo),
                     "trend": f"宿舍异常 {open_de}", "trendQuality": "bad" if open_wo else "good"},
                ],
                "todos": [
                    {"id": "t1", "label": "待审批请假", "value": pend_leave, "link": "/admin/campus-service/leave"},
                    {"id": "t2", "label": "待审核资助", "value": pend_grant, "link": "/admin/campus-service/grants"},
                    {"id": "t3", "label": "待处理工单", "value": open_wo, "link": "/admin/campus-service/work-orders"},
                ],
                "flow": [], "hotServices": [], "riskAlerts": []}
