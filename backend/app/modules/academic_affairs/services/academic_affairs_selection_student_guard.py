"""P0-05/P0-11 学生选课身份与有效成绩课程口径守卫。"""
from __future__ import annotations

import json

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException

from . import academic_affairs_selection_facade as _base

_legacy = _base._legacy


def __getattr__(name):
    return getattr(_base, name)


def _load_student(db, student_no=None, student_id=None):
    """学生选课写入口只认稳定账号绑定，忽略客户端/旧调用链传入的学号。"""
    from app.services.mobile_student_identity_facade import resolve_student

    return resolve_student(db, get_current_user_ctx() or {})


def _passed_course_codes(db, student) -> set[str]:
    from app.models import AcademicGrade, AcademicStudent
    from .academic_affairs_effective_grade_policy_service import resolve_effective_grade

    academic_student = db.query(AcademicStudent).filter(
        AcademicStudent.tenant_id == _legacy._tid(),
        AcademicStudent.student_id == student.id,
        AcademicStudent.is_deleted.is_(False),
    ).first()
    if not academic_student:
        return set()
    rows = db.query(AcademicGrade).filter(
        AcademicGrade.tenant_id == _legacy._tid(),
        AcademicGrade.acad_student_id == academic_student.id,
        AcademicGrade.record_status == "ACTIVE",
        AcademicGrade.is_deleted.is_(False),
    ).all()
    return {
        str(row.course_code or "").strip().upper()
        for row in resolve_effective_grade(rows)
        if str(row.pass_status or "").upper() == "PASSED"
        and str(row.course_code or "").strip()
    }


def _validate_enroll(db, batch, course, student, my_records, add_credit, allow_reselect_closed=False):
    """沿用八条选课校验，仅把已修/先修规则改为稳定courseCode。"""
    from app.models import AaCourse, AaSelectionCourse
    from app.modules.academic_affairs.services.academic_affairs_schedule_service import _weeks_overlap
    from app.modules.academic_affairs.services.academic_affairs_status_service import is_enrolled

    if not is_enrolled(getattr(student, "student_status", None)):
        raise _legacy.no_data_scope("当前学籍状态不可选课")
    if batch.status != _legacy._BATCH_OPEN:
        if not (allow_reselect_closed and batch.status == _legacy._BATCH_CLOSED):
            raise _legacy._invalid("不在选课时间内")
    if batch.apply_scope_json:
        try:
            scope = json.loads(batch.apply_scope_json)
        except ValueError:
            scope = {}
        if scope:
            ok_grade = (not scope.get("grades")) or (student.grade in scope["grades"])
            ok_major = (not scope.get("majorIds")) or (str(student.major_id) in [str(x) for x in scope["majorIds"]])
            ok_class = (not scope.get("classIds")) or (str(student.class_id) in [str(x) for x in scope["classIds"]])
            if not (ok_grade and ok_major and ok_class):
                raise AppException("VALIDATION_ERROR", "不在本批次适用范围内")

    for record in my_records:
        if record.course_id == course.course_id and record.status in (_legacy._REC_SELECTED, _legacy._REC_LOCKED):
            raise _legacy._conflict("已选过该课程")

    target = db.query(AaCourse).filter(
        AaCourse.id == course.course_id,
        AaCourse.tenant_id == _legacy._tid(),
        AaCourse.is_deleted.is_(False),
    ).first()
    if not target:
        raise AppException("DATA_CONFLICT", "选课课程版本不存在", http_status=409)
    target_code = str(target.course_code or "").strip().upper()
    if not target_code:
        raise AppException(
            "DATA_CONFLICT",
            "课程缺少稳定courseCode，禁止用于正式选课",
            details={"courseId": str(target.id)},
            http_status=409,
        )

    passed_codes = _passed_course_codes(db, student)
    if target_code in passed_codes:
        raise AppException("VALIDATION_ERROR", "该课程已通过，不可再选（重修请走重修报名）")

    if target.prerequisite_codes_json:
        try:
            prerequisite_codes = {
                str(value).strip().upper()
                for value in (json.loads(target.prerequisite_codes_json) or [])
                if str(value).strip()
            }
        except ValueError:
            prerequisite_codes = set()
        missing_codes = prerequisite_codes - passed_codes
        if missing_codes:
            labels = {
                str(row.course_code or "").strip().upper(): row.course_name
                for row in db.query(AaCourse).filter(
                    AaCourse.tenant_id == _legacy._tid(),
                    AaCourse.course_code.in_(sorted(missing_codes)),
                    AaCourse.is_deleted.is_(False),
                ).all()
            }
            missing_labels = [f"{code} {labels.get(code, '')}".strip() for code in sorted(missing_codes)]
            raise AppException("VALIDATION_ERROR", f"未满足先修课程要求：{', '.join(missing_labels)}")

    target_slots = _legacy._task_slots(db, course.teaching_task_id)
    if target_slots:
        selected_course_ids = [
            record.selection_course_id for record in my_records
            if record.status in (_legacy._REC_SELECTED, _legacy._REC_LOCKED)
        ]
        if selected_course_ids:
            teaching_tasks = db.query(AaSelectionCourse.teaching_task_id).filter(
                AaSelectionCourse.id.in_(selected_course_ids),
                AaSelectionCourse.tenant_id == _legacy._tid(),
            ).all()
            for (task_id,) in teaching_tasks:
                for (weekday_left, slot_left, start_left, end_left, parity_left) in _legacy._task_slots(db, task_id):
                    for (weekday_right, slot_right, start_right, end_right, parity_right) in target_slots:
                        if (
                            weekday_left == weekday_right
                            and slot_left == slot_right
                            and _weeks_overlap(
                                start_left, end_left, parity_left,
                                start_right, end_right, parity_right,
                            )
                        ):
                            message = f"与已选课程上课时间冲突（周{weekday_left}第{slot_left}节）"
                            _legacy._record_conflict_reject(db, batch, course, student, message)
                            raise _legacy._conflict(message)

    max_credits = _legacy._rule(db, batch, "maxCredits", 0)
    if max_credits and max_credits > 0:
        current_credits = sum(
            float(record.credit or 0) for record in my_records
            if record.status in (_legacy._REC_SELECTED, _legacy._REC_LOCKED)
        )
        if current_credits + add_credit > float(max_credits):
            raise AppException("VALIDATION_ERROR", f"超过本批次选课学分上限 {max_credits}")
    return None


_legacy._load_student = _load_student
_legacy._passed_course_codes = _passed_course_codes
_legacy._validate_enroll = _validate_enroll
