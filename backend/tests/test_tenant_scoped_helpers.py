"""租户隔离安全默认入口的负向测试。

`db.get(Model, id)` 按主键取行，天然不带租户条件——这是共享库 SaaS 最严重的
一类事故来源（A 校老师读到 B 校学生）。tenant_get / tenant_select 必须让
跨租户取数拿不到东西。
"""
from __future__ import annotations

import pytest

from app.core.exceptions import AppException

TENANT_A = 1000000000000000001
TENANT_B = 1000000000000000002


@pytest.fixture
def two_tenant_leaves(db_mode):
    """在两个租户下各建一条同类业务数据，返回 (A的行id, B的行id)。"""
    from app.core.context import set_tenant
    from app.db.session import get_sessionmaker
    from app.models import CsLeave

    db = get_sessionmaker()()
    try:
        rows = {}
        for tid in (TENANT_A, TENANT_B):
            row = CsLeave(tenant_id=tid, student_id=1, leave_type="SICK",
                          reason="测试", status="PENDING_REVIEW")
            db.add(row)
            db.flush()
            rows[tid] = row.id
        db.commit()
        yield rows
    finally:
        db.close()
        set_tenant(None)


def test_tenant_get_returns_none_across_tenants(two_tenant_leaves):
    from app.core.context import set_tenant
    from app.core.tenant_scoped import tenant_get
    from app.db.session import get_sessionmaker
    from app.models import CsLeave

    set_tenant({"tenantId": str(TENANT_A)})
    db = get_sessionmaker()()
    try:
        assert tenant_get(db, CsLeave, two_tenant_leaves[TENANT_A]) is not None
        assert tenant_get(db, CsLeave, two_tenant_leaves[TENANT_B]) is None, \
            "跨租户按主键取行必须取不到"
        # 对照：裸 db.get 拿得到 —— 正是本模块要替换掉的写法。
        assert db.get(CsLeave, two_tenant_leaves[TENANT_B]) is not None
    finally:
        db.close()


def test_tenant_select_filters_to_current_tenant(two_tenant_leaves):
    from app.core.context import set_tenant
    from app.core.tenant_scoped import tenant_select
    from app.db.session import get_sessionmaker
    from app.models import CsLeave

    set_tenant({"tenantId": str(TENANT_B)})
    db = get_sessionmaker()()
    try:
        ids = {r.id for r in db.scalars(tenant_select(CsLeave)).all()}
        assert two_tenant_leaves[TENANT_B] in ids
        assert two_tenant_leaves[TENANT_A] not in ids
    finally:
        db.close()


def test_assert_same_tenant_rejects_foreign_row(two_tenant_leaves):
    from app.core.context import set_tenant
    from app.core.tenant_scoped import assert_same_tenant
    from app.db.session import get_sessionmaker
    from app.models import CsLeave

    set_tenant({"tenantId": str(TENANT_A)})
    db = get_sessionmaker()()
    try:
        foreign = db.get(CsLeave, two_tenant_leaves[TENANT_B])
        with pytest.raises(AppException):
            assert_same_tenant(foreign)
    finally:
        db.close()


def test_missing_tenant_context_is_not_treated_as_all_tenants(db_mode):
    """没有租户上下文时必须报错，绝不能退化成"查全库"。"""
    from app.core.context import set_tenant
    from app.core.tenant_scoped import tenant_select
    from app.models import CsLeave

    set_tenant(None)
    with pytest.raises(AppException) as ei:
        tenant_select(CsLeave)
    assert ei.value.code == "TENANT_CONTEXT_REQUIRED"
