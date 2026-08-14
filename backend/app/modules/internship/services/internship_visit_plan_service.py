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


def _resolved_values(p, body):
    """把 body 叠加到当前行上，算出应落库的字段值——不改动 ORM 实例。

    编辑走的是条件更新（版本+状态）。一旦这里先改了 ORM 实例，SQLAlchemy 的 autoflush 会在
    条件更新执行之前把改动无条件写进去：输家表面上拿到 409，数据其实已经被它盖掉了。
    """
    return {
        "batch_id": int(body["batchId"]) if body.get("batchId") else p.batch_id,
        "college_id": int(body["collegeId"]) if body.get("collegeId") else p.college_id,
        "enterprise_id": int(body["enterpriseId"]) if body.get("enterpriseId") else p.enterprise_id,
        "enterprise_name": (body.get("enterpriseName") or p.enterprise_name or "").strip() or None,
        "collaborators": (body.get("collaborators") or p.collaborators or "").strip() or None,
        "student_scope": (body.get("studentScope") or p.student_scope or "").strip() or None,
        "plan_date": (body.get("planDate") or p.plan_date or "").strip() or None,
        "time_window": (body.get("timeWindow") or p.time_window or "").strip() or None,
        "method": (body.get("method") or p.method or "ONSITE").upper(),
        "location": (body.get("location") or p.location or "").strip() or None,
        "objective": (body.get("objective") or p.objective or "").strip() or None,
    }


def _apply(p, body):
    """创建路径仍走 ORM 赋值：新行还没有并发对手，不需要条件更新。"""
    for key, value in _resolved_values(p, body).items():
        setattr(p, key, value)


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
    """编辑：与 transition() 同一套并发合同，避免两人同时改同一份计划互相覆盖。

    字段值由 _resolved_values() 纯计算得出，全程不碰 ORM 实例——否则 autoflush 会在条件更新
    执行前把改动无条件落库，输家拿到 409 的同时数据已经被它盖掉了。
    """
    from app.modules.internship.services.internship_version import (
        extract_expected_version, versioned_update,
    )

    with session() as db:
        p = _get(db, pid)
        if not _scope_ok(_scope(user), p, db):
            raise no_permission("不在当前数据范围内")
        if p.status not in ("DRAFT", "PUBLISHED"):
            raise AppException("DATA_CONFLICT", "进行中/已完成/已取消的计划不可编辑")
        body = body or {}
        client_version = extract_expected_version(body, required=False)
        current_status, current_version = p.status, int(p.version or 0)
        if client_version is not None and client_version != current_version:
            raise AppException("DATA_CONFLICT", "数据已被其他用户修改，请刷新后重试")
        scope = _scope(user)
        if scope.get("mode") == "SCOPED" and body.get("collegeId"):
            college_names = scope.get("collegeNames") or set()
            if college_names:
                from app.core.tenant_scoped import tenant_get
                from app.models import College
                col = tenant_get(db, College, int(body["collegeId"]))
                if not col or (col.college_name or "").strip() not in college_names:
                    raise no_permission("巡访计划学院不在你的数据范围内")
        values = _resolved_values(p, body)
        versioned_update(
            db, InternshipVisitPlan,
            entity_id=_as_id(pid), tenant_id=_tid(),
            expected_version=current_version, values=values,
            expected_status=current_status,
        )
        _trail(db, _as_id(pid), "UPDATE", {}, user)
        db.commit()
        p = _get(db, pid)
        return _row(p)


def transition(pid, action, body=None, user=None):
    """状态迁移：条件原子更新，两个教师同时操作只有一个能赢。

    原实现是「读 status → 校验 → 改 → version+1 → commit」，两人并发时会双双读到
    PUBLISHED、双双通过校验，后写覆盖先写（last-write-wins），version 虽然自增却没人比对。
    这里改为 UPDATE ... WHERE version=读到的版本 AND status=读到的状态：并发下只有一条能
    匹配，输家拿 DATA_CONFLICT。

    expectedVersion 仍是可选的：PC 端目前不传，强制要求会直接打断现有页面。客户端传了就
    额外校验它是否已过期（能更早地把「你看的是旧数据」告诉用户），不传则以服务端刚读到的
    版本为准——并发正确性由数据库条件更新保证，不依赖客户端是否配合。
    """
    from app.modules.internship.services.internship_version import (
        extract_expected_version, versioned_update,
    )

    action = (action or "").upper()
    if action not in _TRANSITIONS:
        raise AppException("VALIDATION_ERROR", "action 必须是 PUBLISH/START/COMPLETE/CANCEL")
    allowed_from, to = _TRANSITIONS[action]
    body = body or {}
    client_version = extract_expected_version(body, required=False)
    with session() as db:
        p = _get(db, pid)
        if not _scope_ok(_scope(user), p, db):
            raise no_permission("不在当前数据范围内")
        current_status, current_version = p.status, int(p.version or 0)
        if current_status not in allowed_from:
            raise AppException("DATA_CONFLICT", f"当前状态 {current_status} 不可执行 {action}")
        if client_version is not None and client_version != current_version:
            raise AppException("DATA_CONFLICT", "数据已被其他用户修改，请刷新后重试")

        values = {"status": to}
        if action == "CANCEL":
            reason = (body.get("reason") or "").strip()
            if len(reason) < 2:
                raise AppException("VALIDATION_ERROR", "取消原因不少于 2 个字符")
            values["cancel_reason"] = reason
        if action == "COMPLETE":
            values["completed_at"] = datetime.utcnow()
            if body.get("visitId"):
                values["visit_id"] = int(body["visitId"])

        versioned_update(
            db, InternshipVisitPlan,
            entity_id=p.id, tenant_id=_tid(),
            expected_version=current_version, values=values,
            expected_status=current_status,
        )
        _trail(db, p.id, action, {k: v for k, v in body.items() if k in ("reason", "visitId")}, user)
        db.commit()
        db.refresh(p)
        return _row(p)