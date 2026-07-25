"""结构化数据范围服务：不再以 Role.remark 作为主写入链路。

支持：SELF / COUNSELOR_CLASSES / COLLEGE / MAJOR / COURSE / GD_STUDENTS /
INTERN_STUDENTS / DORM_BUILDING / FUNDING_BIZ / PSY_STUDENT / TEMP_AUTH / CUSTOM

CUSTOM 必须指定真实目标；目标缺失默认拒绝，不得扩大为全校。
"""
from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select

from app.core.context import current_tenant_id
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker

SUPPORTED_SCOPES = {
    "SELF", "COUNSELOR_CLASSES", "COLLEGE", "MAJOR", "COURSE",
    "GD_STUDENTS", "INTERN_STUDENTS", "DORM_BUILDING", "FUNDING_BIZ",
    "PSY_STUDENT", "TEMP_AUTH", "CUSTOM",
    # 兼容历史别名
    "ASSIGNED", "CLASS", "SCHOOL", "TENANT", "TENANT_ALL",
}

_SCOPE_ALIASES = {
    "CLASS": "COUNSELOR_CLASSES",
    "SCHOOL": "TENANT",
    "TENANT_ALL": "TENANT",
    "ASSIGNED": "SELF",
}


def normalize_scope(code: str) -> str:
    raw = str(code or "SELF").strip().upper()
    if not re.fullmatch(r"[A-Z_]{2,40}", raw):
        raise AppException("VALIDATION_ERROR", "数据范围编码不合法")
    return _SCOPE_ALIASES.get(raw, raw)


def resolve_role_scope_code(role) -> str | None:
    """从 t_data_scope_rule 读取角色范围；无则 None（调用方回落 remark 只读）。"""
    try:
        from app.models import DataScopeRule
        tid = int(getattr(role, "tenant_id", 0) or current_tenant_id() or 0)
        code = getattr(role, "role_code", None)
        if not tid or not code:
            return None
        return resolve_scope_by_role_code(tid, code)
    except Exception:
        return None


def resolve_scope_by_role_code(tenant_id: int, role_code: str) -> str | None:
    """按租户+角色编码读取结构化范围。供 auth / mock_rbac 共用。"""
    from app.models import DataScopeRule
    tid = int(tenant_id or 0)
    code = str(role_code or "").strip()
    if not tid or not code:
        return None
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(DataScopeRule).where(
            DataScopeRule.tenant_id == tid,
            DataScopeRule.role_code == code,
            DataScopeRule.status == "ACTIVE",
            DataScopeRule.is_deleted.is_(False),
        ).order_by(DataScopeRule.id.desc())).first()
        if row is None:
            return None
        return normalize_scope(row.scope_type)
    finally:
        db.close()


def save_role_scope(role, scope_code: str, *, target_json: dict | None = None,
                    actor: dict | None = None, expected_version: int | None = None) -> dict:
    from app.models import DataScopeRule

    scope = normalize_scope(scope_code)
    if scope not in SUPPORTED_SCOPES and scope not in _SCOPE_ALIASES.values():
        raise AppException("VALIDATION_ERROR", f"不支持的数据范围：{scope}")
    targets = target_json if isinstance(target_json, dict) else {}
    if scope == "CUSTOM":
        college_ids = targets.get("collegeIds") or targets.get("college_ids") or []
        major_ids = targets.get("majorIds") or targets.get("major_ids") or []
        class_ids = targets.get("classIds") or targets.get("class_ids") or []
        object_ids = targets.get("objectIds") or targets.get("object_ids") or []
        if not any([college_ids, major_ids, class_ids, object_ids]):
            raise AppException("VALIDATION_ERROR", "CUSTOM 范围必须指定学院/专业/班级或对象目标，禁止扩大为全校")

    tid = int(getattr(role, "tenant_id", 0) or current_tenant_id() or 0)
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(DataScopeRule).where(
            DataScopeRule.tenant_id == tid,
            DataScopeRule.role_code == role.role_code,
            DataScopeRule.is_deleted.is_(False),
        ).order_by(DataScopeRule.id.desc())).first()
        if row is not None and expected_version is not None:
            if int(row.version or 0) != int(expected_version):
                raise AppException("DATA_CONFLICT", "数据范围已被他人修改，请刷新后重试")
        before = None
        if row is None:
            row = DataScopeRule(
                tenant_id=tid,
                rule_name=f"{role.role_code}-scope",
                role_code=role.role_code,
                scope_type=scope,
                target_json=targets or None,
                status="ACTIVE",
                remark="structured-scope",
            )
            db.add(row)
        else:
            before = {"scopeType": row.scope_type, "target": row.target_json, "version": row.version}
            row.scope_type = scope
            row.target_json = targets or None
            row.status = "ACTIVE"
            row.version = int(row.version or 0) + 1
        # 历史 remark 仅保留兼容标记，不再作为主写入（在本会话内更新 Role）
        from app.models import Role as RoleModel
        role_row = db.scalars(select(RoleModel).where(
            RoleModel.tenant_id == tid, RoleModel.role_code == role.role_code,
            RoleModel.is_deleted.is_(False))).first()
        if role_row is not None:
            remark = str(role_row.remark or "")
            remark = re.sub(r";scope=[^;]*", "", remark)
            remark = re.sub(r";permMode=[^;]*", "", remark).rstrip(";")
            role_row.remark = (remark + ";permMode=DB;scopeSource=RULE").lstrip(";")
        db.commit()
        db.refresh(row)
        from app.services import audit_log
        audit_log.record(
            "DATA_SCOPE_SAVE",
            f"role:{role.role_code}",
            detail={
                "before": before,
                "after": {"scopeType": scope, "target": targets, "version": row.version},
                "moduleCode": "systemAdmin",
                "actor": (actor or {}).get("userId"),
            },
        )
        return {"scopeCode": scope, "target": targets, "version": int(row.version or 0)}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def simulate_access(user: dict, *, resource_type: str, resource: dict,
                    sensitive: bool = False) -> dict[str, Any]:
    """数据范围模拟：返回允许/拒绝及原因。"""
    from app.core.permissions import has_permission

    role = (user or {}).get("currentRoleCode") or ""
    scope = normalize_scope((user or {}).get("dataScope") or "SELF")
    # 尝试读结构化规则
    try:
        from app.models import Role
        tid = int(current_tenant_id() or user.get("tenantId") or 0)
        db = get_sessionmaker()()
        try:
            role_row = db.scalars(select(Role).where(
                Role.tenant_id == tid, Role.role_code == role, Role.is_deleted.is_(False))).first()
            if role_row is not None:
                coded = resolve_role_scope_code(role_row)
                if coded:
                    scope = coded
        finally:
            db.close()
    except Exception:
        pass

    if sensitive and not has_permission(user, "field.view_full") and not has_permission(user, "systemAdmin.audit.sensitive.view"):
        return {"allowed": False, "reason": "缺少敏感查看权限", "scope": scope}

    providers = {
        "COLLEGE": _provider_college,
        "MAJOR": _provider_major,
        "COUNSELOR_CLASSES": _provider_counselor_classes,
        "GD_STUDENTS": _provider_gd_students,
        "INTERN_STUDENTS": _provider_intern_students,
        "SELF": _provider_self,
        "CUSTOM": _provider_custom,
        "TENANT": lambda *_a, **_k: True,
        "COURSE": _provider_course,
    }
    checker = providers.get(scope)
    if checker is None:
        return {"allowed": False, "reason": f"未知数据范围默认拒绝：{scope}", "scope": scope}
    try:
        ok = bool(checker(user, resource_type, resource))
    except AppException as exc:
        return {"allowed": False, "reason": str(exc.message if hasattr(exc, "message") else exc), "scope": scope}
    except Exception as exc:
        return {"allowed": False, "reason": f"范围校验异常：{exc}", "scope": scope}
    return {
        "allowed": ok,
        "reason": "在数据范围内" if ok else "目标不在当前数据范围",
        "scope": scope,
        "resourceType": resource_type,
    }


def _provider_self(user, resource_type, resource) -> bool:
    uid = str(user.get("userId") or "")
    owner = str(resource.get("ownerUserId") or resource.get("userId") or "")
    return bool(uid and owner and uid == owner)


def _provider_college(user, resource_type, resource) -> bool:
    allowed = set(str(x) for x in (user.get("collegeIds") or []))
    target = str(resource.get("collegeId") or "")
    if not allowed:
        return False
    return target in allowed


def _provider_major(user, resource_type, resource) -> bool:
    allowed = set(str(x) for x in (user.get("majorIds") or []))
    target = str(resource.get("majorId") or "")
    return bool(allowed) and target in allowed


def _provider_counselor_classes(user, resource_type, resource) -> bool:
    """辅导员班级关系提供器。"""
    login = str(user.get("loginName") or "")
    class_id = resource.get("classId")
    if not login or not class_id:
        return False
    from app.models import SchoolClass
    tid = int(current_tenant_id() or user.get("tenantId") or 0)
    db = get_sessionmaker()()
    try:
        row = db.scalars(select(SchoolClass).where(
            SchoolClass.tenant_id == tid, SchoolClass.id == int(class_id),
            SchoolClass.is_deleted.is_(False))).first()
        if row is None:
            return False
        return str(row.counselor_id or "") in {str(user.get("userId") or "").replace("db-", ""), login} \
            or str(row.head_teacher_id or "") == str(user.get("userId") or "").replace("db-", "")
    finally:
        db.close()


def _provider_gd_students(user, resource_type, resource) -> bool:
    student_id = resource.get("studentId")
    if not student_id:
        return False
    try:
        from app.models import GraduationStudent
        tid = int(current_tenant_id() or user.get("tenantId") or 0)
        mentor_key = str(user.get("loginName") or "")
        db = get_sessionmaker()()
        try:
            # 兼容不同字段命名
            q = select(GraduationStudent).where(
                GraduationStudent.tenant_id == tid,
                GraduationStudent.is_deleted.is_(False),
            )
            rows = db.scalars(q.limit(500)).all()
            for r in rows:
                sid = getattr(r, "student_id", None) or getattr(r, "id", None)
                mentor = getattr(r, "mentor_user_id", None) or getattr(r, "mentor_no", None) \
                    or getattr(r, "teacher_no", None)
                if str(sid) == str(student_id) and str(mentor) in {
                    mentor_key, str(user.get("userId") or "").replace("db-", "")
                }:
                    return True
            return False
        finally:
            db.close()
    except Exception:
        return False


def _provider_intern_students(user, resource_type, resource) -> bool:
    student_id = resource.get("studentId")
    if not student_id:
        return False
    try:
        from app.models import InternshipRecord
        tid = int(current_tenant_id() or user.get("tenantId") or 0)
        mentor_key = str(user.get("loginName") or "")
        uid = str(user.get("userId") or "").replace("db-", "")
        db = get_sessionmaker()()
        try:
            rows = db.scalars(select(InternshipRecord).where(
                InternshipRecord.tenant_id == tid,
                InternshipRecord.is_deleted.is_(False),
            ).limit(500)).all()
            for r in rows:
                sid = getattr(r, "student_id", None) or getattr(r, "id", None)
                mentor = getattr(r, "advisor_user_id", None) or getattr(r, "teacher_no", None) \
                    or getattr(r, "mentor_no", None) or getattr(r, "school_teacher_id", None) \
                    or getattr(r, "teacher_user_id", None)
                if str(sid) == str(student_id) and str(mentor) in {mentor_key, uid}:
                    return True
            return False
        finally:
            db.close()
    except Exception:
        return False


def _provider_course(user, resource_type, resource) -> bool:
    allowed = set(str(x) for x in (user.get("courseIds") or []))
    target = str(resource.get("courseId") or "")
    return bool(allowed) and target in allowed


def _provider_custom(user, resource_type, resource) -> bool:
    targets = user.get("customScopeTargets") or {}
    if not isinstance(targets, dict) or not targets:
        raise AppException("VALIDATION_ERROR", "CUSTOM 范围目标缺失，默认拒绝")
    for key, field in (
        ("collegeIds", "collegeId"),
        ("majorIds", "majorId"),
        ("classIds", "classId"),
        ("objectIds", "objectId"),
    ):
        allowed = {str(x) for x in (targets.get(key) or [])}
        val = resource.get(field)
        if allowed and val is not None and str(val) in allowed:
            return True
    return False
