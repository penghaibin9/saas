"""学生 PC 门户 · 毕业设计（第2期）。

第2期首刀：任务书 PC 电子确认 + 打印。复用 mobile_student_service 的 graduation_taskbook /
graduation_taskbook_confirm（本人 + 现有毕设表），签署走 PC 重活底座 common_service.sign
（以任务书快照为内容做可靠留痕），再置任务书确认态。不重复建毕设表。
"""
from __future__ import annotations

import json

from app.core.exceptions import AppException
from app.services import mobile_student_service as stu
from app.student_portal.services import common_service as common


def taskbook(user: dict) -> dict:
    """查看本人任务书（复用 graduation_taskbook）。"""
    return stu.graduation_taskbook(user)


def taskbook_sign(user: dict, body: dict) -> dict:
    """任务书 PC 电子确认：以任务书快照为内容电子签署（可靠留痕）+ 置确认态。"""
    body = body or {}
    if not bool(body.get("confirm")):
        raise AppException("VALIDATION_ERROR", "请先勾选确认后再签署任务书")
    detail = stu.graduation_taskbook(user)  # 内部 _require_student，非学生 403
    if not detail.get("hasData"):
        raise AppException("DATA_NOT_FOUND", detail.get("message") or "导师尚未下达任务书")
    # 以任务书快照为签署内容（防篡改：确认时内容与日后比对一致）
    content = json.dumps(detail, sort_keys=True, ensure_ascii=False, default=str)
    biz_id = str(detail.get("gdStudentId") or detail.get("id") or "")
    sign = common.sign(user, {"bizType": "GRADUATION_TASKBOOK", "bizId": biz_id,
                              "content": content, "confirm": True})
    confirmed = stu.graduation_taskbook_confirm(user)  # 置任务书确认态
    return {"signId": sign["signId"], "contentHash": sign["contentHash"],
            "provider": sign["provider"], "signedAt": sign["signedAt"],
            "legalEffect": sign["legalEffect"], "taskbook": confirmed}


def taskbook_print(user: dict, body: dict) -> dict:
    """任务书打印留痕（PORTAL_PRINT + 水印）。"""
    body = body or {}
    return common.print_log(user, {"bizType": "GRADUATION_TASKBOOK",
                                   "bizId": str(body.get("bizId") or ""),
                                   "docName": "毕业设计任务书"})
