"""Graduation concurrency, idempotency and uniqueness closure.

Revision ID: 0136_gd_concurrency
Revises: 0135_gd_topic_advisor_mentor_id
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

revision = "0136_gd_concurrency"
down_revision = "0135_gd_topic_advisor_mentor_id"
branch_labels = None
depends_on = None


def _columns(bind, table):
    return {c["name"] for c in inspect(bind).get_columns(table)}


def _indexes(bind, table):
    return {i["name"] for i in inspect(bind).get_indexes(table)} | {
        u["name"] for u in inspect(bind).get_unique_constraints(table)
    }


def _add_column(bind, table, column):
    if column.name not in _columns(bind, table):
        op.add_column(table, column)


def _issue(bind, table_name, row_id, issue_type, detail):
    bind.execute(text("""
        INSERT INTO t_gd_migration_issue
          (tenant_id, table_name, row_id, issue_type, detail, status, created_at)
        SELECT tenant_id, :table_name, id, :issue_type, :detail, 'OPEN', NOW()
        FROM %s WHERE id=:row_id
    """ % table_name), {
        "table_name": table_name, "row_id": row_id,
        "issue_type": issue_type, "detail": detail,
    })


def _make_single_active(bind, table, group_column, active_status, active_prefix):
    rows = bind.execute(text(f"""
        SELECT tenant_id, {group_column} AS group_id, GROUP_CONCAT(id ORDER BY id DESC) AS ids
        FROM {table}
        WHERE is_deleted=0 AND status=:status
        GROUP BY tenant_id, {group_column} HAVING COUNT(*) > 1
    """), {"status": active_status}).mappings().all()
    duplicate_count = 0
    for group in rows:
        ids = [int(x) for x in str(group["ids"]).split(",")]
        for row_id in ids[1:]:
            bind.execute(text(
                f"UPDATE {table} SET status='MIGRATION_REVIEW', active_key=NULL WHERE id=:id"
            ), {"id": row_id})
            _issue(bind, table, row_id, "DUPLICATE_ACTIVE",
                   f"canonical={ids[0]}; original_status={active_status}")
            duplicate_count += 1
    bind.execute(text(f"UPDATE {table} SET active_key=NULL"))
    bind.execute(text(f"""
        UPDATE {table}
        SET active_key=CONCAT(:prefix, {group_column})
        WHERE is_deleted=0 AND status=:status
    """), {"prefix": active_prefix, "status": active_status})
    print(f"[0136_gd_concurrency] {table}: resolved active duplicates={duplicate_count}")


def _renumber_versions(bind, table, group_columns):
    groups = ", ".join(group_columns)
    rows = bind.execute(text(
        f"SELECT id, {groups} FROM {table} ORDER BY {groups}, id"
    )).mappings().all()
    last = None
    seq = 0
    for row in rows:
        key = tuple(row[col] for col in group_columns)
        seq = seq + 1 if key == last else 1
        bind.execute(text(f"UPDATE {table} SET version=:version WHERE id=:id"),
                     {"version": f"v{seq}", "id": row["id"]})
        last = key


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name != "mysql":
        raise RuntimeError("0136_gd_concurrency must be validated and executed on MySQL")

    if not inspect(bind).has_table("t_gd_migration_issue"):
        op.create_table(
            "t_gd_migration_issue",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False),
            sa.Column("table_name", sa.String(100), nullable=False),
            sa.Column("row_id", sa.BigInteger(), nullable=False),
            sa.Column("issue_type", sa.String(50), nullable=False),
            sa.Column("detail", sa.String(1000)),
            sa.Column("status", sa.String(20), nullable=False, server_default="OPEN"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )

    _add_column(bind, "t_gd_topic_choice",
                sa.Column("submission_version", sa.Integer(), nullable=False, server_default="1"))
    _add_column(bind, "t_gd_proposal", sa.Column("active_key", sa.String(100)))
    _add_column(bind, "t_gd_final", sa.Column("active_key", sa.String(100)))
    _add_column(bind, "t_gd_plagiarism", sa.Column("active_key", sa.String(100)))
    _add_column(bind, "t_gd_defense_score", sa.Column("expert_id", sa.BigInteger()))
    _add_column(bind, "t_gd_defense_score", sa.Column("judge_identity", sa.String(100)))
    _add_column(bind, "t_gd_peer_review",
                sa.Column("task_version", sa.Integer(), nullable=False, server_default="1"))
    _add_column(bind, "t_gd_grade_appeal", sa.Column("active_key", sa.String(100)))

    _renumber_versions(bind, "t_gd_proposal", ("tenant_id", "gd_student_id"))
    _renumber_versions(bind, "t_gd_final", ("tenant_id", "gd_student_id", "final_type"))
    _make_single_active(bind, "t_gd_proposal", "gd_student_id", "PENDING_REVIEW", "pending:")
    _make_single_active(bind, "t_gd_final", "gd_student_id", "PENDING_REVIEW", "pending:")
    _make_single_active(bind, "t_gd_plagiarism", "gd_final_id", "CHECKING", "checking:")
    _make_single_active(bind, "t_gd_grade_appeal", "gd_student_id", "PENDING", "pending:")
    bind.execute(text("""
        UPDATE t_gd_grade SET status='REVIEWED'
        WHERE status='CALCULATED' AND reviewed_at IS NOT NULL
    """))

    bind.execute(text("""
        UPDATE t_gd_defense_score
        SET judge_identity=CONCAT('MENTOR:', judge_mentor_id)
        WHERE judge_mentor_id IS NOT NULL
    """))
    unresolved = bind.execute(text("""
        SELECT id FROM t_gd_defense_score
        WHERE judge_mentor_id IS NULL AND expert_id IS NULL
    """)).scalars().all()
    for row_id in unresolved:
        _issue(bind, "t_gd_defense_score", row_id, "UNRESOLVED_JUDGE_IDENTITY",
               "姓名快照不能安全推断稳定评委身份")
    print(f"[0136_gd_concurrency] unresolved judge identities={len(unresolved)}")

    # Stable-ID duplicates: keep newest effective key; preserve older snapshots without deleting them.
    duplicate_specs = (
        ("t_gd_review", ("tenant_id", "gd_final_id", "reviewer_mentor_id"),
         "gd_final_id IS NOT NULL AND reviewer_mentor_id IS NOT NULL"),
        ("t_gd_defense_score",
         ("tenant_id", "gd_student_id", "defense_group_id", "round_no", "judge_identity"),
         "judge_identity IS NOT NULL"),
        ("t_gd_peer_review",
         ("tenant_id", "gd_student_id", "reviewer_gd_student_id", "task_version"), "1=1"),
    )
    for table, cols, predicate in duplicate_specs:
        grouping = ", ".join(cols)
        groups = bind.execute(text(f"""
            SELECT GROUP_CONCAT(id ORDER BY id DESC) ids FROM {table}
            WHERE is_deleted=0 AND {predicate}
            GROUP BY {grouping} HAVING COUNT(*) > 1
        """)).scalars().all()
        count = 0
        for value in groups:
            ids = [int(x) for x in str(value).split(",")]
            for history_version, row_id in enumerate(ids[1:], start=2):
                if table == "t_gd_review":
                    bind.execute(text(
                        "UPDATE t_gd_review SET reviewer_mentor_id=NULL WHERE id=:id"
                    ), {"id": row_id})
                elif table == "t_gd_defense_score":
                    bind.execute(text(
                        "UPDATE t_gd_defense_score SET judge_identity=NULL WHERE id=:id"
                    ), {"id": row_id})
                else:
                    bind.execute(text(
                        "UPDATE t_gd_peer_review SET task_version=:version WHERE id=:id"
                    ), {"id": row_id, "version": history_version})
                _issue(bind, table, row_id, "DUPLICATE_STABLE_KEY",
                       f"canonical={ids[0]}; historical snapshot retained")
                count += 1
        print(f"[0136_gd_concurrency] {table}: retained historical duplicates={count}")

    constraints = (
        ("t_gd_proposal", "uk_gd_proposal_student_version",
         ["tenant_id", "gd_student_id", "version"]),
        ("t_gd_proposal", "uk_gd_proposal_active", ["tenant_id", "active_key"]),
        ("t_gd_final", "uk_gd_final_student_type_version",
         ["tenant_id", "gd_student_id", "final_type", "version"]),
        ("t_gd_final", "uk_gd_final_active", ["tenant_id", "active_key"]),
        ("t_gd_plagiarism", "uk_gd_plagiarism_active", ["tenant_id", "active_key"]),
        ("t_gd_review", "uk_gd_review_final_reviewer",
         ["tenant_id", "gd_final_id", "reviewer_mentor_id"]),
        ("t_gd_defense_score", "uk_gd_defense_score_judge",
         ["tenant_id", "gd_student_id", "defense_group_id", "round_no", "judge_identity"]),
        ("t_gd_peer_review", "uk_gd_peer_review_task",
         ["tenant_id", "gd_student_id", "reviewer_gd_student_id", "task_version"]),
        ("t_gd_grade_appeal", "uk_gd_grade_appeal_active", ["tenant_id", "active_key"]),
    )
    for table, name, columns in constraints:
        if name not in _indexes(bind, table):
            op.create_unique_constraint(name, table, columns)


def downgrade():
    bind = op.get_bind()
    constraints = (
        ("t_gd_grade_appeal", "uk_gd_grade_appeal_active"),
        ("t_gd_peer_review", "uk_gd_peer_review_task"),
        ("t_gd_defense_score", "uk_gd_defense_score_judge"),
        ("t_gd_review", "uk_gd_review_final_reviewer"),
        ("t_gd_plagiarism", "uk_gd_plagiarism_active"),
        ("t_gd_final", "uk_gd_final_active"),
        ("t_gd_final", "uk_gd_final_student_type_version"),
        ("t_gd_proposal", "uk_gd_proposal_active"),
        ("t_gd_proposal", "uk_gd_proposal_student_version"),
    )
    for table, name in constraints:
        if name in _indexes(bind, table):
            op.drop_constraint(name, table, type_="unique")
    for table, column in (
        ("t_gd_grade_appeal", "active_key"), ("t_gd_peer_review", "task_version"),
        ("t_gd_defense_score", "judge_identity"), ("t_gd_defense_score", "expert_id"),
        ("t_gd_plagiarism", "active_key"), ("t_gd_final", "active_key"),
        ("t_gd_proposal", "active_key"), ("t_gd_topic_choice", "submission_version"),
    ):
        if column in _columns(bind, table):
            op.drop_column(table, column)
    if inspect(bind).has_table("t_gd_migration_issue"):
        op.drop_table("t_gd_migration_issue")
