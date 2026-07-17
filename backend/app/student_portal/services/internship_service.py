"""学生 PC 门户 · 岗位实习（第5期）。

实习学生入口在 mobile_student_service 已很完整（打卡/周报/请假/协议确认/自评/过程报告/变更）。
PC 门户接出并补 PC 重活：月报/总结长文档（复用过程报告）、三方协议打印、实习成绩申诉。
严格本人由底层 _require_student + resolve_student 收口。
"""
from __future__ import annotations

from app.core.exceptions import AppException
from app.services import mobile_student_service as stu
from app.services.mobile_student_service import _require_student
from app.student_portal.services import common_service as common


def my(user: dict) -> dict:
    """我的实习（本人）。"""
    return stu.internship_my(user)


def weekly_submit(user: dict, body: dict) -> dict:
    """实习周报提交（本人，字段校验由底层完成）。"""
    return stu.internship_weekly_submit(user, body or {})


def report_submit(user: dict, body: dict) -> dict:
    """实习月报/总结长文档提交（复用过程报告：reportType + periodKey + content 长文本）。"""
    body = body or {}
    if not str(body.get("reportType") or "").strip():
        raise AppException("VALIDATION_ERROR", "报告类型（reportType）必填")
    if not str(body.get("content") or "").strip():
        raise AppException("VALIDATION_ERROR", "报告内容不能为空")
    return stu.internship_process_report_submit(user, body)


def agreement_print(user: dict, body: dict) -> dict:
    """三方协议打印留痕（PORTAL_PRINT + 水印）。"""
    _require_student(user)
    return common.print_log(user, {"bizType": "INTERNSHIP_AGREEMENT",
                                   "bizId": str((body or {}).get("bizId") or ""),
                                   "docName": "实习三方协议"})


def score_appeal(user: dict, body: dict) -> dict:
    """实习成绩申诉（书面理由，复用通用事务申请）。"""
    body = body or {}
    reason = str(body.get("reason") or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "申诉理由至少 5 个字")
    return stu.campus_service_apply(user, {"serviceKey": "INTERNSHIP_SCORE_APPEAL", "reason": reason})
