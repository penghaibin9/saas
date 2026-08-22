"""岗位实习 P2 服务统一数据范围入口。"""
from app.core.exceptions import no_permission, not_found
from app.models import InternshipRecord, StudentProfile
from app.services.db_service import _as_id, _tid


def assert_internship_record_scope(db, internship_id, user, action,
                                   allow_school_admin=True) -> InternshipRecord:
    rec = db.get(InternshipRecord, _as_id(internship_id))
    if not rec or rec.is_deleted or rec.tenant_id != _tid():
        raise not_found("实习记录不存在")
    from app.modules.internship.services.internship_student_service import _current_scope, _rec_in_scope
    stu = db.get(StudentProfile, rec.student_id)
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
    advisor_roles = {"INTERN_MENTOR", "INTERNSHIP_MENTOR", "INTERN_ADVISOR"}
    advisor_ids = [int(x) for x in scope.get("advisorUserIds", set()) if str(x).isdigit()]
    advisor_names = list(scope.get("advisorNames", set()))
    if role in advisor_roles:
        clauses = []
        if advisor_ids:
            clauses.append(InternshipRecord.advisor_user_id.in_(advisor_ids))
        if advisor_names:
            clauses.append(
                InternshipRecord.advisor_user_id.is_(None)
                & InternshipRecord.advisor_name.in_(advisor_names))
        return query.where(or_(*clauses) if clauses else false())

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
    if advisor_names:
        clauses.append(InternshipRecord.advisor_name.in_(advisor_names))
    return query.where(or_(*clauses) if clauses else false())
