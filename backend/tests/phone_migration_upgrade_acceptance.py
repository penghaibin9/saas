"""One-way MySQL acceptance for the phone-login migration chain.

Run this only against an isolated database.  The script seeds identity facts at
the last pre-phone revision, upgrades to the repository head, and proves that
the canonical account/student identities and their history were not rewritten.
It deliberately has no downgrade, cleanup, or database-drop path.
"""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from app.db.session import get_engine, reset_state

PRE_PHONE_REVISION = "20260910_merge_academic_affairs_main"
MARKER_TENANT_CODE = "PHONE-UPGRADE-ACCEPTANCE"
MARKER_LOGIN_NAME = "20260910000000000001"
MARKER_STUDENT_NO = "20260910000000000001"


def _current_revision() -> str:
    with get_engine().connect() as conn:
        return str(conn.scalar(text("SELECT version_num FROM alembic_version")))


def _repository_head() -> str:
    return str(ScriptDirectory.from_config(Config("alembic.ini")).get_current_head())


def _load_snapshot() -> dict[str, object] | None:
    with get_engine().connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT t.id AS tenant_id, u.id AS user_id, u.login_name,
                       u.password_hash, s.id AS student_id, s.student_no,
                       l.id AS link_id, l.user_id AS linked_user_id,
                       l.student_id AS linked_student_id, l.link_status,
                       e.id AS event_id, e.student_id AS event_student_id,
                       e.from_stage, e.to_stage
                  FROM t_tenant t
                  JOIN t_user u ON u.tenant_id = t.id
                  JOIN t_student_profile s ON s.tenant_id = t.id
                  JOIN t_student_account_link l
                    ON l.tenant_id = t.id AND l.user_id = u.id AND l.student_id = s.id
                  JOIN t_student_stage_event e
                    ON e.tenant_id = t.id AND e.student_id = s.id
                 WHERE t.tenant_code = :tenant_code
                   AND u.login_name = :login_name
                   AND s.student_no = :student_no
                """
            ),
            {
                "tenant_code": MARKER_TENANT_CODE,
                "login_name": MARKER_LOGIN_NAME,
                "student_no": MARKER_STUDENT_NO,
            },
        ).mappings().one_or_none()
        return dict(row) if row else None


def _seed_pre_phone_identity() -> dict[str, object]:
    existing = _load_snapshot()
    if existing:
        return existing

    now = datetime(2026, 9, 10, 9, 0, 0)
    common = {
        "now": now,
        "tenant_code": MARKER_TENANT_CODE,
        "login_name": MARKER_LOGIN_NAME,
        "student_no": MARKER_STUDENT_NO,
    }
    with get_engine().begin() as conn:
        tenant_id = conn.execute(
            text(
                """
                INSERT INTO t_tenant
                  (tenant_code, school_name, deploy_mode, db_mode, status,
                   created_at, updated_at, is_deleted, version)
                VALUES
                  (:tenant_code, '手机号迁移验收学校', 'SAAS', 'SHARED', 'ACTIVE',
                   :now, :now, 0, 0)
                """
            ),
            common,
        ).lastrowid
        user_id = conn.execute(
            text(
                """
                INSERT INTO t_user
                  (tenant_id, login_name, real_name, password_hash, user_type,
                   status, must_change_password, created_at, updated_at,
                   is_deleted, version)
                VALUES
                  (:tenant_id, :login_name, '迁移验收学生',
                   'migration-acceptance-password-hash', 'STUDENT', 'ACTIVE', 0,
                   :now, :now, 0, 0)
                """
            ),
            {**common, "tenant_id": tenant_id},
        ).lastrowid
        student_id = conn.execute(
            text(
                """
                INSERT INTO t_student_profile
                  (tenant_id, student_no, real_name, current_stage,
                   student_status, status, created_at, updated_at,
                   is_deleted, version)
                VALUES
                  (:tenant_id, :student_no, '迁移验收学生', 'ENROLLED',
                   'NORMAL', 'ACTIVE', :now, :now, 0, 0)
                """
            ),
            {**common, "tenant_id": tenant_id},
        ).lastrowid
        conn.execute(
            text(
                """
                INSERT INTO t_student_account_link
                  (tenant_id, student_id, user_id, link_status,
                   bound_login_name, bound_student_no, source, bound_at,
                   created_at, updated_at, is_deleted, version)
                VALUES
                  (:tenant_id, :student_id, :user_id, 'ACTIVE', :login_name,
                   :student_no, 'BACKFILL', :now, :now, :now, 0, 0)
                """
            ),
            {
                **common,
                "tenant_id": tenant_id,
                "student_id": student_id,
                "user_id": user_id,
            },
        )
        conn.execute(
            text(
                """
                INSERT INTO t_student_stage_event
                  (tenant_id, student_id, from_stage, to_stage, reason,
                   source_module, occurred_at, created_at)
                VALUES
                  (:tenant_id, :student_id, 'ADMITTED', 'ENROLLED',
                   'phone migration acceptance history', 'IDENTITY', :now, :now)
                """
            ),
            {**common, "tenant_id": tenant_id, "student_id": student_id},
        )
    seeded = _load_snapshot()
    assert seeded is not None
    return seeded


def main() -> None:
    before_revision = _current_revision()
    assert before_revision == PRE_PHONE_REVISION, (
        f"isolated database must start at {PRE_PHONE_REVISION}, got {before_revision}"
    )
    before = _seed_pre_phone_identity()

    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
    reset_state()

    expected_head = _repository_head()
    assert _current_revision() == expected_head
    after = _load_snapshot()
    assert after == before, "phone migrations changed a canonical identity or history fact"

    engine = get_engine()
    table_names = set(inspect(engine).get_table_names())
    assert {
        "t_user_phone_login_binding",
        "t_user_phone_login_candidate",
        "t_password_reset_sms_job",
    }.issubset(table_names)
    sms_job_columns = {column["name"] for column in inspect(engine).get_columns("t_password_reset_sms_job")}
    assert {"purpose", "challenge_ref"}.issubset(sms_job_columns)
    with engine.connect() as conn:
        credential_version = conn.scalar(
            text("SELECT credential_version FROM t_user WHERE id=:user_id"),
            {"user_id": before["user_id"]},
        )
        binding_count = conn.scalar(text("SELECT COUNT(*) FROM t_user_phone_login_binding"))
        candidate_count = conn.scalar(text("SELECT COUNT(*) FROM t_user_phone_login_candidate"))
    assert credential_version == 0
    assert binding_count == 0
    assert candidate_count == 0
    print(
        "PHONE_MIGRATION_ACCEPTANCE PASS",
        f"from={PRE_PHONE_REVISION}",
        f"to={expected_head}",
        "identity_rows=tenant,user,student,account_link,stage_event",
        "phone_bindings=0",
        "phone_candidates=0",
    )


if __name__ == "__main__":
    main()
