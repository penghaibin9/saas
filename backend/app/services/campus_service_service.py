"""在校服务域真实数据服务。租户过滤 + 脱敏 + 审计留痕。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.core.field_crypto import encrypt_field, mask_id_card_encrypted, mask_phone_encrypted
from app.core.optimistic_lock import atomic_versioned_update, require_expected_version
from app.models import (CsAuditTrail, CsDiscipline, CsDormException, CsDormRecord, CsGrant, CsLeave,
                        CsMentalRecord, CsServiceStudent, CsWorkOrder)
from app.services import shadow_student_service as shadow
from app.services.db_service import _iso, _tid, session

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


def _cs_scope_student_ids(db):
    """当前调用者可见的 CsServiceStudent.id 集合。None=TENANT_ALL(不过滤)；set()=fail-closed(看不到)。
    与 student_affairs 共用 StudentAffairsSecurityContext，保证「在校服务」legacy 面与新学工面同一数据范围口径
    （未配范围的辅导员在两处都 fail-closed，绝不回退全租户）。宿舍域按楼栋范围另判，不走此班级口径。"""
    from app.core.affairs_security import build_affairs_context
    ctx = build_affairs_context(get_current_user_ctx() or {}, db)
    if ctx.scope_type == "TENANT_ALL":
        return None
    names = ctx.allowed_class_names(db)
    if not names:
        return set()
    rows = db.scalars(select(CsServiceStudent.id).where(
        CsServiceStudent.tenant_id == _tid(), CsServiceStudent.class_name.in_(list(names)))).all()
    return set(rows)


def _require_cs_scope(db, cs_student_id, scope_ids="__q__", student_id=None):
    """记录级数据范围校验：越范围→403002 NO_DATA_SCOPE。scope_ids 传入可复用（省重复查）。
    cs_student_id=0 是 13A 新引擎写入的哨兵值（该记录无 CsServiceStudent 台账行，真实学生见 student_id），
    此时改按学工 class 范围口径校验，避免"0 不在任何范围集合内"导致的误 403（见 P0 §4.2 集成①遗留问题）。"""
    if (cs_student_id is None or int(cs_student_id) == 0) and student_id:
        from app.models import StudentProfile
        from app.services.affairs_dashboard_service import _allowed_class_ids
        allowed, _ = _allowed_class_ids(db, get_current_user_ctx() or {})
        if allowed is not None:
            s = db.get(StudentProfile, int(student_id))
            if not s or s.class_id not in allowed:
                raise AppException("NO_DATA_SCOPE", "该记录不在您的数据范围内")
        return
    ids = _cs_scope_student_ids(db) if scope_ids == "__q__" else scope_ids
    if ids is not None and cs_student_id is not None and int(cs_student_id) not in ids:
        raise AppException("NO_DATA_SCOPE", "该记录不在您的数据范围内")


def _get_stu(db, sid) -> CsServiceStudent:
    s = db.get(CsServiceStudent, int(sid))
    if not s or s.is_deleted or s.tenant_id != _tid():
        raise not_found("学生服务记录不存在或不在当前数据范围内")
    _require_cs_scope(db, s.id)
    return s


def _stu_of(db, csid):
    return db.get(CsServiceStudent, csid)


def _cs_students_by_ids(db, rows, attr="cs_student_id"):
    """批量取回 rows 涉及的在校服务学生台账 {id: CsServiceStudent}，替代列表循环内逐行
    _stu_of（消 N+1）。哨兵行 cs_student_id=0 不入集合，循环内 .get(0) 自然落 None。"""
    ids = {int(getattr(x, attr)) for x in rows if getattr(x, attr, None)}
    if not ids:
        return {}
    return {s.id: s for s in db.scalars(select(CsServiceStudent).where(CsServiceStudent.id.in_(ids))).all()}


# ═══ 学生台账 ═══

def _stu_row(s: CsServiceStudent, *, db=None, profiles: dict | None = None,
             cache: dict | None = None) -> dict:
    """渲染台账行。传 db+profiles 时走双读：已绑定行显示主档当前身份，
    未绑定的历史行沿用自己的快照并标 legacyFallback（见 shadow_student_service）。"""
    row = _stu_row_raw(s)
    if db is not None:
        shadow.apply_dual_read(row, s, profiles if profiles is not None else {}, db=db, cache=cache)
    return row


def _stu_row_raw(s: CsServiceStudent) -> dict:
    return {"id": str(s.id), "studentId": str(s.student_id or s.id), "name": s.name,
            "studentNo": s.student_no or "", "gender": s.gender or "", "collegeName": s.college_name or "",
            "majorName": s.major_name or "", "classId": s.class_id or "", "className": s.class_name or "",
            "grade": s.grade or "", "phone": mask_phone_encrypted(s.phone_encrypted),
            "idCard": mask_id_card_encrypted(s.id_card_encrypted), "counselor": s.counselor or "",
            "building": s.building or "", "room": s.room or "",
            "careLevel": s.care_level, "careLevelLabel": L_CARE.get(s.care_level, s.care_level),
            "riskLevel": s.risk_level, "riskLabel": L_RISK.get(s.risk_level, s.risk_level),
            "mentalFlag": s.mental_flag, "recordStatus": s.record_status, "updateTime": _iso(s.updated_at)}


def list_students(page, page_size, keyword=None, class_id=None, care_level=None, risk_level=None):
    with session() as db:
        q = select(CsServiceStudent).where(CsServiceStudent.tenant_id == _tid(),
                                           CsServiceStudent.is_deleted.is_(False),
                                           CsServiceStudent.record_status == "ACTIVE")
        scope_ids = _cs_scope_student_ids(db)
        if scope_ids is not None:
            q = q.where(CsServiceStudent.id.in_(scope_ids or {-1}))
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
        profiles, cache = shadow.load_profiles(db, rows), {}
        return _page([_stu_row(r, db=db, profiles=profiles, cache=cache) for r in rows],
                     page, page_size)


def get_student_detail(sid) -> dict:
    with session() as db:
        s = _get_stu(db, sid)
        grants = db.scalars(select(CsGrant).where(CsGrant.tenant_id == _tid(),
                            CsGrant.cs_student_id == s.id).order_by(CsGrant.id.desc())).all()
        discs = db.scalars(select(CsDiscipline).where(CsDiscipline.tenant_id == _tid(),
                           CsDiscipline.cs_student_id == s.id).order_by(CsDiscipline.id.desc())).all()
        wos = db.scalars(select(CsWorkOrder).where(CsWorkOrder.tenant_id == _tid(),
                         CsWorkOrder.cs_student_id == s.id).order_by(CsWorkOrder.id.desc())).all()
        logs = db.scalars(select(CsAuditTrail).where(CsAuditTrail.tenant_id == _tid(),
                          CsAuditTrail.biz_id == str(s.id)).order_by(CsAuditTrail.id.desc()).limit(20)).all()
        return {"student": _stu_row(s, db=db, profiles=shadow.load_profiles(db, [s])),
                "grants": [_grant_row(x, s) for x in grants],
                "disciplines": [_disc_row(x, s) for x in discs],
                "workOrders": [_wo_row(x, s) for x in wos],
                "auditLogs": [_log_row(x) for x in logs]}


def create_student(body: dict) -> dict:
    """新建服务台账行。阶段 D 起必须挂在已有学籍档案上，不再允许独立影子学生。

    身份字段（姓名/学号/组织）一律取自主档快照，调用方传什么都不采信——
    否则同一个人在这里叫张三、在学籍里叫张山，越权范围和统计口径立刻分裂。
    """
    with session() as db:
        p = shadow.resolve_profile_for_shadow(
            db, _tid(), domain_label="在校服务台账",
            student_id=body.get("studentId") or body.get("profileStudentId"),
            student_no=body.get("studentNo"))
        dup = db.scalars(select(CsServiceStudent).where(
            CsServiceStudent.tenant_id == _tid(), CsServiceStudent.student_id == p.id,
            CsServiceStudent.is_deleted.is_(False))).first()
        if dup:
            raise AppException("DATA_CONFLICT", f"{p.real_name} 已有在校服务台账记录，请勿重复新增")
        snap = shadow.identity_snapshot(db, p)
        s = CsServiceStudent(tenant_id=_tid(), record_status="ACTIVE",
                             care_level=body.get("careLevel") or "NORMAL", room=body.get("room"),
                             building=body.get("building"), counselor=body.get("counselor"),
                             phone_encrypted=encrypt_field(body.get("phone")),
                             **{k: v for k, v in snap.items() if v is not None})
        db.add(s)
        db.flush()
        _audit(db, "RECORD", s.id, "新增服务记录", f"{snap['name']}（{snap['student_no']}）")
        db.commit()
        return {"id": str(s.id), "profileStudentId": str(p.id)}


def update_student(sid, body: dict) -> dict:
    with session() as db:
        s = _get_stu(db, sid)
        shadow.assert_identity_immutable(db, s, body, "在校服务台账")
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


# ═══ 请假旧实现已退出 ═══
# 请假唯一实现：app.services.affairs_leave_service。历史 CsLeave 数据仍保留。

def _parse_versioned_item(raw):
    if isinstance(raw, dict):
        return raw.get("id"), raw.get("version")
    if isinstance(raw, (list, tuple)) and len(raw) >= 2:
        return raw[0], raw[1]
    return raw, None


# ═══ 资助 ═══

def _grant_row(x: CsGrant, stu=None, mask=True) -> dict:
    row = {"id": str(x.id), "code": x.code or "", "studentId": str(x.cs_student_id),
           "name": stu.name if stu else "", "className": stu.class_name if stu else "",
           "type": x.grant_type, "typeLabel": L_GRANT_T.get(x.grant_type, x.grant_type),
           "amountRange": _amt_range(x.amount), "applyReason": x.apply_reason or "",
           "materialSensitive": x.material_sensitive, "status": x.status,
           "statusLabel": L_GRANT_S.get(x.status, x.status), "applyTime": _iso(x.apply_time) or "",
           "reviewer": x.reviewer or "", "reviewTime": _iso(x.review_time) or "",
           "returnReason": x.return_reason or "", "currentNode": x.current_node or "",
           "version": int(x.version or 0)}
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
        scope_ids = _cs_scope_student_ids(db)
        cs_map = _cs_students_by_ids(db, rows)
        items = []
        for x in rows:
            if scope_ids is not None and x.cs_student_id not in scope_ids:
                continue
            stu = cs_map.get(int(x.cs_student_id)) if x.cs_student_id else None
            if keyword and (not stu or keyword.strip() not in (stu.name or "")):
                continue
            items.append(_grant_row(x, stu, mask=True))
        return _page(items, page, page_size)


def get_grant_detail(gid) -> dict:
    with session() as db:
        x = db.get(CsGrant, int(gid))
        if not x or x.is_deleted or x.tenant_id != _tid():
            raise not_found("资助申请不存在")
        _require_cs_scope(db, x.cs_student_id)
        stu = _stu_of(db, x.cs_student_id)
        return {"grant": _grant_row(x, stu, mask=False), "student": _stu_row(stu, db=db, profiles=shadow.load_profiles(db, [stu])) if stu else None}


def _grant_act(gid, target, need_reason=False, reason=None, node="", action="", expected_version=None):
    if need_reason and (not reason or len(reason.strip()) < 5):
        raise AppException("VALIDATION_ERROR", "退回原因必填且不少于 5 字")
    ver = require_expected_version(expected_version)
    with session() as db:
        x = db.get(CsGrant, int(gid))
        if not x or x.is_deleted or x.tenant_id != _tid():
            raise not_found("资助申请不存在")
        _require_cs_scope(db, x.cs_student_id)
        if x.status in ("APPROVED", "REJECTED"):
            raise AppException("DATA_CONFLICT", "该资助已终审，请刷新")
        before = x.status
        n, _ = _op()
        values = {
            "status": target,
            "reviewer": n,
            "review_time": datetime.utcnow(),
            "current_node": node,
        }
        if target == "RETURNED":
            values["return_reason"] = (reason or "").strip()
        atomic_versioned_update(
            db, CsGrant, entity_id=int(x.id), tenant_id=_tid(),
            expected_version=ver, values=values, expected_status=before)
        _audit(db, "GRANT", x.id, action, reason or "", before, target)
        db.commit()
        return {"id": str(x.id), "status": target, "version": ver + 1}


def approve_grant(gid, comment="", expected_version=None):
    return _grant_act(gid, "APPROVED", False, None, "已办结", "审批通过", expected_version)


def return_grant(gid, reason, expected_version=None):
    return _grant_act(gid, "RETURNED", True, reason, "学生补充材料", "退回补充", expected_version)


def batch_approve_grants(items):
    cnt = 0
    errors = []
    for raw in items or []:
        gid, ver = _parse_versioned_item(raw)
        try:
            _grant_act(gid, "APPROVED", False, None, "已办结", "批量审批通过", ver)
            cnt += 1
        except AppException as e:
            errors.append({"id": str(gid), "code": e.code, "message": e.message})
    return {"count": cnt, "failed": errors}


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
        scope_ids = _cs_scope_student_ids(db)
        cs_map = _cs_students_by_ids(db, rows)
        items = []
        for x in rows:
            if scope_ids is not None and x.cs_student_id not in scope_ids:
                continue
            stu = cs_map.get(int(x.cs_student_id)) if x.cs_student_id else None
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
        scope_ids = _cs_scope_student_ids(db)
        cs_map = _cs_students_by_ids(db, rows)
        items = []
        for x in rows:
            if scope_ids is not None and x.cs_student_id not in scope_ids:
                continue
            stu = cs_map.get(int(x.cs_student_id)) if x.cs_student_id else None
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


def handle_dorm_exception(eid, note, complete=False, expected_version=None) -> dict:
    if not note or len(note.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "处理说明必填且不少于 5 字")
    ver = require_expected_version(expected_version)
    with session() as db:
        e = db.get(CsDormException, int(eid))
        if not e or e.is_deleted or e.tenant_id != _tid():
            raise not_found("宿舍异常不存在")
        _require_cs_scope(db, e.cs_student_id)
        before = e.status
        new_status = "COMPLETED" if complete else "PROCESSING"
        atomic_versioned_update(
            db, CsDormException, entity_id=int(e.id), tenant_id=_tid(),
            expected_version=ver, values={
                "status": new_status,
                "handle_note": note.strip(),
                "handle_time": datetime.utcnow(),
            }, expected_status=before)
        _audit(db, "DORM", e.id, "处理宿舍异常", note.strip(), before, new_status)
        db.commit()
        return {"id": str(e.id), "status": new_status, "version": ver + 1}


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
        scope_ids = _cs_scope_student_ids(db)
        cs_map = _cs_students_by_ids(db, rows)
        items = []
        for x in rows:
            if scope_ids is not None and x.cs_student_id not in scope_ids:
                continue
            stu = cs_map.get(int(x.cs_student_id)) if x.cs_student_id else None
            if keyword and (not stu or keyword.strip() not in (stu.name or "")):
                continue
            items.append(_disc_row(x, stu))
        return _page(items, page, page_size)


# 旧版违纪直接编辑入口已废弃（甲方拍板保留新版流程、下线旧版）：新旧两套写入路径共用同一张
# t_cs_discipline 表、权限体系分裂，且旧版 update_discipline 的 REVOKED 分支不同步新版对账用的
# record_status 字段，导致奖助/毕业资格判定会把旧版"已撤销"的处分继续当生效处分——已坐实的真实
# 缺陷（见 review_appeal 修复同期复核）。三个写操作全部拒绝，只保留 list/get 只读查询与既有数据兼容。
_DISCIPLINE_RETIRED_MSG = "违纪登记（现有）写操作已下线，请到「学工中心 → 违纪处分」新版工作台处理"


def create_discipline(body: dict) -> dict:
    raise AppException("DATA_CONFLICT", _DISCIPLINE_RETIRED_MSG)


def update_discipline(did, body: dict) -> dict:
    raise AppException("DATA_CONFLICT", _DISCIPLINE_RETIRED_MSG)


def void_discipline(did, reason) -> dict:
    raise AppException("DATA_CONFLICT", _DISCIPLINE_RETIRED_MSG)


# ═══ 工单 ═══

def _wo_row(x: CsWorkOrder, stu=None) -> dict:
    return {"id": str(x.id), "code": x.code or "", "title": x.title, "studentId": str(x.cs_student_id),
            "name": stu.name if stu else "", "className": stu.class_name if stu else "",
            "type": x.wo_type, "typeLabel": L_WO_T.get(x.wo_type, x.wo_type),
            "priority": x.priority, "handler": x.handler or "",
            "status": x.status, "statusLabel": L_WO_S.get(x.status, x.status),
            "version": int(x.version or 0),
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
        scope_ids = _cs_scope_student_ids(db)
        cs_map = _cs_students_by_ids(db, rows)
        items = []
        for x in rows:
            if scope_ids is not None and x.cs_student_id not in scope_ids:
                continue
            stu = cs_map.get(int(x.cs_student_id)) if x.cs_student_id else None
            if keyword and (not stu or (keyword.strip() not in (stu.name or "") and keyword.strip() not in x.title)):
                continue
            items.append(_wo_row(x, stu))
        return _page(items, page, page_size)


def get_work_order_detail(wid) -> dict:
    with session() as db:
        x = db.get(CsWorkOrder, int(wid))
        if not x or x.is_deleted or x.tenant_id != _tid():
            raise not_found("工单不存在")
        _require_cs_scope(db, x.cs_student_id)
        stu = _stu_of(db, x.cs_student_id)
        row = _wo_row(x, stu)
        row["trail"] = x.trail_json or []
        return {"order": row, "student": _stu_row(stu, db=db, profiles=shadow.load_profiles(db, [stu])) if stu else None}


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
        scope_ids = _cs_scope_student_ids(db)
        for wid in ids:
            w = db.get(CsWorkOrder, int(wid))
            if not w or w.tenant_id != _tid() or w.is_deleted:
                continue
            if scope_ids is not None and int(w.cs_student_id or 0) not in scope_ids:
                continue  # 越数据范围工单跳过，不整批 403
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


def handle_work_order(wid, note, close=False, expected_version=None) -> dict:
    if not note or len(note.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "处理说明必填且不少于 5 字")
    ver = require_expected_version(expected_version)
    with session() as db:
        w = db.get(CsWorkOrder, int(wid))
        if not w or w.is_deleted or w.tenant_id != _tid():
            raise not_found("工单不存在")
        _require_cs_scope(db, w.cs_student_id)
        before = w.status
        new_status = "COMPLETED" if close else "PROCESSING"
        trail = list(w.trail_json or []) + [{"title": "办结" if close else "处理中",
                                            "desc": note.strip(), "time": _iso(datetime.utcnow()),
                                            "tone": "success" if close else "processing"}]
        values = {"status": new_status, "trail_json": trail}
        if close:
            values["close_time"] = datetime.utcnow()
        atomic_versioned_update(
            db, CsWorkOrder, entity_id=int(w.id), tenant_id=_tid(),
            expected_version=ver, values=values, expected_status=before)
        _audit(db, "WORKORDER", w.id, "处理工单", note.strip(), before, new_status)
        db.commit()
        return {"id": str(w.id), "status": new_status, "version": ver + 1}


def close_work_order(wid, reason, expected_version=None) -> dict:
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "关闭原因必填且不少于 5 字")
    ver = require_expected_version(expected_version)
    with session() as db:
        w = db.get(CsWorkOrder, int(wid))
        if not w or w.is_deleted or w.tenant_id != _tid():
            raise not_found("工单不存在")
        _require_cs_scope(db, w.cs_student_id)
        before = w.status
        atomic_versioned_update(
            db, CsWorkOrder, entity_id=int(w.id), tenant_id=_tid(),
            expected_version=ver, values={
                "status": "CLOSED",
                "close_time": datetime.utcnow(),
            }, expected_status=before)
        _audit(db, "WORKORDER", w.id, "关闭工单", reason.strip(), before, "CLOSED")
        db.commit()
        return {"id": str(w.id), "status": "CLOSED", "version": ver + 1}

# ═══ 心理关怀 ═══

def list_mental(page, page_size, keyword=None, user=None, reason=None):
    # SEC-1/SEC-2：counselorNote 涉密明细默认遮蔽；仅授权角色(心理老师/校·平台超管，**不含学工处管理员**)
    # + 原因(≥5字) 方返回明文，并写 t_security_audit_log(SENSITIVE_VIEW)。端点已加 psyDetail.view 细粒度门禁。
    from app.core.context import get_current_user_ctx
    u = user or (get_current_user_ctx() or {})
    role = (u or {}).get("currentRoleCode") or ""
    can = role in {"PSYCHOLOGY_TEACHER", "SCHOOL_ADMIN", "PLATFORM_SUPER_ADMIN"}
    reveal = bool(can and reason and len(str(reason).strip()) >= 5)
    with session() as db:
        rows = db.scalars(select(CsMentalRecord).where(CsMentalRecord.tenant_id == _tid(),
                          CsMentalRecord.is_deleted.is_(False)).order_by(CsMentalRecord.id.desc())).all()
        scope_ids = _cs_scope_student_ids(db)
        cs_map = _cs_students_by_ids(db, rows)
        items = []
        for x in rows:
            if scope_ids is not None and x.cs_student_id not in scope_ids:
                continue
            stu = cs_map.get(int(x.cs_student_id)) if x.cs_student_id else None
            if keyword and (not stu or keyword.strip() not in (stu.name or "")):
                continue
            items.append({"id": str(x.id), "studentId": str(x.cs_student_id),
                          "name": stu.name if stu else "", "className": stu.class_name if stu else "",
                          "level": x.level, "levelLabel": "重点关注" if x.level == "FOCUS" else "常规关注",
                          "lastFollowTime": _iso(x.last_follow_time) or "",
                          "nextFollowTime": _iso(x.next_follow_time) or "", "summary": x.summary or "",
                          "counselorNote": (x.counselor_note or "") if reveal else "[心理明细·受限，需授权+原因]",
                          "noteMasked": not reveal,
                          "operator": x.operator or "", "status": x.status})
        _audit_view_mental(db)
        if reveal:
            try:
                from app.services import audit_log
                audit_log.record("SENSITIVE_VIEW", "cs_mental_records",
                                 detail={"domain": "MENTAL", "reason": str(reason)[:200],
                                         "count": len(items)}, result="SUCCESS")
            except Exception:  # noqa: BLE001
                pass
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
                    {"id": "t1", "label": "待审批请假", "value": pend_leave, "link": "/admin/student-affairs/leave"},
                    {"id": "t2", "label": "待审核资助", "value": pend_grant, "link": "/admin/campus-service/grants"},
                    {"id": "t3", "label": "待处理工单", "value": open_wo, "link": "/admin/campus-service/work-orders"},
                ],
                "flow": [], "hotServices": [], "riskAlerts": []}
