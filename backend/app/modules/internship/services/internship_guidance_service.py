"""岗位实习 · 指导记录（P1-Stage2）。指导教师对本人指导学生的过程指导留痕。
owner + 数据范围复用 internship_service 的 _current_scope / _rec_in_scope。审计 target_type=GUIDANCE。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, no_permission, not_found
from app.models import (InternshipAuditTrail, InternshipGuidance, InternshipRecord, StudentProfile)
from app.services.db_service import _iso, _tid, session

METHOD_LABEL = {"ONLINE": "线上", "PHONE": "电话", "ONSITE": "现场",
                "ENTERPRISE_FEEDBACK": "企业导师反馈", "VIDEO": "视频"}


def _op_name(user) -> str:
    return (user or {}).get("realName") or "系统"


def _trail(db, gid, action, detail=None, operator="系统"):
    db.add(InternshipAuditTrail(tenant_id=_tid(), target_id=gid, target_type="GUIDANCE",
                                action=action, operator_name=operator, detail_json=detail or {},
                                occurred_at=datetime.utcnow()))


def _get(db, gid) -> InternshipGuidance:
    g = db.get(InternshipGuidance, int(gid))
    if not g or g.is_deleted or g.tenant_id != _tid():
        raise not_found("指导记录不存在")
    return g


def _ctx(db, g):
    rec = db.get(InternshipRecord, g.internship_id)
    stu = db.get(StudentProfile, rec.student_id) if rec else None
    return rec, stu


def _row(g, rec, stu):
    return {
        "id": str(g.id), "internId": str(g.internship_id),
        "studentName": stu.real_name if stu else "-", "studentNo": stu.student_no if stu else "-",
        "advisorName": g.advisor_name or (rec.advisor_name if rec else ""),
        "enterpriseName": rec.enterprise_name if rec else "",
        "method": g.method, "methodLabel": METHOD_LABEL.get(g.method, g.method),
        "topic": g.topic or "", "content": g.content or "", "problemType": g.problem_type or "",
        "suggestion": g.suggestion or "", "nextFollowDate": g.next_follow_date or "",
        "toRisk": bool(g.to_risk), "notifyCounselor": bool(g.notify_counselor),
        "status": g.status, "createdAt": _iso(g.created_at) or "",
    }


def _scope_ctx(user):
    from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
    return _current_scope(user), _rec_in_scope


def _validate_file(file_id):
    """附件 file_id 校验：为空放行；非空必须是本租户已存在的文件，否则拒绝。"""
    fid = (file_id or "").strip()
    if not fid:
        return None
    from app.services import file_service
    if not file_service.get_file_meta(fid):
        raise AppException("VALIDATION_ERROR", "附件不存在或无权访问，请重新上传")
    return fid


def _spawn_risk(db, rec, stu, g, user):
    """指导「转风险」联动：to_risk=True 时在 t_risk_record 生成一条待处理风险单并写审计。
    返回新建 risk_id 或 None。风险处置闭环见 internship_risk_service。"""
    from app.models import RiskRecord
    risk = RiskRecord(
        tenant_id=_tid(), internship_id=rec.id,
        risk_code="INT-GUIDE", risk_title=f"指导发现问题：{g.topic or g.problem_type or '需跟进'}",
        risk_level="MEDIUM", source_module="guidance",
        owner_name=_op_name(user), status="PENDING_HANDLE",
        last_follow_note=(g.suggestion or g.content or "")[:500])
    db.add(risk); db.flush()
    notified = False
    if g.notify_counselor:
        from app.modules.internship.services.internship_service import notify_counselor_for_student
        notified = notify_counselor_for_student(
            db, stu, title=f"实习风险提醒：{stu.real_name if stu else '学生'}",
            content=f"指导教师 {_op_name(user)} 在指导中发现问题「{g.topic or g.problem_type or '需跟进'}」，"
                    f"已形成风险单待处置。建议：{(g.suggestion or g.content or '')[:200]}",
            source_biz_id=risk.id, message_type="INTERNSHIP_RISK")
    db.add(InternshipAuditTrail(
        tenant_id=_tid(), target_id=risk.id, target_type="RISK", action="CREATE_FROM_GUIDANCE",
        operator_name=_op_name(user),
        detail_json={"guidanceId": str(g.id), "studentName": stu.real_name if stu else "",
                     "notifyCounselor": bool(g.notify_counselor), "counselorNotified": notified},
        occurred_at=datetime.utcnow()))
    return risk.id


def create(user, body) -> dict:
    b = body or {}
    iid = b.get("internshipId") or b.get("internId")
    if not iid:
        raise AppException("VALIDATION_ERROR", "缺少实习记录 internshipId")
    if not (b.get("content") or "").strip():
        raise AppException("VALIDATION_ERROR", "指导内容必填")
    file_id = _validate_file(b.get("fileId"))
    scope, in_scope = _scope_ctx(user)
    with session() as db:
        rec = db.get(InternshipRecord, int(iid))
        if not rec or rec.is_deleted or rec.tenant_id != _tid():
            raise not_found("实习记录不存在")
        stu = db.get(StudentProfile, rec.student_id)
        if not in_scope(scope, db, rec, stu):  # owner：只能对本人指导学生新增
            raise no_permission("只能对本人指导学生新增指导记录")
        g = InternshipGuidance(
            tenant_id=_tid(), internship_id=rec.id, student_id=rec.student_id,
            advisor_name=_op_name(user), method=b.get("method") or "ONSITE",
            topic=b.get("topic"), content=(b.get("content") or "").strip(),
            problem_type=b.get("problemType"), suggestion=b.get("suggestion"),
            next_follow_date=b.get("nextFollowDate"),
            to_risk=bool(b.get("toRisk")), notify_counselor=bool(b.get("notifyCounselor")),
            file_id=file_id, status="NORMAL")
        db.add(g); db.flush()
        _trail(db, g.id, "CREATE", {"method": g.method, "topic": g.topic or "",
                                    "hasFile": bool(file_id)}, operator=_op_name(user))
        risk_id = _spawn_risk(db, rec, stu, g, user) if g.to_risk else None
        if risk_id:
            _trail(db, g.id, "SPAWN_RISK", {"riskId": str(risk_id)}, operator=_op_name(user))
        elif g.notify_counselor:  # 仅通知辅导员、未形成风险
            from app.modules.internship.services.internship_service import notify_counselor_for_student
            if notify_counselor_for_student(
                    db, stu, title=f"实习指导提醒：{stu.real_name if stu else '学生'}",
                    content=f"指导教师 {_op_name(user)} 反馈：{(g.content or '')[:200]}",
                    source_biz_id=g.id, message_type="INTERNSHIP_GUIDANCE"):
                _trail(db, g.id, "NOTIFY_COUNSELOR", {}, operator=_op_name(user))
        db.commit()
        return {"id": str(g.id), "riskId": str(risk_id) if risk_id else None}


def void_guidance(user, gid, reason="") -> dict:
    scope, in_scope = _scope_ctx(user)
    with session() as db:
        g = _get(db, gid)
        rec, stu = _ctx(db, g)
        if not in_scope(scope, db, rec, stu):
            raise no_permission("只能撤销本人指导学生的指导记录")
        g.is_deleted = True
        g.status = "VOIDED"
        g.version += 1
        _trail(db, g.id, "VOID", {"reason": reason}, operator=_op_name(user))
        db.commit()
        return {"id": str(g.id), "status": "VOIDED"}


def list_guidances(page, page_size, keyword=None, user=None) -> tuple[list[dict], int]:
    scope, in_scope = _scope_ctx(user)
    with session() as db:
        rows = db.scalars(select(InternshipGuidance).where(
            InternshipGuidance.tenant_id == _tid(), InternshipGuidance.is_deleted.is_(False)
        ).order_by(InternshipGuidance.id.desc())).all()
        items = []
        for g in rows:
            rec, stu = _ctx(db, g)
            if keyword and (not stu or keyword.strip() not in (stu.real_name or "")):
                continue
            if not in_scope(scope, db, rec, stu):
                continue
            items.append(_row(g, rec, stu))
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


def get_guidance(gid, user=None) -> dict:
    scope, in_scope = _scope_ctx(user)
    with session() as db:
        g = _get(db, gid)
        rec, stu = _ctx(db, g)
        if not in_scope(scope, db, rec, stu):
            raise no_permission("该指导记录不在你的数据范围内")
        trail = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == _tid(), InternshipAuditTrail.target_type == "GUIDANCE",
            InternshipAuditTrail.target_id == g.id).order_by(InternshipAuditTrail.id)).all()
        from app.services import file_service
        return {**_row(g, rec, stu), "attachment": file_service.attachment_view(g.file_id),
                "auditTrail": [{"action": t.action, "operator": t.operator_name or "",
                                "occurredAt": _iso(t.occurred_at)} for t in trail]}


def export_guidances(keyword=None, user=None) -> dict:
    from app.services import xlsx_util
    items, _ = list_guidances(1, 100000, keyword=keyword, user=user)
    headers = ["学号", "姓名", "指导教师", "企业", "指导方式", "主题", "问题类型", "处理建议",
               "下次跟进", "是否形成风险"]
    rows = [[it["studentNo"], it["studentName"], it["advisorName"], it["enterpriseName"],
             it["methodLabel"], it["topic"], it["problemType"], it["suggestion"],
             it["nextFollowDate"], "是" if it["toRisk"] else "否"] for it in items]
    wm = f"岗位实习中心·指导记录台账 · 导出人：{_op_name(user)} · {datetime.now():%Y-%m-%d %H:%M} · 导出留痕"
    content = xlsx_util.build_ledger_xlsx("指导记录台账", headers, rows, watermark=wm)
    return xlsx_util.pack_xlsx_result(content, "指导记录台账.xlsx", len(items))
