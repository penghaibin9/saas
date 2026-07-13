"""迎新分宿 → 宿舍台账初始化导入测试（P8 上线检查单 §5 item4）。

覆盖：已分配迎新学生被占床 + 回写 t_cs_dorm_record；幂等（二次运行不重复占床）；
dry_run 不落库；未分配/未关联学生不纳入。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import func, select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

TID = 1000000000000000091


def _seed_orientation(db, allocated=2, unassigned=1):
    """建 allocated 个已分配（同楼同房 101）+ unassigned 个未分配迎新学生。返回已分配 student_id 列表。"""
    from app.models import OrientationStudent, StudentProfile
    ids = []
    for i in range(1, allocated + unassigned + 1):
        sp = StudentProfile(tenant_id=TID, student_no=f"2026O{i:04d}", real_name=f"新生{i}",
                            gender="男", current_stage="ON_CAMPUS", student_status="NORMAL", status="ACTIVE")
        db.add(sp); db.flush()
        is_alloc = i <= allocated
        db.add(OrientationStudent(
            tenant_id=TID, name=f"新生{i}", admission_no=f"LQ2026O{i:04d}", student_id=sp.id,
            class_name="电商2601班", grade="2026级", stage="ENROLLED",
            dorm_status="CHECKED_IN" if is_alloc else "UNASSIGNED",
            building="1号楼" if is_alloc else None, room="101" if is_alloc else None))
        if is_alloc:
            ids.append(sp.id)
    db.commit()
    return ids


@pytest.fixture()
def orient_seeded(db_mode):
    from app.db.session import get_sessionmaker
    db = get_sessionmaker()()
    try:
        ids = _seed_orientation(db)
    finally:
        db.close()
    return ids


def _occupied_beds(db):
    from app.models import DormBed
    return db.scalar(select(func.count()).select_from(DormBed).where(
        DormBed.tenant_id == TID, DormBed.status == "OCCUPIED")) or 0


def _dorm_records(db):
    from app.models import CsDormRecord
    return db.scalar(select(func.count()).select_from(CsDormRecord).where(
        CsDormRecord.tenant_id == TID, CsDormRecord.status == "IN")) or 0


def test_init_assigns_beds_and_writesback(orient_seeded):
    from app.db.session import get_sessionmaker
    from init_orientation_dorm import init_orientation_dorm
    db = get_sessionmaker()()
    try:
        rep = init_orientation_dorm(db, TID, dry_run=False)
        assert rep["candidates"] == 2        # 仅 2 个已分配纳入（未分配排除）
        assert rep["assigned"] == 2
        assert rep["buildings"] == 1 and rep["rooms"] == 1
        assert _occupied_beds(db) == 2       # 两床占用
        assert _dorm_records(db) == 2        # 回写"我的宿舍"两条 IN
    finally:
        db.close()


def test_init_is_idempotent(orient_seeded):
    from app.db.session import get_sessionmaker
    from init_orientation_dorm import init_orientation_dorm
    db = get_sessionmaker()()
    try:
        init_orientation_dorm(db, TID, dry_run=False)
        before = _occupied_beds(db)
        rep2 = init_orientation_dorm(db, TID, dry_run=False)  # 二次运行
        assert rep2["assigned"] == 0 and rep2["skipped_housed"] == 2
        assert _occupied_beds(db) == before  # 不重复占床
    finally:
        db.close()


def test_init_dry_run_no_persist(orient_seeded):
    from app.db.session import get_sessionmaker
    from init_orientation_dorm import init_orientation_dorm
    db = get_sessionmaker()()
    try:
        rep = init_orientation_dorm(db, TID, dry_run=True)
        assert rep["assigned"] == 2          # 报告显示将占 2 床
    finally:
        db.close()
    db2 = get_sessionmaker()()
    try:
        assert _occupied_beds(db2) == 0      # dry_run 未落库
    finally:
        db2.close()
