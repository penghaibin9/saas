"""包 11：处分主档、投影、决定版本与唯一活动子流程真实 MySQL 收口。"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import threading
import uuid

from alembic.migration import MigrationContext
from alembic.operations import Operations
import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

_MIGRATION = Path("alembic/versions/20260806_discipline_package11.py")


def _load_migration():
    spec = importlib.util.spec_from_file_location("discipline_package11", _MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _install(engine):
    migration = _load_migration()
    with engine.begin() as conn:
        migration.op = Operations(MigrationContext.configure(conn))
        migration.upgrade()
    return migration


def _drop_triggers(engine, migration):
    with engine.begin() as conn:
        migration.op = Operations(MigrationContext.configure(conn))
        for trigger in migration._TRIGGERS:
            migration._drop_trigger(trigger)


def _restore_triggers(engine, migration):
    with engine.begin() as conn:
        migration.op = Operations(MigrationContext.configure(conn))
        migration._create_triggers()


def test_package11_static_contracts_are_installed():
    migration = _MIGRATION.read_text("utf-8")
    guard = Path("app/services/affairs_discipline_integrity_guard.py").read_text("utf-8")
    api = Path("app/api/v1/affairs_discipline_integrity_api.py").read_text("utf-8")
    router = Path("app/api/v1/router.py").read_text("utf-8")

    assert 'revision = "20260806_discipline_pkg11"' in migration
    assert 'down_revision = "20260806_funding_pkg10_close"' in migration
    assert "DISCIPLINE_PROJECTION_STUDENT_MISMATCH" in migration
    assert "DISCIPLINE_DECISION_IMMUTABLE" in migration
    assert "DISCIPLINE_ACTIVE_SUBFLOW_EXISTS" in migration
    assert "_ensure_cs_student" in guard
    assert "appeal_todo._ensure_todo" in guard
    assert "emit_receiver_notice" in guard
    assert "db.commit()" in guard
    assert "decision-review" in api
    assert "affairs_discipline_integrity_router" in router


def test_package11_mysql_projection_versions_and_subflow_mutex(db_mode, monkeypatch):
    from app.db.session import get_sessionmaker
    from app.models import (
        CsDiscipline, CsServiceStudent, DisciplineAppeal, DisciplineCase,
        DisciplineRemoveApply, StudentProfile,
    )
    from app.services import affairs_discipline_integrity_guard as guard
    from app.services import affairs_discipline_service as discipline

    db = get_sessionmaker()()
    if db.get_bind().dialect.name != "mysql":
        db.close()
        pytest.skip("package 11 integrity contract requires MySQL")

    engine = db.get_bind()
    migration = _install(engine)
    marker = uuid.uuid4().hex[:10]
    tenant_id = 1000000000000000001
    profile_ids: list[int] = []
    service_ids: list[int] = []
    case_ids: list[int] = []
    projection_ids: list[int] = []
    child_ids: list[tuple[str, int]] = []

    monkeypatch.setattr(guard, "_tid", lambda: tenant_id)
    monkeypatch.setattr(discipline, "_tid", lambda: tenant_id)

    try:
        first = StudentProfile(
            tenant_id=tenant_id,
            student_no=f"PKG11-A-{marker}",
            real_name="包十一学生甲",
            current_stage="ENROLLED",
            student_status="NORMAL",
            status="ACTIVE",
        )
        second = StudentProfile(
            tenant_id=tenant_id,
            student_no=f"PKG11-B-{marker}",
            real_name="包十一学生乙",
            current_stage="ENROLLED",
            student_status="NORMAL",
            status="ACTIVE",
        )
        db.add_all([first, second])
        db.flush()
        profile_ids = [int(first.id), int(second.id)]

        # 先占用若干服务台账主键，确保测试能识别“返回 StudentProfile.id”的旧降级错误。
        for index in range(3):
            db.add(CsServiceStudent(
                tenant_id=tenant_id,
                student_no=f"PKG11-D-{marker}-{index}",
                student_id=990000000 + index,
                name=f"占位学生{index}",
                care_level="NORMAL",
                risk_level="LOW",
                mental_flag=False,
                record_status="ACTIVE",
            ))
        db.commit()

        service_a = guard._ensure_cs_student(db, profile_ids[0])
        service_b = guard._ensure_cs_student(db, profile_ids[1])
        db.commit()
        service_ids = [int(service_a.id), int(service_b.id)]
        assert int(service_a.student_id) == profile_ids[0]
        assert int(service_b.student_id) == profile_ids[1]
        assert service_ids[0] != profile_ids[0]

        case = DisciplineCase(
            tenant_id=tenant_id,
            student_id=profile_ids[0],
            disc_type="WARNING",
            reason="包十一投影串人反向测试事实",
            doc_no=f"PKG11-{marker}",
            status="EFFECTIVE",
        )
        db.add(case)
        db.commit()
        case_ids.append(int(case.id))

        # 错把乙的服务台账挂到甲的处分主案，数据库必须拒绝。
        wrong = CsDiscipline(
            tenant_id=tenant_id,
            cs_student_id=service_ids[1],
            disc_type="WARNING",
            reason=case.reason,
            doc_no=case.doc_no,
            status="EFFECTIVE",
            record_status="ACTIVE",
            source_case_id=case_ids[0],
        )
        db.add(wrong)
        with pytest.raises(DBAPIError):
            db.commit()
        db.rollback()

        correct = CsDiscipline(
            tenant_id=tenant_id,
            cs_student_id=service_ids[0],
            disc_type="WARNING",
            reason=case.reason,
            doc_no=case.doc_no,
            status="EFFECTIVE",
            record_status="ACTIVE",
            source_case_id=case_ids[0],
        )
        db.add(correct)
        db.commit()
        projection_ids.append(int(correct.id))

        locked_case = db.scalars(select(DisciplineCase).where(
            DisciplineCase.id == case_ids[0],
        ).with_for_update()).one()
        original = guard._append_decision(
            db, locked_case,
            kind="ORIGINAL", source_type="APPROVAL", source_id=case_ids[0],
            disc_type="WARNING", reason=locked_case.reason, doc_no=locked_case.doc_no,
        )
        revised = guard._append_decision(
            db, locked_case,
            kind="REVISED", source_type="APPEAL", source_id=700001,
            disc_type="SERIOUS_WARNING", reason="申诉后变更的完整处分事实", doc_no="REV-001",
        )
        revoked = guard._append_decision(
            db, locked_case,
            kind="REVOKED", source_type="APPEAL", source_id=700001,
            disc_type="SERIOUS_WARNING", reason="申诉后变更的完整处分事实", doc_no="REV-001",
        )
        db.commit()
        assert [original.version_no, revised.version_no, revoked.version_no] == [1, 2, 3]
        assert int(revised.previous_version_id) == int(original.id)
        assert int(revoked.previous_version_id) == int(revised.id)

        with pytest.raises(DBAPIError):
            db.execute(text("""
                UPDATE t_affairs_discipline_decision_version
                   SET reason = '篡改'
                 WHERE id = :id
            """), {"id": int(original.id)})
            db.commit()
        db.rollback()

        mutex_case = DisciplineCase(
            tenant_id=tenant_id,
            student_id=profile_ids[0],
            disc_type="DEMERIT",
            reason="包十一申诉解除并发互斥测试事实",
            status="EFFECTIVE",
        )
        db.add(mutex_case)
        db.commit()
        mutex_case_id = int(mutex_case.id)
        case_ids.append(mutex_case_id)

        barrier = threading.Barrier(2)
        outcomes: list[tuple[str, bool, int | None]] = []
        lock = threading.Lock()

        def insert_appeal():
            local = get_sessionmaker()()
            success = False
            row_id = None
            try:
                barrier.wait(timeout=10)
                row = DisciplineAppeal(
                    tenant_id=tenant_id,
                    case_id=mutex_case_id,
                    student_id=profile_ids[0],
                    reason="并发申诉理由不少于五个字",
                    status="SUBMITTED",
                )
                local.add(row)
                local.commit()
                row_id = int(row.id)
                success = True
            except Exception:
                local.rollback()
            finally:
                local.close()
                with lock:
                    outcomes.append(("APPEAL", success, row_id))

        def insert_remove():
            local = get_sessionmaker()()
            success = False
            row_id = None
            try:
                barrier.wait(timeout=10)
                row = DisciplineRemoveApply(
                    tenant_id=tenant_id,
                    case_id=mutex_case_id,
                    student_id=profile_ids[0],
                    apply_reason="并发解除理由不少于五个字",
                    status="COUNSELOR_REVIEW",
                    current_node="COUNSELOR_REVIEW",
                )
                local.add(row)
                local.commit()
                row_id = int(row.id)
                success = True
            except Exception:
                local.rollback()
            finally:
                local.close()
                with lock:
                    outcomes.append(("REMOVE", success, row_id))

        threads = [threading.Thread(target=insert_appeal), threading.Thread(target=insert_remove)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=20)
        assert len(outcomes) == 2
        assert sum(1 for _kind, success, _row_id in outcomes if success) == 1
        child_ids.extend((kind, int(row_id)) for kind, success, row_id in outcomes if success and row_id)

        active_lock = db.execute(text("""
            SELECT flow_type, flow_id
              FROM t_affairs_discipline_subflow_lock
             WHERE tenant_id = :tenant_id AND case_id = :case_id
        """), {"tenant_id": tenant_id, "case_id": mutex_case_id}).mappings().all()
        assert len(active_lock) == 1
        assert active_lock[0]["flow_type"] in {"APPEAL", "REMOVE"}
    finally:
        try:
            db.rollback()
            _drop_triggers(engine, migration)
            db.execute(text("""
                DELETE FROM t_affairs_discipline_subflow_lock
                 WHERE tenant_id = :tenant_id AND case_id IN :case_ids
            """).bindparams(case_ids=tuple(case_ids or [-1])), {"tenant_id": tenant_id})
        except Exception:
            db.rollback()
            # MySQL 的 IN tuple 绑定兼容性差时，逐案清理。
            for case_id in case_ids:
                db.execute(text("""
                    DELETE FROM t_affairs_discipline_subflow_lock
                     WHERE tenant_id = :tenant_id AND case_id = :case_id
                """), {"tenant_id": tenant_id, "case_id": case_id})
        try:
            if case_ids:
                for case_id in case_ids:
                    db.execute(text("DELETE FROM t_affairs_discipline_appeal WHERE tenant_id=:t AND case_id=:c"),
                               {"t": tenant_id, "c": case_id})
                    db.execute(text("DELETE FROM t_affairs_discipline_remove_apply WHERE tenant_id=:t AND case_id=:c"),
                               {"t": tenant_id, "c": case_id})
                    db.execute(text("DELETE FROM t_affairs_discipline_decision_version WHERE tenant_id=:t AND case_id=:c"),
                               {"t": tenant_id, "c": case_id})
                    db.execute(text("DELETE FROM t_cs_discipline WHERE tenant_id=:t AND source_case_id=:c"),
                               {"t": tenant_id, "c": case_id})
                    db.execute(text("DELETE FROM t_affairs_discipline_case WHERE tenant_id=:t AND id=:c"),
                               {"t": tenant_id, "c": case_id})
            for service_id in service_ids:
                db.execute(text("DELETE FROM t_cs_service_student WHERE tenant_id=:t AND id=:id"),
                           {"t": tenant_id, "id": service_id})
            db.execute(text("DELETE FROM t_cs_service_student WHERE tenant_id=:t AND student_no LIKE :prefix"),
                       {"t": tenant_id, "prefix": f"PKG11-D-{marker}-%"})
            for profile_id in profile_ids:
                db.execute(text("DELETE FROM t_student_profile WHERE tenant_id=:t AND id=:id"),
                           {"t": tenant_id, "id": profile_id})
            db.commit()
        finally:
            db.close()
            _restore_triggers(engine, migration)
