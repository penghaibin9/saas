"""Resolve concrete student-affairs assignees from active organization relations."""

from datetime import datetime

from sqlalchemy import case, func, or_, select

from app.core.exceptions import AppException
from app.services.db_service import _tid


_NODE_ROLES = {
    "COLLEGE_REVIEW": {"COLLEGE_ADMIN", "COLLEGE_SA"},
    "STUDENT_AFFAIRS_REVIEW": {"STUDENT_AFFAIRS", "STUDENT_AFFAIRS_ADMIN", "SA_ADMIN"},
    "SA_OFFICE_REVIEW": {"STUDENT_AFFAIRS", "STUDENT_AFFAIRS_ADMIN", "SA_ADMIN"},
    "SA_OFFICE_FINAL": {"STUDENT_AFFAIRS", "STUDENT_AFFAIRS_ADMIN", "SA_ADMIN"},
    "SCHOOL_REVIEW": {"SCHOOL_ADMIN", "STUDENT_AFFAIRS_ADMIN"},
}


def _active_user_ids_for_roles(db, role_codes: set[str]) -> list[int]:
    from app.models import Role, User, UserRole

    return [int(value) for value in db.scalars(
        select(User.id)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .where(
            User.tenant_id == _tid(),
            User.is_deleted.is_(False),
            User.status == "ACTIVE",
            UserRole.tenant_id == _tid(),
            UserRole.is_deleted.is_(False),
            UserRole.status == "ACTIVE",
            Role.tenant_id == _tid(),
            Role.is_deleted.is_(False),
            Role.status == "ACTIVE",
            Role.role_code.in_(role_codes),
        )
        .distinct()
        .order_by(User.id)
    ).all()]


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


def resolve_assignee_ids(db, node: str, *, student_id=None) -> list[int]:
    """Return active, concrete User IDs. An empty result is never a valid assignment."""
    from app.models import AffairsCounselorAssignment, TeacherStudentScope, User

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
        if not ids and school_class.counselor_id:
            ids = [int(school_class.counselor_id)]
        return [uid for uid in dict.fromkeys(ids) if db.scalar(select(User.id).where(
            User.id == uid, User.tenant_id == _tid(), User.status == "ACTIVE",
            User.is_deleted.is_(False)
        ))]

    candidates = _active_user_ids_for_roles(db, _NODE_ROLES.get(node, set()))
    if node == "COLLEGE_REVIEW":
        if not college:
            return []
        users = {u.id: u for u in db.scalars(select(User).where(
            User.tenant_id == _tid(), User.id.in_(candidates or {-1}),
            User.status == "ACTIVE", User.is_deleted.is_(False),
        )).all()}
        scoped_keys = set(db.scalars(select(TeacherStudentScope.teacher_key).where(
            TeacherStudentScope.tenant_id == _tid(),
            TeacherStudentScope.scope_type == "COLLEGE",
            TeacherStudentScope.ref_value == college.college_name,
            TeacherStudentScope.status == "ACTIVE",
            TeacherStudentScope.is_deleted.is_(False),
        )).all())
        return [
            uid for uid in candidates
            if uid in users and (str(uid) in scoped_keys or users[uid].login_name in scoped_keys)
        ]
    return candidates


def require_assignee_id(db, node: str, *, student_id=None) -> int:
    ids = resolve_assignee_ids(db, node, student_id=student_id)
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
            f"未配置受理人：{node}。请在组织任职/临时代办配置中指定有效用户",
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
