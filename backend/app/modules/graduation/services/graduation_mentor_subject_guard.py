"""包 9：毕业设计导师稳定主体类型守卫。

毕业设计统一导师主档以 GraduationMentor.id 为稳定主体，mentor_type 区分校内、
企业与双导师。本守卫保留统一主档，同时确保请求字段和主体类型严格匹配：
mentorId 仅可指向 INTERNAL/DUAL，externalAdvisorId 仅可指向 ENTERPRISE/DUAL。
"""
from __future__ import annotations

from app.core.exceptions import AppException
from app.modules.graduation.services import graduation_mentor_service as mentor_service

_INSTALLED = False
_PREVIOUS_GET_MENTOR = None


def _stable_reference(raw_id, subject_type: str, field_name: str) -> str:
    value = str(raw_id or "").strip()
    if not value.isdigit() or int(value) <= 0:
        raise AppException("VALIDATION_ERROR", f"{field_name} 必须是有效的稳定主体 ID")
    return f"{subject_type}:{int(value)}"


def normalize_assignment_item(item: dict) -> dict:
    if not isinstance(item, dict):
        raise AppException("VALIDATION_ERROR", "导师分配项必须是对象")
    allowed = {"gdStudentId", "mentorId", "externalAdvisorId", "reason"}
    unknown = sorted(set(item) - allowed)
    if unknown:
        raise AppException(
            "VALIDATION_ERROR",
            "导师分配只接受稳定主体 ID",
            details={"unknownFields": unknown},
        )
    student_id = str(item.get("gdStudentId") or "").strip()
    mentor_id = str(item.get("mentorId") or "").strip()
    external_id = str(item.get("externalAdvisorId") or "").strip()
    if not student_id or not student_id.isdigit() or int(student_id) <= 0:
        raise AppException("VALIDATION_ERROR", "gdStudentId 必须是有效的稳定主体 ID")
    if bool(mentor_id) == bool(external_id):
        raise AppException(
            "VALIDATION_ERROR",
            "mentorId 与 externalAdvisorId 必须且只能提供一个",
        )
    if mentor_id:
        subject_ref = _stable_reference(mentor_id, "INTERNAL", "mentorId")
    else:
        subject_ref = _stable_reference(external_id, "EXTERNAL", "externalAdvisorId")
    return {
        "gdStudentId": str(int(student_id)),
        "mentorId": subject_ref,
        "reason": item.get("reason"),
    }


def _get_typed_mentor(db, mentor_ref):
    value = str(mentor_ref or "").strip()
    if ":" not in value:
        # 兼容服务层内部与历史迁移脚本的稳定数值 ID；所有正式 HTTP 分配请求
        # 已由 DTO 或批量守卫转为带主体类型的引用。
        return _PREVIOUS_GET_MENTOR(db, value)

    subject_type, raw_id = value.split(":", 1)
    subject_type = subject_type.upper()
    if subject_type not in {"INTERNAL", "EXTERNAL"}:
        raise AppException("VALIDATION_ERROR", "导师主体类型无效")
    mentor = _PREVIOUS_GET_MENTOR(db, raw_id)
    mentor_type = str(mentor.mentor_type or "").upper()
    allowed_types = {"INTERNAL", "DUAL"} if subject_type == "INTERNAL" else {"ENTERPRISE", "DUAL"}
    if mentor_type not in allowed_types:
        requested_field = "mentorId" if subject_type == "INTERNAL" else "externalAdvisorId"
        raise AppException(
            "VALIDATION_ERROR",
            "导师主体类型与请求字段不匹配",
            details={
                "requestedField": requested_field,
                "mentorId": str(mentor.id),
                "mentorType": mentor_type,
            },
        )
    return mentor


def _batch_assign(assignments: list[dict]) -> dict:
    result = {"assigned": 0, "skipped": 0, "details": []}
    for item in assignments or []:
        try:
            normalized = normalize_assignment_item(item)
            assigned = mentor_service.assign_mentor(
                normalized["gdStudentId"],
                normalized["mentorId"],
                normalized.get("reason"),
            )
            result["assigned"] += 1
            result["details"].append({
                "gdStudentId": normalized["gdStudentId"],
                "ok": True,
                "mentorName": assigned["mentorName"],
            })
        except AppException as exc:
            result["skipped"] += 1
            result["details"].append({
                "gdStudentId": str(item.get("gdStudentId") or "") if isinstance(item, dict) else "",
                "ok": False,
                "reason": exc.message,
            })
    return result


def install() -> None:
    global _INSTALLED, _PREVIOUS_GET_MENTOR
    if _INSTALLED:
        return
    _PREVIOUS_GET_MENTOR = mentor_service._get_mentor
    mentor_service._get_mentor = _get_typed_mentor
    mentor_service.batch_assign = _batch_assign
    _INSTALLED = True
