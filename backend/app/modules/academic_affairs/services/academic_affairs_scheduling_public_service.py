"""排课工作台公开入口：规则/冲突来自 final，汇总与发布共用同一闸门。"""
from __future__ import annotations

import importlib

from app.core.exceptions import not_found

from . import academic_affairs_schedule_gate_service as gate_service

_base = importlib.import_module(
    ".academic_affairs_scheduling_final_service",
    package=__package__,
)


def __getattr__(name):
    return getattr(_base, name)


def summary(user, batch_id):
    from app.models import AaScheduleBatch

    with _base._base.session() as db:
        _base._base._ctx(user, db)
        batch = db.query(AaScheduleBatch).filter(
            AaScheduleBatch.id == int(batch_id),
            AaScheduleBatch.tenant_id == _base._base._tid(),
            AaScheduleBatch.is_deleted.is_(False),
        ).first()
        if not batch:
            raise not_found("课表批次不存在")
        return gate_service.evaluate(db, batch)
