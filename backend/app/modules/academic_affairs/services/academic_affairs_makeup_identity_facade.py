"""补考重修免修学生身份最终保护层。

学生入口缺少真实StudentProfile时返回业务404，禁止在重修/免修申请中继续访问None属性形成500。
"""
from __future__ import annotations

from app.core.exceptions import not_found

from . import academic_affairs_makeup_term_facade as _base

_legacy = _base._legacy
_original_student = _legacy._student


def __getattr__(name):
    return getattr(_base, name)


def _required_student(db):
    student = _original_student(db)
    if not student:
        raise not_found("学生档案不存在")
    return student


_legacy._student = _required_student
