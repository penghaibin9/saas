"""巡访计划（07 整改方案 §5.2）。

谁在什么时间、以什么方式、巡访哪个企业和哪些学生；区别于巡访记录(InternshipVisit=执行证据)。
状态机 DRAFT→PUBLISHED→IN_PROGRESS→COMPLETED，旁路 CANCELLED/OVERDUE。
owner：指导教师只处理分派给本人(owner_name)的计划；管理端全校。临时巡访补录标 plan_type=UNPLANNED。
审计走 InternshipAuditTrail(target_type=VISIT_PLAN)。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, no_permission, not_found
from app.models import InternshipAuditTrail, InternshipVisitPlan
from app.services.db_service import _as_id, _iso, _tid, session

STATUS_LABEL = {"DRAFT": "草稿", "PUBLISHED": "已发布", "IN_PROGRESS": "进行中",
                "COMPLETED": "已完成", "CANCELLED": "已取消", "OVERDUE": "已逾期"}
# 状态迁移白名单：action → (allowed_from, to)
_TRANSITIONS = {
    "PUBLISH": (("DRAFT",), "PUBLISHED"),
    "START": (("PUBLISHED",), "IN_PROGRESS"),
    "COMPLETE": (("IN_PROGRESS",), "COMPLETED"),
    "CANCEL": (("DRAFT", "PUBLISHED", "IN_PROGRESS"), "CANCELLED"),
}


def _op_name(user=None):
    return (user or get_current_user_ctx() or {}).get("realName") or "系统"


def _trail(db, pid, action, detail=None, user=None):
    db.add(InternshipAuditTrail(
        tenant_id=_tid(), target_id=pid, target_type="VISIT_PLAN", action=action,
        operator_name=_op_name(user), detail_json=detail or {}, occurred_at=datetime.utcnow()))


def _get(db, pid):
    p = db.get(InternshipVisitPlan, _as_id(pid))
    if not p or p.is_deleted or p.tenant_id != _tid():
        raise not_found("巡访计划不存在或不在当前数据范围内")
    return p


def _scope(user):
    from app.modules.internship.services.internship_service import _current_scope
    return _current_scope(user)


def _scope_ok(scope, p, db=None):
    if scope.get("mode") != "SCOPED":
        return True
    names = scope.get("advisorNames") or set()
    if (p.owner_name or "") in names:
        return True
    collaborators = {n.strip() for n in (p.collaborators or "").split(",") if n.strip()}
    if collaborators & names:
        return True
    # 学院负责人：按计划上的 college_id 匹配学院名范围
    college_names = scope.get("collegeNames") or set()
    if college_names and p.college_id and db is not None:
        from app.models import College
        col = db.get(College, p.college_id)
        if col and (col.college_name or "").strip() in college_names:
            return True
    return False


def _row(p):
    return {
        "id": str(p.id), "batchId": str(p.batch_id) if p.batch_id else "",
        "collegeId": str(p.college_id) if p.college_id else "",
        "enterpriseId": str(p.enterprise_id) if p.enterprise_id else "",
        "enterpriseName": p.enterprise_name or "", "ownerName": p.owner_name or "",
        "collaborators": p.collaborators or "", "studentScope": p.student_scope or "",
        "planDate": p.plan_date or "", "timeWindow": p.time_window or "", "method": p.method,
        "location": p.location or "", "objective": p.objective or "",
        "status": p.status, "statusLabel": STATUS_LABEL.get(p.status, p.status),
        "planType": p.plan_type, "remindAt": _iso(p.remind_at) or "",
        "visitId": str(p.visit_id) if p.visit_id else "", "completedAt": _iso(p.completed_at) or "",
        "cancelReason": p.cancel_reason or "", "createdAt": _iso(p.created_at) or "",
    }


def list_visit_plans(page, page_size, status=None, batch_id=None, user=None):
    scope = _scope(user)
    with session() as db:
        q = select(InternshipVisitPlan).where(
            InternshipVisitPlan.tenant_id == _tid(), InternshipVisitPlan.is_deleted.is_(False))
        if status:
            q = q.where(InternshipVisitPlan.status == status)
        if batch_id:
            q = q.where(InternshipVisitPlan.batch_id == int(batch_id))
        rows = db.scalars(q.order_by(InternshipVisitPlan.id.desc())).all()
        items = [_row(p) for p in rows if _scope_ok(scope, p, db)]
        total = len(items)
        start = (max(1, page) - 1) * page_size
        return items[start:start + page_size], total


def get_visit_plan(pid, user=None):
    with session() as db:
        p = _get(db, pid)
        if not _scope_ok(_scope(user), p, db):
            raise no_permission("不在当前数据范围内")
        item = _row(p)
        trail = db.scalars(select(InternshipAuditTrail).where(
            InternshipAuditTrail.tenant_id == _tid(), InternshipAuditTrail.target_type == "VISIT_PLAN",
            InternshipAuditTrail.target_id == p.id).order_by(InternshipAuditTrail.id)).all()
        item["auditTrail"] = [{"action": t.action, "operator": t.operator_name or "",
                               "detail": t.detail_json or {}, "occurredAt": _iso(t.occurred_at) or ""}
                              for t in trail]
        return item


def _apply(p, body):
    p.batch_id = int(body["batchId"]) if body.get("batchId") else p.batch_id
    p.college_id = int(body["collegeId"]) if body.get("collegeId") else p.college_id
    p.enterprise_id = int(body["enterpriseId"]) if body.get("enterpriseId") else p.enterprise_id
    p.enterprise_name = (body.get("enterpriseName") or p.enterprise_name or "").strip() or None
    p.collaborators = (body.get("collaborators") or p.collaborators or "").strip() or None
    p.student_scope = (body.get("studentScope") or p.student_scope or "").strip() or None
    p.plan_date = (body.get("planDate") or p.plan_date or "").strip() or None
    p.time_window = (body.get("timeWindow") or p.time_window or "").strip() or None
    p.method = (body.get("method") or p.method or "ONSITE").upper()
    p.location = (body.get("location") or p.location or "").strip() or None
    p.objective = (body.get("objective") or p.objective or "").strip() or None


def create_visit_plan(body, user=None):
    body = body or {}
    if len((body.get("objective") or "").strip()) < 2 and not body.get("enterpriseName"):
        raise AppException("VALIDATION_ERROR", "请至少填写巡访企业或巡访目标")
    plan_type = (body.get("planType") or "VISIT").upper()
    with session() as db:
        scope = _scope(user)
        # 学院负责人不可跨院写 collegeId（与读侧 collegeNames 对齐）
        if scope.get("mode") == "SCOPED" and body.get("collegeId"):
            college_names = scope.get("collegeNames") or set()
            if college_names:
                from app.models import College
                col = db.get(College, int(body["collegeId"]))
                if not col or (col.college_name or "").strip() not in college_names:
                    raise no_permission("巡访计划学院不在你的数据范围内")
            elif not ((scope.get("advisorNames") or set()) & {(user or {}).get("realName") or ""}):
                # 无学院名范围且非本人指导名：拒绝指定外院
                pass
        p = InternshipVisitPlan(tenant_id=_tid(), owner_name=_op_name(user),
                                status="DRAFT", plan_type=plan_type,
                                created_by=None)
        _apply(p, body)
        # 创建后也必须可读（owner 本人或学院命中）
        if not _scope_ok(scope, p, db):
            # 草稿归属本人 owner_name，一般可通过；若 college 越权已在上拦截
            if scope.get("mode") == "SCOPED" and p.college_id:
                raise no_permission("巡访计划不在你的数据范围内")
        db.add(p)
        db.flush()
        _trail(db, p.id, "CREATE", {"planType": plan_type}, user)
        db.commit()
        return _row(p)


def update_visit_plan(pid, body, user=None):
    with session() as db:
        p = _get(db, pid)
        if not _scope_ok(_scope(user), p, db):
            raise no_permission("不在当前数据范围内")
        if p.status not in ("DRAFT", "PUBLISHED"):
            raise AppException("DATA_CONFLICT", "进行中/已完成/已取消的计划不可编辑")
        body = body or {}
        scope = _scope(user)
        if scope.get("mode") == "SCOPED" and body.get("collegeId"):
            college_names = scope.get("collegeNames") or set()
            if college_names:
                from app.models import College
                col = db.get(College, int(body["collegeId"]))
                if not col or (col.college_name or "").strip() not in college_names:
                    raise no_permission("巡访计划学院不在你的数据范围内")
        _apply(p, body)
        p.version = int(p.version or 0) + 1
        _trail(db, p.id, "UPDATE", {}, user)
        db.commit()
        return _row(p)


def transition(pid, action, body=None, user=None):
    action = (action or "").upper()
    if action not in _TRANSITIONS:
        raise AppException("VALIDATION_ERROR", "action 必须是 PUBLISH/START/COMPLETE/CANCEL")
    allowed_from, to = _TRANSITIONS[action]
    body = body or {}
    with session() as db:
        p = _get(db, pid)
        if not _scope_ok(_scope(user), p, db):
            raise no_permission("不在当前数据范围内")
        if p.status not in allowed_from:
            raise AppException("DATA_CONFLICT", f"当前状态 {p.status} 不可执行 {action}")
        if action == "CANCEL":
            reason = (body.get("reason") or "").strip()
            if len(reason) < 2:
                raise AppException("VALIDATION_ERROR", "取消原因不少于 2 个字符")
            p.cancel_reason = reason
        if action == "COMPLETE":
            p.completed_at = datetime.utcnow()
            if body.get("visitId"):
                p.visit_id = int(body["visitId"])
        p.status = to
        p.version = int(p.version or 0) + 1
        _trail(db, p.id, action, {k: v for k, v in body.items() if k in ("reason", "visitId")}, user)
        db.commit()
        return _row(p)
