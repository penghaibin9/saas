"""D6 轮次只读对象范围门禁。

Final facade 继续是公开 owner；这里必须用 importlib 取 legacy module 本体，避免 package alias
被重新绑定后形成递归。
"""
from __future__ import annotations

import importlib

from . import academic_affairs_selection_read_service as _read


def list_rounds(user, batch_id):
    with _read._core.session() as db:
        ctx = _read._core._ctx(user, db)
        scoped = _read._scope_values(db, ctx)
        _read._core._get_batch(db, int(batch_id))
        _read._require_batch_visible(db, int(batch_id), scoped)

    legacy = importlib.import_module(
        "app.modules.academic_affairs.services.academic_affairs_selection_round_service"
    )
    return legacy.list_rounds(user, int(batch_id))
