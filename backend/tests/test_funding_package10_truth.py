"""包 10：申请额/批准额分离、批准快照冻结、名额与金额原子占用合同。"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import uuid

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

_MIGRATION_PATH = Path("alembic/versions/20260806_funding_package10_truth.py")


def _load_package10_migration():
    """直接加载生产迁移，避免测试复制一份与线上可能漂移的触发器 SQL。"""
    spec = importlib.util.spec_from_file_location("funding_package10_truth", _MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _install_package10_triggers(engine):
    migration = _load_package10_migration()
    with engine.begin() as conn:
        migration.op = Operations(MigrationContext.configure(conn))
        migration._create_triggers()
    return migration


def _drop_package10_triggers(engine, migration) -> None:
    with engine.begin() as conn:
        migration.op = Operations(MigrationContext.configure(conn))
        for trigger in migration._TRIGGERS:
            migration._drop_trigger(trigger)


def test_package10_migration_declares_separate_truth_and_atomic_guards():
    source = _MIGRATION_PATH.read_text("utf-8")
    assert 'revision = "20260806_funding_pkg10"' in source
    assert 'down_revision = "20260806_gd_pkg9_archive_ver"' in source
    assert "requested_amount" in source
    assert "approved_amount" in source
    assert "approved_amount_snapshot" in source
    assert "approval_version_snapshot" in source
    assert "reserved_quota" in source
    assert "reserved_amount" in source
    assert "FUNDING_QUOTA_OR_BUDGET_EXCEEDED" in source
    assert "FUNDING_APPROVAL_FACT_IMMUTABLE" in source
    assert "FUNDING_DISBURSEMENT_SNAPSHOT_IMMUTABLE" in source
    assert "UPDATE t_affairs_funding_batch" in source
    assert "ROW_COUNT() <> 1" in source


def test_package10_mysql_reservation_and_snapshot_are_database_enforced(db_mode):
    """真实 MySQL：第二笔批准无法越过单名额/金额额度，发放金额只能来自冻结批准快照。"""
    from app.db.session import get_sessionmaker
    from app.models import FundingApplication, FundingBatch, FundingDisbursement, FundingProject

    db = get_sessionmaker()()
    if db.bind.dialect.name != "mysql":
        db.close()
        pytest.skip("package 10 trigger contract requires MySQL")

    engine = db.get_bind()
    migration = _install_package10_triggers(engine)
    marker = uuid.uuid4().hex[:12]
    tenant_id = 1000000000000000001
    project_id = batch_id = first_id = second_id = disbursement_id = None
    try:
        project = FundingProject(
            tenant_id=tenant_id,
            project_name=f"包10原子额度-{marker}",
            project_type="GRANT",
            amount=100,
            quota=1,
            status="ENABLED",
        )
        db.add(project)
        db.flush()
        project_id = int(project.id)

        batch = FundingBatch(
            tenant_id=tenant_id,
            project_id=project_id,
            project_type="GRANT",
            year_code=f"PKG10-{marker}",
            quota=1,
            status="OPEN",
        )
        db.add(batch)
        db.flush()
        batch_id = int(batch.id)

        first = FundingApplication(
            tenant_id=tenant_id,
            batch_id=batch_id,
            student_id=900000001,
            apply_source="SELF",
            project_type="GRANT",
            amount=100,
            status="PUBLICITY",
        )
        second = FundingApplication(
            tenant_id=tenant_id,
            batch_id=batch_id,
            student_id=900000002,
            apply_source="SELF",
            project_type="GRANT",
            amount=100,
            status="PUBLICITY",
        )
        db.add_all([first, second])
        db.commit()
        first_id = int(first.id)
        second_id = int(second.id)

        first_truth = db.execute(text("""
            SELECT requested_amount, approved_amount, quota_reserved
              FROM t_affairs_funding_application
             WHERE id = :id
        """), {"id": first_id}).mappings().one()
        assert str(first_truth["requested_amount"]) == "100.00"
        assert first_truth["approved_amount"] is None
        assert int(first_truth["quota_reserved"] or 0) == 0

        db.execute(text("""
            UPDATE t_affairs_funding_application
               SET status = 'GRANTED'
             WHERE id = :id
        """), {"id": first_id})
        db.commit()

        approved = db.execute(text("""
            SELECT requested_amount, approved_amount, approved_at, quota_reserved, version
              FROM t_affairs_funding_application
             WHERE id = :id
        """), {"id": first_id}).mappings().one()
        reserved = db.execute(text("""
            SELECT amount_budget, reserved_quota, reserved_amount
              FROM t_affairs_funding_batch
             WHERE id = :id
        """), {"id": batch_id}).mappings().one()
        assert str(approved["requested_amount"]) == "100.00"
        assert str(approved["approved_amount"]) == "100.00"
        assert approved["approved_at"] is not None
        assert int(approved["quota_reserved"]) == 1
        assert str(reserved["amount_budget"]) == "100.00"
        assert int(reserved["reserved_quota"]) == 1
        assert str(reserved["reserved_amount"]) == "100.00"

        with pytest.raises(DBAPIError):
            db.execute(text("""
                UPDATE t_affairs_funding_application
                   SET status = 'GRANTED'
                 WHERE id = :id
            """), {"id": second_id})
            db.commit()
        db.rollback()

        second_truth = db.execute(text("""
            SELECT status, approved_amount, quota_reserved
              FROM t_affairs_funding_application
             WHERE id = :id
        """), {"id": second_id}).mappings().one()
        assert second_truth["status"] == "PUBLICITY"
        assert second_truth["approved_amount"] is None
        assert int(second_truth["quota_reserved"] or 0) == 0

        disbursement = FundingDisbursement(
            tenant_id=tenant_id,
            application_id=first_id,
            batch_id=batch_id,
            student_id=900000001,
            project_type="GRANT",
            amount=999,
            bank_status="PENDING",
        )
        db.add(disbursement)
        db.commit()
        disbursement_id = int(disbursement.id)

        snapshot = db.execute(text("""
            SELECT amount, approved_amount_snapshot, approved_at_snapshot,
                   approval_version_snapshot
              FROM t_affairs_funding_disbursement
             WHERE id = :id
        """), {"id": disbursement_id}).mappings().one()
        assert str(snapshot["amount"]) == "100.00"
        assert str(snapshot["approved_amount_snapshot"]) == "100.00"
        assert snapshot["approved_at_snapshot"] == approved["approved_at"]
        assert int(snapshot["approval_version_snapshot"]) == int(approved["version"] or 0)

        with pytest.raises(DBAPIError):
            db.execute(text("""
                UPDATE t_affairs_funding_disbursement
                   SET approved_amount_snapshot = 99
                 WHERE id = :id
            """), {"id": disbursement_id})
            db.commit()
        db.rollback()

        with pytest.raises(DBAPIError):
            db.execute(text("""
                UPDATE t_affairs_funding_application
                   SET approved_amount = 99
                 WHERE id = :id
            """), {"id": first_id})
            db.commit()
        db.rollback()
    finally:
        try:
            if disbursement_id is not None:
                db.execute(text("DELETE FROM t_affairs_funding_disbursement WHERE id = :id"),
                           {"id": disbursement_id})
            if first_id is not None:
                db.execute(text("DELETE FROM t_affairs_funding_application WHERE id IN (:first, :second)"),
                           {"first": first_id, "second": second_id if second_id is not None else -1})
            if batch_id is not None:
                db.execute(text("DELETE FROM t_affairs_funding_batch WHERE id = :id"), {"id": batch_id})
            if project_id is not None:
                db.execute(text("DELETE FROM t_affairs_funding_project WHERE id = :id"), {"id": project_id})
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
            _drop_package10_triggers(engine, migration)
