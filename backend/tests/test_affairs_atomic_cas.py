from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy import Boolean, Integer, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from app.core.exceptions import AppException
from app.core.optimistic_lock import atomic_claim_version


class _Base(DeclarativeBase):
    pass


class _Record(_Base):
    __tablename__ = "cas_record"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(default="PENDING")


def test_atomic_claim_allows_exactly_one_concurrent_writer(tmp_path):
    engine = create_engine(
        f"sqlite+pysqlite:///{tmp_path / 'cas.db'}",
        connect_args={"timeout": 10},
    )
    _Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions.begin() as db:
        db.add(_Record(id=1, tenant_id=1, version=0))

    barrier = Barrier(2)

    def write(next_status):
        with sessions() as db:
            row = db.get(_Record, 1)
            barrier.wait()
            try:
                atomic_claim_version(db, row, 0)
                row.status = next_status
                row.version += 1
                db.commit()
                return "SUCCESS"
            except AppException as exc:
                db.rollback()
                return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(write, ("APPROVED", "REJECTED")))

    assert results.count("SUCCESS") == 1
    assert results.count("APPROVAL_VERSION_CONFLICT") == 1
    with sessions() as db:
        row = db.get(_Record, 1)
        assert row.version == 1
        assert row.status in {"APPROVED", "REJECTED"}
