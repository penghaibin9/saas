"""学生 PC 门户 · 教务学业（第3期）。

教务学生自视图已很完整（mobile_academic_affairs_service：成绩单/课表/学籍/异动/选课/学分/预警/
补重修/毕业进度）。PC 门户在其上接出并叠加 PC 重活（成绩单打印、学籍异动材料+签署等）。
首刀：我的成绩 / 成绩单查看 + 打印。严格本人由 aa._me（_require_student+resolve_student）收口。
"""
from __future__ import annotations

from app.modules.academic_affairs.services import mobile_academic_affairs_service as aa
from app.student_portal.services import common_service as common


def transcript(user: dict) -> dict:
    """我的成绩单（本人已发布成绩 + GPA）。未发布不露分由教务成绩服务口径保证。"""
    return aa.transcript_my(user)


def transcript_print(user: dict, body: dict) -> dict:
    """成绩单打印留痕（PORTAL_PRINT + 水印）。"""
    body = body or {}
    return common.print_log(user, {"bizType": "TRANSCRIPT",
                                   "bizId": str(body.get("bizId") or ""),
                                   "docName": "成绩单"})
