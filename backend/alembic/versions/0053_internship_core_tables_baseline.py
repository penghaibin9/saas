"""岗位实习中心 · 核心表基线迁移。

把历史上仅靠 Base.metadata.create_all 建立、从未纳入 Alembic 版本史的 8 张实习核心表，
在 head 处补成幂等 CREATE，使 `alembic upgrade head` 在全新 MySQL 上也能建出与模型一致的
结构（收口 CLAUDE.md §6.2「数据结构变化必须走迁移、不得长期依赖 create_all」欠账）。

背景（审计事实）：
    t_internship_batch / t_internship_record / t_internship_position / t_internship_checkin /
    t_attendance_exception / t_internship_audit_trail / t_risk_record / t_weekly_report
    这 8 张表早期靠 create_all 建表、无 CREATE 迁移，但 0048/0049/0050 又对其 add_column ——
    干净库上 `alembic upgrade head` 会在这些 ALTER 处因基表不存在而崩（MySQL 1146）。
    本迁移在 head 幂等补建（已存在则整表跳过），并配合 0048/0049/0050 的守卫加固
    （表不存在则跳过 ALTER），使「create_all 现网库增量升级」与「全新库纯迁移建库」两条路径都可用。

Revision ID: 0053_internship_core_baseline
Revises: aa_sandbox_baseline
Create Date: 2026-07-17
"""
from __future__ import annotations

from alembic import op

revision = "0053_internship_core_baseline"
down_revision = "aa_sandbox_baseline"
branch_labels = None
depends_on = None


def _core_tables():
    """返回 8 张待补建表的 SQLAlchemy Table 对象（延迟导入，避免收集阶段即加载全部模型）。

    直接取模型的 __table__，保证补建结构与 create_all 完全一致、不手抄列、永不漂移。
    其余实习表已在 0016~0052 各自 create_table，不在此列。"""
    from app.models import (AttendanceException, InternshipAuditTrail, InternshipBatch,
                            InternshipCheckin, InternshipPosition, InternshipRecord,
                            RiskRecord, WeeklyReport)
    models = (InternshipBatch, InternshipRecord, InternshipPosition, InternshipCheckin,
              AttendanceException, InternshipAuditTrail, RiskRecord, WeeklyReport)
    return [m.__table__ for m in models]


def upgrade() -> None:
    bind = op.get_bind()
    # checkfirst=True → 已由 create_all 建好的现网库整表跳过；全新库按模型建全量结构。
    # 实习模型无 DB 级外键（已核验），逐表 create 顺序无关。
    for table in _core_tables():
        table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    # 基线采纳迁移：这 8 张是承载真实业务数据的核心表，降级不删除以防数据丢失。
    # 如确需回退结构，请单独评估数据迁移后再手工处理，不在本迁移自动 drop。
    pass
