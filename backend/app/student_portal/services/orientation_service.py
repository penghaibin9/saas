"""学生 PC 门户 · 迎新报到（第5期）。

复用 mobile_student_service 的迎新学生入口（orientation_my/collect_submit/green_channel_submit，
均经 _require_student 收口本人）。PC 补报到回执打印。
"""
from __future__ import annotations

from app.services import mobile_student_service as stu
from app.services.mobile_student_service import _require_student
from app.student_portal.services import common_service as common


def my(user: dict) -> dict:
    """我的迎新报到（本人：各环节状态 + 报到码）。"""
    return stu.orientation_my(user)


def collect(user: dict, body: dict) -> dict:
    """预报到信息采集（本人：联系电话/生源地）。"""
    return stu.orientation_collect_submit(user, body or {})


def green_channel(user: dict, body: dict) -> dict:
    """绿色通道申请（本人）。"""
    return stu.orientation_green_channel_submit(user, body or {})


def print_receipt(user: dict, body: dict) -> dict:
    """打印迎新报到回执（PORTAL_PRINT + 水印）。"""
    _require_student(user)
    return common.print_log(user, {"bizType": "ORIENTATION",
                                   "bizId": str((body or {}).get("bizId") or ""),
                                   "docName": "迎新报到回执"})
