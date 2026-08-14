"""岗位实习 V9.3 迁移上线预检（**只读**，不改任何数据）。

用法：
  python -m scripts.check_internship_v93_migration_readiness

为什么需要它：本批次新增的三条迁移里，`20260814_ix_first_create` 会在发现"同一实习记录
存在多条同时活动的记录"时**主动拒绝执行**——因为那些是学生真实提交的申请，删哪条该由学校
决定，不是迁移脚本能替他们做主的。

那个设计是对的，但意味着上线当天可能会卡住。这个脚本让你**提前**知道会不会卡、卡在哪几条，
好在停机窗口之前就把清单发给学校确认。

本脚本会报告四件事：
1. 三条迁移是否已经应用（看 alembic_version）；
2. 会不会被脏数据拦下——逐条列出冲突分组，附带学号/姓名，学校能直接照着看；
3. 索引补齐迁移要动几张表、各有多少行（估算停机耗时的依据）；
4. 特殊备案的四个新列是否已存在。

退出码：0 = 可以放心升级；1 = 存在会拦住迁移的脏数据，需要学校先决策。
"""
from __future__ import annotations

import sys

from sqlalchemy import text

from app.db.session import db_enabled, get_sessionmaker

#: 与 20260814_ix_first_create 的 _SPECS 保持一致；改那边务必同步改这里
#: 活动状态谓词里的 {a} 是表别名占位符：单表分组查询填空串，JOIN 明细查询填 "t."。
#: 不带别名的话，明细查询 JOIN 了同样有 status 列的 t_internship_record，MySQL 直接报
#: 1052 ambiguous——只测"无冲突"的顺利路径发现不了。
_ACTIVE_SPECS = (
    ("t_internship_change_request", "internship_id", "{a}status = 'PENDING'", (), "变更申请"),
    ("t_internship_intention", "record_id", "{a}status IN ('DRAFT', 'SUBMITTED')", (), "实习意向"),
    ("t_internship_compliance_exemption", "internship_id", "{a}status = 'PENDING_REVIEW'",
     ("check_code",), "合规豁免"),
)

#: 索引补齐迁移涉及的表（20260814_ix_missing_idx）
_INDEX_TABLES = (
    "t_internship_compliance_exemption", "t_internship_compliance_template",
    "t_internship_consent", "t_internship_emergency_plan",
    "t_internship_enterprise_inspection", "t_internship_evidence_package",
    "t_internship_incident", "t_internship_record",
    "t_internship_remuneration_record", "t_internship_safety_completion",
    "t_internship_safety_course", "t_internship_score_config",
    "t_internship_special_filing",
)

_REVISIONS = ("20260814_ix_filing_actor_cols", "20260814_ix_first_create",
              "20260814_ix_missing_idx")

_FILING_COLUMNS = ("requested_by_name", "requested_by_user_id",
                   "reviewed_by_name", "reviewed_at")


def _table_exists(db, table: str) -> bool:
    return bool(db.execute(text("""
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_schema = DATABASE() AND table_name = :t"""), {"t": table}).scalar())


def _row_count(db, table: str) -> int:
    return int(db.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0)


def _current_revision(db) -> str:
    if not _table_exists(db, "alembic_version"):
        return "(无 alembic_version 表)"
    return str(db.execute(text("SELECT version_num FROM alembic_version")).scalar() or "")


def _scan_conflicts(db, table, source_col, active_sql, extra):
    """列出会拦住迁移的冲突分组，带上学号/姓名方便学校直接核对。"""
    group_cols = ", ".join(("tenant_id", source_col, *extra))
    groups = db.execute(text(f"""
        SELECT {group_cols}, COUNT(*) AS c
        FROM {table}
        WHERE is_deleted = 0 AND {active_sql.format(a="")}
        GROUP BY {group_cols}
        HAVING c > 1
        ORDER BY c DESC
        LIMIT 200
    """)).mappings().all()
    detailed = []
    for g in groups:
        rows = db.execute(text(f"""
            SELECT t.id, t.created_at, s.student_no, s.real_name
            FROM {table} t
            LEFT JOIN t_internship_record r ON r.id = t.{source_col}
            LEFT JOIN t_student_profile s ON s.id = r.student_id
            WHERE t.is_deleted = 0 AND {active_sql.format(a="t.")}
              AND t.tenant_id = :tid AND t.{source_col} = :sid
            ORDER BY t.created_at
        """), {"tid": g["tenant_id"], "sid": g[source_col]}).mappings().all()
        detailed.append({"group": dict(g), "rows": [dict(r) for r in rows]})
    return detailed


def main() -> int:
    if not db_enabled():
        print("DB 未启用，无法预检")
        return 1

    db = get_sessionmaker()()
    blocked = False
    try:
        print("=" * 72)
        print("岗位实习 V9.3 迁移上线预检（只读）")
        print("=" * 72)

        current = _current_revision(db)
        print(f"\n[1] 当前 alembic 版本：{current}")
        for rev in _REVISIONS:
            print(f"    {'已应用' if current == rev else '待应用/未知'}  {rev}")

        print("\n[2] 会不会被脏数据拦住（20260814_ix_first_create）")
        for table, source_col, active_sql, extra, label in _ACTIVE_SPECS:
            if not _table_exists(db, table):
                print(f"    - {label}（{table}）：表不存在，跳过")
                continue
            conflicts = _scan_conflicts(db, table, source_col, active_sql, extra)
            if not conflicts:
                print(f"    OK  {label}：无冲突")
                continue
            blocked = True
            print(f"    拦截 {label}：{len(conflicts)} 组同时活动的重复记录，迁移会停下来")
            for item in conflicts[:20]:
                g = item["group"]
                who = ""
                for r in item["rows"]:
                    if r.get("student_no"):
                        who = f"{r['student_no']} {r.get('real_name') or ''}".strip()
                        break
                print(f"        · {source_col}={g[source_col]} 共 {g['c']} 条"
                      + (f"（{who}）" if who else ""))
                for r in item["rows"]:
                    print(f"            id={r['id']} 创建于 {r['created_at']}")
            if len(conflicts) > 20:
                print(f"        …… 另有 {len(conflicts) - 20} 组未列出")

        print("\n[3] 索引补齐涉及的表与数据量（20260814_ix_missing_idx）")
        total = 0
        for table in _INDEX_TABLES:
            if not _table_exists(db, table):
                print(f"    - {table}：表不存在，跳过")
                continue
            n = _row_count(db, table)
            total += n
            print(f"    {n:>10,} 行  {table}")
        print(f"    合计 {total:,} 行；行数越少 ALTER 越快，建议仍在生产快照上实测计时")

        print("\n[4] 特殊备案的四个新列（20260814_ix_filing_actor_cols）")
        if _table_exists(db, "t_internship_special_filing"):
            have = {r[0] for r in db.execute(text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = DATABASE() AND table_name = 't_internship_special_filing'
            """)).all()}
            for col in _FILING_COLUMNS:
                print(f"    {'已存在' if col in have else '待补齐'}  {col}")
        else:
            print("    表不存在，跳过")

        print("\n" + "=" * 72)
        if blocked:
            print("结论：存在会拦住迁移的重复数据。")
            print("这些是学生真实提交的申请，请先由学校决定每组保留哪一条")
            print("（把多余的置为已撤回/已驳回即可，不要直接删除），再执行升级。")
        else:
            print("结论：无阻断项，可以执行 alembic upgrade head。")
        print("=" * 72)
        return 1 if blocked else 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
