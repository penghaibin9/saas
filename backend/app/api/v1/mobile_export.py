"""学生个人数据导出（本人·只读聚合）。

GET /mobile/me/export-data —— 把本人「档案 + 我的申请」聚合成一个 xlsx，
以 base64 随统一响应返回，前端写入临时文件后用系统程序打开/另存。

设计要点：
- 不新建任何数据库表、不写任何数据，纯读取现有 my_profile / my_applications 结果；
- 独立 router 文件，避免与并行编辑的 mobile.py 冲突；
- 仅本人：底层聚合函数已做 STUDENT 校验与本人范围限定，非学生/查不到本人档案会透出业务错误。
"""
from __future__ import annotations

import base64
import io

from fastapi import APIRouter, Depends
from openpyxl import Workbook

from app.core.response import success
from app.core.security import get_current_user
from app.services import mobile_student_service as stu

router = APIRouter(prefix="/mobile", tags=["移动端聚合"])

_PROFILE_FIELDS = [
    ("姓名", "name"),
    ("学号", "studentNo"),
    ("性别", "gender"),
    ("手机(脱敏)", "phoneMasked"),
    ("身份证(脱敏)", "idCardMasked"),
    ("班级", "className"),
    ("专业", "majorName"),
    ("学院", "collegeName"),
    ("入学年份", "enrollYear"),
    ("学籍状态", "status"),
]


@router.get("/me/export-data", summary="导出本人数据（档案+申请，xlsx，本人只读）")
def export_my_data(user=Depends(get_current_user)):
    profile = stu.my_profile(user) or {}
    apps = stu.my_applications(user) or {}

    wb = Workbook()
    ws1 = wb.active
    ws1.title = "个人档案"
    ws1.append(["字段", "内容"])
    p = profile.get("profile") or {}
    for label, key in _PROFILE_FIELDS:
        ws1.append([label, str(p.get(key, "") if p.get(key, "") is not None else "")])

    ws2 = wb.create_sheet("我的申请")
    ws2.append(["单号", "事项", "状态", "申请时间", "办理部门", "经办人", "最新意见"])
    for a in apps.get("applications") or []:
        ws2.append([
            a.get("no", "") or "",
            a.get("name", "") or "",
            a.get("statusText") or a.get("status", "") or "",
            a.get("applyTime") or "",
            a.get("dept", "") or "",
            a.get("handler", "") or "",
            a.get("lastOpinion", "") or "",
        ])

    bio = io.BytesIO()
    wb.save(bio)
    b64 = base64.b64encode(bio.getvalue()).decode("ascii")
    return success({
        "fileName": "我的数据.xlsx",
        "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "base64": b64,
    })
