"""租户内取数的安全默认入口。

背景（P0）：本系统是 共享 MySQL + tenant_id 行级隔离。隔离目前靠每个开发者
自觉在 where 里带上 tenant_id —— 少写一次，就是 A 学校老师读到 B 学校学生。
`db.get(Model, id)` 尤其危险：它按主键取行，**天然不带任何租户条件**。

本模块提供带租户约束的取数入口，让"写对"比"写错"更省事：

    from app.core.tenant_scoped import tenant_get, tenant_select

    student = tenant_get(db, StudentProfile, student_id)      # 跨租户直接取不到
    rows = db.scalars(tenant_select(StudentProfile)).all()     # select 自动带 tenant_id

新增业务代码请一律用这两个入口；确需跨租户（平台控制面）时用 tenant_get(...,
allow_cross_tenant=True) 并在调用处写明理由，这样审计时能一眼看出是刻意为之。
"""
from __future__ import annotations

from typing import Any, TypeVar

from sqlalchemy import Select, select

T = TypeVar("T")


def has_tenant_column(model: Any) -> bool:
    return "tenant_id" in getattr(model, "__table__", {}).columns  # type: ignore[operator]


def current_tenant_id_int() -> int:
    """当前请求租户 id。取不到就报错——绝不"没有租户就查全库"。"""
    from app.core.exceptions import AppException
    from app.services.db_service import current_tenant_id
    tid = current_tenant_id()
    if not tid:
        raise AppException("TENANT_CONTEXT_REQUIRED", "缺少租户上下文")
    return int(tid)


def tenant_select(model: type[T], *, tenant_id: int | None = None) -> Select:
    """等价于 select(model).where(model.tenant_id == 当前租户)。

    模型没有 tenant_id 列（控制面表，如 t_tenant 自身）时退化为普通 select。
    """
    stmt = select(model)
    if not has_tenant_column(model):
        return stmt
    tid = tenant_id if tenant_id is not None else current_tenant_id_int()
    return stmt.where(model.tenant_id == tid)  # type: ignore[attr-defined]


def tenant_get(db, model: type[T], pk, *, tenant_id: int | None = None,
               allow_cross_tenant: bool = False) -> T | None:
    """按主键取一行，并强制校验它属于当前租户。

    跨租户命中一律返回 None（表现得像"这行不存在"），不泄露他校数据的存在性。
    allow_cross_tenant=True 仅供平台控制面使用，调用处必须写明理由。
    """
    if pk is None:
        return None
    row = db.get(model, pk)
    if row is None or allow_cross_tenant or not has_tenant_column(model):
        return row
    tid = tenant_id if tenant_id is not None else current_tenant_id_int()
    if int(getattr(row, "tenant_id", 0) or 0) != int(tid):
        return None
    return row


def assert_same_tenant(row, *, tenant_id: int | None = None) -> None:
    """已经拿到对象时的补救校验（改造历史 db.get 调用点时用）。"""
    from app.core.exceptions import AppException
    if row is None or not hasattr(row, "tenant_id"):
        return
    tid = tenant_id if tenant_id is not None else current_tenant_id_int()
    if int(getattr(row, "tenant_id", 0) or 0) != int(tid):
        raise AppException("NO_PERMISSION", "无权访问该数据")
