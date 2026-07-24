"""毕业设计中心 · 指导过程记录服务。

时间线留痕 + 指导频次统计（供 GD-R06 指导不足预警使用）。记录不可篡改历史，撤销走软删+原因留痕。
隔离说明：不引用实习/迎新域文件。
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.models import (
    GraduationAuditTrail, GraduationGuidance, GraduationGuidancePlan, GraduationStudent,
)
from app.services.db_service import _iso, _tid, session
from app.modules.graduation.services.graduation_scope_service import accessible_student_ids, assert_student_access, can_access_student

METHOD_LABEL = {"ONLINE": "线上", "OFFLINE": "线下", "MANUAL": "手工"}
PLAN_STATUS_LABEL = {"PLANNED": "待签到", "CHECKED_IN": "已签到", "CANCELLED": "已取消"}


def _op() -> tuple[str, str]:
    u = get_current_user_ctx() or {}
    return u.get("realName") or "系统", u.get("roleName") or u.get("currentRoleCode") or ""


def _audit(db, bid, action, detail="", before="", after=""):
    n, r = _op()
    db.add(GraduationAuditTrail(tenant_id=_tid(), biz_type="GUIDANCE", biz_id=str(bid), action=action,
                                operator=n, role_name=r, detail=detail, before_val=before, after_val=after,
                                occurred_at=datetime.now(timezone.utc)))


def _stu(db, sid) -> GraduationStudent:
    s = db.get(GraduationStudent, int(sid))
    if not s or s.is_deleted or s.tenant_id != _tid():
        raise not_found("毕设学生不存在或不在当前数据范围内")
    return assert_student_access(db, s, "guidance")


def _row(g: GraduationGuidance, stu=None) -> dict:
    return {"id": str(g.id), "gdStudentId": str(g.gd_student_id),
            "studentName": stu.name if stu else "", "studentNo": stu.student_no if stu else "",
            "guidanceDate": _iso(g.guidance_date), "method": g.method,
            "methodLabel": METHOD_LABEL.get(g.method, g.method), "content": g.content or "",
            "issues": g.issues or "", "attachments": g.attachments_json or [],
            "createdAt": _iso(g.created_at)}


def list_guidance(page: int, page_size: int, gd_student_id=None, keyword=None) -> tuple[list[dict], int]:
    with session() as db:
        scope_ids = accessible_student_ids(db, _tid())
        q = select(GraduationGuidance).where(GraduationGuidance.tenant_id == _tid(),
                                              GraduationGuidance.is_deleted.is_(False),
                                              GraduationGuidance.gd_student_id.in_(scope_ids or [-1]))
        if gd_student_id:
            q = q.where(GraduationGuidance.gd_student_id == int(gd_student_id))
        total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
        rows = db.scalars(q.order_by(GraduationGuidance.id.desc())
                          .offset((max(1, page) - 1) * page_size).limit(page_size)).all()
        items = []
        for g in rows:
            stu = db.get(GraduationStudent, g.gd_student_id)
            if keyword and (not stu or keyword.strip() not in (stu.name or "")):
                continue
            items.append(_row(g, stu))
        return items, total


def create_guidance(gd_student_id, body: dict) -> dict:
    with session() as db:
        stu = _stu(db, gd_student_id)
        n, _ = _op()
        d = None
        if body.get("guidanceDate"):
            try:
                d = datetime.fromisoformat(str(body["guidanceDate"])[:19])
            except ValueError:
                d = None
        g = GraduationGuidance(
            tenant_id=_tid(), gd_student_id=stu.id, mentor_id=stu.mentor_id,
            guidance_date=d or datetime.now(timezone.utc), method=body.get("method") or "ONLINE",
            content=body.get("content"), issues=body.get("issues"),
            attachments_json=body.get("attachments") or [])
        db.add(g)
        db.flush()
        _audit(db, g.id, "新增指导记录", detail=f"{stu.name}/{n}")
        db.commit()
        return _row(g, stu)


def void_guidance(gid, reason: str) -> dict:
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "撤销原因必填且不少于 5 字")
    with session() as db:
        g = db.get(GraduationGuidance, int(gid))
        if not g or g.is_deleted or g.tenant_id != _tid():
            raise not_found("指导记录不存在")
        g.is_deleted = True
        g.void_reason = reason.strip()
        _audit(db, g.id, "撤销指导记录", reason.strip())
        db.commit()
        return {"id": str(g.id), "voided": True}


def guidance_count(gd_student_id) -> int:
    with session() as db:
        _stu(db, gd_student_id)
        return int(db.scalar(select(func.count()).select_from(GraduationGuidance).where(
            GraduationGuidance.tenant_id == _tid(), GraduationGuidance.gd_student_id == int(gd_student_id),
            GraduationGuidance.is_deleted.is_(False))) or 0)


def guidance_stats(threshold: int = 3, batch_id=None) -> dict:
    """按学生统计指导次数，标记低于阈值（GD-R06 指导不足预警）。"""
    with session() as db:
        scope_ids = set(accessible_student_ids(db, _tid(), batch_id=batch_id))
        students = db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.is_deleted.is_(False),
            GraduationStudent.record_status == "ACTIVE",
            GraduationStudent.id.in_(scope_ids or [-1]),
            GraduationStudent.stage.notin_(("TOPIC_SELECTING", "TASKBOOK_CONFIRM")))).all()
        students = [student for student in students if can_access_student(db, student)]
        insufficient = []
        total_count = 0
        for s in students:
            cnt = int(db.scalar(select(func.count()).select_from(GraduationGuidance).where(
                GraduationGuidance.tenant_id == _tid(), GraduationGuidance.gd_student_id == s.id,
                GraduationGuidance.is_deleted.is_(False))) or 0)
            total_count += cnt
            if cnt < threshold:
                insufficient.append({"gdStudentId": str(s.id), "studentName": s.name,
                                     "advisorName": s.advisor_name or "", "count": cnt})
        return {"threshold": threshold, "studentCount": len(students),
                "avgCount": round(total_count / len(students), 1) if students else 0,
                "insufficientCount": len(insufficient), "insufficientStudents": insufficient[:50],
                "batchId": str(batch_id) if batch_id else None}


# ═══════════ 指导计划 + 签到（P2 MVP） ═══════════

def _plan_row(p: GraduationGuidancePlan, stu=None) -> dict:
    return {
        "id": str(p.id),
        "gdStudentId": str(p.gd_student_id),
        "studentName": stu.name if stu else "",
        "studentNo": stu.student_no if stu else "",
        "mentorId": str(p.mentor_id) if p.mentor_id else "",
        "title": p.title,
        "planDate": _iso(p.plan_date),
        "content": p.content or "",
        "status": p.status,
        "statusLabel": PLAN_STATUS_LABEL.get(p.status, p.status),
        "checkedInAt": _iso(p.checked_in_at),
        "checkedInBy": p.checked_in_by or "",
        "checkinRole": p.checkin_role or "",
        "checkinNote": p.checkin_note or "",
        "checkinMethod": p.checkin_method or "",
        "checkinMethodLabel": METHOD_LABEL.get(p.checkin_method or "", p.checkin_method or ""),
        "createdAt": _iso(p.created_at),
    }


def list_plans(page: int, page_size: int, gd_student_id=None) -> tuple[list[dict], int]:
    with session() as db:
        scope_ids = accessible_student_ids(db, _tid())
        q = select(GraduationGuidancePlan).where(
            GraduationGuidancePlan.tenant_id == _tid(),
            GraduationGuidancePlan.is_deleted.is_(False),
            GraduationGuidancePlan.gd_student_id.in_(scope_ids or [-1]))
        if gd_student_id:
            q = q.where(GraduationGuidancePlan.gd_student_id == int(gd_student_id))
        total = int(db.scalar(select(func.count()).select_from(q.subquery())) or 0)
        rows = db.scalars(
            q.order_by(GraduationGuidancePlan.id.desc())
            .offset((max(1, page) - 1) * page_size).limit(page_size)
        ).all()
        items = []
        for p in rows:
            stu = db.get(GraduationStudent, p.gd_student_id)
            items.append(_plan_row(p, stu))
        return items, total


def create_plan(gd_student_id, body: dict) -> dict:
    title = (body.get("title") or "").strip()
    if len(title) < 2:
        raise AppException("VALIDATION_ERROR", "计划标题必填且不少于 2 字")
    with session() as db:
        stu = _stu(db, gd_student_id)
        plan_date = None
        raw = body.get("planDate")
        if raw:
            try:
                plan_date = datetime.fromisoformat(str(raw)[:19])
            except ValueError:
                plan_date = None
        p = GraduationGuidancePlan(
            tenant_id=_tid(), gd_student_id=stu.id, mentor_id=stu.mentor_id,
            title=title, plan_date=plan_date,
            content=(body.get("content") or "").strip() or None,
            status="PLANNED",
        )
        db.add(p)
        db.flush()
        _audit(db, p.id, "新增指导计划", detail=f"{stu.name}/{title}")
        db.commit()
        return _plan_row(p, stu)


def checkin_plan(plan_id, body: dict | None = None) -> dict:
    """学生本人或指导教师/有范围的教职工对计划条目签到。"""
    body = body or {}
    with session() as db:
        p = db.get(GraduationGuidancePlan, int(plan_id))
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("指导计划不存在")
        stu = _stu(db, p.gd_student_id)
        if p.status == "CANCELLED":
            raise AppException("DATA_CONFLICT", "计划已取消，无法签到")
        if p.status == "CHECKED_IN":
            raise AppException("DATA_CONFLICT", "该计划已签到，不可重复签到")
        u = get_current_user_ctx() or {}
        role = (u.get("currentRoleCode") or "").strip().upper()
        user_type = (u.get("userType") or "").strip().upper()
        is_student = user_type == "STUDENT" or role == "STUDENT"
        n, _ = _op()
        method = (body.get("method") or "MANUAL").strip().upper()
        if method not in METHOD_LABEL:
            method = "MANUAL"
        p.status = "CHECKED_IN"
        p.checked_in_at = datetime.now(timezone.utc)
        p.checked_in_by = n
        p.checkin_role = "STUDENT" if is_student else ("MENTOR" if role in {"GD_MENTOR", "COUNSELOR"} else "STAFF")
        p.checkin_note = (body.get("note") or "").strip() or None
        p.checkin_method = method
        _audit(db, p.id, "指导计划签到", detail=f"{stu.name}/{p.checkin_role}/{n}")
        db.commit()
        return _plan_row(p, stu)


def cancel_plan(plan_id, reason: str) -> dict:
    if not reason or len(reason.strip()) < 5:
        raise AppException("VALIDATION_ERROR", "取消原因必填且不少于 5 字")
    with session() as db:
        p = db.get(GraduationGuidancePlan, int(plan_id))
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("指导计划不存在")
        stu = _stu(db, p.gd_student_id)
        if p.status == "CHECKED_IN":
            raise AppException("DATA_CONFLICT", "已签到计划不可取消，请保留留痕")
        if p.status == "CANCELLED":
            raise AppException("DATA_CONFLICT", "计划已取消")
        p.status = "CANCELLED"
        p.void_reason = reason.strip()
        p.is_deleted = True
        _audit(db, p.id, "取消指导计划", reason.strip())
        db.commit()
        return {"id": str(p.id), "cancelled": True}
