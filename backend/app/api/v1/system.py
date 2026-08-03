"""系统信息接口。"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import io
import re
import secrets
from urllib.parse import quote

from fastapi import APIRouter, Body, Depends, File, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select

from app.core.config import settings
from app.core.context import current_tenant_id
from app.core.response import success
from app.core.permissions import require_any_permission, require_permission
from app.db.session import db_enabled, get_sessionmaker

router = APIRouter()

STAFF_ACCOUNT_USER_TYPES = ("TEACHER", "STAFF", "ADMIN", "SCHOOL_ADMIN")


def _normalize_account_type(value: object, *, allow_empty: bool = True) -> str:
    from app.core.exceptions import AppException
    raw = str(value or "").strip().upper()
    if not raw and allow_empty:
        return ""
    if raw not in ("STAFF", "STUDENT"):
        raise AppException("VALIDATION_ERROR", "account_type 必须是 STAFF 或 STUDENT")
    return raw


def _is_student_account(db, account, roles: list | None = None) -> bool:
    """兼容历史脏数据：类型、稳定主档绑定、学生角色任一命中即视为学生。"""
    if str(account.user_type or "").upper() == "STUDENT":
        return True
    if roles is not None and any(str(role.role_code or "").upper() == "STUDENT" for role in roles):
        return True
    if db is None:
        return False
    from app.models import Role, StudentAccountLink, UserRole
    linked = db.scalar(select(func.count(StudentAccountLink.id)).where(
        StudentAccountLink.tenant_id == account.tenant_id,
        StudentAccountLink.user_id == account.id,
        StudentAccountLink.link_status == "ACTIVE",
        StudentAccountLink.is_deleted.is_(False),
    ))
    if linked:
        return True
    student_role = db.scalar(select(func.count(UserRole.id)).join(
        Role, Role.id == UserRole.role_id
    ).where(
        UserRole.tenant_id == account.tenant_id,
        UserRole.user_id == account.id,
        UserRole.status == "ACTIVE",
        UserRole.is_deleted.is_(False),
        Role.role_code == "STUDENT",
        Role.is_deleted.is_(False),
    ))
    return bool(student_role)


def _account_type_of(account, db=None, roles: list | None = None) -> str:
    return "STUDENT" if _is_student_account(db, account, roles) else "STAFF"


def _check_account_version(account, expected_version) -> None:
    """SYS-03：账号写操作的乐观锁。不传视为老客户端（放行），传了就必须对得上。"""
    from app.core.exceptions import AppException
    if expected_version in (None, ""):
        return
    try:
        expected = int(expected_version)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "expectedVersion 必须是整数") from None
    if expected != int(account.version or 0):
        raise AppException("DATA_CONFLICT", "账号已被他人更新，请刷新后重试")


def _account_type_condition(User, account_type: str, tenant_id: int):
    """数据库层使用同一分类规则，确保列表、批量操作、异常与导出边界一致。"""
    from app.models import Role, StudentAccountLink, UserRole
    linked_student = select(StudentAccountLink.id).where(
        StudentAccountLink.tenant_id == tenant_id,
        StudentAccountLink.user_id == User.id,
        StudentAccountLink.link_status == "ACTIVE",
        StudentAccountLink.is_deleted.is_(False),
    ).exists()
    has_student_role = select(UserRole.id).join(
        Role, Role.id == UserRole.role_id
    ).where(
        UserRole.tenant_id == tenant_id,
        UserRole.user_id == User.id,
        UserRole.status == "ACTIVE",
        UserRole.is_deleted.is_(False),
        Role.role_code == "STUDENT",
        Role.is_deleted.is_(False),
    ).exists()
    student_condition = (
        (User.user_type == "STUDENT") | linked_student | has_student_role
    )
    if account_type == "STUDENT":
        return student_condition
    return User.user_type.in_(STAFF_ACCOUNT_USER_TYPES) & ~student_condition


def _student_profile_user_ids(
        tenant_id: int, *, college_id: object = "", class_id: object = "",
        grade: object = "", student_status: object = ""):
    """按权威学生主档范围返回稳定绑定的账号 ID 子查询。"""
    from app.models import StudentAccountLink, StudentProfile
    stmt = select(StudentAccountLink.user_id).join(
        StudentProfile, StudentProfile.id == StudentAccountLink.student_id
    ).where(
        StudentAccountLink.tenant_id == tenant_id,
        StudentAccountLink.link_status == "ACTIVE",
        StudentAccountLink.is_deleted.is_(False),
        StudentProfile.tenant_id == tenant_id,
        StudentProfile.is_deleted.is_(False),
    )
    for raw, column in (
        (college_id, StudentProfile.college_id),
        (class_id, StudentProfile.class_id),
    ):
        if str(raw or "").isdigit():
            stmt = stmt.where(column == int(raw))
    if str(grade or "").strip():
        stmt = stmt.where(StudentProfile.grade == str(grade).strip())
    if str(student_status or "").strip():
        stmt = stmt.where(StudentProfile.student_status == str(student_status).strip().upper())
    return stmt


def _is_last_active_school_admin(db, tenant_id: int, user_id: int) -> bool:
    """最后一名可登录学校管理员不得被停用或移除管理员角色。"""
    from app.models import Role, User, UserRole
    owns_role = db.scalar(select(func.count(UserRole.id)).join(
        Role, Role.id == UserRole.role_id
    ).where(
        UserRole.tenant_id == tenant_id, UserRole.user_id == user_id,
        UserRole.status == "ACTIVE", UserRole.is_deleted.is_(False),
        Role.role_code == "SCHOOL_ADMIN", Role.is_deleted.is_(False),
    ))
    if not owns_role:
        return False
    active_admins = db.scalar(select(func.count(func.distinct(User.id))).join(
        UserRole, UserRole.user_id == User.id
    ).join(Role, Role.id == UserRole.role_id).where(
        User.tenant_id == tenant_id, User.status == "ACTIVE", User.is_deleted.is_(False),
        UserRole.tenant_id == tenant_id, UserRole.status == "ACTIVE", UserRole.is_deleted.is_(False),
        Role.role_code == "SCHOOL_ADMIN", Role.is_deleted.is_(False),
    ))
    return int(active_admins or 0) <= 1


def _role_scope(role) -> str:
    """只读兼容：优先结构化规则，历史 Role.remark 仅作回落。"""
    try:
        from app.services.data_scope_service import resolve_role_scope_code
        coded = resolve_role_scope_code(role)
        if coded:
            return coded
    except Exception:
        pass
    marker = str(role.remark or "")
    prefix = ";scope="
    return marker.split(prefix, 1)[1].split(";", 1)[0] if prefix in marker else "ASSIGNED"


def _set_role_scope(role, scope_code: str, *, target_json: dict | None = None, user: dict | None = None) -> None:
    """写入结构化数据范围；禁止再以 Role.remark 作为主链路。"""
    import re
    from app.services.data_scope_service import save_role_scope
    save_role_scope(role, scope_code, target_json=target_json, actor=user)
    # 同步调用方会话中的 role，避免外层 commit 用旧 remark 覆盖结构化标记
    remark = str(getattr(role, "remark", "") or "")
    remark = re.sub(r";scope=[^;]*", "", remark)
    remark = re.sub(r";permMode=[^;]*", "", remark).rstrip(";")
    role.remark = (remark + ";permMode=DB;scopeSource=RULE").lstrip(";")


def _role_row(role, member_count: int) -> dict:
    status = str(role.status or "").upper()
    return {
        "id": str(role.id), "name": role.role_name, "code": role.role_code,
        "type": "BUILTIN" if str(role.role_type or "").upper() == "SYSTEM" else "CUSTOM",
        "typeLabel": "预设角色" if str(role.role_type or "").upper() == "SYSTEM" else "自定义角色",
        "scopeCode": _role_scope(role), "scopeName": _role_scope(role),
        "memberCount": int(member_count or 0), "description": role.remark or "",
        "status": "ENABLED" if status in ("ACTIVE", "ENABLED") else "DISABLED",
        "statusLabel": "启用中" if status in ("ACTIVE", "ENABLED") else "已停用",
        "updatedAt": str(getattr(role, "updated_at", "") or "")[:19],
    }


def _mask_user_phone(raw: str | None) -> str:
    from app.core.field_crypto import decrypt_field
    from app.services.db_service import _mask_phone
    if not raw:
        return ""
    try:
        plain = decrypt_field(raw, allow_legacy_plaintext=True)
    except Exception:
        plain = None
    return _mask_phone(plain or "")


def _student_account_meta(db, account) -> dict:
    """通过稳定绑定返回学生主档投影；历史库才回落到登录名=学号。"""
    try:
        from app.models import (College, Major, SchoolClass, StudentAccountLink,
                                StudentProfile)
        link = db.scalars(select(StudentAccountLink).where(
            StudentAccountLink.tenant_id == account.tenant_id,
            StudentAccountLink.user_id == account.id,
            StudentAccountLink.link_status == "ACTIVE",
            StudentAccountLink.is_deleted.is_(False),
        )).first()
        sp = db.get(StudentProfile, link.student_id) if link is not None else None
        if sp is None:
            sp = db.scalars(select(StudentProfile).where(
                StudentProfile.tenant_id == account.tenant_id,
                StudentProfile.is_deleted.is_(False),
                StudentProfile.student_no == account.login_name,
            )).first()
        if sp is None:
            return {
                "studentId": "", "studentNo": account.login_name,
                "collegeId": "", "collegeName": "", "majorId": "", "majorName": "",
                "classId": "", "className": "", "grade": "",
                "studentStatus": "UNBOUND", "studentStatusLabel": "未绑定学生主档",
                "currentStage": "", "profileBound": False,
            }
        college = db.get(College, sp.college_id) if sp.college_id else None
        major = db.get(Major, sp.major_id) if sp.major_id else None
        cls = db.get(SchoolClass, sp.class_id) if sp.class_id else None
        student_status = str(sp.student_status or sp.status or "").upper()
        return {
            "studentId": str(sp.id), "studentNo": sp.student_no,
            "collegeId": str(sp.college_id or ""),
            "collegeName": college.college_name if college else "",
            "majorId": str(sp.major_id or ""),
            "majorName": major.major_name if major else "",
            "classId": str(sp.class_id or ""),
            "className": cls.class_name if cls else "",
            "grade": sp.grade or (cls.grade if cls else "") or "",
            "studentStatus": student_status,
            "studentStatusLabel": {
                "NORMAL": "正常在籍", "REGISTERED": "已注册", "SUSPENDED": "休学",
                "GRADUATED": "已毕业", "WITHDRAWN": "已退学", "MERGED": "已合并",
                "RECYCLED": "已作废",
            }.get(student_status, student_status or "未设置"),
            "currentStage": str(sp.current_stage or ""),
            "profileBound": True,
        }
    except Exception:
        return {
            "studentId": "", "studentNo": account.login_name,
            "collegeId": "", "collegeName": "", "majorId": "", "majorName": "",
            "classId": "", "className": "", "grade": "",
            "studentStatus": "UNBOUND", "studentStatusLabel": "主档读取失败",
            "currentStage": "", "profileBound": False,
        }


def _user_org_hint(db, account, account_type: str | None = None) -> tuple[str, str]:
    """学生读稳定主档绑定；教职工展示现有业务归属，不伪造人事部门。"""
    try:
        from app.models import TeacherStudentScope
        if (account_type or _account_type_of(account, db)) == "STUDENT":
            meta = _student_account_meta(db, account)
            name = " / ".join(
                x for x in (meta["collegeName"], meta["majorName"], meta["className"]) if x
            ) or "未绑定学生主档"
            return (meta["classId"] or meta["majorId"] or meta["collegeId"], name)
        scope = db.scalars(select(TeacherStudentScope).where(
            TeacherStudentScope.tenant_id == account.tenant_id,
            TeacherStudentScope.teacher_key == account.login_name).limit(1)).first()
        if scope is not None:
            return (str(scope.ref_value or ""), f"{scope.scope_type}:{scope.ref_value}" if scope.ref_value else "按岗位范围")
    except Exception:
        pass
    return ("", "未设置")


def _user_row(account, roles: list, db=None) -> dict:
    status = str(account.status or "").upper()
    account_type = _account_type_of(account, db, roles)
    org_id, org_name = ("", "未设置")
    if db is not None:
        org_id, org_name = _user_org_hint(db, account, account_type)
    phone_masked = _mask_user_phone(getattr(account, "phone_encrypted", None))
    row = {
        "id": str(account.id),
        "userNo": account.login_name,
        "loginName": account.login_name,
        "name": account.real_name,
        "realName": account.real_name,
        "userType": account.user_type,
        "accountType": account_type,
        "orgId": org_id, "orgName": org_name, "roles": [r.role_code for r in roles],
        "roleNames": [r.role_name for r in roles], "phone": phone_masked, "email": "",
        "mustChangePassword": bool(getattr(account, "must_change_password", False)),
        # SYS-03：写操作要带 expectedVersion，列表/详情必须把当前版本给出去
        "version": int(getattr(account, "version", 0) or 0),
        "status": "ACTIVE" if status == "ACTIVE" else status,
        "statusLabel": {"ACTIVE": "启用中", "DISABLED": "已停用", "LOCKED": "已锁定"}.get(status, "待激活"),
        "source": "统一师生导入" if account.user_type in ("TEACHER", "STUDENT") else "系统创建",
        "lastLoginAt": str(account.last_login_at or "")[:19], "createdAt": str(account.created_at or "")[:10],
    }
    if db is not None and row["accountType"] == "STUDENT":
        row.update(_student_account_meta(db, account))
    return row


@router.get("/system/readiness", summary="学校上线初始化检查（真实库）")
def get_system_readiness(user=Depends(require_permission("systemAdmin.dashboard.view"))):
    from app.models import College, Major, Role, SchoolClass, User
    tenant_id = current_tenant_id()
    db = get_sessionmaker()()
    try:
        def count(model):
            return int(db.scalar(select(func.count(model.id)).where(model.tenant_id == tenant_id,
                         model.is_deleted.is_(False))) or 0)
        values = {"accounts": count(User), "roles": count(Role), "colleges": count(College),
                  "majors": count(Major), "classes": count(SchoolClass)}
        checks = [
            {"key": "roles", "label": "预设角色", "passed": values["roles"] >= 26,
             "message": f"已初始化 {values['roles']} / 26 个角色"},
            {"key": "org", "label": "组织主数据", "passed": values["colleges"] > 0,
             "message": f"学院 {values['colleges']}，专业 {values['majors']}，班级 {values['classes']}"},
            {"key": "accounts", "label": "师生账号", "passed": values["accounts"] > 0,
             "message": f"已创建 {values['accounts']} 个账号（仅统一导入入口可创建）"},
        ]
        return success({"ready": all(item["passed"] for item in checks), "counts": values, "checks": checks})
    finally:
        db.close()


@router.get("/system/org-tree", summary="学院专业班级组织树（真实库）")
def get_system_org_tree(user=Depends(require_permission("systemAdmin.org.view"))):
    from app.models import College, Major, SchoolClass, StudentProfile
    tenant_id = current_tenant_id()
    db = get_sessionmaker()()
    try:
        colleges = db.scalars(select(College).where(College.tenant_id == tenant_id,
                             College.is_deleted.is_(False)).order_by(College.sort_order, College.college_name)).all()
        majors = db.scalars(select(Major).where(Major.tenant_id == tenant_id, Major.is_deleted.is_(False))).all()
        classes = db.scalars(select(SchoolClass).where(SchoolClass.tenant_id == tenant_id,
                                SchoolClass.is_deleted.is_(False))).all()
        student_counts = dict(db.execute(select(StudentProfile.class_id, func.count(StudentProfile.id)).where(
            StudentProfile.tenant_id == tenant_id, StudentProfile.is_deleted.is_(False)).group_by(StudentProfile.class_id)).all())
        by_college = {c.id: [] for c in colleges}; by_major = {m.id: [] for m in majors}
        for major in majors: by_college.setdefault(major.college_id, []).append(major)
        for school_class in classes: by_major.setdefault(school_class.major_id, []).append(school_class)
        rows = []
        for college in colleges:
            major_rows = []
            for major in by_college.get(college.id, []):
                class_rows = [{"id": str(c.id), "code": c.class_code or "", "name": c.class_name,
                               "type": "CLASS", "typeLabel": "班级", "memberCount": int(student_counts.get(c.id, 0)),
                               "status": "ENABLED" if c.status == "ACTIVE" else "DISABLED", "children": []}
                              for c in by_major.get(major.id, [])]
                major_rows.append({"id": str(major.id), "code": major.code or "", "name": major.major_name,
                                   "type": "MAJOR", "typeLabel": "专业", "memberCount": sum(x["memberCount"] for x in class_rows),
                                   "status": "ENABLED" if major.status == "ACTIVE" else "DISABLED", "children": class_rows})
            rows.append({"id": str(college.id), "code": college.code or "", "name": college.college_name,
                         "type": "COLLEGE", "typeLabel": "学院", "memberCount": sum(x["memberCount"] for x in major_rows),
                         "status": "ENABLED" if college.status == "ACTIVE" else "DISABLED", "children": major_rows})
        return success(rows)
    finally:
        db.close()


@router.post("/system/org-nodes", summary="创建学院、专业或班级主数据")
@router.put("/system/org-nodes/{node_id}", summary="更新学院、专业或班级主数据")
def save_system_org_node(body: dict = Body(...), node_id: int | None = None,
                         user=Depends(require_any_permission("systemAdmin.org.create", "systemAdmin.org.update",
                                                              "systemAdmin.org.major.manage", "systemAdmin.org.class.manage"))):
    from app.services.org_master_service import save_org_node
    result = save_org_node(
        node_type=str((body or {}).get("type") or ""),
        name=str((body or {}).get("name") or ""),
        code=str((body or {}).get("code") or ""),
        parent_id=(body or {}).get("parentId"),
        node_id=node_id,
        reason=str((body or {}).get("reason") or ""),
        expected_version=(body or {}).get("expectedVersion"),
        actor=user,
    )
    return success({"id": result["id"], "version": result.get("version")}, message="组织主数据已保存")


@router.get("/system/roles", summary="学校预设角色与成员统计（真实库）")
def list_system_roles(
        keyword: str = "", type: str = "", status: str = "", page: int = 1, page_size: int = 50,
        user=Depends(require_permission("systemAdmin.role.view"))):
    if not db_enabled():
        from app.core.exceptions import AppException
        raise AppException("UNAUTHORIZED", "角色目录需启用数据库")
    from app.models import Role, UserRole
    tenant_id = current_tenant_id()
    db = get_sessionmaker()()
    try:
        stmt = select(Role).where(Role.tenant_id == tenant_id, Role.is_deleted.is_(False))
        if keyword.strip():
            like = f"%{keyword.strip()}%"
            stmt = stmt.where(Role.role_name.like(like) | Role.role_code.like(like))
        if type.upper() == "BUILTIN":
            stmt = stmt.where(Role.role_type == "SYSTEM")
        elif type.upper() == "CUSTOM":
            stmt = stmt.where((Role.role_type != "SYSTEM") | Role.role_type.is_(None))
        if status.upper() == "ENABLED":
            stmt = stmt.where(Role.status.in_(("ACTIVE", "ENABLED")))
        elif status.upper() == "DEPRECATED":
            stmt = stmt.where(Role.status.notin_(("ACTIVE", "ENABLED")))
        roles = db.scalars(stmt.order_by(Role.role_type, Role.role_code)).all()
        counts = dict(db.execute(
            select(UserRole.role_id, func.count(UserRole.id))
            .where(UserRole.tenant_id == tenant_id, UserRole.is_deleted.is_(False), UserRole.status == "ACTIVE")
            .group_by(UserRole.role_id)
        ).all())
        page = max(1, int(page or 1)); page_size = min(100, max(1, int(page_size or 50)))
        total = len(roles); start = (page - 1) * page_size
        return success({"list": [_role_row(role, counts.get(role.id, 0)) for role in roles[start:start + page_size]],
                        "total": total, "page": page, "pageSize": page_size})
    finally:
        db.close()


@router.get("/system/users", summary="学校账号列表（真实库）")
def list_system_users(
        keyword: str = "", role: str = "", status: str = "", account_type: str = "",
        college_id: str = "", major_id: str = "", class_id: str = "", grade: str = "",
        student_status: str = "", page: int = 1, page_size: int = 20,
                      user=Depends(require_permission("systemAdmin.user.view"))):
    from app.models import Role, User, UserRole
    tenant_id = current_tenant_id()
    normalized_type = _normalize_account_type(account_type)
    db = get_sessionmaker()()
    try:
        stmt = select(User).where(User.tenant_id == tenant_id, User.is_deleted.is_(False))
        if normalized_type:
            stmt = stmt.where(_account_type_condition(User, normalized_type, tenant_id))
        if keyword.strip():
            like = f"%{keyword.strip()}%"
            stmt = stmt.where(User.login_name.like(like) | User.real_name.like(like))
        if status.strip():
            stmt = stmt.where(User.status == status.upper())
        if role.strip():
            stmt = stmt.where(User.id.in_(select(UserRole.user_id).join(Role, Role.id == UserRole.role_id).where(
                UserRole.tenant_id == tenant_id, UserRole.status == "ACTIVE", UserRole.is_deleted.is_(False),
                Role.role_code == role.strip().upper(), Role.is_deleted.is_(False))))
        student_filters = {
            "college_id": college_id, "major_id": major_id, "class_id": class_id,
            "grade": grade, "student_status": student_status,
        }
        if any(str(value or "").strip() for value in student_filters.values()):
            profile_users = _student_profile_user_ids(
                tenant_id, college_id=college_id, class_id=class_id,
                grade=grade, student_status=student_status)
            if str(major_id or "").isdigit():
                from app.models import StudentProfile, StudentAccountLink
                profile_users = profile_users.where(StudentProfile.major_id == int(major_id))
            stmt = stmt.where(User.id.in_(profile_users))
        page = max(1, int(page or 1))
        page_size = min(100, max(1, int(page_size or 20)))
        total = int(db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0)
        users = db.scalars(
            stmt.order_by(User.created_at.desc(), User.id.desc())
            .offset((page - 1) * page_size).limit(page_size)
        ).all()
        user_ids = [u.id for u in users]
        by_user: dict[int, list] = {uid: [] for uid in user_ids}
        if user_ids:
            for uid, r in db.execute(select(UserRole.user_id, Role).join(Role, Role.id == UserRole.role_id).where(
                UserRole.tenant_id == tenant_id, UserRole.user_id.in_(user_ids), UserRole.status == "ACTIVE",
                UserRole.is_deleted.is_(False), Role.status.in_(("ACTIVE", "ENABLED")), Role.is_deleted.is_(False))).all():
                by_user[uid].append(r)
        return success({"list": [_user_row(account, by_user.get(account.id, []), db) for account in users],
                        "total": total, "page": page, "pageSize": page_size,
                        "accountType": normalized_type or "MIXED_LEGACY"})
    finally:
        db.close()


@router.get("/system/users/{user_id}", summary="学校账号详情（真实库）")
def get_system_user(user_id: int, user=Depends(require_permission("systemAdmin.user.view"))):
    from app.core.exceptions import AppException
    from app.models import Role, User, UserRole
    from app.models.audit import SecurityAuditLog
    tenant_id = current_tenant_id()
    db = get_sessionmaker()()
    try:
        account = db.scalars(select(User).where(User.id == user_id, User.tenant_id == tenant_id,
                                                User.is_deleted.is_(False))).first()
        if account is None:
            raise AppException("DATA_NOT_FOUND", "账号不存在或不在当前数据范围内")
        roles = [r for _, r in db.execute(select(UserRole.user_id, Role).join(Role, Role.id == UserRole.role_id).where(
            UserRole.tenant_id == tenant_id, UserRole.user_id == user_id, UserRole.status == "ACTIVE",
            UserRole.is_deleted.is_(False), Role.is_deleted.is_(False))).all()]
        row = _user_row(account, roles, db)
        audits = db.scalars(select(SecurityAuditLog).where(
            SecurityAuditLog.tenant_id == tenant_id,
            SecurityAuditLog.resource.like(f"%{account.login_name}%")
        ).order_by(SecurityAuditLog.id.desc()).limit(20)).all()
        row.update({
            "roles": [{"code": r.role_code, "name": r.role_name, "scopeName": _role_scope(r)} for r in roles],
            "contexts": [r.role_name for r in roles],
            "loginHistory": [],
            "auditTrail": [{"who": a.operator_name or "系统", "time": str(a.created_at or "")[:19],
                            "action": a.action, "affected": a.resource or ""} for a in audits],
        })
        return success(row)
    finally:
        db.close()


@router.put("/system/users/{user_id}", summary="编辑学校账号基础信息（不可改工号；建号请走统一导入）")
def update_system_user(user_id: int, body: dict = Body(...),
                       user=Depends(require_permission("systemAdmin.user.manage"))):
    from app.core.exceptions import AppException
    from app.models import Role, User, UserRole
    tenant_id = current_tenant_id()
    name = str((body or {}).get("name") or (body or {}).get("realName") or "").strip()
    phone = str((body or {}).get("phone") or "").strip()
    if len(name) < 2:
        raise AppException("VALIDATION_ERROR", "姓名至少 2 个字")
    if phone and (not phone.isdigit() or len(phone) < 11):
        # 允许传入已脱敏号码（含*）时忽略更新
        if "*" in phone:
            phone = ""
        else:
            raise AppException("VALIDATION_ERROR", "手机号格式不正确")
    db = get_sessionmaker()()
    try:
        account = db.scalars(select(User).where(User.id == user_id, User.tenant_id == tenant_id,
                                                User.is_deleted.is_(False))).first()
        if account is None:
            raise AppException("DATA_NOT_FOUND", "账号不存在")
        if _account_type_of(account, db) == "STUDENT" and name != account.real_name:
            raise AppException("VALIDATION_ERROR", "学生姓名属于学生主档，请到学生主档办理更正")
        _check_account_version(account, (body or {}).get("expectedVersion"))
        before = {"name": account.real_name, "phone": _mask_user_phone(account.phone_encrypted)}
        account.real_name = name
        if phone:
            from app.core.field_crypto import encrypt_field, hash_sensitive
            account.phone_encrypted = encrypt_field(phone)
            account.phone_hash = hash_sensitive(phone, "phone")
        account.version = int(account.version or 0) + 1
        db.commit(); db.refresh(account)
        roles = [r for _, r in db.execute(select(UserRole.user_id, Role).join(Role, Role.id == UserRole.role_id).where(
            UserRole.tenant_id == tenant_id, UserRole.user_id == user_id, UserRole.status == "ACTIVE",
            UserRole.is_deleted.is_(False), Role.is_deleted.is_(False))).all()]
        from app.services import audit_log
        audit_log.record("USER_UPDATE", f"账号 {account.login_name}（{account.real_name}）",
                         detail={"before": before, "after": {"name": name, "phone": _mask_user_phone(account.phone_encrypted)},
                                 "summary": "编辑账号基础信息"})
        return success(_user_row(account, roles, db), message="账号信息已更新")
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


@router.put("/system/user-batch-status", summary="批量停用/启用学校账号")
def batch_set_system_user_status(body: dict = Body(...),
                                 user=Depends(require_permission("systemAdmin.user.manage"))):
    from app.core.exceptions import AppException
    from app.models import User
    action = str((body or {}).get("action") or "DISABLE").strip().upper()
    reason = str((body or {}).get("reason") or "").strip()
    account_type = _normalize_account_type((body or {}).get("accountType"))
    scope = str((body or {}).get("scope") or "SELECTED").strip().upper()
    filters = (body or {}).get("filters") or {}
    ids = [int(x) for x in (body or {}).get("ids") or [] if str(x).isdigit() or isinstance(x, int)]
    if action == "DISABLE" and len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "批量停用原因必填且不少于 5 个字")
    if scope not in ("SELECTED", "CLASS", "GRADE", "COLLEGE", "SCHOOL"):
        raise AppException("VALIDATION_ERROR", "批量停用范围无效")

    # 大批量学生账号按主档范围在数据库内一次完成，不能把几千个 ID 发给前端逐个调用。
    if scope != "SELECTED":
        if action != "DISABLE" or account_type != "STUDENT":
            raise AppException("VALIDATION_ERROR", "班级、年级、学院和全校范围仅支持批量停用学生账号")
        scope_value = {
            "CLASS": filters.get("classId"),
            "GRADE": filters.get("grade"),
            "COLLEGE": filters.get("collegeId"),
        }.get(scope)
        if scope != "SCHOOL" and not str(scope_value or "").strip():
            raise AppException("VALIDATION_ERROR", "请选择具体的班级、年级或学院")
        if scope in ("CLASS", "COLLEGE") and not str(scope_value).isdigit():
            raise AppException("VALIDATION_ERROR", "班级或学院参数无效")
        if scope == "SCHOOL" and (body or {}).get("confirmSchoolScope") is not True:
            raise AppException("VALIDATION_ERROR", "全校停用属于高风险操作，请完成全校范围二次确认")

        tenant_id = current_tenant_id()
        db = get_sessionmaker()()
        try:
            stmt = select(User).where(
                User.tenant_id == tenant_id,
                User.is_deleted.is_(False),
                User.status == "ACTIVE",
                _account_type_condition(User, "STUDENT", tenant_id),
            )
            if scope != "SCHOOL":
                profile_users = _student_profile_user_ids(
                    tenant_id,
                    college_id=scope_value if scope == "COLLEGE" else "",
                    class_id=scope_value if scope == "CLASS" else "",
                    grade=scope_value if scope == "GRADE" else "",
                )
                stmt = stmt.where(User.id.in_(profile_users))
            accounts = db.scalars(stmt).all()
            disabled_ids = []
            for account in accounts:
                account.status = "DISABLED"
                account.version = int(account.version or 0) + 1
                disabled_ids.append(int(account.id))
            db.commit()
            count = len(accounts)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

        # 单个停用会清主体缓存，按范围批量停用原来没清：被停用的学生在缓存 TTL 内
        # 仍然带着旧令牌照常访问。逐个清掉，让停用立刻生效。
        from app.services.auth_service_db import invalidate_subject_cache
        for uid in disabled_ids:
            try:
                invalidate_subject_cache(f"db-{uid}", tenant_id)
            except Exception:  # noqa: BLE001
                pass

        from app.services import audit_log
        scope_label = {
            "CLASS": "班级", "GRADE": "年级", "COLLEGE": "学院", "SCHOOL": "全校",
        }[scope]
        audit_log.record("USER_BATCH_DISABLE", f"{scope_label}学生账号批量停用", detail={
            "scope": scope,
            "scopeValue": str(scope_value or ""),
            "count": count,
            "reason": reason,
            "summary": f"按{scope_label}范围批量停用学生账号（逻辑停用，可恢复）",
        })
        return success({"count": count, "errors": [], "scope": scope},
                       message=f"已按{scope_label}范围停用 {count} 个学生账号")

    if not ids:
        raise AppException("VALIDATION_ERROR", "请选择账号")
    if account_type:
        db = get_sessionmaker()()
        try:
            matched = int(db.scalar(select(func.count(User.id)).where(
                User.tenant_id == current_tenant_id(),
                User.id.in_(ids),
                User.is_deleted.is_(False),
                _account_type_condition(User, account_type, current_tenant_id()),
            )) or 0)
        finally:
            db.close()
        if matched != len(set(ids)):
            raise AppException("VALIDATION_ERROR", "所选账号包含其他类型，已拒绝批量操作")
    self_id = _acting_db_id(user)
    count = 0
    errors = []
    results = []  # SYS03-T04：逐项结果，不能只回一个总数让管理员猜哪一条没成
    for uid in ids:
        if action == "DISABLE" and self_id == uid:
            errors.append({"id": uid, "message": "不能停用本人"})
            results.append({"id": str(uid), "status": "FAILED", "message": "不能停用本人"})
            continue
        try:
            set_system_user_status(uid, {"action": action, "reason": reason}, user=user)
            count += 1
            results.append({"id": str(uid), "status": "OK",
                            "message": "已停用" if action == "DISABLE" else "已启用"})
        except Exception as exc:  # noqa: BLE001
            message = getattr(exc, "message", None) or str(exc)
            errors.append({"id": uid, "message": message})
            results.append({"id": str(uid), "status": "FAILED", "message": message})
    return success({"count": count, "errors": errors, "results": results,
                    "total": len(results), "succeeded": count, "failed": len(errors)},
                   message=f"已处理 {count} 个账号" + (f"，{len(errors)} 个失败" if errors else ""))


@router.get("/system/users-exceptions", summary="账号异常中心（锁定/停用/长期未登录/强制改密）")
def list_account_exceptions(account_type: str = "", page: int = 1, page_size: int = 50,
                            user=Depends(require_any_permission(
                                "systemAdmin.user.exception.view", "systemAdmin.user.view", "systemAdmin.user.manage"))):
    from datetime import datetime, timedelta
    from app.models import Role, User, UserRole
    tenant_id = current_tenant_id()
    normalized_type = _normalize_account_type(account_type)
    db = get_sessionmaker()()
    try:
        stmt = select(User).where(User.tenant_id == tenant_id, User.is_deleted.is_(False))
        if normalized_type:
            stmt = stmt.where(_account_type_condition(User, normalized_type, tenant_id))
        users = db.scalars(stmt.order_by(User.updated_at.desc())).all()
        cutoff = datetime.utcnow() - timedelta(days=90)
        rows = []
        for account in users:
            status = str(account.status or "").upper()
            reasons = []
            if status == "LOCKED":
                reasons.append("账号已锁定")
            if status == "DISABLED":
                reasons.append("账号已停用")
            if getattr(account, "must_change_password", False):
                reasons.append("待强制改密")
            if (
                (account.last_login_at is None and account.created_at and account.created_at < cutoff)
                or (account.last_login_at is not None and account.last_login_at < cutoff)
            ):
                reasons.append("超过90天未登录")
            if not reasons:
                continue
            roles = [r for _, r in db.execute(select(UserRole.user_id, Role).join(Role, Role.id == UserRole.role_id).where(
                UserRole.tenant_id == tenant_id, UserRole.user_id == account.id, UserRole.status == "ACTIVE",
                UserRole.is_deleted.is_(False), Role.is_deleted.is_(False))).all()]
            item = _user_row(account, roles, db)
            item["exceptionReasons"] = reasons
            rows.append(item)
        page = max(1, int(page or 1)); page_size = min(100, max(1, int(page_size or 50)))
        start = (page - 1) * page_size
        return success({"list": rows[start:start + page_size], "total": len(rows),
                        "page": page, "pageSize": page_size,
                        "accountType": normalized_type or "MIXED_LEGACY"})
    finally:
        db.close()


# ── SYS-05 业务关系中心（只发现与治理，不复制业务关系数据）────────────────────
@router.get("/system/business-relations/types", summary="业务关系注册表（owner/resolver/测试真实校验）")
def api_business_relation_types(user=Depends(require_any_permission(
        "systemAdmin.org.view", "systemAdmin.role.view", "systemAdmin.dashboard.view"))):
    from app.services import business_relation_registry as registry
    return success(registry.list_types())


@router.get("/system/business-relations/issues", summary="业务关系缺口（按业务权威表实时统计）")
def api_business_relation_issues(user=Depends(require_any_permission(
        "systemAdmin.org.view", "systemAdmin.role.view", "systemAdmin.dashboard.view"))):
    from app.services import business_relation_registry as registry
    return success(registry.list_issues())


@router.post("/system/business-relations/{relation_type}/validate", summary="校验单个业务关系类型")
def api_validate_business_relation(relation_type: str, user=Depends(require_any_permission(
        "systemAdmin.org.view", "systemAdmin.role.view"))):
    from app.services import business_relation_registry as registry
    return success(registry.validate_type(relation_type))


# ── SYS-03 稳定主体解析与绑定修复 ────────────────────────────────────────────
@router.get("/system/accounts/identity-issues", summary="身份绑定异常队列（学号改名/未绑定/同名同手机号）")
def api_identity_issues(issue_code: str = "", page: int = 1, page_size: int = 50,
                        user=Depends(require_any_permission(
                            "systemAdmin.user.exception.view", "systemAdmin.user.view",
                            "systemAdmin.user.manage"))):
    from app.services import account_identity_resolution_service as ident
    return success(ident.identity_issues(issue_code=issue_code, page=page, page_size=page_size))


@router.get("/system/accounts/{user_id}/effective-identity", summary="账号的稳定主体解析（userId/studentId/staffId）")
def api_effective_identity(user_id: int, user=Depends(require_any_permission(
        "systemAdmin.user.view", "systemAdmin.user.manage"))):
    from app.services import account_identity_resolution_service as ident
    return success(ident.effective_identity(user_id))


@router.post("/system/accounts/{user_id}/repair-binding", summary="修复身份绑定（登录名兜底转结构化绑定）")
def api_repair_binding(user_id: int, body: dict = Body(...),
                       user=Depends(require_any_permission(
                           "systemAdmin.user.bind", "systemAdmin.user.manage"))):
    from app.core.exceptions import AppException
    from app.services import account_identity_resolution_service as ident
    payload = body or {}
    student_id = str(payload.get("studentId") or "").strip()
    if not student_id.isdigit():
        raise AppException("VALIDATION_ERROR", "studentId 必须是学籍主档主键")
    return success(ident.repair_binding(
        user_id, student_id=int(student_id), reason=payload.get("reason") or "",
        expected_version=payload.get("expectedVersion"), user=user), message="绑定已修复")


@router.post("/system/accounts/{user_id}/unbind", summary="解除身份绑定（历史留痕，不物理删除）")
def api_unbind_identity(user_id: int, body: dict = Body(...),
                        user=Depends(require_any_permission(
                            "systemAdmin.user.bind", "systemAdmin.user.manage"))):
    from app.services import account_identity_resolution_service as ident
    payload = body or {}
    return success(ident.unbind(
        user_id, reason=payload.get("reason") or "",
        expected_version=payload.get("expectedVersion"), user=user), message="绑定已解除")


@router.post("/system/accounts/batch-repair-binding", summary="批量修复绑定（逐项返回结果）")
def api_batch_repair_binding(body: dict = Body(...),
                             user=Depends(require_any_permission(
                                 "systemAdmin.user.bind", "systemAdmin.user.manage"))):
    from app.services import account_identity_resolution_service as ident
    payload = body or {}
    return success(ident.batch_repair(payload.get("items") or [],
                                      reason=payload.get("reason") or "", user=user),
                   message="批量修复已完成，请逐项查看结果")


@router.get("/system/staff-affiliations", summary="教职工岗位与归属（班级辅导员/班主任 + 教师范围）")
def list_staff_affiliations(user=Depends(require_any_permission(
        "systemAdmin.org.affiliation.manage", "systemAdmin.org.view"))):
    from app.models import College, SchoolClass, TeacherStudentScope
    tenant_id = current_tenant_id()
    db = get_sessionmaker()()
    try:
        rows = []
        for cls in db.scalars(select(SchoolClass).where(SchoolClass.tenant_id == tenant_id,
                                SchoolClass.is_deleted.is_(False))).all():
            if getattr(cls, "counselor_id", None):
                rows.append({"id": f"class-counselor-{cls.id}", "orgName": cls.class_name, "orgType": "CLASS",
                             "roleLabel": "辅导员", "staffKey": str(cls.counselor_id), "status": "ACTIVE"})
            if getattr(cls, "head_teacher_id", None):
                rows.append({"id": f"class-head-{cls.id}", "orgName": cls.class_name, "orgType": "CLASS",
                             "roleLabel": "班主任", "staffKey": str(cls.head_teacher_id), "status": "ACTIVE"})
        for college in db.scalars(select(College).where(College.tenant_id == tenant_id,
                                  College.is_deleted.is_(False))).all():
            if getattr(college, "secretary_id", None):
                rows.append({"id": f"college-sec-{college.id}", "orgName": college.college_name, "orgType": "COLLEGE",
                             "roleLabel": "教学秘书", "staffKey": str(college.secretary_id), "status": "ACTIVE"})
        for scope in db.scalars(select(TeacherStudentScope).where(
                TeacherStudentScope.tenant_id == tenant_id).limit(200)).all():
            rows.append({"id": f"scope-{scope.id}", "orgName": f"{scope.scope_type}:{scope.ref_value}",
                         "orgType": scope.scope_type, "roleLabel": scope.role_code or "岗位范围",
                         "staffKey": scope.teacher_key, "staffName": scope.teacher_name or "",
                         "status": getattr(scope, "status", None) or "ACTIVE"})
        return success({"list": rows, "total": len(rows)})
    finally:
        db.close()


@router.get("/system/permissions/tree", summary="学校可配置权限树（真实 permissionCode）")
def get_permission_tree(user=Depends(require_permission("systemAdmin.role.config"))):
    from app.services.system_admin_catalog_service import build_permission_tree, visible_codes_from_tree
    tree = build_permission_tree(user)
    return success({"tree": tree, "visibleCodes": sorted(visible_codes_from_tree(tree))})


@router.get("/system/context", summary="系统管理页上下文（品牌/角色/权限动作）")
def get_system_context(user=Depends(require_any_permission(
        "systemAdmin.dashboard.view", "systemAdmin.user.view", "systemAdmin.role.view",
        "systemAdmin.org.view", "systemAdmin.audit.view", "systemAdmin.config.view",
        "systemAdmin.implementation.view", "systemAdmin.scope.view"))):
    from app.core.permissions import get_effective_access_context, has_permission
    tenant_id = int(current_tenant_id() or 0)
    brand = {}
    role_options = []
    college_options = []
    class_options = []
    grade_options = []
    if db_enabled():
        from app.models import College, Role, SchoolClass, StudentProfile
        db = get_sessionmaker()()
        try:
            brand = _brand_form(db, tenant_id)
            roles = db.scalars(select(Role).where(
                Role.tenant_id == tenant_id,
                Role.is_deleted.is_(False),
                Role.status.in_(("ACTIVE", "ENABLED")),
            ).order_by(Role.role_type, Role.role_name)).all()
            colleges = db.scalars(select(College).where(
                College.tenant_id == tenant_id,
                College.is_deleted.is_(False),
                College.status == "ACTIVE",
            ).order_by(College.college_name)).all()
            role_options = [{"value": row.role_code, "label": row.role_name} for row in roles]
            college_options = [{"value": str(row.id), "label": row.college_name} for row in colleges]
            classes = db.scalars(select(SchoolClass).where(
                SchoolClass.tenant_id == tenant_id,
                SchoolClass.is_deleted.is_(False),
                SchoolClass.status == "ACTIVE",
            ).order_by(SchoolClass.grade.desc(), SchoolClass.class_name)).all()
            class_options = [{
                "value": str(row.id),
                "label": " · ".join(x for x in (row.grade, row.class_name) if x),
            } for row in classes]
            grades = db.scalars(select(StudentProfile.grade).where(
                StudentProfile.tenant_id == tenant_id,
                StudentProfile.is_deleted.is_(False),
                StudentProfile.grade.is_not(None),
                StudentProfile.grade != "",
            ).distinct().order_by(StudentProfile.grade.desc())).all()
            grade_options = [{"value": str(value), "label": str(value)} for value in grades]
        finally:
            db.close()
    role_code = (user or {}).get("currentRoleCode") or ""
    access = get_effective_access_context(user or {})
    patterns = list(access.get("permissionPatterns") or [])
    actions = {
        "importUsers": {"visible": True, "allowed": has_permission(user, "systemAdmin.user.import"), "reason": ""},
        "exportUsers": {"visible": True, "allowed": has_permission(user, "systemAdmin.user.export") or has_permission(user, "systemAdmin.user.view"), "reason": ""},
        "createUser": {"visible": False, "allowed": False, "reason": "师生账号只能通过统一导入入口创建"},
        "editUser": {"visible": True, "allowed": has_permission(user, "systemAdmin.user.manage"), "reason": ""},
        "disableUser": {"visible": True, "allowed": has_permission(user, "systemAdmin.user.manage"), "reason": ""},
        "enableUser": {"visible": True, "allowed": has_permission(user, "systemAdmin.user.manage"), "reason": ""},
        "resetPassword": {"visible": True, "allowed": has_permission(user, "systemAdmin.user.manage"), "reason": ""},
        "batchDisableUsers": {"visible": True, "allowed": has_permission(user, "systemAdmin.user.manage"), "reason": ""},
        "assignRole": {"visible": True, "allowed": has_permission(user, "systemAdmin.user.assign-role"), "reason": ""},
        "viewSensitiveFull": {"visible": True, "allowed": has_permission(user, "systemAdmin.user.sensitive.view"),
                              "reason": "查看完整敏感字段需要专项权限，操作将被审计"},
        "createRole": {"visible": True, "allowed": has_permission(user, "systemAdmin.role.create"), "reason": ""},
        "editRole": {"visible": True, "allowed": has_permission(user, "systemAdmin.role.config"), "reason": ""},
        "copyRole": {"visible": True, "allowed": has_permission(user, "systemAdmin.role.create"), "reason": ""},
        "configRolePermission": {"visible": True, "allowed": has_permission(user, "systemAdmin.role.config"), "reason": ""},
        "configRoleScope": {"visible": True, "allowed": has_permission(user, "systemAdmin.role.config"), "reason": ""},
        "deprecateRole": {"visible": True, "allowed": has_permission(user, "systemAdmin.role.config"), "reason": ""},
        "exportRoleConfig": {"visible": True, "allowed": has_permission(user, "systemAdmin.role.view"), "reason": ""},
        "createOrg": {"visible": True, "allowed": has_permission(user, "systemAdmin.org.create"), "reason": ""},
        "editOrg": {"visible": True, "allowed": has_permission(user, "systemAdmin.org.update"), "reason": ""},
        "deprecateOrg": {"visible": True, "allowed": has_permission(user, "systemAdmin.org.manage"), "reason": ""},
        "importOrg": {"visible": True, "allowed": has_permission(user, "systemAdmin.implementation.mapping.manage"),
                      "reason": "请前往实施中心「数据导入与智能匹配」"},
        "exportOrg": {"visible": True, "allowed": has_permission(user, "systemAdmin.org.view"), "reason": ""},
        "editBrandConfig": {"visible": True, "allowed": has_permission(user, "systemAdmin.config.manage"), "reason": ""},
        "resetBrandConfig": {"visible": True, "allowed": has_permission(user, "systemAdmin.config.manage"), "reason": ""},
        "editSystemConfig": {"visible": True, "allowed": has_permission(user, "systemAdmin.config.manage"), "reason": ""},
        "exportSystemConfig": {"visible": True, "allowed": has_permission(user, "systemAdmin.config.view"), "reason": ""},
        "saveConfig": {"visible": True, "allowed": has_permission(user, "systemAdmin.config.manage"), "reason": ""},
        "viewLoginLogs": {"visible": True, "allowed": has_permission(user, "systemAdmin.audit.view"), "reason": ""},
        "viewOperationLogs": {"visible": True, "allowed": has_permission(user, "systemAdmin.audit.view"), "reason": ""},
        "exportLogs": {"visible": True, "allowed": has_permission(user, "systemAdmin.audit.view"), "reason": ""},
        "exportScopeRules": {"visible": True, "allowed": has_permission(user, "systemAdmin.scope.view"), "reason": ""},
        "createScopeRule": {"visible": True, "allowed": has_permission(user, "systemAdmin.scope.manage"), "reason": ""},
        "editScopeRule": {"visible": True, "allowed": has_permission(user, "systemAdmin.scope.manage"), "reason": ""},
        "viewScopeAffected": {"visible": True, "allowed": has_permission(user, "systemAdmin.scope.view"), "reason": ""},
        "saveScopeRule": {"visible": True, "allowed": has_permission(user, "systemAdmin.scope.manage"), "reason": ""},
        "deprecateScopeRule": {"visible": True, "allowed": has_permission(user, "systemAdmin.scope.manage"), "reason": ""},
    }
    for key, meta in actions.items():
        if not meta["allowed"] and not meta["reason"]:
            meta["reason"] = "当前角色无此操作权限"
    return success({
        "tenantBrandConfig": brand,
        "currentRole": {"roleCode": role_code, "roleName": (user or {}).get("realName") or role_code,
                        "userName": (user or {}).get("realName") or "", "userId": (user or {}).get("userId")},
        "dataScope": {"scopeCode": (user or {}).get("dataScope") or "TENANT", "scopeName": "按当前角色数据范围"},
        "permissionActions": actions,
        "permissionPatterns": patterns,
        "moduleEntitlements": access.get("moduleEntitlements") or [],
        "moduleStates": access.get("moduleStates") or {},
        "permissionVersion": access.get("permissionVersion"),
        "statusOptions": {
            "userStatus": [{"value": "ACTIVE", "label": "启用中"}, {"value": "DISABLED", "label": "已停用"},
                           {"value": "LOCKED", "label": "已锁定"}],
            "scopeTypes": [{"value": k, "label": v} for k, v in _SCOPE_LABELS.items()],
            "roleStatus": [{"value": "ENABLED", "label": "启用中"},
                           {"value": "DEPRECATED", "label": "已作废"}],
            "roleType": [{"value": "BUILTIN", "label": "内置角色"},
                         {"value": "CUSTOM", "label": "自定义角色"}],
            "ruleStatus": [{"value": "ENABLED", "label": "启用中"},
                           {"value": "DEPRECATED", "label": "已作废"}],
        },
        "filterOptions": {"roles": role_options, "colleges": college_options,
                          "classes": class_options, "grades": grade_options,
                          "logModules": [], "logActions": []},
        "fieldColumns": {}, "batchActions": [], "importTemplates": {}, "exportOptions": {},
    })


@router.put("/system/users/{user_id}/roles", summary="分配学校账号角色")
def assign_system_user_roles(user_id: int, body: dict = Body(...),
                             user=Depends(require_permission("systemAdmin.user.assign-role"))):
    from app.core.exceptions import AppException
    from app.core.permissions import ROLE_PERMISSIONS, has_permission
    from app.models import Permission, Role, RolePermission, User, UserRole
    tenant_id = current_tenant_id()
    codes = sorted({str(code).strip().upper() for code in (body.get("roleCodes") or []) if str(code).strip()})
    if not codes:
        raise AppException("VALIDATION_ERROR", "至少保留一个角色")
    db = get_sessionmaker()()
    try:
        account = db.scalars(select(User).where(User.id == user_id, User.tenant_id == tenant_id,
                                                User.is_deleted.is_(False))).first()
        if account is None: raise AppException("DATA_NOT_FOUND", "账号不存在")
        if _account_type_of(account, db) == "STUDENT":
            if codes != ["STUDENT"]:
                raise AppException("NO_PERMISSION", "学生账号固定绑定 STUDENT，禁止分配教职工或管理员角色")
        elif "STUDENT" in codes:
            raise AppException("VALIDATION_ERROR", "教职工账号不能绑定 STUDENT 角色")
        if "SCHOOL_ADMIN" not in codes and _is_last_active_school_admin(db, tenant_id, account.id):
            raise AppException("VALIDATION_ERROR", "不能移除本校最后一名启用中的学校管理员")
        roles = db.scalars(select(Role).where(Role.tenant_id == tenant_id, Role.role_code.in_(codes),
                                              Role.status.in_(("ACTIVE", "ENABLED")), Role.is_deleted.is_(False))).all()
        if len(roles) != len(codes): raise AppException("VALIDATION_ERROR", "包含不存在或已停用的角色")
        for role_obj in roles:
            if str(role_obj.role_type or "").upper() == "SYSTEM":
                patterns = ROLE_PERMISSIONS.get(role_obj.role_code, set())
            else:
                patterns = set(db.scalars(select(Permission.permission_code).join(RolePermission,
                    RolePermission.permission_id == Permission.id).where(RolePermission.tenant_id == tenant_id,
                    RolePermission.role_id == role_obj.id, RolePermission.status == "ACTIVE",
                    RolePermission.is_deleted.is_(False))).all())
            if any(not has_permission(user, pattern) for pattern in patterns):
                raise AppException("NO_PERMISSION", f"不能分配超出自身权限边界的角色：{role_obj.role_name}")
        existing = {link.role_id: link for link in db.scalars(select(UserRole).where(
            UserRole.tenant_id == tenant_id, UserRole.user_id == account.id)).all()}
        wanted = {role_obj.id for role_obj in roles}
        for role_id, link in existing.items():
            if role_id in wanted:
                link.status = "ACTIVE"; link.is_deleted = False
            else:
                link.status = "DISABLED"; link.is_deleted = True
            link.version = int(link.version or 0) + 1
        for role_id in wanted - set(existing):
            db.add(UserRole(tenant_id=tenant_id, user_id=account.id, role_id=role_id, status="ACTIVE"))
        account.version = int(account.version or 0) + 1
        db.commit()
        from app.services.auth_service_db import invalidate_subject_cache
        invalidate_subject_cache(f"db-{account.id}", tenant_id)
        from app.services import audit_log
        audit_log.record("USER_ROLE_ASSIGN", f"user:{account.id}", detail={"loginName": account.login_name,
                         "roleCodes": codes})
        return success({"id": str(account.id), "roleCodes": codes}, message="角色已分配；该账号需重新登录")
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


@router.get("/system/roles/{role_id}", summary="学校角色详情（真实库）")
def get_system_role(role_id: int, user=Depends(require_permission("systemAdmin.role.view"))):
    from app.core.permissions import ROLE_PERMISSIONS
    from app.models import Permission, Role, RolePermission, User, UserRole
    from app.services.system_admin_catalog_service import (
        build_permission_tree, expand_permission_patterns, split_selection)
    tenant_id = current_tenant_id()
    db = get_sessionmaker()()
    try:
        role = db.scalars(select(Role).where(Role.id == role_id, Role.tenant_id == tenant_id,
                                             Role.is_deleted.is_(False))).first()
        if role is None:
            from app.core.exceptions import not_found
            raise not_found("角色不存在或不属于当前学校")
        member_count = db.scalar(select(func.count(UserRole.id)).where(
            UserRole.tenant_id == tenant_id, UserRole.role_id == role.id,
            UserRole.status == "ACTIVE", UserRole.is_deleted.is_(False))) or 0
        members = db.execute(select(User.id, User.real_name).join(
            UserRole, UserRole.user_id == User.id).where(
            UserRole.tenant_id == tenant_id, UserRole.role_id == role.id,
            UserRole.status == "ACTIVE", UserRole.is_deleted.is_(False),
            User.is_deleted.is_(False)).limit(50)).all()
        if str(role.role_type or "").upper() == "SYSTEM":
            permission_codes = sorted(expand_permission_patterns(set(ROLE_PERMISSIONS.get(role.role_code, set()))))
        else:
            permission_codes = [row[0] for row in db.execute(select(Permission.permission_code).join(
                RolePermission, RolePermission.permission_id == Permission.id).where(
                RolePermission.tenant_id == tenant_id, RolePermission.role_id == role.id,
                RolePermission.status == "ACTIVE", RolePermission.is_deleted.is_(False)).order_by(
                Permission.permission_code)).all()]
        selection = split_selection(permission_codes, build_permission_tree(user))
        return success({**_role_row(role, member_count), "permissionCodes": permission_codes,
                        "menuKeys": selection["menuKeys"], "buttonKeys": selection["buttonKeys"],
                        "members": [{"id": str(mid), "name": name, "orgName": "—"} for mid, name in members],
                        "auditTrail": []})
    finally:
        db.close()


@router.post("/system/roles", summary="创建学校自定义角色")
def create_system_role(body: dict = Body(...), user=Depends(require_permission("systemAdmin.role.create"))):
    from app.core.exceptions import AppException
    from app.models import Role
    tenant_id = current_tenant_id()
    name = str(body.get("name") or "").strip()
    code = str(body.get("code") or "").strip().upper() or f"CUSTOM_{secrets.token_hex(4).upper()}"
    if not name or not re.fullmatch(r"[A-Z][A-Z0-9_]{2,49}", code):
        raise AppException("VALIDATION_ERROR", "角色名称必填，编码须为 3-50 位大写字母、数字或下划线")
    db = get_sessionmaker()()
    try:
        if db.scalars(select(Role).where(Role.tenant_id == tenant_id, Role.role_code == code)).first():
            raise AppException("DATA_CONFLICT", "角色编码已存在")
        role = Role(tenant_id=tenant_id, role_code=code, role_name=name, role_type="CUSTOM", status="ACTIVE",
                    remark="SAAS_CUSTOM")
        _set_role_scope(role, body.get("scopeCode") or "ASSIGNED")
        db.add(role); db.commit(); db.refresh(role)
        from app.services import audit_log
        audit_log.record("ROLE_CREATE", f"role:{role.id}", detail={"roleCode": code, "roleName": name})
        return success(_role_row(role, 0), message="自定义角色已创建；请继续配置权限")
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


@router.post("/system/roles/{role_id}/copy", summary="从预设或自定义角色复制学校自定义角色")
def copy_system_role(role_id: int, user=Depends(require_permission("systemAdmin.role.create"))):
    from app.core.exceptions import AppException
    from app.core.permissions import ROLE_PERMISSIONS, has_permission
    from app.models import Permission, Role, RolePermission
    from app.services.system_admin_catalog_service import expand_permission_patterns
    tenant_id = current_tenant_id()
    db = get_sessionmaker()()
    try:
        source = db.scalars(select(Role).where(Role.id == role_id, Role.tenant_id == tenant_id,
                                               Role.is_deleted.is_(False))).first()
        if source is None:
            raise AppException("DATA_NOT_FOUND", "源角色不存在")
        if str(source.role_type or "").upper() == "SYSTEM":
            source_codes = expand_permission_patterns(set(ROLE_PERMISSIONS.get(source.role_code, set())))
        else:
            source_codes = set(db.scalars(select(Permission.permission_code).join(
                RolePermission, RolePermission.permission_id == Permission.id).where(
                RolePermission.tenant_id == tenant_id, RolePermission.role_id == source.id,
                RolePermission.status == "ACTIVE", RolePermission.is_deleted.is_(False))).all())
            source_codes = expand_permission_patterns(source_codes)
        # 禁止落库通配或 *
        source_codes = {c for c in source_codes if c and c != "*" and not c.endswith(".*") and not c.startswith("*.")}
        excess = sorted(code for code in source_codes if not has_permission(user, code))
        if excess:
            raise AppException("NO_PERMISSION", "当前操作者不能复制超出自身权限边界的角色", {"codes": excess[:10]})
        base = re.sub(r"[^A-Z0-9_]", "_", f"{source.role_code}_CUSTOM")[:44].rstrip("_") or "CUSTOM"
        existing_codes = set(db.scalars(select(Role.role_code).where(Role.tenant_id == tenant_id)).all())
        code = next((f"{base}_{i}" for i in range(1, 1000) if f"{base}_{i}" not in existing_codes), None)
        if code is None:
            raise AppException("DATA_CONFLICT", "无法生成可用的角色编码")
        role = Role(tenant_id=tenant_id, role_code=code, role_name=f"{source.role_name}（自定义）",
                    role_type="CUSTOM", status="ACTIVE", remark="SAAS_CUSTOM")
        _set_role_scope(role, _role_scope(source))
        db.add(role); db.flush()
        permissions = {p.permission_code: p for p in db.scalars(select(Permission).where(
            Permission.permission_code.in_(source_codes))).all()} if source_codes else {}
        for permission_code in source_codes:
            if permission_code not in permissions:
                module, _, action = permission_code.partition(".")
                p = Permission(permission_code=permission_code, permission_name=permission_code,
                               module_code=module, action=action or None)
                db.add(p); db.flush(); permissions[permission_code] = p
            db.add(RolePermission(tenant_id=tenant_id, role_id=role.id,
                                  permission_id=permissions[permission_code].id, status="ACTIVE"))
        db.commit(); db.refresh(role)
        from app.services import audit_log
        audit_log.record("ROLE_COPY", f"role:{role.id}", detail={"sourceRoleId": str(source.id),
                         "sourceRoleCode": source.role_code, "roleCode": role.role_code,
                         "permissionCount": len(source_codes)})
        return success(_role_row(role, 0), message="已复制为自定义角色；成员未复制")
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


@router.put("/system/roles/{role_id}/permissions", summary="保存自定义角色权限与默认范围")
def save_system_role_permissions(role_id: int, body: dict = Body(...),
                                 user=Depends(require_permission("systemAdmin.role.config"))):
    from app.core.exceptions import AppException
    from app.core.permissions import has_permission
    from app.models import Permission, Role, RolePermission
    from app.services.system_admin_catalog_service import build_permission_tree, expand_permission_patterns, visible_codes_from_tree
    tenant_id = current_tenant_id()
    raw_codes = body.get("permissionCodes") or []
    if not isinstance(raw_codes, list):
        raise AppException("VALIDATION_ERROR", "permissionCodes 必须为数组")
    codes = expand_permission_patterns({str(code).strip() for code in raw_codes if str(code).strip()})
    codes = {c for c in codes if c != "*" and not c.endswith(".*") and not c.startswith("*.") and not c.startswith("platform.")}
    if len(codes) > 500:
        raise AppException("VALIDATION_ERROR", "权限点超出学校角色可配置范围")
    forbidden = [code for code in codes if not has_permission(user, code)]
    if forbidden:
        raise AppException("NO_PERMISSION", "不能向角色授予当前操作者没有的权限", {"codes": forbidden[:10]})
    # 可见码集合：仅替换本页能展示的权限，页外已有权限保留，防止误伤实习/教务等码
    raw_visible = body.get("visiblePermissionCodes")
    if isinstance(raw_visible, list) and raw_visible:
        visible = {str(c).strip() for c in raw_visible if str(c).strip()}
    else:
        visible = visible_codes_from_tree(build_permission_tree(user))
    db = get_sessionmaker()()
    try:
        role = db.scalars(select(Role).where(Role.id == role_id, Role.tenant_id == tenant_id,
                                             Role.is_deleted.is_(False))).first()
        if role is None:
            raise AppException("DATA_NOT_FOUND", "角色不存在")
        if str(role.role_type or "").upper() == "SYSTEM":
            raise AppException("VALIDATION_ERROR", "预设角色由平台模板维护；请复制为自定义角色后再裁剪")
        expected_version = body.get("expectedVersion")
        if expected_version is not None and int(role.version or 0) != int(expected_version):
            raise AppException("DATA_CONFLICT", "角色权限已被他人修改，请刷新后重试")
        existing_links = list(db.scalars(select(RolePermission).where(
            RolePermission.tenant_id == tenant_id, RolePermission.role_id == role.id)).all())
        existing_by_perm_id = {rp.permission_id: rp for rp in existing_links}
        existing_codes = set(db.scalars(select(Permission.permission_code).join(
            RolePermission, RolePermission.permission_id == Permission.id).where(
            RolePermission.tenant_id == tenant_id, RolePermission.role_id == role.id,
            RolePermission.status == "ACTIVE", RolePermission.is_deleted.is_(False))).all())
        # merge：页外保留 + 页内以提交为准
        preserved = {c for c in existing_codes if c not in visible}
        final_codes = sorted(preserved | codes)
        permissions = {p.permission_code: p for p in db.scalars(select(Permission).where(
            Permission.permission_code.in_(final_codes))).all()} if final_codes else {}
        for code in final_codes:
            if code not in permissions:
                module, _, action = code.partition(".")
                p = Permission(permission_code=code, permission_name=code, module_code=module, action=action or None)
                db.add(p); db.flush(); permissions[code] = p
        wanted_ids = {permissions[c].id for c in final_codes}
        for permission_id, link in existing_by_perm_id.items():
            if permission_id in wanted_ids:
                link.status = "ACTIVE"; link.is_deleted = False
            else:
                # 仅当该权限属于本页可见集合时才撤销
                perm_code = next((c for c, p in permissions.items() if p.id == permission_id), None)
                if perm_code is None:
                    # 查库拿 code
                    p_row = db.get(Permission, permission_id)
                    perm_code = p_row.permission_code if p_row else ""
                if perm_code in visible:
                    link.status = "DISABLED"; link.is_deleted = True
        for permission_id in wanted_ids - set(existing_by_perm_id):
            db.add(RolePermission(tenant_id=tenant_id, role_id=role.id, permission_id=permission_id, status="ACTIVE"))
        _set_role_scope(role, body.get("scopeCode") or _role_scope(role),
                        target_json=body.get("scopeTarget") or body.get("targetJson"), user=user)
        role.version = int(role.version or 0) + 1
        db.commit()
        from app.services.auth_service_db import invalidate_tenant_subject_caches
        try:
            invalidate_tenant_subject_caches(tenant_id)
            cache_ok = True
            cache_warn = ""
        except Exception as cache_exc:
            cache_ok = False
            cache_warn = str(cache_exc)[:200]
        from app.services import audit_log
        audit_log.record("ROLE_PERMISSION_SAVE", f"role:{role.id}",
                         detail={"roleCode": role.role_code, "permissionCount": len(final_codes),
                                 "scopeCode": _role_scope(role), "preservedOutsideTree": len(preserved),
                                 "moduleCode": "systemAdmin", "cacheInvalidated": cache_ok,
                                 "cacheWarning": cache_warn, "version": role.version})
        payload = {"id": str(role.id), "permissionCount": len(final_codes), "scopeCode": _role_scope(role),
                   "permissionCodes": final_codes, "version": int(role.version or 0),
                   "cacheInvalidated": cache_ok}
        if not cache_ok:
            payload["warning"] = "权限已保存，但缓存失效失败，请人工刷新或通知成员重新登录"
        return success(payload, message="权限配置已生效；该角色成员需重新登录")
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


@router.put("/system/roles/{role_id}", summary="编辑自定义角色名称（预设角色不可改；权限/范围走权限配置）")
def update_system_role(role_id: int, body: dict = Body(...),
                       user=Depends(require_permission("systemAdmin.role.config"))):
    from app.core.exceptions import AppException
    from app.models import Role
    tenant_id = current_tenant_id()
    name = str((body or {}).get("name") or "").strip()
    if len(name) < 2:
        raise AppException("VALIDATION_ERROR", "角色名称至少 2 个字")
    db = get_sessionmaker()()
    try:
        role = db.scalars(select(Role).where(Role.id == role_id, Role.tenant_id == tenant_id,
                                             Role.is_deleted.is_(False))).first()
        if role is None:
            raise AppException("DATA_NOT_FOUND", "角色不存在")
        if str(role.role_type or "").upper() == "SYSTEM":
            raise AppException("VALIDATION_ERROR", "预设角色由平台模板维护，不可改名")
        before = role.role_name
        role.role_name = name
        role.version = int(role.version or 0) + 1
        db.commit(); db.refresh(role)
        from app.services import audit_log
        audit_log.record("ROLE_UPDATE", f"角色「{name}」",
                         detail={"before": before, "after": name, "summary": "编辑角色名称"})
        member_count = 0
        return success(_role_row(role, member_count), message="角色名称已更新")
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


@router.put("/system/roles/{role_id}/status", summary="停用 / 启用自定义角色")
def set_system_role_status(role_id: int, body: dict = Body(...),
                           user=Depends(require_permission("systemAdmin.role.config"))):
    from app.core.exceptions import AppException
    from app.models import Role, UserRole
    tenant_id = current_tenant_id()
    action = str((body or {}).get("action") or "").strip().upper()
    reason = str((body or {}).get("reason") or "").strip()
    if action not in ("DISABLE", "ENABLE"):
        raise AppException("VALIDATION_ERROR", "action 必须是 DISABLE 或 ENABLE")
    if action == "DISABLE" and len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "停用原因必填且不少于 5 个字")
    db = get_sessionmaker()()
    try:
        role = db.scalars(select(Role).where(Role.id == role_id, Role.tenant_id == tenant_id,
                                             Role.is_deleted.is_(False))).first()
        if role is None:
            raise AppException("DATA_NOT_FOUND", "角色不存在")
        if str(role.role_type or "").upper() == "SYSTEM":
            raise AppException("VALIDATION_ERROR", "预设角色不可停用")
        if action == "DISABLE":
            members = int(db.scalar(select(func.count(UserRole.id)).where(
                UserRole.tenant_id == tenant_id, UserRole.role_id == role.id,
                UserRole.status == "ACTIVE", UserRole.is_deleted.is_(False))) or 0)
            if members > 0:
                raise AppException("DATA_CONFLICT", f"该角色仍有 {members} 名成员，请先改派成员再停用")
        role.status = "DISABLED" if action == "DISABLE" else "ACTIVE"
        role.version = int(role.version or 0) + 1
        db.commit()
        from app.services.auth_service_db import invalidate_tenant_subject_caches
        invalidate_tenant_subject_caches(tenant_id)
        from app.services import audit_log
        audit_log.record("ROLE_DISABLE" if action == "DISABLE" else "ROLE_ENABLE",
                         f"角色「{role.role_name}」",
                         detail={"after": "已停用" if action == "DISABLE" else "启用中", "reason": reason})
        return success({"id": str(role.id), "status": role.status}, message="角色已停用" if action == "DISABLE" else "角色已启用")
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


@router.put("/system/org-nodes/{node_id}/status", summary="停用 / 启用组织节点（学院/专业/班级）")
def set_system_org_node_status(node_id: int, body: dict = Body(...),
                               user=Depends(require_permission("systemAdmin.org.manage"))):
    from app.core.exceptions import AppException
    from app.services.org_master_service import disable_org_node
    node_type = str((body or {}).get("type") or "").strip().upper()
    action = str((body or {}).get("action") or "").strip().upper()
    reason = str((body or {}).get("reason") or "").strip()
    if node_type not in ("COLLEGE", "MAJOR", "CLASS"):
        raise AppException("VALIDATION_ERROR", "type 必须是 COLLEGE / MAJOR / CLASS")
    if action not in ("DISABLE", "ENABLE"):
        raise AppException("VALIDATION_ERROR", "action 必须是 DISABLE 或 ENABLE")
    result = disable_org_node(
        node_type=node_type, node_id=node_id, reason=reason,
        expected_version=(body or {}).get("expectedVersion"), actor=user,
        enable=(action == "ENABLE"),
    )
    return success(result, message="节点已停用" if action == "DISABLE" else "节点已启用")


@router.get("/system/org-duplicate-codes", summary="只读：检测学院/专业/班级编码重复")
def api_org_duplicate_codes(user=Depends(require_any_permission(
        "systemAdmin.org.view", "systemAdmin.implementation.check.run"))):
    from app.services.org_master_service import find_duplicate_org_codes
    return success(find_duplicate_org_codes())


@router.get("/system/identity-import/role-templates", summary="师生导入可选的 SaaS 预设角色")
def identity_role_templates(user=Depends(require_permission("systemAdmin.user.view"))):
    from app.services.saas_role_templates import role_catalog
    return success(role_catalog(teacher_only=True))


@router.get("/system/identity-import/template", summary="下载师生账号导入标准模板（仅 xlsx）")
def identity_import_template(user=Depends(require_permission("systemAdmin.user.import"))):
    from app.services.identity_import_file_service import build_template
    filename = "师生账号导入模板.xlsx"
    return StreamingResponse(
        io.BytesIO(build_template()),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"})


@router.post("/system/identity-import/validate-file", summary="上传师生账号 xlsx 并预检")
async def identity_import_validate_file(
        file: UploadFile = File(...),
        user=Depends(require_permission("systemAdmin.user.import"))):
    from app.services.identity_import_file_service import MAX_FILE_BYTES, create_batch, parse_xlsx
    from app.services.identity_import_service import preview_identity_import
    chunks, size = [], 0
    while chunk := await file.read(1024 * 1024):
        size += len(chunk)
        if size > MAX_FILE_BYTES:
            from app.core.exceptions import AppException
            raise AppException("FILE_TOO_LARGE", "导入文件超过 20MB 上限，请拆分后重试")
        chunks.append(chunk)
    parsed = parse_xlsx(b"".join(chunks), file.filename or "")
    payload = {"students": parsed["students"], "teachers": parsed["teachers"], "atomic": True}
    report = preview_identity_import(user, payload, pre_errors=parsed["errors"])
    return success(create_batch(user, parsed, report), message="Excel 解析及预检完成")


@router.post("/system/identity-import/confirm-batch", summary="确认预检批次并整批创建师生账号")
def identity_import_confirm_batch(
        body: dict = Body(...),
        user=Depends(require_permission("systemAdmin.user.import"))):
    from app.services import audit_log
    from app.services.identity_import_file_service import (build_credential_receipt, claim_batch,
                                                            mark_confirmed, release_claim)
    from app.services.identity_import_service import run_identity_import
    batch_no = str(body.get("batchNo") or "").strip()
    tenant_id = current_tenant_id()
    entry, claim_token, already_confirmed = claim_batch(user, tenant_id, batch_no)
    if already_confirmed:
        return success({**entry.get("publicResult", {}), "batchNo": batch_no,
                        "alreadyConfirmed": True, "credentialReceipt": None},
                       message="该批次已完成确认；初始密码回执不会重复显示")
    try:
        report = run_identity_import(user, entry["payload"], dry_run=False)
        credential_receipt = build_credential_receipt(entry, report)
        public_report = {key: value for key, value in report.items()
                         if key not in ("studentCredentials", "teacherCredentials")}
        mark_confirmed(user, tenant_id, batch_no, claim_token, public_report)
    except Exception as exc:
        release_claim(user, tenant_id, batch_no, claim_token, str(exc))
        raise
    public_report["credentialReceipt"] = credential_receipt
    audit_log.record("IDENTITY_IMPORT", f"batch:{batch_no}", detail={
        "fileName": entry["fileName"], "fileSha256": entry["fileSha256"],
        "tenantId": entry["tenantId"], "entities": report.get("entities")})
    return success({**public_report, "batchNo": batch_no}, message="师生账号已整批创建")


# ── 学生 / 教师拆分入口（身份与账号）────────────────────────────────────────
# 混合模板靠「账号类型」列区分，学校填表极易串列，且两类导入的权限、结果统计、
# 后续流程完全不同，故拆成两个独立入口：各自的模板、字段规则、接口语义与结果统计；
# 共用批次租约、整批事务、错误回执、初始密码回执与审计（不复制第二套批次系统）。

def _identity_import_upload(file: UploadFile, parser):
    """两个专用入口共用的上传读取与大小限制。"""
    from app.services.identity_import_file_service import MAX_FILE_BYTES
    chunks, size = [], 0
    while True:
        chunk = file.file.read(1024 * 1024)
        if not chunk:
            break
        size += len(chunk)
        if size > MAX_FILE_BYTES:
            from app.core.exceptions import AppException
            raise AppException("FILE_TOO_LARGE", "导入文件超过 20MB 上限，请拆分后重试")
        chunks.append(chunk)
    return parser(b"".join(chunks), file.filename or "")


@router.get("/system/identity-import/students/template", summary="下载学生导入模板（仅 xlsx）")
def student_import_template(user=Depends(require_permission("systemAdmin.user.import"))):
    from app.services.identity_import_file_service import build_student_template
    filename = "学生导入模板.xlsx"
    return StreamingResponse(
        io.BytesIO(build_student_template()),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"})


@router.post("/system/identity-import/students/validate-file", summary="上传学生 xlsx 并预检")
async def student_import_validate_file(
        file: UploadFile = File(...),
        user=Depends(require_permission("systemAdmin.user.import"))):
    from app.core.import_export_auth import enforce_student_import
    from app.services.identity_import_file_service import create_batch, parse_student_xlsx
    from app.services.identity_import_service import preview_identity_import
    # 学生导入的租户特性闸门（原挂在已删除的 /import/students/*，随入口收敛迁到这里，
    # 否则学校「是否购买学生导入」将失去唯一执行点）
    enforce_student_import(user)
    parsed = _identity_import_upload(file, parse_student_xlsx)
    payload = {"students": parsed["students"], "teachers": [], "atomic": True}
    report = preview_identity_import(user, payload, pre_errors=parsed["errors"])
    return success(create_batch(user, parsed, report), message="学生名单解析及预检完成")


@router.post("/system/identity-import/students/confirm-batch", summary="确认批次并整批开通学生")
def student_import_confirm_batch(
        body: dict = Body(...),
        user=Depends(require_permission("systemAdmin.user.import"))):
    from app.core.import_export_auth import enforce_student_import
    enforce_student_import(user)
    return identity_import_confirm_batch(body=body, user=user)


@router.get("/system/identity-import/teachers/template", summary="下载教师导入模板（仅 xlsx）")
def teacher_import_template(user=Depends(require_permission("systemAdmin.user.import"))):
    from app.services.identity_import_file_service import build_teacher_template
    filename = "教师导入模板.xlsx"
    return StreamingResponse(
        io.BytesIO(build_teacher_template()),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"})


@router.post("/system/identity-import/teachers/validate-file", summary="上传教师 xlsx 并预检")
async def teacher_import_validate_file(
        file: UploadFile = File(...),
        user=Depends(require_permission("systemAdmin.user.import"))):
    from app.services.identity_import_file_service import create_batch, parse_teacher_xlsx
    from app.services.identity_import_service import preview_identity_import
    parsed = _identity_import_upload(file, parse_teacher_xlsx)
    payload = {"students": [], "teachers": parsed["teachers"], "atomic": True}
    report = preview_identity_import(user, payload, pre_errors=parsed["errors"])
    return success(create_batch(user, parsed, report), message="教师名单解析及预检完成")


@router.post("/system/identity-import/teachers/confirm-batch", summary="确认批次并整批开通教师")
def teacher_import_confirm_batch(
        body: dict = Body(...),
        user=Depends(require_permission("systemAdmin.user.import"))):
    return identity_import_confirm_batch(body=body, user=user)


@router.get("/system/identity-import/batches/{batch_no}/errors", summary="下载师生导入错误回执")
def identity_import_errors(
        batch_no: str,
        user=Depends(require_permission("systemAdmin.user.import"))):
    from app.services.identity_import_file_service import build_error_workbook, get_batch
    entry = get_batch(user, current_tenant_id(), batch_no)
    filename = f"师生账号导入错误_{batch_no}.xlsx"
    return StreamingResponse(
        io.BytesIO(build_error_workbook(entry)),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"})


def _acting_db_id(user: dict) -> int | None:
    uid = str((user or {}).get("userId") or "")
    return int(uid[3:]) if uid.startswith("db-") and uid[3:].isdigit() else None


@router.put("/system/users/{user_id}/status", summary="停用 / 启用学校账号（逻辑操作，可恢复）")
def set_system_user_status(user_id: int, body: dict = Body(...),
                           user=Depends(require_permission("systemAdmin.user.manage"))):
    from app.core.exceptions import AppException
    from app.models import User
    action = str((body or {}).get("action") or "").strip().upper()
    reason = str((body or {}).get("reason") or "").strip()
    if action not in ("DISABLE", "ENABLE"):
        raise AppException("VALIDATION_ERROR", "action 必须是 DISABLE 或 ENABLE")
    if action == "DISABLE" and len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "停用原因必填且不少于 5 个字")
    if action == "DISABLE" and _acting_db_id(user) == user_id:
        raise AppException("VALIDATION_ERROR", "不能停用当前登录的本人账号")
    tenant_id = current_tenant_id()
    db = get_sessionmaker()()
    try:
        account = db.scalars(select(User).where(User.id == user_id, User.tenant_id == tenant_id,
                                                User.is_deleted.is_(False))).first()
        if account is None:
            raise AppException("DATA_NOT_FOUND", "账号不存在")
        if action == "DISABLE" and _is_last_active_school_admin(db, tenant_id, account.id):
            raise AppException("VALIDATION_ERROR", "不能停用本校最后一名启用中的学校管理员")
        _check_account_version(account, (body or {}).get("expectedVersion"))
        before = str(account.status or "").upper()
        account.status = "DISABLED" if action == "DISABLE" else "ACTIVE"
        account.version = int(account.version or 0) + 1
        db.commit()
        from app.services.auth_service_db import invalidate_subject_cache
        invalidate_subject_cache(f"db-{account.id}", tenant_id)
        from app.services import audit_log
        audit_log.record("USER_DISABLE" if action == "DISABLE" else "USER_ENABLE",
                         f"账号 {account.login_name}（{account.real_name}）",
                         detail={"before": {"DISABLED": "已停用", "ACTIVE": "启用中", "LOCKED": "已锁定"}.get(before, before),
                                 "after": "已停用" if action == "DISABLE" else "启用中",
                                 "reason": reason, "summary": "停用账号（逻辑删除，可恢复，历史留痕保留）"
                                 if action == "DISABLE" else "启用账号"},
                         result="SUCCESS")
        return success({"id": str(account.id), "status": account.status,
                        "statusLabel": "已停用" if action == "DISABLE" else "启用中"},
                       message="账号已停用，原因已留痕" if action == "DISABLE" else "账号已启用，已留痕")
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


@router.post("/system/users/{user_id}/reset-password", summary="重置学校账号密码（生成临时密码，强制首登改密）")
def reset_system_user_password(user_id: int, body: dict | None = Body(default=None),
                               user=Depends(require_permission("systemAdmin.user.manage"))):
    from app.core.exceptions import AppException
    from app.core.security import hash_password
    from app.models import User
    tenant_id = current_tenant_id()
    db = get_sessionmaker()()
    try:
        account = db.scalars(select(User).where(User.id == user_id, User.tenant_id == tenant_id,
                                                User.is_deleted.is_(False))).first()
        if account is None:
            raise AppException("DATA_NOT_FOUND", "账号不存在")
        # 本函数也被内部直接调用（此时 body 还是 Body() 标记对象，不是 dict），故显式判类型
        _check_account_version(account, (body if isinstance(body, dict) else {}).get("expectedVersion"))
        temp_password = "Tmp" + secrets.token_urlsafe(6)  # 一次性临时密码，仅本次返回给管理员转交
        account.password_hash = hash_password(temp_password)
        account.must_change_password = True
        account.version = int(account.version or 0) + 1
        db.commit()
        from app.services.auth_service_db import invalidate_subject_cache
        invalidate_subject_cache(f"db-{account.id}", tenant_id)
        from app.services import audit_log
        audit_log.record("RESET_PASSWORD", f"账号 {account.login_name}（{account.real_name}）",
                         detail={"summary": "重置密码：已生成一次性临时密码，强制首登改密", "reason": "管理员重置"},
                         result="SUCCESS")
        # 临时密码仅本次随响应返回给操作管理员转交，不入库明文、不重复展示。
        return success({"id": str(account.id), "tempPassword": temp_password, "mustChangePassword": True,
                        "notice": "临时密码仅本次显示，请立即转交本人；该账号首次登录须强制改密"},
                       message="密码已重置")
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


# ═══════════ 登录 / 操作审计日志（真实库：t_security_audit_log，append-only） ═══════════
# 登录/安全类动作归「登录日志」，其余归「操作日志」。二者同源一张审计表，只按 action 分流。
# 注意：真实登录流记的是中文动作「登录」（auth.py），authz.py 的英文 "LOGIN" 为兼容入口未使用；
# 二者及门户监护人登录、令牌刷新、限流等安全事件都归登录/安全审计，PERMISSION_DENIED 归操作/权限审计。
_LOGIN_ACTIONS = ("登录", "登出", "LOGIN", "LOGOUT", "LOGIN_FAIL", "LOGIN_LOCKED",
                  "TOKEN_REFRESH", "RATE_LIMITED", "PORTAL_GUARDIAN_LOGIN", "PORTAL_GUARDIAN_OTP")
_RESULT_TO_BUCKET = {"SUCCESS": ("SUCCESS", "成功"), "FAIL": ("FAILED", "失败"),
                     "FAILED": ("FAILED", "失败"), "DENIED": ("DENIED", "越权拦截"),
                     "BLOCKED": ("BLOCKED", "已拦截")}
_ACTION_LABELS = {
    "LOGIN": "登录", "LOGIN_FAIL": "登录失败", "LOGIN_LOCKED": "账号锁定", "LOGOUT": "登出",
    "EXPORT": "导出", "IMPORT": "导入", "IDENTITY_IMPORT": "师生导入", "GRANT": "授权变更",
    "CONFIG": "配置变更", "CONFIG_CHANGE": "配置变更", "BRAND_CONFIG": "品牌配置",
    "DISABLE": "停用/作废", "ENABLE": "启用", "USER_DISABLE": "停用/作废", "USER_ENABLE": "启用",
    "USER_ROLE_ASSIGN": "分配角色", "RESET_PASSWORD": "重置密码", "PERMISSION_DENIED": "越权拦截",
    "MODULE_DENIED": "模块越权", "SENSITIVE_VIEW": "敏感查看", "FILE_UPLOAD": "文件上传",
    "ROLE_CREATE": "新建角色", "ROLE_UPDATE": "编辑角色", "ROLE_PERMISSION_SAVE": "保存角色权限",
    "ORG_NODE_SAVE": "组织维护",
}


def _mask_ip(ip: str | None) -> str:
    s = (ip or "").strip()
    if not s:
        return ""
    parts = s.split(".")
    if len(parts) == 4:  # IPv4 脱敏后两段
        return f"{parts[0]}.{parts[1]}.*.*"
    return s[:6] + "…" if len(s) > 8 else s


def _resolve_login_names(db, operator_ids: set[int]) -> dict[int, str]:
    from app.models import User
    ids = {i for i in operator_ids if i}
    if not ids:
        return {}
    rows = db.execute(select(User.id, User.login_name).where(User.id.in_(ids))).all()
    return {row[0]: row[1] for row in rows}


def _audit_page(login_only: bool, keyword: str, result: str, action: str, module: str,
                page: int, page_size: int, date_from: str = "", date_to: str = "",
                sensitive_only: bool = False) -> dict:
    from app.models import SecurityAuditLog
    tenant_id = current_tenant_id()
    page = max(1, int(page or 1))
    page_size = min(200, max(1, int(page_size or 20)))
    db = get_sessionmaker()()
    try:
        stmt = select(SecurityAuditLog).where(SecurityAuditLog.tenant_id == tenant_id)
        if login_only:
            stmt = stmt.where(SecurityAuditLog.action.in_(_LOGIN_ACTIONS))
        else:
            stmt = stmt.where(SecurityAuditLog.action.notin_(_LOGIN_ACTIONS))
        if sensitive_only:
            stmt = stmt.where(SecurityAuditLog.action.in_(
                ("SENSITIVE_VIEW", "SENSITIVE_EXPORT", "EXPORT", "IMPORT", "IDENTITY_IMPORT")))
        if keyword.strip():
            like = f"%{keyword.strip()}%"
            stmt = stmt.where(SecurityAuditLog.operator_name.like(like) | SecurityAuditLog.resource.like(like))
        if result.strip():
            want = result.strip().upper()
            equivalents = {"FAILED": ("FAIL", "FAILED"), "FAIL": ("FAIL", "FAILED")}.get(want, (want,))
            stmt = stmt.where(SecurityAuditLog.result.in_(equivalents))
        if action.strip():
            stmt = stmt.where(SecurityAuditLog.action == action.strip().upper())
        if date_from.strip():
            stmt = stmt.where(SecurityAuditLog.created_at >= date_from.strip()[:10] + " 00:00:00")
        if date_to.strip():
            stmt = stmt.where(SecurityAuditLog.created_at <= date_to.strip()[:10] + " 23:59:59")
        # module 筛选：优先 detail.moduleCode，再按 action/path 归类后过滤
        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = db.scalars(stmt.order_by(SecurityAuditLog.id.desc())
                          .offset(0).limit(min(2000, max(page_size * page, page_size)))).all()
        if module.strip():
            want = module.strip()
            rows = [r for r in rows if _audit_module_of(r)[0] == want
                    or _audit_module_of(r)[0].lower() == want.lower()
                    or want.upper() in (_audit_module_of(r)[0].upper(), "SYSTEM" if _audit_module_of(r)[0] == "systemAdmin" else "")]
            total = len(rows)
            start = (page - 1) * page_size
            rows = rows[start:start + page_size]
        else:
            start = (page - 1) * page_size
            # 重新按分页取（无 module 时走 SQL 分页）
            rows = db.scalars(stmt.order_by(SecurityAuditLog.id.desc())
                              .offset(start).limit(page_size)).all()
        name_map = _resolve_login_names(db, {r.operator_id for r in rows})
        items = [_login_log_row(r, name_map) if login_only else _operation_log_row(r) for r in rows]
        return {"list": items, "total": int(total), "page": page, "pageSize": page_size}
    finally:
        db.close()


def _login_log_row(r, name_map: dict) -> dict:
    detail = r.detail_json if isinstance(r.detail_json, dict) else {}
    if r.action in ("LOGIN_LOCKED", "RATE_LIMITED"):
        bucket, label = "BLOCKED", "已拦截"
    elif r.action == "LOGIN_FAIL":
        bucket, label = "FAILED", "失败"
    else:
        bucket, label = _RESULT_TO_BUCKET.get(str(r.result or "SUCCESS").upper(), ("SUCCESS", "成功"))
    return {
        "id": str(r.id), "userName": r.operator_name or "—",
        "userNo": name_map.get(r.operator_id, "") or (str(r.operator_id) if r.operator_id else ""),
        "roleName": r.current_role or "—", "time": str(r.created_at or "")[:16],
        "result": bucket, "resultLabel": label,
        "reason": detail.get("reason") or detail.get("summary") or ("" if bucket == "SUCCESS" else _ACTION_LABELS.get(r.action, "")),
        "ip": _mask_ip(r.ip), "location": detail.get("location", "") or "",
        "device": r.user_agent or "",
    }


_MODULE_BY_ACTION = {
    "LOGIN": "systemAdmin", "LOGOUT": "systemAdmin", "LOGIN_FAIL": "systemAdmin",
    "PERMISSION_DENIED": "systemAdmin", "MODULE_DENIED": "systemAdmin",
    "USER_UPDATE": "systemAdmin", "USER_ROLE_ASSIGN": "systemAdmin", "RESET_PASSWORD": "systemAdmin",
    "ROLE_CREATE": "systemAdmin", "ROLE_UPDATE": "systemAdmin", "ROLE_PERMISSION_SAVE": "systemAdmin",
    "ORG_NODE_SAVE": "systemAdmin", "ORG_NODE_DISABLE": "systemAdmin",
    "DATA_SCOPE_SAVE": "systemAdmin", "DELEGATION_CREATE": "systemAdmin", "DELEGATION_REVOKE": "systemAdmin",
    "INTEGRATION_SAVE": "systemAdmin", "INTEGRATION_ROTATE": "systemAdmin", "INTEGRATION_TEST": "systemAdmin",
    "SYNC_JOB_ENQUEUE": "systemAdmin", "SYNC_JOB_RETRY": "systemAdmin", "SYNC_JOB_CANCEL": "systemAdmin",
    "MODULE_FEATURE_SAVE": "systemAdmin", "SENSITIVE_VIEW": "systemAdmin",
    "EXPORT": "systemAdmin", "IMPORT": "systemAdmin", "IDENTITY_IMPORT": "systemAdmin",
    "BRAND_CONFIG": "systemAdmin", "CONFIG_CHANGE": "systemAdmin",
    "GO_LIVE_CHECK": "systemAdmin",
}

_MODULE_LABELS = {
    "systemAdmin": "系统管理", "studentAffairs": "学工中心", "academicAffairs": "教务中心",
    "graduationDesign": "毕业设计", "internship": "岗位实习", "employment": "就业",
    "orientation": "数字迎新", "campusService": "在校服务", "workbench": "工作台",
    "platform": "平台运营",
}


def _audit_module_of(r) -> tuple[str, str]:
    detail = r.detail_json if isinstance(r.detail_json, dict) else {}
    code = str(detail.get("moduleCode") or detail.get("module") or "").strip()
    if not code:
        code = _MODULE_BY_ACTION.get(str(r.action or "").upper(), "")
    if not code:
        # 从 resource / path 启发式
        path = str(r.request_path or "")
        resource = str(r.resource or "")
        for key, label_key in (
            ("student-affairs", "studentAffairs"), ("academic-affairs", "academicAffairs"),
            ("graduation", "graduationDesign"), ("internship", "internship"),
            ("employment", "employment"), ("orientation", "orientation"),
            ("campus-service", "campusService"), ("system", "systemAdmin"),
            ("platform", "platform"),
        ):
            if key in path or key in resource:
                code = label_key
                break
    if not code:
        code = "systemAdmin"
    return code, _MODULE_LABELS.get(code, code)


def _operation_log_row(r) -> dict:
    detail = r.detail_json if isinstance(r.detail_json, dict) else {}
    bucket, label = _RESULT_TO_BUCKET.get(str(r.result or "SUCCESS").upper(), ("SUCCESS", "成功"))
    module_code, module_label = _audit_module_of(r)
    return {
        "id": str(r.id), "time": str(r.created_at or "")[:16], "who": r.operator_name or "—",
        "roleName": r.current_role or "—", "module": module_code, "moduleLabel": module_label,
        "action": r.action, "actionLabel": _ACTION_LABELS.get(r.action, r.action),
        "target": r.resource or "", "result": bucket, "resultLabel": label, "ip": _mask_ip(r.ip),
        "detail": {"summary": detail.get("summary", ""), "before": detail.get("before", ""),
                   "after": detail.get("after", ""), "reason": detail.get("reason", ""),
                   "path": r.request_path or "", "method": r.request_method or "",
                   "traceId": r.trace_id or "", "dataScope": r.data_scope or detail.get("dataScope", "")},
    }


@router.get("/system/login-logs", summary="登录与安全审计（真实库 t_security_audit_log）")
def list_login_logs(keyword: str = "", result: str = "", page: int = 1, page_size: int = 20,
                    date_from: str = "", date_to: str = "",
                    user=Depends(require_permission("systemAdmin.audit.view"))):
    return success(_audit_page(True, keyword, result, "", "", page, page_size, date_from, date_to))


@router.get("/system/operation-logs", summary="操作与权限审计（真实库 t_security_audit_log）")
def list_operation_logs(keyword: str = "", result: str = "", action: str = "", module: str = "",
                        page: int = 1, page_size: int = 20, date_from: str = "", date_to: str = "",
                        user=Depends(require_permission("systemAdmin.audit.view"))):
    return success(_audit_page(False, keyword, result, action, module, page, page_size, date_from, date_to))


@router.get("/system/sensitive-logs", summary="敏感与导入导出审计")
def list_sensitive_logs(keyword: str = "", result: str = "", page: int = 1, page_size: int = 20,
                        date_from: str = "", date_to: str = "",
                        user=Depends(require_any_permission(
                            "systemAdmin.audit.sensitive.view", "systemAdmin.audit.view"))):
    return success(_audit_page(False, keyword, result, "", "", page, page_size, date_from, date_to,
                               sensitive_only=True))


# ═══════════ 导出（真实 xlsx：查真库 → build_ledger_xlsx → 流式下载 + 导出留痕审计） ═══════════
def _xlsx_response(title: str, headers: list, rows: list, filename: str, user: dict, audit_target: str):
    from app.services import xlsx_util
    op_name = (user or {}).get("realName") or "系统"
    wm = f"系统管理·{title} · 导出人：{op_name} · {datetime.now():%Y-%m-%d %H:%M} · 导出留痕"
    content = xlsx_util.build_ledger_xlsx(title, headers, rows, watermark=wm)
    from app.services import audit_log
    audit_log.record("EXPORT", audit_target, detail={"rowCount": len(rows), "summary": f"导出 {len(rows)} 行（含水印）"})
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"})


@router.get("/system/export/users", summary="导出账号台账（真实 xlsx）")
def export_system_users(keyword: str = "", role: str = "", status: str = "", account_type: str = "",
                        user=Depends(require_any_permission("systemAdmin.user.export", "systemAdmin.user.view"))):
    from app.models import Role, User, UserRole
    tenant_id = current_tenant_id()
    normalized_type = _normalize_account_type(account_type)
    db = get_sessionmaker()()
    try:
        stmt = select(User).where(User.tenant_id == tenant_id, User.is_deleted.is_(False))
        if normalized_type:
            stmt = stmt.where(_account_type_condition(User, normalized_type, tenant_id))
        if keyword.strip():
            like = f"%{keyword.strip()}%"
            stmt = stmt.where(User.login_name.like(like) | User.real_name.like(like))
        if status.strip():
            stmt = stmt.where(User.status == status.upper())
        users = db.scalars(stmt.order_by(User.created_at.desc())).all()
        uids = [u.id for u in users]
        by_user: dict[int, list] = {uid: [] for uid in uids}
        if uids:
            for uid, r in db.execute(select(UserRole.user_id, Role).join(Role, Role.id == UserRole.role_id).where(
                UserRole.tenant_id == tenant_id, UserRole.user_id.in_(uids), UserRole.status == "ACTIVE",
                UserRole.is_deleted.is_(False), Role.is_deleted.is_(False))).all():
                by_user[uid].append(r)
        if role.strip():
            want = role.strip().upper()
            users = [u for u in users if any(rr.role_code == want for rr in by_user.get(u.id, []))]
        status_label = {"ACTIVE": "启用中", "DISABLED": "已停用", "LOCKED": "已锁定"}
        if normalized_type == "STUDENT":
            headers = ["学号", "姓名", "学院", "专业", "年级", "班级", "学籍状态",
                       "账号状态", "最后登录", "创建时间"]
            rows = []
            for account in users:
                meta = _student_account_meta(db, account)
                rows.append([
                    meta["studentNo"] or account.login_name, account.real_name,
                    meta["collegeName"] or "—", meta["majorName"] or "—",
                    meta["grade"] or "—", meta["className"] or "—",
                    meta["studentStatusLabel"],
                    status_label.get(str(account.status or "").upper(), account.status or ""),
                    str(account.last_login_at or "")[:19] or "—",
                    str(account.created_at or "")[:10],
                ])
            title = "学生账号台账"
        elif normalized_type == "STAFF":
            headers = ["工号", "姓名", "业务归属", "角色", "账号状态", "最后登录", "创建时间"]
            rows = [[
                account.login_name, account.real_name, _user_org_hint(db, account)[1],
                "、".join(r.role_name for r in by_user.get(account.id, [])) or "—",
                status_label.get(str(account.status or "").upper(), account.status or ""),
                str(account.last_login_at or "")[:19] or "—",
                str(account.created_at or "")[:10],
            ] for account in users]
            title = "教职工账号台账"
        else:
            headers = ["工号/学号", "姓名", "角色", "状态", "最后登录", "创建时间"]
            rows = [[
                account.login_name, account.real_name,
                "、".join(r.role_name for r in by_user.get(account.id, [])) or "—",
                status_label.get(str(account.status or "").upper(), account.status or ""),
                str(account.last_login_at or "")[:19] or "—",
                str(account.created_at or "")[:10],
            ] for account in users]
            title = "账号台账"
        return _xlsx_response(title, headers, rows, f"{title}_{datetime.now():%Y%m%d}.xlsx", user, title)
    finally:
        db.close()


@router.get("/system/export/logs", summary="导出登录/操作审计（真实 xlsx）")
def export_system_logs(tab: str = "operation", keyword: str = "", result: str = "",
                       user=Depends(require_permission("systemAdmin.audit.view"))):
    login_only = tab == "login"
    data = _audit_page(login_only, keyword, result, "", "", 1, 100000)
    if login_only:
        headers = ["时间", "用户", "工号", "角色", "结果", "原因", "IP", "设备"]
        rows = [[r["time"], r["userName"], r["userNo"], r["roleName"], r["resultLabel"],
                 r["reason"], r["ip"], r["device"]] for r in data["list"]]
        title, fn, target = "登录审计", f"登录审计_{datetime.now():%Y%m%d}.xlsx", "登录审计"
    else:
        headers = ["时间", "操作人", "角色", "动作", "对象", "结果", "IP", "摘要"]
        rows = [[r["time"], r["who"], r["roleName"], r["actionLabel"], r["target"], r["resultLabel"],
                 r["ip"], r["detail"].get("summary", "")] for r in data["list"]]
        title, fn, target = "操作审计", f"操作审计_{datetime.now():%Y%m%d}.xlsx", "操作审计"
    return _xlsx_response(title, headers, rows, fn, user, target)


@router.get("/system/export/org", summary="导出组织结构（真实 xlsx）")
def export_system_org(user=Depends(require_permission("systemAdmin.org.view"))):
    from app.models import College, Major, SchoolClass, StudentProfile
    tenant_id = current_tenant_id()
    db = get_sessionmaker()()
    try:
        colleges = {c.id: c for c in db.scalars(select(College).where(College.tenant_id == tenant_id,
                    College.is_deleted.is_(False))).all()}
        majors = {m.id: m for m in db.scalars(select(Major).where(Major.tenant_id == tenant_id,
                  Major.is_deleted.is_(False))).all()}
        classes = db.scalars(select(SchoolClass).where(SchoolClass.tenant_id == tenant_id,
                  SchoolClass.is_deleted.is_(False))).all()
        counts = dict(db.execute(select(StudentProfile.class_id, func.count(StudentProfile.id)).where(
            StudentProfile.tenant_id == tenant_id, StudentProfile.is_deleted.is_(False)).group_by(
            StudentProfile.class_id)).all())
        headers = ["学院", "专业", "班级", "在籍人数", "状态"]
        st = {"ACTIVE": "启用中", "DISABLED": "已停用"}
        rows = []
        for c in classes:
            major = majors.get(c.major_id)
            college = colleges.get(major.college_id) if major else None
            rows.append([college.college_name if college else "—", major.major_name if major else "—",
                         c.class_name, int(counts.get(c.id, 0)), st.get(str(c.status or "").upper(), c.status or "")])
        return _xlsx_response("组织结构", headers, rows, f"组织结构_{datetime.now():%Y%m%d}.xlsx", user, "组织结构")
    finally:
        db.close()


def _json_response(payload: dict, filename: str, user: dict, audit_target: str):
    import json
    from app.services import audit_log
    content = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    audit_log.record("EXPORT", audit_target, detail={"summary": "导出配置快照（JSON，不含密钥/敏感明文）"})
    return StreamingResponse(
        io.BytesIO(content), media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"})


@router.get("/system/export/scope-rules", summary="导出数据范围规则清单（真实 xlsx）")
def export_scope_rules(user=Depends(require_permission("systemAdmin.scope.view"))):
    from app.models import DataScopeRule
    tenant_id = current_tenant_id()
    db = get_sessionmaker()()
    try:
        rules = db.scalars(select(DataScopeRule).where(DataScopeRule.tenant_id == tenant_id,
                DataScopeRule.is_deleted.is_(False)).order_by(DataScopeRule.id.desc())).all()
        headers = ["规则名称", "范围类型", "引用角色", "影响用户数", "状态", "备注"]
        rows = []
        for r in rules:
            row = _scope_rule_row(db, r)
            rows.append([row["name"], row["scopeLabel"], "、".join(row["appliedRoles"]) or "未引用",
                         row["affectedUsers"], row["statusLabel"], row["remark"]])
        return _xlsx_response("数据范围规则", headers, rows, f"数据范围规则_{datetime.now():%Y%m%d}.xlsx",
                              user, "数据范围规则")
    finally:
        db.close()


@router.get("/system/export/role-config/{role_id}", summary="导出角色权限配置（真实 JSON，不含成员）")
def export_role_config(role_id: int, user=Depends(require_permission("systemAdmin.role.view"))):
    from app.core.exceptions import AppException
    from app.models import Permission, Role, RolePermission
    from app.core.permissions import ROLE_PERMISSIONS
    tenant_id = current_tenant_id()
    db = get_sessionmaker()()
    try:
        role = db.scalars(select(Role).where(Role.id == role_id, Role.tenant_id == tenant_id,
                                             Role.is_deleted.is_(False))).first()
        if role is None:
            raise AppException("DATA_NOT_FOUND", "角色不存在")
        if str(role.role_type or "").upper() == "SYSTEM":
            codes = sorted(ROLE_PERMISSIONS.get(role.role_code, set()))
        else:
            codes = sorted(db.scalars(select(Permission.permission_code).join(RolePermission,
                RolePermission.permission_id == Permission.id).where(
                RolePermission.tenant_id == tenant_id, RolePermission.role_id == role.id,
                RolePermission.status == "ACTIVE", RolePermission.is_deleted.is_(False))).all())
        payload = {"roleName": role.role_name, "roleCode": role.role_code,
                   "roleType": "BUILTIN" if str(role.role_type or "").upper() == "SYSTEM" else "CUSTOM",
                   "scopeCode": _role_scope(role), "permissionCount": len(codes),
                   "permissions": codes, "exportedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        return _json_response(payload, f"角色配置_{role.role_code}.json", user, f"角色配置「{role.role_name}」")
    finally:
        db.close()


@router.get("/system/export/configs", summary="导出系统与品牌配置快照（真实 JSON，不含密钥）")
def export_configs(user=Depends(require_permission("systemAdmin.config.view"))):
    from app.services import system_config_service
    tenant_id = int(current_tenant_id() or 0)
    db = get_sessionmaker()()
    try:
        brand = _brand_form(db, tenant_id)
    finally:
        db.close()
    payload = {"systemConfigs": system_config_service.list_configs(),
               "brand": {k: v for k, v in brand.items() if k != "schoolName"},
               "exportedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    return _json_response(payload, f"系统配置快照_{datetime.now():%Y%m%d}.json", user, "系统与品牌配置")


# ═══════════ 数据范围规则（真实可编辑目录，t_data_scope_rule；角色经 scopeCode 引用生效） ═══════════
_SCOPE_LABELS = {"SELF": "本人", "CLASS": "本班", "COUNSELOR_CLASSES": "本人所带班级",
                 "GD_STUDENTS": "本人指导毕设学生", "INTERN_STUDENTS": "本人指导实习学生",
                 "MAJOR": "本专业", "COLLEGE": "本学院", "SCHOOL": "全校",
                 "DEPARTMENT": "本部门", "TEMP_AUTH": "临时授权", "CUSTOM": "自定义范围", "ASSIGNED": "按角色指派"}


def _scope_rule_row(db, rule) -> dict:
    from app.models import Role, User, UserRole
    tenant_id = rule.tenant_id
    code = str(rule.scope_type or "").upper()
    # 引用本范围码的角色（角色 remark 里 ;scope=<code>）→ 真实 appliedRoles / affectedUsers
    roles = db.scalars(select(Role).where(Role.tenant_id == tenant_id, Role.is_deleted.is_(False),
                                          Role.remark.like(f"%;scope={code}%"))).all()
    role_ids = [r.id for r in roles]
    affected = 0
    if role_ids:
        affected = int(db.scalar(select(func.count(func.distinct(UserRole.user_id))).where(
            UserRole.tenant_id == tenant_id, UserRole.role_id.in_(role_ids),
            UserRole.status == "ACTIVE", UserRole.is_deleted.is_(False))) or 0)
    status = str(rule.status or "").upper()
    return {
        "id": str(rule.id), "name": rule.rule_name, "scopeCode": code,
        "scopeLabel": _SCOPE_LABELS.get(code, code or "自定义"),
        "appliedRoles": [r.role_name for r in roles], "affectedUsers": affected,
        "remark": rule.remark or "",
        "status": "ENABLED" if status in ("ACTIVE", "ENABLED") else "DEPRECATED",
        "statusLabel": "启用中" if status in ("ACTIVE", "ENABLED") else "已作废",
        "updatedAt": str(getattr(rule, "updated_at", "") or "")[:19],
    }


@router.get("/system/scope-rules", summary="数据范围规则目录（真实库）")
def list_scope_rules(keyword: str = "", status: str = "",
                     user=Depends(require_permission("systemAdmin.scope.view"))):
    from app.models import DataScopeRule
    tenant_id = current_tenant_id()
    db = get_sessionmaker()()
    try:
        stmt = select(DataScopeRule).where(DataScopeRule.tenant_id == tenant_id,
                                           DataScopeRule.is_deleted.is_(False))
        if keyword.strip():
            stmt = stmt.where(DataScopeRule.rule_name.like(f"%{keyword.strip()}%"))
        if status.strip():
            want = "ACTIVE" if status.strip().upper() in ("ENABLED", "ACTIVE") else "DISABLED"
            stmt = stmt.where(DataScopeRule.status == want)
        rules = db.scalars(stmt.order_by(DataScopeRule.id.desc())).all()
        rows = [_scope_rule_row(db, r) for r in rules]
        return success({"list": rows, "total": len(rows)})
    finally:
        db.close()


@router.get("/system/scope-rules/{rule_id}/users", summary="数据范围规则影响用户明细")
def list_scope_affected_users(rule_id: int, user=Depends(require_permission("systemAdmin.scope.view"))):
    from app.core.exceptions import AppException
    from app.models import DataScopeRule, Role, User, UserRole
    tenant_id = current_tenant_id()
    db = get_sessionmaker()()
    try:
        rule = db.scalars(select(DataScopeRule).where(DataScopeRule.id == rule_id,
                          DataScopeRule.tenant_id == tenant_id, DataScopeRule.is_deleted.is_(False))).first()
        if rule is None:
            raise AppException("DATA_NOT_FOUND", "规则不存在")
        code = str(rule.scope_type or "").upper()
        roles = db.scalars(select(Role).where(Role.tenant_id == tenant_id, Role.is_deleted.is_(False),
                                              Role.remark.like(f"%;scope={code}%"))).all()
        role_ids = [r.id for r in roles]
        if not role_ids:
            return success([])
        rows = db.execute(select(User.id, User.login_name, User.real_name, Role.role_name).join(
            UserRole, UserRole.user_id == User.id).join(Role, Role.id == UserRole.role_id).where(
            UserRole.tenant_id == tenant_id, UserRole.role_id.in_(role_ids),
            UserRole.status == "ACTIVE", UserRole.is_deleted.is_(False),
            User.is_deleted.is_(False)).limit(200)).all()
        return success([{"id": str(uid), "userNo": login, "name": name, "roleName": role_name}
                        for uid, login, name, role_name in rows])
    finally:
        db.close()


@router.post("/system/scope-rules", summary="新增/编辑数据范围规则")
def save_scope_rule(body: dict = Body(...), user=Depends(require_permission("systemAdmin.scope.manage"))):
    from app.core.exceptions import AppException
    from app.models import DataScopeRule
    tenant_id = current_tenant_id()
    name = str((body or {}).get("name") or "").strip()
    scope_code = str((body or {}).get("scopeCode") or "").strip().upper()
    remark = str((body or {}).get("remark") or "").strip()
    rule_id = (body or {}).get("id")
    if len(name) < 2:
        raise AppException("VALIDATION_ERROR", "规则名称至少 2 个字")
    if scope_code and scope_code not in _SCOPE_LABELS:
        raise AppException("VALIDATION_ERROR", "未知的范围类型")
    db = get_sessionmaker()()
    try:
        if rule_id:
            rule = db.scalars(select(DataScopeRule).where(DataScopeRule.id == int(rule_id),
                              DataScopeRule.tenant_id == tenant_id, DataScopeRule.is_deleted.is_(False))).first()
            if rule is None:
                raise AppException("DATA_NOT_FOUND", "规则不存在")
            rule.rule_name = name
            if scope_code:
                rule.scope_type = scope_code
            rule.remark = remark
            rule.version = int(rule.version or 0) + 1
            action = "编辑"
        else:
            rule = DataScopeRule(tenant_id=tenant_id, rule_name=name, scope_type=scope_code or "CUSTOM",
                                 remark=remark, status="ACTIVE")
            db.add(rule)
            action = "新增"
        db.commit(); db.refresh(rule)
        from app.services import audit_log
        audit_log.record("SCOPE_RULE_SAVE", f"数据范围规则「{name}」",
                         detail={"action": action, "scopeCode": rule.scope_type})
        return success(_scope_rule_row(db, rule), message=f"规则已{action}")
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


@router.put("/system/scope-rules/{rule_id}/status", summary="停用数据范围规则")
def set_scope_rule_status(rule_id: int, body: dict = Body(...),
                          user=Depends(require_permission("systemAdmin.scope.manage"))):
    from app.core.exceptions import AppException
    from app.models import DataScopeRule, Role
    tenant_id = current_tenant_id()
    reason = str((body or {}).get("reason") or "").strip()
    action = str((body or {}).get("action") or "DISABLE").strip().upper()
    if action == "DISABLE" and len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "作废原因必填且不少于 5 个字")
    db = get_sessionmaker()()
    try:
        rule = db.scalars(select(DataScopeRule).where(DataScopeRule.id == rule_id,
                          DataScopeRule.tenant_id == tenant_id, DataScopeRule.is_deleted.is_(False))).first()
        if rule is None:
            raise AppException("DATA_NOT_FOUND", "规则不存在")
        if action == "DISABLE":
            refs = int(db.scalar(select(func.count(Role.id)).where(
                Role.tenant_id == tenant_id, Role.is_deleted.is_(False),
                Role.remark.like(f"%;scope={str(rule.scope_type or '').upper()}%"))) or 0)
            if refs > 0:
                raise AppException("DATA_CONFLICT", f"该范围仍被 {refs} 个角色引用，请先在角色配置中改用其它范围")
        rule.status = "DISABLED" if action == "DISABLE" else "ACTIVE"
        rule.version = int(rule.version or 0) + 1
        db.commit()
        from app.services import audit_log
        audit_log.record("SCOPE_RULE_STATUS", f"数据范围规则「{rule.rule_name}」",
                         detail={"after": "已作废" if action == "DISABLE" else "启用中", "reason": reason})
        return success({"id": str(rule.id), "status": rule.status})
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


# ═══════════ 系统配置（真实可编辑 + 真实生效：登录锁定阈值/时长、密码最小长度） ═══════════
@router.get("/system/configs", summary="系统配置列表（真实生效值）")
def list_system_configs(user=Depends(require_permission("systemAdmin.config.view"))):
    from app.services import system_config_service
    return success({"list": system_config_service.list_configs()})


@router.put("/system/configs/{config_key}", summary="保存系统配置（真实生效）")
def save_system_config(config_key: str, body: dict = Body(...),
                       user=Depends(require_permission("systemAdmin.config.manage"))):
    from app.services import system_config_service
    value_text = (body or {}).get("valueText")
    reason = str((body or {}).get("reason") or "")
    return success(system_config_service.save_config(user, config_key, value_text, reason),
                   message="配置已保存并生效")


# ═══════════ 学校侧品牌配置（真实库 t_tenant_brand_config，编辑后经 get_brand 真实生效于顶栏/登录页） ═══════════
_BRAND_LOCKED_NAME = "高校学生全生命周期管理平台"
_BRAND_EDITABLE = ("schoolShortName", "brandColor", "loginSlogan", "watermarkText", "watermarkDensity", "footerText")


def _brand_form(db, tenant_id: int) -> dict:
    from app.models import TenantBrandConfig, Tenant
    row = db.scalars(select(TenantBrandConfig).where(TenantBrandConfig.tenant_id == tenant_id)).first()
    tenant = db.get(Tenant, tenant_id)
    extra = (row.config_json if row is not None and isinstance(row.config_json, dict) else {})
    return {
        "schoolName": (tenant.school_name if tenant else "") or "",  # 平台核定，学校侧只读
        "platformDisplayName": _BRAND_LOCKED_NAME,                      # 平台核定，学校侧只读
        "schoolShortName": extra.get("schoolShortName", "") or (tenant.short_name if tenant else "") or "",
        "brandColor": (row.primary_color if row is not None else "") or "#2563EB",
        "loginSlogan": extra.get("loginSlogan", "") or (row.motto if row is not None else "") or "",
        "watermarkText": (row.watermark_text if row is not None else "") or "",
        "watermarkDensity": extra.get("watermarkDensity", "") or "适中",
        "footerText": extra.get("footerText", "") or "",
    }


@router.get("/system/brand", summary="学校侧品牌配置（真实库）")
def get_system_brand(user=Depends(require_permission("systemAdmin.config.view"))):
    tenant_id = int(current_tenant_id() or 0)
    db = get_sessionmaker()()
    try:
        return success(_brand_form(db, tenant_id))
    finally:
        db.close()


@router.put("/system/brand", summary="保存学校侧品牌配置（真实生效）")
def save_system_brand(body: dict = Body(...), user=Depends(require_permission("systemAdmin.config.manage"))):
    from app.core.exceptions import AppException
    from app.models import TenantBrandConfig
    tenant_id = int(current_tenant_id() or 0)
    patch = {k: str(v) for k, v in (body or {}).items() if k in _BRAND_EDITABLE and v is not None}
    reason = str((body or {}).get("reason") or "")
    if not patch:
        raise AppException("VALIDATION_ERROR", "没有可保存的品牌变更（学校名称/平台显示名为平台核定项，学校侧不可修改）")
    if "brandColor" in patch and not re.fullmatch(r"#[0-9A-Fa-f]{6}", patch["brandColor"]):
        raise AppException("VALIDATION_ERROR", "品牌主色须为 #RRGGBB 十六进制")
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(TenantBrandConfig).where(TenantBrandConfig.tenant_id == tenant_id)).first()
        if row is None:
            row = TenantBrandConfig(tenant_id=tenant_id)
            db.add(row)
        before = _brand_form(db, tenant_id)
        extra = dict(row.config_json) if isinstance(row.config_json, dict) else {}
        if "brandColor" in patch:
            row.primary_color = patch["brandColor"]
        if "watermarkText" in patch:
            row.watermark_text = patch["watermarkText"]
        if "loginSlogan" in patch:
            row.motto = patch["loginSlogan"]
        for k in ("schoolShortName", "loginSlogan", "footerText", "watermarkDensity"):
            if k in patch:
                extra[k] = patch[k]
        row.config_json = extra
        db.commit()
        after = _brand_form(db, tenant_id)
        from app.services import audit_log
        audit_log.record("BRAND_CONFIG", "学校品牌配置",
                         detail={"keys": list(patch), "reason": reason, "summary": f"变更 {len(patch)} 项品牌配置（真实生效）"})
        return success(after, message="品牌配置已保存并生效")
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


@router.post("/system/brand/reset", summary="恢复学校品牌为平台默认值（真实生效）")
def reset_system_brand(body: dict = Body(...),
                       user=Depends(require_permission("systemAdmin.config.manage"))):
    from app.core.exceptions import AppException
    from app.models import TenantBrandConfig
    tenant_id = int(current_tenant_id() or 0)
    reason = str((body or {}).get("reason") or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "恢复默认原因不少于 5 个字")
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(TenantBrandConfig).where(
            TenantBrandConfig.tenant_id == tenant_id)).first()
        before = _brand_form(db, tenant_id)
        if row is not None:
            row.primary_color = None
            row.watermark_text = None
            row.motto = None
            extra = dict(row.config_json) if isinstance(row.config_json, dict) else {}
            for key in ("schoolShortName", "loginSlogan", "footerText", "watermarkDensity"):
                extra.pop(key, None)
            row.config_json = extra
        db.commit()
        after = _brand_form(db, tenant_id)
        from app.services import audit_log
        audit_log.record(
            "BRAND_CONFIG_RESET",
            "学校品牌配置",
            detail={
                "reason": reason,
                "before": before,
                "after": after,
                "summary": "学校自定义品牌已恢复为平台默认值",
                "moduleCode": "systemAdmin",
            },
        )
        return success(after, message="品牌配置已恢复为平台默认值")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.get("/system/info", summary="系统信息 / 能力开关（需登录）")
def system_info(user=Depends(require_any_permission(
        "systemAdmin.dashboard.view", "systemAdmin.config.view", "systemAdmin.audit.view"))):
    now = datetime.now(timezone(timedelta(hours=settings.TIMEZONE_OFFSET_HOURS))).isoformat(timespec="seconds")
    return success({
        "appName": settings.APP_NAME,
        "env": settings.APP_ENV,
        "version": "1.0.0",
        "apiPrefix": settings.API_V1_PREFIX,
        "tenancyMode": settings.TENANCY_MODE,
        "databaseConnected": bool(settings.DB_ENABLED and db_enabled()),
        "serverTime": now,
        "capabilities": {
            "auth": "real", "rbac": "real", "tenantBrand": "real",
            "todo": "real", "message": "real", "audit": "real",
            "fileUpload": "real", "import": "real",
            "export": "real", "database": "mysql" if db_enabled() else "disabled",
        },
        "operator": {"userId": (user or {}).get("userId"), "role": (user or {}).get("currentRoleCode")},
    })


# ═══════════ 治理扩展：临时授权 / 接口 / 同步 / 模块开关 ═══════════

@router.get("/system/delegations", summary="临时授权列表")
def api_list_delegations(user=Depends(require_permission("systemAdmin.delegation.manage"))):
    from app.services import system_governance_service as gov
    items = gov.list_delegations()
    return success({"list": items, "total": len(items)})


@router.post("/system/delegations", summary="创建临时授权")
def api_create_delegation(body: dict = Body(...), user=Depends(require_permission("systemAdmin.delegation.manage"))):
    from app.services import system_governance_service as gov
    return success(gov.create_delegation(user, body or {}), message="临时授权已创建")


@router.post("/system/delegations/{delegation_id}/revoke", summary="回收临时授权")
def api_revoke_delegation(delegation_id: str, body: dict = Body(...),
                          user=Depends(require_permission("systemAdmin.delegation.manage"))):
    from app.services import system_governance_service as gov
    return success(gov.revoke_delegation(user, delegation_id, (body or {}).get("reason") or ""),
                   message="临时授权已回收")


@router.get("/system/integrations", summary="接口连接列表")
def api_list_integrations(user=Depends(require_permission("systemAdmin.integration.manage"))):
    from app.services import system_governance_service as gov
    items = gov.list_integrations()
    return success({"list": items, "total": len(items)})


@router.post("/system/integrations", summary="保存接口连接")
def api_save_integration(body: dict = Body(...), user=Depends(require_permission("systemAdmin.integration.manage"))):
    from app.services import system_governance_service as gov
    return success(gov.save_integration(user, body or {}), message="接口连接已保存")


@router.post("/system/integrations/{integration_id}/rotate", summary="轮换接口凭证")
def api_rotate_integration(integration_id: str, body: dict = Body(...),
                           user=Depends(require_permission("systemAdmin.integration.manage"))):
    from app.services import system_governance_service as gov
    return success(gov.rotate_integration_credential(user, integration_id, (body or {}).get("credential") or ""),
                   message="凭证已轮换")


@router.get("/system/sync-jobs", summary="同步任务列表")
def api_list_sync_jobs(user=Depends(require_any_permission(
        "systemAdmin.integration.sync.view", "systemAdmin.integration.manage"))):
    from app.services import system_governance_service as gov
    items = gov.list_sync_jobs()
    return success({"list": items, "total": len(items)})


@router.post("/system/sync-jobs", summary="登记同步任务")
def api_enqueue_sync_job(body: dict = Body(...), user=Depends(require_permission("systemAdmin.integration.manage"))):
    from app.services import system_governance_service as gov
    return success(gov.enqueue_sync_job(user, body or {}), message="同步任务已登记")


@router.post("/system/sync-jobs/{job_id}/retry", summary="重试同步任务")
def api_retry_sync_job(job_id: str, user=Depends(require_permission("systemAdmin.integration.manage"))):
    from app.services import system_governance_service as gov
    return success(gov.retry_sync_job(user, job_id), message="已重试")


@router.post("/system/sync-jobs/{job_id}/cancel", summary="取消同步任务")
def api_cancel_sync_job(job_id: str, body: dict = Body(...),
                        user=Depends(require_permission("systemAdmin.integration.manage"))):
    from app.services import system_governance_service as gov
    return success(gov.cancel_sync_job(user, job_id, (body or {}).get("reason") or ""), message="已取消")


@router.get("/system/module-features", summary="模块授权与业务开关（学校只读套餐 + 可调开关）")
def api_get_module_features(user=Depends(require_any_permission(
        "systemAdmin.config.feature.view", "systemAdmin.config.view"))):
    from app.services import system_governance_service as gov
    return success(gov.get_module_features())


@router.put("/system/module-features", summary="调整业务开关")
def api_save_module_features(body: dict = Body(...),
                             user=Depends(require_permission("systemAdmin.config.manage"))):
    from app.services import system_governance_service as gov
    features = (body or {}).get("features") or body or {}
    reason = (body or {}).get("reason") or ""
    return success(gov.save_module_features(
        user, features, reason, expected_version=(body or {}).get("expectedVersion")),
        message="业务开关已更新")


# ── SYS-13 能力启用（结构化单键写入，取代整份 MODULE_FEATURES 覆盖）─────────────
@router.get("/system/capability-settings", summary="模块商业授权与学校启用（四态：entitled/enabled/ready/allowed）")
def api_list_capability_settings(user=Depends(require_any_permission(
        "systemAdmin.config.feature.view", "systemAdmin.config.view"))):
    from app.services import tenant_capability_setting_service as caps
    items = caps.list_capabilities()
    return success({"list": items, "total": len(items)})


@router.get("/system/capability-settings/{capability_key}/impact", summary="停用影响预览")
def api_capability_impact(capability_key: str, user=Depends(require_any_permission(
        "systemAdmin.config.feature.view", "systemAdmin.config.view"))):
    from app.services import tenant_capability_setting_service as caps
    return success(caps.capability_impact(capability_key))


@router.put("/system/capability-settings/{capability_key}", summary="启停单个能力（带 expectedVersion）")
def api_set_capability_setting(capability_key: str, body: dict = Body(...),
                               user=Depends(require_permission("systemAdmin.config.manage"))):
    from app.services import tenant_capability_setting_service as caps
    payload = body or {}
    if "enabled" not in payload:
        from app.core.exceptions import AppException
        raise AppException("VALIDATION_ERROR", "缺少 enabled")
    return success(caps.set_capability(
        capability_key,
        enabled=bool(payload.get("enabled")),
        reason=payload.get("reason") or "",
        expected_version=payload.get("expectedVersion"),
        expires_at=payload.get("expiresAt"),
        user=user,
    ), message="模块开关已更新")


@router.post("/system/integrations/{integration_id}/test", summary="测试接口连接（可达性，不伪造成功连接）")
def api_test_integration(integration_id: str, user=Depends(require_permission("systemAdmin.integration.manage"))):
    from app.services import system_governance_service as gov
    return success(gov.test_integration_connection(user, integration_id), message="连接测试完成")


@router.post("/system/data-scope/simulate", summary="数据范围模拟：输入用户与业务对象，返回允许/拒绝原因")
def api_simulate_data_scope(body: dict = Body(...),
                            user=Depends(require_permission("systemAdmin.scope.view"))):
    from app.services.data_scope_service import simulate_access
    target_user = (body or {}).get("user") or user
    result = simulate_access(
        target_user,
        resource_type=str((body or {}).get("resourceType") or "generic"),
        resource=(body or {}).get("resource") or {},
        sensitive=bool((body or {}).get("sensitive")),
    )
    return success(result)


@router.get("/system/go-live-checks", summary="上线检查（阻断/建议/通过/不适用）")
def api_go_live_checks(user=Depends(require_any_permission(
        "systemAdmin.implementation.check.run", "systemAdmin.implementation.view", "systemAdmin.dashboard.view"))):
    from app.services.go_live_check_service import run_go_live_checks
    return success(run_go_live_checks())


@router.get("/system/capability-map", summary="完整能力地图（与日常菜单分离）")
def api_capability_map(user=Depends(require_any_permission(
        "systemAdmin.dashboard.view", "systemAdmin.implementation.view"))):
    from pathlib import Path
    import json
    path = Path(__file__).resolve().parents[4] / "shared" / "generated" / "capability-registry.json"
    if not path.exists():
        return success({"count": 0, "capabilities": [], "note": "请先运行 generate-capability-registry.mjs"})
    data = json.loads(path.read_text(encoding="utf-8"))
    return success({"count": data.get("count"), "generatedAt": data.get("generatedAt"),
                    "capabilities": data.get("capabilities") or []})


@router.get("/system/overview-board", summary="系统总览第一屏：健康/缺口/同步失败/安全风险/待办")
def api_overview_board(user=Depends(require_any_permission(
        "systemAdmin.dashboard.view", "systemAdmin.implementation.view"))):
    from app.services import system_governance_service as gov
    from app.services.go_live_check_service import run_go_live_checks
    from app.services.module_access_service import module_access_state

    tid = int(current_tenant_id() or 0)
    checks = run_go_live_checks(tid)
    jobs = gov.list_sync_jobs()
    failed = [j for j in jobs if j.get("status") == "FAILED"]
    modules = {}
    for mk in ("studentAffairs", "academicAffairs", "graduationDesign", "internship", "employment", "orientation"):
        modules[mk] = module_access_state(tid, mk) if tid else {"entitled": False, "enabled": False}
    risks = []
    if checks["summary"]["blocker"]:
        risks.append({"level": "HIGH", "text": f"{checks['summary']['blocker']} 项阻断上线检查未通过"})
    if failed:
        risks.append({"level": "MEDIUM", "text": f"{len(failed)} 个同步任务失败"})
    todos = [c for c in checks["items"] if c["status"] in ("BLOCKER", "ADVISORY")][:12]
    return success({
        "moduleHealth": modules,
        "configGaps": [c for c in checks["items"] if c["status"] in ("BLOCKER", "ADVISORY")],
        "syncFailures": failed[:20],
        "securityRisks": risks,
        "pendingItems": todos,
        "goLive": {"canGoLive": checks["canGoLive"], "summary": checks["summary"]},
    })


# ═══════════ SYS-12 学年学期、业务日历与统一切换 ═══════════
# 设计来源：existing_code（t_aa_term 仍是学期事实源）+ V6 SYS-12 卡（治理状态机与唯一 ACTIVE）。
# 系统管理只做治理与统一读取入口，学期主数据仍由教务维护，避免第二个"当前学期"。

def _calendar_dt(value, field: str, *, required: bool = True):
    """解析 ISO 时间。前端统一传 ISO8601，服务端按 UTC 存储。"""
    from app.core.exceptions import AppException

    if value in (None, ""):
        if required:
            raise AppException("VALIDATION_ERROR", f"{field} 不能为空")
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo is None else value.astimezone(timezone.utc).replace(tzinfo=None)
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as exc:
        raise AppException("VALIDATION_ERROR", f"{field} 格式不正确，应为 ISO8601") from exc
    return parsed.astimezone(timezone.utc).replace(tzinfo=None) if parsed.tzinfo else parsed


@router.get("/system/academic-calendars", summary="学年学期治理列表与切换影响面")
def list_academic_calendars(user=Depends(require_permission("systemAdmin.academicCalendar.view"))):
    from app.services import academic_calendar_service as svc

    return success(svc.list_calendars())


@router.get("/system/academic-calendars/current", summary="当前生效学期（全系统唯一读取入口）")
def current_academic_calendar(
    module: str | None = None,
    user=Depends(require_any_permission("systemAdmin.academicCalendar.view", "systemAdmin.dashboard.view")),
):
    from app.services import academic_calendar_service as svc

    return success(svc.resolve_current(module_code=module))


@router.get("/system/academic-calendars/{term_id}", summary="学期治理详情、阻断项、窗口与切换历史")
def get_academic_calendar(term_id: int, user=Depends(require_permission("systemAdmin.academicCalendar.view"))):
    from app.services import academic_calendar_service as svc

    return success(svc.get_calendar(term_id))


@router.post("/system/academic-calendars/{term_id}/enroll", summary="把教务已建学期纳入全校治理（幂等）")
def enroll_academic_calendar(
    term_id: int,
    body: dict = Body(default={}),
    user=Depends(require_permission("systemAdmin.academicCalendar.manage")),
):
    from app.services import academic_calendar_service as svc

    return success(svc.enroll_term(term_id, timezone=str(body.get("timezone") or "Asia/Shanghai")))


@router.post("/system/academic-calendars/{term_id}/transition", summary="学期状态统一切换（含激活、结期、归档）")
def transition_academic_calendar(
    term_id: int,
    body: dict = Body(...),
    user=Depends(require_permission("systemAdmin.academicCalendar.manage")),
):
    from app.core.exceptions import AppException
    from app.services import academic_calendar_service as svc

    target = str(body.get("targetStatus") or "").upper()
    if "expectedVersion" not in body:
        raise AppException("VALIDATION_ERROR", "缺少 expectedVersion，无法保证并发安全")
    return success(
        svc.transition(
            term_id,
            target,
            reason=str(body.get("reason") or ""),
            expected_version=int(body.get("expectedVersion")),
            scheduled_at=_calendar_dt(body.get("scheduledAt"), "scheduledAt", required=False),
            force=bool(body.get("force")),
        ),
        message=f"学期状态已变更为 {target}",
    )


@router.get("/system/academic-calendars/{term_id}/closing-blockers", summary="结期阻断项（只读，不代业务确认）")
def academic_calendar_blockers(term_id: int, user=Depends(require_permission("systemAdmin.academicCalendar.view"))):
    from app.services import academic_calendar_service as svc

    return success({"items": svc.closing_blockers(term_id)})


@router.put("/system/academic-calendars/{term_id}/windows", summary="维护考试/迎新/实习/毕设等业务窗口")
def upsert_academic_calendar_window(
    term_id: int,
    body: dict = Body(...),
    user=Depends(require_permission("systemAdmin.academicCalendar.manage")),
):
    from app.services import academic_calendar_service as svc

    return success(
        svc.upsert_window(
            term_id,
            window_type=str(body.get("windowType") or ""),
            module_code=str(body.get("moduleCode") or ""),
            start_at=_calendar_dt(body.get("startAt"), "startAt"),
            end_at=_calendar_dt(body.get("endAt"), "endAt"),
            config=body.get("config") or {},
            expected_version=body.get("expectedVersion"),
        ),
        message="业务窗口已保存",
    )


# ═══════════ SYS-04 组织变更版本与教职工任职 ═══════════
# 组织仍是 t_college/t_major/t_class 三张实体表；这里只加"未来生效的变更集"和"带有效期的任职"。
# 既有 /system/org-tree、/system/org-nodes 保持不变，继续服务于当前组织的即时维护。

@router.get("/system/org-versions", summary="组织变更版本列表")
def list_org_versions(user=Depends(require_permission("systemAdmin.org.view"))):
    from app.services import organization_version_service as svc

    return success(svc.list_versions())


@router.post("/system/org-versions", summary="创建组织变更版本（草稿不影响当前组织）")
def create_org_version(body: dict = Body(...), user=Depends(require_permission("systemAdmin.org.activate"))):
    from app.services import organization_version_service as svc

    return success(
        svc.create_version(version_name=str(body.get("versionName") or ""), reason=str(body.get("reason") or "")),
        message="组织变更版本已创建",
    )


@router.get("/system/org-versions/{version_id}", summary="组织变更版本详情与变更项")
def get_org_version(version_id: int, user=Depends(require_permission("systemAdmin.org.view"))):
    from app.services import organization_version_service as svc

    return success(svc.get_version(version_id))


@router.post("/system/org-versions/{version_id}/changes", summary="向草稿版本添加一条组织变更")
def add_org_version_change(
    version_id: int, body: dict = Body(...), user=Depends(require_permission("systemAdmin.org.activate"))
):
    from app.services import organization_version_service as svc

    return success(
        svc.add_change(
            version_id,
            change_type=str(body.get("changeType") or ""),
            org_type=str(body.get("orgType") or ""),
            org_node_id=body.get("orgNodeId"),
            payload=body.get("payload") or {},
        ),
        message="变更项已加入草稿",
    )


@router.post("/system/org-versions/{version_id}/transition", summary="校验/排期/激活/回滚组织变更版本")
def transition_org_version(
    version_id: int, body: dict = Body(...), user=Depends(require_permission("systemAdmin.org.activate"))
):
    from app.core.exceptions import AppException
    from app.services import organization_version_service as svc

    if "expectedVersion" not in body:
        raise AppException("VALIDATION_ERROR", "缺少 expectedVersion，无法保证并发安全")
    target = str(body.get("targetStatus") or "").upper()
    return success(
        svc.transition_version(
            version_id,
            target,
            reason=str(body.get("reason") or ""),
            expected_version=int(body.get("expectedVersion")),
            effective_at=_calendar_dt(body.get("effectiveAt"), "effectiveAt", required=False),
        ),
        message=f"组织版本已变更为 {target}",
    )


@router.get("/system/org-nodes/{org_type}/{node_id}/impact", summary="移动或停用该节点会影响谁")
def org_node_impact(org_type: str, node_id: int, user=Depends(require_permission("systemAdmin.org.view"))):
    from app.services import organization_version_service as svc

    return success(svc.compute_impact(str(org_type).upper(), node_id))


@router.get("/system/staff-assignments", summary="教职工任职（带有效期，默认只返回此刻生效的）")
def list_staff_assignments(
    userId: int | None = None,
    orgType: str | None = None,
    orgNodeId: int | None = None,
    includeExpired: bool = False,
    user=Depends(require_any_permission("systemAdmin.org.affiliation.manage", "systemAdmin.org.view")),
):
    from app.services import organization_version_service as svc

    return success(
        svc.list_assignments(
            user_id=userId, org_type=orgType, org_node_id=orgNodeId, include_expired=includeExpired
        )
    )


@router.post("/system/staff-assignments", summary="任命教职工岗位（可指定起止时间）")
def create_staff_assignment(
    body: dict = Body(...), user=Depends(require_permission("systemAdmin.org.affiliation.manage"))
):
    from app.services import organization_version_service as svc

    return success(
        svc.create_assignment(
            user_id=int(body.get("userId")),
            org_type=str(body.get("orgType") or ""),
            org_node_id=int(body.get("orgNodeId")),
            assignment_type=str(body.get("assignmentType") or ""),
            effective_at=_calendar_dt(body.get("effectiveAt"), "effectiveAt", required=False),
            expires_at=_calendar_dt(body.get("expiresAt"), "expiresAt", required=False),
            is_primary=bool(body.get("isPrimary")),
            reason=str(body.get("reason") or ""),
        ),
        message="任职已生效",
    )


@router.post("/system/staff-assignments/{assignment_id}/revoke", summary="撤销任职")
def revoke_staff_assignment(
    assignment_id: int, body: dict = Body(...), user=Depends(require_permission("systemAdmin.org.affiliation.manage"))
):
    from app.core.exceptions import AppException
    from app.services import organization_version_service as svc

    if "expectedVersion" not in body:
        raise AppException("VALIDATION_ERROR", "缺少 expectedVersion，无法保证并发安全")
    return success(
        svc.revoke_assignment(
            assignment_id, reason=str(body.get("reason") or ""), expected_version=int(body.get("expectedVersion"))
        ),
        message="任职已撤销",
    )


# ═══════════ SYS-11 有效配置：定义、分层覆盖与来源解释 ═══════════
# t_sys_config 继续承载学校既有安全配置且仍被 auth 强制层读取；这里补"平台底线校验、
# 分层覆盖、未来生效和来源链解释"，解析时把旧表作为 TENANT_LEGACY 层一并合并。

@router.get("/system/config-registry", summary="配置项定义目录")
def config_registry(user=Depends(require_permission("systemAdmin.config.view"))):
    from app.services import effective_config_service as svc

    svc.ensure_definitions()
    return success(svc.resolve_all())


@router.get("/system/effective-config", summary="配置最终值与完整来源链")
def effective_config(
    configKey: str | None = None,
    domain: str | None = None,
    orgUnitId: str | None = None,
    termId: str | None = None,
    user=Depends(require_permission("systemAdmin.config.view")),
):
    from app.services import effective_config_service as svc

    svc.ensure_definitions()
    if configKey:
        return success(svc.resolve(configKey, org_unit_id=orgUnitId, term_id=termId))
    return success(svc.resolve_all(domain=domain))


@router.put("/system/config-overrides", summary="设置学校/组织/学期级配置覆盖")
def set_config_override(
    body: dict = Body(...), user=Depends(require_permission("systemAdmin.config.manage"))
):
    from app.core.exceptions import AppException
    from app.services import effective_config_service as svc

    config_key = str(body.get("configKey") or "")
    if not config_key:
        raise AppException("VALIDATION_ERROR", "缺少 configKey")
    svc.ensure_definitions()
    return success(
        svc.set_override(
            config_key,
            value=body.get("value"),
            scope_type=str(body.get("scopeType") or "TENANT"),
            scope_id=str(body.get("scopeId") or ""),
            effective_at=_calendar_dt(body.get("effectiveAt"), "effectiveAt", required=False),
            expires_at=_calendar_dt(body.get("expiresAt"), "expiresAt", required=False),
            reason=str(body.get("reason") or ""),
            expected_version=body.get("expectedVersion"),
        ),
        message="配置已保存",
    )


@router.post("/system/config-overrides/{override_id}/revoke", summary="撤销一层配置覆盖")
def revoke_config_override(
    override_id: int, body: dict = Body(...), user=Depends(require_permission("systemAdmin.config.manage"))
):
    from app.core.exceptions import AppException
    from app.services import effective_config_service as svc

    if "expectedVersion" not in body:
        raise AppException("VALIDATION_ERROR", "缺少 expectedVersion，无法保证并发安全")
    return success(
        svc.revoke_override(
            override_id, reason=str(body.get("reason") or ""), expected_version=int(body.get("expectedVersion"))
        ),
        message="配置覆盖已撤销",
    )


@router.get("/system/config-history/{config_key}", summary="配置变更历史")
def config_history(config_key: str, user=Depends(require_permission("systemAdmin.config.view"))):
    from app.services import effective_config_service as svc

    return success(svc.history(config_key))


# ═══════════ SYS-06 权限包、交付角色模板与自定义角色 ═══════════
# 治理层，不接管鉴权：真实鉴权仍读 app.core.permissions.ROLE_PERMISSIONS 常量。
# 保存自定义角色只写治理表，不改变任何人当前的实际权限。

@router.post("/system/permission-governance/bootstrap", summary="从当前代码固化交付模板与权限包（幂等）")
def bootstrap_permission_governance(user=Depends(require_permission("systemAdmin.role.config"))):
    from app.services import permission_bundle_service as svc

    return success(svc.bootstrap_from_code(), message="交付模板与权限包已同步")


@router.get("/system/permission-bundles", summary="权限包目录")
def list_permission_bundles(user=Depends(require_any_permission(
        "systemAdmin.role.view", "systemAdmin.role.config"))):
    from app.services import permission_bundle_service as svc

    return success(svc.list_bundles())


@router.get("/system/role-templates", summary="交付角色模板（DELIVERED，学校只读）")
def list_role_templates(user=Depends(require_any_permission(
        "systemAdmin.role.view", "systemAdmin.role.config"))):
    from app.services import permission_bundle_service as svc

    return success(svc.list_templates())


@router.get("/system/role-templates/{template_code}", summary="模板权限上限与持有的通配")
def get_role_template(template_code: str, user=Depends(require_any_permission(
        "systemAdmin.role.view", "systemAdmin.role.config"))):
    from app.services import permission_bundle_service as svc

    return success(svc.get_template(template_code))


@router.get("/system/custom-roles", summary="学校自定义角色（含来源模板）")
def list_custom_roles(user=Depends(require_any_permission(
        "systemAdmin.role.view", "systemAdmin.role.config"))):
    from app.services import permission_bundle_service as svc

    return success(svc.list_custom_roles())


@router.post("/system/custom-roles/clone", summary="从交付模板复制出学校自定义角色")
def clone_custom_role(body: dict = Body(...), user=Depends(require_permission("systemAdmin.role.config"))):
    from app.core.exceptions import AppException
    from app.services import permission_bundle_service as svc

    template_code = str(body.get("templateCode") or "")
    new_role_code = str(body.get("roleCode") or "")
    if not template_code or not new_role_code:
        raise AppException("VALIDATION_ERROR", "缺少 templateCode 或 roleCode")
    return success(
        svc.clone_template(
            template_code, new_role_code=new_role_code, permission_codes=body.get("permissionCodes")
        ),
        message="自定义角色已创建（草稿不改变真实鉴权）",
    )


@router.put("/system/custom-roles/{role_code}", summary="裁剪自定义角色权限（不得超模板上限）")
def update_custom_role(
    role_code: str, body: dict = Body(...), user=Depends(require_permission("systemAdmin.role.config"))
):
    from app.core.exceptions import AppException
    from app.services import permission_bundle_service as svc

    if "expectedVersion" not in body:
        raise AppException("VALIDATION_ERROR", "缺少 expectedVersion，无法保证并发安全")
    return success(
        svc.update_custom_role(
            role_code,
            permission_codes=body.get("permissionCodes") or [],
            expected_version=int(body.get("expectedVersion")),
        ),
        message="自定义角色已保存（草稿不改变真实鉴权）",
    )


@router.get("/system/wildcard-retirement", summary="通配权限退役队列")
def wildcard_retirement_queue(user=Depends(require_any_permission(
        "systemAdmin.role.view", "systemAdmin.role.config"))):
    from app.services import permission_bundle_service as svc

    return success(svc.wildcard_queue())


# ═══════════ SYS-08 组织安全树：显式 DENY、继承与判定解释 ═══════════
# 既有 t_data_scope_rule 和 data_scope_service 的 provider 继续负责"业务关系"这一层；
# 这里只补显式 DENY、敏感专项、未来生效，并把整条判定链解释出来。

@router.get("/system/scope-policies", summary="范围策略列表（ALLOW/DENY）")
def list_scope_policies(
    roleCode: str | None = None,
    user=Depends(require_any_permission("systemAdmin.scope.view", "systemAdmin.role.view")),
):
    from app.services import scope_policy_service as svc

    return success(svc.list_policies(role_code=roleCode))


@router.put("/system/scope-policies", summary="设置角色对某组织节点的 ALLOW 或 DENY")
def set_scope_policy(body: dict = Body(...), user=Depends(require_permission("systemAdmin.scope.manage"))):
    from app.core.exceptions import AppException
    from app.services import scope_policy_service as svc

    role_code = str(body.get("roleCode") or "")
    if not role_code:
        raise AppException("VALIDATION_ERROR", "缺少 roleCode")
    return success(
        svc.set_policy(
            role_code,
            effect=str(body.get("effect") or "ALLOW"),
            target_type=str(body.get("targetType") or ""),
            target_id=str(body.get("targetId") or ""),
            include_children=bool(body.get("includeChildren", True)),
            sensitive_domain=body.get("sensitiveDomain"),
            effective_at=_calendar_dt(body.get("effectiveAt"), "effectiveAt", required=False),
            expires_at=_calendar_dt(body.get("expiresAt"), "expiresAt", required=False),
            reason=str(body.get("reason") or ""),
            expected_version=body.get("expectedVersion"),
        ),
        message="范围策略已保存",
    )


@router.post("/system/scope-policies/{policy_id}/revoke", summary="撤销一条范围策略")
def revoke_scope_policy(
    policy_id: int, body: dict = Body(...), user=Depends(require_permission("systemAdmin.scope.manage"))
):
    from app.core.exceptions import AppException
    from app.services import scope_policy_service as svc

    if "expectedVersion" not in body:
        raise AppException("VALIDATION_ERROR", "缺少 expectedVersion，无法保证并发安全")
    return success(
        svc.revoke_policy(
            policy_id, reason=str(body.get("reason") or ""), expected_version=int(body.get("expectedVersion"))
        ),
        message="范围策略已撤销",
    )


@router.post("/system/scope-policies/simulate", summary="模拟判定：返回完整判定链与原因码")
def simulate_scope_policy(
    body: dict = Body(...),
    user=Depends(require_any_permission("systemAdmin.scope.view", "systemAdmin.role.view")),
):
    from app.core.exceptions import AppException
    from app.services import scope_policy_service as svc

    role_code = str(body.get("roleCode") or "")
    if not role_code:
        raise AppException("VALIDATION_ERROR", "缺少 roleCode")
    return success(
        svc.decide(
            role_code,
            target_type=str(body.get("targetType") or ""),
            target_id=str(body.get("targetId") or ""),
            business_relation_allows=body.get("businessRelationAllows"),
        )
    )


@router.get("/system/scope-policies/references/{role_code}", summary="角色范围引用统计（结构化来源）")
def scope_policy_references(
    role_code: str,
    user=Depends(require_any_permission("systemAdmin.scope.view", "systemAdmin.role.view")),
):
    from app.services import scope_policy_service as svc

    return success(svc.references(role_code))


# ═══════════ SYS-09 安全变更：草稿、审核、排期、激活与回滚 ═══════════
# 草稿/审核/排期期间不写任何目标表——改动只存在变更项里，物理上没碰权限配置。
# 只有激活才在单事务内应用并产生新的 securityRevision。

@router.get("/system/security-revision", summary="当前安全版本号（客户端据此判断权限快照是否过期）")
def get_security_revision(user=Depends(require_any_permission(
        "systemAdmin.security.view", "systemAdmin.role.view", "systemAdmin.dashboard.view"))):
    from app.services import security_change_service as svc

    return success({"currentRevision": svc.current_revision()})


@router.get("/system/security-changes", summary="安全变更列表")
def list_security_changes(user=Depends(require_any_permission(
        "systemAdmin.security.view", "systemAdmin.role.view"))):
    from app.services import security_change_service as svc

    return success(svc.list_change_sets())


@router.post("/system/security-changes", summary="创建安全变更草稿（不影响任何人当前权限）")
def create_security_change(body: dict = Body(...), user=Depends(require_permission("systemAdmin.security.manage"))):
    from app.services import security_change_service as svc

    return success(
        svc.create_change_set(
            title=str(body.get("title") or ""),
            reason=str(body.get("reason") or ""),
            risk_level=str(body.get("riskLevel") or "NORMAL"),
        ),
        message="安全变更草稿已创建",
    )


@router.get("/system/security-changes/{change_set_id}", summary="安全变更详情与变更项")
def get_security_change(change_set_id: int, user=Depends(require_any_permission(
        "systemAdmin.security.view", "systemAdmin.role.view"))):
    from app.services import security_change_service as svc

    return success(svc.get_change_set(change_set_id))


@router.post("/system/security-changes/{change_set_id}/items", summary="向草稿追加一条改动")
def add_security_change_item(
    change_set_id: int, body: dict = Body(...), user=Depends(require_permission("systemAdmin.security.manage"))
):
    from app.services import security_change_service as svc

    return success(
        svc.add_item(
            change_set_id,
            target_type=str(body.get("targetType") or ""),
            target_id=str(body.get("targetId") or ""),
            after=body.get("after") or {},
        ),
        message="变更项已加入草稿",
    )


@router.post("/system/security-changes/{change_set_id}/transition", summary="提交/审核/排期/激活/回滚")
def transition_security_change(
    change_set_id: int, body: dict = Body(...), user=Depends(require_permission("systemAdmin.security.manage"))
):
    from app.core.exceptions import AppException
    from app.services import security_change_service as svc

    if "expectedVersion" not in body:
        raise AppException("VALIDATION_ERROR", "缺少 expectedVersion，无法保证并发安全")
    target = str(body.get("targetStatus") or "").upper()
    return success(
        svc.transition(
            change_set_id,
            target,
            reason=str(body.get("reason") or ""),
            expected_version=int(body.get("expectedVersion")),
            scheduled_at=_calendar_dt(body.get("scheduledAt"), "scheduledAt", required=False),
            self_review_ack=body.get("selfReviewAck"),
        ),
        message=f"安全变更已变更为 {target}",
    )


@router.get("/system/security-activations", summary="安全激活历史（版本号只进不退）")
def list_security_activations(user=Depends(require_any_permission(
        "systemAdmin.security.view", "systemAdmin.audit.view"))):
    from app.services import security_change_service as svc

    return success(svc.activation_history())


# ═══════════ SYS-10 访问解释、权限复核、职责分离与紧急访问 ═══════════
# 解释器只展开真实鉴权函数的中间量，最终结论以 has_permission 为准；
# 资源标识一律以摘要出现，避免这个接口变成对象枚举器。

@router.post("/system/access-explanations", summary="解释某人对某动作的判定，逐层给出 PASS/FAIL")
def create_access_explanation(
    body: dict = Body(...),
    user=Depends(require_any_permission("systemAdmin.access.explain", "systemAdmin.audit.view")),
):
    from app.core.exceptions import AppException
    from app.services import policy_decision_service as svc

    action_code = str(body.get("actionCode") or "")
    if not action_code:
        raise AppException("VALIDATION_ERROR", "缺少 actionCode")
    # 默认解释当前登录者；解释他人需要更高权限，避免变成探测工具
    subject = body.get("subject") or user
    return success(
        svc.explain(
            subject,
            action_code=action_code,
            resource_type=body.get("resourceType"),
            resource_id=body.get("resourceId"),
            scope_target_type=body.get("scopeTargetType"),
            scope_target_id=body.get("scopeTargetId"),
        )
    )


@router.get("/system/access-explanations/{trace_id}", summary="按 traceId 复现当时的判定链")
def get_access_explanation(
    trace_id: str,
    user=Depends(require_any_permission("systemAdmin.access.explain", "systemAdmin.audit.view")),
):
    from app.services import policy_decision_service as svc

    return success(svc.get_trace(trace_id))


@router.get("/system/access-denials", summary="最近的拒绝记录")
def list_access_denials(user=Depends(require_any_permission(
        "systemAdmin.access.explain", "systemAdmin.audit.view"))):
    from app.services import policy_decision_service as svc

    return success(svc.list_denials())


@router.get("/system/sod", summary="职责分离规则与已检出冲突")
def list_sod_rules(user=Depends(require_any_permission(
        "systemAdmin.access.explain", "systemAdmin.role.view"))):
    from app.services import policy_decision_service as svc

    return success(svc.list_sod())


@router.post("/system/sod/rules", summary="新增职责分离规则")
def create_sod_rule(body: dict = Body(...), user=Depends(require_permission("systemAdmin.security.manage"))):
    from app.services import policy_decision_service as svc

    return success(
        svc.add_sod_rule(
            rule_code=str(body.get("ruleCode") or ""),
            role_a=str(body.get("roleA") or ""),
            role_b=str(body.get("roleB") or ""),
            reason=str(body.get("reason") or ""),
            severity=str(body.get("severity") or "HIGH"),
        ),
        message="职责分离规则已创建",
    )


@router.post("/system/sod/check", summary="检查一组角色是否触犯职责分离")
def check_sod_conflict(body: dict = Body(...), user=Depends(require_any_permission(
        "systemAdmin.access.explain", "systemAdmin.role.view"))):
    from app.services import policy_decision_service as svc

    return success(
        svc.check_sod(int(body.get("subjectUserId") or 0), body.get("roleCodes") or [])
    )


@router.get("/system/emergency-sessions", summary="紧急访问会话列表")
def list_emergency_sessions(user=Depends(require_any_permission(
        "systemAdmin.security.view", "systemAdmin.audit.view"))):
    from app.services import policy_decision_service as svc

    return success(svc.list_emergency())


@router.post("/system/emergency-sessions", summary="开通紧急访问（必须有工单号与到期时间）")
def grant_emergency_session(
    body: dict = Body(...), user=Depends(require_permission("systemAdmin.security.manage"))
):
    from app.services import policy_decision_service as svc

    return success(
        svc.grant_emergency(
            subject_user_id=int(body.get("subjectUserId") or 0),
            granted_role_code=str(body.get("grantedRole") or ""),
            ticket_ref=str(body.get("ticketRef") or ""),
            reason=str(body.get("reason") or ""),
            minutes=int(body.get("minutes") or 60),
        ),
        message="紧急访问已开通，到期自动失效",
    )


@router.post("/system/emergency-sessions/{session_code}/revoke", summary="提前收回紧急访问")
def revoke_emergency_session(
    session_code: str, body: dict = Body(default={}),
    user=Depends(require_permission("systemAdmin.security.manage")),
):
    from app.services import policy_decision_service as svc

    return success(
        svc.revoke_emergency(session_code, reason=str(body.get("reason") or "")), message="紧急访问已收回"
    )


@router.get("/system/access-reviews", summary="权限复核活动列表")
def list_access_reviews(user=Depends(require_any_permission(
        "systemAdmin.access.explain", "systemAdmin.role.view"))):
    from app.services import policy_decision_service as svc

    return success(svc.list_campaigns())


@router.post("/system/access-reviews", summary="发起一轮权限复核")
def create_access_review(body: dict = Body(...), user=Depends(require_permission("systemAdmin.security.manage"))):
    from app.services import policy_decision_service as svc

    return success(
        svc.create_campaign(
            title=str(body.get("title") or ""),
            role_codes=body.get("roleCodes") or [],
            due_at=_calendar_dt(body.get("dueAt"), "dueAt", required=False),
        ),
        message="复核活动已创建",
    )


@router.get("/system/access-reviews/{campaign_id}", summary="复核活动详情与明细")
def get_access_review(campaign_id: int, user=Depends(require_any_permission(
        "systemAdmin.access.explain", "systemAdmin.role.view"))):
    from app.services import policy_decision_service as svc

    return success(svc.get_campaign(campaign_id))


@router.post("/system/access-reviews/{campaign_id}/items", summary="向复核活动追加待复核条目")
def add_access_review_item(
    campaign_id: int, body: dict = Body(...), user=Depends(require_permission("systemAdmin.security.manage"))
):
    from app.services import policy_decision_service as svc

    return success(
        svc.add_review_item(
            campaign_id,
            subject_user_id=int(body.get("subjectUserId") or 0),
            role_code=str(body.get("roleCode") or ""),
        )
    )


@router.post("/system/access-reviews/items/{item_id}/decide", summary="给出复核结论（调整/回收须关联安全变更）")
def decide_access_review_item(
    item_id: int, body: dict = Body(...), user=Depends(require_permission("systemAdmin.security.manage"))
):
    from app.services import policy_decision_service as svc

    return success(
        svc.decide_review_item(
            item_id,
            decision=str(body.get("decision") or ""),
            note=str(body.get("note") or ""),
            follow_up_change_set_id=body.get("followUpChangeSetId"),
        ),
        message="复核结论已记录",
    )


@router.post("/system/access-reviews/{campaign_id}/close", summary="关闭复核（有未处理条目时拒绝）")
def close_access_review(campaign_id: int, user=Depends(require_permission("systemAdmin.security.manage"))):
    from app.services import policy_decision_service as svc

    return success(svc.close_campaign(campaign_id), message="复核已关闭")
