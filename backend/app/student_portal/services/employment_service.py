"""学生 PC 门户 · 就业服务（第5期）。

就业模块现有写入口为管理端（create/update/batch_mark_destination），无学生自助去向登记。
按"不伪造/不新建重复表"原则：查看复用 employment_my；学生去向登记走通用事务申请通道
（campus_service_apply serviceKey=EMPLOYMENT_DESTINATION，结构化文本 + 材料另经 POST /files），
由就业管理端处理入库。就业协议/回执打印走 common.print_log。
"""
from __future__ import annotations

from app.core.exceptions import AppException
from app.services import mobile_student_service as stu
from app.services.mobile_student_service import _require_student
from app.student_portal.services import common_service as common


def my(user: dict) -> dict:
    """我的就业（本人：去向/核验状态/材料/回访）。"""
    return stu.employment_my(user)


def destination_register(user: dict, body: dict) -> dict:
    """就业去向登记（本人，结构化文本经通用事务通道提交，就业管理端处理）。"""
    body = body or {}
    dtype = str(body.get("destinationType") or "").strip()
    if not dtype:
        raise AppException("VALIDATION_ERROR", "去向类型（destinationType）必填")
    unit = str(body.get("unitName") or "").strip()
    remark = str(body.get("remark") or body.get("reason") or "").strip()
    reason = f"就业去向登记｜类型:{dtype}｜单位:{unit or '—'}｜说明:{remark or '—'}"
    return stu.campus_service_apply(user, {"serviceKey": "EMPLOYMENT_DESTINATION", "reason": reason})


def destination_print(user: dict, body: dict) -> dict:
    """打印就业协议/回执（PORTAL_PRINT + 水印）。"""
    _require_student(user)
    return common.print_log(user, {"bizType": "EMPLOYMENT",
                                   "bizId": str((body or {}).get("bizId") or ""),
                                   "docName": "就业协议/回执"})
