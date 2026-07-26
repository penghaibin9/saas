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
