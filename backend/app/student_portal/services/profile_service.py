"""学生 PC 门户 · 我的档案：学籍信息只读 + 敏感字段明文授权查看（留痕）。

复用 resolve_student 严格「本人」；学籍信息为只读展示（异动走教务学籍异动，第3期）。
敏感明文查看：本人 + 填写原因 + 审计（SENSITIVE_VIEW）+ 前端水印；不改动任何数据。
"""
from __future__ import annotations

from app.core.exceptions import AppException
from app.core.student_lifecycle import student_stage_label
from app.db.session import db_enabled
from app.services import audit_log
from app.services.db_service import (_iso, _mask_id_card, _mask_phone, _org_names,
                                     _primary_phone)
from app.services.mobile_student_service import (_require_student, _session,
                                                 resolve_student)

# 允许本人授权查看明文的敏感字段
SENSITIVE_FIELDS = {"idCard", "phone"}


def enrollment(user: dict) -> dict:
    """学籍信息（只读）。默认脱敏；明文经 /portal/profile/sensitive 单独授权。"""
    u = _require_student(user)
    if not db_enabled():
        return {"hasData": False, "note": "演示模式"}
    with _session() as db:
        stu = resolve_student(db, u)
        if not stu:
            return {"hasData": False, "note": "尚未建立你的学生档案"}
        _org_names(db, [stu])
        phone_plain = _primary_phone(db, stu.id)
        sensitive_viewable = ["idCard"] if stu.id_card_encrypted else []
        if phone_plain:
            sensitive_viewable.append("phone")
        return {
            "hasData": True,
            "studentId": str(stu.id), "studentNo": stu.student_no, "name": stu.real_name,
            "gender": stu.gender or "",
            "collegeName": getattr(stu, "_college_name", "") or "",
            "majorName": getattr(stu, "_major_name", "") or "",
            "className": getattr(stu, "_class_name", "") or "",
            "grade": stu.grade or "",
            "enrollDate": _iso(stu.enroll_date) if stu.enroll_date else "",
            "studentStatus": stu.student_status,
            "stage": stu.current_stage,
            "stageLabel": student_stage_label(stu.current_stage),
            "status": stu.status,
            "phoneMasked": _mask_phone(phone_plain) if phone_plain else "",
            "idCardMasked": _mask_id_card(stu.id_card_encrypted) if stu.id_card_encrypted else "",
            "sensitiveViewable": sensitive_viewable,
        }


def sensitive_view(user: dict, body: dict) -> dict:
    """本人授权查看某敏感字段明文（填原因 + 审计 + 前端水印）。只读，不改数据。"""
    u = _require_student(user)
    body = body or {}
    field = str(body.get("field") or "").strip()
    reason = str(body.get("reason") or "").strip()
    if field not in SENSITIVE_FIELDS:
        raise AppException("VALIDATION_ERROR", "不支持查看该字段明文")
    if len(reason) < 2:
        raise AppException("VALIDATION_ERROR", "请填写查看原因")
    if not db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持")
    with _session() as db:
        stu = resolve_student(db, u)
        if not stu:
            raise AppException("DATA_NOT_FOUND", "未找到你的学生档案")
        if field == "idCard":
            value = stu.id_card_encrypted or ""
        else:  # phone
            value = _primary_phone(db, stu.id) or ""
    if not value:
        raise AppException("DATA_NOT_FOUND", "该字段暂无数据")
    audit_log.record("SENSITIVE_VIEW", f"student-profile:{field}",
                     {"studentNo": u.get("studentNo"), "field": field, "reason": reason})
    return {"field": field, "value": value,
            "watermark": u.get("realName") or u.get("studentNo") or "本人"}
