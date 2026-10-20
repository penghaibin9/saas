from __future__ import annotations

from datetime import datetime

from app.core.exceptions import AppException
from app.services import audit_log
from app.services.db_service import _iso
from app.services.mobile_student_service import _require_student


def _watermark(user: dict) -> str:
    return str(user.get("realName") or user.get("studentNo") or "本人")


def print_log(user: dict, body: dict) -> dict:
    u = _require_student(user)
    payload = body or {}
    biz_type = str(payload.get("bizType") or "").strip()
    biz_id = str(payload.get("bizId") or "").strip()
    doc_name = str(payload.get("docName") or "").strip()
    if not biz_type:
        raise AppException("VALIDATION_ERROR", "bizType 必填")
    audit_log.record(
        "PORTAL_PRINT",
        f"{biz_type}:{biz_id}",
        {"studentNo": u.get("studentNo"), "docName": doc_name},
    )
    return {"watermark": _watermark(u), "loggedAt": _iso(datetime.utcnow())}


def export_log(user: dict, body: dict) -> dict:
    u = _require_student(user)
    payload = body or {}
    biz_type = str(payload.get("bizType") or "").strip()
    biz_id = str(payload.get("bizId") or "").strip()
    doc_name = str(payload.get("docName") or "").strip()
    if not biz_type:
        raise AppException("VALIDATION_ERROR", "bizType 必填")
    audit_log.record(
        "PORTAL_EXPORT",
        f"{biz_type}:{biz_id}",
        {"studentNo": u.get("studentNo"), "docName": doc_name},
    )
    return {"watermark": _watermark(u), "loggedAt": _iso(datetime.utcnow())}
