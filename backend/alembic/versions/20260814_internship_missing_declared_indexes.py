"""补齐存量库缺失的 49 个 ORM 已声明索引（新库/老库两条路径产出不同 schema）

Revision ID: 20260814_ix_missing_idx
Revises: 20260814_ix_first_create
Create Date: 2026-08-14

批次二的索引审计发现：合规域这批表在**开发库**里只有主键，连 `tenant_id` 都没有索引；
但在跑完整迁移链的**全新库**里，这些索引是齐的。两条建库路径产出了不同的 schema：

- **全新库**：表来自冻结基线 `alembic/frozen/0001_baseline_mysql.sql`（当年由
  `metadata.create_all()` materialize），快照里**带**索引；
- **存量库**：建库时这些表还不存在，是后来由 `0131_internship_p2_compliance.py` 补建的，
  而它的 `_create()` helper 只建列和唯一约束、**从不调用 `op.create_index`**，
  于是 ORM 里写的 `index=True` / `Index(...)` 全部落空。

**所以缺不缺索引取决于学校的库是什么时候建的**：新部署的没事；从 0131 之前一路升上来的
（和我们的开发库一样）就缺。这正是本仓 §架构审计 记过的"迁移双路径 schema 差异"同一类问题。

EXPLAIN 实测（缺索引的开发库）：知情同意查重、特殊备案查重、合规豁免列表三条查询
全部 `type=ALL / possible_keys=NULL / key=NULL`——全表扫描，连可用索引都没有。

**这不只是性能问题。** 批次二实测的豁免 MySQL 死锁(1213→500) 就是它引起的：
没有索引时 InnoDB 只能全表扫描加锁，两个线程的加锁顺序不定就互等。

**还有一个更隐蔽的后果**：测试夹具用 `create_all()` 建库（**有**这些索引），真实库走
alembic（**没有**）。两边加锁行为不同，意味着测试库上测出的并发结论无法外推到真实库。
补齐之后两者才一致。

本迁移**不新增任何索引设计**，只把 ORM 早就声明、存量库漏建的那 49 个补上——
不是"觉得该加就加"，是让两条建库路径收敛到同一个 schema。
全新库上执行时会发现绝大多数已存在而跳过（实测 created=1/49）；
存量库形态上执行才会真正补齐（实测 created=49/49）。

注意：在已有数据的学校库上执行会有真实耗时（每张表一次 ALTER）。这批表当前数据量都很小，
上线前仍建议在生产快照上先跑一次计时。
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260814_ix_missing_idx"
down_revision = "20260814_ix_first_create"
branch_labels = None
depends_on = None

#: (表名, 索引名, 列清单) —— 与 ORM 声明逐条对齐，由 information_schema 差集生成
_MISSING = (
    ("t_internship_compliance_exemption", "ix_ix_exempt_intern", ['tenant_id', 'internship_id', 'check_code', 'is_deleted']),
    ("t_internship_compliance_exemption", "ix_t_internship_compliance_exemption_batch_id", ['batch_id']),
    ("t_internship_compliance_exemption", "ix_t_internship_compliance_exemption_internship_id", ['internship_id']),
    ("t_internship_compliance_exemption", "ix_t_internship_compliance_exemption_tenant_id", ['tenant_id']),
    ("t_internship_compliance_template", "ix_t_internship_compliance_template_template_code", ['template_code']),
    ("t_internship_compliance_template", "ix_t_internship_compliance_template_tenant_id", ['tenant_id']),
    ("t_internship_consent", "ix_ix_consent_intern", ['tenant_id', 'internship_id', 'consent_type', 'is_deleted']),
    ("t_internship_consent", "ix_t_internship_consent_batch_id", ['batch_id']),
    ("t_internship_consent", "ix_t_internship_consent_content_hash", ['content_hash']),
    ("t_internship_consent", "ix_t_internship_consent_internship_id", ['internship_id']),
    ("t_internship_consent", "ix_t_internship_consent_student_id", ['student_id']),
    ("t_internship_consent", "ix_t_internship_consent_tenant_id", ['tenant_id']),
    ("t_internship_emergency_plan", "ix_ix_emerg_company", ['tenant_id', 'company_id', 'is_deleted']),
    ("t_internship_emergency_plan", "ix_t_internship_emergency_plan_batch_id", ['batch_id']),
    ("t_internship_emergency_plan", "ix_t_internship_emergency_plan_company_id", ['company_id']),
    ("t_internship_emergency_plan", "ix_t_internship_emergency_plan_tenant_id", ['tenant_id']),
    ("t_internship_enterprise_inspection", "ix_ix_ent_insp_tenant_company", ['tenant_id', 'company_id', 'is_deleted']),
    ("t_internship_enterprise_inspection", "ix_t_internship_enterprise_inspection_batch_id", ['batch_id']),
    ("t_internship_enterprise_inspection", "ix_t_internship_enterprise_inspection_company_id", ['company_id']),
    ("t_internship_enterprise_inspection", "ix_t_internship_enterprise_inspection_tenant_id", ['tenant_id']),
    ("t_internship_evidence_package", "ix_ix_evpkg_target", ['tenant_id', 'package_type', 'target_id', 'is_deleted']),
    ("t_internship_evidence_package", "ix_t_internship_evidence_package_batch_id", ['batch_id']),
    ("t_internship_evidence_package", "ix_t_internship_evidence_package_tenant_id", ['tenant_id']),
    ("t_internship_incident", "ix_ix_incident_batch", ['tenant_id', 'batch_id', 'is_deleted']),
    ("t_internship_incident", "ix_t_internship_incident_batch_id", ['batch_id']),
    ("t_internship_incident", "ix_t_internship_incident_company_id", ['company_id']),
    ("t_internship_incident", "ix_t_internship_incident_idempotency_key", ['idempotency_key']),
    ("t_internship_incident", "ix_t_internship_incident_internship_id", ['internship_id']),
    ("t_internship_incident", "ix_t_internship_incident_student_id", ['student_id']),
    ("t_internship_incident", "ix_t_internship_incident_tenant_id", ['tenant_id']),
    ("t_internship_record", "ix_t_internship_record_enterprise_id", ['enterprise_id']),
    ("t_internship_record", "ix_t_internship_record_position_id", ['position_id']),
    ("t_internship_remuneration_record", "ix_t_internship_remuneration_record_batch_id", ['batch_id']),
    ("t_internship_remuneration_record", "ix_t_internship_remuneration_record_internship_id", ['internship_id']),
    ("t_internship_remuneration_record", "ix_t_internship_remuneration_record_position_id", ['position_id']),
    ("t_internship_remuneration_record", "ix_t_internship_remuneration_record_tenant_id", ['tenant_id']),
    ("t_internship_safety_completion", "ix_t_internship_safety_completion_batch_id", ['batch_id']),
    ("t_internship_safety_completion", "ix_t_internship_safety_completion_course_id", ['course_id']),
    ("t_internship_safety_completion", "ix_t_internship_safety_completion_internship_id", ['internship_id']),
    ("t_internship_safety_completion", "ix_t_internship_safety_completion_student_id", ['student_id']),
    ("t_internship_safety_completion", "ix_t_internship_safety_completion_tenant_id", ['tenant_id']),
    ("t_internship_safety_course", "ix_t_internship_safety_course_batch_id", ['batch_id']),
    ("t_internship_safety_course", "ix_t_internship_safety_course_tenant_id", ['tenant_id']),
    ("t_internship_score_config", "ix_t_internship_score_config_active_scope_key", ['active_scope_key']),
    ("t_internship_special_filing", "ix_ix_filing_intern", ['tenant_id', 'internship_id', 'is_deleted']),
    ("t_internship_special_filing", "ix_t_internship_special_filing_batch_id", ['batch_id']),
    ("t_internship_special_filing", "ix_t_internship_special_filing_internship_id", ['internship_id']),
    ("t_internship_special_filing", "ix_t_internship_special_filing_student_id", ['student_id']),
    ("t_internship_special_filing", "ix_t_internship_special_filing_tenant_id", ['tenant_id']),

)


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _index_names(table: str) -> set[str]:
    insp = sa.inspect(op.get_bind())
    names = {i["name"] for i in insp.get_indexes(table)}
    names |= {u["name"] for u in insp.get_unique_constraints(table)}
    return {n for n in names if n}


def _index_column_sets(table: str) -> set[tuple]:
    """已存在的索引列组合。名字不同但列组合相同时不该重复建。"""
    insp = sa.inspect(op.get_bind())
    return {tuple(i.get("column_names") or ()) for i in insp.get_indexes(table)}


def upgrade() -> None:
    tables = _tables()
    created = 0
    for table, name, columns in _MISSING:
        if table not in tables:
            continue
        if name in _index_names(table):
            continue
        if tuple(columns) in _index_column_sets(table):
            # 列组合已被另一个名字的索引覆盖，重复建只会浪费写入与空间
            continue
        op.create_index(name, table, list(columns))
        created += 1
    print(f"[20260814_ix_missing_idx] created={created} / declared={len(_MISSING)}")


def downgrade() -> None:
    """故意不删索引。

    这些索引属于 ORM 声明的既有 schema，本迁移只是把存量库缺的那部分补回来。
    如果按名字回删，在**全新库**上回滚会把冻结基线本来就带的 48 个一并删掉——
    那是拿回滚把一个好库弄坏，比不回滚糟得多。

    索引是纯附加物：留着不影响回滚后的旧代码，只多占一点空间。真要清理请单独出一条
    带明确取舍说明的迁移，而不是让它藏在这条的回滚路径里。
    """
    return
