"""包 8 第一组：校内实习导师稳定主体授权。

姓名仅作为展示快照；所有运行时授权只接受 ``InternshipRecord.advisor_user_id``
与当前登录 ``userId`` 的稳定相等关系。历史记录缺少稳定 ID 时 fail-closed，
禁止同名教师、姓名变更或伪造 realName 获得学生范围。
"""
from __future__ import annotations

from sqlalchemy import and_, false

from app.core.exceptions import AppException
from app.models import InternshipRecord
from app.modules.internship.services import internship_scope as scope_service
from app.modules.internship.services import internship_service as domain_service
from app.modules.internship.services import internship_student_service as student_service
from app.services.mobile_teacher_service import scope_match_row

_INSTALLED = False


def _user_id(user) -> int | None:
    value = (user or {}).get("userId")
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def stable_advisor_matches(record, user) -> bool:
    """唯一校内导师授权合同：record.advisor_user_id == token.userId。"""
    uid = _user_id(user)
    return bool(
        record is not None
        and uid is not None
        and getattr(record, "advisor_user_id", None) is not None
        and int(record.advisor_user_id) == uid
    )


def _advisor_condition(user):
    uid = _user_id(user)
    if uid is None:
        return false()
    return and_(
        InternshipRecord.advisor_user_id.is_not(None),
        InternshipRecord.advisor_user_id == uid,
    )


def _stable_scope_match(scope, *, student_no=None, class_name=None,
                        college_name=None, advisor_user_id=None) -> bool:
    """保留班级/学院/显式学生范围，只移除 advisor_name 授权输入。"""
    return scope_match_row(
        scope,
        student_no=student_no,
        class_name=class_name,
        advisor_name=None,
        college_name=college_name,
        advisor_user_id=advisor_user_id,
    )


def _scope_rec_in_scope(scope, db, record, student) -> bool:
    if scope.get("mode") != "SCOPED":
        return True
    if record is None:
        return False
    class_name, college_name = domain_service.resolve_student_class_college_names(
        db, student,
    )
    return _stable_scope_match(
        scope,
        student_no=student.student_no if student else None,
        class_name=class_name,
        college_name=college_name,
        advisor_user_id=record.advisor_user_id,
    )


def _domain_rec_in_scope(scope, db, record, student) -> bool:
    return _scope_rec_in_scope(scope, db, record, student)


def _domain_rec_in_scope_pre(scope, record, student, class_name_map,
                             college_name_map, stu_college_name_map=None) -> bool:
    if scope.get("mode") != "SCOPED":
        return True
    if record is None:
        return False
    class_name = college_name = None
    if student is not None:
        if getattr(student, "class_id", None):
            class_name = class_name_map.get(student.class_id)
        if stu_college_name_map is not None:
            college_name = stu_college_name_map.get(student.id)
        elif getattr(student, "college_id", None):
            college_name = college_name_map.get(student.college_id)
    return _stable_scope_match(
        scope,
        student_no=student.student_no if student else None,
        class_name=class_name,
        college_name=college_name,
        advisor_user_id=record.advisor_user_id,
    )


def _student_rec_in_scope(scope, db, record, student) -> bool:
    return _scope_rec_in_scope(scope, db, record, student)


def _stable_advisor(db, advisor_user_id=None, advisor_name=None):
    """新写入必须提交稳定账号 ID；advisorName 仅作响应展示，不可反查授权。"""
    if advisor_user_id in (None, ""):
        if (advisor_name or "").strip():
            raise AppException(
                "VALIDATION_ERROR",
                "指导教师姓名仅用于展示，分配必须提交稳定 advisorUserId",
            )
        return None
    return _ORIGINAL_ADVISOR(db, advisor_user_id, None)


_ORIGINAL_ADVISOR = student_service._advisor


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    scope_service._advisor_condition = _advisor_condition
    scope_service._rec_in_scope = _scope_rec_in_scope
    domain_service._rec_in_scope = _domain_rec_in_scope
    domain_service._rec_in_scope_pre = _domain_rec_in_scope_pre
    student_service._rec_in_scope = _student_rec_in_scope
    student_service._advisor = _stable_advisor
    _INSTALLED = True
