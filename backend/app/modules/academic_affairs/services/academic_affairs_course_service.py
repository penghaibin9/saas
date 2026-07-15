"""13B-P3 课程库（版本化字典 + 两级审核 ACAD_COURSE_APPROVE）。

字段与流程对齐成熟商业教务软件（正方/强智）：课程代码/性质/类别/学时构成/考核方式/开课单位/核心课/先修课。
两级审：DRAFT→(提交)COLLEGE_REVIEW→(学院审)ACADEMIC_REVIEW→(教务审)ENABLED；退回 RETURNED 可改重提。
已启用课程改动强制新版本（prev_version_id 链），历史引用锁旧版。

Tier1 R2（新增课程/课程分类/课程性质/学分学时/课程负责人/课程停用）续工新增：
- 课程负责人（owner_teacher_id）读写接线——模型早已建列，此前 service 从未读写，属代码基线漂移修复；
- 课程简介（description）、适用专业（applicable_majors_json + is_all_major）——迁移 aa_course_lib_tier1_r2 补列；
  三者均为可选字段（新建/编辑时不强制，兼容既有教学任务/考务/选课等模块通过本端点铺底数据的调用方），
  一旦提供则做真实业务校验，不接受脏数据；
- 课程编号格式校验（G8：大写字母 1-4 位 + 数字 3-8 位）；
- 开课单位数据范围收敛：COLLEGE_ADMIN 只能在本学院开课单位下新建/编辑课程；
- 课程停用「被在途/已启用培养方案引用」限停校验 + 课程引用查询（供停用前提示）；
- 课程负责人检索只读端点，供前端 AppTeacherPicker 接真实在职教师数据。
"""
from __future__ import annotations

import json
import re
from datetime import datetime

from sqlalchemy import func, or_, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _iso, _tid, session

CATEGORIES = ("PUBLIC_BASIC", "DISCIPLINE_BASIC", "MAJOR_CORE", "MAJOR_ELECTIVE", "PRACTICE")
NATURES = ("REQUIRED", "ELECTIVE", "LIMITED_ELECTIVE", "PUBLIC_ELECTIVE")
EXAM_MODES = ("EXAM", "CHECK")
_REVIEW = ("COLLEGE_REVIEW", "ACADEMIC_REVIEW")
# 课程被下列状态的培养方案引用时不可停用（对齐培养方案状态机 DRAFT/COLLEGE_REVIEW/ACADEMIC_REVIEW/
# RETURNED/PUBLISHED/ENABLED/FROZEN/DISABLED —— 仅在途审核与已生效/冻结方案视为「活引用」）。
_LIVE_PROGRAM_STATUSES = ("COLLEGE_REVIEW", "ACADEMIC_REVIEW", "PUBLISHED", "ENABLED", "FROZEN")
_CODE_RE = re.compile(r"^[A-Z]{1,4}[0-9]{3,8}$")

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
        "ownerTeacherId": str(c.owner_teacher_id or ""),
        "isCore": bool(c.is_core), "version": c.version, "status": c.status,
        "description": c.description or "",
        "applicableMajors": json.loads(c.applicable_majors_json) if c.applicable_majors_json else [],
        "isAllMajor": bool(c.is_all_major),
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
    code = (getattr(body, "courseCode", None) or "").strip()
    if code and not _CODE_RE.match(code):
        raise AppException("VALIDATION_ERROR", "课程编号须为大写字母(1-4位)+数字(3-8位)，如 CS101")
    desc = getattr(body, "description", None)
    if desc and len(desc.strip()) > 500:
        raise AppException("VALIDATION_ERROR", "课程简介不超过 500 字")
    is_all = bool(getattr(body, "isAllMajor", False))
    majors = getattr(body, "applicableMajors", None) or []
    if is_all and majors:
        raise AppException("VALIDATION_ERROR", "全校通用不能与具体适用专业同时选择")


def _validate_owner_teacher(db, owner_teacher_id):
    """课程负责人须为本租户在职教师（未提供则跳过——兼容既有铺底数据调用方）。"""
    if not owner_teacher_id:
        return
    from app.models import User
    t = db.get(User, int(owner_teacher_id))
    if (not t or t.is_deleted or t.tenant_id != _tid() or t.user_type != "TEACHER" or t.status != "ACTIVE"):
        raise AppException("VALIDATION_ERROR", "课程负责人须为本校在职教师")


def _validate_majors(db, tenant_id, major_ids):
    """适用专业须为本租户启用专业（未提供则跳过）。"""
    if not major_ids:
        return
    from app.models import Major
    ids = [int(m) for m in major_ids]
    rows = db.scalars(select(Major).where(
        Major.tenant_id == tenant_id, Major.id.in_(ids), Major.is_deleted.is_(False))).all()
    if len(rows) != len(set(ids)):
        raise AppException("VALIDATION_ERROR", "适用专业包含不存在的专业")
    if any(r.status != "ACTIVE" for r in rows):
        raise AppException("VALIDATION_ERROR", "适用专业包含已停用专业")


def _check_college_scope(db, user, owner_college_id):
    """学院管理员只能在本学院开课单位下新增/编辑课程；教务处/超管不限（对齐数据范围）。"""
    role = (user.get("currentRoleCode") or "").upper() if user else ""
    if role != "COLLEGE_ADMIN":
        return
    from app.core.affairs_security import build_affairs_context, no_data_scope
    ctx = build_affairs_context(user, db)
    if ctx.scope_type != "COLLEGE" or not ctx.college_ids:
        return
    if not owner_college_id or int(owner_college_id) not in ctx.college_ids:
        raise no_data_scope("开课单位不在您的管理范围内")


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
    c.owner_teacher_id = int(body.ownerTeacherId) if getattr(body, "ownerTeacherId", None) else None
    c.is_core = bool(getattr(body, "isCore", False))
    c.description = (getattr(body, "description", None) or "").strip() or None
    c.is_all_major = bool(getattr(body, "isAllMajor", False))
    c.applicable_majors_json = json.dumps(getattr(body, "applicableMajors", []) or [], ensure_ascii=False)
    c.prerequisite_codes_json = json.dumps(getattr(body, "prerequisiteCodes", []) or [], ensure_ascii=False)


def create_course(body, user) -> dict:
    _validate(body)
    with session() as db:
        from app.models import AaCourse
        _validate_owner_teacher(db, getattr(body, "ownerTeacherId", None))
        _validate_majors(db, _tid(), getattr(body, "applicableMajors", None) or [])
        _check_college_scope(db, user, getattr(body, "ownerCollegeId", None))
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
        _validate_owner_teacher(db, getattr(body, "ownerTeacherId", None))
        _validate_majors(db, _tid(), getattr(body, "applicableMajors", None) or [])
        _check_college_scope(db, user, getattr(body, "ownerCollegeId", None))
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


def get_course_references(course_id, user) -> list[dict]:
    """课程被哪些培养方案引用（供停用前提示 / 详情页「查看引用情况」）。"""
    from app.models import AaCourse, AaProgram, AaProgramCourse
    with session() as db:
        c = db.get(AaCourse, int(course_id))
        if not c or c.is_deleted or c.tenant_id != _tid():
            raise not_found("课程不存在")
        rows = db.scalars(select(AaProgramCourse).where(
            AaProgramCourse.tenant_id == _tid(), AaProgramCourse.course_id == c.id,
            AaProgramCourse.is_deleted.is_(False))).all()
        out, seen = [], set()
        for r in rows:
            if r.program_id in seen:
                continue
            seen.add(r.program_id)
            p = db.get(AaProgram, r.program_id)
            if p and not p.is_deleted:
                out.append({"programId": str(p.id), "programName": p.program_name, "status": p.status})
        return out


def set_course_status(course_id, user, enable: bool) -> dict:
    with session() as db:
        from app.models import AaCourse, AaProgram, AaProgramCourse
        c = db.get(AaCourse, int(course_id))
        if not c or c.is_deleted or c.tenant_id != _tid():
            raise not_found("课程不存在")
        if enable and c.status == "DISABLED":
            c.status = "ENABLED"
            _audit(db, c.id, "ENABLE")
        elif not enable and c.status == "ENABLED":
            # 被引用限停：存在引用本课程的在途/生效培养方案时不可停用
            refs = db.scalars(select(AaProgramCourse.program_id).where(
                AaProgramCourse.tenant_id == _tid(), AaProgramCourse.course_id == c.id,
                AaProgramCourse.is_deleted.is_(False))).all()
            if refs:
                live = db.scalar(select(func.count(AaProgram.id)).where(
                    AaProgram.tenant_id == _tid(), AaProgram.id.in_(list(set(refs))),
                    AaProgram.status.in_(_LIVE_PROGRAM_STATUSES), AaProgram.is_deleted.is_(False)))
                if live:
                    raise AppException("VALIDATION_ERROR", "该课程仍被在途/已启用的培养方案引用，不能停用")
            c.status = "DISABLED"
            _audit(db, c.id, "DISABLE")
        else:
            raise AppException("DATA_CONFLICT", "仅已启用课程可停用、已停用课程可启用")
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


def list_courses(user, keyword=None, category=None, nature=None, status=None, page=1, page_size=20,
                 owner_teacher_id=None, owner_college_id=None):
    from app.models import AaCourse
    with session() as db:
        conds = [AaCourse.tenant_id == _tid(), AaCourse.is_deleted.is_(False)]
        if category:
            conds.append(AaCourse.category == category)
        if nature:
            conds.append(AaCourse.nature == nature)
        if status:
            conds.append(AaCourse.status == status)
        if owner_teacher_id:
            conds.append(AaCourse.owner_teacher_id == int(owner_teacher_id))
        if owner_college_id:
            conds.append(AaCourse.owner_college_id == int(owner_college_id))
        rows = db.scalars(select(AaCourse).where(*conds).order_by(AaCourse.id.desc())).all()
        out = []
        for c in rows:
            if keyword and keyword not in (c.course_name or "") and keyword not in (c.course_code or ""):
                continue
            out.append(_row(c))
        total = len(out)
        start = (max(1, page) - 1) * page_size
        return out[start:start + page_size], total


def search_teachers(keyword="", limit=20) -> list[dict]:
    """课程负责人检索：本租户在职教师（AppTeacherPicker.remoteSearch）。"""
    from app.models import User
    with session() as db:
        conds = [User.tenant_id == _tid(), User.is_deleted.is_(False),
                User.user_type == "TEACHER", User.status == "ACTIVE"]
        kw = (keyword or "").strip()
        if kw:
            conds.append(or_(User.real_name.contains(kw), User.login_name.contains(kw)))
        rows = db.scalars(select(User).where(*conds).order_by(User.real_name).limit(limit)).all()
        return [{"value": str(u.id), "label": f"{u.real_name}（{u.login_name}）"} for u in rows]
