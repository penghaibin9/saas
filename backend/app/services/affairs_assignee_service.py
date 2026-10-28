"""Resolve concrete student-affairs assignees from active organization relations."""

from datetime import datetime

from sqlalchemy import case, func, or_, select

from app.core.exceptions import AppException
from app.services.db_service import _tid


_NODE_ROLES = {
    "COLLEGE_REVIEW": {"COLLEGE_ADMIN", "COLLEGE_SA", "STUDENT_AFFAIRS_COLLEGE"},
    "STUDENT_AFFAIRS_REVIEW": {"STUDENT_AFFAIRS", "STUDENT_AFFAIRS_ADMIN", "SA_ADMIN"},
    "SA_OFFICE_REVIEW": {"STUDENT_AFFAIRS", "STUDENT_AFFAIRS_ADMIN", "SA_ADMIN"},
    "SA_OFFICE_FINAL": {"STUDENT_AFFAIRS", "STUDENT_AFFAIRS_ADMIN", "SA_ADMIN"},
    "SCHOOL_REVIEW": {"SCHOOL_ADMIN", "STUDENT_AFFAIRS_ADMIN"},
    # SP-E02/E04：就业去向登记单节点审核，无 TeacherStudentScope 式的院系/班级范围
    # 概念（就业老师按学校配置的岗位任职覆盖全校），落到角色候选池即可，不做
    # COLLEGE_REVIEW 式的二次地理收敛。
    "EMPLOYMENT_TEACHER_REVIEW": {"EMPLOYMENT_TEACHER"},
}


def _active_user_ids_for_roles(db, role_codes: set[str]) -> list[int]:
    from app.models import Role, UserRole
    from app.services.role_assignment_scope_service import active_role_membership_query
    query = active_role_membership_query(_tid()).with_only_columns(UserRole.user_id).where(
        Role.role_code.in_(role_codes),
    ).distinct().order_by(UserRole.user_id)
    return [int(value) for value in db.scalars(query).all()]


def _student_org(db, student_id):
    from app.models import College, Major, SchoolClass, StudentProfile

    student = db.get(StudentProfile, int(student_id)) if student_id else None
    if not student or student.tenant_id != _tid() or student.is_deleted:
        return None, None, None
    school_class = db.get(SchoolClass, student.class_id) if student.class_id else None
    college_id = student.college_id
    if not college_id and school_class:
        major = db.get(Major, school_class.major_id)
        college_id = major.college_id if major else None
    college = db.get(College, college_id) if college_id else None
    return student, school_class, college


def resolve_assignee_ids(db, node: str, *, student_id=None, role_codes: set[str] | None = None) -> list[int]:
    """Return active, concrete User IDs. An empty result is never a valid assignment.

    ``role_codes`` is an explicit domain override for a shared node name.  When omitted,
    the historical shared-node mapping remains authoritative, so one domain cannot widen
    or narrow another domain merely because both happen to call the node SCHOOL_REVIEW.
    """
    from app.models import AffairsCounselorAssignment, Role, TeacherStudentScope, User, UserRole

    student, school_class, college = _student_org(db, student_id)
    if node in {"COUNSELOR_REVIEW", "CLASS_REVIEW"}:
        if not school_class:
            return []
        now = datetime.utcnow()
        priority = case(
            (AffairsCounselorAssignment.duty_type == "TEMP", 0),
            (AffairsCounselorAssignment.duty_type == "PRIMARY", 1),
            (AffairsCounselorAssignment.duty_type == "CO", 2),
            else_=3,
        )
        ids = [int(value) for value in db.scalars(select(AffairsCounselorAssignment.user_id).where(
            AffairsCounselorAssignment.tenant_id == _tid(),
            AffairsCounselorAssignment.class_id == school_class.id,
            AffairsCounselorAssignment.status == "ACTIVE",
            AffairsCounselorAssignment.is_deleted.is_(False),
            AffairsCounselorAssignment.effective_from <= now,
            or_(
                AffairsCounselorAssignment.effective_to.is_(None),
                AffairsCounselorAssignment.effective_to > now,
            ),
        ).order_by(priority, AffairsCounselorAssignment.id)).all()]
        has_formal_assignment = db.scalar(select(AffairsCounselorAssignment.id).where(
            AffairsCounselorAssignment.tenant_id == _tid(),
            AffairsCounselorAssignment.class_id == school_class.id,
        ).limit(1)) is not None
        if not ids and not has_formal_assignment and school_class.counselor_id:
            ids = [int(school_class.counselor_id)]
        from app.services.role_assignment_scope_service import active_role_membership_query
        valid = set(db.scalars(active_role_membership_query(_tid()).with_only_columns(UserRole.user_id).where(
            Role.role_code == "COUNSELOR", UserRole.user_id.in_(ids or {-1}),
        )).all())
        ids = [uid for uid in dict.fromkeys(ids) if uid in valid]
        if ids and not has_formal_assignment:
            from app.core.affairs_security import build_affairs_context
            actor = db.get(User, ids[0])
            try:
                build_affairs_context({"userId": str(actor.id), "loginName": actor.login_name,
                    "currentRoleCode": "COUNSELOR", "tenantId": str(_tid())}, db).require_student(db, student.id)
            except AppException:
                return []
        return ids

    candidate_roles = set(role_codes) if role_codes is not None else _NODE_ROLES.get(node, set())
    if node == "COLLEGE_REVIEW":
        if not college:
            return []
        from sqlalchemy import String, and_, cast
        from app.models import Role, RoleAssignmentScope, UserRole
        from app.services.role_assignment_scope_service import active_assignment_scope_query, active_role_membership_query, resolve_legacy_scope_ids
        explicit = active_assignment_scope_query(_tid()).with_only_columns(RoleAssignmentScope.user_id).where(
            RoleAssignmentScope.role_code.in_(candidate_roles),
            RoleAssignmentScope.scope_type == "COLLEGE", RoleAssignmentScope.scope_id == college.id,
        )
        legacy = active_role_membership_query(_tid()).join(TeacherStudentScope, and_(
            TeacherStudentScope.tenant_id == UserRole.tenant_id,
            func.upper(TeacherStudentScope.role_code).collate("utf8mb4_unicode_ci") == Role.role_code,
            or_(TeacherStudentScope.teacher_key.collate("utf8mb4_unicode_ci") == User.login_name,
                TeacherStudentScope.teacher_key.collate("utf8mb4_unicode_ci") == cast(User.id, String),
                TeacherStudentScope.teacher_key.collate("utf8mb4_unicode_ci") == func.concat("db-", cast(User.id, String))),
        )).with_only_columns(UserRole.user_id).where(
            Role.role_code.in_(candidate_roles), TeacherStudentScope.scope_type == "COLLEGE",
            TeacherStudentScope.ref_value == college.college_name, TeacherStudentScope.status == "ACTIVE",
            TeacherStudentScope.is_deleted.is_(False),
            ~select(RoleAssignmentScope.id).where(
                RoleAssignmentScope.tenant_id == UserRole.tenant_id,
                RoleAssignmentScope.user_id == UserRole.user_id,
                RoleAssignmentScope.role_code == Role.role_code,
            ).correlate(UserRole, Role).exists(),
        )
        legacy_ids = set(db.scalars(legacy).all()) if college.id in resolve_legacy_scope_ids(
            db, tenant_id=_tid(), scope_type="COLLEGE", values={college.college_name},
        ) else set()
        return sorted(set(db.scalars(explicit).all()) | legacy_ids)
    if node in {"SCHOOL_REVIEW", "STUDENT_AFFAIRS_REVIEW", "SA_OFFICE_REVIEW", "SA_OFFICE_FINAL"}:
        scoped_roles = candidate_roles & {"FUNDING_TEACHER", "STUDENT_AFFAIRS"}
        if scoped_roles:
            from app.models import RoleAssignmentScope
            from app.services.role_assignment_scope_service import active_assignment_scope_query
            explicit = active_assignment_scope_query(_tid()).with_only_columns(RoleAssignmentScope.user_id).where(
                RoleAssignmentScope.role_code.in_(scoped_roles), RoleAssignmentScope.scope_type == "SCHOOL",
            )
            fixed = _active_user_ids_for_roles(db, candidate_roles - scoped_roles)
            return sorted(set(fixed) | set(db.scalars(explicit).all()))
    return _active_user_ids_for_roles(db, candidate_roles)


def completed_review_actor_ids(db, instance_id: int, node_codes) -> set[int]:
    """回避依据为实际办理人；历史缺失身份时保留在办单等待核验。"""
    from app.models import WorkflowTask
    nodes = set(node_codes)
    rows = list(db.scalars(select(WorkflowTask).where(
        WorkflowTask.tenant_id == _tid(), WorkflowTask.instance_id == int(instance_id or 0),
        WorkflowTask.node_code.in_(nodes), WorkflowTask.acted_at.is_not(None),
        WorkflowTask.status.in_(("APPROVED", "REJECTED", "TRANSFERRED")),
        WorkflowTask.is_deleted.is_(False),
    )).all())
    rows = [row for row in rows if not (row.status == "TRANSFERRED"
                                        and str(row.remark or "").startswith("TRANSFER_TO:"))]
    if not nodes <= {row.node_code for row in rows if row.status == "APPROVED"} or any(
            not row.updated_by or int(row.updated_by) <= 0 for row in rows):
        raise AppException("DATA_CONFLICT", "前序实际评审人记录不完整，请先核验交接；申请与材料已保留")
    return {int(row.updated_by) for row in rows}


def require_assignee_id(db, node: str, *, student_id=None, role_codes: set[str] | None = None,
                        exclude_user_ids=()) -> int:
    ids = resolve_assignee_ids(db, node, student_id=student_id, role_codes=role_codes)
    excluded = set(exclude_user_ids)
    ids = [uid for uid in ids if uid not in excluded]
    if not ids:
        from app.services.db_service import audit_insert
        audit_insert(
            "CONFIG_ANOMALY",
            "student-affairs:assignee",
            {"node": node, "studentId": str(student_id or ""), "tenantId": str(_tid())},
            "FAILED",
        )
        raise AppException(
            "ASSIGNEE_NOT_CONFIGURED",
            "未配置受理人：" + {
                "COUNSELOR_REVIEW": "辅导员审核", "CLASS_REVIEW": "班级评议",
                "COLLEGE_REVIEW": "学院审核", "SCHOOL_REVIEW": "学校审核",
                "STUDENT_AFFAIRS_REVIEW": "校学工审核", "SA_OFFICE_REVIEW": "校学工审核",
                "SA_OFFICE_FINAL": "校学工终审", "EMPLOYMENT_TEACHER_REVIEW": "就业审核",
            }.get(node, "当前审批环节") + "。请核验任职、范围和不同人审核要求后重新指派",
        )
    from app.models import UnifiedTodo
    loads = dict(db.execute(
        select(UnifiedTodo.assignee_id, func.count(UnifiedTodo.id))
        .where(
            UnifiedTodo.tenant_id == _tid(),
            UnifiedTodo.source_module == "student-affairs",
            UnifiedTodo.assignee_id.in_(ids),
            UnifiedTodo.status == "PENDING",
            UnifiedTodo.is_deleted.is_(False),
        )
        .group_by(UnifiedTodo.assignee_id)
    ).all())
    strategy = "LEAST_PENDING"
    try:
        from app.services import effective_config_service
        configured = effective_config_service.resolve("AFFAIRS_ASSIGNEE_STRATEGY").get("value")
        if str(configured or "").upper() in {"LEAST_PENDING", "FIRST_ACTIVE"}:
            strategy = str(configured).upper()
    except Exception:
        pass
    if strategy == "FIRST_ACTIVE":
        return min(ids)
    # 默认最小负载优先，同负载按 user_id 稳定排序。
    return min(ids, key=lambda uid: (int(loads.get(uid, 0)), int(uid)))
