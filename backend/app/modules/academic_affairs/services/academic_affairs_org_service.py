"""13B-R3 学院专业班级（组织架构）服务层。

组织三表复用冻结册 t_college / t_major / t_class（不建新表，R3 仅加列）。本服务提供：
- 学院 / 专业 / 行政班 CRUD（软删、乐观状态字段），教学秘书绑定；
- 年级（按 t_class.grade 聚合，非独立表）、组织树、组织统计（只读）；
- 教学班只读台账（正式 AaTeachingClass 投影优先，兼容历史任务字段）；
- 班级学生只读 + 班级调整（移动学生 class_id，单写入口 + 审计）；
- 组织变更审计（读 t_affairs_audit_trail，biz_type=AA_ORG_*）。

数据范围复用 app.core.affairs_security.build_affairs_context：
- TENANT_ALL（校管/教务处/校领导）→ 全租户；
- COLLEGE（学院管理员）→ 限授权学院及其下专业/班级；
- CLASS → 仅授权班及必要上级路径可读，不上溯为整个学院写授权；
- 其它/无授权 → fail-closed（列表空、写 403）。绝不回退看全租户。
写操作若目标学院不在范围内 → NO_DATA_SCOPE(403002)。
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import and_, func, or_, select

from app.core.affairs_security import build_affairs_context, no_data_scope
from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.core.field_crypto import mask_phone_encrypted
from app.services.db_service import _tid, session

_MAJOR_ENROLL = {"ENROLLING", "STOPPED"}
_CLASS_STATUS = {"NORMAL", "GRADUATED", "DISBANDED"}
_SECRETARY_USER_TYPES = {"TEACHER", "SCHOOL_ADMIN"}

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


def _allowed_class_ids(ctx, db) -> set[int] | None:
    """Organization metadata never promotes individual-student access to a whole class."""
    if ctx.scope_type == "TENANT_ALL":
        return None
    return ctx.allowed_class_ids(db) if ctx.scope_type in {"COLLEGE", "CLASS"} else set()


def _allowed_major_ids(ctx, db, *, include_deleted=False) -> set[int] | None:
    from app.models import Major, SchoolClass
    if ctx.scope_type == "TENANT_ALL":
        return None
    classes = _allowed_class_ids(ctx, db)
    parents = select(SchoolClass.major_id).where(
        SchoolClass.tenant_id == ctx.tenant_id, SchoolClass.id.in_(list(classes or set())))
    if not include_deleted:
        parents = parents.where(SchoolClass.is_deleted.is_(False))
    query = select(Major.id).where(Major.tenant_id == ctx.tenant_id,
        or_(Major.college_id.in_(list(ctx.college_ids)), Major.id.in_(parents)))
    if not include_deleted:
        query = query.where(Major.is_deleted.is_(False))
    return set(db.scalars(query).all())


def _allowed_college_ids(ctx, db) -> set[int] | None:
    """Read only the parents of visible branches; this is not write authorization."""
    from app.models import Major
    if ctx.scope_type == "TENANT_ALL":
        return None
    parents = db.scalars(select(Major.college_id).where(
        Major.tenant_id == ctx.tenant_id, Major.id.in_(list(_allowed_major_ids(ctx, db) or set())))).all()
    return set(ctx.college_ids) | {value for value in parents if value}


def _require_college_write(ctx, db, college_id: int):
    """写操作学院范围校验：越范围 → 403002。"""
    if ctx.scope_type == "TENANT_ALL":
        return
    if college_id is None or int(college_id) not in ctx.college_ids:
        raise no_data_scope("该学院不在您的管理范围内")


def _get_college(db, college_id, *, for_update=False):
    from app.models import College
    stmt = select(College).where(College.id == int(college_id or 0), College.tenant_id == _tid())
    if for_update:
        stmt = stmt.execution_options(populate_existing=True).with_for_update()
    c = db.scalar(stmt)
    if not c or getattr(c, "is_deleted", False) or c.tenant_id != _tid():
        raise not_found("学院不存在")
    return c


def _get_major(db, major_id, *, for_update=False):
    from app.models import Major
    stmt = select(Major).where(Major.id == int(major_id or 0), Major.tenant_id == _tid())
    if for_update:
        stmt = stmt.execution_options(populate_existing=True).with_for_update()
    m = db.scalar(stmt)
    if not m or getattr(m, "is_deleted", False) or m.tenant_id != _tid():
        raise not_found("专业不存在")
    return m


def _get_class(db, class_id, *, for_update=False):
    from app.models import SchoolClass
    stmt = select(SchoolClass).where(SchoolClass.id == int(class_id or 0), SchoolClass.tenant_id == _tid())
    if for_update:
        stmt = stmt.execution_options(populate_existing=True).with_for_update()
    c = db.scalar(stmt)
    if not c or getattr(c, "is_deleted", False) or c.tenant_id != _tid():
        raise not_found("行政班不存在")
    return c


# ═══════════ 学院 ═══════════

def _college_dto(c) -> dict:
    return {"id": str(c.id), "collegeName": c.college_name, "code": c.code, "shortName": c.short_name,
            "sortOrder": c.sort_order, "secretaryId": str(c.secretary_id) if c.secretary_id else None,
            "status": c.status, "remark": c.remark, "version": int(c.version or 0)}


def _college_dtos(db, rows) -> list[dict]:
    """Resolve only the staff bound to these visible colleges, in one tenant-scoped query."""
    from app.models import User
    ids = {c.secretary_id for c in rows if c.secretary_id}
    people = {u.id: u for u in db.scalars(select(User).where(User.tenant_id == _tid(), User.id.in_(ids))).all()} if ids else {}
    result = []
    for c in rows:
        dto = _college_dto(c)
        person = people.get(c.secretary_id)
        state = None
        if c.secretary_id:
            state = ("MISSING" if not person else "DELETED" if person.is_deleted else
                     "INVALID_TYPE" if person.user_type not in _SECRETARY_USER_TYPES else person.status)
        dto.update(secretaryName=person.real_name or person.login_name if person else None,
                   secretaryLoginName=person.login_name if person else None, secretaryStatus=state)
        result.append(dto)
    return result


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
        return _college_dtos(db, rows), total


def _sync_college_name_scopes(db, college, name):
    """保持历史名称授权指向同一个学院；不猜测重名或未归属授权的含义。"""
    from app.models import College, TeacherStudentScope
    if name == college.college_name:
        return 0
    old_name = college.college_name
    normalized_ref = func.trim(TeacherStudentScope.ref_value)
    # Compare in the database's collation, as the scope consumers do. Cosmetic
    # case changes must not be mistaken for a separate destination authorization.
    rows = db.execute(select(TeacherStudentScope, normalized_ref == old_name).where(
        TeacherStudentScope.tenant_id == _tid(), TeacherStudentScope.is_deleted.is_(False),
        TeacherStudentScope.scope_type == 'COLLEGE', normalized_ref.in_([old_name, name]))
        .order_by(TeacherStudentScope.id).execution_options(populate_existing=True).with_for_update()).all()
    sources = [row for row, matches_old in rows if matches_old]
    if any(not matches_old for _, matches_old in rows):
        raise AppException('DATA_CONFLICT', '目标名称已有学院管理范围，请先核对授权归属或使用其他名称',
            details={'reason': 'SCOPE_NAME_AMBIGUITY'})
    if not sources:
        return 0
    conflicts = db.scalars(select(College.id).where(College.tenant_id == _tid(),
        College.id != college.id, College.college_name.in_([old_name, name])).with_for_update()).all()
    if conflicts:
        raise AppException('DATA_CONFLICT', '同名学院会混淆现有管理范围，请先核对授权归属后再更名',
            details={'reason': 'SCOPE_NAME_AMBIGUITY'})
    if len(name) > 128:
        raise AppException('VALIDATION_ERROR', '该学院已有管理范围，请使用128字以内的学院名称')
    for row in sources:
        row.ref_value = name
        row.version = int(row.version or 0) + 1
    return len(sources)


def create_college(user, body) -> dict:
    """授权、学院主数据与两类审计使用同一个事务。"""
    from app.services.org_master_service import apply_org_node_in_session
    from app.services.db_service import audit_insert_in_session
    name = (getattr(body, "collegeName", None) or "").strip()
    if not name:
        raise AppException("VALIDATION_ERROR", "学院名称必填")
    code = (getattr(body, "code", None) or "").strip()
    with session() as db:
        ctx = _ctx(user, db)
        if _allowed_college_ids(ctx, db) is not None:
            raise no_data_scope("仅教务处/校管可新建学院")
        extras = {
            "short_name": getattr(body, "shortName", None),
            "sort_order": int(getattr(body, "sortOrder", 0) or 0),
            "remark": getattr(body, "remark", None),
        }
        result = apply_org_node_in_session(db, node_type="COLLEGE", name=name, code=code, actor=user, extras=extras)
        c = result['row']
        _audit(db, "AA_ORG_COLLEGE", c.id, "CREATE", name)
        audit_insert_in_session(db, 'ORG_NODE_SAVE', f'COLLEGE:{c.id}',
            {'name': c.college_name, 'code': c.code, 'before': None, 'reason': '',
             'moduleCode': 'systemAdmin', 'actor': (user or {}).get('userId'), 'extras': extras},
            'SUCCESS', tenant_id=_tid())
        db.commit()
        return _college_dtos(db, [c])[0]


def update_college(user, college_id, body) -> dict:
    """学院更名保持原管理范围；与秘书绑定共用 College 行锁和版本。"""
    from app.services.org_master_service import apply_org_node_in_session
    from app.services.db_service import audit_insert_in_session
    with session() as db:
        ctx = _ctx(user, db)
        c = _get_college(db, college_id, for_update=True)
        _require_college_write(ctx, db, c.id)
        before = _college_dtos(db, [c])[0]
        value = getattr(body, "collegeName", None)
        name = str(value).strip() if value is not None else c.college_name
        code = body.code if "code" in body.model_fields_set else before["code"]
        expected = getattr(body, "expectedVersion", None)
        if expected is not None and int(c.version or 0) != int(expected):
            raise AppException('DATA_CONFLICT', '学院资料已被他人修改，请重新核对',
                details={'reason': 'VERSION_CONFLICT', 'currentVersion': int(c.version or 0)})
        if not name:
            raise AppException('VALIDATION_ERROR', '学院名称必填')
        scope_count = _sync_college_name_scopes(db, c, name)
        extras = {attr: getattr(body, field) for field, attr in {
            "shortName": "short_name", "sortOrder": "sort_order", "remark": "remark", "status": "status",
        }.items() if field in body.model_fields_set}
        apply_org_node_in_session(db, node_type="COLLEGE", name=name,
            code=("" if code is None else str(code).strip()), node_id=int(college_id),
            expected_version=int(c.version or 0), actor=user, extras=extras)
        _audit(db, "AA_ORG_COLLEGE", c.id, "UPDATE",
               f'{c.college_name}；原学院管理范围已随名称更新（{scope_count}条）' if scope_count else c.college_name,
               before=str(before), after=str(_college_dtos(db, [c])[0]))
        audit_insert_in_session(db, 'ORG_NODE_SAVE', f'COLLEGE:{c.id}',
            {'name': c.college_name, 'code': c.code, 'before': before, 'reason': '',
             'moduleCode': 'systemAdmin', 'actor': (user or {}).get('userId'), 'extras': extras,
             'renamedScopeCount': scope_count}, 'SUCCESS', tenant_id=_tid())
        db.commit()
        return _college_dtos(db, [c])[0]


def list_secretary_candidates(user, college_id, *, keyword=None, user_id=None, page=1, page_size=50):
    from app.models import User
    with session() as db:
        ctx = _ctx(user, db)
        c = _get_college(db, college_id)
        _require_college_write(ctx, db, c.id)
        conds = [User.tenant_id == _tid(), User.is_deleted.is_(False), User.status == "ACTIVE",
                 User.user_type.in_(_SECRETARY_USER_TYPES)]
        if user_id is not None:
            conds.append(User.id == int(user_id))
        if keyword and keyword.strip():
            kw = keyword.strip()
            conds.append(or_(User.real_name.contains(kw, autoescape=True), User.login_name.contains(kw, autoescape=True)))
        total = db.scalar(select(func.count()).select_from(User).where(*conds)) or 0
        people = db.scalars(select(User).where(*conds).order_by(User.real_name, User.id)
                            .offset((page - 1) * page_size).limit(page_size)).all()
        return [{"value": str(u.id), "label": u.real_name or u.login_name,
                 "loginName": u.login_name, "userType": u.user_type} for u in people], total


def bind_secretary(user, college_id, body) -> dict:
    """教学秘书绑定 / 解绑（secretaryId=null 解绑）。"""
    from app.models import College, User
    raw = str(getattr(body, "secretaryId", None) or "").strip()
    if raw and (not raw.isascii() or not raw.isdecimal() or int(raw) <= 0 or int(raw) > 9223372036854775807):
        raise AppException("VALIDATION_ERROR", "请选择有效的教职工账号")
    sid = int(raw) if raw else None
    with session() as db:
        ctx = _ctx(user, db)
        c = db.scalar(select(College).where(College.id == int(college_id), College.tenant_id == _tid())
                      .execution_options(populate_existing=True).with_for_update())
        if not c or c.is_deleted:
            raise not_found("学院不存在")
        _require_college_write(ctx, db, c.id)
        expected = getattr(body, "expectedVersion", None)
        if expected is not None and int(expected) != int(c.version or 0):
            raise AppException("DATA_CONFLICT", "学院记录已被更新，请刷新后重新核对绑定", {"reason": "VERSION_CONFLICT"})
        if sid is not None:
            target = db.scalar(select(User).where(User.id == sid, User.tenant_id == _tid())
                               .execution_options(populate_existing=True).with_for_update())
            if not target or target.is_deleted:
                raise not_found("教职工账号不存在或已删除")
            if target.user_type not in _SECRETARY_USER_TYPES or target.status != "ACTIVE":
                raise AppException("VALIDATION_ERROR", "教学秘书必须是本校启用的教职工账号")
            if c.status != "ACTIVE":
                raise AppException("VALIDATION_ERROR", "学院已停用，不能新增或更换教学秘书；可解除原绑定")
        before = _college_dtos(db, [c])[0]
        if c.secretary_id == sid:
            return before
        c.secretary_id = sid
        c.version = int(c.version or 0) + 1
        db.flush()
        after = _college_dtos(db, [c])[0]
        _audit(db, "AA_ORG_COLLEGE", c.id, "BIND_SECRETARY", c.college_name,
               before=str({k: before[k] for k in ("secretaryId", "secretaryName", "version")}),
               after=str({k: after[k] for k in ("secretaryId", "secretaryName", "version")}))
        db.commit()
        return after


def delete_college(user, college_id) -> dict:
    from app.services.org_master_service import soft_delete_org_node
    with session() as db:
        ctx = _ctx(user, db)
        c = _get_college(db, college_id, for_update=True)
        _require_college_write(ctx, db, c.id)
        name = c.college_name
        result = soft_delete_org_node(node_type="COLLEGE", node_id=int(college_id), actor=user, reason="教务删除学院", db=db)
        _audit(db, "AA_ORG_COLLEGE", int(college_id), "DELETE", name)
        db.commit()
        return result


# ═══════════ 专业 ═══════════

def _major_dto(m, college_name=None) -> dict:
    return {"id": str(m.id), "collegeId": str(m.college_id), "collegeName": college_name,
            "majorName": m.major_name, "code": m.code, "educationYears": m.education_years,
            "trainingLevel": m.training_level, "enrollStatus": m.enroll_status,
            "direction": m.direction, "status": m.status, "remark": m.remark, "version": int(m.version or 0)}


def list_majors(user, college_id=None, enroll_status=None, keyword=None, page=1, page_size=50):
    from app.models import College, Major
    with session() as db:
        ctx = _ctx(user, db)
        allowed = _allowed_major_ids(ctx, db)
        if allowed is not None and not allowed:
            return [], 0
        conds = [Major.tenant_id == _tid(), Major.is_deleted.is_(False)]
        if allowed is not None:
            conds.append(Major.id.in_(list(allowed)))
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
    from app.services.org_master_service import apply_org_node_in_session
    from app.services.db_service import audit_insert_in_session
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
        extras = {
            "education_years": years,
            "training_level": getattr(body, "trainingLevel", None),
            "enroll_status": enroll,
            "direction": getattr(body, "direction", None),
            "remark": getattr(body, "remark", None),
        }
        result = apply_org_node_in_session(db, node_type="MAJOR", name=name,
            code=(getattr(body, "code", None) or ""), parent_id=int(college_id), actor=user, extras=extras)
        m = result['row']
        _audit(db, "AA_ORG_MAJOR", m.id, "CREATE", name)
        audit_insert_in_session(db, 'ORG_NODE_SAVE', f'MAJOR:{m.id}',
            {'name': m.major_name, 'code': m.code, 'before': None, 'reason': '',
             'moduleCode': 'systemAdmin', 'actor': (user or {}).get('userId'), 'extras': extras},
            'SUCCESS', tenant_id=_tid())
        db.commit()
        return _major_dto(m)


def update_major(user, major_id, body) -> dict:
    """按锁定后的当前归属授权，主数据、版本与两类审计一并提交。"""
    from app.services.org_master_service import apply_org_node_in_session
    from app.services.db_service import audit_insert_in_session
    with session() as db:
        ctx = _ctx(user, db)
        m = _get_major(db, major_id, for_update=True)
        _require_college_write(ctx, db, m.college_id)
        before = _major_dto(m)
        name = getattr(body, "majorName", None)
        code = body.code if "code" in body.model_fields_set else before["code"]
        expected = getattr(body, "expectedVersion", None)
        if expected is not None and int(m.version or 0) != int(expected):
            raise AppException('DATA_CONFLICT', '专业资料已被他人修改，请重新核对',
                details={'reason': 'VERSION_CONFLICT', 'currentVersion': int(m.version or 0)})
        yrs = getattr(body, "educationYears", None)
        if yrs is not None:
            yrs = int(yrs)
            if yrs < 1 or yrs > 10:
                raise AppException("VALIDATION_ERROR", "学制须在 1~10 年之间")
        es = getattr(body, "enrollStatus", None)
        if es is not None and es not in _MAJOR_ENROLL:
            raise AppException("VALIDATION_ERROR", "招生状态非法")
        parent_id = getattr(body, "collegeId", None)
        if parent_id is not None:
            destination = _get_college(db, parent_id)
            _require_college_write(ctx, db, destination.id)
            if destination.id == m.college_id:
                parent_id = None
        reason = str(getattr(body, "reason", None) or "").strip()
        extras = {attr: getattr(body, field) for field, attr in {
            "educationYears": "education_years", "trainingLevel": "training_level",
            "direction": "direction", "remark": "remark", "status": "status", "enrollStatus": "enroll_status",
        }.items() if field in body.model_fields_set}
        apply_org_node_in_session(db, node_type="MAJOR",
            name=(str(name).strip() if name is not None else before["majorName"]),
            code=("" if code is None else str(code).strip()),
            parent_id=(int(parent_id) if parent_id is not None else None),
            node_id=int(major_id), reason=reason, expected_version=int(m.version or 0),
            actor=user, extras=extras)
        _audit(db, "AA_ORG_MAJOR", m.id, "UPDATE", f'{m.major_name}；{reason}' if reason else m.major_name,
               before=str(before), after=str(_major_dto(m)))
        audit_insert_in_session(db, 'ORG_NODE_SAVE', f'MAJOR:{m.id}',
            {'name': m.major_name, 'code': m.code, 'before': before, 'reason': reason,
             'moduleCode': 'systemAdmin', 'actor': (user or {}).get('userId'), 'extras': extras},
            'SUCCESS', tenant_id=_tid())
        db.commit()
        return _major_dto(m)


def delete_major(user, major_id) -> dict:
    from app.services.org_master_service import soft_delete_org_node
    with session() as db:
        ctx = _ctx(user, db)
        m = _get_major(db, major_id, for_update=True)
        _require_college_write(ctx, db, m.college_id)
        name = m.major_name
        result = soft_delete_org_node(node_type="MAJOR", node_id=int(major_id), actor=user, reason="教务删除专业", db=db)
        _audit(db, "AA_ORG_MAJOR", int(major_id), "DELETE", name)
        db.commit()
        return result


# ═══════════ 行政班 ═══════════

def _class_dto(c, major_name=None) -> dict:
    return {"id": str(c.id), "majorId": str(c.major_id), "majorName": major_name,
            "className": c.class_name, "classCode": c.class_code, "grade": c.grade,
            "capacity": c.capacity, "graduateYear": c.graduate_year, "classStatus": c.class_status,
            "counselorId": str(c.counselor_id) if c.counselor_id else None,
            "headTeacherId": str(c.head_teacher_id) if c.head_teacher_id else None,
            "status": c.status, "remark": c.remark, "version": int(c.version or 0)}


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
        allowed = _allowed_class_ids(ctx, db)
        conds = [SchoolClass.tenant_id == _tid(), SchoolClass.is_deleted.is_(False)]
        if allowed is not None:
            if not allowed:
                return [], 0
            conds.append(SchoolClass.id.in_(list(allowed)))
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
    class_status = (getattr(body, "classStatus", None) or "NORMAL")
    if class_status not in _CLASS_STATUS:
        raise AppException("VALIDATION_ERROR", "班级状态非法")
    with session() as db:
        ctx = _ctx(user, db)
        m = _get_major(db, major_id)
        _require_college_write(ctx, db, m.college_id)
    from app.services.org_master_service import save_org_node
    extras = {
        "grade": getattr(body, "grade", None),
        "capacity": (int(cap) if cap is not None else None),
        "graduate_year": getattr(body, "graduateYear", None),
        "class_status": class_status,
        "remark": getattr(body, "remark", None),
    }
    if getattr(body, "counselorId", "__omit__") != "__omit__":
        extras["counselor_id"] = int(body.counselorId) if body.counselorId else None
    if getattr(body, "headTeacherId", "__omit__") != "__omit__":
        extras["head_teacher_id"] = int(body.headTeacherId) if body.headTeacherId else None
    result = save_org_node(
        node_type="CLASS", name=name,
        code=(getattr(body, "classCode", None) or ""),
        parent_id=int(major_id), actor=user,
        extras=extras,
    )
    with session() as db:
        c = db.get(SchoolClass, int(result["id"]))
        scope_note = _sync_counselor_scope(db, c, None) if c.counselor_id else ""
        _audit(db, "AA_ORG_CLASS", c.id, "CREATE", f"{name}({scope_note})" if scope_note else name)
        db.commit()
        return _class_dto(c)


def _sync_counselor_scope(db, c, old_counselor_id) -> str:
    """辅导员绑定变更后同步 t_teacher_student_scope（历史欠账 CL-1 残余收口）。

    学工数据范围完全由 scope 表驱动（affairs_security.build_affairs_context）——此前改绑只写
    SchoolClass.counselor_id 不动 scope，导致旧辅导员仍看得到该班、新辅导员 fail-closed 看不到。
    口径与 school_onboarding_service 一致：teacher_key=登录名、role_code=COUNSELOR、
    scope_type=CLASS、ref_value=班级名。撤旧行兼容 teacher_key=登录名或 userId 两种历史口径。
    新辅导员 User 不存在时不写 scope（保持既有 API 的宽松行为），在审计里如实标注。"""
    from app.models import TeacherStudentScope, User
    notes = []
    # 撤旧：旧辅导员对本班的 CLASS scope 置 INACTIVE（软撤留痕，不物理删）
    if old_counselor_id:
        old_u = db.get(User, int(old_counselor_id))
        old_keys = [str(old_counselor_id)] + ([old_u.login_name] if old_u else [])
        for row in db.scalars(select(TeacherStudentScope).where(
                TeacherStudentScope.tenant_id == _tid(),
                TeacherStudentScope.teacher_key.in_(old_keys),
                TeacherStudentScope.role_code == "COUNSELOR",
                TeacherStudentScope.scope_type == "CLASS",
                TeacherStudentScope.ref_value == c.class_name,
                TeacherStudentScope.status == "ACTIVE",
                TeacherStudentScope.is_deleted.is_(False))).all():
            row.status, row.version = "INACTIVE", int(row.version or 0) + 1
            notes.append(f"撤旧scope:{row.teacher_key}")
    # 立新：新辅导员 upsert 本班 CLASS scope
    if c.counselor_id:
        new_u = db.get(User, int(c.counselor_id))
        if new_u and not new_u.is_deleted and new_u.tenant_id == _tid():
            existing = db.scalars(select(TeacherStudentScope).where(
                TeacherStudentScope.tenant_id == _tid(),
                TeacherStudentScope.teacher_key == new_u.login_name,
                TeacherStudentScope.role_code == "COUNSELOR",
                TeacherStudentScope.scope_type == "CLASS",
                TeacherStudentScope.ref_value == c.class_name)).first()
            if existing:
                existing.is_deleted, existing.status = False, "ACTIVE"
                existing.version = int(existing.version or 0) + 1
            else:
                db.add(TeacherStudentScope(tenant_id=_tid(), teacher_key=new_u.login_name,
                                           teacher_name=new_u.real_name, role_code="COUNSELOR",
                                           scope_type="CLASS", ref_value=c.class_name,
                                           status="ACTIVE"))
            notes.append(f"立新scope:{new_u.login_name}")
        else:
            notes.append(f"新辅导员user_id={c.counselor_id}不存在,未写scope")
    return ";".join(notes)


def _lock_class_parent(db, ctx, c):
    from app.models import Major, College
    major = db.scalar(select(Major).where(Major.id == c.major_id, Major.tenant_id == _tid())
        .execution_options(populate_existing=True).with_for_update())
    college = db.scalar(select(College).where(College.id == major.college_id, College.tenant_id == _tid())
        .execution_options(populate_existing=True).with_for_update()) if major else None
    _require_college_write(ctx, db, major.college_id if major else None)
    return major, college


def _class_state_impact(db, ctx, c, target_status, target_active_status=None):
    import hashlib
    import json
    from app.services.org_class_lifecycle_service import read_class_references, closing_blockers, reference_snapshot

    if target_status not in _CLASS_STATUS:
        raise AppException('VALIDATION_ERROR', '请选择有效的班级状态')
    major, college = _lock_class_parent(db, ctx, c)
    students, tasks, counts, task_counts = read_class_references(db, _tid(), [c.id])
    active_status = target_active_status if target_active_status is not None else c.status
    blockers = closing_blockers(counts.get(c.id, 0), task_counts.get(c.id, 0)) if target_status != 'NORMAL' or active_status != 'ACTIVE' else []
    if not major or major.is_deleted or major.status != 'ACTIVE' or not college or college.is_deleted or college.status != 'ACTIVE':
        blockers.append('所属专业或学院不可用，请先处理组织归属')
    snapshot = {
        'class': [c.id, c.version, c.major_id, c.class_status, c.status, c.is_deleted],
        'target': [target_status, active_status],
        'major': [major.id, major.version, major.college_id, major.status, major.is_deleted] if major else None,
        'college': [college.id, college.version, college.status, college.is_deleted] if college else None,
        **reference_snapshot(students, tasks),
    }
    return {'classId': str(c.id), 'className': c.class_name, 'version': int(c.version or 0),
            'currentStatus': c.class_status, 'targetStatus': target_status,
            'activeStudentCount': counts.get(c.id, 0), 'openTaskCount': task_counts.get(c.id, 0),
            'blocked': bool(blockers), 'blockers': blockers,
            'snapshotHash': hashlib.sha256(json.dumps(snapshot, sort_keys=True, separators=(',', ':')).encode()).hexdigest()}


def preview_class_state(user, class_id, body) -> dict:
    with session() as db:
        ctx = _ctx(user, db)
        c = _get_class(db, class_id, for_update=True)
        _require_college_write(ctx, db, _class_college_id(db, c.id))
        expected = getattr(body, 'expectedVersion', None)
        if expected is not None and int(c.version or 0) != int(expected):
            raise AppException('DATA_CONFLICT', '组织数据已被他人修改，请刷新后重试')
        return _class_state_impact(db, ctx, c, getattr(body, 'classStatus', None))


def update_class(user, class_id, body) -> dict:
    """范围、统一主数据、教师范围与审计在同一事务内完成。"""
    from app.models import TeacherStudentScope
    from app.services.org_master_service import apply_org_node_in_session
    from app.services.db_service import audit_insert_in_session
    with session() as db:
        ctx = _ctx(user, db)
        c = _get_class(db, class_id, for_update=True)
        _require_college_write(ctx, db, _class_college_id(db, c.id))
        before = _class_dto(c)
        old_class_name, old_counselor_id = c.class_name, c.counselor_id
        name = getattr(body, "className", None)
        code = body.classCode if "classCode" in body.model_fields_set else before["classCode"]
        expected = getattr(body, "expectedVersion", None)
        if expected is not None and int(c.version or 0) != int(expected):
            raise AppException('DATA_CONFLICT', '组织数据已被他人修改，请刷新后重试')
        parent_id = getattr(body, "majorId", None)
        if parent_id is not None:
            destination = _get_major(db, parent_id)
            _require_college_write(ctx, db, destination.college_id)
            if destination.id == c.major_id:
                parent_id = None
        reason = str(getattr(body, "reason", None) or "").strip()
        cap = getattr(body, "capacity", None)
        if cap is not None and int(cap) < 0:
            raise AppException("VALIDATION_ERROR", "编制人数不能为负")
        cs = getattr(body, "classStatus", None)
        if cs is not None and cs not in _CLASS_STATUS:
            raise AppException("VALIDATION_ERROR", "班级状态非法")
        active_status = getattr(body, 'status', None)
        state_changed = (cs is not None and cs != c.class_status) or (active_status is not None and active_status != c.status)
        if state_changed:
            if len(reason) < 5:
                raise AppException('VALIDATION_ERROR', '班级状态变更须填写原因（至少5字）')
            checked = _class_state_impact(db, ctx, c, cs if cs is not None else (c.class_status or 'NORMAL'), active_status)
            fingerprint = getattr(body, 'expectedStateSnapshotHash', None)
            if fingerprint and fingerprint != checked['snapshotHash']:
                raise AppException('DATA_CONFLICT', '班级、学生或教学任务已变化，请重新核对后保存')
            if checked['blocked']:
                raise AppException('VALIDATION_ERROR', '；'.join(checked['blockers']), details=checked)
        extras = {attr: getattr(body, field) for field, attr in {
            "grade": "grade", "graduateYear": "graduate_year", "remark": "remark", "status": "status",
            "capacity": "capacity", "classStatus": "class_status",
        }.items() if field in body.model_fields_set}
        if "counselorId" in body.model_fields_set:
            extras["counselor_id"] = int(body.counselorId) if body.counselorId else None
        if "headTeacherId" in body.model_fields_set:
            extras["head_teacher_id"] = int(body.headTeacherId) if body.headTeacherId else None
        apply_org_node_in_session(db, node_type="CLASS",
            name=(str(name).strip() if name is not None else before["className"]),
            code=("" if code is None else str(code).strip()),
            parent_id=(int(parent_id) if parent_id is not None else None), node_id=int(class_id),
            reason=reason, expected_version=int(c.version or 0), actor=user, extras=extras)
        scope_notes = ""
        if c.class_name != old_class_name:
            for row in db.scalars(select(TeacherStudentScope).where(
                    TeacherStudentScope.tenant_id == _tid(),
                    TeacherStudentScope.scope_type == "CLASS",
                    TeacherStudentScope.ref_value == old_class_name,
                    TeacherStudentScope.is_deleted.is_(False))).all():
                row.ref_value, row.version = c.class_name, int(row.version or 0) + 1
            scope_notes = f"班名scope跟随:{old_class_name}->{c.class_name}"
        if "counselorId" in body.model_fields_set and \
                int(c.counselor_id or 0) != int(old_counselor_id or 0):
            note = _sync_counselor_scope(db, c, old_counselor_id)
            scope_notes = f"{scope_notes};{note}" if scope_notes else note
        _audit(db, "AA_ORG_CLASS", c.id, "UPDATE",
               f"{c.class_name}；{reason}；{scope_notes}" if reason or scope_notes else c.class_name,
               before=str(before), after=str(_class_dto(c)))
        audit_insert_in_session(db, 'ORG_NODE_SAVE', f'CLASS:{c.id}',
            {'name': c.class_name, 'code': c.class_code, 'before': before, 'reason': reason,
             'moduleCode': 'systemAdmin', 'actor': (user or {}).get('userId'), 'extras': extras},
            'SUCCESS', tenant_id=_tid())
        db.commit()
        return _class_dto(c)


def delete_class(user, class_id) -> dict:
    from app.services.org_master_service import soft_delete_org_node
    with session() as db:
        ctx = _ctx(user, db)
        c = _get_class(db, class_id, for_update=True)
        _require_college_write(ctx, db, _class_college_id(db, c.id))
        _lock_class_parent(db, ctx, c)
        name = c.class_name
        result = soft_delete_org_node(node_type="CLASS", node_id=int(class_id), actor=user, reason="教务删除班级", db=db)
        _audit(db, "AA_ORG_CLASS", int(class_id), "DELETE", name)
        db.commit()
        return result


# ═══════════ 年级（聚合，非独立表）═══════════

def list_grades(user, college_id=None, major_id=None):
    """按 t_class.grade 聚合：每个年级班级数 / 学生数（在范围内）。"""
    from app.models import Major, SchoolClass, StudentProfile
    with session() as db:
        ctx = _ctx(user, db)
        allowed = _allowed_class_ids(ctx, db)
        conds = [SchoolClass.tenant_id == _tid(), SchoolClass.is_deleted.is_(False),
                 SchoolClass.grade.is_not(None)]
        if allowed is not None:
            if not allowed:
                return {"items": []}
            conds.append(SchoolClass.id.in_(list(allowed)))
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

def list_teaching_classes(user, term_code=None, batch_id=None, page=1, page_size=50, *, term_id=None, keyword=None):
    """Read the existing formal projection, with legacy task fields as migration fallback."""
    from app.models import AaTeachingClass, AaTeachingTask, AaTeachingTaskBatch, AaTerm
    with session() as db:
        allowed = _allowed_class_ids(_ctx(user, db), db)
        if allowed is not None and not allowed:
            return [], 0
        conds = [AaTeachingTask.tenant_id == _tid(), AaTeachingTask.is_deleted.is_(False),
                 AaTeachingTask.status != "MERGED",
                 AaTeachingTaskBatch.is_deleted.is_(False), AaTerm.is_deleted.is_(False),
                 func.coalesce(AaTeachingClass.class_code, AaTeachingTask.teaching_class_code).is_not(None)]
        if allowed is not None:
            conds.append(AaTeachingTask.class_id.in_(list(allowed)))
        if batch_id:
            conds.append(AaTeachingTask.batch_id == int(batch_id))
        if term_id:
            conds.append(AaTerm.id == int(term_id))
        if term_code:
            conds.append(func.concat(AaTerm.year_code, "-", AaTerm.term_no) == term_code)
        if keyword:
            like = f"%{keyword.strip()}%"
            conds.append(or_(AaTeachingTask.course_name.like(like),
                func.coalesce(AaTeachingClass.class_name, AaTeachingTask.teaching_class_name).like(like),
                func.coalesce(AaTeachingClass.class_code, AaTeachingTask.teaching_class_code).like(like)))
        rows = db.execute(select(AaTeachingTask, AaTeachingTaskBatch, AaTerm, AaTeachingClass)
            .join(AaTeachingTaskBatch, and_(AaTeachingTaskBatch.id == AaTeachingTask.batch_id,
                                           AaTeachingTaskBatch.tenant_id == AaTeachingTask.tenant_id))
            .join(AaTerm, and_(AaTerm.id == AaTeachingTaskBatch.term_id, AaTerm.tenant_id == AaTeachingTask.tenant_id))
            .outerjoin(AaTeachingClass, and_(AaTeachingClass.teaching_task_id == AaTeachingTask.id,
                AaTeachingClass.tenant_id == AaTeachingTask.tenant_id, AaTeachingClass.is_deleted.is_(False)))
            .where(*conds).order_by(AaTerm.year_code.desc(), AaTerm.term_no.desc(), AaTeachingTask.batch_id, AaTeachingTask.id)).all()
        agg = {}
        course_ids = {}
        for t, batch, term, formal in rows:
            code = formal.class_code if formal else t.teaching_class_code
            key = f"formal:{formal.id}" if formal else f"batch:{batch.id}:{code}"
            it = agg.setdefault(key, {"id": key, "teachingClassId": str(formal.id) if formal else None,
                "teachingClassCode": code, "teachingClassName": formal.class_name if formal else t.teaching_class_name,
                "termId": str(term.id), "termName": term.term_name or f"{term.year_code} 第{term.term_no}学期",
                "batchId": str(batch.id), "batchName": batch.batch_name,
                "isMerged": bool(t.is_merged), "courseCount": 0,
                "expectedStudents": formal.capacity if formal else t.expected_students, "courses": []})
            course_ids.setdefault(key, set()).add(t.course_id)
            it["courseCount"] = len(course_ids[key])
            it["isMerged"] = it["isMerged"] or bool(t.is_merged)
            if t.course_name and t.course_name not in it["courses"]:
                it["courses"].append(t.course_name)
        items = list(agg.values())
        total = len(items)
        offset = (max(1, page) - 1) * page_size
        return items[offset:offset + page_size], total


# ═══════════ 班级学生 + 班级调整 ═══════════

def list_class_students(user, class_id, keyword=None, page=1, page_size=50):
    """班级学生名册（07 号卡，只读）：学号/姓名/性别/学籍状态/手机号脱敏 + 关键字搜索。
    数据范围按当前授权的精确班级集合校验，手机号复用 db_service._primary_phone 同款脱敏口径
    （t_student_contact.contact_type=PHONE，演示环境明文占位、真实环境密文，脱敏在本函数内完成，
    不返回明文；本卡不提供明文解锁入口，见三级卡 §10）。"""
    from app.models import StudentContact, StudentProfile
    with session() as db:
        ctx = _ctx(user, db)
        c = _get_class(db, class_id)
        allowed = _allowed_class_ids(ctx, db)
        if allowed is not None and c.id not in allowed:
            raise no_data_scope("该班级不在您的查看范围内")
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
                  "phoneMasked": mask_phone_encrypted(pmap.get(s.id, "")),
                  "classId": str(s.class_id) if s.class_id else None, "version": int(s.version or 0)} for s in rows]
        return items, total


def adjust_student_class(user, body) -> dict:
    """Keep legacy direct callers on the same C1 fact command as the public router."""
    from .academic_affairs_org_fact_facade import adjust_student_class as command
    return command(user, body)


# ═══════════ 组织树 / 统计 / 变更审计 ═══════════

def _inspect_org(db, ctx, kind, node_id):
    from app.services.org_reference_check_service import check_org_references
    getters = {'COLLEGE': _get_college, 'MAJOR': _get_major, 'CLASS': _get_class}
    if kind not in getters:
        raise AppException('VALIDATION_ERROR', '请选择学院、专业或行政班')
    node = getters[kind](db, node_id)
    if kind == 'CLASS':
        allowed = _allowed_class_ids(ctx, db)
        if allowed is not None and node.id not in allowed:
            raise no_data_scope('该行政班不在您的管理范围内')
    else:
        # Parent paths visible to a class manager do not grant aggregate access.
        _require_college_write(ctx, db, node.id if kind == 'COLLEGE' else node.college_id)
    report = check_org_references(db, _tid(), kind, node)
    summary = '；'.join(f"{ref['label']}={ref['refCount']}" for ref in report['refs'])
    _audit(db, f'AA_ORG_{kind}', node.id, 'SYNC_CHECK', summary)
    return report


def get_org_reference_check(user, kind, node_id):
    with session() as db:
        report = _inspect_org(db, _ctx(user, db), kind, node_id)
        db.commit()
        return report


def list_org_reference_checks(user, kind=None, college_id=None, keyword=None, page=1, page_size=20):
    from sqlalchemy import literal, union_all
    from app.models import College, Major, SchoolClass
    if kind and kind not in {'COLLEGE', 'MAJOR', 'CLASS'}:
        raise AppException('VALIDATION_ERROR', '请选择学院、专业或行政班')
    with session() as db:
        ctx = _ctx(user, db)
        classes = _allowed_class_ids(ctx, db)
        queries = []
        for node_kind, model, name in [('COLLEGE', College, College.college_name),
                                       ('MAJOR', Major, Major.major_name),
                                       ('CLASS', SchoolClass, SchoolClass.class_name)]:
            if kind and kind != node_kind:
                continue
            conditions = [model.tenant_id == _tid(), model.is_deleted.is_(False)]
            if node_kind == 'CLASS':
                if classes is not None:
                    conditions.append(model.id.in_(classes))
                if college_id:
                    conditions.append(model.major_id.in_(select(Major.id).where(
                        Major.tenant_id == _tid(), Major.college_id == college_id)))
            else:
                parent = model.id if node_kind == 'COLLEGE' else model.college_id
                if ctx.scope_type != 'TENANT_ALL':
                    conditions.append(parent.in_(ctx.college_ids))
                if college_id:
                    conditions.append(parent == college_id)
            if keyword and keyword.strip():
                conditions.append(name.contains(keyword.strip(), autoescape=True))
            queries.append(select(literal(node_kind).label('kind'), model.id.label('id')).where(*conditions))
        targets = union_all(*queries).subquery()
        total = db.scalar(select(func.count()).select_from(targets)) or 0
        rows = db.execute(select(targets.c.kind, targets.c.id).order_by(targets.c.kind, targets.c.id)
            .offset((page - 1) * page_size).limit(page_size)).all()
        items = [_inspect_org(db, ctx, node_kind, node_id) for node_kind, node_id in rows]
        db.commit()
        return items, total


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
        allowed_majors = _allowed_major_ids(ctx, db)
        if allowed_majors is not None:
            majors = [m for m in majors if m.id in allowed_majors]
            maj_ids = [m.id for m in majors] or [0]
        classes = db.scalars(select(SchoolClass).where(
            SchoolClass.tenant_id == _tid(), SchoolClass.is_deleted.is_(False),
            SchoolClass.major_id.in_(maj_ids))).all()
        allowed_classes = _allowed_class_ids(ctx, db)
        if allowed_classes is not None:
            classes = [c for c in classes if c.id in allowed_classes]
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
    """组织统计：学院/专业/班级/学生档案计数 + 招生专业数 + 已毕业班数（范围内）。"""
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
            maj_conds.append(Major.id.in_(list(_allowed_major_ids(ctx, db) or set())))
            class_ids = list(_allowed_class_ids(ctx, db) or set())
            cls_conds.append(SchoolClass.id.in_(class_ids))
            stu_conds.append(StudentProfile.class_id.in_(class_ids))
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

def _direction_toggle_row(db, tenant_id: int, *, for_update=False):
    """总开关默认关闭（业务政策待学校确认，见三级卡 §3）；缺省行=未启用。"""
    from app.models import PlatformConfig
    stmt = select(PlatformConfig).where(
        PlatformConfig.tenant_id == tenant_id, PlatformConfig.config_type == _MD_CFG_TYPE,
        PlatformConfig.config_key == _MD_CFG_KEY)
    if for_update:
        stmt = stmt.execution_options(populate_existing=True).with_for_update()
    return db.scalar(stmt)


def _direction_toggle_dto(row):
    return {"enabled": bool(row and not row.is_deleted and row.enabled), "version": int(row.version or 0) if row else 0}


def _check_direction_version(row, expected):
    if expected is not None and int(expected) != int(row.version or 0):
        raise AppException("DATA_CONFLICT", "记录已被更新，请刷新后重试", {"reason": "VERSION_CONFLICT"})


def get_major_direction_toggle(user) -> dict:
    with session() as db:
        _ctx(user, db)
        return _direction_toggle_dto(_direction_toggle_row(db, _tid()))


def set_major_direction_toggle(user, enabled: bool, expected_version=None) -> dict:
    """仅教务处/校管（TENANT_ALL 范围）可切换总开关；学院教务无此权限。"""
    from app.models import PlatformConfig
    from sqlalchemy.dialects.mysql import insert
    with session() as db:
        ctx = _ctx(user, db)
        if _allowed_college_ids(ctx, db) is not None:
            raise no_data_scope("仅教务处/校管可设置专业方向总开关")
        # Materialize only on an authorized write. The unique key serializes first-time
        # switches as well as existing rows; GET never creates a configuration record.
        db.execute(insert(PlatformConfig).values(tenant_id=_tid(), config_type=_MD_CFG_TYPE,
            config_key=_MD_CFG_KEY, config_json={}, enabled=False).on_duplicate_key_update(id=PlatformConfig.id))
        row = _direction_toggle_row(db, _tid(), for_update=True)
        _check_direction_version(row, expected_version)
        before = _direction_toggle_dto(row)
        if bool(row.enabled) == bool(enabled) and not row.is_deleted:
            db.commit()
            return before
        row.enabled = bool(enabled)
        row.is_deleted = False
        row.version = int(row.version or 0) + 1
        db.flush()
        _audit(db, "AA_ORG_MAJOR_DIRECTION", None, "TOGGLE", f"总开关→{'启用' if enabled else '停用'}",
               before=str(before), after=str(_direction_toggle_dto(row)))
        db.commit()
        return _direction_toggle_dto(row)


def _require_direction_enabled(db, *, for_update=False):
    if not _direction_toggle_dto(_direction_toggle_row(db, _tid(), for_update=for_update))["enabled"]:
        raise AppException("FEATURE_DISABLED", "专业方向总开关未启用，请联系教务处/校管开启")


def _direction_dto(d) -> dict:
    return {"id": str(d.id), "majorId": str(d.major_id), "directionName": d.direction_name,
            "code": d.code, "status": d.status, "version": int(d.version or 0)}


def _direction_write_major(db, ctx, major_id):
    from app.models import College, Major
    # Read the current parent under locks, then authorize that parent, not an old snapshot.
    m = db.scalar(select(Major).where(Major.id == int(major_id), Major.tenant_id == _tid())
                  .execution_options(populate_existing=True).with_for_update())
    if not m or m.is_deleted:
        raise not_found("专业不存在")
    c = db.scalar(select(College).where(College.id == m.college_id, College.tenant_id == _tid())
                  .execution_options(populate_existing=True).with_for_update())
    _require_college_write(ctx, db, m.college_id)
    if not c or c.is_deleted:
        raise not_found("所属学院不存在")
    if m.status != "ACTIVE" or c.status != "ACTIVE":
        raise AppException("VALIDATION_ERROR", "所属学院或专业已停用，不能维护方向")
    return m


def _check_direction_code(db, major_id, code, direction_id=None):
    from app.models import AaMajorDirection
    if not code:
        return
    stmt = select(AaMajorDirection.id).where(AaMajorDirection.tenant_id == _tid(),
        AaMajorDirection.major_id == major_id, AaMajorDirection.code == code)
    if direction_id is not None:
        stmt = stmt.where(AaMajorDirection.id != direction_id)
    # Historical codes are still reserved by the existing unique database constraint.
    if db.scalar(stmt.with_for_update()) is not None:
        raise AppException("DATA_CONFLICT", "该专业下同编码方向已存在（含历史记录）")


def list_directions(user, major_id, page=1, page_size=50):
    from app.models import AaMajorDirection
    with session() as db:
        ctx = _ctx(user, db)
        _require_direction_enabled(db)
        m = _get_major(db, major_id)
        allowed = _allowed_major_ids(ctx, db)
        if allowed is not None and m.id not in allowed:
            raise no_data_scope("该专业不在您的查看范围内")
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
        _require_direction_enabled(db, for_update=True)
        m = _direction_write_major(db, ctx, major_id)
        code = (getattr(body, "code", None) or "").strip() or None
        _check_direction_code(db, m.id, code)
        d = AaMajorDirection(tenant_id=_tid(), major_id=m.id, direction_name=name, code=code, status="ACTIVE")
        db.add(d)
        db.flush()
        _audit(db, "AA_ORG_MAJOR_DIRECTION", d.id, "DIRECTION_CREATE", name)
        db.commit()
        db.refresh(d)
        return _direction_dto(d)


def _get_direction(db, major_id, direction_id):
    from app.models import AaMajorDirection
    d = db.scalar(select(AaMajorDirection).where(AaMajorDirection.id == int(direction_id or 0),
        AaMajorDirection.tenant_id == _tid(), AaMajorDirection.major_id == int(major_id))
        .execution_options(populate_existing=True).with_for_update())
    if not d or getattr(d, "is_deleted", False) or d.tenant_id != _tid() or d.major_id != int(major_id):
        raise not_found("专业方向不存在")
    return d


def update_direction(user, major_id, direction_id, body) -> dict:
    with session() as db:
        ctx = _ctx(user, db)
        _require_direction_enabled(db, for_update=True)
        m = _direction_write_major(db, ctx, major_id)
        d = _get_direction(db, major_id, direction_id)
        _check_direction_version(d, getattr(body, "expectedVersion", None))
        if d.status != "ACTIVE":
            raise AppException("DATA_CONFLICT", "已停用方向仅保留历史，不允许编辑", {"reason": "INVALID_STATE"})
        before = _direction_dto(d)
        name = getattr(body, "directionName", None)
        if name is not None:
            if not str(name).strip():
                raise AppException("VALIDATION_ERROR", "方向名称不能为空")
            d.direction_name = str(name).strip()
        if "code" in body.model_fields_set:
            code = (body.code or "").strip() or None
            _check_direction_code(db, m.id, code, d.id)
            d.code = code
        d.version = int(d.version or 0) + 1
        db.flush()
        _audit(db, "AA_ORG_MAJOR_DIRECTION", d.id, "DIRECTION_UPDATE", d.direction_name,
               before=str(before), after=str(_direction_dto(d)))
        db.commit()
        db.refresh(d)
        return _direction_dto(d)


def disable_direction(user, major_id, direction_id, expected_version=None) -> dict:
    with session() as db:
        ctx = _ctx(user, db)
        _require_direction_enabled(db, for_update=True)
        _direction_write_major(db, ctx, major_id)
        d = _get_direction(db, major_id, direction_id)
        if d.status == "DISABLED":
            return _direction_dto(d)  # 幂等
        _check_direction_version(d, expected_version)
        before = _direction_dto(d)
        d.status = "DISABLED"
        d.version = int(d.version or 0) + 1
        db.flush()
        _audit(db, "AA_ORG_MAJOR_DIRECTION", d.id, "DIRECTION_DISABLE", d.direction_name,
               before=str(before), after=str(_direction_dto(d)))
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
        "version": int(a.version or 0),
        "checkExpiresAt": (a.checked_at + timedelta(hours=_ADJUST_CHECK_TTL_HOURS)).isoformat() if a.checked_at else None,
    }


def _get_adjustment(db, adjustment_id, ctx):
    from app.models import AaClassAdjustmentRequest
    a = db.scalars(select(AaClassAdjustmentRequest).where(
        AaClassAdjustmentRequest.id == int(adjustment_id), AaClassAdjustmentRequest.tenant_id == _tid(),
        AaClassAdjustmentRequest.is_deleted.is_(False)).with_for_update()).first() if adjustment_id else None
    if not a or getattr(a, "is_deleted", False) or a.tenant_id != _tid():
        raise not_found("调整申请单不存在")
    if not _visible_adjustment_rows([a], _allowed_class_ids(ctx, db)):
        raise no_data_scope("该调整申请不在您的管理范围内")
    for college_id in _adjustment_colleges(db, a):
        _require_college_write(ctx, db, college_id)
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


def _visible_adjustment_rows(rows, class_ids):
    """An unresolved or partly unauthorized application must not become visible."""
    import json
    if class_ids is None:
        return rows
    result = []
    for row in rows:
        try:
            ids = {int(value) for value in json.loads(row.from_class_ids or "[]")}
        except (TypeError, ValueError):
            continue
        if not ids:
            continue
        if row.to_class_id:
            ids.add(row.to_class_id)
        if ids.issubset(class_ids):
            result.append(row)
    return result


def list_class_adjustments(user, status=None, adjust_type=None, page=1, page_size=50):
    import json
    from app.models import AaClassAdjustmentRequest
    with session() as db:
        ctx = _ctx(user, db)
        allowed = _allowed_class_ids(ctx, db)
        conds = [AaClassAdjustmentRequest.tenant_id == _tid(), AaClassAdjustmentRequest.is_deleted.is_(False)]
        if status:
            conds.append(AaClassAdjustmentRequest.status == status)
        if adjust_type:
            conds.append(AaClassAdjustmentRequest.adjust_type == adjust_type)
        rows = db.scalars(select(AaClassAdjustmentRequest).where(*conds)
                          .order_by(AaClassAdjustmentRequest.id.desc())).all()
        filtered = _visible_adjustment_rows(rows, allowed)
        total = len(filtered)
        offset = (max(1, page) - 1) * page_size
        page_rows = filtered[offset:offset + page_size]
        all_ids = set()
        for row in page_rows:
            all_ids.update(int(value) for value in json.loads(row.from_class_ids or "[]"))
            if row.to_class_id:
                all_ids.add(row.to_class_id)
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
        from_ids = sorted({int(x) for x in from_ids_raw})
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "来源班级参数非法")
    if not from_ids or any(value <= 0 for value in from_ids) or len(from_ids) > 500:
        raise AppException("VALIDATION_ERROR", "请选择1至500个有效来源班级")
    to_id_raw = getattr(body, "toClassId", None)
    try:
        to_id = int(to_id_raw) if to_id_raw else None
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "目标班级参数非法")
    if to_id is not None and (to_id <= 0 or adjust_type != "MERGE"):
        raise AppException("VALIDATION_ERROR", "仅合班登记可以指定有效目标班级")
    if adjust_type == "MERGE" and not to_id:
        raise AppException("VALIDATION_ERROR", "合班登记必须指定目标班级")
    if to_id and to_id in from_ids:
        raise AppException("VALIDATION_ERROR", "目标班级不能同时是来源班级")
    reason = (getattr(body, "reason", None) or "").strip()
    if len(reason) < 5 or len(reason) > 1000:
        raise AppException("VALIDATION_ERROR", "调整理由需为5至1000个字符")
    with session() as db:
        ctx = _ctx(user, db)
        all_ids = set(from_ids) | ({to_id} if to_id else set())
        classes = {c.id: c for c in db.scalars(select(SchoolClass).where(
            SchoolClass.tenant_id == _tid(), SchoolClass.is_deleted.is_(False),
            SchoolClass.id.in_(list(all_ids))).order_by(SchoolClass.id).with_for_update()).all()}
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
            if classes[cid].class_status != "NORMAL" or classes[cid].status != "ACTIVE":
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


def _require_adjustment_version(a, expected_version):
    if expected_version is not None and int(a.version or 0) != int(expected_version):
        raise AppException("DATA_CONFLICT", "申请或核对结果已更新，请刷新后重新核对")


def _check_class_adjustment(db, ctx, a):
    """Lock current references and derive one snapshot for both precheck and execute.

    Under MySQL REPEATABLE READ isolation, the indexed student/task
    locking reads also protect matching empty ranges during this transaction.
    """
    import hashlib
    import json
    from app.models import College, Major, SchoolClass
    from app.services.org_class_lifecycle_service import read_class_references, closing_blockers, reference_snapshot

    source_ids = {int(value) for value in json.loads(a.from_class_ids or "[]")}
    ids = source_ids | ({a.to_class_id} if a.to_class_id else set())
    classes = {row.id: row for row in db.scalars(select(SchoolClass).where(
        SchoolClass.tenant_id == _tid(), SchoolClass.id.in_(sorted(ids)))
        .order_by(SchoolClass.id).with_for_update()).all()}
    major_ids = {row.major_id for row in classes.values() if row.major_id}
    majors = {row.id: row for row in db.scalars(select(Major).where(
        Major.tenant_id == _tid(), Major.id.in_(sorted(major_ids)))
        .order_by(Major.id).with_for_update()).all()}
    college_ids = {row.college_id for row in majors.values() if row.college_id}
    colleges = {row.id: row for row in db.scalars(select(College).where(
        College.tenant_id == _tid(), College.id.in_(sorted(college_ids)))
        .order_by(College.id).with_for_update()).all()}
    for college_id in college_ids:
        _require_college_write(ctx, db, college_id)

    students, tasks, counts, task_counts = read_class_references(db, _tid(), ids)

    refs, snapshot_classes = [], []
    for cid in sorted(ids):
        row = classes.get(cid)
        major = majors.get(row.major_id) if row else None
        college = colleges.get(major.college_id) if major else None
        blockers = []
        if not row or row.is_deleted:
            blockers.append("班级已删除或不存在，请撤销后重新选择")
        elif row.status != "ACTIVE" or row.class_status != "NORMAL":
            blockers.append("班级已停用或毕业，请重新确认调整范围")
        if not major or major.is_deleted or major.status != "ACTIVE" or not college or college.is_deleted or college.status != "ACTIVE":
            blockers.append("所属专业或学院不可用，请先处理组织归属")
        closing_source = cid in source_ids and a.adjust_type in {"MERGE", "DISBAND", "GRADUATE_CLEAR"}
        if closing_source:
            blockers.extend(closing_blockers(counts.get(cid, 0), task_counts.get(cid, 0)))
        if a.adjust_type == "MERGE" and len(college_ids) > 1:
            blockers.append("合班来源与目标需属于同一学院")
        refs.append({"classId": str(cid), "className": row.class_name if row else "",
                     "isTarget": cid == a.to_class_id, "activeStudentCount": counts.get(cid, 0),
                     "openTaskCount": task_counts.get(cid, 0), "blockers": blockers})
        snapshot_classes.append([cid, row.version if row else None, row.class_status if row else None,
            row.status if row else None, row.is_deleted if row else None,
            major.id if major else None, major.college_id if major else None,
            major.version if major else None, major.status if major else None, major.is_deleted if major else None,
            college.version if college else None, college.status if college else None, college.is_deleted if college else None])
    snapshot = {
        "classes": snapshot_classes,
        **reference_snapshot(students, tasks),
    }
    fingerprint = hashlib.sha256(json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"blocked": any(ref["blockers"] for ref in refs), "refs": refs,
            "snapshotVersion": 1, "snapshotHash": fingerprint}, classes


def precheck_class_adjustment(user, adjustment_id, expected_version=None) -> dict:
    import json
    with session() as db:
        ctx = _ctx(user, db)
        a = _get_adjustment(db, adjustment_id, ctx)
        _require_adjustment_version(a, expected_version)
        if a.status not in ("DRAFT", "CHECKED"):
            raise AppException("DATA_CONFLICT", "仅草稿/已核对状态可（重新）核对")
        result, classes = _check_class_adjustment(db, ctx, a)
        a.check_result_json = json.dumps(result, ensure_ascii=False)
        a.checked_at = datetime.utcnow()
        a.status = "CHECKED"
        a.version = int(a.version or 0) + 1
        db.flush()
        _audit(db, "AA_ORG_CLASS_ADJUST_REQUEST", a.id, "SYNC_CHECK", "存在待处理事项" if result["blocked"] else "核对通过")
        db.commit()
        db.refresh(a)
        cmap = {cid: row.class_name for cid, row in classes.items()}
        return _adjustment_dto(a, cmap)


def execute_class_adjustment(user, adjustment_id, expected_version=None) -> dict:
    import json
    from app.services.org_master_service import apply_org_node_in_session
    with session() as db:
        ctx = _ctx(user, db)
        a = _get_adjustment(db, adjustment_id, ctx)
        from_ids = [int(x) for x in json.loads(a.from_class_ids or "[]")]
        if a.status == "EXECUTED":  # 幂等：重复执行直接返回已执行状态
            cmap = _adjustment_class_names(db, from_ids + ([a.to_class_id] if a.to_class_id else []))
            return _adjustment_dto(a, cmap)
        _require_adjustment_version(a, expected_version)
        if a.status != "CHECKED":
            raise AppException("DATA_CONFLICT", "仅已核对状态可执行")
        if not a.checked_at or (datetime.utcnow() - a.checked_at).total_seconds() > _ADJUST_CHECK_TTL_HOURS * 3600:
            raise AppException("DATA_CONFLICT", "核对结果已过期（超过24小时），请重新核对")
        result = json.loads(a.check_result_json or "{}")
        if result.get("blocked"):
            raise AppException("VALIDATION_ERROR", "核对结果存在阻断项，无法执行")
        if result.get("snapshotVersion") != 1 or not result.get("snapshotHash"):
            raise AppException("DATA_CONFLICT", "旧核对记录缺少完整影响快照，请重新核对")
        current, classes = _check_class_adjustment(db, ctx, a)
        if current["snapshotHash"] != result["snapshotHash"]:
            raise AppException("DATA_CONFLICT", "班级、学生或教学任务已变化，请重新核对后执行")
        if current["blocked"]:
            raise AppException("VALIDATION_ERROR", "当前仍有待处理事项，请重新核对")
        new_status = {"MERGE": "DISBANDED", "DISBAND": "DISBANDED",
                      "GRADUATE_CLEAR": "GRADUATED"}.get(a.adjust_type)
        changed = 0
        if new_status:  # SPLIT is record-only; student facts remain owned by their existing command.
            for cid in sorted(set(from_ids)):
                cls = classes[cid]
                before = cls.class_status
                apply_org_node_in_session(db, node_type="CLASS", node_id=cid, name=cls.class_name,
                    code=cls.class_code, expected_version=int(cls.version or 0),
                    extras={"class_status": new_status}, tenant_id=_tid(), actor=user)
                changed += 1
                _audit(db, "AA_ORG_CLASS", cid, "UPDATE", f"班级调整申请 {a.id}：{a.reason}", before=before, after=new_status)
        result["execution"] = {"executedAt": datetime.utcnow().isoformat(), "changedClassCount": changed,
                               "studentMoveCount": 0, "classStatus": new_status}
        a.check_result_json = json.dumps(result, ensure_ascii=False)
        a.status = "EXECUTED"
        a.version = int(a.version or 0) + 1
        db.flush()
        _audit(db, "AA_ORG_CLASS_ADJUST_REQUEST", a.id, "ADJUST_EXECUTE", f"{a.adjust_type} executed")
        db.commit()
        db.refresh(a)
        cmap = _adjustment_class_names(db, from_ids + ([a.to_class_id] if a.to_class_id else []))
        return _adjustment_dto(a, cmap)


def cancel_class_adjustment(user, adjustment_id, expected_version=None) -> dict:
    with session() as db:
        ctx = _ctx(user, db)
        a = _get_adjustment(db, adjustment_id, ctx)
        _require_adjustment_version(a, expected_version)
        if a.status not in ("DRAFT", "CHECKED"):
            raise AppException("DATA_CONFLICT", "已执行/已撤销的申请单不可再撤销")
        for cg in _adjustment_colleges(db, a):
            _require_college_write(ctx, db, cg)
        a.status = "CANCELLED"
        a.version = int(a.version or 0) + 1
        db.flush()
        _audit(db, "AA_ORG_CLASS_ADJUST_REQUEST", a.id, "ADJUST_CANCEL", "撤销")
        db.commit()
        db.refresh(a)
        cmap = _adjustment_class_names(db, [])
        return _adjustment_dto(a, cmap)


def list_org_audit(user, biz_type=None, page=1, page_size=50):
    """组织变更审计（读 t_affairs_audit_trail，biz_type=AA_ORG_*）。"""
    from app.models import AffairsAuditTrail, AaMajorDirection, AaClassAdjustmentRequest
    kinds = {"AA_ORG_COLLEGE", "AA_ORG_MAJOR", "AA_ORG_CLASS", "AA_ORG_MAJOR_DIRECTION",
             "AA_ORG_CLASS_ADJUST", "AA_ORG_CLASS_ADJUST_REQUEST"}
    if biz_type and biz_type not in kinds:
        raise AppException("VALIDATION_ERROR", "请选择本模块的组织审计类型")
    with session() as db:
        ctx = _ctx(user, db)
        conds = [AffairsAuditTrail.tenant_id == _tid(),
                 AffairsAuditTrail.biz_type.in_(kinds)]
        if biz_type:
            conds.append(AffairsAuditTrail.biz_type == biz_type)
        classes = _allowed_class_ids(ctx, db)
        if classes is not None:
            majors = _allowed_major_ids(ctx, db, include_deleted=True)
            directions = select(AaMajorDirection.id).where(AaMajorDirection.tenant_id == _tid(),
                AaMajorDirection.major_id.in_(list(majors)))
            requests = db.scalars(select(AaClassAdjustmentRequest).where(
                AaClassAdjustmentRequest.tenant_id == _tid())).all()
            requests = [row.id for row in _visible_adjustment_rows(requests, classes)]
            object_ids = {
                "AA_ORG_COLLEGE": list(ctx.college_ids),
                "AA_ORG_MAJOR": list(majors), "AA_ORG_CLASS": list(classes),
                "AA_ORG_MAJOR_DIRECTION": directions, "AA_ORG_CLASS_ADJUST_REQUEST": requests,
            }
            alternatives = [and_(AffairsAuditTrail.biz_type == kind, AffairsAuditTrail.biz_id.in_(ids))
                            for kind, ids in object_ids.items()]
            class_keys = [str(value) for value in classes]
            alternatives.append(and_(AffairsAuditTrail.biz_type == "AA_ORG_CLASS_ADJUST",
                AffairsAuditTrail.before_val.in_(class_keys), AffairsAuditTrail.after_val.in_(class_keys)))
            conds.append(or_(*alternatives))
        total = db.scalar(select(func.count()).select_from(AffairsAuditTrail).where(*conds)) or 0
        offset = (max(1, page) - 1) * page_size
        rows = db.scalars(select(AffairsAuditTrail).where(*conds)
                          .order_by(AffairsAuditTrail.id.desc()).offset(offset).limit(page_size)).all()
        items = [{"id": str(a.id), "bizType": a.biz_type, "bizId": str(a.biz_id) if a.biz_id else None,
                  "action": a.action, "operator": a.operator, "roleName": a.role_name,
                  "detail": a.detail, "beforeVal": a.before_val, "afterVal": a.after_val,
                  "occurredAt": a.occurred_at.isoformat() if a.occurred_at else None} for a in rows]
        return items, total
