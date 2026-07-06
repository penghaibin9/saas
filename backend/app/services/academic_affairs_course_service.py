"""13B-P3 课程库（版本化字典 + 两级审核 ACAD_COURSE_APPROVE）。

字段与流程对齐成熟商业教务软件（正方/强智）：课程代码/性质/类别/学时构成/考核方式/开课单位/核心课/先修课。
两级审：DRAFT→(提交)COLLEGE_REVIEW→(学院审)ACADEMIC_REVIEW→(教务审)ENABLED；退回 RETURNED 可改重提。
已启用课程改动强制新版本（prev_version_id 链），历史引用锁旧版。
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _iso, _tid, session

CATEGORIES = ("PUBLIC_BASIC", "DISCIPLINE_BASIC", "MAJOR_CORE", "MAJOR_ELECTIVE", "PRACTICE")
NATURES = ("REQUIRED", "ELECTIVE", "LIMITED_ELECTIVE", "PUBLIC_ELECTIVE")
EXAM_MODES = ("EXAM", "CHECK")
_REVIEW = ("COLLEGE_REVIEW", "ACADEMIC_REVIEW")

L_CAT = {"PUBLIC_BASIC": "公共基础", "DISCIPLINE_BASIC": "学科基础", "MAJOR_CORE": "专业核心",
         "MAJOR_ELECTIVE": "专业选修", "PRACTICE": "集中实践"}
L_NAT = {"REQUIRED": "必修", "ELECTIVE": "选修", "LIMITED_ELECTIVE": "限选", "PUBLIC_ELECTIVE": "公选"}


def _op():
    u = get_current_user_ctx() or {}
    return (u.get("realName") or "系统"), (u.get("currentRoleCode") or ""), str(u.get("userId") or "")


def _audit(db, biz_id, action, detail=""):
    from app.models import AffairsAuditTrail
    n, r, uid = _op()
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type="AA_COURSE", biz_id=int(biz_id) if biz_id else None,
                             action=action, operator=n or uid, role_name=r, detail=detail,
                             occurred_at=datetime.utcnow()))


def _row(c) -> dict:
    return {
        "courseId": str(c.id), "courseCode": c.course_code, "courseName": c.course_name,
        "courseNameEn": c.course_name_en or "", "category": c.category,
        "categoryLabel": L_CAT.get(c.category, c.category), "nature": c.nature,
        "natureLabel": L_NAT.get(c.nature, c.nature), "credit": float(c.credit or 0),
        "hoursTotal": c.hours_total, "hoursTheory": c.hours_theory, "hoursPractice": c.hours_practice,
        "hoursExperiment": c.hours_experiment, "hoursComputer": c.hours_computer,
        "examMode": c.exam_mode, "ownerCollegeId": str(c.owner_college_id or ""),
        "isCore": bool(c.is_core), "version": c.version, "status": c.status,
        "prerequisiteCodes": json.loads(c.prerequisite_codes_json) if c.prerequisite_codes_json else [],
    }


def _validate(body):
    if (body.category or "MAJOR_CORE") not in CATEGORIES:
        raise AppException("VALIDATION_ERROR", "课程类别非法")
    if (body.nature or "REQUIRED") not in NATURES:
        raise AppException("VALIDATION_ERROR", "课程性质非法")
    if (body.examMode or "EXAM") not in EXAM_MODES:
        raise AppException("VALIDATION_ERROR", "考核方式非法")
    # 学时构成校验（真实：分项学时之和应≈总学时）
    parts = [getattr(body, k, None) or 0 for k in ("hoursTheory", "hoursPractice", "hoursExperiment", "hoursComputer")]
    if body.hoursTotal and sum(parts) and sum(parts) != body.hoursTotal:
        raise AppException("VALIDATION_ERROR", f"分项学时之和({sum(parts)})≠总学时({body.hoursTotal})")


def _apply_fields(c, body):
    c.course_name = body.courseName
    c.course_name_en = getattr(body, "courseNameEn", None)
    c.category = body.category or "MAJOR_CORE"
    c.nature = body.nature or "REQUIRED"
    c.credit = body.credit or 0
    c.hours_total = getattr(body, "hoursTotal", None)
    c.hours_theory = getattr(body, "hoursTheory", None)
    c.hours_practice = getattr(body, "hoursPractice", None)
    c.hours_experiment = getattr(body, "hoursExperiment", None)
    c.hours_computer = getattr(body, "hoursComputer", None)
    c.exam_mode = body.examMode or "EXAM"
    c.owner_college_id = int(body.ownerCollegeId) if getattr(body, "ownerCollegeId", None) else None
    c.is_core = bool(getattr(body, "isCore", False))
    c.prerequisite_codes_json = json.dumps(getattr(body, "prerequisiteCodes", []) or [], ensure_ascii=False)


def create_course(body, user) -> dict:
    _validate(body)
    with session() as db:
        from app.models import AaCourse
        # 同代码同版本查重
        dup = db.scalars(select(AaCourse).where(
            AaCourse.tenant_id == _tid(), AaCourse.course_code == body.courseCode,
            AaCourse.status != "DISABLED", AaCourse.is_deleted.is_(False))).first()
        if dup:
            raise AppException("DATA_CONFLICT", "该课程代码已存在有效课程")
        c = AaCourse(tenant_id=_tid(), course_code=body.courseCode, credit=0, version=1, status="DRAFT")
        _apply_fields(c, body)
        db.add(c)
        db.flush()
        _audit(db, c.id, "CREATE", body.courseCode)
        db.commit()
        db.refresh(c)
        return _row(c)


def update_course(course_id, user, body) -> dict:
    """编制态(DRAFT/RETURNED)直接改；已启用(ENABLED)改动强制新版本。"""
    _validate(body)
    with session() as db:
        from app.models import AaCourse
        c = db.get(AaCourse, int(course_id))
        if not c or c.is_deleted or c.tenant_id != _tid():
            raise not_found("课程不存在")
        if c.status in ("DRAFT", "RETURNED"):
            _apply_fields(c, body)
            _audit(db, c.id, "UPDATE")
            db.commit()
            db.refresh(c)
            return _row(c)
        if c.status == "ENABLED":
            # 强制新版本（历史引用锁旧版）
            nv = AaCourse(tenant_id=_tid(), course_code=c.course_code, credit=0,
                          version=c.version + 1, prev_version_id=c.id, status="DRAFT")
            _apply_fields(nv, body)
            db.add(nv)
            db.flush()
            _audit(db, nv.id, "NEW_VERSION", f"v{c.version}->v{nv.version}")
            db.commit()
            db.refresh(nv)
            return _row(nv)
        raise AppException("DATA_CONFLICT", "审核中的课程不可编辑")


def submit_course(course_id, user) -> dict:
    with session() as db:
        from app.models import AaCourse
        c = db.get(AaCourse, int(course_id))
        if not c or c.is_deleted or c.tenant_id != _tid():
            raise not_found("课程不存在")
        if c.status not in ("DRAFT", "RETURNED"):
            raise AppException("APPROVAL_VERSION_CONFLICT", "仅草稿/退回课程可提交审核")
        c.status, c.version = "COLLEGE_REVIEW", c.version
        _audit(db, c.id, "SUBMIT")
        db.commit()
        db.refresh(c)
        return _row(c)


def review_course(course_id, user, action, reason="") -> dict:
    action = (action or "").upper()
    with session() as db:
        from app.models import AaCourse
        c = db.get(AaCourse, int(course_id))
        if not c or c.is_deleted or c.tenant_id != _tid():
            raise not_found("课程不存在")
        if c.status not in _REVIEW:
            raise AppException("APPROVAL_VERSION_CONFLICT", "该课程当前状态不可审核")
        if action == "APPROVE":
            c.status = "ACADEMIC_REVIEW" if c.status == "COLLEGE_REVIEW" else "ENABLED"
            _audit(db, c.id, "APPROVE", f"->{c.status}")
        elif action in ("REJECT", "RETURN"):
            if not reason or len(reason.strip()) < 5:
                raise AppException("VALIDATION_ERROR", "退回原因必填且不少于 5 字")
            c.status = "RETURNED"
            _audit(db, c.id, "RETURNED", reason.strip())
        else:
            raise AppException("VALIDATION_ERROR", "无效操作")
        db.commit()
        db.refresh(c)
        return _row(c)


def set_course_status(course_id, user, enable: bool) -> dict:
    with session() as db:
        from app.models import AaCourse
        c = db.get(AaCourse, int(course_id))
        if not c or c.is_deleted or c.tenant_id != _tid():
            raise not_found("课程不存在")
        if enable and c.status == "DISABLED":
            c.status = "ENABLED"
        elif not enable and c.status == "ENABLED":
            c.status = "DISABLED"
        _audit(db, c.id, "ENABLE" if enable else "DISABLE")
        db.commit()
        db.refresh(c)
        return _row(c)


def get_course(course_id, user) -> dict:
    with session() as db:
        from app.models import AaCourse
        c = db.get(AaCourse, int(course_id))
        if not c or c.is_deleted or c.tenant_id != _tid():
            raise not_found("课程不存在")
        return _row(c)


def list_courses(user, keyword=None, category=None, nature=None, status=None, page=1, page_size=20):
    from app.models import AaCourse
    with session() as db:
        conds = [AaCourse.tenant_id == _tid(), AaCourse.is_deleted.is_(False)]
        if category:
            conds.append(AaCourse.category == category)
        if nature:
            conds.append(AaCourse.nature == nature)
        if status:
            conds.append(AaCourse.status == status)
        rows = db.scalars(select(AaCourse).where(*conds).order_by(AaCourse.id.desc())).all()
        out = []
        for c in rows:
            if keyword and keyword not in (c.course_name or "") and keyword not in (c.course_code or ""):
                continue
            out.append(_row(c))
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total
