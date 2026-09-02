"""Orientation O1: batch, stable organization and source authority.

Revision ID: 20260901_orientation_batch_o1
Revises: 20260831_iam_alias_backfill

The legacy ``class_id`` column is a varchar and contains a mixture of numeric
ids and local codes.  It is preserved as ``class_ref_legacy``.  The new
``class_id`` is a stable bigint organization id; ambiguous or unmapped legacy
values are recorded in a migration issue table and are never guessed by name.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

revision = "20260901_orientation_batch_o1"
down_revision = "20260831_iam_alias_backfill"
branch_labels = None
depends_on = None

assert len(revision) <= 32

STUDENT = "t_orientation_student"
BATCH = "t_orientation_batch"
ISSUE = "t_orientation_o1_backfill_issue"


def _require_mysql() -> None:
    if op.get_bind().dialect.name != "mysql":
        raise RuntimeError("20260901_orientation_batch_o1 requires MySQL")


def _columns(table: str) -> dict[str, dict]:
    return {str(row["name"]): row for row in inspect(op.get_bind()).get_columns(table)}


def _index_names(table: str) -> set[str]:
    return {str(row["name"]) for row in inspect(op.get_bind()).get_indexes(table)}


def _unique_names(table: str) -> set[str]:
    return {str(row["name"]) for row in inspect(op.get_bind()).get_unique_constraints(table)}


def _expand() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    tables = set(insp.get_table_names())
    required = {STUDENT, BATCH, "t_student_profile", "t_class", "t_major", "t_college"}
    missing = sorted(required - tables)
    if missing:
        raise RuntimeError("O1 requires existing authority tables: " + ",".join(missing))

    cols = _columns(STUDENT)
    if "class_ref_legacy" not in cols:
        if "class_id" not in cols:
            raise RuntimeError("legacy t_orientation_student.class_id is missing")
        op.alter_column(
            STUDENT,
            "class_id",
            new_column_name="class_ref_legacy",
            existing_type=sa.String(50),
            existing_nullable=True,
            comment="O1 前字符串班级引用，只读兼容快照",
        )
        cols = _columns(STUDENT)

    additions = {
        "batch_id": sa.Column(
            "batch_id", sa.BigInteger(), nullable=True,
            comment="迎新批次 Authority → t_orientation_batch.id",
        ),
        "college_id": sa.Column(
            "college_id", sa.BigInteger(), nullable=True, comment="稳定学院 ID → t_college.id"
        ),
        "major_id": sa.Column(
            "major_id", sa.BigInteger(), nullable=True, comment="稳定专业 ID → t_major.id"
        ),
        "class_id": sa.Column(
            "class_id", sa.BigInteger(), nullable=True, comment="稳定班级 ID → t_class.id"
        ),
        "admission_type": sa.Column(
            "admission_type", sa.String(50), nullable=True, comment="录取类型"
        ),
        "source_type": sa.Column(
            "source_type", sa.String(50), nullable=False, server_default="LEGACY_BACKFILL",
            comment="MANUAL/DOMAIN_IMPORT/LEGACY_BACKFILL",
        ),
        "source_record_id": sa.Column(
            "source_record_id", sa.String(200), nullable=True, comment="批次内来源业务键"
        ),
        "identity_status": sa.Column(
            "identity_status", sa.String(50), nullable=False, server_default="UNLINKED",
            comment="UNLINKED/LINKED；是否已绑定 StudentProfile",
        ),
    }
    for name, column in additions.items():
        if name not in cols:
            op.add_column(STUDENT, column)

    if ISSUE not in tables:
        op.create_table(
            ISSUE,
            sa.Column("orientation_student_id", sa.BigInteger(), primary_key=True),
            sa.Column("tenant_id", sa.BigInteger(), nullable=False, index=True),
            sa.Column("issue_code", sa.String(50), nullable=False),
            sa.Column("legacy_class_ref", sa.String(50), nullable=True),
            sa.Column("detail", sa.String(500), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            mysql_engine="InnoDB",
            mysql_charset="utf8mb4",
        )


def _year(value: object) -> str:
    match = re.search(r"(19|20)\d{2}", str(value or ""))
    return match.group(0) if match else "UNKNOWN"


def _backfill_batches() -> None:
    bind = op.get_bind()
    rows = list(bind.execute(text(
        f"SELECT id, tenant_id, admission_no, grade FROM {STUDENT} "
        "WHERE batch_id IS NULL ORDER BY tenant_id, id"
    )).mappings())
    groups: dict[tuple[int, str], list[dict]] = defaultdict(list)
    for row in rows:
        groups[(int(row["tenant_id"]), _year(row["grade"]))].append(dict(row))

    now = datetime.utcnow()
    for (tenant_id, year), members in groups.items():
        batch_no = f"__O1_LEGACY_{year}__"
        existing = bind.execute(text(
            f"SELECT id, remark FROM {BATCH} "
            "WHERE tenant_id=:tenant_id AND batch_no=:batch_no LIMIT 1"
        ), {"tenant_id": tenant_id, "batch_no": batch_no}).mappings().first()
        if existing:
            if not str(existing["remark"] or "").startswith("O1 migration backfill"):
                raise RuntimeError(
                    f"reserved O1 batch number already exists for tenant={tenant_id}, year={year}"
                )
            batch_id = int(existing["id"])
        else:
            result = bind.execute(text(
                f"INSERT INTO {BATCH} "
                "(batch_name,batch_no,year,status,planned_count,remark,tenant_id,"
                "updated_at,is_deleted,version,created_at) "
                "VALUES (:name,:batch_no,:year,'CLOSED',:planned_count,:remark,:tenant_id,"
                ":now,0,1,:now)"
            ), {
                "name": f"O1历史名单回填（{year}）",
                "batch_no": batch_no,
                "year": None if year == "UNKNOWN" else year,
                "planned_count": len(members),
                "remark": "O1 migration backfill; historical rows only; do not reuse for new imports",
                "tenant_id": tenant_id,
                "now": now,
            })
            batch_id = int(result.lastrowid)

        ids = [int(row["id"]) for row in members]
        bind.execute(text(
            f"UPDATE {STUDENT} SET batch_id=:batch_id, source_type='LEGACY_BACKFILL', "
            "source_record_id=admission_no WHERE tenant_id=:tenant_id AND id IN :ids"
        ).bindparams(sa.bindparam("ids", expanding=True)), {
            "batch_id": batch_id,
            "tenant_id": tenant_id,
            "ids": ids,
        })


def _write_issue(row: dict, code: str, detail: str) -> None:
    op.get_bind().execute(text(
        f"INSERT INTO {ISSUE} "
        "(orientation_student_id,tenant_id,issue_code,legacy_class_ref,detail,created_at) "
        "VALUES (:student_id,:tenant_id,:issue_code,:legacy_ref,:detail,:created_at) "
        "ON DUPLICATE KEY UPDATE issue_code=VALUES(issue_code),"
        "legacy_class_ref=VALUES(legacy_class_ref),detail=VALUES(detail)"
    ), {
        "student_id": int(row["id"]),
        "tenant_id": int(row["tenant_id"]),
        "issue_code": code,
        "legacy_ref": row.get("class_ref_legacy"),
        "detail": detail[:500],
        "created_at": datetime.utcnow(),
    })


def _backfill_organization() -> None:
    bind = op.get_bind()
    # A linked StudentProfile is an explicit stable identity bridge.  Only a
    # complete, same-tenant organization chain may be copied.
    bind.execute(text(f"""
        UPDATE {STUDENT} o
        JOIN t_student_profile s
          ON s.id=o.student_id AND s.tenant_id=o.tenant_id AND s.is_deleted=0
        JOIN t_class c
          ON c.id=s.class_id AND c.tenant_id=o.tenant_id AND c.is_deleted=0
        JOIN t_major m
          ON m.id=c.major_id AND m.tenant_id=o.tenant_id AND m.is_deleted=0
        JOIN t_college g
          ON g.id=m.college_id AND g.tenant_id=o.tenant_id AND g.is_deleted=0
        SET o.class_id=c.id, o.major_id=m.id, o.college_id=g.id
        WHERE o.class_id IS NULL
    """))

    classes = list(bind.execute(text("""
        SELECT c.id, c.tenant_id, c.class_code, c.major_id, m.college_id
        FROM t_class c
        JOIN t_major m
          ON m.id=c.major_id AND m.tenant_id=c.tenant_id AND m.is_deleted=0
        JOIN t_college g
          ON g.id=m.college_id AND g.tenant_id=c.tenant_id AND g.is_deleted=0
        WHERE c.is_deleted=0
    """)).mappings())
    by_id: dict[tuple[int, int], dict] = {}
    by_code: dict[tuple[int, str], list[dict]] = defaultdict(list)
    for row in classes:
        item = dict(row)
        by_id[(int(row["tenant_id"]), int(row["id"]))] = item
        code = str(row["class_code"] or "").strip()
        if code:
            by_code[(int(row["tenant_id"]), code)].append(item)

    unresolved = list(bind.execute(text(
        f"SELECT id, tenant_id, class_ref_legacy FROM {STUDENT} "
        "WHERE class_id IS NULL ORDER BY tenant_id, id"
    )).mappings())
    for raw in unresolved:
        row = dict(raw)
        tenant_id = int(row["tenant_id"])
        legacy = str(row["class_ref_legacy"] or "").strip()
        target = None
        if legacy.isdigit():
            target = by_id.get((tenant_id, int(legacy)))
        if target is None and legacy:
            candidates = by_code.get((tenant_id, legacy), [])
            if len(candidates) == 1:
                target = candidates[0]
            elif len(candidates) > 1:
                _write_issue(row, "CLASS_CODE_AMBIGUOUS", "同租户班级代码存在多条，禁止自动选择")
                continue
        if target is None:
            code = "CLASS_REF_MISSING" if not legacy else "CLASS_REF_UNRESOLVED"
            _write_issue(row, code, "未找到可证明的同租户稳定班级映射；名称快照不参与自动回填")
            continue
        bind.execute(text(
            f"UPDATE {STUDENT} SET class_id=:class_id, major_id=:major_id, college_id=:college_id "
            "WHERE id=:student_id AND tenant_id=:tenant_id AND class_id IS NULL"
        ), {
            "class_id": int(target["id"]),
            "major_id": int(target["major_id"]),
            "college_id": int(target["college_id"]),
            "student_id": int(row["id"]),
            "tenant_id": tenant_id,
        })


def _backfill_identity_status() -> None:
    op.get_bind().execute(text(
        f"UPDATE {STUDENT} SET identity_status="
        "CASE WHEN student_id IS NULL THEN 'UNLINKED' ELSE 'LINKED' END"
    ))


def _validate_and_contract() -> None:
    bind = op.get_bind()
    missing = int(bind.execute(text(
        f"SELECT COUNT(*) FROM {STUDENT} "
        "WHERE batch_id IS NULL OR source_type IS NULL OR source_record_id IS NULL "
        "OR identity_status NOT IN ('UNLINKED','LINKED') "
        "OR (student_id IS NULL AND identity_status<>'UNLINKED') "
        "OR (student_id IS NOT NULL AND identity_status<>'LINKED')"
    )).scalar() or 0)
    batch_cross_tenant = int(bind.execute(text(f"""
        SELECT COUNT(*) FROM {STUDENT} o
        LEFT JOIN {BATCH} b ON b.id=o.batch_id AND b.tenant_id=o.tenant_id
        WHERE b.id IS NULL
    """)).scalar() or 0)
    org_mismatch = int(bind.execute(text(f"""
        SELECT COUNT(*) FROM {STUDENT} o
        LEFT JOIN t_class c ON c.id=o.class_id AND c.tenant_id=o.tenant_id AND c.is_deleted=0
        LEFT JOIN t_major m ON m.id=o.major_id AND m.tenant_id=o.tenant_id AND m.is_deleted=0
        LEFT JOIN t_college g ON g.id=o.college_id AND g.tenant_id=o.tenant_id AND g.is_deleted=0
        WHERE o.class_id IS NOT NULL
          AND (c.id IS NULL OR m.id IS NULL OR g.id IS NULL
               OR c.major_id<>o.major_id OR m.college_id<>o.college_id)
    """)).scalar() or 0)
    duplicate_source = int(bind.execute(text(f"""
        SELECT COUNT(*) FROM (
          SELECT tenant_id,batch_id,source_type,source_record_id
          FROM {STUDENT}
          GROUP BY tenant_id,batch_id,source_type,source_record_id
          HAVING COUNT(*)>1
        ) d
    """)).scalar() or 0)
    if missing or batch_cross_tenant or org_mismatch or duplicate_source:
        raise RuntimeError(
            "O1 validation failed: "
            f"missing={missing}, batch_cross_tenant={batch_cross_tenant}, "
            f"org_mismatch={org_mismatch}, duplicate_source={duplicate_source}"
        )

    op.alter_column(
        STUDENT, "batch_id", existing_type=sa.BigInteger(), nullable=False, existing_nullable=True,
        existing_comment="迎新批次 Authority → t_orientation_batch.id",
    )
    op.alter_column(
        STUDENT, "source_record_id", existing_type=sa.String(200), nullable=False, existing_nullable=True,
        existing_comment="批次内来源业务键",
    )
    op.alter_column(
        STUDENT,
        "source_type",
        existing_type=sa.String(50),
        nullable=False,
        server_default=None,
        existing_server_default="LEGACY_BACKFILL",
        existing_comment="MANUAL/DOMAIN_IMPORT/LEGACY_BACKFILL",
    )
    op.alter_column(
        STUDENT,
        "identity_status",
        existing_type=sa.String(50),
        nullable=False,
        server_default=None,
        existing_server_default="UNLINKED",
        existing_comment="UNLINKED/LINKED；是否已绑定 StudentProfile",
    )

    indexes = _index_names(STUDENT)
    if "ix_ori_student_batch_active" not in indexes:
        op.create_index(
            "ix_ori_student_batch_active", STUDENT, ["tenant_id", "batch_id", "is_deleted"]
        )
    if "ix_ori_student_org_active" not in indexes:
        op.create_index(
            "ix_ori_student_org_active",
            STUDENT,
            ["tenant_id", "college_id", "major_id", "class_id", "is_deleted"],
        )
    if "uk_ori_batch_source_record" not in _unique_names(STUDENT):
        op.create_unique_constraint(
            "uk_ori_batch_source_record",
            STUDENT,
            ["tenant_id", "batch_id", "source_type", "source_record_id"],
        )


def upgrade() -> None:
    _require_mysql()
    _expand()
    _backfill_batches()
    _backfill_organization()
    _backfill_identity_status()
    _validate_and_contract()


def downgrade() -> None:
    _require_mysql()
    bind = op.get_bind()
    if STUDENT not in inspect(bind).get_table_names():
        return

    cols = _columns(STUDENT)
    if "class_ref_legacy" in cols and "class_id" in cols:
        bind.execute(text(
            f"UPDATE {STUDENT} SET class_ref_legacy=CAST(class_id AS CHAR) "
            "WHERE class_ref_legacy IS NULL AND class_id IS NOT NULL"
        ))
    uniques = _unique_names(STUDENT)
    if "uk_ori_batch_source_record" in uniques:
        op.drop_constraint("uk_ori_batch_source_record", STUDENT, type_="unique")
    indexes = _index_names(STUDENT)
    for name in ("ix_ori_student_org_active", "ix_ori_student_batch_active"):
        if name in indexes:
            op.drop_index(name, table_name=STUDENT)

    cols = _columns(STUDENT)
    for name in (
        "identity_status", "source_record_id", "source_type", "admission_type",
        "college_id", "major_id", "class_id", "batch_id",
    ):
        if name in cols:
            op.drop_column(STUDENT, name)
    cols = _columns(STUDENT)
    if "class_ref_legacy" in cols and "class_id" not in cols:
        op.alter_column(
            STUDENT,
            "class_ref_legacy",
            new_column_name="class_id",
            existing_type=sa.String(50),
            existing_nullable=True,
        )
    bind.execute(text(
        f"DELETE FROM {BATCH} WHERE batch_no LIKE '__O1\\_LEGACY\\_%' ESCAPE '\\\\' "
        "AND remark LIKE 'O1 migration backfill%'"
    ))
    if ISSUE in inspect(bind).get_table_names():
        op.drop_table(ISSUE)
