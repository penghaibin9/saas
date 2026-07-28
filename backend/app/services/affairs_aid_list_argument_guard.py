"""困难认定列表参数兼容收口。

历史 API 路由按 ``(user, batchId, status, level, page, pageSize)`` 位置调用，
而正式服务签名是 ``(user, status, batch_id, level, page, page_size)``。
本守卫保留服务公开签名，只在检测到“数字批次号被误放到 status”时纠正位置，
避免把批次号当状态查询而恒返回空列表。
"""
from __future__ import annotations


_INSTALLED = False


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    from app.services import affairs_aid_service as aid

    original = aid.list_applications

    def list_applications(user, status=None, batch_id=None, level=None,
                          page=1, page_size=20, student_id=None):
        status_text = str(status or "").strip()
        batch_text = str(batch_id or "").strip()
        if status_text.isdigit() and (not batch_text or not batch_text.isdigit()):
            status, batch_id = batch_id, status
        return original(
            user,
            status=status,
            batch_id=batch_id,
            level=level,
            page=page,
            page_size=page_size,
            student_id=student_id,
        )

    aid.list_applications = list_applications
    _INSTALLED = True
