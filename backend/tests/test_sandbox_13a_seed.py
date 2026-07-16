"""沙箱 13A 学工域演示种子测试（P8 上线检查单 §5 item2）。

seed_sandbox 为体验沙箱补齐困难认定/奖助/违纪最小演示数据（各一条中间态单据）；
要求：可种、幂等、reset 的 wipe 动态覆盖 13A 表并在 reseed 后恢复。
"""
from __future__ import annotations

import pytest
from sqlalchemy import func, select

SBX_TID = 1000000000000000007


def _count(db, model):
    return db.scalar(select(func.count()).select_from(model)
                     .where(model.tenant_id == SBX_TID)) or 0


@pytest.fixture()
def sandbox_seeded(db_mode):
    """在 db_mode 空库上种沙箱租户（含 13A 域最小数据）。"""
    from app.db.session import get_sessionmaker
    from app.services.sandbox_service import seed_sandbox
    db = get_sessionmaker()()
    try:
        seed_sandbox(db)
    finally:
        db.close()
    return db_mode


def test_sandbox_seeds_13a_domains(sandbox_seeded):
    from app.db.session import get_sessionmaker
    from app.models import (AidApply, AidBatch, DisciplineCase, FundingApplication,
                            FundingProject)
    db = get_sessionmaker()()
    try:
        assert _count(db, AidBatch) >= 1
        assert _count(db, AidApply) >= 1
        assert _count(db, FundingProject) >= 1
        assert _count(db, FundingApplication) >= 1
        assert _count(db, DisciplineCase) >= 1
        # 申请为中间态，便于体验审批流
        ap = db.scalars(select(AidApply).where(AidApply.tenant_id == SBX_TID)).first()
        assert ap.status == "CLASS_REVIEW"
        fa = db.scalars(select(FundingApplication).where(
            FundingApplication.tenant_id == SBX_TID)).first()
        assert fa.status == "COUNSELOR_REVIEW"
    finally:
        db.close()


def test_sandbox_13a_seed_idempotent(sandbox_seeded):
    from app.db.session import get_sessionmaker
    from app.models import AidApply, DisciplineCase, FundingApplication
    from app.services.sandbox_service import seed_sandbox
    db = get_sessionmaker()()
    try:
        before = (_count(db, AidApply), _count(db, FundingApplication),
                  _count(db, DisciplineCase))
        seed_sandbox(db)  # 二次种子不新增
        after = (_count(db, AidApply), _count(db, FundingApplication),
                 _count(db, DisciplineCase))
        assert after == before
    finally:
        db.close()


def test_sandbox_reset_covers_and_reseeds_13a(sandbox_seeded):
    from app.db.session import get_sessionmaker
    from app.models import AidApply, DisciplineCase, FundingApplication
    from app.services.sandbox_service import reset_sandbox
    db = get_sessionmaker()()
    try:
        report = reset_sandbox(db, dry_run=False)
        removed = report["removed"]
        # wipe 动态覆盖 13A 表（证明 reset 不漏学工域）
        assert "t_affairs_aid_apply" in removed
        assert "t_affairs_funding_application" in removed
        assert "t_affairs_discipline_case" in removed
        # reseed 后 13A 域恢复
        assert _count(db, AidApply) >= 1
        assert _count(db, FundingApplication) >= 1
        assert _count(db, DisciplineCase) >= 1
    finally:
        db.close()
