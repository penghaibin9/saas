"""13B-R3 学院专业班级（组织架构）服务层。

组织三表复用冻结册 t_college / t_major / t_class（不建新表，R3 仅加列）。本服务提供：
- 学院 / 专业 / 行政班 CRUD（软删、乐观状态字段），教学秘书绑定；
- 年级（按 t_class.grade 聚合，非独立表）、组织树、组织统计（只读）；
- 教学班只读汇总（派生自 t_aa_teaching_task.teaching_class_code，无独立表）；
- 班级学生只读 + 班级调整（移动学生 class_id，单写入口 + 审计）；
- 组织变更审计（读 t_affairs_audit_trail，biz_type=AA_ORG_*）。

数据范围复用 app.core.affairs_security.build_affairs_context：
- TENANT_ALL（校管/教务处/校领导）→ 全租户；
- COLLEGE（学院管理员）→ 限授权学院及其下专业/班级；
- 其它/无授权 → fail-closed（列表空、写 403）。绝不回退看全租户。
写操作若目标学院不在范围内 → NO_DATA_SCOPE(403002)。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.core.affairs_security import build_affairs_context, no_data_scope
from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _mask_phone, _tid, session

_MAJOR_ENROLL = {"ENROLLING", "STOPPED"}
_CLASS_STATUS = {"NORMAL", "GRADUATED", "DISBANDED"}

# 06 专业方向：总开关（t_platform_config，config_type 独立于既有 FEATURES/PACKAGE 等控制面 KV，
# 不复用 platform_defaults.FEATURE_KEYS 整模块开关列表——那是粗粒度模块级且默认 True，
# 本开关要求默认关闭，业务政策待学校确认，故走独立 config_type，自成一体不影响其它平台配置）。
_MD_CFG_TYPE = "AA_FEATURE_TOGGLE"
_MD_CFG_KEY = "academicAffairs.majorDirection.enabled"
_DIRECTION_STATUS = {"ACTIVE", "DISABLED"}

# 08 班级调整申请单：类型与状态机
_ADJUST_TYPES = {"MERGE", "SPLIT", "DISBAND", "GRADUATE_CLEAR"}
_ADJUST_STATUS = {"DRAFT", "CHECKED", "EXECUTED", "CANCELLED"}
_ADJUST_CHECK_TTL_HOURS = 24


def _op():
    u = get_current_user_ctx() or {}
    return (u.get("realName") or "系统"), (u.get("currentRoleCode") or ""), str(u.get("userId") or "")


def _audit(db, biz_type, biz_id, action, detail="", before="", after=""):
    from app.models import AffairsAuditTrail
    n, r, uid = _op()
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type=biz_type, biz_id=int(biz_id) if biz_id else None,
                             action=action, operator=n or uid, role_name=r, detail=(detail or "")[:1000],
                             before_val=(before or "")[:1000] or None, after_val=(after or "")[:1000] or None,
                             occurred_at=datetime.utcnow()))


# ═══════════ 数据范围 ═══════════

def _ctx(user, db):
    return build_affairs_context(user, db)


def _allowed_college_ids(ctx, db) -> set[int] | None:
    """None=本租户全量可见；否则允许的学院 id 集合（可能为空=fail-closed）。"""
    from app.models import Major, SchoolClass
    if ctx.scope_type == "TENANT_ALL":
        return None
    ids: set[int] = set(ctx.college_ids)
    if ctx.class_ids:  # 班级级角色：class → major → college 上溯
        majs = db.scalars(select(SchoolClass.major_id).where(
            SchoolClass.tenant_id == ctx.tenant_id, SchoolClass.id.in_(list(ctx.class_ids)))).all()
        if majs:
            cols = db.scalars(select(Major.college_id).where(
                Major.tenant_id == ctx.tenant_id, Major.id.in_([m for m in majs if m]))).all()
            ids |= {c for c in cols if c}
    return ids  # 可能为空 → fail-closed


def _require_college_write(ctx, db, college_id: int):
    """写操作学院范围校验：越范围 → 403002。"""
    allowed = _allowed_college_ids(ctx, db)
    if allowed is None:
        return
    if college_id is None or int(college_id) not in allowed:
        raise no_data_scope("该学院不在您的管理范围内")


def _get_college(db, college_id):
    from app.models import College
    c = db.get(College, int(college_id)) if college_id else None
    if not c or getattr(c, "is_deleted", False) or c.tenant_id != _tid():
        raise not_found("学院不存在")
    return c


def _get_major(db, major_id):
    from app.models import Major
    m = db.get(Major, int(major_id)) if major_id else None
    if not m or getattr(m, "is_deleted", False) or m.tenant_id != _tid():
        raise not_found("专业不存在")
    return m


def _get_class(db, class_id):
    from app.models import SchoolClass
    c = db.get(SchoolClass, int(class_id)) if class_id else None
    if not c or getattr(c, "is_deleted", False) or c.tenant_id != _tid():
        raise not_found("行政班不存在")
    return c


# ═══════════ 学院 ═══════════

def _college_dto(c) -> dict:
    return {"id": str(c.id), "collegeName": c.college_name, "code": c.code, "shortName": c.short_name,
            "sortOrder": c.sort_order, "secretaryId": str(c.secretary_id) if c.secretary_id else None,
            "status": c.status, "remark": c.remark}


def list_colleges(user, keyword=None, status=None, page=1, page_size=50):
    from app.models import College
    with session() as db:
        ctx = _ctx(user, db)
        allowed = _allowed_college_ids(ctx, db)
        if allowed is not None and not allowed:
            return [], 0
        conds = [College.tenant_id == _tid(), College.is_deleted.is_(False)]
        if allowed is not None:
            conds.append(College.id.in_(list(allowed)))
        if status:
            conds.append(College.status == status)
        if keyword:
            like = f"%{keyword}%"
            conds.append(College.college_name.like(like) | College.code.like(like))
        total = db.scalar(select(func.count()).select_from(College).where(*conds)) or 0
        offset = (max(1, page) - 1) * page_size
        rows = db.scalars(select(College).where(*conds)
                          .order_by(College.sort_order, College.id).offset(offset).limit(page_size)).all()
        return [_college_dto(c) for c in rows], total


def create_college(user, body) -> dict:
    from app.models import College
    name = (getattr(body, "collegeName", None) or "").strip()
    if not name:
        raise AppException("VALIDATION_ERROR", "学院名称必填")
    with session() as db:
        ctx = _ctx(user, db)
        if _allowed_college_ids(ctx, db) is not None:  # 仅全租户角色可新建学院
            raise no_data_scope("仅教务处/校管可新建学院")
        dup = db.scalars(select(College).where(
            College.tenant_id == _tid(), College.is_deleted.is_(False),
            College.college_name == name)).first()
        if dup:
            raise AppException("DATA_CONFLICT", "同名学院已存在")
        c = College(tenant_id=_tid(), college_name=name, code=getattr(body, "code", None),
                    short_name=getattr(body, "shortName", None),
                    sort_order=int(getattr(body, "sortOrder", 0) or 0),
                    status="ACTIVE", remark=getattr(body, "remark", None))
        db.add(c)
        db.flush()
        _audit(db, "AA_ORG_COLLEGE", c.id, "CREATE", name)
        db.commit()
        db.refresh(c)
        return _college_dto(c)


def update_college(user, college_id, body) -> dict:
    with session() as db:
        ctx = _ctx(user, db)
        c = _get_college(db, college_id)
        _require_college_write(ctx, db, c.id)
        before = _college_dto(c)
        for attr, key in (("college_name", "collegeName"), ("code", "code"), ("short_name", "shortName"),
                          ("remark", "remark"), ("status", "status")):
            v = getattr(body, key, None)
            if v is not None:
                if attr == "college_name" and not str(v).strip():
                    raise AppException("VALIDATION_ERROR", "学院名称不能为空")
                setattr(c, attr, v)
        so = getattr(body, "sortOrder", None)
        if so is not None:
            c.sort_order = int(so)
        db.flush()
        _audit(db, "AA_ORG_COLLEGE", c.id, "UPDATE", c.college_name,
               before=str(before), after=str(_college_dto(c)))
        db.commit()
        db.refresh(c)
        return _college_dto(c)


def bind_secretary(user, college_id, body) -> dict:
    """教学秘书绑定 / 解绑（secretaryId=null 解绑）。"""
    with session() as db:
        ctx = _ctx(user, db)
        c = _get_college(db, college_id)
        _require_college_write(ctx, db, c.id)
        old = c.secretary_id
        sid = getattr(body, "secretaryId", None)
        c.secretary_id = int(sid) if sid else None
        db.flush()
        _audit(db, "AA_ORG_COLLEGE", c.id, "BIND_SECRETARY", c.college_name,
               before=str(old or ""), after=str(c.secretary_id or ""))
        db.commit()
        db.refresh(c)
        return _college_dto(c)


def delete_college(user, college_id) -> dict:
    from app.models import Major
    with session() as db:
        ctx = _ctx(user, db)
        c = _get_college(db, college_id)
        _require_college_write(ctx, db, c.id)
        child = db.scalar(select(func.count()).select_from(Major).where(
            Major.tenant_id == _tid(), Major.is_deleted.is_(False), Major.college_id == c.id)) or 0
        if child:
            raise AppException("DATA_CONFLICT", f"该学院下仍有 {child} 个专业，请先处理专业")
        c.is_deleted = True
        c.status = "DISABLED"
        _audit(db, "AA_ORG_COLLEGE", c.id, "DELETE", c.college_name)
        db.commit()
        return {"id": str(college_id), "deleted": True}


# ═══════════ 专业 ═══════════

def _major_dto(m, college_name=None) -> dict:
    return {"id": str(m.id), "collegeId": str(m.college_id), "collegeName": college_name,
            "majorName": m.major_name, "code": m.code, "educationYears": m.education_years,
            "trainingLevel": m.training_level, "enrollStatus": m.enroll_status,
            "direction": m.direction, "status": m.status, "remark": m.remark}


def list_majors(user, college_id=None, enroll_status=None, keyword=None, page=1, page_size=50):
    from app.models import College, Major
    with session() as db:
        ctx = _ctx(user, db)
        allowed = _allowed_college_ids(ctx, db)
        if allowed is not None and not allowed:
            return [], 0
        conds = [Major.tenant_id == _tid(), Major.is_deleted.is_(False)]
        if allowed is not None:
            conds.append(Major.college_id.in_(list(allowed)))
        if college_id:
            conds.append(Major.college_id == int(college_id))
        if enroll_status:
            conds.append(Major.enroll_status == enroll_status)
        if keyword:
            like = f"%{keyword}%"
            conds.append(Major.major_name.like(like) | Major.code.like(like))
        total = db.scalar(select(func.count()).select_from(Major).where(*conds)) or 0
        offset = (max(1, page) - 1) * page_size
        rows = db.scalars(select(Major).where(*conds)
                          .order_by(Major.college_id, Major.id).offset(offset).limit(page_size)).all()
        cmap = {c.id: c.college_name for c in db.scalars(select(College).where(
            College.tenant_id == _tid(), College.id.in_([m.college_id for m in rows] or [0]))).all()}
        return [_major_dto(m, cmap.get(m.college_id)) for m in rows], total


def create_major(user, body) -> dict:
    from app.models import Major
    name = (getattr(body, "majorName", None) or "").strip()
    college_id = getattr(body, "collegeId", None)
    if not name or not college_id:
        raise AppException("VALIDATION_ERROR", "专业名称与所属学院必填")
    years = int(getattr(body, "educationYears", 3) or 3)
    if years < 1 or years > 10:
        raise AppException("VALIDATION_ERROR", "学制须在 1~10 年之间")
    enroll = getattr(body, "enrollStatus", None) or "ENROLLING"
    if enroll not in _MAJOR_ENROLL:
        raise AppException("VALIDATION_ERROR", "招生状态非法")
    with session() as db:
        ctx = _ctx(user, db)
        _get_college(db, college_id)
        _require_college_write(ctx, db, college_id)
        dup = db.scalars(select(Major).where(
            Major.tenant_id == _tid(), Major.is_deleted.is_(False),
            Major.college_id == int(college_id), Major.major_name == name)).first()
        if dup:
            raise AppException("DATA_CONFLICT", "该学院下同名专业已存在")
        m = Major(tenant_id=_tid(), college_id=int(college_id), major_name=name,
                  code=getattr(body, "code", None), education_years=years,
                  training_level=getattr(body, "trainingLevel", None), enroll_status=enroll,
                  direction=getattr(body, "direction", None), status="ACTIVE",
                  remark=getattr(body, "remark", None))
        db.add(m)
        db.flush()
        _audit(db, "AA_ORG_MAJOR", m.id, "CREATE", name)
        db.commit()
        db.refresh(m)
        return _major_dto(m)


def update_major(user, major_id, body) -> dict:
    with session() as db:
        ctx = _ctx(user, db)
        m = _get_major(db, major_id)
        _require_college_write(ctx, db, m.college_id)
        before = _major_dto(m)
        for attr, key in (("major_name", "majorName"), ("code", "code"), ("training_level", "trainingLevel"),
                          ("direction", "direction"), ("remark", "remark"), ("status", "status")):
            v = getattr(body, key, None)
            if v is not None:
                setattr(m, attr, v)
        yrs = getattr(body, "educationYears", None)
        if yrs is not None:
            yrs = int(yrs)
            if yrs < 1 or yrs > 10:
                raise AppException("VALIDATION_ERROR", "学制须在 1~10 年之间")
            m.education_years = yrs
        es = getattr(body, "enrollStatus", None)
        if es is not None:
            if es not in _MAJOR_ENROLL:
                raise AppException("VALIDATION_ERROR", "招生状态非法")
            m.enroll_status = es
        db.flush()
        _audit(db, "AA_ORG_MAJOR", m.id, "UPDATE", m.major_name,
               before=str(before), after=str(_major_dto(m)))
        db.commit()
        db.refresh(m)
        return _major_dto(m)


def delete_major(user, major_id) -> dict:
    from app.models import SchoolClass
    with session() as db:
        ctx = _ctx(user, db)
        m = _get_major(db, major_id)
        _require_college_write(ctx, db, m.college_id)
        child = db.scalar(select(func.count()).select_from(SchoolClass).where(
            SchoolClass.tenant_id == _tid(), SchoolClass.is_deleted.is_(False),
            SchoolClass.major_id == m.id)) or 0
        if child:
            raise AppException("DATA_CONFLICT", f"该专业下仍有 {child} 个行政班，请先处理班级")
        m.is_deleted = True
        m.status = "DISABLED"
        _audit(db, "AA_ORG_MAJOR", m.id, "DELETE", m.major_name)
        db.commit()
        return {"id": str(major_id), "deleted": True}


# ═══════════ 行政班 ═══════════

def _class_dto(c, major_name=None) -> dict:
    return {"id": str(c.id), "majorId": str(c.major_id), "majorName": major_name,
            "className": c.class_name, "classCode": c.class_code, "grade": c.grade,
            "capacity": c.capacity, "graduateYear": c.graduate_year, "classStatus": c.class_status,
            "counselorId": str(c.counselor_id) if c.counselor_id else None,
            "headTeacherId": str(c.head_teacher_id) if c.head_teacher_id else None,
            "status": c.status, "remark": c.remark}


def _class_college_id(db, class_id) -> int | None:
    """班级 → 学院（经专业）用于写范围校验。"""
    from app.models import Major, SchoolClass
    c = db.get(SchoolClass, int(class_id))
    if not c:
        return None
    m = db.get(Major, int(c.major_id)) if c.major_id else None
    return m.college_id if m else None


def list_classes(user, major_id=None, grade=None, class_status=None, keyword=None, page=1, page_size=50):
    from app.models import Major, SchoolClass
    with session() as db:
        ctx = _ctx(user, db)
        allowed = _allowed_college_ids(ctx, db)
        conds = [SchoolClass.tenant_id == _tid(), SchoolClass.is_deleted.is_(False)]
        if allowed is not None:
            if not allowed:
                return [], 0
            maj_ids = db.scalars(select(Major.id).where(
                Major.tenant_id == _tid(), Major.college_id.in_(list(allowed)))).all()
            if not maj_ids:
                return [], 0
            conds.append(SchoolClass.major_id.in_(list(maj_ids)))
        if major_id:
            conds.append(SchoolClass.major_id == int(major_id))
        if grade:
            conds.append(SchoolClass.grade == grade)
        if class_status:
            conds.append(SchoolClass.class_status == class_status)
        if keyword:
            like = f"%{keyword}%"
            conds.append(SchoolClass.class_name.like(like) | SchoolClass.class_code.like(like))
        total = db.scalar(select(func.count()).select_from(SchoolClass).where(*conds)) or 0
        offset = (max(1, page) - 1) * page_size
        rows = db.scalars(select(SchoolClass).where(*conds)
                          .order_by(SchoolClass.major_id, SchoolClass.grade, SchoolClass.id)
                          .offset(offset).limit(page_size)).all()
        mmap = {m.id: m.major_name for m in db.scalars(select(Major).where(
            Major.tenant_id == _tid(), Major.id.in_([c.major_id for c in rows] or [0]))).all()}
        return [_class_dto(c, mmap.get(c.major_id)) for c in rows], total


def create_class(user, body) -> dict:
    from app.models import SchoolClass
    name = (getattr(body, "className", None) or "").strip()
    major_id = getattr(body, "majorId", None)
    if not name or not major_id:
        raise AppException("VALIDATION_ERROR", "班级名称与所属专业必填")
    cap = getattr(body, "capacity", None)
    if cap is not None and int(cap) < 0:
        raise AppException("VALIDATION_ERROR", "编制人数不能为负")
    with session() as db:
        ctx = _ctx(user, db)
        m = _get_major(db, major_id)
        _require_college_write(ctx, db, m.college_id)
        dup = db.scalars(select(SchoolClass).where(
            SchoolClass.tenant_id == _tid(), SchoolClass.is_deleted.is_(False),
            SchoolClass.major_id == int(major_id), SchoolClass.class_name == name)).first()
        if dup:
            raise AppException("DATA_CONFLICT", "该专业下同名班级已存在")
        c = SchoolClass(tenant_id=_tid(), major_id=int(major_id), class_name=name,
                        class_code=getattr(body, "classCode", None), grade=getattr(body, "grade", None),
                        capacity=(int(cap) if cap is not None else None),
                        graduate_year=getattr(body, "graduateYear", None),
                        class_status=(getattr(body, "classStatus", None) or "NORMAL"),
                        counselor_id=(int(body.counselorId) if getattr(body, "counselorId", None) else None),
                        head_teacher_id=(int(body.headTeacherId) if getattr(body, "headTeacherId", None) else None),
                        status="ACTIVE", remark=getattr(body, "remark", None))
        if c.class_status not in _CLASS_STATUS:
            raise AppException("VALIDATION_ERROR", "班级状态非法")
        db.add(c)
        db.flush()
        _audit(db, "AA_ORG_CLASS", c.id, "CREATE", name)
        db.commit()
        db.refresh(c)
        return _class_dto(c)


def update_class(user, class_id, body) -> dict:
    with session() as db:
        ctx = _ctx(user, db)
        c = _get_class(db, class_id)
        _require_college_write(ctx, db, _class_college_id(db, c.id))
        before = _class_dto(c)
        for attr, key in (("class_name", "className"), ("class_code", "classCode"), ("grade", "grade"),
                          ("graduate_year", "graduateYear"), ("remark", "remark"), ("status", "status")):
            v = getattr(body, key, None)
            if v is not None:
                setattr(c, attr, v)
        cap = getattr(body, "capacity", None)
        if cap is not None:
            if int(cap) < 0:
                raise AppException("VALIDATION_ERROR", "编制人数不能为负")
            c.capacity = int(cap)
        cs = getattr(body, "classStatus", None)
        if cs is not None:
            if cs not in _CLASS_STATUS:
                raise AppException("VALIDATION_ERROR", "班级状态非法")
            c.class_status = cs
        for attr, key in (("counselor_id", "counselorId"), ("head_teacher_id", "headTeacherId")):
            v = getattr(body, key, None)
            if v is not None:
                setattr(c, attr, int(v) if v else None)
        db.flush()
        _audit(db, "AA_ORG_CLASS", c.id, "UPDATE", c.class_name,
               before=str(before), after=str(_class_dto(c)))
        db.commit()
        db.refresh(c)
        return _class_dto(c)


def delete_class(user, class_id) -> dict:
    from app.models import StudentProfile
    with session() as db:
        ctx = _ctx(user, db)
        c = _get_class(db, class_id)
        _require_college_write(ctx, db, _class_college_id(db, c.id))
        stu = db.scalar(select(func.count()).select_from(StudentProfile).where(
            StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
            StudentProfile.class_id == c.id)) or 0
        if stu:
            raise AppException("DATA_CONFLICT", f"该班仍有 {stu} 名学生，请先调整学生归属")
        c.is_deleted = True
        c.class_status = "DISBANDED"
        c.status = "DISABLED"
        _audit(db, "AA_ORG_CLASS", c.id, "DELETE", c.class_name)
        db.commit()
        return {"id": str(class_id), "deleted": True}


# ═══════════ 年级（聚合，非独立表）═══════════

def list_grades(user, college_id=None, major_id=None):
    """按 t_class.grade 聚合：每个年级班级数 / 学生数（在范围内）。"""
    from app.models import Major, SchoolClass, StudentProfile
    with session() as db:
        ctx = _ctx(user, db)
        allowed = _allowed_college_ids(ctx, db)
        conds = [SchoolClass.tenant_id == _tid(), SchoolClass.is_deleted.is_(False),
                 SchoolClass.grade.is_not(None)]
        if allowed is not None:
            if not allowed:
                return {"items": []}
            maj_ids = db.scalars(select(Major.id).where(
                Major.tenant_id == _tid(), Major.college_id.in_(list(allowed)))).all()
            if not maj_ids:
                return {"items": []}
            conds.append(SchoolClass.major_id.in_(list(maj_ids)))
        if college_id:
            maj_ids = db.scalars(select(Major.id).where(
                Major.tenant_id == _tid(), Major.college_id == int(college_id))).all()
            conds.append(SchoolClass.major_id.in_(list(maj_ids) or [0]))
        if major_id:
            conds.append(SchoolClass.major_id == int(major_id))
        rows = db.execute(select(SchoolClass.grade, func.count(SchoolClass.id))
                          .where(*conds).group_by(SchoolClass.grade)
                          .order_by(SchoolClass.grade.desc())).all()
        # 学生数按年级
        stu_rows = db.execute(select(SchoolClass.grade, func.count(StudentProfile.id))
                              .join(StudentProfile, (StudentProfile.class_id == SchoolClass.id) &
                                    (StudentProfile.tenant_id == SchoolClass.tenant_id) &
                                    (StudentProfile.is_deleted.is_(False)))
                              .where(*conds).group_by(SchoolClass.grade)).all()
        smap = {g: n for g, n in stu_rows}
        items = [{"grade": g, "classCount": n, "studentCount": int(smap.get(g, 0))} for g, n in rows]
        return {"items": items}


# ═══════════ 教学班（只读汇总，派生自教学任务）═══════════

def list_teaching_classes(user, term_code=None, batch_id=None, page=1, page_size=50):
    """教学班无独立表：按 t_aa_teaching_task.teaching_class_code 去重汇总（只读）。"""
    from app.models import AaTeachingTask
    with session() as db:
        _ctx(user, db)  # 建立上下文（教学班读侧不做学院过滤，属教务任务派生视图）
        conds = [AaTeachingTask.tenant_id == _tid(), AaTeachingTask.is_deleted.is_(False),
                 AaTeachingTask.teaching_class_code.is_not(None)]
        if batch_id:
            conds.append(AaTeachingTask.batch_id == int(batch_id))
        rows = db.scalars(select(AaTeachingTask).where(*conds)
                          .order_by(AaTeachingTask.batch_id, AaTeachingTask.id)).all()
        agg: dict[str, dict] = {}
        for t in rows:
            key = t.teaching_class_code
            it = agg.setdefault(key, {"teachingClassCode": key, "teachingClassName": t.teaching_class_name,
                                      "isMerged": bool(t.is_merged), "courseCount": 0,
                                      "expectedStudents": t.expected_students, "courses": []})
            it["courseCount"] += 1
            if t.course_name:
                it["courses"].append(t.course_name)
        items = list(agg.values())
        total = len(items)
        offset = (max(1, page) - 1) * page_size
        return items[offset:offset + page_size], total


# ═══════════ 班级学生 + 班级调整 ═══════════

def list_class_students(user, class_id, keyword=None, page=1, page_size=50):
    """班级学生名册（07 号卡，只读）：学号/姓名/性别/学籍状态/手机号脱敏 + 关键字搜索。
    数据范围与既有写口径一致（本学院），手机号复用 db_service._primary_phone 同款脱敏口径
    （t_student_contact.contact_type=PHONE，演示环境明文占位、真实环境密文，脱敏在本函数内完成，
    不返回明文；本卡不提供明文解锁入口，见三级卡 §10）。"""
    from app.models import StudentContact, StudentProfile
    with session() as db:
        ctx = _ctx(user, db)
        c = _get_class(db, class_id)
        _require_college_write(ctx, db, _class_college_id(db, c.id))
        conds = [StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
                 StudentProfile.class_id == c.id]
        if keyword:
            like = f"%{keyword}%"
            conds.append(StudentProfile.real_name.like(like) | StudentProfile.student_no.like(like))
        total = db.scalar(select(func.count()).select_from(StudentProfile).where(*conds)) or 0
        offset = (max(1, page) - 1) * page_size
        rows = db.scalars(select(StudentProfile).where(*conds)
                          .order_by(StudentProfile.student_no).offset(offset).limit(page_size)).all()
        ids = [s.id for s in rows] or [0]
        contacts = db.scalars(select(StudentContact).where(
            StudentContact.tenant_id == _tid(), StudentContact.student_id.in_(ids),
            StudentContact.contact_type == "PHONE", StudentContact.is_deleted.is_(False))).all()
        pmap: dict[int, str] = {}
        for ctc in contacts:
            pmap.setdefault(ctc.student_id, ctc.contact_value_encrypted or "")
        items = [{"id": str(s.id), "studentId": str(s.id), "studentNo": s.student_no, "realName": s.real_name,
                  "gender": s.gender or "", "studentStatus": s.student_status or "",
                  "phoneMasked": _mask_phone(pmap.get(s.id, "")),
                  "classId": str(s.class_id) if s.class_id else None} for s in rows]
        return items, total


def adjust_student_class(user, body) -> dict:
    """班级调整：把学生移动到目标班（源班/目标班均须在范围内）+ 审计。"""
    from app.models import StudentProfile
    student_id = getattr(body, "studentId", None)
    target_class_id = getattr(body, "targetClassId", None)
    if not student_id or not target_class_id:
        raise AppException("VALIDATION_ERROR", "学生与目标班级必填")
    with session() as db:
        ctx = _ctx(user, db)
        target = _get_class(db, target_class_id)
        _require_college_write(ctx, db, _class_college_id(db, target.id))
        s = db.get(StudentProfile, int(student_id))
        if not s or getattr(s, "is_deleted", False) or s.tenant_id != _tid():
            raise not_found("学生不存在")
        old_class = s.class_id
        if old_class:  # 源班也须在范围内，禁止跨范围抢人
            _require_college_write(ctx, db, _class_college_id(db, old_class))
        if old_class == target.id:
            raise AppException("DATA_CONFLICT", "学生已在目标班级")
        s.class_id = target.id
        s.major_id = target.major_id
        s.college_id = _class_college_id(db, target.id)
        _audit(db, "AA_ORG_CLASS_ADJUST", s.id, "ADJUST_CLASS",
               f"{s.real_name} → {target.class_name}", before=str(old_class or ""), after=str(target.id))
        db.commit()
        return {"studentId": str(student_id), "fromClassId": str(old_class) if old_class else None,
                "toClassId": str(target.id)}


# ═══════════ 组织树 / 统计 / 变更审计 ═══════════

def org_tree(user):
    """组织结构（学院→专业→班级）层级只读（范围内）。"""
    from app.models import College, Major, SchoolClass
    with session() as db:
        ctx = _ctx(user, db)
        allowed = _allowed_college_ids(ctx, db)
        col_conds = [College.tenant_id == _tid(), College.is_deleted.is_(False)]
        if allowed is not None:
            if not allowed:
                return {"colleges": []}
            col_conds.append(College.id.in_(list(allowed)))
        cols = db.scalars(select(College).where(*col_conds).order_by(College.sort_order, College.id)).all()
        col_ids = [c.id for c in cols] or [0]
        majors = db.scalars(select(Major).where(
            Major.tenant_id == _tid(), Major.is_deleted.is_(False),
            Major.college_id.in_(col_ids))).all()
        maj_ids = [m.id for m in majors] or [0]
        classes = db.scalars(select(SchoolClass).where(
            SchoolClass.tenant_id == _tid(), SchoolClass.is_deleted.is_(False),
            SchoolClass.major_id.in_(maj_ids))).all()
        cls_by_maj: dict[int, list] = {}
        for cl in classes:
            cls_by_maj.setdefault(cl.major_id, []).append(
                {"id": str(cl.id), "className": cl.class_name, "grade": cl.grade,
                 "classStatus": cl.class_status})
        maj_by_col: dict[int, list] = {}
        for m in majors:
            maj_by_col.setdefault(m.college_id, []).append(
                {"id": str(m.id), "majorName": m.major_name, "enrollStatus": m.enroll_status,
                 "classes": cls_by_maj.get(m.id, [])})
        return {"colleges": [{"id": str(c.id), "collegeName": c.college_name, "shortName": c.short_name,
                              "majors": maj_by_col.get(c.id, [])} for c in cols]}


def org_stats(user):
    """组织统计：学院/专业/班级/在校生计数 + 招生专业数 + 已毕业班数（范围内）。"""
    from app.models import College, Major, SchoolClass, StudentProfile
    with session() as db:
        ctx = _ctx(user, db)
        allowed = _allowed_college_ids(ctx, db)
        col_conds = [College.tenant_id == _tid(), College.is_deleted.is_(False)]
        maj_conds = [Major.tenant_id == _tid(), Major.is_deleted.is_(False)]
        cls_conds = [SchoolClass.tenant_id == _tid(), SchoolClass.is_deleted.is_(False)]
        stu_conds = [StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False)]
        if allowed is not None:
            if not allowed:
                return {"collegeCount": 0, "majorCount": 0, "classCount": 0, "studentCount": 0,
                        "enrollingMajorCount": 0, "graduatedClassCount": 0}
            col_conds.append(College.id.in_(list(allowed)))
            maj_conds.append(Major.college_id.in_(list(allowed)))
            maj_ids = db.scalars(select(Major.id).where(
                Major.tenant_id == _tid(), Major.college_id.in_(list(allowed)))).all()
            cls_conds.append(SchoolClass.major_id.in_(list(maj_ids) or [0]))
            stu_conds.append(StudentProfile.college_id.in_(list(allowed)))
        return {
            "collegeCount": db.scalar(select(func.count()).select_from(College).where(*col_conds)) or 0,
            "majorCount": db.scalar(select(func.count()).select_from(Major).where(*maj_conds)) or 0,
            "classCount": db.scalar(select(func.count()).select_from(SchoolClass).where(*cls_conds)) or 0,
            "studentCount": db.scalar(select(func.count()).select_from(StudentProfile).where(*stu_conds)) or 0,
            "enrollingMajorCount": db.scalar(select(func.count()).select_from(Major).where(
                *maj_conds, Major.enroll_status == "ENROLLING")) or 0,
            "graduatedClassCount": db.scalar(select(func.count()).select_from(SchoolClass).where(
                *cls_conds, SchoolClass.class_status == "GRADUATED")) or 0,
        }


# ═══════════ 专业方向（06 号卡）═══════════

def _major_direction_enabled(db, tenant_id: int) -> bool:
    """总开关默认关闭（业务政策待学校确认，见三级卡 §3）；缺省行=未启用。"""
    from app.models import PlatformConfig
    row = db.scalars(select(PlatformConfig).where(
        PlatformConfig.tenant_id == tenant_id, PlatformConfig.config_type == _MD_CFG_TYPE,
        PlatformConfig.config_key == _MD_CFG_KEY, PlatformConfig.is_deleted.is_(False))).first()
    return bool(row.enabled) if row else False


def get_major_direction_toggle(user) -> dict:
    with session() as db:
        _ctx(user, db)
        return {"enabled": _major_direction_enabled(db, _tid())}


def set_major_direction_toggle(user, enabled: bool) -> dict:
    """仅教务处/校管（TENANT_ALL 范围）可切换总开关；学院教务无此权限。"""
    from app.models import PlatformConfig
    with session() as db:
        ctx = _ctx(user, db)
        if _allowed_college_ids(ctx, db) is not None:
            raise no_data_scope("仅教务处/校管可设置专业方向总开关")
        row = db.scalars(select(PlatformConfig).where(
            PlatformConfig.tenant_id == _tid(), PlatformConfig.config_type == _MD_CFG_TYPE,
            PlatformConfig.config_key == _MD_CFG_KEY)).first()
        if row:
            row.enabled = bool(enabled)
            row.is_deleted = False
            row.version += 1
        else:
            row = PlatformConfig(tenant_id=_tid(), config_type=_MD_CFG_TYPE, config_key=_MD_CFG_KEY,
                                 config_json={}, enabled=bool(enabled))
            db.add(row)
        db.flush()
        _audit(db, "AA_ORG_MAJOR_DIRECTION", None, "TOGGLE", f"总开关→{'启用' if enabled else '停用'}")
        db.commit()
        return {"enabled": bool(enabled)}


def _require_direction_enabled(db):
    if not _major_direction_enabled(db, _tid()):
        raise AppException("FEATURE_DISABLED", "专业方向总开关未启用，请联系教务处/校管开启")


def _direction_dto(d) -> dict:
    return {"id": str(d.id), "majorId": str(d.major_id), "directionName": d.direction_name,
            "code": d.code, "status": d.status}


def list_directions(user, major_id, page=1, page_size=50):
    from app.models import AaMajorDirection
    with session() as db:
        ctx = _ctx(user, db)
        _require_direction_enabled(db)
        m = _get_major(db, major_id)
        _require_college_write(ctx, db, m.college_id)
        conds = [AaMajorDirection.tenant_id == _tid(), AaMajorDirection.is_deleted.is_(False),
                 AaMajorDirection.major_id == m.id]
        total = db.scalar(select(func.count()).select_from(AaMajorDirection).where(*conds)) or 0
        offset = (max(1, page) - 1) * page_size
        rows = db.scalars(select(AaMajorDirection).where(*conds)
                          .order_by(AaMajorDirection.id).offset(offset).limit(page_size)).all()
        return [_direction_dto(d) for d in rows], total


def create_direction(user, major_id, body) -> dict:
    from app.models import AaMajorDirection
    name = (getattr(body, "directionName", None) or "").strip()
    if not name:
        raise AppException("VALIDATION_ERROR", "方向名称必填")
    with session() as db:
        ctx = _ctx(user, db)
        _require_direction_enabled(db)
        m = _get_major(db, major_id)
        _require_college_write(ctx, db, m.college_id)
        code = getattr(body, "code", None) or None
        if code:
            dup = db.scalars(select(AaMajorDirection).where(
                AaMajorDirection.tenant_id == _tid(), AaMajorDirection.is_deleted.is_(False),
                AaMajorDirection.major_id == m.id, AaMajorDirection.code == code)).first()
            if dup:
                raise AppException("DATA_CONFLICT", "该专业下同编码方向已存在")
        d = AaMajorDirection(tenant_id=_tid(), major_id=m.id, direction_name=name, code=code, status="ACTIVE")
        db.add(d)
        db.flush()
        _audit(db, "AA_ORG_MAJOR_DIRECTION", d.id, "DIRECTION_CREATE", name)
        db.commit()
        db.refresh(d)
        return _direction_dto(d)


def _get_direction(db, major_id, direction_id):
    from app.models import AaMajorDirection
    d = db.get(AaMajorDirection, int(direction_id)) if direction_id else None
    if not d or getattr(d, "is_deleted", False) or d.tenant_id != _tid() or d.major_id != int(major_id):
        raise not_found("专业方向不存在")
    return d


def update_direction(user, major_id, direction_id, body) -> dict:
    from app.models import AaMajorDirection
    with session() as db:
        ctx = _ctx(user, db)
        _require_direction_enabled(db)
        m = _get_major(db, major_id)
        _require_college_write(ctx, db, m.college_id)
        d = _get_direction(db, major_id, direction_id)
        before = _direction_dto(d)
        name = getattr(body, "directionName", None)
        if name is not None:
            if not str(name).strip():
                raise AppException("VALIDATION_ERROR", "方向名称不能为空")
            d.direction_name = name
        code = getattr(body, "code", None)
        if code is not None:
            if code:
                dup = db.scalars(select(AaMajorDirection).where(
                    AaMajorDirection.tenant_id == _tid(), AaMajorDirection.is_deleted.is_(False),
                    AaMajorDirection.major_id == m.id, AaMajorDirection.code == code,
                    AaMajorDirection.id != d.id)).first()
                if dup:
                    raise AppException("DATA_CONFLICT", "该专业下同编码方向已存在")
            d.code = code or None
        db.flush()
        _audit(db, "AA_ORG_MAJOR_DIRECTION", d.id, "DIRECTION_UPDATE", d.direction_name,
               before=str(before), after=str(_direction_dto(d)))
        db.commit()
        db.refresh(d)
        return _direction_dto(d)


def disable_direction(user, major_id, direction_id) -> dict:
    with session() as db:
        ctx = _ctx(user, db)
        _require_direction_enabled(db)
        m = _get_major(db, major_id)
        _require_college_write(ctx, db, m.college_id)
        d = _get_direction(db, major_id, direction_id)
        if d.status == "DISABLED":
            return _direction_dto(d)  # 幂等
        d.status = "DISABLED"
        db.flush()
        _audit(db, "AA_ORG_MAJOR_DIRECTION", d.id, "DIRECTION_DISABLE", d.direction_name)
        db.commit()
        db.refresh(d)
        return _direction_dto(d)


# ═══════════ 班级调整申请单（08 号卡，行政班层面批量组织调整）═══════════
# 区别于既有 adjust_student_class（个体学生转班，见上）：本组不改写 t_student_profile.class_id，
# 只做行政班 class_status 层面的组织记录（合班/停用→DISBANDED，毕业清班→GRADUATED），
# DRAFT→CHECKED→EXECUTED/CANCELLED，核对结果 24 小时内有效，执行前需未过期且无阻断项。

def _adjustment_class_names(db, ids: list[int]) -> dict[int, str]:
    from app.models import SchoolClass
    ids = [i for i in ids if i]
    if not ids:
        return {}
    rows = db.scalars(select(SchoolClass).where(
        SchoolClass.tenant_id == _tid(), SchoolClass.id.in_(ids))).all()
    return {c.id: c.class_name for c in rows}


def _adjustment_dto(a, class_names: dict[int, str] | None = None) -> dict:
    import json
    try:
        from_ids = [int(x) for x in json.loads(a.from_class_ids or "[]")]
    except (TypeError, ValueError):
        from_ids = []
    cmap = class_names or {}
    return {
        "id": str(a.id), "adjustType": a.adjust_type,
        "fromClassIds": [str(x) for x in from_ids],
        "fromClassNames": "、".join(cmap.get(x, str(x)) for x in from_ids),
        "toClassId": str(a.to_class_id) if a.to_class_id else None,
        "toClassName": cmap.get(a.to_class_id) if a.to_class_id else None,
        "reason": a.reason,
        "checkResult": json.loads(a.check_result_json) if a.check_result_json else None,
        "checkedAt": a.checked_at.isoformat() if a.checked_at else None,
        "status": a.status, "createdAt": a.created_at.isoformat() if a.created_at else None,
    }


def _get_adjustment(db, adjustment_id):
    from app.models import AaClassAdjustmentRequest
    a = db.get(AaClassAdjustmentRequest, int(adjustment_id)) if adjustment_id else None
    if not a or getattr(a, "is_deleted", False) or a.tenant_id != _tid():
        raise not_found("调整申请单不存在")
    return a


def _adjustment_colleges(db, a) -> set[int]:
    import json
    ids: set[int] = set()
    try:
        ids |= {int(x) for x in json.loads(a.from_class_ids or "[]")}
    except (TypeError, ValueError):
        pass
    if a.to_class_id:
        ids.add(a.to_class_id)
    cols: set[int] = set()
    for cid in ids:
        cg = _class_college_id(db, cid)
        if cg:
            cols.add(cg)
    return cols


def list_class_adjustments(user, status=None, adjust_type=None, page=1, page_size=50):
    import json
    from app.models import AaClassAdjustmentRequest, Major, SchoolClass
    with session() as db:
        ctx = _ctx(user, db)
        allowed = _allowed_college_ids(ctx, db)
        conds = [AaClassAdjustmentRequest.tenant_id == _tid(), AaClassAdjustmentRequest.is_deleted.is_(False)]
        if status:
            conds.append(AaClassAdjustmentRequest.status == status)
        if adjust_type:
            conds.append(AaClassAdjustmentRequest.adjust_type == adjust_type)
        rows = db.scalars(select(AaClassAdjustmentRequest).where(*conds)
                          .order_by(AaClassAdjustmentRequest.id.desc())).all()
        all_ids: set[int] = set()
        parsed: list[tuple] = []
        for a in rows:
            try:
                fids = [int(x) for x in json.loads(a.from_class_ids or "[]")]
            except (TypeError, ValueError):
                fids = []
            all_ids |= set(fids)
            if a.to_class_id:
                all_ids.add(a.to_class_id)
            parsed.append((a, fids))
        cls_college: dict[int, int | None] = {}
        if all_ids:
            classes = db.scalars(select(SchoolClass).where(
                SchoolClass.tenant_id == _tid(), SchoolClass.id.in_(list(all_ids)))).all()
            maj_ids = {c.major_id for c in classes if c.major_id}
            majs = db.scalars(select(Major).where(
                Major.tenant_id == _tid(), Major.id.in_(list(maj_ids) or [0]))).all()
            mmap = {m.id: m.college_id for m in majs}
            cls_college = {c.id: mmap.get(c.major_id) for c in classes}
        filtered = []
        for a, fids in parsed:
            if allowed is not None:  # COLLEGE 范围：涉及班级全部越出授权学院则不可见
                cols = {cls_college.get(fid) for fid in fids}
                if a.to_class_id:
                    cols.add(cls_college.get(a.to_class_id))
                cols.discard(None)
                if cols and not cols.issubset(allowed):
                    continue
            filtered.append(a)
        total = len(filtered)
        offset = (max(1, page) - 1) * page_size
        page_rows = filtered[offset:offset + page_size]
        cmap = _adjustment_class_names(db, list(all_ids))
        return [_adjustment_dto(a, cmap) for a in page_rows], total


def create_class_adjustment(user, body) -> dict:
    import json
    from app.models import AaClassAdjustmentRequest, SchoolClass
    adjust_type = (getattr(body, "adjustType", None) or "").upper()
    if adjust_type not in _ADJUST_TYPES:
        raise AppException("VALIDATION_ERROR", "调整类型非法")
    from_ids_raw = getattr(body, "fromClassIds", None) or []
    try:
        from_ids = [int(x) for x in from_ids_raw if x]
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "来源班级参数非法")
    if not from_ids:
        raise AppException("VALIDATION_ERROR", "来源班级至少选择1个")
    to_id_raw = getattr(body, "toClassId", None)
    to_id = int(to_id_raw) if to_id_raw else None
    if adjust_type == "MERGE" and not to_id:
        raise AppException("VALIDATION_ERROR", "合班登记必须指定目标班级")
    if to_id and to_id in from_ids:
        raise AppException("VALIDATION_ERROR", "目标班级不能同时是来源班级")
    reason = (getattr(body, "reason", None) or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "调整理由至少5个字符")
    with session() as db:
        ctx = _ctx(user, db)
        all_ids = set(from_ids) | ({to_id} if to_id else set())
        classes = {c.id: c for c in db.scalars(select(SchoolClass).where(
            SchoolClass.tenant_id == _tid(), SchoolClass.is_deleted.is_(False),
            SchoolClass.id.in_(list(all_ids)))).all()}
        if len(classes) != len(all_ids):
            raise not_found("涉及班级不存在")
        colleges: set[int] = set()
        for cid in all_ids:
            cg = _class_college_id(db, cid)
            if cg is None:
                raise AppException("VALIDATION_ERROR", "班级未归属有效专业/学院，无法发起调整")
            colleges.add(cg)
        if adjust_type == "MERGE" and len(colleges) > 1:
            raise AppException("VALIDATION_ERROR", "合班登记仅支持同学院内班级")
        for cg in colleges:
            _require_college_write(ctx, db, cg)
        for cid in all_ids:
            if classes[cid].class_status != "NORMAL":
                raise AppException("VALIDATION_ERROR", f"班级「{classes[cid].class_name}」当前状态非在读，无法发起调整")
        a = AaClassAdjustmentRequest(tenant_id=_tid(), adjust_type=adjust_type,
                                     from_class_ids=json.dumps(from_ids), to_class_id=to_id,
                                     reason=reason, status="DRAFT")
        db.add(a)
        db.flush()
        _audit(db, "AA_ORG_CLASS_ADJUST_REQUEST", a.id, "ADJUST_CREATE", f"{adjust_type}: {reason}")
        db.commit()
        db.refresh(a)
        cmap = _adjustment_class_names(db, list(all_ids))
        return _adjustment_dto(a, cmap)


def precheck_class_adjustment(user, adjustment_id) -> dict:
    import json
    from app.models import SchoolClass, StudentProfile
    with session() as db:
        ctx = _ctx(user, db)
        a = _get_adjustment(db, adjustment_id)
        if a.status not in ("DRAFT", "CHECKED"):
            raise AppException("DATA_CONFLICT", "仅草稿/已核对状态可（重新）核对")
        for cg in _adjustment_colleges(db, a):
            _require_college_write(ctx, db, cg)
        from_ids = [int(x) for x in json.loads(a.from_class_ids or "[]")]
        refs = []
        blocked = False
        block_types = {"DISBAND", "GRADUATE_CLEAR"}
        for cid in from_ids:
            cnt = db.scalar(select(func.count()).select_from(StudentProfile).where(
                StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
                StudentProfile.class_id == cid,
                StudentProfile.student_status.notin_(["GRADUATED", "WITHDRAWN"]))) or 0
            cls = db.get(SchoolClass, cid)
            if a.adjust_type in block_types and cnt:
                blocked = True
            refs.append({"classId": str(cid), "className": cls.class_name if cls else "",
                        "activeStudentCount": cnt})
        result = {"blocked": blocked, "refs": refs}
        a.check_result_json = json.dumps(result)
        a.checked_at = datetime.utcnow()
        a.status = "CHECKED"
        db.flush()
        _audit(db, "AA_ORG_CLASS_ADJUST_REQUEST", a.id, "SYNC_CHECK", f"blocked={blocked}")
        db.commit()
        db.refresh(a)
        cmap = _adjustment_class_names(db, from_ids + ([a.to_class_id] if a.to_class_id else []))
        return _adjustment_dto(a, cmap)


def execute_class_adjustment(user, adjustment_id) -> dict:
    import json
    from app.models import SchoolClass
    with session() as db:
        ctx = _ctx(user, db)
        a = _get_adjustment(db, adjustment_id)
        from_ids = [int(x) for x in json.loads(a.from_class_ids or "[]")]
        if a.status == "EXECUTED":  # 幂等：重复执行直接返回已执行状态
            cmap = _adjustment_class_names(db, from_ids + ([a.to_class_id] if a.to_class_id else []))
            return _adjustment_dto(a, cmap)
        if a.status != "CHECKED":
            raise AppException("DATA_CONFLICT", "仅已核对状态可执行")
        if not a.checked_at or (datetime.utcnow() - a.checked_at).total_seconds() > _ADJUST_CHECK_TTL_HOURS * 3600:
            raise AppException("DATA_CONFLICT", "核对结果已过期（超过24小时），请重新核对")
        result = json.loads(a.check_result_json or "{}")
        if result.get("blocked"):
            raise AppException("VALIDATION_ERROR", "核对结果存在阻断项，无法执行")
        for cg in _adjustment_colleges(db, a):
            _require_college_write(ctx, db, cg)
        new_status = {"MERGE": "DISBANDED", "DISBAND": "DISBANDED",
                      "GRADUATE_CLEAR": "GRADUATED"}.get(a.adjust_type)
        if new_status:  # SPLIT：记录型动作，不改写来源班状态、不自动生成新班级（见三级卡边界说明），仅落审计
            for cid in from_ids:
                cls = db.get(SchoolClass, cid)
                if cls and cls.class_status != new_status:
                    cls.class_status = new_status
        a.status = "EXECUTED"
        db.flush()
        _audit(db, "AA_ORG_CLASS_ADJUST_REQUEST", a.id, "ADJUST_EXECUTE", f"{a.adjust_type} executed")
        db.commit()
        db.refresh(a)
        cmap = _adjustment_class_names(db, from_ids + ([a.to_class_id] if a.to_class_id else []))
        return _adjustment_dto(a, cmap)


def cancel_class_adjustment(user, adjustment_id) -> dict:
    with session() as db:
        ctx = _ctx(user, db)
        a = _get_adjustment(db, adjustment_id)
        if a.status not in ("DRAFT", "CHECKED"):
            raise AppException("DATA_CONFLICT", "已执行/已撤销的申请单不可再撤销")
        for cg in _adjustment_colleges(db, a):
            _require_college_write(ctx, db, cg)
        a.status = "CANCELLED"
        db.flush()
        _audit(db, "AA_ORG_CLASS_ADJUST_REQUEST", a.id, "ADJUST_CANCEL", "撤销")
        db.commit()
        db.refresh(a)
        cmap = _adjustment_class_names(db, [])
        return _adjustment_dto(a, cmap)


def list_org_audit(user, biz_type=None, page=1, page_size=50):
    """组织变更审计（读 t_affairs_audit_trail，biz_type=AA_ORG_*）。"""
    from app.models import AffairsAuditTrail
    with session() as db:
        _ctx(user, db)
        conds = [AffairsAuditTrail.tenant_id == _tid()]
        if biz_type:
            conds.append(AffairsAuditTrail.biz_type == biz_type)
        else:
            conds.append(AffairsAuditTrail.biz_type.like("AA_ORG%"))
        total = db.scalar(select(func.count()).select_from(AffairsAuditTrail).where(*conds)) or 0
        offset = (max(1, page) - 1) * page_size
        rows = db.scalars(select(AffairsAuditTrail).where(*conds)
                          .order_by(AffairsAuditTrail.id.desc()).offset(offset).limit(page_size)).all()
        items = [{"id": str(a.id), "bizType": a.biz_type, "bizId": str(a.biz_id) if a.biz_id else None,
                  "action": a.action, "operator": a.operator, "roleName": a.role_name,
                  "detail": a.detail, "beforeVal": a.before_val, "afterVal": a.after_val,
                  "occurredAt": a.occurred_at.isoformat() if a.occurred_at else None} for a in rows]
        return items, total
