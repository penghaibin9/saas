"""岗位实习 P2 服务统一数据范围入口。"""
from sqlalchemy import select

from app.core.exceptions import no_permission, not_found
from app.models import InternshipRecord, StudentProfile
from app.services.db_service import _as_id, _tid


_ORG_SCOPE_ROLES = {"COLLEGE_ADMIN", "GD_COLLEGE_ADMIN", "GD_MAJOR_ADMIN"}
_ORG_SCOPE_CLAIMS = ("collegeIds", "majorIds", "classIds", "studentIds")
ADVISOR_SCOPE_ROLES = {
    "INTERN_MENTOR", "INTERNSHIP_MENTOR", "INTERN_ADVISOR", "GD_MENTOR", "MENTOR",
}


def resolve_internship_scope(user=None) -> dict:
    """优先使用认证层签名的稳定角色范围；未配置时兼容旧教师范围并默认拒绝。

    账号管理页写入 RoleAssignmentScope，登录服务只把该已生效范围签入 JWT。
    这里只消费经认证依赖传入的 claims，不接受请求体提供的范围；导师仍走专属
    advisor_user_id 边界，不可用学院/班级范围扩大本人指导范围。稳定范围存在时完全替换旧
    名称范围，避免旧授权与新授权取并集造成范围扩张。
    """
    from app.core.context import get_current_user_ctx
    from app.services.mobile_teacher_service import resolve_teacher_scope

    actor = user or get_current_user_ctx() or {}
    scope = dict(resolve_teacher_scope(actor))
    role = str(actor.get("currentRoleCode") or scope.get("roleCode") or "").upper()
    if role not in _ORG_SCOPE_ROLES or role in ADVISOR_SCOPE_ROLES:
        return scope

    trusted_ids = {}
    for claim in _ORG_SCOPE_CLAIMS:
        values = actor.get(claim) or []
        if isinstance(values, (str, int)):
            values = [values]
        ids = {int(value) for value in values
               if str(value).isascii() and str(value).isdecimal() and int(value) > 0}
        singular = {"collegeIds": "collegeId", "majorIds": "majorId",
                    "classIds": "classId", "studentIds": "studentId"}[claim]
        value = actor.get(singular)
        if value is not None and str(value).isascii() and str(value).isdecimal() and int(value) > 0:
            ids.add(int(value))
        if ids:
            trusted_ids[claim] = ids

    if not trusted_ids:
        return scope
    # Once signed, stable assignments exist, they are authoritative. Keeping a
    # legacy name-based scope alongside them would form a union and could retain
    # access to an old college after an administrator narrowed the assignment.
    scope.update({
        "studentNos": set(), "classNames": set(), "collegeNames": set(),
        "advisorUserIds": set(), "advisorNames": set(),
    })
    scope.pop("studentIds", None)
    scope.pop("classIds", None)
    scope.pop("majorIds", None)
    scope.pop("collegeIds", None)
    for claim, ids in trusted_ids.items():
        key = claim[0].lower() + claim[1:]
        scope[key] = ids
    scope["mode"] = "SCOPED"
    scope["roleCode"] = role
    scope["by"] = "ROLE_ASSIGNMENT_SCOPE"
    return scope


def _student_matches_stable_scope(db, scope: dict, student) -> bool:
    """在 Python 单记录守卫中按稳定组织主键判定（不依赖可变名称）。"""
    if student is None:
        return False
    if int(getattr(student, "id", 0) or 0) in scope.get("studentIds", set()):
        return True
    from app.core.tenant_scoped import tenant_get
    from app.models import College, Major, SchoolClass

    class_id = int(getattr(student, "class_id", 0) or 0)
    major_id = int(getattr(student, "major_id", 0) or 0)
    college_id = int(getattr(student, "college_id", 0) or 0)
    if class_id and class_id in scope.get("classIds", set()):
        return True
    cls = tenant_get(db, SchoolClass, class_id) if class_id else None
    if not major_id and cls:
        major_id = int(cls.major_id or 0)
    if major_id and major_id in scope.get("majorIds", set()):
        return True
    major = tenant_get(db, Major, major_id) if major_id else None
    if not college_id and major:
        college_id = int(major.college_id or 0)
    if college_id and college_id in scope.get("collegeIds", set()):
        return True
    return False


def _student_matches_stable_scope_preloaded(scope: dict, student, *,
                                            class_major_ids=None, major_college_ids=None,
                                            student_college_ids=None) -> bool:
    """与单记录守卫同口径，供已批量预载班级/专业关系的列表使用。"""
    if student is None:
        return False
    if int(getattr(student, "id", 0) or 0) in scope.get("studentIds", set()):
        return True
    class_id = int(getattr(student, "class_id", 0) or 0)
    major_id = int(getattr(student, "major_id", 0) or 0)
    if class_id and class_id in scope.get("classIds", set()):
        return True
    if not major_id and class_id:
        major_id = int((class_major_ids or {}).get(class_id) or 0)
    if major_id and major_id in scope.get("majorIds", set()):
        return True
    college_id = int(getattr(student, "college_id", 0) or 0)
    if not college_id and major_id:
        college_id = int((major_college_ids or {}).get(major_id) or 0)
    if not college_id:
        college_id = int((student_college_ids or {}).get(int(student.id)) or 0)
    return bool(college_id and college_id in scope.get("collegeIds", set()))


def lock_internship_record(db, internship_id) -> InternshipRecord:
    """Lock an existing tenant-scoped owner before any child first-write.

    Retain the lock in the caller's transaction; refresh pre-lock ORM state.
    This helper does not replace the caller's data-scope or student checks.
    """
    record = db.scalar(select(InternshipRecord).where(
        InternshipRecord.id == _as_id(internship_id),
        InternshipRecord.tenant_id == _tid(),
        InternshipRecord.is_deleted.is_(False),
    ).with_for_update().execution_options(populate_existing=True))
    if record is None:
        raise not_found("实习记录不存在")
    return record


def assert_internship_record_scope(db, internship_id, user, action,
                                   allow_school_admin=True, *, lock=False) -> InternshipRecord:
    rec = lock_internship_record(db, internship_id) if lock else db.get(InternshipRecord, _as_id(internship_id))
    if not rec or rec.is_deleted or rec.tenant_id != _tid():
        raise not_found("实习记录不存在")
    from app.modules.internship.services.internship_student_service import _current_scope, _rec_in_scope
    stu = db.scalar(select(StudentProfile).where(
        StudentProfile.id == rec.student_id,
        StudentProfile.tenant_id == _tid(),
        StudentProfile.is_deleted.is_(False),
    ))
    if stu is None:
        raise not_found("实习关联的学生档案不存在或不属于当前学校")
    if not _rec_in_scope(_current_scope(user), db, rec, stu):
        raise no_permission(f"该实习学生不在你的数据范围内，不能执行{action}")
    return rec


def apply_internship_record_scope(query, user):
    """在 SQL 层收敛实习记录聚合，避免先加载全租户学生再用 Python 过滤。

    学院范围必须与 legacy/Python scope 完全同口径：学生直挂学院优先，其次学生专业所属
    学院，最后按班级→专业→学院兜底。这样历史导入数据缺 college_id/major_id 时，SQL
    分页不会把本学院学生错误过滤掉。
    """
    from sqlalchemy import and_, false, func, or_, select
    from sqlalchemy.orm import aliased
    from app.models import College, Major, SchoolClass, StudentProfile
    from app.modules.internship.services.internship_student_service import _current_scope
    scope = _current_scope(user)
    if scope.get("mode") != "SCOPED":
        return query
    role = (scope.get("roleCode") or "").upper()
    advisor_roles = {"INTERN_MENTOR", "INTERNSHIP_MENTOR", "INTERN_ADVISOR", "GD_MENTOR", "MENTOR"}
    advisor_ids = [int(x) for x in scope.get("advisorUserIds", set()) if str(x).isdigit()]
    if role in advisor_roles:
        # 运行时授权只认稳定 user_id；历史只有 advisor_name 的记录必须先治理数据，
        # 不能因为同名教师存在就扩大数据范围。
        return query.where(
            InternshipRecord.advisor_user_id.in_(advisor_ids) if advisor_ids else false()
        )

    direct_major = aliased(Major)
    class_major = aliased(Major)
    direct_college = aliased(College)
    major_college = aliased(College)
    class_college = aliased(College)

    student_ids = (
        select(StudentProfile.id)
        .outerjoin(
            SchoolClass,
            and_(
                SchoolClass.id == StudentProfile.class_id,
                SchoolClass.tenant_id == StudentProfile.tenant_id,
                SchoolClass.is_deleted.is_(False),
            ),
        )
        .outerjoin(
            direct_major,
            and_(
                direct_major.id == StudentProfile.major_id,
                direct_major.tenant_id == StudentProfile.tenant_id,
                direct_major.is_deleted.is_(False),
            ),
        )
        .outerjoin(
            class_major,
            and_(
                class_major.id == SchoolClass.major_id,
                class_major.tenant_id == StudentProfile.tenant_id,
                class_major.is_deleted.is_(False),
            ),
        )
        .outerjoin(
            direct_college,
            and_(
                direct_college.id == StudentProfile.college_id,
                direct_college.tenant_id == StudentProfile.tenant_id,
                direct_college.is_deleted.is_(False),
            ),
        )
        .outerjoin(
            major_college,
            and_(
                major_college.id == direct_major.college_id,
                major_college.tenant_id == StudentProfile.tenant_id,
                major_college.is_deleted.is_(False),
            ),
        )
        .outerjoin(
            class_college,
            and_(
                class_college.id == class_major.college_id,
                class_college.tenant_id == StudentProfile.tenant_id,
                class_college.is_deleted.is_(False),
            ),
        )
        .where(
            StudentProfile.tenant_id == _tid(),
            StudentProfile.is_deleted.is_(False),
        )
    )

    student_clauses = []
    if scope.get("studentIds"):
        student_clauses.append(StudentProfile.id.in_(scope["studentIds"]))
    if scope.get("classIds"):
        student_clauses.append(StudentProfile.class_id.in_(scope["classIds"]))
    if scope.get("majorIds"):
        student_clauses.append(or_(
            StudentProfile.major_id.in_(scope["majorIds"]),
            SchoolClass.major_id.in_(scope["majorIds"]),
        ))
    if scope.get("collegeIds"):
        student_clauses.append(or_(
            StudentProfile.college_id.in_(scope["collegeIds"]),
            direct_major.college_id.in_(scope["collegeIds"]),
            class_major.college_id.in_(scope["collegeIds"]),
        ))
    if scope.get("studentNos"):
        student_clauses.append(StudentProfile.student_no.in_(scope["studentNos"]))
    if scope.get("classNames"):
        variants = set(scope["classNames"])
        variants.update(x.rstrip("班") for x in list(variants))
        variants.update(x + "班" for x in list(variants))
        student_clauses.append(SchoolClass.class_name.in_(variants))
    if scope.get("collegeNames"):
        student_clauses.append(
            func.coalesce(
                direct_college.college_name,
                major_college.college_name,
                class_college.college_name,
            ).in_(scope["collegeNames"])
        )

    clauses = []
    if student_clauses:
        clauses.append(InternshipRecord.student_id.in_(student_ids.where(or_(*student_clauses))))
    return query.where(or_(*clauses) if clauses else false())
