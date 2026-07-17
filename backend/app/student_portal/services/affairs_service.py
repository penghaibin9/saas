"""学生 PC 门户 · 学工事务（第4期）。

学工学生自视图已在 mobile_affairs_service（aff：leave_my/funding_my/aid_my/discipline_my/
overview_my，均经 aff._me 收口本人+非学生403）。学生写入口为 campus_service_apply（通用事务申请：
请假/咨询/工单）。本刀 PC 接出：学工自视图聚合 + 通用事务申请 + 打印回执/请假条。
（困难认定长表+批量材料+承诺书签署 见后续专卡。）
"""
from __future__ import annotations

from app.services import mobile_affairs_service as aff
from app.services import mobile_student_service as stu
from app.services.mobile_student_service import _require_student
from app.student_portal.services import common_service as common


def overview(user: dict) -> dict:
    """学工总览（本人）。"""
    return aff.overview_my(user)


def leave(user: dict) -> dict:
    """我的请假（本人）。"""
    return aff.leave_my(user)


def funding(user: dict) -> dict:
    """我的奖助勤贷补申请（本人）。"""
    return aff.funding_my(user)


def aid(user: dict) -> dict:
    """我的困难资助等级（本人）。"""
    return aff.aid_my(user)


def discipline(user: dict) -> dict:
    """我的违纪处分（本人·仅数量，明细不在自助端）。"""
    return aff.discipline_my(user)


def service_apply(user: dict, body: dict) -> dict:
    """通用学工事务申请（请假/咨询/工单，复用现有学生写入口 campus_service_apply）。"""
    return stu.campus_service_apply(user, body or {})


def print_doc(user: dict, body: dict) -> dict:
    """打印学工回执/请假条（PORTAL_PRINT + 水印）。"""
    _require_student(user)
    body = body or {}
    biz_type = str(body.get("bizType") or "AFFAIRS").strip().upper()
    doc_name = str(body.get("docName") or "学工申请回执")
    return common.print_log(user, {"bizType": biz_type,
                                   "bizId": str(body.get("bizId") or ""), "docName": doc_name})
