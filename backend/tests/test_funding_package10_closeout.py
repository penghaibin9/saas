"""包 10 收口：项目规则金额、双人调整复核与真实并发竞争。"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import importlib.util
from pathlib import Path
import threading
import uuid

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

_BASE_MIGRATION = Path("alembic/versions/20260806_funding_package10_truth.py")
_CLOSE_MIGRATION = Path("alembic/versions/20260806_funding_pkg10_closeout.py")


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _install(engine):
    base = _load(_BASE_MIGRATION, "funding_pkg10_base")
    closeout = _load(_CLOSE_MIGRATION, "funding_pkg10_closeout")
    with engine.begin() as conn:
        operations = Operations(MigrationContext.configure(conn))
        base.op = operations
        closeout.op = operations
        base._create_triggers()
        closeout._create_adjustment_table()
        closeout._create_triggers()
    return base, closeout


def _cleanup_contract(engine, base, closeout):
    with engine.begin() as conn:
        operations = Operations(MigrationContext.configure(conn))
        base.op = operations
        closeout.op = operations
        for trigger in closeout._TRIGGERS:
            closeout._drop_trigger(trigger)
        if closeout._has_table(closeout._ADJUST):
            operations.drop_table(closeout._ADJUST)
        for trigger in base._TRIGGERS:
            base._drop_trigger(trigger)


def test_package10_closeout_sources_lock_authoritative_contract():
    migration = _CLOSE_MIGRATION.read_text("utf-8")
    service = Path("app/services/affairs_funding_authority_service.py").read_text("utf-8")
    api = Path("app/api/v1/affairs_funding_authority_api.py").read_text("utf-8")
    router = Path("app/api/v1/router.py").read_text("utf-8")

    assert 'revision = "20260806_funding_pkg10_close"' in migration
    assert 'down_revision = "20260806_aa_pkg1_change"' in migration
    assert "t_affairs_funding_amount_adjustment" in migration
    assert "uk_funding_amount_adjust_one_pending" in migration
    assert "FUNDING_RULE_AMOUNT_MISSING" in migration
    assert "FUNDING_ADJUST_SOD_REQUIRED" in migration
    assert "NEW.amount = v_project_amount" in migration
    assert "NEW.requested_amount = v_project_amount" in migration
    assert "SET NEW.approved_amount = v_adjust_amount" in migration
    assert "SET NEW.approved_amount = v_project_amount" in migration
    assert "UPDATE t_affairs_funding_batch" in migration
    assert "ROW_COUNT() <> 1" in migration

    assert 'model_copy(update={"amount": None})' in service
    assert "申请人与复核人必须为不同人员" in service
    assert "APPROVED_AMOUNT_FROZEN" in service
    assert "legacy._grant_one = _grant_one" in service
    assert "/amount-adjustments/{adjustment_id}/review" in api
    assert "studentAffairs.funding.publicity.manage" in api
    assert "install_funding_authority()" in router


def test_package10_mysql_rule_adjustment_and_concurrency(db_mode):
    """真实 MySQL：客户端金额被覆盖、双人复核生效、最后一个名额并发只能成功一次。"""
    from app.db.session import get_sessionmaker
    from app.models import FundingApplication, FundingBatch, FundingProject

    db = get_sessionmaker()()
    if db.bind.dialect.name != "mysql":
        db.close()
        pytest.skip("package 10 closeout requires MySQL")

    engine = db.get_bind()
    base, closeout = _install(engine)
    marker = uuid.uuid4().hex[:10]
    tenant_id = 1000000000000000001
    project_ids: list[int] = []
    batch_ids: list[int] = []
    app_ids: list[int] = []
    try:
        project = FundingProject(
            tenant_id=tenant_id,
            project_name=f"包10规则金额-{marker}",
            project_type="GRANT",
            amount=100,
            quota=1,
            status="ENABLED",
        )
        db.add(project)
        db.flush()
        project_id = int(project.id)
        project_ids.append(project_id)

        batch = FundingBatch(
            tenant_id=tenant_id,
            project_id=project_id,
            project_type="GRANT",
            year_code=f"PKG10-A-{marker}",
            quota=1,
            status="OPEN",
        )
        db.add(batch)
        db.flush()
        batch_id = int(batch.id)
        batch_ids.append(batch_id)

        application = FundingApplication(
            tenant_id=tenant_id,
            batch_id=batch_id,
            student_id=910000001,
            apply_source="SELF",
            project_type="GRANT",
            amount=999,
            status="PUBLICITY",
        )
        db.add(application)
        db.commit()
        application_id = int(application.id)
        app_ids.append(application_id)

        inserted = db.execute(text("""
            SELECT amount, requested_amount, approved_amount, quota_reserved
              FROM t_affairs_funding_application
             WHERE id = :id
        """), {"id": application_id}).mappings().one()
        assert str(inserted["amount"]) == "100.00"
        assert str(inserted["requested_amount"]) == "100.00"
        assert inserted["approved_amount"] is None
        assert int(inserted["quota_reserved"] or 0) == 0

        db.execute(text("""
            INSERT INTO t_affairs_funding_amount_adjustment
                (tenant_id, application_id, requested_amount, reason,
                 requester_id, requester_name, status, version,
                 created_at, updated_at, is_deleted)
            VALUES
                (:tenant_id, :application_id, 80, '经家庭情况复核调整',
                 1001, '申请人甲', 'PENDING', 0,
                 CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 0)
        """), {"tenant_id": tenant_id, "application_id": application_id})
        adjustment_id = int(db.execute(text("SELECT LAST_INSERT_ID()" )).scalar_one())
        db.commit()

        with pytest.raises(DBAPIError):
            db.execute(text("""
                UPDATE t_affairs_funding_amount_adjustment
                   SET status = 'APPROVED',
                       reviewer_id = 1001,
                       reviewer_name = '申请人甲',
                       review_reason = '本人复核不得通过'
                 WHERE id = :id
            """), {"id": adjustment_id})
            db.commit()
        db.rollback()

        db.execute(text("""
            UPDATE t_affairs_funding_amount_adjustment
               SET status = 'APPROVED',
                   reviewer_id = 1002,
                   reviewer_name = '复核人乙',
                   review_reason = '复核材料完整同意调整'
             WHERE id = :id
        """), {"id": adjustment_id})
        db.execute(text("""
            UPDATE t_affairs_funding_application
               SET status = 'GRANTED'
             WHERE id = :id
        """), {"id": application_id})
        db.commit()

        granted = db.execute(text("""
            SELECT approved_amount, quota_reserved
              FROM t_affairs_funding_application
             WHERE id = :id
        """), {"id": application_id}).mappings().one()
        reserved = db.execute(text("""
            SELECT reserved_quota, reserved_amount
              FROM t_affairs_funding_batch
             WHERE id = :id
        """), {"id": batch_id}).mappings().one()
        assert str(granted["approved_amount"]) == "80.00"
        assert int(granted["quota_reserved"]) == 1
        assert int(reserved["reserved_quota"]) == 1
        assert str(reserved["reserved_amount"]) == "80.00"

        project2 = FundingProject(
            tenant_id=tenant_id,
            project_name=f"包10并发名额-{marker}",
            project_type="GRANT",
            amount=60,
            quota=1,
            status="ENABLED",
        )
        db.add(project2)
        db.flush()
        project2_id = int(project2.id)
        project_ids.append(project2_id)
        batch2 = FundingBatch(
            tenant_id=tenant_id,
            project_id=project2_id,
            project_type="GRANT",
            year_code=f"PKG10-B-{marker}",
            quota=1,
            status="OPEN",
        )
        db.add(batch2)
        db.flush()
        batch2_id = int(batch2.id)
        batch_ids.append(batch2_id)
        app1 = FundingApplication(
            tenant_id=tenant_id, batch_id=batch2_id, student_id=910000011,
            apply_source="SELF", project_type="GRANT", amount=1, status="PUBLICITY",
        )
        app2 = FundingApplication(
            tenant_id=tenant_id, batch_id=batch2_id, student_id=910000012,
            apply_source="SELF", project_type="GRANT", amount=9999, status="PUBLICITY",
        )
        db.add_all([app1, app2])
        db.commit()
        concurrent_ids = [int(app1.id), int(app2.id)]
        app_ids.extend(concurrent_ids)

        barrier = threading.Barrier(2)

        def _grant(app_id: int) -> str:
            with engine.connect() as conn:
                tx = conn.begin()
                try:
                    barrier.wait(timeout=10)
                    conn.execute(text("""
                        UPDATE t_affairs_funding_application
                           SET status = 'GRANTED'
                         WHERE id = :id
                    """), {"id": app_id})
                    tx.commit()
                    return "SUCCESS"
                except Exception:
                    tx.rollback()
                    return "FAILED"

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(_grant, concurrent_ids))
        assert sorted(outcomes) == ["FAILED", "SUCCESS"]

        rows = db.execute(text("""
            SELECT status, approved_amount, quota_reserved
              FROM t_affairs_funding_application
             WHERE id IN (:first_id, :second_id)
             ORDER BY id
        """), {"first_id": concurrent_ids[0], "second_id": concurrent_ids[1]}).mappings().all()
        assert sum(1 for row in rows if row["status"] == "GRANTED") == 1
        assert sum(int(row["quota_reserved"] or 0) for row in rows) == 1
        assert {str(row["approved_amount"]) for row in rows if row["approved_amount"] is not None} == {"60.00"}

        batch_truth = db.execute(text("""
            SELECT reserved_quota, reserved_amount
              FROM t_affairs_funding_batch
             WHERE id = :id
        """), {"id": batch2_id}).mappings().one()
        assert int(batch_truth["reserved_quota"]) == 1
        assert str(batch_truth["reserved_amount"]) == "60.00"
    finally:
        try:
            if app_ids:
                placeholders = ",".join(str(int(value)) for value in app_ids)
                db.execute(text(f"DELETE FROM t_affairs_funding_amount_adjustment WHERE application_id IN ({placeholders})"))
                db.execute(text(f"DELETE FROM t_affairs_funding_application WHERE id IN ({placeholders})"))
            if batch_ids:
                placeholders = ",".join(str(int(value)) for value in batch_ids)
                db.execute(text(f"DELETE FROM t_affairs_funding_batch WHERE id IN ({placeholders})"))
            if project_ids:
                placeholders = ",".join(str(int(value)) for value in project_ids)
                db.execute(text(f"DELETE FROM t_affairs_funding_project WHERE id IN ({placeholders})"))
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
            _cleanup_contract(engine, base, closeout)
