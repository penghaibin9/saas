"""毕业设计中心 · 指导过程记录服务。

时间线留痕 + 指导频次统计（供 GD-R06 指导不足预警使用）。记录不可篡改历史，撤销走软删+原因留痕。
隔离说明：不引用实习/迎新域文件。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.models import GraduationAuditTrail, GraduationGuidance, GraduationStudent
from app.services.db_service import _iso, _tid, session
from app.services.graduation_scope_service import accessible_student_ids, assert_student_access, can_access_student

METHOD_LABEL = {"ONLINE": "线上", "OFFLINE": "线下"}


def _op() -> tuple[str, str]:
    u = get_current_user_ctx() or {}
    return u.get("realName") or "系统", u.get("roleName") or u.get("currentRoleCode") or ""


def _audit(db, bid, action, detail="", before="", after=""):
    n, r = _op()
    db.add(GraduationAuditTrail(tenant_id=_tid(), biz_type="GUIDANCE", biz_id=str(bid), action=action,
                                operator=n, role_name=r, detail=detail, before_val=before, after_val=after,
                                occurred_at=datetime.utcnow()))


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
            guidance_date=d or datetime.utcnow(), method=body.get("method") or "ONLINE",
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


def guidance_stats(threshold: int = 3) -> dict:
    """按学生统计指导次数，标记低于阈值（GD-R06 指导不足预警）。"""
    with session() as db:
        students = db.scalars(select(GraduationStudent).where(
            GraduationStudent.tenant_id == _tid(), GraduationStudent.is_deleted.is_(False),
            GraduationStudent.record_status == "ACTIVE",
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
                "insufficientCount": len(insufficient), "insufficientStudents": insufficient[:50]}
