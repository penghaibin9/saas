"""学工中心 · 统一安全上下文（StudentAffairsSecurityContext）。

一处解析「登录 → 角色能力 → 数据范围」，供全部 student_affairs 服务与 legacy campus_service 共用，
杜绝各 service 自行按角色名猜范围。核心裁决：

- 数据范围类型（scope_type）由**角色**决定，绝不因「是教职工」就 TENANT_ALL：
  TENANT_ALL：学校管理员 / 学工处管理员 / 校领导 / 平台超管（本租户全量）；
  COLLEGE   ：学院管理员（限授权学院，未配 = fail-closed）；
  CLASS     ：辅导员 / 班主任（限授权班级，未配 = NONE）；
  STUDENT   ：心理老师（限 PSY_STUDENT 授权学生）/ 点名 STUDENT 授权；
  DORM_BUILDING：宿管（限负责楼栋）；
  SELF      ：学生（仅本人）；
  NONE      ：无任何授权 → fail-closed，列表空 / 详情改批导出 403002，**绝不回退 TENANT_ALL**。

- 彻底取消 `_allowed_class_ids` 旧 `TENANT_FALLBACK=看全租户` 行为（改由本上下文 fail-closed）。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.core.permissions import ROLE_PERMISSIONS, is_super_admin
from app.services.db_service import _tid

# ── 角色 → 范围类型 ──
# ACADEMIC_ADMIN（教务处管理员，用户已拍板"本校教务全权"，默认无人持有）纳入 TENANT_ALL：
# 13B 教务中心组织/统计/调停课需全校教学数据范围；该角色仅持 academicAffairs.*，学工端点仍被
# require_permission 拦截，授予全租户 scope 不越学工域。未纳入 ACADEMIC_TEACHER（普通教务教师保持按范围收敛读，更安全）。
# FUNDING_TEACHER（资助老师）纳入 TENANT_ALL：permissions.py 注释明确"困难认定+奖助勤贷全域经办"，
# 权限集本身已窄限于 aid/funding/dashboard/student.view/stats.view，授予全租户 scope 不越出该权限集，
# 且修复此前 fail-closed→NONE 导致该角色"有权限但审批不了任何人"的实际阻断（历史欠账，见 permissions.py:61 注释）。
_TENANT_ALL_ROLES = {"SCHOOL_ADMIN", "PLATFORM_SUPER_ADMIN", "STUDENT_AFFAIRS_ADMIN",
                     "STUDENT_AFFAIRS", "SCHOOL_LEADER", "SA_ADMIN", "LEADER", "ACADEMIC_ADMIN",
                     "FUNDING_TEACHER"}
_COLLEGE_ROLES = {"COLLEGE_ADMIN", "COLLEGE_SA"}
_DORM_ROLES = {"DORM_MANAGER"}
_PSY_ROLES = {"PSYCHOLOGY_TEACHER"}

# 敏感权限点（拥有才可查看原文 / 导出）
_SENSITIVE_CODES = {
    "studentAffairs.aid.sensitiveView", "studentAffairs.risk.psyDetail.view",
    "studentAffairs.archive.psySensitive", "studentAffairs.funding.sensitiveView",
    "campusService.grant.sensitiveView",
}


def no_data_scope(msg: str = "该数据不在您的管理范围内") -> AppException:
    """统一 403002。"""
    return AppException("NO_DATA_SCOPE", msg)


def _derive_keys(user: dict) -> set[str]:
    """teacher_key 命中键：mock u_counselor01→counselor01 / db ctx_<login>。

    只派生工号族标识（t_user.login_name，租户内唯一 uk_tenant_login），**不含 realName**：
    姓名在学校里会重名，一旦参与匹配，两个同名教师会互相命中对方的授课/带班/指导范围
    （t_teacher_student_scope 等表存在 `teacher_name.in_(keys)` 分支）。工号唯一，姓名不唯一，
    因此身份判定一律以工号为准。
    历史数据前提（改动前已核验开发库 t_teacher_student_scope 22 行）：teacher_key 全部为工号
    （如 t_luo_yaqin / counselor_demo），无「仅有姓名」的行，故移除姓名不会使既有范围查空。
    若今后导入的范围数据只有姓名没有工号，正确做法是在导入时补齐 teacher_key，而不是把姓名放回本函数。
    """
    uid = str(user.get("userId") or "")
    ctx = str(user.get("activeContextId") or "")
    login = user.get("loginName") or ""
    return {k for k in (uid, login, uid[2:] if uid.startswith("u_") else "",
                        ctx[4:] if ctx.startswith("ctx_") else "") if k}


@dataclass
class StudentAffairsSecurityContext:
    user_id: str
    login_name: str
    tenant_id: int
    role_codes: set[str]
    permission_codes: set[str]
    sensitive_permissions: set[str]
    scope_type: str                       # TENANT_ALL/COLLEGE/CLASS/STUDENT/DORM_BUILDING/SELF/NONE
    college_ids: set[int] = field(default_factory=set)
    class_ids: set[int] = field(default_factory=set)
    student_ids: set[int] = field(default_factory=set)
    dorm_building_ids: set[int] = field(default_factory=set)
    psychology_student_ids: set[int] = field(default_factory=set)
    self_student_id: int | None = None
    is_scope_configured: bool = False
    scope_source: str = "NONE"

    # ── 范围判断 ──
    def allowed_class_ids(self, db) -> set[int] | None:
        """None=本租户全量可见；否则具体班级集合（可能为空=fail-closed）。"""
        if self.scope_type == "TENANT_ALL":
            return None
        if self.scope_type == "NONE" or self.scope_type == "SELF":
            return set()
        from app.models import Major, SchoolClass, StudentProfile
        ids: set[int] = set(self.class_ids)
        if self.college_ids:
            maj = db.scalars(select(Major.id).where(
                Major.tenant_id == self.tenant_id, Major.college_id.in_(self.college_ids))).all()
            if maj:
                cls = db.scalars(select(SchoolClass.id).where(
                    SchoolClass.tenant_id == self.tenant_id, SchoolClass.major_id.in_(list(maj)))).all()
                ids |= set(cls)
        if self.student_ids:
            cls = db.scalars(select(StudentProfile.class_id).where(
                StudentProfile.tenant_id == self.tenant_id, StudentProfile.id.in_(self.student_ids))).all()
            ids |= {c for c in cls if c}
        return ids  # 可能为空 → fail-closed

    def allowed_class_names(self, db) -> set[str] | None:
        """None=全租户；否则班级名集合（可能空=fail-closed）。供 legacy campus_service(CsServiceStudent.class_name) 收敛用。"""
        ids = self.allowed_class_ids(db)
        if ids is None:
            return None
        if not ids:
            return set()
        from app.models import SchoolClass
        rows = db.scalars(select(SchoolClass.class_name).where(
            SchoolClass.tenant_id == self.tenant_id, SchoolClass.id.in_(list(ids)))).all()
        return {n for n in rows if n}

    def require_student(self, db, student_id):
        """写/详情目标学生范围校验：越租户→not_found；越范围→403002。返回 StudentProfile。"""
        from app.models import StudentProfile
        s = db.scalar(select(StudentProfile).where(
            StudentProfile.id == int(student_id),
            StudentProfile.tenant_id == self.tenant_id,
            StudentProfile.is_deleted.is_(False),
        )) if student_id else None
        if not s:
            raise not_found("学生不存在")
        allowed = self.allowed_class_ids(db)
        if allowed is None:
            return s
        if self.scope_type == "STUDENT":  # 心理/点名：按学生集合判定
            if int(student_id) in (self.psychology_student_ids | self.student_ids):
                return s
            raise no_data_scope("该学生不在您的授权范围内")
        if s.class_id not in allowed:
            raise no_data_scope("该学生不在您的数据范围内")
        return s

    def can_view_building(self, building_id) -> bool:
        if self.scope_type == "TENANT_ALL":
            return True
        return int(building_id) in self.dorm_building_ids if building_id is not None else False

    def has_sensitive(self, code: str) -> bool:
        return code in self.sensitive_permissions


# ── 学生主档目录数据范围（/students 公共选择器 + 学生主档；fail-closed）──
# TENANT_ALL → 不收敛；有明确 CLASS/COLLEGE/STUDENT/DORM 范围 → 按范围；
# 其余角色（含未配置 scope 的教职工）→ 空集合，禁止全校目录。


def student_directory_scope(user) -> tuple[set[int] | None, set[int] | None]:
    """返回 (class_ids, student_ids)。
    - (None, None)：TENANT_ALL，不收敛
    - (set(), None) 或 (None, set())：fail-closed 空结果
    - (ids, None) / (None, ids)：按班级或学生集合过滤
    """
    from app.db.session import db_enabled
    if not db_enabled():
        # 非 DB 演示模式：仅 TENANT_ALL 角色可看全量，其余空
        from app.core.permissions import is_super_admin
        role = ((user or {}).get("currentRoleCode") or "").upper()
        if is_super_admin(user) or role in _TENANT_ALL_ROLES:
            return None, None
        return set(), None
    from app.services.db_service import session
    with session() as db:
        ctx = build_affairs_context(user, db)
        if ctx.scope_type == "TENANT_ALL":
            return None, None
        if ctx.scope_type == "SELF":
            sid = ctx.self_student_id
            try:
                return None, {int(sid)} if sid else set()
            except (TypeError, ValueError):
                return None, set()
        if ctx.scope_type == "STUDENT":
            return None, {int(i) for i in (ctx.psychology_student_ids | ctx.student_ids)}
        if ctx.scope_type == "NONE":
            return set(), None
        if ctx.scope_type == "DORM_BUILDING":
            # 宿管：通过宿舍楼关联学生由上层业务收敛；公共 /students 目录默认空，避免全校
            return set(), None
        ids = ctx.allowed_class_ids(db)
        return (ids if ids is not None else set()), None


def build_affairs_context(user: dict, db=None) -> StudentAffairsSecurityContext:
    """解析当前登录用户的学工安全上下文。db 可复用调用方会话（省一次开库）。"""
    u = user or {}
    role = (u.get("currentRoleCode") or "").upper()
    tenant_id = _tid()
    granted = set(ROLE_PERMISSIONS.get(role, set()))
    ctx = StudentAffairsSecurityContext(
        user_id=str(u.get("userId") or ""), login_name=u.get("loginName") or "",
        tenant_id=tenant_id, role_codes={role} if role else set(),
        permission_codes=granted, sensitive_permissions=granted & _SENSITIVE_CODES,
        scope_type="NONE")

    # 学生 → SELF
    if (u.get("userType") or "").upper() == "STUDENT" or role == "STUDENT":
        ctx.scope_type = "SELF"
        ctx.self_student_id = u.get("studentId") or u.get("studentProfileId")
        ctx.scope_source = "SELF"
        ctx.is_scope_configured = True
        return ctx

    # TENANT_ALL（按角色，绝不按 userType==ADMIN 兜底）
    if is_super_admin(user) or role in _TENANT_ALL_ROLES:
        ctx.scope_type = "TENANT_ALL"
        ctx.scope_source = "ROLE_TENANT_ALL"
        ctx.is_scope_configured = True
        return ctx

    # 需要读 scope 表的角色
    _own = db is None
    if _own:
        from app.services.db_service import session as _sess
        cm = _sess()
        db = cm.__enter__()
    try:
        keys = _derive_keys(u)
        from app.models import (College, DormBuilding, SchoolClass, StudentProfile,
                                TeacherStudentScope)
        rows = db.scalars(select(TeacherStudentScope).where(
            TeacherStudentScope.tenant_id == tenant_id,
            TeacherStudentScope.is_deleted.is_(False),
            TeacherStudentScope.status == "ACTIVE",
            (TeacherStudentScope.teacher_key.in_(keys)) |
            (TeacherStudentScope.teacher_name.in_(keys)))).all()
        rows = [r for r in rows if not r.role_code or (r.role_code or "").upper() == role]
        class_names, college_names, student_nos, psy_nos = set(), set(), set(), set()
        for r in rows:
            st = (r.scope_type or "").upper()
            v = (r.ref_value or "").strip()
            if st == "CLASS" and v:
                class_names.add(v)
            elif st == "COLLEGE" and v:
                college_names.add(v)
            elif st == "STUDENT" and v:
                student_nos.add(v)
            elif st == "PSY_STUDENT" and v:
                psy_nos.add(v)

        # 名称 → id（本租户内解析）
        if class_names:
            variants = class_names | {n + "班" for n in class_names} | {n.rstrip("班") for n in class_names}
            cls = db.scalars(select(SchoolClass).where(
                SchoolClass.tenant_id == tenant_id, SchoolClass.class_name.in_(list(variants)))).all()
            ctx.class_ids = {c.id for c in cls}
        if college_names:
            cols = db.scalars(select(College).where(
                College.tenant_id == tenant_id, College.college_name.in_(list(college_names)))).all()
            ctx.college_ids = {c.id for c in cols}
        if student_nos:
            studs = db.scalars(select(StudentProfile).where(
                StudentProfile.tenant_id == tenant_id, StudentProfile.student_no.in_(list(student_nos)))).all()
            ctx.student_ids = {s.id for s in studs}
        if psy_nos:
            studs = db.scalars(select(StudentProfile).where(
                StudentProfile.tenant_id == tenant_id, StudentProfile.student_no.in_(list(psy_nos)))).all()
            ctx.psychology_student_ids = {s.id for s in studs}

        # 宿管楼栋（按 manager_teacher_key）
        if role in _DORM_ROLES:
            blds = db.scalars(select(DormBuilding).where(
                DormBuilding.tenant_id == tenant_id, DormBuilding.is_deleted.is_(False),
                DormBuilding.manager_teacher_key.in_(list(keys)))).all()
            ctx.dorm_building_ids = {b.id for b in blds}
    finally:
        if _own:
            cm.__exit__(None, None, None)

    # scope_type 裁决
    if role in _DORM_ROLES:
        ctx.scope_type = "DORM_BUILDING"
        ctx.is_scope_configured = bool(ctx.dorm_building_ids)
        ctx.scope_source = "SCOPE_TABLE_DORM"
    elif role in _PSY_ROLES:
        ctx.scope_type = "STUDENT"
        ctx.is_scope_configured = bool(ctx.psychology_student_ids)
        ctx.scope_source = "SCOPE_TABLE_PSY"
    elif role in _COLLEGE_ROLES:
        ctx.scope_type = "COLLEGE"
        ctx.is_scope_configured = bool(ctx.college_ids)
        ctx.scope_source = "SCOPE_TABLE_COLLEGE"
    elif ctx.class_ids or ctx.college_ids or ctx.student_ids:
        ctx.scope_type = "CLASS"
        ctx.is_scope_configured = True
        ctx.scope_source = "SCOPE_TABLE_CLASS"
    else:
        ctx.scope_type = "NONE"          # fail-closed：绝不回退 TENANT_ALL
        ctx.is_scope_configured = False
        ctx.scope_source = "NONE"
    return ctx
