"""D6：选课轮次真实 MySQL 并发互斥。

证明两条生产不变量：
1. 同一批次两个 DRAFT 轮次并发 OPEN，最终只能有一个 OPEN；
2. 同一批次并发创建轮次，round_no 必须稳定生成 1/2，不得唯一键撞成 500。
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import importlib
from threading import Barrier
from types import SimpleNamespace

import pytest

from app.core.exceptions import AppException
from app.db.session import get_sessionmaker

round_service = importlib.import_module(
    "app.modules.academic_affairs.services.academic_affairs_selection_round_service"
)

TID = 1000000000000000001


def _seed_batch(*, with_two_rounds=False):
    from app.models import AaSelectionBatch, AaSelectionRound, AaTerm

    db = get_sessionmaker()()
    try:
        term = AaTerm(
            tenant_id=TID,
            year_code="2097-2098",
            term_no=1,
            term_name="D6轮次并发学期",
            teaching_weeks=18,
            status="PUBLISHED",
            is_current=False,
        )
        db.add(term)
        db.flush()
        batch = AaSelectionBatch(
            tenant_id=TID,
            term_id=term.id,
            batch_name="D6轮次并发批次",
            status="OPEN",
        )
        db.add(batch)
        db.flush()
        round_ids = []
        if with_two_rounds:
            for no in (1, 2):
                row = AaSelectionRound(
                    tenant_id=TID,
                    batch_id=batch.id,
                    round_no=no,
                    round_name=f"D6并发第{no}轮",
                    mode="FCFS",
                    allow_enroll=True,
                    allow_drop=True,
                    status="DRAFT",
                )
                db.add(row)
                db.flush()
                round_ids.append(int(row.id))
        db.commit()
        return int(batch.id), round_ids
    finally:
        db.close()


def _install_service_test_context(monkeypatch):
    monkeypatch.setattr(round_service._core, "_tid", lambda: TID)
    monkeypatch.setattr(
        round_service._core,
        "_ctx",
        lambda _user, _db: SimpleNamespace(scope_type="TENANT_ALL"),
    )
    monkeypatch.setattr(round_service._core, "_require_manage_scope", lambda _ctx: None)
    monkeypatch.setattr(round_service._core, "_audit", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        round_service.selection_service,
        "_guard_batch_writable",
        lambda _db, _batch: None,
    )


@pytest.mark.usefixtures("db_mode")
def test_two_rounds_concurrent_open_only_one_wins(monkeypatch):
    _install_service_test_context(monkeypatch)
    _batch_id, round_ids = _seed_batch(with_two_rounds=True)
    barrier = Barrier(2)

    def open_one(round_id):
        barrier.wait()
        try:
            result = round_service.open_round({}, round_id)
            return f"ok:{result['roundId']}"
        except AppException as exc:
            return f"rejected:{exc.code}"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(open_one, round_ids))

    assert sum(value.startswith("ok:") for value in results) == 1, results
    assert sum(value.startswith("rejected:") for value in results) == 1, results

    from app.models import AaSelectionRound

    db = get_sessionmaker()()
    try:
        rows = db.query(AaSelectionRound).filter(
            AaSelectionRound.tenant_id == TID,
            AaSelectionRound.id.in_(round_ids),
            AaSelectionRound.is_deleted.is_(False),
        ).order_by(AaSelectionRound.round_no).all()
        assert sum(row.status == "OPEN" for row in rows) == 1
        assert sum(row.status == "DRAFT" for row in rows) == 1
    finally:
        db.close()


@pytest.mark.usefixtures("db_mode")
def test_concurrent_round_create_serializes_round_numbers(monkeypatch):
    _install_service_test_context(monkeypatch)
    batch_id, _ = _seed_batch(with_two_rounds=False)
    barrier = Barrier(2)

    def create_one(index):
        barrier.wait()
        body = SimpleNamespace(
            roundName=f"D6并发创建-{index}",
            mode="FCFS",
            allowEnroll=True,
            allowDrop=True,
            startAt=None,
            endAt=None,
        )
        result = round_service.create_round({}, batch_id, body)
        return int(result["roundNo"])

    with ThreadPoolExecutor(max_workers=2) as pool:
        round_nos = sorted(pool.map(create_one, (1, 2)))

    assert round_nos == [1, 2]

    from app.models import AaSelectionRound

    db = get_sessionmaker()()
    try:
        stored = [
            int(row.round_no)
            for row in db.query(AaSelectionRound).filter(
                AaSelectionRound.tenant_id == TID,
                AaSelectionRound.batch_id == batch_id,
                AaSelectionRound.is_deleted.is_(False),
            ).order_by(AaSelectionRound.round_no).all()
        ]
        assert stored == [1, 2]
    finally:
        db.close()
