"""角色成员五级范围的校验、读写与展示。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select

from app.core.exceptions import AppException

NODE_SCOPE_TYPES = {"SCHOOL", "COLLEGE", "MAJOR", "CLASS", "STUDENT"}
_SCOPE_LABELS = {
    "SCHOOL": "学校", "COLLEGE": "学院", "MAJOR": "专业",
    "CLASS": "班级", "STUDENT": "学生",
}
_POLICY_MAP = {
    "SCHOOL": ("NODE", "SCHOOL"),
    "TENANT": ("NODE", "SCHOOL"),
    "TENANT_ALL": ("NODE", "SCHOOL"),
    "COLLEGE": ("NODE", "COLLEGE"),
    "MAJOR": ("NODE", "MAJOR"),
    "CLASS": ("NODE", "CLASS"),
    "COUNSELOR_CLASSES": ("NODE", "CLASS"),
    "STUDENT": ("NODE", "STUDENT"),
    "PSY_STUDENT": ("NODE", "STUDENT"),
    "TEMP_AUTH": ("FLEX", "STUDENT"),
    "CUSTOM": ("FLEX", "COLLEGE"),
    "ASSIGNED": ("FLEX", "COLLEGE"),
}
_AUTOMATIC_LABELS = {
    "SELF": "仅本人，无需另选范围",
    "COURSE": "按本人授课任务自动确定",
    "GD_STUDENTS": "按毕业设计指导关系自动确定",
    "INTERN_STUDENTS": "按实习指导关系自动确定",
    "DORM_BUILDING": "按负责宿舍楼栋自动确定",
    "FUNDING_BIZ": "按资助业务关系自动确定",
    "DEPARTMENT": "按教职工部门任职关系自动确定",
}
_ROLE_AUTOMATIC_LABELS = {
    # 这些预设角色虽然历史 scopeCode 为 ASSIGNED，但“分配”来自业务事实，
    # 不能在账号页手工扩成学院/专业/班级/学生范围。
    "ACADEMIC_TEACHER": "按本人授课与教学任务自动确定",
    "GD_REVIEWER": "按毕业设计评阅任务自动确定",
    "GD_DEFENSE_SECRETARY": "按答辩组秘书关系自动确定",
    "GD_DEFENSE_EXPERT": "按答辩组专家关系自动确定",
}


def _actor_id(user: dict | None) -> int | None:
    raw = str((user or {}).get("userId") or "").replace("db-", "")
    return int(raw) if raw.isdigit() else None


def _raw_role_scope(db, role) -> str:
    from app.models import DataScopeRule
    row = db.scalars(select(DataScopeRule).where(
        DataScopeRule.tenant_id == int(role.tenant_id),
        DataScopeRule.role_code == role.role_code,
        DataScopeRule.status == "ACTIVE",
        DataScopeRule.is_deleted.is_(False),
    ).order_by(DataScopeRule.id.desc())).first()
    if row is not None:
        return str(row.scope_type or "ASSIGNED").strip().upper()
    marker = str(role.remark or "")
    if ";scope=" in marker:
        return marker.split(";scope=", 1)[1].split(";", 1)[0].strip().upper()
    from app.services.auth_service_db import ROLE_DEFAULT_SCOPE
    return str(ROLE_DEFAULT_SCOPE.get(role.role_code, ("ASSIGNED", ""))[0]).upper()


def role_scope_policy(db, role) -> dict:
    raw = _raw_role_scope(db, role)
    role_code = str(role.role_code or "").strip().upper()
    automatic_role_label = _ROLE_AUTOMATIC_LABELS.get(role_code)
    mode, scope_type = (
        ("AUTO", raw) if automatic_role_label else _POLICY_MAP.get(raw, ("AUTO", raw))
    )
    allowed = []
    if mode == "NODE":
        allowed = [scope_type]
    elif mode == "FLEX":
        allowed = ["COLLEGE", "MAJOR", "CLASS", "STUDENT"]
    label = (
        f"按{_SCOPE_LABELS.get(scope_type, scope_type)}授权"
        if mode in {"NODE", "FLEX"}
        else automatic_role_label or _AUTOMATIC_LABELS.get(raw, f"由 {raw} 业务关系自动确定")
    )
    return {
        "roleScopeCode": raw,
        "scopeMode": mode,
        "scopeType": scope_type,
        "allowedScopeTypes": allowed,
        "scopePolicyLabel": label,
    }


def _scope_rows(db, *, tenant_id: int, user_id: int, role_code: str):
    """Return the persisted scope inventory for the account editor.

    This is an administrative read-back, not an authorization decision.  The
    authorization paths in ``affairs_security`` and ``auth_service_db`` apply
    the effective/expiry window.  Keeping that clock filter here made a scope
    disappear intermittently immediately after commit, so an unrelated edit
    could overwrite the persisted selection with an empty one.
    """
    from app.models import RoleAssignmentScope
    return list(db.scalars(select(RoleAssignmentScope).where(
        RoleAssignmentScope.tenant_id == tenant_id,
        RoleAssignmentScope.user_id == user_id,
        RoleAssignmentScope.role_code == role_code,
        RoleAssignmentScope.status == "ACTIVE",
        RoleAssignmentScope.is_deleted.is_(False),
    ).order_by(RoleAssignmentScope.scope_type, RoleAssignmentScope.scope_name_snapshot)).all())


def assignment_payload(db, *, account, role, user_role_id: int) -> dict:
    policy = role_scope_policy(db, role)
    rows = _scope_rows(
        db, tenant_id=int(account.tenant_id), user_id=int(account.id), role_code=role.role_code,
    )
    items = [{
        "id": str(row.scope_id),
        "type": row.scope_type,
        "name": row.scope_name_snapshot or f"{row.scope_type}:{row.scope_id}",
    } for row in rows]
    scope_type = rows[0].scope_type if rows else policy["scopeType"]
    configured = policy["scopeMode"] == "AUTO" or bool(rows) or scope_type == "SCHOOL"
    return {
        "roleCode": role.role_code,
        "roleName": role.role_name,
        "userRoleId": str(user_role_id),
        **policy,
        "scopeType": scope_type,
        "scopeIds": [str(row.scope_id) for row in rows],
        "scopeItems": items,
        "scopeConfigured": configured,
    }


def _normalize_assignments(raw: Any) -> dict[str, dict]:
    result: dict[str, dict] = {}
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        code = str(item.get("roleCode") or "").strip().upper()
        if not code:
            continue
        scope_type = str(item.get("scopeType") or "").strip().upper()
        ids = []
        for value in item.get("scopeIds") or []:
            text = str(value).strip()
            if text.isdigit() and int(text) not in ids:
                ids.append(int(text))
        result[code] = {"scopeType": scope_type, "scopeIds": ids}
    return result


def _validated_nodes(db, *, tenant_id: int, scope_type: str, scope_ids: list[int]) -> dict[int, str]:
    from app.models import College, Major, SchoolClass, StudentProfile
    if scope_type == "SCHOOL":
        return {0: "全校"}
    result: dict[int, str] = {}
    if scope_type == "COLLEGE":
        rows = db.scalars(select(College).where(
            College.tenant_id == tenant_id, College.id.in_(scope_ids),
            College.status == "ACTIVE", College.is_deleted.is_(False),
        )).all()
        result = {int(row.id): row.college_name for row in rows}
    elif scope_type == "MAJOR":
        rows = db.execute(select(Major, College).join(
            College, College.id == Major.college_id
        ).where(
            Major.tenant_id == tenant_id, Major.id.in_(scope_ids),
            Major.status == "ACTIVE", Major.is_deleted.is_(False),
            College.tenant_id == tenant_id, College.status == "ACTIVE",
            College.is_deleted.is_(False),
        )).all()
        result = {int(major.id): f"{college.college_name} / {major.major_name}" for major, college in rows}
    elif scope_type == "CLASS":
        rows = db.execute(select(SchoolClass, Major, College).join(
            Major, Major.id == SchoolClass.major_id
        ).join(College, College.id == Major.college_id).where(
            SchoolClass.tenant_id == tenant_id, SchoolClass.id.in_(scope_ids),
            SchoolClass.status == "ACTIVE", SchoolClass.is_deleted.is_(False),
            Major.tenant_id == tenant_id, Major.status == "ACTIVE", Major.is_deleted.is_(False),
            College.tenant_id == tenant_id, College.status == "ACTIVE",
            College.is_deleted.is_(False),
        )).all()
        result = {
            int(school_class.id): f"{college.college_name} / {major.major_name} / {school_class.class_name}"
            for school_class, major, college in rows
        }
    elif scope_type == "STUDENT":
        rows = db.execute(select(StudentProfile, SchoolClass, Major, College).join(
            SchoolClass, SchoolClass.id == StudentProfile.class_id
        ).join(Major, Major.id == StudentProfile.major_id).join(
            College, College.id == StudentProfile.college_id
        ).where(
            StudentProfile.tenant_id == tenant_id, StudentProfile.id.in_(scope_ids),
            StudentProfile.status == "ACTIVE", StudentProfile.is_deleted.is_(False),
            SchoolClass.tenant_id == tenant_id, SchoolClass.status == "ACTIVE",
            SchoolClass.is_deleted.is_(False),
            Major.tenant_id == tenant_id, Major.status == "ACTIVE", Major.is_deleted.is_(False),
            College.tenant_id == tenant_id, College.status == "ACTIVE",
            College.is_deleted.is_(False),
        )).all()
        result = {
            int(student.id): (
                f"{student.real_name}（{student.student_no}） · "
                f"{college.college_name} / {major.major_name} / {school_class.class_name}"
            )
            for student, school_class, major, college in rows
        }
    if len(result) != len(scope_ids):
        raise AppException(
            "VALIDATION_ERROR",
            f"包含不存在、已停用、跨学校或父子链不完整的{_SCOPE_LABELS[scope_type]}范围",
        )
    return result


def _assert_actor_scope(user: dict | None, *, scope_type: str, nodes: dict[int, str], db, tenant_id: int) -> None:
    actor_scope = str((user or {}).get("dataScope") or "").upper()
    actor_role = str((user or {}).get("currentRoleCode") or "").upper()
    if actor_role in {"SCHOOL_ADMIN", "SYS_ADMIN"} or actor_scope in {"SCHOOL", "TENANT", "TENANT_ALL"}:
        return
    from app.models import Major, SchoolClass, StudentProfile
    college_ids = {int(x) for x in (user or {}).get("collegeIds") or [] if str(x).isdigit()}
    major_ids = {int(x) for x in (user or {}).get("majorIds") or [] if str(x).isdigit()}
    class_ids = {int(x) for x in (user or {}).get("classIds") or [] if str(x).isdigit()}
    student_ids = {int(x) for x in (user or {}).get("studentIds") or [] if str(x).isdigit()}
    ids = set(nodes)
    if scope_type == "COLLEGE" and ids <= college_ids:
        return
    if scope_type == "MAJOR":
        if ids <= major_ids:
            return
        parents = set(db.scalars(select(Major.college_id).where(
            Major.tenant_id == tenant_id, Major.id.in_(ids))).all())
        if parents and parents <= college_ids:
            return
    if scope_type == "CLASS":
        if ids <= class_ids:
            return
        rows = db.execute(select(SchoolClass.id, Major.id, Major.college_id).join(
            Major, Major.id == SchoolClass.major_id
        ).where(SchoolClass.tenant_id == tenant_id, SchoolClass.id.in_(ids))).all()
        if rows and all(int(major_id) in major_ids or int(college_id) in college_ids
                        for _, major_id, college_id in rows):
            return
    if scope_type == "STUDENT":
        if ids <= student_ids:
            return
        rows = db.execute(select(
            StudentProfile.id, StudentProfile.class_id, StudentProfile.major_id, StudentProfile.college_id
        ).where(StudentProfile.tenant_id == tenant_id, StudentProfile.id.in_(ids))).all()
        if rows and all(
            (class_id and int(class_id) in class_ids)
            or (major_id and int(major_id) in major_ids)
            or (college_id and int(college_id) in college_ids)
            for _, class_id, major_id, college_id in rows
        ):
            return
    raise AppException("NO_PERMISSION", "不能授予超出自身数据范围的组织或学生")


def sync_assignment_scopes(
    db,
    *,
    account,
    roles: list,
    links_by_role_id: dict[int, Any],
    raw_assignments: Any,
    actor: dict | None,
) -> list[dict]:
    """校验并同步所有角色范围；调用方负责事务提交。"""
    from app.models import RoleAssignmentScope
    tenant_id = int(account.tenant_id)
    supplied = _normalize_assignments(raw_assignments)
    role_codes = {str(role.role_code).upper() for role in roles}
    unknown = set(supplied) - role_codes
    if unknown:
        raise AppException("VALIDATION_ERROR", f"范围包含未选择的角色：{', '.join(sorted(unknown))}")

    existing = list(db.scalars(select(RoleAssignmentScope).where(
        RoleAssignmentScope.tenant_id == tenant_id,
        RoleAssignmentScope.user_id == int(account.id),
    ).with_for_update()).all())
    by_key = {(row.role_code, row.scope_type, int(row.scope_id)): row for row in existing}
    desired: set[tuple[str, str, int]] = set()
    result = []
    now = datetime.utcnow().replace(microsecond=0)
    actor_id = _actor_id(actor)

    for role in roles:
        code = str(role.role_code).upper()
        policy = role_scope_policy(db, role)
        item = supplied.get(code, {})
        scope_type = str(item.get("scopeType") or policy["scopeType"]).upper()
        scope_ids = list(item.get("scopeIds") or [])
        if policy["scopeMode"] == "AUTO":
            if scope_ids:
                raise AppException("VALIDATION_ERROR", f"{role.role_name} 的范围由业务关系自动确定，不能手工指定")
            result.append({"roleCode": code, **policy, "scopeIds": []})
            continue
        if scope_type not in policy["allowedScopeTypes"]:
            raise AppException("VALIDATION_ERROR", f"{role.role_name} 只允许配置：{'、'.join(policy['allowedScopeTypes'])}")
        if scope_type == "SCHOOL":
            scope_ids = [0]
        if not scope_ids:
            raise AppException("VALIDATION_ERROR", f"请为 {role.role_name} 选择{_SCOPE_LABELS.get(scope_type, '授权')}范围")
        max_count = 100 if scope_type == "STUDENT" else 20
        if len(scope_ids) > max_count:
            raise AppException("VALIDATION_ERROR", f"{role.role_name} 单次最多选择 {max_count} 个范围节点")
        nodes = _validated_nodes(
            db, tenant_id=tenant_id, scope_type=scope_type, scope_ids=scope_ids,
        )
        _assert_actor_scope(
            actor, scope_type=scope_type, nodes=nodes, db=db, tenant_id=tenant_id,
        )
        link = links_by_role_id[int(role.id)]
        for scope_id, name in nodes.items():
            key = (code, scope_type, int(scope_id))
            desired.add(key)
            row = by_key.get(key)
            if row is None:
                row = RoleAssignmentScope(
                    tenant_id=tenant_id, user_role_id=int(link.id), user_id=int(account.id),
                    role_code=code, scope_type=scope_type, scope_id=int(scope_id),
                    scope_name_snapshot=name, source_type="MANUAL", status="ACTIVE",
                    effective_at=now, granted_by=actor_id, reason="编辑账号角色授权",
                    created_by=actor_id, updated_by=actor_id,
                )
                db.add(row)
            else:
                row.user_role_id = int(link.id)
                row.scope_name_snapshot = name
                row.status = "ACTIVE"
                row.is_deleted = False
                row.expires_at = None
                row.updated_by = actor_id
                row.version = int(row.version or 0) + 1
        result.append({
            "roleCode": code, **policy, "scopeType": scope_type,
            "scopeIds": [str(value) for value in nodes],
        })

    for row in existing:
        key = (str(row.role_code).upper(), str(row.scope_type).upper(), int(row.scope_id))
        if key not in desired:
            row.status = "REVOKED"
            row.is_deleted = True
            row.updated_by = actor_id
            row.version = int(row.version or 0) + 1
    db.flush()
    return result


def revoke_removed_role_scopes(
    db, *, tenant_id: int, user_id: int, active_role_codes: set[str], actor: dict | None
) -> None:
    """兼容旧客户端：即使未提交范围，也要随角色移除同步撤销其范围。"""
    from app.models import RoleAssignmentScope
    actor_id = _actor_id(actor)
    rows = db.scalars(select(RoleAssignmentScope).where(
        RoleAssignmentScope.tenant_id == tenant_id,
        RoleAssignmentScope.user_id == user_id,
        RoleAssignmentScope.status == "ACTIVE",
        RoleAssignmentScope.is_deleted.is_(False),
    ).with_for_update()).all()
    for row in rows:
        if str(row.role_code or "").upper() in active_role_codes:
            continue
        row.status = "REVOKED"
        row.is_deleted = True
        row.updated_by = actor_id
        row.version = int(row.version or 0) + 1
