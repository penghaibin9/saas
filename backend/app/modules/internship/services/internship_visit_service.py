"""岗位实习 · 教师巡访（P1-Stage2）。含企业/学生反馈、安全隐患与整改跟进。
owner + 数据范围复用 internship_service。审计 target_type=VISIT。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, no_permission, not_found
from app.models import (InternshipAuditTrail, InternshipRecord, InternshipVisit, StudentProfile)
from app.services.db_service import _as_id, _iso, _tid, session

METHOD_LABEL = {"ONSITE": "现场", "ONLINE": "线上", "PHONE": "电话"}
RECTIFY_LABEL = {"NONE": "无需整改", "PENDING": "整改中", "DONE": "已整改"}


def _op_name(user) -> str:
    return (user or {}).get("realName") or "系统"


def _trail(db, vid, action, detail=None, operator="系统"):
    db.add(InternshipAuditTrail(tenant_id=_tid(), target_id=vid, target_type="VISIT",
                                action=action, operator_name=operator, detail_json=detail or {},
                                occurred_at=datetime.utcnow()))


def _get(db, vid) -> InternshipVisit:
    v = db.get(InternshipVisit, _as_id(vid))
    if not v or v.is_deleted or v.tenant_id != _tid():
        raise not_found("巡访记录不存在")
    return v


def _ctx(db, v):
    rec = db.get(InternshipRecord, v.internship_id)
    stu = db.get(StudentProfile, rec.student_id) if rec else None
    return rec, stu


def _row(v, rec, stu):
    return {
        "id": str(v.id), "internId": str(v.internship_id),
        "studentName": stu.real_name if stu else "-", "studentNo": stu.student_no if stu else "-",
        "advisorName": v.advisor_name or "", "enterpriseName": v.enterprise_name or (rec.enterprise_name if rec else ""),
        "visitAt": _iso(v.visit_at) or "", "method": v.method, "methodLabel": METHOD_LABEL.get(v.method, v.method),
        "enterpriseFeedback": v.enterprise_feedback or "", "studentFeedback": v.student_feedback or "",
        "safetyIssue": v.safety_issue or "", "rectifyRequire": v.rectify_require or "",
        "rectifyDeadline": v.rectify_deadline or "",
        "rectifyStatus": v.rectify_status, "rectifyStatusLabel": RECTIFY_LABEL.get(v.rectify_status, v.rectify_status),
        "createdAt": _iso(v.created_at) or "",
    }


def _scope_ctx(user):
    from app.modules.internship.services.internship_service import _current_scope, _rec_in_scope
    return _current_scope(user), _rec_in_scope


def _validate_file(file_id):
    """附件 file_id 校验：为空放行；非空必须是本租户已存在文件，否则拒绝。"""
    fid = (file_id or "").strip()
    if not fid:
        return None
    from app.services import file_service
    if not file_service.get_file_meta(fid):
        raise AppException("VALIDATION_ERROR", "附件不存在或无权访问，请重新上传")
    return fid


def create(user, body) -> dict:
    b = body or {}
    iid = b.get("internshipId") or b.get("internId")
    if not iid:
        raise AppException("VALIDATION_ERROR", "缺少实习记录 internshipId")
    file_id = _validate_file(b.get("fileId"))
    scope, in_scope = _scope_ctx(user)
    with session() as db:
        rec = db.get(InternshipRecord, _as_id(iid))
        if not rec or rec.is_deleted or rec.tenant_id != _tid():
            raise not_found("实习记录不存在")
        stu = db.get(StudentProfile, rec.student_id)
        if not in_scope(scope, db, rec, stu):  # owner
            raise no_permission("只能对本人指导学生新增巡访记录")
        has_rectify = bool((b.get("safetyIssue") or "").strip() or (b.get("rectifyRequire") or "").strip())
        v = InternshipVisit(
            tenant_id=_tid(), internship_id=rec.id, student_id=rec.student_id,
            advisor_name=_op_name(user), enterprise_name=b.get("enterpriseName") or (rec.enterprise_name or None),
            visit_at=datetime.utcnow(), method=b.get("method") or "ONSITE",
            enterprise_feedback=b.get("enterpriseFeedback"), student_feedback=b.get("studentFeedback"),
            safety_issue=b.get("safetyIssue"), rectify_require=b.get("rectifyRequire"),
            rectify_deadline=b.get("rectifyDeadline"),
            rectify_status="PENDING" if has_rectify else "NONE",
            monthly_report=b.get("monthlyReport"), file_id=file_id)
        db.add(v); db.flush()
        _trail(db, v.id, "CREATE", {"method": v.method, "hasRectify": has_rectify},
               operator=_op_name(user))
        if has_rectify:
            from app.modules.internship.services import internship_todo_helper as ix_todo
            ix_todo.push_visit_rectify_todo(db, v, rec)
        db.commit()
        return {"id": str(v.id), "rectifyStatus": v.rectify_status}


def rectify_follow(user, visit_id, status, note="") -> dict:
    if status not in ("PENDING", "DONE"):
        raise AppException("VALIDATION_ERROR", "整改状态必须是 PENDING/DONE")
    if not (note or "").strip() or len(note.strip()) < 2:
        raise AppException("VALIDATION_ERROR", "整改跟进说明必填")
    scope, in_scope = _scope_ctx(user)
    with session() as db:
        v = _get(db, visit_id)
        rec, stu = _ctx(db, v)
        if not in_scope(scope, db, rec, stu):  # owner 级写校验
            raise no_permission("只能跟进本人指导学生的巡访整改")
        if v.rectify_status == "NONE":
            raise AppException("DATA_CONFLICT", "该巡访无整改要求，无需跟进")
        v.rectify_status = status
        v.version += 1
        _trail(db, v.id, f"RECTIFY_{status}", {"note": note.strip()}, operator=_op_name(user))
        if status == "DONE":
            from app.modules.internship.services import internship_todo_helper as ix_todo
            ix_todo.todo_done(db, biz_id=v.id, todo_type=ix_todo.TODO_VISIT_RECTIFY)
        elif status == "PENDING":
            from app.modules.internship.services import internship_todo_helper as ix_todo
            ix_todo.push_visit_rectify_todo(db, v, rec)
        db.commit()
        return {"id": str(v.id), "rectifyStatus": v.rectify_status}


def list_visits(page, page_size, keyword=None, rectify=None, batch_id=None, user=None) -> tuple[list[dict], int]:
    scope, in_scope = _scope_ctx(user)
    with session() as db:
        from app.modules.internship.services.internship_batch_context import batch_record_ids
        _, record_ids = batch_record_ids(db, batch_id)
        if not record_ids:
            return [], 0
        q = select(InternshipVisit).where(InternshipVisit.tenant_id == _tid(),
                                          InternshipVisit.is_deleted.is_(False),
                                          InternshipVisit.internship_id.in_(record_ids))
        if rectify:
            q = q.where(InternshipVisit.rectify_status == rectify)
        rows = db.scalars(q.order_by(InternshipVisit.id.desc())).all()
        items = []
        for v in rows:
            rec, stu = _ctx(db, v)
            if keyword and (not stu or keyword.strip() not in (stu.real_name or "")):
                continue
            if not in_scope(scope, db, rec, stu):
                continue
            items.append(_row(v, rec, stu))
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


def get_visit(vid, user=None) -> dict:
    scope, in_scope = _scope_ctx(user)
    with session() as db:
        v = _get(db, vid)
        rec, stu = _ctx(db, v)
        if not in_scope(scope, db, rec, stu):
            raise no_permission("该巡访记录不在你的数据范围内")
        trail = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == _tid(), InternshipAuditTrail.target_type == "VISIT",
            InternshipAuditTrail.target_id == v.id).order_by(InternshipAuditTrail.id)).all()
        from app.services import file_service
        return {**_row(v, rec, stu), "monthlyReport": v.monthly_report or "",
                "attachment": file_service.attachment_view(v.file_id),
                "auditTrail": [{"action": t.action, "operator": t.operator_name or "",
                                "detail": t.detail_json or {}, "occurredAt": _iso(t.occurred_at)}
                               for t in trail]}


def visit_stats(batch_id=None, user=None) -> dict:
    items, _ = list_visits(1, 100000, batch_id=batch_id, user=user)
    return {"totalVisits": len(items),
            "pendingRectify": sum(1 for item in items if item["rectifyStatus"] == "PENDING"),
            "doneRectify": sum(1 for item in items if item["rectifyStatus"] == "DONE"),
            "withSafetyIssue": sum(1 for item in items if item["safetyIssue"])}


def export_visits(keyword=None, batch_id=None, user=None) -> dict:
    from app.services import xlsx_util
    items, _ = list_visits(1, 100000, keyword=keyword, batch_id=batch_id, user=user)
    headers = ["学号", "姓名", "巡访教师", "企业", "巡访时间", "方式", "安全隐患", "整改要求",
               "整改截止", "整改状态"]
    rows = [[it["studentNo"], it["studentName"], it["advisorName"], it["enterpriseName"],
             it["visitAt"], it["methodLabel"], it["safetyIssue"], it["rectifyRequire"],
             it["rectifyDeadline"], it["rectifyStatusLabel"]] for it in items]
    wm = f"岗位实习中心·巡访记录台账 · 导出人：{_op_name(user)} · {datetime.now():%Y-%m-%d %H:%M} · 导出留痕"
    content = xlsx_util.build_ledger_xlsx("巡访记录台账", headers, rows, watermark=wm)
    return xlsx_util.pack_xlsx_result(content, "巡访记录台账.xlsx", len(items))
