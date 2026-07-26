"""毕业设计敏感操作的批次上下文守卫。

页面选择的 batchId 不是展示参数，而是防止旧链接、并行标签页和缓存数据
把当前操作落到另一批次学生上的安全条件。学生门户/小程序通过当前档案解析器
得到唯一批次，学校端敏感接口则必须显式携带 batchId。
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
    expected = require_batch_id(batch_id)
    query = select(GraduationStudent).where(
        GraduationStudent.id == int(gd_student_id),
        GraduationStudent.tenant_id == _tid(),
        GraduationStudent.is_deleted.is_(False),
        GraduationStudent.record_status == "ACTIVE",
    )
    if for_update:
        query = query.with_for_update()
    student = db.scalars(query).first()
    if not student:
        raise not_found("毕设学生不存在或不在当前数据范围内")
    assert_student_batch(student, expected)
    return student
