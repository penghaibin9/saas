"""毕业设计敏感操作的批次上下文守卫。

页面选择的 batchId 不是展示参数，而是防止旧链接、并行标签页和缓存数据
把当前操作落到另一批次学生上的安全条件。学生门户/小程序通过当前档案解析器
得到唯一批次，学校端敏感接口则必须显式携带 batchId。

本模块只负责请求进入业务 Service 前的只读批次断言。写操作所需的 ``FOR UPDATE``
必须由真正执行状态转换的 Service 在同一事务内持有；路由层短会话锁会在调用
Service 前释放，不能作为并发安全证据。
"""
from __future__ import annotations

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.models import GraduationStudent
from app.services.db_service import _tid


def require_batch_id(batch_id) -> int:
    if batch_id in (None, ""):
        raise AppException("VALIDATION_ERROR", "请先选择毕业设计批次后再操作")
    try:
        value = int(batch_id)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "batchId 必须为有效数字") from None
    if value <= 0:
        raise AppException("VALIDATION_ERROR", "batchId 必须为有效数字")
    return value


def assert_student_batch(student: GraduationStudent | None, batch_id, *, required: bool = True) -> int | None:
    expected = require_batch_id(batch_id) if required else (int(batch_id) if batch_id not in (None, "") else None)
    if student is None:
        raise not_found("毕设学生不存在")
    actual = int(student.batch_id) if student.batch_id is not None else None
    if expected is not None and actual != expected:
        raise AppException(
            "DATA_CONFLICT",
            f"当前页面批次与学生档案批次不一致（页面批次 {expected}，学生批次 {actual or '未绑定'}），请刷新后重试",
        )
    return expected


def load_student_in_batch(db, gd_student_id, batch_id, *, for_update: bool = False) -> GraduationStudent:
    """只读核对学生所属批次。

    ``for_update`` 为旧路由调用兼容参数，故意不再执行行锁。真正写锁必须留在
    后续业务 Service 的同一数据库事务内，否则锁在本函数会话关闭时立即释放。
    """
    _ = for_update
    expected = require_batch_id(batch_id)
    student = db.scalars(select(GraduationStudent).where(
        GraduationStudent.id == int(gd_student_id),
        GraduationStudent.tenant_id == _tid(),
        GraduationStudent.is_deleted.is_(False),
        GraduationStudent.record_status == "ACTIVE",
    )).first()
    if not student:
        raise not_found("毕设学生不存在或不在当前数据范围内")
    assert_student_batch(student, expected)
    return student
