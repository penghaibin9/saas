"""毕设：答辩组/评阅/答辩评分增加稳定 mentor_id，姓名保留为快照。

回填：租户内 teacher_name 唯一命中时写入 mentor_id；重名不回填（fail-closed 留给写路径补齐）。
members_json 字符串在唯一命中时升级为 {mentorId,name,teacherNo}。

Revision ID: 0129_gd_stable_mentor_ids
Revises: 0128_gd_defense_batch_student_uk
"""
from __future__ import annotations

import json
import logging

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect, text

revision = "0129_gd_stable_mentor_ids"
down_revision = "0128_gd_defense_batch_student_uk"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.0129_gd_stable_mentor_ids")


def _has_column(insp, table: str, col: str) -> bool:
    if table not in insp.get_table_names():
        return False
    return any(c["name"] == col for c in insp.get_columns(table))


def _has_index(insp, table: str, name: str) -> bool:
    if table not in insp.get_table_names():
        return False
    return any(ix.get("name") == name for ix in insp.get_indexes(table))


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    if "t_gd_defense_group" in insp.get_table_names():
        if not _has_column(insp, "t_gd_defense_group", "chair_mentor_id"):
            op.add_column(
                "t_gd_defense_group",
                sa.Column("chair_mentor_id", sa.BigInteger(), nullable=True, comment="主席→t_gd_mentor.id"),
            )
        if not _has_column(insp, "t_gd_defense_group", "secretary_mentor_id"):
            op.add_column(
                "t_gd_defense_group",
                sa.Column("secretary_mentor_id", sa.BigInteger(), nullable=True, comment="秘书→t_gd_mentor.id"),
            )
        insp = inspect(bind)
        if not _has_index(insp, "t_gd_defense_group", "ix_gd_defense_chair_mentor"):
            op.create_index("ix_gd_defense_chair_mentor", "t_gd_defense_group", ["chair_mentor_id"])
        if not _has_index(insp, "t_gd_defense_group", "ix_gd_defense_secretary_mentor"):
            op.create_index("ix_gd_defense_secretary_mentor", "t_gd_defense_group", ["secretary_mentor_id"])

    if "t_gd_review" in insp.get_table_names() and not _has_column(insp, "t_gd_review", "reviewer_mentor_id"):
        op.add_column(
            "t_gd_review",
            sa.Column("reviewer_mentor_id", sa.BigInteger(), nullable=True, comment="评阅人→t_gd_mentor.id"),
        )
        op.create_index("ix_gd_review_reviewer_mentor", "t_gd_review", ["reviewer_mentor_id"])

    if "t_gd_defense_score" in insp.get_table_names() and not _has_column(insp, "t_gd_defense_score", "judge_mentor_id"):
        op.add_column(
            "t_gd_defense_score",
            sa.Column("judge_mentor_id", sa.BigInteger(), nullable=True, comment="评委→t_gd_mentor.id"),
        )
        op.create_index("ix_gd_defense_score_judge_mentor", "t_gd_defense_score", ["judge_mentor_id"])

    _backfill(bind)


def _unique_mentor_map(bind) -> dict[tuple[int, str], int]:
    """(tenant_id, teacher_name) → mentor_id，仅唯一姓名。"""
    counts: dict[tuple[int, str], list[int]] = {}
    rows = bind.execute(text(
        "SELECT id, tenant_id, teacher_name FROM t_gd_mentor "
        "WHERE is_deleted = 0 AND teacher_name IS NOT NULL AND teacher_name <> ''"
    )).mappings().all()
    for r in rows:
        key = (int(r["tenant_id"]), str(r["teacher_name"]).strip())
        counts.setdefault(key, []).append(int(r["id"]))
    return {k: ids[0] for k, ids in counts.items() if len(ids) == 1}


def _backfill(bind) -> None:
    if "t_gd_mentor" not in inspect(bind).get_table_names():
        return
    uniq = _unique_mentor_map(bind)
    if not uniq:
        log.info("no unique mentor names for backfill")
        return

    # 答辩组主席/秘书
    if "t_gd_defense_group" in inspect(bind).get_table_names():
        groups = bind.execute(text(
            "SELECT id, tenant_id, chair, secretary, members_json, chair_mentor_id, secretary_mentor_id "
            "FROM t_gd_defense_group WHERE is_deleted = 0"
        )).mappings().all()
        for g in groups:
            tid = int(g["tenant_id"])
            updates = {}
            chair = (g["chair"] or "").strip()
            if not g["chair_mentor_id"] and chair and (tid, chair) in uniq:
                updates["chair_mentor_id"] = uniq[(tid, chair)]
            sec = (g["secretary"] or "").strip()
            if not g["secretary_mentor_id"] and sec and (tid, sec) in uniq:
                updates["secretary_mentor_id"] = uniq[(tid, sec)]
            members_raw = g["members_json"]
            new_members = None
            if members_raw is not None:
                try:
                    members = members_raw if isinstance(members_raw, list) else json.loads(members_raw)
                except (TypeError, ValueError, json.JSONDecodeError):
                    members = None
                if isinstance(members, list):
                    converted = []
                    changed = False
                    for raw in members:
                        if isinstance(raw, dict) and (raw.get("mentorId") or raw.get("id")):
                            converted.append(raw)
                            continue
                        name = raw.strip() if isinstance(raw, str) else str(
                            (raw or {}).get("name") or (raw or {}).get("realName") or ""
                        ).strip() if isinstance(raw, dict) else ""
                        if not name:
                            continue
                        mid = uniq.get((tid, name))
                        if mid:
                            converted.append({"mentorId": str(mid), "name": name, "teacherNo": ""})
                            changed = True
                        else:
                            converted.append(name if isinstance(raw, str) else raw)
                    if changed:
                        new_members = json.dumps(converted, ensure_ascii=False)
            if updates or new_members is not None:
                sets = [f"{k} = :{k}" for k in updates]
                params = {"id": int(g["id"]), **updates}
                if new_members is not None:
                    sets.append("members_json = :members_json")
                    params["members_json"] = new_members
                bind.execute(text(f"UPDATE t_gd_defense_group SET {', '.join(sets)} WHERE id = :id"), params)

    # 评阅
    if "t_gd_review" in inspect(bind).get_table_names():
        reviews = bind.execute(text(
            "SELECT id, tenant_id, reviewer_name FROM t_gd_review "
            "WHERE is_deleted = 0 AND reviewer_mentor_id IS NULL "
            "AND reviewer_name IS NOT NULL AND reviewer_name <> ''"
        )).mappings().all()
        for r in reviews:
            mid = uniq.get((int(r["tenant_id"]), str(r["reviewer_name"]).strip()))
            if mid:
                bind.execute(text(
                    "UPDATE t_gd_review SET reviewer_mentor_id = :mid WHERE id = :id"
                ), {"mid": mid, "id": int(r["id"])})

    # 答辩评分
    if "t_gd_defense_score" in inspect(bind).get_table_names():
        scores = bind.execute(text(
            "SELECT id, tenant_id, judge_name FROM t_gd_defense_score "
            "WHERE is_deleted = 0 AND judge_mentor_id IS NULL "
            "AND judge_name IS NOT NULL AND judge_name <> ''"
        )).mappings().all()
        for r in scores:
            mid = uniq.get((int(r["tenant_id"]), str(r["judge_name"]).strip()))
            if mid:
                bind.execute(text(
                    "UPDATE t_gd_defense_score SET judge_mentor_id = :mid WHERE id = :id"
                ), {"mid": mid, "id": int(r["id"])})


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    for table, col, ix in (
        ("t_gd_defense_score", "judge_mentor_id", "ix_gd_defense_score_judge_mentor"),
        ("t_gd_review", "reviewer_mentor_id", "ix_gd_review_reviewer_mentor"),
        ("t_gd_defense_group", "secretary_mentor_id", "ix_gd_defense_secretary_mentor"),
        ("t_gd_defense_group", "chair_mentor_id", "ix_gd_defense_chair_mentor"),
    ):
        if table not in insp.get_table_names():
            continue
        if _has_index(insp, table, ix):
            op.drop_index(ix, table_name=table)
        if _has_column(insp, table, col):
            op.drop_column(table, col)
        insp = inspect(bind)
