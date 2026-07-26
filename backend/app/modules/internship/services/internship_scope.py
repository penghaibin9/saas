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
    """在 SQL 层收敛实习记录聚合，避免先加载全租户学生再用 Python 过滤。"""
    from sqlalchemy import false, or_, select
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

    student_ids = select(StudentProfile.id).outerjoin(
        SchoolClass, SchoolClass.id == StudentProfile.class_id).outerjoin(
        Major, Major.id == StudentProfile.major_id).outerjoin(
        College, College.id == StudentProfile.college_id)
    clauses = []
    if scope.get("studentNos"):
        clauses.append(StudentProfile.student_no.in_(scope["studentNos"]))
    if scope.get("classNames"):
        variants = set(scope["classNames"])
        variants.update(x.rstrip("班") for x in list(variants))
        variants.update(x + "班" for x in list(variants))
        clauses.append(SchoolClass.class_name.in_(variants))
    if scope.get("collegeNames"):
        clauses.append(College.college_name.in_(scope["collegeNames"]))
    if advisor_names:
        clauses.append(InternshipRecord.advisor_name.in_(advisor_names))
    return query.where(
        or_(InternshipRecord.student_id.in_(student_ids.where(or_(*clauses))),
            InternshipRecord.advisor_name.in_(advisor_names))
        if clauses or advisor_names else false())
