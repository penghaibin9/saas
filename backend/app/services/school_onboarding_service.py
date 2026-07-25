"""新学校开局向导（P13-A）。
把一所新学校从"空租户"带到"可试点"：建租户 → 品牌 → 院系/专业/班级。
师生账号只能从系统管理的身份导入入口创建；本服务仅被该唯一入口以内部分支复用。
设计要点：
- 复用已有能力：租户/校管账号复用 platform_service；教师范围复用 t_teacher_student_scope。
- dry-run：只校验、给行号错误，不落库。
- confirm：整批一个事务；atomic 模式下任一硬错误 → 整批回滚（422）。
- 严格租户隔离：非平台运营账号不得写入非本人租户（403）。
- 所有 confirm 写审计；空数据不 500。
本模块不重复造文件解析轮子：身份通道只接收系统管理标准 .xlsx 预检后产生的结构化行；
文件解析、批次绑定和一次性凭证回执均由唯一身份导入入口负责。
"""
from __future__ import annotations

from sqlalchemy import func, select

from app.core.exceptions import AppException
from app.core.security import hash_password
from app.core.student_lifecycle import ENROLLED, normalize_student_stage
from app.db.session import db_enabled, get_sessionmaker
from app.services import audit_log
from app.services.db_service import _tid
from app.services.saas_role_templates import (BUILTIN_ROLE_TEMPLATES,
                                               ROLE_TEMPLATE_VERSION,
                                               role_codes_from_row)

_PLATFORM_TYPES = {"PLATFORM_OP", "PLATFORM_ADMIN", "PLATFORM_SUPER_ADMIN", "SUPER_ADMIN"}
_OPERATOR_ROLES = _PLATFORM_TYPES | {"SCHOOL_ADMIN", "SYS_ADMIN"}


def _session():
    return get_sessionmaker()()


def _require_operator(user: dict | None) -> dict:
    u = user or {}
    ut = (u.get("userType") or "").strip().upper()
    role = (u.get("currentRoleCode") or "").strip().upper()
    effective = role or ut
    if effective not in _OPERATOR_ROLES and ut not in ("SCHOOL_ADMIN", "ADMIN"):
        raise AppException("NO_PERMISSION", "无权执行开局向导")
    return u


def _is_platform(user: dict) -> bool:
    return ((user.get("currentRoleCode") or "").strip().upper() in _PLATFORM_TYPES
            or (user.get("userType") or "").strip().upper() in _PLATFORM_TYPES)


def _resolve_target_tenant(user: dict, body: dict) -> int:
    """目标租户：body.tenantId 优先；非平台运营只能操作本租户，否则 403（禁跨租户）。"""
    own = 0
    try:
        own = _tid()
    except Exception:  # noqa: BLE001
        own = 0
    raw = body.get("tenantId")
    target = int(raw) if raw not in (None, "") else own
    if target and own and target != own and not _is_platform(user):
        raise AppException("NO_PERMISSION", "禁止跨租户写入：只能操作本校租户")
    if not target:
        raise AppException("VALIDATION_ERROR", "缺少目标租户（tenantId）")
    return target


def _blank_report(dry_run: bool, tenant_id: int) -> dict:
    return {
        "dryRun": dry_run, "tenantId": str(tenant_id),
        "entities": {k: {"created": 0, "skipped": 0, "failed": 0}
                     for k in ("roles", "colleges", "majors", "classes", "students",
                               "studentAccounts", "teachers", "roleBindings", "scopes")},
        "errors": [], "studentCredentials": [], "teacherCredentials": [],
        "roleTemplateVersion": ROLE_TEMPLATE_VERSION,
    }


def _student_class_matches(db, tenant_id: int, row: dict, SchoolClass, Major, College):
    """按学校真实组织路径定位班级；只填班级且同名时返回多条，由调用方阻断。"""
    class_name = str((row or {}).get("className") or "").strip()
    if not class_name:
        return []
    stmt = (select(SchoolClass)
            .join(Major, Major.id == SchoolClass.major_id)
            .where(SchoolClass.tenant_id == tenant_id,
                   SchoolClass.class_name == class_name,
                   SchoolClass.is_deleted.is_(False),
                   Major.tenant_id == tenant_id,
                   Major.is_deleted.is_(False)))
    major_name = str((row or {}).get("majorName") or "").strip()
    college_name = str((row or {}).get("collegeName") or "").strip()
    if major_name:
        stmt = stmt.where(Major.major_name == major_name)
    if college_name:
        stmt = (stmt.join(College, College.id == Major.college_id)
                .where(College.tenant_id == tenant_id,
                       College.college_name == college_name,
                       College.is_deleted.is_(False)))
    return db.scalars(stmt).all()


# ─────────── 租户创建（平台运营，复用 platform_service） ───────────

def create_tenant_step(user: dict, body: dict) -> dict:
    u = _require_operator(user)
    if not _is_platform(u):
        raise AppException("NO_PERMISSION", "仅平台运营可创建新租户")
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实建租户")
    from app.services import platform_service
    res = platform_service.create_tenant(body)
    audit_log.record("ONBOARD_CREATE_TENANT", f"tenant:{body.get('tenantCode')}",
                     {"tenantName": body.get("tenantName")})
    return res


# ─────────── 校验器（返回错误列表；不写库） ───────────

def _validate_rows(body: dict) -> list[dict]:
    """跨实体校验，返回 [{row, entity, field, error}]。行号 1-based（对应导入表行）。"""
    errors: list[dict] = []
    colleges = body.get("colleges") or []
    majors = body.get("majors") or []
    classes = body.get("classes") or []
    students = body.get("students") or []
    teachers = body.get("teachers") or []

    college_names = set()
    for i, c in enumerate(colleges, 1):
        nm = str((c or {}).get("name") or "").strip()
        if not nm:
            errors.append({"row": i, "entity": "college", "field": "name", "error": "院系名称必填"})
        else:
            college_names.add(nm)
    major_names = set()
    for i, m in enumerate(majors, 1):
        nm = str((m or {}).get("name") or "").strip()
        cg = str((m or {}).get("collegeName") or "").strip()
        if not nm:
            errors.append({"row": i, "entity": "major", "field": "name", "error": "专业名称必填"})
        if not cg:
            errors.append({"row": i, "entity": "major", "field": "collegeName", "error": "所属院系必填"})
        if nm:
            major_names.add(nm)
    for i, k in enumerate(classes, 1):
        nm = str((k or {}).get("name") or "").strip()
        mj = str((k or {}).get("majorName") or "").strip()
        if not nm:
            errors.append({"row": i, "entity": "class", "field": "name", "error": "班级名称必填"})
        if not mj:
            errors.append({"row": i, "entity": "class", "field": "majorName", "error": "所属专业必填"})
    seen_no = set()
    for i, s in enumerate(students, 1):
        row_no = int((s or {}).get("_rowNo") or i)
        no = str((s or {}).get("studentNo") or "").strip()
        nm = str((s or {}).get("name") or "").strip()
        if not no:
            errors.append({"row": row_no, "entity": "student", "field": "studentNo", "error": "学号必填"})
        elif no in seen_no:
            errors.append({"row": row_no, "entity": "student", "field": "studentNo", "error": f"文件内学号重复：{no}"})
        else:
            seen_no.add(no)
        if not nm:
            errors.append({"row": row_no, "entity": "student", "field": "name", "error": "姓名必填"})
    seen_login = set()
    for i, t in enumerate(teachers, 1):
        row_no = int((t or {}).get("_rowNo") or i)
        ln = str((t or {}).get("loginName") or "").strip()
        nm = str((t or {}).get("name") or "").strip()
        if not ln:
            errors.append({"row": row_no, "entity": "teacher", "field": "loginName", "error": "登录名必填"})
        elif ln in seen_login:
            errors.append({"row": row_no, "entity": "teacher", "field": "loginName", "error": f"文件内登录名重复：{ln}"})
        else:
            seen_login.add(ln)
        if not nm:
            errors.append({"row": row_no, "entity": "teacher", "field": "name", "error": "姓名必填"})
        try:
            role_codes = role_codes_from_row(t or {})
        except AppException as exc:
            errors.append({"row": row_no, "entity": "teacher", "field": "roleCodes",
                           "error": exc.message})
            role_codes = []
        scope_type = str((t or {}).get("scopeType") or "").strip().upper()
        scope_ref = (t or {}).get("scopeRef")
        if "COUNSELOR" in role_codes and scope_type not in ("CLASS", "ADVISOR"):
            errors.append({"row": row_no, "entity": "teacher", "field": "scopeType",
                           "error": "辅导员必须配置 CLASS 或 ADVISOR 数据范围"})
        if scope_type in ("CLASS", "COLLEGE", "STUDENT") and scope_ref in (None, ""):
            errors.append({"row": row_no, "entity": "teacher", "field": "scopeRef",
                           "error": f"{scope_type} 数据范围必须填写 scopeRef"})
    for value in sorted(seen_no & seen_login):
        errors.append({"row": 0, "entity": "account", "field": "loginName",
                       "error": f"同一批次学号与教师登录名冲突：{value}"})
    return errors


# ─────────── 主编排 ───────────

def run_onboarding(user: dict, body: dict, dry_run: bool = True,
                   *, identity_channel: bool = False) -> dict:
    u = _require_operator(user)
    if not identity_channel and ((body.get("students") or []) or (body.get("teachers") or [])):
        raise AppException(
            "VALIDATION_ERROR",
            "开局向导禁止创建师生账号，请到「系统管理 → 导入老师和学生」操作")
    tenant_id = _resolve_target_tenant(u, body)
    report = _blank_report(dry_run, tenant_id)
    if not db_enabled():
        # 演示模式：只做校验，返回报告，不落库
        report["errors"] = _validate_rows(body)
        report["entities"]["roles"]["created"] = len(BUILTIN_ROLE_TEMPLATES)
        report["entities"]["colleges"]["created"] = len(body.get("colleges") or [])
        report["entities"]["majors"]["created"] = len(body.get("majors") or [])
        report["entities"]["classes"]["created"] = len(body.get("classes") or [])
        report["entities"]["students"]["created"] = len(body.get("students") or [])
        report["entities"]["studentAccounts"]["created"] = len(body.get("students") or [])
        report["entities"]["teachers"]["created"] = len(body.get("teachers") or [])
        valid_teacher_rows = []
        for teacher in body.get("teachers") or []:
            try:
                valid_teacher_rows.append(role_codes_from_row(teacher))
            except AppException:
                pass
        report["entities"]["roleBindings"]["created"] = (
            len(body.get("students") or []) + sum(len(codes) for codes in valid_teacher_rows))
        report["entities"]["scopes"]["created"] = sum(
            1 for t in body.get("teachers") or []
            if str(t.get("scopeType") or "").strip().upper() in ("CLASS", "COLLEGE", "STUDENT", "ADVISOR"))
        report["note"] = "演示模式：仅校验不落库"
        return report

    # 1) 结构校验（行号）
    errors = _validate_rows(body)
    report["errors"] = errors
    atomic = bool(body.get("atomic", True))

    if dry_run:
        # 预演：统计将创建/跳过数量（不写库）
        _count_preview(tenant_id, body, report)
        return report

    if errors and atomic:
        # 整批回滚语义：有硬错误直接拒绝，不写任何一行
        raise AppException("VALIDATION_ERROR", "存在错误行，已整批回滚（未写入任何数据）",
                           details={"errors": errors})

    # 2) confirm：一个事务写入
    with _session() as db:
        from app.models import (College, Major, SchoolClass, StudentProfile, TeacherStudentScope,
                                User)
        from app.services.saas_role_service import ensure_builtin_roles, ensure_user_roles

        role_report = ensure_builtin_roles(db, tenant_id)
        report["entities"]["roles"]["created"] = role_report["created"] + role_report["restored"]
        report["entities"]["roles"]["skipped"] = role_report["unchanged"]

        def col(name):
            return db.scalars(select(College).where(College.tenant_id == tenant_id,
                              College.college_name == name, College.is_deleted.is_(False))).first()

        def maj(name):
            return db.scalars(select(Major).where(Major.tenant_id == tenant_id,
                              Major.major_name == name, Major.is_deleted.is_(False))).first()

        def cls(name):
            return db.scalars(select(SchoolClass).where(SchoolClass.tenant_id == tenant_id,
                              SchoolClass.class_name == name, SchoolClass.is_deleted.is_(False))).first()

        # 院系（统一走组织主数据校验，复用本事务会话）
        from app.services.org_master_service import apply_org_node_in_session
        for c in (body.get("colleges") or []):
            nm = str(c.get("name")).strip()
            if col(nm):
                report["entities"]["colleges"]["skipped"] += 1
                continue
            apply_org_node_in_session(
                db, node_type="COLLEGE", name=nm, code=c.get("code"),
                tenant_id=tenant_id, commit=False,
            )
            report["entities"]["colleges"]["created"] += 1
        db.flush()
        # 专业
        for m in (body.get("majors") or []):
            nm = str(m.get("name")).strip()
            cg = col(str(m.get("collegeName")).strip())
            if not cg:
                report["entities"]["majors"]["failed"] += 1
                report["errors"].append({"entity": "major", "field": "collegeName",
                                         "error": f"院系不存在：{m.get('collegeName')}"})
                continue
            if maj(nm):
                report["entities"]["majors"]["skipped"] += 1
                continue
            apply_org_node_in_session(
                db, node_type="MAJOR", name=nm, code=m.get("code"), parent_id=cg.id,
                tenant_id=tenant_id, commit=False,
            )
            report["entities"]["majors"]["created"] += 1
        db.flush()
        # 班级
        for k in (body.get("classes") or []):
            nm = str(k.get("name")).strip()
            mj = maj(str(k.get("majorName")).strip())
            if not mj:
                report["entities"]["classes"]["failed"] += 1
                report["errors"].append({"entity": "class", "field": "majorName",
                                         "error": f"专业不存在：{k.get('majorName')}"})
                continue
            if cls(nm):
                report["entities"]["classes"]["skipped"] += 1
                continue
            apply_org_node_in_session(
                db, node_type="CLASS", name=nm, parent_id=mj.id,
                tenant_id=tenant_id, commit=False,
                extras={"grade": k.get("grade")},
            )
            report["entities"]["classes"]["created"] += 1
        db.flush()
        # 学生
        for s in (body.get("students") or []):
            no = str(s.get("studentNo")).strip()
            class_name = str(s.get("className") or "").strip()
            class_matches = _student_class_matches(db, tenant_id, s, SchoolClass, Major, College)
            k = class_matches[0] if len(class_matches) == 1 else None
            if class_name and len(class_matches) != 1:
                report["entities"]["students"]["failed"] += 1
                report["errors"].append({"row": int(s.get("_rowNo") or 0),
                                         "entity": "student", "field": "className",
                                         "error": (f"班级不存在：{class_name}" if not class_matches else
                                                   f"班级名称不唯一，请同时填写学院和专业：{class_name}")})
                continue
            account = db.scalars(select(User).where(
                User.tenant_id == tenant_id, User.login_name == no)).first()
            if account and (account.is_deleted or account.user_type != "STUDENT"):
                report["entities"]["studentAccounts"]["failed"] += 1
                report["errors"].append({"entity": "studentAccount", "field": "studentNo",
                                         "error": f"学号被历史/非学生账号占用：{no}"})
                continue
            profile = db.scalars(select(StudentProfile).where(
                StudentProfile.tenant_id == tenant_id, StudentProfile.student_no == no,
                StudentProfile.is_deleted.is_(False))).first()
            if profile:
                report["entities"]["students"]["skipped"] += 1
                # IX-E2E：历史导入可能缺 college_id，按 专业 / 班级→专业 回填
                if not profile.college_id:
                    major_id = profile.major_id
                    if not major_id and profile.class_id:
                        cls = db.get(SchoolClass, profile.class_id)
                        major_id = cls.major_id if cls else None
                        if major_id and not profile.major_id:
                            profile.major_id = major_id
                    if major_id:
                        maj = db.get(Major, major_id)
                        if maj and maj.college_id:
                            profile.college_id = maj.college_id
            else:
                major_id = k.major_id if k else None
                college_id = None
                if major_id:
                    maj = db.get(Major, major_id)
                    college_id = maj.college_id if maj else None
                db.add(StudentProfile(
                    tenant_id=tenant_id, student_no=no, real_name=str(s.get("name")).strip(),
                    gender=s.get("gender"), grade=s.get("grade"),
                    class_id=k.id if k else None, major_id=major_id, college_id=college_id,
                    current_stage=normalize_student_stage(s.get("stage") or ENROLLED),
                    student_status="NORMAL", status="ACTIVE"))
                report["entities"]["students"]["created"] += 1

            if account:
                report["entities"]["studentAccounts"]["skipped"] += 1
            else:
                import secrets
                pwd = "Stu@" + secrets.token_urlsafe(6)
                account = User(tenant_id=tenant_id, login_name=no,
                               real_name=str(s.get("name")).strip(),
                               password_hash=hash_password(pwd), user_type="STUDENT",
                               status="ACTIVE", must_change_password=True)
                db.add(account)
                db.flush()
                report["entities"]["studentAccounts"]["created"] += 1
                report["studentCredentials"].append({"studentNo": no, "initialPassword": pwd})
            binding = ensure_user_roles(db, tenant_id, account.id, ["STUDENT"])
            report["entities"]["roleBindings"]["created"] += binding["created"] + binding["restored"]
            report["entities"]["roleBindings"]["skipped"] += binding["unchanged"]
        db.flush()
        # 教师账号 + 角色 + 范围
        for t in (body.get("teachers") or []):
            ln = str(t.get("loginName")).strip()
            stype = str(t.get("scopeType") or "").strip().upper()
            sref = str(t.get("scopeRef") or "").strip()
            scope_exists = True
            if stype == "CLASS" and sref:
                scope_exists = cls(sref) is not None
            elif stype == "COLLEGE" and sref:
                scope_exists = col(sref) is not None
            elif stype == "STUDENT" and sref:
                scope_exists = db.scalars(select(StudentProfile).where(
                    StudentProfile.tenant_id == tenant_id,
                    StudentProfile.student_no == sref,
                    StudentProfile.is_deleted.is_(False))).first() is not None
            if not scope_exists:
                report["entities"]["scopes"]["failed"] += 1
                report["errors"].append({"row": int(t.get("_rowNo") or 0),
                                         "entity": "teacher", "field": "scopeRef",
                                         "error": f"数据范围引用不存在：{sref}"})
                continue
            dup = db.scalars(select(User).where(User.tenant_id == tenant_id,
                             User.login_name == ln)).first()
            if dup and dup.is_deleted:
                report["entities"]["teachers"]["failed"] += 1
                report["errors"].append({"entity": "teacher", "field": "loginName",
                                         "error": f"登录名存在于历史软删账号，请先恢复或更换：{ln}"})
                continue
            role_codes = role_codes_from_row(t)
            if dup and dup.user_type not in ("TEACHER", "STAFF"):
                report["entities"]["teachers"]["failed"] += 1
                report["errors"].append({"entity": "teacher", "field": "loginName",
                                         "error": f"登录名已被非教师账号占用：{ln}"})
                continue
            if dup:
                uobj = dup
                report["entities"]["teachers"]["skipped"] += 1
            else:
                import secrets
                pwd = "Tmp@" + secrets.token_urlsafe(6)
                uobj = User(tenant_id=tenant_id, login_name=ln, real_name=str(t.get("name")).strip(),
                            password_hash=hash_password(pwd), user_type="TEACHER",
                            status="ACTIVE", must_change_password=True)
                db.add(uobj)
                db.flush()
                report["entities"]["teachers"]["created"] += 1
                report["teacherCredentials"].append({"loginName": ln, "initialPassword": pwd})

            binding = ensure_user_roles(db, tenant_id, uobj.id, role_codes)
            report["entities"]["roleBindings"]["created"] += binding["created"] + binding["restored"]
            report["entities"]["roleBindings"]["skipped"] += binding["unchanged"]
            # 数据范围绑定（复用 t_teacher_student_scope）
            if stype in ("CLASS", "COLLEGE", "STUDENT", "ADVISOR"):
                scope_role = role_codes[0]
                existing_scope = db.scalars(select(TeacherStudentScope).where(
                    TeacherStudentScope.tenant_id == tenant_id,
                    TeacherStudentScope.teacher_key == ln,
                    TeacherStudentScope.role_code == scope_role,
                    TeacherStudentScope.scope_type == stype,
                    TeacherStudentScope.ref_value == (sref or None))).first()
                if existing_scope and not existing_scope.is_deleted and existing_scope.status == "ACTIVE":
                    report["entities"]["scopes"]["skipped"] += 1
                elif existing_scope:
                    existing_scope.is_deleted = False
                    existing_scope.status = "ACTIVE"
                    existing_scope.version = int(existing_scope.version or 0) + 1
                    report["entities"]["scopes"]["created"] += 1
                else:
                    db.add(TeacherStudentScope(tenant_id=tenant_id, teacher_key=ln,
                           teacher_name=str(t.get("name")).strip(), role_code=scope_role,
                           scope_type=stype, ref_value=sref or None,
                           status="ACTIVE"))
                    report["entities"]["scopes"]["created"] += 1
        if report["errors"] and atomic:
            raise AppException("VALIDATION_ERROR", "存在关联错误，已整批回滚（未写入任何数据）",
                               details={"errors": report["errors"]})
        db.commit()

    audit_log.record("ONBOARD_IMPORT", f"tenant:{tenant_id}",
                     {"entities": {k: v for k, v in report["entities"].items()}})
    return report


def _count_preview(tenant_id: int, body: dict, report: dict) -> None:
    """dry-run 预演：统计将新建/跳过（不写库）。"""
    with _session() as db:
        from app.models import College, Major, Role, SchoolClass, StudentProfile, User

        existing_role_codes = set(db.scalars(select(Role.role_code).where(
            Role.tenant_id == tenant_id,
            Role.role_code.in_(tuple(r["roleCode"] for r in BUILTIN_ROLE_TEMPLATES)),
            Role.is_deleted.is_(False))).all())
        report["entities"]["roles"]["skipped"] = len(existing_role_codes)
        report["entities"]["roles"]["created"] = len(BUILTIN_ROLE_TEMPLATES) - len(existing_role_codes)

        def exists(model, col, val):
            return db.scalars(select(model).where(model.tenant_id == tenant_id, col == val,
                              model.is_deleted.is_(False))).first() is not None
        for c in (body.get("colleges") or []):
            nm = str((c or {}).get("name") or "").strip()
            if not nm:
                report["entities"]["colleges"]["failed"] += 1
            elif exists(College, College.college_name, nm):
                report["entities"]["colleges"]["skipped"] += 1
            else:
                report["entities"]["colleges"]["created"] += 1
        for m in (body.get("majors") or []):
            nm = str((m or {}).get("name") or "").strip()
            if not nm:
                report["entities"]["majors"]["failed"] += 1
            elif exists(Major, Major.major_name, nm):
                report["entities"]["majors"]["skipped"] += 1
            else:
                report["entities"]["majors"]["created"] += 1
        for k in (body.get("classes") or []):
            nm = str((k or {}).get("name") or "").strip()
            if not nm:
                report["entities"]["classes"]["failed"] += 1
            elif exists(SchoolClass, SchoolClass.class_name, nm):
                report["entities"]["classes"]["skipped"] += 1
            else:
                report["entities"]["classes"]["created"] += 1
        incoming_student_nos = {
            str((row or {}).get("studentNo") or "").strip()
            for row in (body.get("students") or [])
        }
        for index, s in enumerate(body.get("students") or [], 1):
            no = str((s or {}).get("studentNo") or "").strip()
            row_no = int((s or {}).get("_rowNo") or index)
            if not no:
                report["entities"]["students"]["failed"] += 1
            elif exists(StudentProfile, StudentProfile.student_no, no):
                report["entities"]["students"]["skipped"] += 1
            else:
                report["entities"]["students"]["created"] += 1
            account = db.scalars(select(User).where(
                User.tenant_id == tenant_id, User.login_name == no)).first() if no else None
            if account and (account.is_deleted or account.user_type != "STUDENT"):
                report["entities"]["studentAccounts"]["failed"] += 1
                report["errors"].append({"row": row_no, "entity": "studentAccount",
                                         "field": "studentNo",
                                         "error": f"学号被历史/非学生账号占用：{no}"})
            elif account:
                report["entities"]["studentAccounts"]["skipped"] += 1
            elif no:
                report["entities"]["studentAccounts"]["created"] += 1
            class_name = str((s or {}).get("className") or "").strip()
            class_matches = _student_class_matches(db, tenant_id, s, SchoolClass, Major, College)
            if class_name and len(class_matches) != 1:
                report["errors"].append({"row": row_no, "entity": "student",
                                         "field": "className",
                                         "error": (f"班级不存在：{class_name}" if not class_matches else
                                                   f"班级名称不唯一，请同时填写学院和专业：{class_name}")})
        for index, t in enumerate(body.get("teachers") or [], 1):
            ln = str((t or {}).get("loginName") or "").strip()
            row_no = int((t or {}).get("_rowNo") or index)
            if not ln:
                report["entities"]["teachers"]["failed"] += 1
            account = db.scalars(select(User).where(
                User.tenant_id == tenant_id, User.login_name == ln)).first() if ln else None
            if account and (account.is_deleted or account.user_type not in ("TEACHER", "STAFF")):
                report["entities"]["teachers"]["failed"] += 1
                report["errors"].append({"row": row_no, "entity": "teacher",
                                         "field": "loginName",
                                         "error": f"登录名被历史/非教师账号占用：{ln}"})
            elif account:
                report["entities"]["teachers"]["skipped"] += 1
            elif ln:
                report["entities"]["teachers"]["created"] += 1
            scope_type = str((t or {}).get("scopeType") or "").strip().upper()
            scope_ref = str((t or {}).get("scopeRef") or "").strip()
            scope_exists = True
            if scope_type == "CLASS" and scope_ref:
                scope_exists = exists(SchoolClass, SchoolClass.class_name, scope_ref)
            elif scope_type == "COLLEGE" and scope_ref:
                scope_exists = exists(College, College.college_name, scope_ref)
            elif scope_type == "STUDENT" and scope_ref:
                scope_exists = (scope_ref in incoming_student_nos
                                or exists(StudentProfile, StudentProfile.student_no, scope_ref))
            if not scope_exists:
                report["errors"].append({"row": row_no, "entity": "teacher",
                                         "field": "scopeRef",
                                         "error": f"数据范围引用不存在：{scope_ref}"})
