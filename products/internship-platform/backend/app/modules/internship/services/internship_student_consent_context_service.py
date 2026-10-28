"""学生双端知情确认批次上下文。

列表必须绑定学生明确选择的实习批次；正文、确认和拒绝继续由 consent service
按任务 ID 校验当前学生本人，形成“列表批次约束 + 对象本人约束”双层边界。
"""
from __future__ import annotations

from app.core.exceptions import AppException
from app.modules.internship.services import internship_consent_service as consent
from app.modules.internship.services.internship_record_resolver import (
    resolve_student_internship_context,
)
from app.services.db_service import session


def list_my(user, batch_id=None):
    from app.services.mobile_student_service import _require_student, resolve_student
    with session() as db:
        student = resolve_student(db, _require_student(user))
        if not student:
            raise AppException("NO_PERMISSION", "无法解析当前登录学生身份")
        ctx = resolve_student_internship_context(
            db, student=student, batch_id=batch_id, for_write=False)
        if ctx.mode == "need_select":
            raise AppException("DATA_CONFLICT", "你有多条进行中的实习记录，请先选择实习批次")
        if not ctx.record:
            return []
        record_id = str(ctx.record.id)
    return [
        item for item in consent.list_my(user)
        if str(item.get("internshipId") or "") == record_id
    ]
