"""班级辅导员责任关系：真实用户绑定、交接、历史与工作量汇总。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.core.exceptions import AppException, check_version, not_found
from app.services.affairs_dashboard_service import _allowed_class_ids, _audit, _class_in_scope_or_403
from app.services.db_service import _iso, _tid, session

_DUTY_TYPES = {"PRIMARY", "CO", "TEMP"}
_STATUSES = {"ACTIVE", "ENDED"}


def _actor_id(user) -> int | None:
    try:
        return int((user or {}).get("userId") or 0) or None
    except (TypeError, ValueError):
        return None


def _dt(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value), fmt)
        except ValueError:
            pass
    raise AppException("VALIDATION_ERROR", "日期格式应为 YYYY-MM-DD 或 ISO 日期时间")


def _active_user(db, user_id):
    from app.models import User
    u = db.get(User, int(user_id))
    if not u or u.tenant_id != _tid() or u.is_deleted or u.status != "ACTIVE":
        raise AppException("VALIDATION_ERROR", "辅导员不存在、已离职或不在当前租户")
    return u


def _row(db, x, classes=None, users=None, student_counts=None):
    from app.models import SchoolClass, StudentProfile, User
    classes = classes if classes is not None else {}
    users = users if users is not None else {}
    student_counts = student_counts if student_counts is not None else {}
    c = classes.get(x.class_id)
    if c is None:
        c = db.get(SchoolClass, x.class_id)
    u = users.get(x.user_id)
    if u is None:
        u = db.get(User, x.user_id)
    count = student_counts.get(x.class_id)
    if count is None:
        count = db.scalar(select(func.count()).select_from(StudentProfile).where(
            StudentProfile.tenant_id == _tid(), StudentProfile.class_id == x.class_id,
            StudentProfile.is_deleted.is_(False))) or 0
    return {
        "id": str(x.id), "classId": str(x.class_id), "className": c.class_name if c else "",
        "userId": str(x.user_id), "counselorName": u.real_name if u else "",
        "studentCount": count, "dutyType": x.duty_type, "status": x.status,
        "effectiveFrom": _iso(x.effective_from), "effectiveTo": _iso(x.effective_to),
        "reason": x.reason or "", "handoverFromUserId": str(x.handover_from_user_id or ""),
        "version": x.version, "createdAt": _iso(x.created_at), "updatedAt": _iso(x.updated_at),
    }


def _visible_classes(db, user):
    allowed, scope = _allowed_class_ids(db, user)
    return allowed, scope


def list_assignments(user, class_id=None, user_id=None, status=None, vacancy_only=False,
                     page=1, page_size=20):
    from app.models import AffairsCounselorAssignment, SchoolClass, StudentProfile, User
    if status and status not in _STATUSES:
        raise AppException("VALIDATION_ERROR", "状态仅支持 ACTIVE 或 ENDED")
    with session() as db:
        allowed, _ = _visible_classes(db, user)
        if class_id:
            _class_in_scope_or_403(db, class_id, user)
        if vacancy_only:
            return _vacancy_rows(db, allowed, page, page_size)
        q = select(AffairsCounselorAssignment).where(
            AffairsCounselorAssignment.tenant_id == _tid(),
            AffairsCounselorAssignment.is_deleted.is_(False))
        if allowed is not None:
            q = q.where(AffairsCounselorAssignment.class_id.in_(allowed or {-1}))
        if class_id:
            q = q.where(AffairsCounselorAssignment.class_id == int(class_id))
        if user_id:
            q = q.where(AffairsCounselorAssignment.user_id == int(user_id))
        if status:
            q = q.where(AffairsCounselorAssignment.status == status)
        rows = db.scalars(q.order_by(AffairsCounselorAssignment.class_id,
                                     AffairsCounselorAssignment.status,
                                     AffairsCounselorAssignment.id.desc())).all()
        class_ids, user_ids = {x.class_id for x in rows}, {x.user_id for x in rows}
        classes = {x.id: x for x in db.scalars(select(SchoolClass).where(SchoolClass.id.in_(class_ids))).all()} if class_ids else {}
        users = {x.id: x for x in db.scalars(select(User).where(User.id.in_(user_ids))).all()} if user_ids else {}
        counts = dict(db.execute(select(StudentProfile.class_id, func.count()).where(
            StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
            StudentProfile.class_id.in_(class_ids or {-1})).group_by(StudentProfile.class_id)).all())
        out = [_row(db, x, classes, users, counts) for x in rows]
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total


def _vacancy_rows(db, allowed, page, page_size):
    from app.models import AffairsCounselorAssignment, SchoolClass, StudentProfile
    q = select(SchoolClass).where(SchoolClass.tenant_id == _tid(),
                                  SchoolClass.is_deleted.is_(False),
                                  SchoolClass.status == "ACTIVE")
    if allowed is not None:
        q = q.where(SchoolClass.id.in_(allowed or {-1}))
    classes = db.scalars(q.order_by(SchoolClass.class_name)).all()
    primary_ids = set(db.scalars(select(AffairsCounselorAssignment.class_id).where(
        AffairsCounselorAssignment.tenant_id == _tid(), AffairsCounselorAssignment.is_deleted.is_(False),
        AffairsCounselorAssignment.status == "ACTIVE", AffairsCounselorAssignment.duty_type == "PRIMARY")).all())
    vacant = [c for c in classes if c.id not in primary_ids]
    ids = {c.id for c in vacant}
    counts = dict(db.execute(select(StudentProfile.class_id, func.count()).where(
        StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
        StudentProfile.class_id.in_(ids or {-1})).group_by(StudentProfile.class_id)).all())
    out = [{"classId": str(c.id), "className": c.class_name, "studentCount": counts.get(c.id, 0),
            "status": "VACANT"} for c in vacant]
    total, start = len(out), (max(1, page) - 1) * page_size
    return out[start:start + page_size], total


def vacancies(user):
    with session() as db:
        allowed, _ = _visible_classes(db, user)
        items, total = _vacancy_rows(db, allowed, 1, 10000)
        return {"items": items, "total": total}


def list_counselor_ledger(user, page=1, page_size=20):
    from app.models import AffairsCounselorAssignment, StudentProfile, User
    with session() as db:
        allowed, _ = _visible_classes(db, user)
        q = select(AffairsCounselorAssignment).where(
            AffairsCounselorAssignment.tenant_id == _tid(), AffairsCounselorAssignment.is_deleted.is_(False),
            AffairsCounselorAssignment.status == "ACTIVE")
        if allowed is not None:
            q = q.where(AffairsCounselorAssignment.class_id.in_(allowed or {-1}))
        assignments = db.scalars(q).all()
        class_ids = {x.class_id for x in assignments}
        counts = dict(db.execute(select(StudentProfile.class_id, func.count()).where(
            StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
            StudentProfile.class_id.in_(class_ids or {-1})).group_by(StudentProfile.class_id)).all())
        users = {u.id: u for u in db.scalars(select(User).where(
            User.tenant_id == _tid(), User.id.in_({x.user_id for x in assignments} or {-1}))).all()}
        grouped = {}
        for x in assignments:
            item = grouped.setdefault(x.user_id, {"userId": str(x.user_id),
                "name": users.get(x.user_id).real_name if users.get(x.user_id) else "",
                "classIds": set(), "studentCount": 0, "primaryCount": 0, "tempCount": 0})
            if x.class_id not in item["classIds"]:
                item["classIds"].add(x.class_id)
                item["studentCount"] += counts.get(x.class_id, 0)
            item["primaryCount"] += int(x.duty_type == "PRIMARY")
            item["tempCount"] += int(x.duty_type == "TEMP")
        out = [{"userId": x["userId"], "name": x["name"], "classCount": len(x["classIds"]),
                "studentCount": x["studentCount"], "primaryCount": x["primaryCount"],
                "tempCount": x["tempCount"]} for x in grouped.values()]
        out.sort(key=lambda x: (-x["studentCount"], x["name"]))
        total, start = len(out), (max(1, page) - 1) * page_size
        return out[start:start + page_size], total


def _end(db, assignment, reason, actor_id):
    assignment.status, assignment.effective_to = "ENDED", datetime.utcnow()
    assignment.reason = reason or assignment.reason
    assignment.updated_by, assignment.version = actor_id, assignment.version + 1


def assign(user, class_id, user_id, duty_type, effective_from=None, effective_to=None, reason=""):
    from app.models import AffairsCounselorAssignment
    duty_type = (duty_type or "").upper()
    if duty_type not in _DUTY_TYPES:
        raise AppException("VALIDATION_ERROR", "责任类型仅支持 PRIMARY、CO、TEMP")
    start, end = _dt(effective_from) or datetime.utcnow(), _dt(effective_to)
    if duty_type == "TEMP" and not end:
        raise AppException("VALIDATION_ERROR", "临时代班必须填写有效截止时间")
    if end and end < start:
        raise AppException("VALIDATION_ERROR", "有效截止时间不能早于开始时间")
    with session() as db:
        c = _class_in_scope_or_403(db, class_id, user)
        _active_user(db, user_id)
        actor = _actor_id(user)
        if duty_type == "PRIMARY":
            old = db.scalars(select(AffairsCounselorAssignment).where(
                AffairsCounselorAssignment.tenant_id == _tid(), AffairsCounselorAssignment.class_id == c.id,
                AffairsCounselorAssignment.duty_type == "PRIMARY", AffairsCounselorAssignment.status == "ACTIVE",
                AffairsCounselorAssignment.is_deleted.is_(False))).all()
            for item in old:
                _end(db, item, reason or "主辅导员调整", actor)
            c.counselor_id, c.updated_by = int(user_id), actor
        x = AffairsCounselorAssignment(tenant_id=_tid(), class_id=c.id, user_id=int(user_id),
            duty_type=duty_type, status="ACTIVE", effective_from=start, effective_to=end,
            reason=(reason or None), created_by=actor, updated_by=actor)
        db.add(x); db.flush()
        _audit(db, "COUNSELOR_ASSIGN", x.id, "ASSIGN", f"class={c.id},user={user_id},duty={duty_type}")
        db.commit(); db.refresh(x)
        return _row(db, x)


def handover(user, class_id, from_user_id, to_user_id, reason, version):
    from app.models import AffairsCounselorAssignment
    if not (reason or "").strip():
        raise AppException("VALIDATION_ERROR", "交接原因必填")
    if int(from_user_id) == int(to_user_id):
        raise AppException("VALIDATION_ERROR", "交接双方不能是同一辅导员")
    with session() as db:
        c = _class_in_scope_or_403(db, class_id, user)
        _active_user(db, to_user_id)
        from_rows = db.scalars(select(AffairsCounselorAssignment).where(
            AffairsCounselorAssignment.tenant_id == _tid(), AffairsCounselorAssignment.class_id == c.id,
            AffairsCounselorAssignment.user_id == int(from_user_id), AffairsCounselorAssignment.status == "ACTIVE",
            AffairsCounselorAssignment.is_deleted.is_(False)).order_by(
                AffairsCounselorAssignment.duty_type == "PRIMARY")).all()
        if not from_rows:
            raise not_found("原辅导员没有有效责任关系")
        current = next((x for x in from_rows if x.duty_type == "PRIMARY"), from_rows[0])
        check_version(current.version, version)
        actor = _actor_id(user)
        for x in from_rows:
            _end(db, x, reason, actor)
        for x in db.scalars(select(AffairsCounselorAssignment).where(
            AffairsCounselorAssignment.tenant_id == _tid(), AffairsCounselorAssignment.class_id == c.id,
            AffairsCounselorAssignment.duty_type == "PRIMARY", AffairsCounselorAssignment.status == "ACTIVE",
            AffairsCounselorAssignment.user_id != int(from_user_id),
            AffairsCounselorAssignment.is_deleted.is_(False))).all():
            _end(db, x, "主辅导员交接", actor)
        x = AffairsCounselorAssignment(tenant_id=_tid(), class_id=c.id, user_id=int(to_user_id),
            duty_type="PRIMARY", status="ACTIVE", effective_from=datetime.utcnow(), reason=reason.strip(),
            handover_from_user_id=int(from_user_id), created_by=actor, updated_by=actor)
        c.counselor_id, c.updated_by = int(to_user_id), actor
        db.add(x); db.flush()
        _audit(db, "COUNSELOR_ASSIGN", x.id, "HANDOVER",
               f"class={c.id},from={from_user_id},to={to_user_id},reason={reason.strip()}")
        db.commit(); db.refresh(x)
        return _row(db, x)


def end_assignment(user, assignment_id, reason, version):
    from app.models import AffairsCounselorAssignment, SchoolClass
    if not (reason or "").strip():
        raise AppException("VALIDATION_ERROR", "结束责任关系必须填写原因")
    with session() as db:
        x = db.get(AffairsCounselorAssignment, int(assignment_id))
        if not x or x.tenant_id != _tid() or x.is_deleted:
            raise not_found("辅导员责任关系不存在")
        c = _class_in_scope_or_403(db, x.class_id, user)
        if x.status != "ACTIVE":
            raise AppException("DATA_CONFLICT", "责任关系已结束")
        check_version(x.version, version)
        _end(db, x, reason.strip(), _actor_id(user))
        if x.duty_type == "PRIMARY" and c.counselor_id == x.user_id:
            c.counselor_id, c.updated_by = None, _actor_id(user)
        _audit(db, "COUNSELOR_ASSIGN", x.id, "END", reason.strip())
        db.commit(); db.refresh(x)
        return _row(db, x)
