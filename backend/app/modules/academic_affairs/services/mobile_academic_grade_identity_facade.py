"""V2-04 移动端成绩身份最终层。

重修候选、免修候选与成绩认定全部返回并消费稳定ID；禁止同名课程合并和纯文本提交。
"""
from __future__ import annotations

from app.core.exceptions import AppException

from . import mobile_academic_affairs_service as _mobile
from . import mobile_academic_gaps_service as _gaps


def _identity_options(user) -> dict:
    from app.models import AcademicGrade
    from app.modules.academic_affairs.services import academic_affairs_grade_service as grade_service

    with _mobile.session() as db:
        student = _mobile._me(db, user)
        academic_student = _gaps._best_grades_for_me(db, student)[1]
        if not academic_student:
            return {
                "retakeOptions": [], "exemptionOptions": [],
                "retakeTotal": 0, "exemptionTotal": 0,
                "identityDebtCount": 0, "note": "尚未建立学业成绩台账",
            }
        rows = db.query(AcademicGrade).filter(
            AcademicGrade.tenant_id == _mobile._tid(),
            AcademicGrade.acad_student_id == academic_student.id,
            AcademicGrade.record_status == "ACTIVE",
            AcademicGrade.is_deleted.is_(False),
        ).all()
        effective = grade_service.effective_grade_rows(rows)
        retakes, exemptions, debts = [], [], []
        for row in effective:
            identity_ready = bool(
                row.course_id and row.course_code and row.course_version and row.attempt_no
            )
            item = {
                "gradeId": str(row.id),
                "courseId": str(row.course_id or ""),
                "courseCode": row.course_code or "",
                "courseVersion": int(row.course_version or 0) or None,
                "attemptNo": int(row.attempt_no or 0) or None,
                "courseName": row.course_name,
                "termCode": row.term or "",
                "score": row.score,
                "credit": float(row.credit_value or 0),
                "passStatus": row.pass_status,
                "identityReady": identity_ready,
            }
            status = str(row.pass_status or "").upper()
            if status in {"FAIL", "FAILED"}:
                (retakes if identity_ready else debts).append(item)
                if identity_ready:
                    exemptions.append(item)
            elif status != "PASSED":
                (exemptions if identity_ready else debts).append(item)
        key = lambda item: (
            item.get("termCode") or "",
            item.get("courseCode") or "",
            int(item.get("attemptNo") or 0),
        )
        retakes.sort(key=key)
        exemptions.sort(key=key)
        return {
            "retakeOptions": retakes,
            "exemptionOptions": exemptions,
            "retakeTotal": len(retakes),
            "exemptionTotal": len(exemptions),
            "identityDebtCount": len(debts),
            "identityDebtItems": debts[:50],
            "note": (
                f"有{len(debts)}条历史成绩缺少课程身份，暂不能用于重修或免修"
                if debts else "请从稳定课程身份候选中选择"
            ),
        }


def makeup_options_my(user) -> dict:
    return _identity_options(user)


def retake_apply_my(user, body) -> dict:
    from app.modules.academic_affairs.services import academic_affairs_makeup_service as makeup

    payload = body or {}
    grade_id = payload.get("gradeId")
    if not grade_id:
        raise AppException("VALIDATION_ERROR", "请从本人当前有效挂科成绩选择gradeId")
    options = {str(item["gradeId"]): item for item in _identity_options(user)["retakeOptions"]}
    if str(grade_id) not in options:
        raise AppException("APPROVAL_VERSION_CONFLICT", "所选挂科成绩已失效，请刷新候选列表", http_status=409)
    return makeup.retake_apply(user, _mobile._ns({
        "gradeId": int(grade_id),
        "termCode": payload.get("termCode"),
        "reason": payload.get("reason"),
    }))


def exemption_apply_my(user, body) -> dict:
    from app.modules.academic_affairs.services import academic_affairs_makeup_service as makeup

    payload = body or {}
    course_id = payload.get("courseId")
    if not course_id:
        raise AppException("VALIDATION_ERROR", "请从可申请课程选择courseId")
    options = {str(item["courseId"]): item for item in _identity_options(user)["exemptionOptions"]}
    if str(course_id) not in options:
        raise AppException("APPROVAL_VERSION_CONFLICT", "所选课程已不满足免修候选条件，请刷新", http_status=409)
    return makeup.exemption_apply(user, _mobile._ns({
        "courseId": int(course_id),
        "termCode": payload.get("termCode"),
        "reason": payload.get("reason"),
        "materialFileIds": payload.get("materialFileIds") or [],
    }))


def recognition_submit_my(user, body) -> dict:
    from app.modules.academic_affairs.services import academic_affairs_recognition_service as recognition

    payload = body or {}
    if not payload.get("sourceCourseName"):
        raise AppException("VALIDATION_ERROR", "原课程名称必填")
    if not payload.get("targetCourseId"):
        raise AppException("VALIDATION_ERROR", "目标课程必须选择课程库具体targetCourseId")
    return recognition.submit(user, _mobile._ns(payload))


# 移动路由调用 legacy service；候选接口调用 gaps service。统一替换两层。
_mobile.retake_apply_my = retake_apply_my
_mobile.exemption_apply_my = exemption_apply_my
_mobile.recognition_submit_my = recognition_submit_my
_gaps.makeup_options_my = makeup_options_my
