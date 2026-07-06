"""13B-P2 培养方案编制骨架（建/编/列 + 课程明细）。审批发布(两审→PUBLISHED→绑年级)留 P3。"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _iso, _tid, session


def _op():
    u = get_current_user_ctx() or {}
    return (u.get("realName") or "系统"), (u.get("currentRoleCode") or ""), str(u.get("userId") or "")


def _audit(db, biz_id, action, detail=""):
    from app.models import AffairsAuditTrail
    n, r, uid = _op()
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type="AA_PROGRAM", biz_id=int(biz_id) if biz_id else None,
                             action=action, operator=n or uid, role_name=r, detail=detail,
                             occurred_at=datetime.utcnow()))


def _row(p) -> dict:
    return {"programId": str(p.id), "programName": p.program_name, "majorId": str(p.major_id or ""),
            "gradeYear": p.grade_year or "", "totalCredits": p.total_credits, "version": p.version,
            "status": p.status}


def create_program(body, user) -> dict:
    with session() as db:
        from app.models import AaProgram
        p = AaProgram(tenant_id=_tid(), program_name=body.programName,
                      major_id=(int(body.majorId) if getattr(body, "majorId", None) else None),
                      grade_year=getattr(body, "gradeYear", None),
                      total_credits=getattr(body, "totalCredits", None),
                      requirement_json=json.dumps(getattr(body, "requirement", {}) or {}, ensure_ascii=False),
                      version=1, status="DRAFT")
        db.add(p)
        db.flush()
        _audit(db, p.id, "CREATE", body.programName)
        db.commit()
        db.refresh(p)
        return _row(p)


def update_program(program_id, user, body) -> dict:
    with session() as db:
        from app.models import AaProgram
        p = db.get(AaProgram, int(program_id))
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("培养方案不存在")
        if p.status not in ("DRAFT", "RETURNED"):
            raise AppException("DATA_CONFLICT", "已进入审批/发布的方案不可直接编辑（发布后改动强制新版本，P3）")
        if getattr(body, "programName", None):
            p.program_name = body.programName
        if getattr(body, "totalCredits", None) is not None:
            p.total_credits = body.totalCredits
        if getattr(body, "requirement", None) is not None:
            p.requirement_json = json.dumps(body.requirement, ensure_ascii=False)
        p.version += 0  # 编辑不升版本，发布后改动才强制新版本(P3)
        _audit(db, p.id, "UPDATE")
        db.commit()
        db.refresh(p)
        return _row(p)


def add_course(program_id, user, body) -> dict:
    with session() as db:
        from app.models import AaProgram, AaProgramCourse
        p = db.get(AaProgram, int(program_id))
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("培养方案不存在")
        if p.status not in ("DRAFT", "RETURNED"):
            raise AppException("DATA_CONFLICT", "非编制态方案不可增删课程")
        c = AaProgramCourse(tenant_id=_tid(), program_id=p.id,
                            course_id=(int(body.courseId) if getattr(body, "courseId", None) else None),
                            course_name=getattr(body, "courseName", None),
                            open_term_no=getattr(body, "openTermNo", None),
                            module=getattr(body, "module", None),
                            credit_snapshot=getattr(body, "credit", None))
        db.add(c)
        db.flush()
        _audit(db, p.id, "ADD_COURSE", getattr(body, "courseName", "") or "")
        db.commit()
        return {"programCourseId": str(c.id), "programId": str(program_id),
                "courseName": c.course_name or ""}


def get_program(program_id, user) -> dict:
    with session() as db:
        from app.models import AaProgram, AaProgramCourse
        p = db.get(AaProgram, int(program_id))
        if not p or p.is_deleted or p.tenant_id != _tid():
            raise not_found("培养方案不存在")
        courses = db.scalars(select(AaProgramCourse).where(
            AaProgramCourse.tenant_id == _tid(), AaProgramCourse.program_id == p.id,
            AaProgramCourse.is_deleted.is_(False)).order_by(AaProgramCourse.open_term_no)).all()
        d = _row(p)
        d["requirement"] = json.loads(p.requirement_json) if p.requirement_json else {}
        d["courses"] = [{"programCourseId": str(c.id), "courseName": c.course_name or "",
                         "openTermNo": c.open_term_no, "module": c.module or "",
                         "credit": c.credit_snapshot} for c in courses]
        # 编制期学分校验提示（真实：课程学分合计 vs 毕业总学分）
        course_sum = sum(float(c.credit_snapshot or 0) for c in courses)
        d["creditSum"] = course_sum
        d["creditGap"] = (float(p.total_credits) - course_sum) if p.total_credits else None
        return d


def list_programs(user, major_id=None, status=None, page=1, page_size=20):
    from app.models import AaProgram
    with session() as db:
        conds = [AaProgram.tenant_id == _tid(), AaProgram.is_deleted.is_(False)]
        if major_id:
            conds.append(AaProgram.major_id == int(major_id))
        if status:
            conds.append(AaProgram.status == status)
        rows = db.scalars(select(AaProgram).where(*conds).order_by(AaProgram.id.desc())).all()
        out = [_row(p) for p in rows]
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total
