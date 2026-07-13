"""迎新分宿 → 宿舍台账初始化导入（P8 上线检查单 §5 item4）。

把迎新阶段已分配宿舍的学生（t_orientation_student.building/room，且已关联 student_id）
物化为宿舍三级台账（楼/房/床）并占用床位、回写 t_cs_dorm_record，使"我的宿舍"读链路
与宿管台账从迎新数据一次性对齐。生成器负责"建空床"，本脚本负责"按迎新取数占床"。

设计口径（夜间默认，格式未由学校冻结前的约定 —— 待确认）：
- building = t_orientation_student.building（楼栋名，get-or-create DormBuilding）；
- room    = t_orientation_student.room（房号，get-or-create DormRoom，room_no 原样）；
- floor_no = room 首位数字（"101"→1；无数字→1）；
- 每间默认 default_capacity 张床，床号 f"{room}-{n}"；
- 幂等：学生已占任一床位则跳过；房/床按唯一键 get-or-create，不重复铺床。

安全边界：只操作显式传入的 tenant_id；只处理 building/room/student_id 齐备且
dorm_status ∈ {ASSIGNED, CHECKED_IN} 的迎新行；dry_run 只统计不落库。

用法：
    python scripts/init_orientation_dorm.py --tenant <tenant_id> --dry-run
    python scripts/init_orientation_dorm.py --tenant <tenant_id> --confirm
"""
from __future__ import annotations

import argparse
from datetime import datetime

from sqlalchemy import select

ALLOCATED_STATUSES = ("ASSIGNED", "CHECKED_IN")


def _floor_of(room: str) -> int:
    room = (room or "").strip()
    return int(room[0]) if room and room[0].isdigit() else 1


def _cs_student_id(db, tenant_id, student_id):
    """student_profile.id → CsServiceStudent.id（无则回退 student_id，与 dorm_service 一致）。"""
    from app.models import CsServiceStudent
    cs = db.scalars(select(CsServiceStudent).where(
        CsServiceStudent.tenant_id == tenant_id, CsServiceStudent.student_id == int(student_id),
        CsServiceStudent.is_deleted.is_(False))).first()
    return cs.id if cs else int(student_id)


def _get_or_create_building(db, tenant_id, name):
    from app.models import DormBuilding
    b = db.scalars(select(DormBuilding).where(
        DormBuilding.tenant_id == tenant_id, DormBuilding.building_name == name,
        DormBuilding.is_deleted.is_(False))).first()
    if b is None:
        b = DormBuilding(tenant_id=tenant_id, building_name=name, gender_limit="MIXED",
                         status="ENABLED")
        db.add(b); db.flush()
    return b


def _get_or_create_room(db, tenant_id, building, room_no, capacity):
    from app.models import DormRoom
    r = db.scalars(select(DormRoom).where(
        DormRoom.tenant_id == tenant_id, DormRoom.building_id == building.id,
        DormRoom.room_no == room_no, DormRoom.is_deleted.is_(False))).first()
    if r is None:
        r = DormRoom(tenant_id=tenant_id, building_id=building.id, floor_no=_floor_of(room_no),
                     room_no=room_no, capacity=capacity, room_type="STANDARD", status="ENABLED")
        db.add(r); db.flush()
    return r


def _next_vacant_bed(db, tenant_id, building, room, capacity):
    """返回房内一张 VACANT 床；不足则在容量内补建床，满员返回 None。"""
    from app.models import DormBed
    beds = db.scalars(select(DormBed).where(
        DormBed.tenant_id == tenant_id, DormBed.room_id == room.id,
        DormBed.is_deleted.is_(False))).all()
    for b in beds:
        if b.status == "VACANT" and b.student_id is None:
            return b
    if len(beds) < capacity:
        n = len(beds) + 1
        b = DormBed(tenant_id=tenant_id, building_id=building.id, room_id=room.id,
                    bed_no=f"{room.room_no}-{n}", status="VACANT")
        db.add(b); db.flush()
        return b
    return None


def _writeback_dorm_record(db, tenant_id, student_id, building_name, room_no, bed_no) -> int:
    from app.models import CsDormRecord
    csid = _cs_student_id(db, tenant_id, student_id)
    rec = db.scalars(select(CsDormRecord).where(
        CsDormRecord.tenant_id == tenant_id, CsDormRecord.cs_student_id == csid,
        CsDormRecord.record_status == "ACTIVE", CsDormRecord.is_deleted.is_(False))).first()
    if rec:
        rec.building, rec.room, rec.bed, rec.status = building_name, room_no, bed_no, "IN"
    else:
        rec = CsDormRecord(tenant_id=tenant_id, cs_student_id=csid, building=building_name,
                           room=room_no, bed=bed_no, checkin_date=datetime.utcnow(),
                           status="IN", record_status="ACTIVE")
        db.add(rec); db.flush()
    return rec.id


def _already_housed(db, tenant_id, student_id) -> bool:
    from app.models import DormBed
    return db.scalars(select(DormBed).where(
        DormBed.tenant_id == tenant_id, DormBed.student_id == int(student_id),
        DormBed.status == "OCCUPIED", DormBed.is_deleted.is_(False))).first() is not None


def init_orientation_dorm(db, tenant_id: int, default_capacity: int = 4, dry_run: bool = True) -> dict:
    """迎新分宿初始化。返回 {candidates, assigned, skipped_housed, skipped_full, buildings, rooms, beds}。"""
    from app.models import OrientationStudent
    rows = db.scalars(select(OrientationStudent).where(
        OrientationStudent.tenant_id == tenant_id,
        OrientationStudent.student_id.is_not(None),
        OrientationStudent.building.is_not(None),
        OrientationStudent.room.is_not(None),
        OrientationStudent.dorm_status.in_(ALLOCATED_STATUSES),
        OrientationStudent.is_deleted.is_(False))).all()
    report = {"candidates": len(rows), "assigned": 0, "skipped_housed": 0,
              "skipped_full": 0, "buildings": set(), "rooms": set(), "beds": 0}
    for o in rows:
        if _already_housed(db, tenant_id, o.student_id):
            report["skipped_housed"] += 1
            continue
        building = _get_or_create_building(db, tenant_id, o.building)
        room = _get_or_create_room(db, tenant_id, building, o.room, default_capacity)
        report["buildings"].add(building.id); report["rooms"].add(room.id)
        bed = _next_vacant_bed(db, tenant_id, building, room, default_capacity)
        if bed is None:
            report["skipped_full"] += 1
            continue
        rec_id = _writeback_dorm_record(db, tenant_id, o.student_id, o.building, o.room, bed.bed_no)
        bed.student_id, bed.status = int(o.student_id), "OCCUPIED"
        bed.occupied_at, bed.cs_dorm_record_id = datetime.utcnow(), rec_id
        report["assigned"] += 1; report["beds"] += 1
    report["buildings"] = len(report["buildings"]); report["rooms"] = len(report["rooms"])
    if dry_run:
        db.rollback()
    else:
        db.commit()
    return report


def main():
    ap = argparse.ArgumentParser(description="迎新分宿 → 宿舍台账初始化导入")
    ap.add_argument("--tenant", type=int, required=True, help="目标租户 tenant_id")
    ap.add_argument("--capacity", type=int, default=4, help="默认每间床位数（缺房时铺床用）")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true", help="只统计不落库")
    g.add_argument("--confirm", action="store_true", help="真正落库")
    args = ap.parse_args()

    from app.db.session import get_sessionmaker
    db = get_sessionmaker()()
    try:
        rep = init_orientation_dorm(db, args.tenant, args.capacity, dry_run=not args.confirm)
        print(f"[init-dorm] tenant={args.tenant} dry_run={not args.confirm} -> {rep}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
