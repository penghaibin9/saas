"""包 11：处分主档、服务学生投影、决定版本与唯一活动子流程。

Revision ID: 20260806_discipline_pkg11
Revises: 20260806_funding_pkg10_close
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260806_discipline_pkg11"
down_revision = "20260806_funding_pkg10_close"
branch_labels = None
depends_on = None

assert len(revision) <= 32

_CASE = "t_affairs_discipline_case"
_APPEAL = "t_affairs_discipline_appeal"
_REMOVE = "t_affairs_discipline_remove_apply"
_STUDENT = "t_student_profile"
_CS_STUDENT = "t_cs_service_student"
_PROJECTION = "t_cs_discipline"
_DECISION = "t_affairs_discipline_decision_version"
_SUBFLOW = "t_affairs_discipline_subflow_lock"

_TRIGGERS = (
    "trg_disc_decision_bi_pkg11",
    "trg_disc_decision_bu_pkg11",
    "trg_disc_decision_bd_pkg11",
    "trg_cs_discipline_bi_pkg11",
    "trg_cs_discipline_bu_pkg11",
    "trg_disc_appeal_bi_pkg11",
    "trg_disc_appeal_ai_pkg11",
    "trg_disc_appeal_au_pkg11",
    "trg_disc_remove_bi_pkg11",
    "trg_disc_remove_ai_pkg11",
    "trg_disc_remove_au_pkg11",
)


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("20260806_discipline_pkg11 requires MySQL")


def _has_table(name: str) -> bool:
    return inspect(op.get_bind()).has_table(name)


def _columns(table: str) -> set[str]:
    return {column["name"] for column in inspect(op.get_bind()).get_columns(table)}


def _indexes(table: str) -> set[str]:
    return {index["name"] for index in inspect(op.get_bind()).get_indexes(table)}


def _add_column(table: str, column: sa.Column) -> None:
    if column.name not in _columns(table):
        op.add_column(table, column)


def _drop_trigger(name: str) -> None:
    op.execute(sa.text(f"DROP TRIGGER IF EXISTS `{name}`"))


def _create_tables() -> None:
    if not _has_table(_DECISION):
        op.create_table(
            _DECISION,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("case_id", sa.BigInteger(), nullable=False),
            sa.Column("version_no", sa.Integer(), nullable=False),
            sa.Column("decision_kind", sa.String(20), nullable=False,
                      comment="ORIGINAL/REVISED/REVOKED"),
            sa.Column("previous_version_id", sa.BigInteger(), nullable=True),
            sa.Column("disc_type", sa.String(50), nullable=False),
            sa.Column("reason", sa.String(1000), nullable=True),
            sa.Column("doc_no", sa.String(100), nullable=True),
            sa.Column("source_type", sa.String(50), nullable=False,
                      comment="APPROVAL/APPEAL/LEGACY_BACKFILL"),
            sa.Column("source_id", sa.BigInteger(), nullable=True),
            sa.Column("decided_by", sa.BigInteger(), nullable=True),
            sa.Column("decided_at", sa.DateTime(), nullable=False,
                      server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("created_at", sa.DateTime(), nullable=False,
                      server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("tenant_id", "case_id", "version_no",
                                name="uk_disc_decision_case_ver"),
        )
        op.create_index("ix_disc_decision_case", _DECISION,
                        ["tenant_id", "case_id", "id"], unique=False)
        op.create_index("ix_disc_decision_source", _DECISION,
                        ["tenant_id", "source_type", "source_id"], unique=False)

    if not _has_table(_SUBFLOW):
        op.create_table(
            _SUBFLOW,
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("case_id", sa.BigInteger(), nullable=False),
            sa.Column("flow_type", sa.String(20), nullable=False,
                      comment="APPEAL/REMOVE"),
            sa.Column("flow_id", sa.BigInteger(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False,
                      server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("tenant_id", "case_id", name="uk_disc_active_subflow"),
            sa.UniqueConstraint("tenant_id", "flow_type", "flow_id",
                                name="uk_disc_subflow_source"),
        )


def _add_contract_columns() -> None:
    _add_column(_CASE, sa.Column("current_decision_version_id", sa.BigInteger(), nullable=True,
                                 comment="当前有效处分决定版本"))
    _add_column(_CASE, sa.Column("current_decision_version_no", sa.Integer(), nullable=True,
                                 comment="当前有效处分决定版本号"))
    _add_column(_PROJECTION, sa.Column("decision_version_id", sa.BigInteger(), nullable=True,
                                       comment="投影对应的处分决定版本"))
    _add_column(_PROJECTION, sa.Column("decision_version_no", sa.Integer(), nullable=True,
                                       comment="投影对应的处分决定版本号"))

    if "active_student_id" not in _columns(_CS_STUDENT):
        op.execute(sa.text("""
            ALTER TABLE t_cs_service_student
            ADD COLUMN active_student_id BIGINT
            GENERATED ALWAYS AS (
                CASE WHEN is_deleted = 0 THEN student_id ELSE NULL END
            ) STORED
        """))
    if "active_source_case_id" not in _columns(_PROJECTION):
        op.execute(sa.text("""
            ALTER TABLE t_cs_discipline
            ADD COLUMN active_source_case_id BIGINT
            GENERATED ALWAYS AS (
                CASE WHEN is_deleted = 0 THEN source_case_id ELSE NULL END
            ) STORED
        """))


def _repair_service_students_and_projections() -> None:
    # 先把重复服务学生投影统一指向最早的正确台账，再软删重复行。
    op.execute(sa.text("""
        UPDATE t_cs_discipline d
        JOIN t_cs_service_student old_s
          ON old_s.id = d.cs_student_id
         AND old_s.tenant_id = d.tenant_id
        JOIN (
            SELECT tenant_id, student_id, MIN(id) AS keep_id
              FROM t_cs_service_student
             WHERE is_deleted = 0 AND student_id IS NOT NULL
             GROUP BY tenant_id, student_id
        ) keep_s
          ON keep_s.tenant_id = old_s.tenant_id
         AND keep_s.student_id = old_s.student_id
           SET d.cs_student_id = keep_s.keep_id
         WHERE d.is_deleted = 0
           AND d.cs_student_id <> keep_s.keep_id
    """))
    op.execute(sa.text("""
        UPDATE t_cs_service_student s
        JOIN (
            SELECT tenant_id, student_id, MIN(id) AS keep_id
              FROM t_cs_service_student
             WHERE is_deleted = 0 AND student_id IS NOT NULL
             GROUP BY tenant_id, student_id
        ) keep_s
          ON keep_s.tenant_id = s.tenant_id
         AND keep_s.student_id = s.student_id
           SET s.is_deleted = 1,
               s.record_status = 'VOID',
               s.void_reason = 'PACKAGE11_DUPLICATE_SERVICE_STUDENT',
               s.updated_at = CURRENT_TIMESTAMP,
               s.version = COALESCE(s.version, 0) + 1
         WHERE s.is_deleted = 0
           AND s.id <> keep_s.keep_id
    """))

    # 对所有已有处分主案补建真实 CsServiceStudent，禁止再借用 StudentProfile.id。
    op.execute(sa.text("""
        INSERT INTO t_cs_service_student (
            tenant_id, student_no, student_id, name, gender, class_id, grade,
            care_level, risk_level, mental_flag, record_status,
            created_at, updated_at, is_deleted, version
        )
        SELECT p.tenant_id, p.student_no, p.id, p.real_name, p.gender,
               CAST(p.class_id AS CHAR), p.grade,
               'NORMAL', 'LOW', 0, 'ACTIVE',
               CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 0, 0
          FROM t_student_profile p
         WHERE p.is_deleted = 0
           AND EXISTS (
               SELECT 1
                 FROM t_affairs_discipline_case c
                WHERE c.tenant_id = p.tenant_id
                  AND c.student_id = p.id
                  AND c.is_deleted = 0
           )
           AND NOT EXISTS (
               SELECT 1
                 FROM t_cs_service_student s
                WHERE s.tenant_id = p.tenant_id
                  AND s.student_id = p.id
                  AND s.is_deleted = 0
           )
    """))

    # source_case_id 是权威关联，按主案学生修复所有历史串号投影。
    op.execute(sa.text("""
        UPDATE t_cs_discipline d
        JOIN t_affairs_discipline_case c
          ON c.id = d.source_case_id
         AND c.tenant_id = d.tenant_id
         AND c.is_deleted = 0
        JOIN t_cs_service_student s
          ON s.tenant_id = c.tenant_id
         AND s.student_id = c.student_id
         AND s.is_deleted = 0
           SET d.cs_student_id = s.id,
               d.updated_at = CURRENT_TIMESTAMP,
               d.version = COALESCE(d.version, 0) + 1
         WHERE d.is_deleted = 0
           AND (d.cs_student_id IS NULL OR d.cs_student_id <> s.id)
    """))

    # 一主案只保留一个活动投影；主案回链统一指向保留行。
    op.execute(sa.text("""
        UPDATE t_affairs_discipline_case c
        JOIN (
            SELECT tenant_id, source_case_id, MIN(id) AS keep_id
              FROM t_cs_discipline
             WHERE is_deleted = 0 AND source_case_id IS NOT NULL
             GROUP BY tenant_id, source_case_id
        ) p
          ON p.tenant_id = c.tenant_id
         AND p.source_case_id = c.id
           SET c.cs_discipline_id = p.keep_id,
               c.updated_at = CURRENT_TIMESTAMP,
               c.version = COALESCE(c.version, 0) + 1
         WHERE c.is_deleted = 0
           AND (c.cs_discipline_id IS NULL OR c.cs_discipline_id <> p.keep_id)
    """))
    op.execute(sa.text("""
        UPDATE t_cs_discipline d
        JOIN (
            SELECT tenant_id, source_case_id, MIN(id) AS keep_id
              FROM t_cs_discipline
             WHERE is_deleted = 0 AND source_case_id IS NOT NULL
             GROUP BY tenant_id, source_case_id
        ) p
          ON p.tenant_id = d.tenant_id
         AND p.source_case_id = d.source_case_id
           SET d.is_deleted = 1,
               d.record_status = 'VOID',
               d.void_reason = 'PACKAGE11_DUPLICATE_PROJECTION',
               d.updated_at = CURRENT_TIMESTAMP,
               d.version = COALESCE(d.version, 0) + 1
         WHERE d.is_deleted = 0
           AND d.id <> p.keep_id
    """))


def _create_indexes() -> None:
    if "uk_cs_service_student_active" not in _indexes(_CS_STUDENT):
        op.create_index("uk_cs_service_student_active", _CS_STUDENT,
                        ["tenant_id", "active_student_id"], unique=True)
    if "uk_cs_discipline_active_case" not in _indexes(_PROJECTION):
        op.create_index("uk_cs_discipline_active_case", _PROJECTION,
                        ["tenant_id", "active_source_case_id"], unique=True)
    if "ix_disc_case_current_decision" not in _indexes(_CASE):
        op.create_index("ix_disc_case_current_decision", _CASE,
                        ["tenant_id", "current_decision_version_id"], unique=False)


def _backfill_decision_versions() -> None:
    op.execute(sa.text("""
        INSERT INTO t_affairs_discipline_decision_version (
            tenant_id, case_id, version_no, decision_kind, previous_version_id,
            disc_type, reason, doc_no, source_type, source_id,
            decided_by, decided_at, created_at
        )
        SELECT c.tenant_id, c.id, 1, 'ORIGINAL', NULL,
               c.disc_type, c.reason, c.doc_no, 'LEGACY_BACKFILL', c.id,
               c.updated_by, COALESCE(c.effective_at, c.decide_date, c.updated_at, c.created_at),
               CURRENT_TIMESTAMP
          FROM t_affairs_discipline_case c
         WHERE c.is_deleted = 0
           AND c.status IN ('EFFECTIVE', 'REMOVE_REVIEW', 'REMOVED', 'REVOKED')
           AND NOT EXISTS (
               SELECT 1
                 FROM t_affairs_discipline_decision_version v
                WHERE v.tenant_id = c.tenant_id
                  AND v.case_id = c.id
           )
    """))
    op.execute(sa.text("""
        UPDATE t_affairs_discipline_case c
        JOIN t_affairs_discipline_decision_version v
          ON v.tenant_id = c.tenant_id
         AND v.case_id = c.id
        JOIN (
            SELECT tenant_id, case_id, MAX(version_no) AS max_version
              FROM t_affairs_discipline_decision_version
             GROUP BY tenant_id, case_id
        ) latest
          ON latest.tenant_id = v.tenant_id
         AND latest.case_id = v.case_id
         AND latest.max_version = v.version_no
           SET c.current_decision_version_id = v.id,
               c.current_decision_version_no = v.version_no
         WHERE c.is_deleted = 0
    """))
    op.execute(sa.text("""
        UPDATE t_cs_discipline d
        JOIN t_affairs_discipline_case c
          ON c.id = d.source_case_id
         AND c.tenant_id = d.tenant_id
           SET d.decision_version_id = c.current_decision_version_id,
               d.decision_version_no = c.current_decision_version_no
         WHERE d.is_deleted = 0
           AND d.source_case_id IS NOT NULL
    """))


def _preflight_subflows() -> None:
    overlap = op.get_bind().execute(sa.text("""
        SELECT COUNT(*)
          FROM t_affairs_discipline_appeal a
          JOIN t_affairs_discipline_remove_apply r
            ON r.tenant_id = a.tenant_id
           AND r.case_id = a.case_id
           AND r.is_deleted = 0
           AND r.status NOT IN ('APPROVED', 'REJECTED')
         WHERE a.is_deleted = 0
           AND a.status IN ('SUBMITTED', 'REVIEWING')
    """)).scalar() or 0
    if int(overlap) > 0:
        raise RuntimeError("package 11 preflight failed: appeal/remove active subflow overlap exists")

    op.execute(sa.text("""
        INSERT INTO t_affairs_discipline_subflow_lock (
            tenant_id, case_id, flow_type, flow_id, created_at
        )
        SELECT a.tenant_id, a.case_id, 'APPEAL', a.id, CURRENT_TIMESTAMP
          FROM t_affairs_discipline_appeal a
         WHERE a.is_deleted = 0
           AND a.status IN ('SUBMITTED', 'REVIEWING')
           AND NOT EXISTS (
               SELECT 1 FROM t_affairs_discipline_subflow_lock l
                WHERE l.tenant_id = a.tenant_id AND l.case_id = a.case_id
           )
    """))
    op.execute(sa.text("""
        INSERT INTO t_affairs_discipline_subflow_lock (
            tenant_id, case_id, flow_type, flow_id, created_at
        )
        SELECT r.tenant_id, r.case_id, 'REMOVE', r.id, CURRENT_TIMESTAMP
          FROM t_affairs_discipline_remove_apply r
         WHERE r.is_deleted = 0
           AND r.status NOT IN ('APPROVED', 'REJECTED')
           AND NOT EXISTS (
               SELECT 1 FROM t_affairs_discipline_subflow_lock l
                WHERE l.tenant_id = r.tenant_id AND l.case_id = r.case_id
           )
    """))


def _create_triggers() -> None:
    for trigger in _TRIGGERS:
        _drop_trigger(trigger)

    op.execute(sa.text("""
        CREATE TRIGGER trg_disc_decision_bi_pkg11
        BEFORE INSERT ON t_affairs_discipline_decision_version
        FOR EACH ROW
        BEGIN
            DECLARE v_prev_case BIGINT;
            DECLARE v_prev_version INT;
            DECLARE v_case_exists INT DEFAULT 0;

            SELECT COUNT(*) INTO v_case_exists
              FROM t_affairs_discipline_case c
             WHERE c.id = NEW.case_id
               AND c.tenant_id = NEW.tenant_id
               AND c.is_deleted = 0;
            IF v_case_exists <> 1 THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'DISCIPLINE_DECISION_CASE_MISMATCH';
            END IF;
            IF NEW.decision_kind NOT IN ('ORIGINAL', 'REVISED', 'REVOKED') THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'DISCIPLINE_DECISION_KIND_INVALID';
            END IF;
            IF NEW.version_no = 1 THEN
                IF NEW.decision_kind <> 'ORIGINAL' OR NEW.previous_version_id IS NOT NULL THEN
                    SIGNAL SQLSTATE '45000'
                        SET MESSAGE_TEXT = 'DISCIPLINE_ORIGINAL_VERSION_INVALID';
                END IF;
            ELSE
                IF NEW.previous_version_id IS NULL THEN
                    SIGNAL SQLSTATE '45000'
                        SET MESSAGE_TEXT = 'DISCIPLINE_PREVIOUS_VERSION_REQUIRED';
                END IF;
                SELECT v.case_id, v.version_no
                  INTO v_prev_case, v_prev_version
                  FROM t_affairs_discipline_decision_version v
                 WHERE v.id = NEW.previous_version_id
                   AND v.tenant_id = NEW.tenant_id
                 LIMIT 1;
                IF v_prev_case IS NULL OR v_prev_case <> NEW.case_id
                   OR v_prev_version <> NEW.version_no - 1 THEN
                    SIGNAL SQLSTATE '45000'
                        SET MESSAGE_TEXT = 'DISCIPLINE_DECISION_CHAIN_INVALID';
                END IF;
            END IF;
        END
    """))
    op.execute(sa.text("""
        CREATE TRIGGER trg_disc_decision_bu_pkg11
        BEFORE UPDATE ON t_affairs_discipline_decision_version
        FOR EACH ROW
        BEGIN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'DISCIPLINE_DECISION_IMMUTABLE';
        END
    """))
    op.execute(sa.text("""
        CREATE TRIGGER trg_disc_decision_bd_pkg11
        BEFORE DELETE ON t_affairs_discipline_decision_version
        FOR EACH ROW
        BEGIN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'DISCIPLINE_DECISION_IMMUTABLE';
        END
    """))

    validation_body = """
            DECLARE v_case_student BIGINT;
            DECLARE v_service_student BIGINT;
            DECLARE v_decision_case BIGINT;
            DECLARE v_decision_no INT;
            IF NEW.source_case_id IS NOT NULL THEN
                SELECT c.student_id INTO v_case_student
                  FROM t_affairs_discipline_case c
                 WHERE c.id = NEW.source_case_id
                   AND c.tenant_id = NEW.tenant_id
                   AND c.is_deleted = 0
                 LIMIT 1;
                SELECT s.student_id INTO v_service_student
                  FROM t_cs_service_student s
                 WHERE s.id = NEW.cs_student_id
                   AND s.tenant_id = NEW.tenant_id
                   AND s.is_deleted = 0
                 LIMIT 1;
                IF v_case_student IS NULL OR v_service_student IS NULL
                   OR v_case_student <> v_service_student THEN
                    SIGNAL SQLSTATE '45000'
                        SET MESSAGE_TEXT = 'DISCIPLINE_PROJECTION_STUDENT_MISMATCH';
                END IF;
                IF NEW.decision_version_id IS NOT NULL THEN
                    SELECT v.case_id, v.version_no
                      INTO v_decision_case, v_decision_no
                      FROM t_affairs_discipline_decision_version v
                     WHERE v.id = NEW.decision_version_id
                       AND v.tenant_id = NEW.tenant_id
                     LIMIT 1;
                    IF v_decision_case IS NULL OR v_decision_case <> NEW.source_case_id
                       OR v_decision_no <> NEW.decision_version_no THEN
                        SIGNAL SQLSTATE '45000'
                            SET MESSAGE_TEXT = 'DISCIPLINE_PROJECTION_DECISION_MISMATCH';
                    END IF;
                END IF;
            END IF;
    """
    op.execute(sa.text(f"""
        CREATE TRIGGER trg_cs_discipline_bi_pkg11
        BEFORE INSERT ON t_cs_discipline
        FOR EACH ROW
        BEGIN
            {validation_body}
        END
    """))
    op.execute(sa.text(f"""
        CREATE TRIGGER trg_cs_discipline_bu_pkg11
        BEFORE UPDATE ON t_cs_discipline
        FOR EACH ROW
        BEGIN
            {validation_body}
        END
    """))

    op.execute(sa.text("""
        CREATE TRIGGER trg_disc_appeal_bi_pkg11
        BEFORE INSERT ON t_affairs_discipline_appeal
        FOR EACH ROW
        BEGIN
            IF EXISTS (
                SELECT 1 FROM t_affairs_discipline_subflow_lock l
                 WHERE l.tenant_id = NEW.tenant_id AND l.case_id = NEW.case_id
            ) THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'DISCIPLINE_ACTIVE_SUBFLOW_EXISTS';
            END IF;
        END
    """))
    op.execute(sa.text("""
        CREATE TRIGGER trg_disc_appeal_ai_pkg11
        AFTER INSERT ON t_affairs_discipline_appeal
        FOR EACH ROW
        BEGIN
            IF NEW.status IN ('SUBMITTED', 'REVIEWING') AND NEW.is_deleted = 0 THEN
                INSERT INTO t_affairs_discipline_subflow_lock
                    (tenant_id, case_id, flow_type, flow_id, created_at)
                VALUES (NEW.tenant_id, NEW.case_id, 'APPEAL', NEW.id, CURRENT_TIMESTAMP);
            END IF;
        END
    """))
    op.execute(sa.text("""
        CREATE TRIGGER trg_disc_appeal_au_pkg11
        AFTER UPDATE ON t_affairs_discipline_appeal
        FOR EACH ROW
        BEGIN
            IF NEW.is_deleted = 1
               OR NEW.status IN ('UPHELD', 'REVISED', 'REVOKED', 'WITHDRAWN') THEN
                DELETE FROM t_affairs_discipline_subflow_lock
                 WHERE tenant_id = NEW.tenant_id
                   AND case_id = NEW.case_id
                   AND flow_type = 'APPEAL'
                   AND flow_id = NEW.id;
            END IF;
        END
    """))

    op.execute(sa.text("""
        CREATE TRIGGER trg_disc_remove_bi_pkg11
        BEFORE INSERT ON t_affairs_discipline_remove_apply
        FOR EACH ROW
        BEGIN
            IF EXISTS (
                SELECT 1 FROM t_affairs_discipline_subflow_lock l
                 WHERE l.tenant_id = NEW.tenant_id AND l.case_id = NEW.case_id
            ) THEN
                SIGNAL SQLSTATE '45000'
                    SET MESSAGE_TEXT = 'DISCIPLINE_ACTIVE_SUBFLOW_EXISTS';
            END IF;
        END
    """))
    op.execute(sa.text("""
        CREATE TRIGGER trg_disc_remove_ai_pkg11
        AFTER INSERT ON t_affairs_discipline_remove_apply
        FOR EACH ROW
        BEGIN
            IF NEW.status NOT IN ('APPROVED', 'REJECTED') AND NEW.is_deleted = 0 THEN
                INSERT INTO t_affairs_discipline_subflow_lock
                    (tenant_id, case_id, flow_type, flow_id, created_at)
                VALUES (NEW.tenant_id, NEW.case_id, 'REMOVE', NEW.id, CURRENT_TIMESTAMP);
            END IF;
        END
    """))
    op.execute(sa.text("""
        CREATE TRIGGER trg_disc_remove_au_pkg11
        AFTER UPDATE ON t_affairs_discipline_remove_apply
        FOR EACH ROW
        BEGIN
            IF NEW.is_deleted = 1 OR NEW.status IN ('APPROVED', 'REJECTED') THEN
                DELETE FROM t_affairs_discipline_subflow_lock
                 WHERE tenant_id = NEW.tenant_id
                   AND case_id = NEW.case_id
                   AND flow_type = 'REMOVE'
                   AND flow_id = NEW.id;
            END IF;
        END
    """))


def upgrade() -> None:
    _require_mysql()
    _create_tables()
    _add_contract_columns()
    _repair_service_students_and_projections()
    _create_indexes()
    _backfill_decision_versions()
    _preflight_subflows()
    _create_triggers()


def downgrade() -> None:
    _require_mysql()
    for trigger in _TRIGGERS:
        _drop_trigger(trigger)

    if "ix_disc_case_current_decision" in _indexes(_CASE):
        op.drop_index("ix_disc_case_current_decision", table_name=_CASE)
    if "uk_cs_discipline_active_case" in _indexes(_PROJECTION):
        op.drop_index("uk_cs_discipline_active_case", table_name=_PROJECTION)
    if "uk_cs_service_student_active" in _indexes(_CS_STUDENT):
        op.drop_index("uk_cs_service_student_active", table_name=_CS_STUDENT)

    if "active_source_case_id" in _columns(_PROJECTION):
        op.drop_column(_PROJECTION, "active_source_case_id")
    if "active_student_id" in _columns(_CS_STUDENT):
        op.drop_column(_CS_STUDENT, "active_student_id")
    for table, columns in (
        (_PROJECTION, ("decision_version_no", "decision_version_id")),
        (_CASE, ("current_decision_version_no", "current_decision_version_id")),
    ):
        existing = _columns(table)
        for column in columns:
            if column in existing:
                op.drop_column(table, column)

    if _has_table(_SUBFLOW):
        op.drop_table(_SUBFLOW)
    if _has_table(_DECISION):
        op.drop_table(_DECISION)
