#!/usr/bin/env python
"""迁移"时间旅行"门禁：禁止新增 `metadata.create_all` 型迁移。

问题是什么
──────────
正常的 Alembic 迁移是**冻结的历史 DDL**：0001 写死了 2026-07-04 那天的表结构，
之后每个版本只描述增量。任何时候重放这条链，都得到同一个结果。

本项目不是这样。`0001_init_core_tables` 执行的是：

    from app.db.base import metadata
    metadata.create_all(bind=bind)

也就是"用**运行迁移那一天**的 ORM 建表"。同一个 0001，2026-07 跑和今天跑
建出来的结构不一样。而且这不止 0001 —— 全仓有 12 个迁移这么写。

直接后果：
- 老学校（一路升级）和新学校（全新安装）可能跑在不同结构上；
- 后续迁移只能用"表已存在就 return"来兼容，把差异越掩盖越深；
- 历史链无法重放（已实测：从 2026-07-07 / 2026-07-09 两个基线 commit 重放，
  一个撞 alembic_version 列宽、一个撞 down_revision 断链），
  所以**目前没有任何一条被验证过的老库升级路径**。

本门禁做什么
────────────
不假装能一次修好历史（那是一次专门的迁移基线重建），但**冻结现状、禁止变坏**：
已登记的 12 个历史迁移允许保留，任何**新增**的 create_all 型迁移一律拦下。

新表请老老实实写 `op.create_table(...)`，让这条链可重放。

用法：
    python scripts/check/check-migration-time-travel.py
"""
from __future__ import annotations

import sys
from pathlib import Path

VERSIONS = Path(__file__).resolve().parents[2] / "backend" / "alembic" / "versions"

# 历史欠账清单（冻结于 2026-08-10）。只允许**减少**，不允许增加。
# 逐项收口方式：把 create_all 换成显式 op.create_table，并确认对既有库幂等。
KNOWN_CREATE_ALL = {
    "0001_init_core_tables.py",
    "0002_tenant_portal_config.py",
    "0044_13a_psy_referral.py",
    "0051_gd_core_table_baseline.py",
    "0053_internship_core_tables_baseline.py",
    "0070_13b_r4_classroom.py",
    "0106_runtime_preset_masters.py",
    "0142_gd_excellent_delay_workflows.py",
    "20260807_aa_grade_snapshot_cols.py",
    "20260809_aa_academic_fact_c1.py",
    "20260809_password_reset_sms_job.py",
    "4c722c7c33fa_add_t_feedback.py",
}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    if not VERSIONS.is_dir():
        print(f"找不到迁移目录：{VERSIONS}")
        return 2

    found = set()
    for path in sorted(VERSIONS.glob("*.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if "metadata.create_all" in text or "metadata.drop_all" in text:
            found.add(path.name)

    added = sorted(found - KNOWN_CREATE_ALL)
    fixed = sorted(KNOWN_CREATE_ALL - found)

    if added:
        print("❌ 新增了 metadata.create_all / drop_all 型迁移（禁止）：")
        for name in added:
            print(f"   - {name}")
        print("\n迁移必须是冻结的历史 DDL。请改用显式 op.create_table(...)，")
        print("否则同一个版本在不同日期跑会建出不同结构，老库和新库将彻底分裂。")
        return 1

    if fixed:
        print("✅ 以下历史迁移已收口，请从 KNOWN_CREATE_ALL 清单中移除：")
        for name in fixed:
            print(f"   - {name}")
        return 1

    print(f"✅ 无新增 create_all 型迁移（历史欠账仍为 {len(found)} 个，已登记）")
    return 0


if __name__ == "__main__":
    sys.exit(main())

