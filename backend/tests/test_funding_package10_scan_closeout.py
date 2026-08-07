"""包 10 复审：公示自动扫描必须逐申请提交，额度冲突不得回滚整批。"""
from __future__ import annotations

from datetime import datetime, timedelta
import importlib.util
from pathlib import Path
import uuid

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import text

_BASE_MIGRATION = Path("alembic/versions/20260806_funding_package10_truth.py")
_CLOSE_MIGRATION = Path("alembic/versions/20260806_funding_pkg10_closeout.py")


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _install(engine):
    base = _load(_BASE_MIGRATION, "funding_pkg10_scan_base")
    closeout = _load(_CLOSE_MIGRATION, "funding_pkg10_scan_closeout")
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


def test_package10_scan_guard_is_installed_on_existing_url():
    service = Path("app/services/affairs_funding_scan_guard.py").read_text("utf-8")
    api = Path("app/api/v1/affairs_funding_authority_api.py").read_text("utf-8")

    assert "with_for_update(skip_locked=True)" in service
    assert "legacy.scan_publicity = scan_publicity" in service
    assert "quotaConflict" in service
    assert "install_funding_scan_guard()" in api


def test_package10_mysql_scan_keeps_success_when_next_application_exceeds_quota(db_mode, monkeypatch):
    """真实 MySQL 服务路径：同批次两条到期申请、一个名额，结果必须 1 成功 + 1 冲突。"""
    from app.db.session import get_sessionmaker
    from app.models import FundingApplication, FundingBatch, FundingProject
    from app.services import affairs_funding_scan_guard as scan_guard
    from app.services import affairs_funding_service as legacy

    db = get_sessionmaker()()
    if db.bind.dialect.name != "mysql":
        db.close()
        pytest.skip("package 10 scan closeout requires MySQL")

    engine = db.get_bind()
    base, closeout = _install(engine)
    marker = uuid.uuid4().hex[:10]
    tenant_id = 1000000000000000001
    project_id = batch_id = None
    app_ids: list[int] = []

    monkeypatch.setattr(scan_guard, "_tid", lambda: tenant_id)
    monkeypatch.setattr(legacy, "_tid", lambda: tenant_id)
    monkeypatch.setattr(legacy, "_pending_appeal_ids", lambda _db, _ids: set())
    monkeypatch.setattr(legacy, "_drain_message_outbox", lambda: None)

    def _minimal_grant(_db, application):
        application.status = "GRANTED"
        application.result_at = datetime.utcnow()
        application.version = int(application.version or 0) + 1

    monkeypatch.setattr(legacy, "_grant_one", _minimal_grant)

    try:
        project = FundingProject(
            tenant_id=tenant_id,
            project_name=f"包10扫描事务-{marker}",
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
            year_code=f"PKG10-SCAN-{marker}",
            quota=1,
            publicity_days=1,
            status="OPEN",
        )
        db.add(batch)
        db.flush()
        batch_id = int(batch.id)

        due_at = datetime.utcnow() - timedelta(days=2)
        first = FundingApplication(
            tenant_id=tenant_id,
            batch_id=batch_id,
            student_id=920000001,
            apply_source="SELF",
            project_type="GRANT",
            amount=999,
            status="PUBLICITY",
            publicity_at=due_at,
        )
        second = FundingApplication(
            tenant_id=tenant_id,
            batch_id=batch_id,
            student_id=920000002,
            apply_source="SELF",
            project_type="GRANT",
            amount=1,
            status="PUBLICITY",
            publicity_at=due_at,
        )
        db.add_all([first, second])
        db.commit()
        app_ids = [int(first.id), int(second.id)]

        result = scan_guard.scan_publicity()
        assert result["count"] == 1
        assert result["quotaConflict"] == 1

        rows = db.execute(text("""
            SELECT status, approved_amount, quota_reserved
              FROM t_affairs_funding_application
             WHERE id IN (:first_id, :second_id)
             ORDER BY id
        """), {"first_id": app_ids[0], "second_id": app_ids[1]}).mappings().all()
        assert sum(1 for row in rows if row["status"] == "GRANTED") == 1
        assert sum(1 for row in rows if row["status"] == "PUBLICITY") == 1
        assert sum(int(row["quota_reserved"] or 0) for row in rows) == 1

        batch_truth = db.execute(text("""
            SELECT reserved_quota, reserved_amount
              FROM t_affairs_funding_batch
             WHERE id = :id
        """), {"id": batch_id}).mappings().one()
        assert int(batch_truth["reserved_quota"]) == 1
        assert str(batch_truth["reserved_amount"]) == "100.00"
    finally:
        try:
            if app_ids:
                db.execute(text("DELETE FROM t_affairs_funding_application WHERE id IN (:first_id, :second_id)"),
                           {"first_id": app_ids[0], "second_id": app_ids[1]})
            if batch_id is not None:
                db.execute(text("DELETE FROM t_affairs_funding_batch WHERE id = :id"), {"id": batch_id})
            if project_id is not None:
                db.execute(text("DELETE FROM t_affairs_funding_project WHERE id = :id"), {"id": project_id})
            db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()
            _cleanup_contract(engine, base, closeout)
