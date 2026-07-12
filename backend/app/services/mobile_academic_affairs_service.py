"""13B-P7 多端收口：教务中心学生自视图 + 教师课表（mobile 前缀）。

学生端本人只读：我的课表(最新已发布批次·按行政班)/我的成绩单/我的学籍+异动/我的毕业进度；
学生唯一写入口=异动申请(本人)。教师端：我的课表。全部经 resolve_student/身份解析，只见本人。
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.context import get_current_user_ctx
from app.core.exceptions import no_permission
from app.services.db_service import _iso, _tid, session
from app.services.mobile_student_service import _require_student, resolve_student


def _me(db, user):
    stu = resolve_student(db, _require_student(user))
    if not stu:
        raise no_permission("尚未建立你的学生档案")
    return stu


def _teacher_key(user) -> str:
    u = user or {}
    uid = str(u.get("userId") or "")
    ctx = str(u.get("activeContextId") or "")
    if uid.startswith("u_"):
        return uid[2:]
    if ctx.startswith("ctx_"):
        return ctx[4:]
    return uid or (u.get("realName") or "")


def _latest_published_batch(db):
    from app.models import AaScheduleBatch
    return db.scalars(select(AaScheduleBatch).where(
        AaScheduleBatch.tenant_id == _tid(), AaScheduleBatch.status == "PUBLISHED",
        AaScheduleBatch.is_deleted.is_(False)).order_by(AaScheduleBatch.id.desc())).first()


# ═══════════ 学生自视图 ═══════════

def schedule_my(user) -> dict:
    from app.modules.academic_affairs.services import academic_affairs_schedule_service as sched
    with session() as db:
        stu = _me(db, user)
        b = _latest_published_batch(db)
        sid = stu.id
    if not b:
        return {"batchId": "", "items": [], "note": "暂无已发布课表"}
    data = sched.student_view(b.id, user, sid)
    return {"batchId": str(b.id), **data}


def transcript_my(user) -> dict:
    from app.modules.academic_affairs.services import academic_affairs_grade_service as grade
    with session() as db:
        stu = _me(db, user)
        sid = stu.id
    return grade.transcript(sid, user)


def status_my(user) -> dict:
    """我的学籍状态 + 我的异动记录。"""
    from app.models import AaStatusChange
    from app.modules.academic_affairs.services.academic_affairs_status_service import is_enrolled
    with session() as db:
        stu = _me(db, user)
        rows = db.scalars(select(AaStatusChange).where(
            AaStatusChange.tenant_id == _tid(), AaStatusChange.student_id == stu.id,
            AaStatusChange.change_type.notin_(["ENROLL_REGISTER", "ANNUAL_REGISTER"]),
            AaStatusChange.is_deleted.is_(False)).order_by(AaStatusChange.id.desc())).all()
        return {
            "studentStatus": stu.student_status, "enrolled": is_enrolled(stu.student_status),
            "changes": [{"changeId": str(x.id), "changeType": x.change_type, "toStatus": x.to_status,
                         "status": x.status, "effectiveDate": _iso(x.effective_date)} for x in rows],
        }


def submit_status_change_my(user, body) -> dict:
    """学生本人发起异动申请（唯一学生写入口，只能给自己）。"""
    from app.modules.academic_affairs.services import academic_affairs_change_service as change
    with session() as db:
        stu = _me(db, user)
        sid = stu.id

    class _B:
        studentId = str(sid)
        changeType = getattr(body, "changeType", None) or (body.get("changeType") if isinstance(body, dict) else None)
        reason = getattr(body, "reason", None) or (body.get("reason") if isinstance(body, dict) else None)
        toMajorId = getattr(body, "toMajorId", None) or (body.get("toMajorId") if isinstance(body, dict) else None)
        toClassId = getattr(body, "toClassId", None) or (body.get("toClassId") if isinstance(body, dict) else None)
        toCollegeId = getattr(body, "toCollegeId", None) or (body.get("toCollegeId") if isinstance(body, dict) else None)
    return change.submit(_B(), user)


def graduation_progress_my(user) -> dict:
    """我的毕业进度（最新预审结果七项）。"""
    import json

    from app.models import AaGraduationAuditResult
    with session() as db:
        stu = _me(db, user)
        r = db.scalars(select(AaGraduationAuditResult).where(
            AaGraduationAuditResult.tenant_id == _tid(), AaGraduationAuditResult.student_id == stu.id,
            AaGraduationAuditResult.is_deleted.is_(False)).order_by(
            AaGraduationAuditResult.id.desc())).first()
        if not r:
            return {"hasAudit": False, "note": "尚未纳入毕业预审"}
        return {"hasAudit": True, "overall": r.overall, "conclusion": r.conclusion,
                "status": r.status,
                "items": json.loads(r.item_results_json) if r.item_results_json else []}


def exam_my(user) -> dict:
    """我的考试（V1 占位空态，考务未上线）。"""
    with session() as db:
        _me(db, user)
    return {"hasData": False, "note": "考试安排功能即将上线"}


# ═══════════ 教师端 ═══════════

def teacher_schedule_my(user) -> dict:
    from app.modules.academic_affairs.services import academic_affairs_schedule_service as sched
    if (user or {}).get("userType") == "STUDENT":
        raise no_permission("该接口仅教职工可用")
    with session() as db:
        b = _latest_published_batch(db)
    if not b:
        return {"batchId": "", "items": [], "note": "暂无已发布课表"}
    data = sched.teacher_view(b.id, user, _teacher_key(user))
    return {"batchId": str(b.id), **data}
