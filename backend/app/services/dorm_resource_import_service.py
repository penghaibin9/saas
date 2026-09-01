"""X1 宿舍房源 XLSX Dry-Run 与事务确认。

复用 SharedImportBatch；Dry-Run 只解析、校验和冻结稳定行快照，确认阶段才在一个
事务内写楼栋/房间/床位。既有同编码房源只允许属性完全一致时复用，绝不按名称猜测。
"""
from __future__ import annotations

import uuid
from collections import defaultdict

from sqlalchemy import select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException
from app.db.session import get_sessionmaker

MAX_ROWS = 5000
GENDER_MAP = {
    "男": "MALE", "男生": "MALE", "MALE": "MALE",
    "女": "FEMALE", "女生": "FEMALE", "FEMALE": "FEMALE",
    "混合": "MIXED", "不限": "MIXED", "MIXED": "MIXED",
}
STATUS_MAP = {
    "启用": "ENABLED", "正常": "ENABLED", "ENABLED": "ENABLED",
    "停用": "DISABLED", "DISABLED": "DISABLED",
    "维修": "MAINTAIN", "维护": "MAINTAIN", "MAINTAIN": "MAINTAIN",
}


def _text(row: dict, key: str, label: str) -> str:
    return str(row.get(key) or row.get(label) or "").strip()


def _positive_int(value, *, field: str, label: str) -> tuple[int | None, dict | None]:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return None, {"field": field, "rawValue": value, "message": f"{label}须为正整数"}
    if parsed <= 0:
        return None, {"field": field, "rawValue": value, "message": f"{label}须为正整数"}
    return parsed, None


def _catalog(tenant_id: int) -> dict:
    from app.models import DormBed, DormBuilding, DormRoom

    db = get_sessionmaker()()
    try:
        buildings = defaultdict(list)
        for row in db.scalars(select(DormBuilding).where(
            DormBuilding.tenant_id == tenant_id,
            DormBuilding.is_deleted.is_(False),
        )).all():
            if str(row.building_code or "").strip():
                buildings[str(row.building_code).strip()].append(row)
        building_ids = {int(row.id) for rows in buildings.values() for row in rows}
        rooms = defaultdict(list)
        if building_ids:
            for row in db.scalars(select(DormRoom).where(
                DormRoom.tenant_id == tenant_id,
                DormRoom.building_id.in_(building_ids),
                DormRoom.is_deleted.is_(False),
            )).all():
                rooms[(int(row.building_id), str(row.room_no).strip())].append(row)
        room_ids = {int(row.id) for rows in rooms.values() for row in rows}
        beds = defaultdict(list)
        if room_ids:
            for row in db.scalars(select(DormBed).where(
                DormBed.tenant_id == tenant_id,
                DormBed.room_id.in_(room_ids),
                DormBed.is_deleted.is_(False),
            )).all():
                beds[(int(row.room_id), str(row.bed_no).strip())].append(row)
        return {"buildings": buildings, "rooms": rooms, "beds": beds}
    finally:
        db.close()


def dry_run(tenant_id: int, rows: list[dict], *, namespace: str, user: dict | None = None) -> dict:
    if len(rows) > MAX_ROWS:
        raise AppException("VALIDATION_ERROR", f"单次导入不能超过 {MAX_ROWS} 行")
    catalog = _catalog(int(tenant_id))
    errors: list[dict] = []
    normalized: list[dict] = []
    seen_beds: set[tuple[str, str, str]] = set()
    building_defs: dict[str, tuple] = {}
    room_defs: dict[tuple[str, str], tuple] = {}
    room_rows: dict[tuple[str, str], list[dict]] = defaultdict(list)

    for row_index, raw in enumerate(rows, start=2):
        building_code = _text(raw, "buildingCode", "楼栋编码")
        building_name = _text(raw, "buildingName", "楼栋名称")
        gender_raw = _text(raw, "genderLimit", "性别属性").upper()
        room_no = _text(raw, "roomNo", "房号")
        room_type = _text(raw, "roomType", "房型") or "STANDARD"
        bed_no = _text(raw, "bedNo", "床号")
        status_raw = _text(raw, "roomStatus", "房间状态").upper()
        missing = next(((field, label) for field, label, value in (
            ("buildingCode", "楼栋编码", building_code),
            ("buildingName", "楼栋名称", building_name),
            ("genderLimit", "性别属性", gender_raw),
            ("roomNo", "房号", room_no),
            ("bedNo", "床号", bed_no),
            ("roomStatus", "房间状态", status_raw),
        ) if not value), None)
        if missing:
            errors.append({"rowIndex": row_index, "field": missing[0], "rawValue": "",
                           "message": f"{missing[1]}必填"})
            continue
        floor_no, error = _positive_int(raw.get("floorNo") or raw.get("楼层"), field="floorNo", label="楼层")
        if error:
            errors.append({"rowIndex": row_index, **error})
            continue
        capacity, error = _positive_int(raw.get("capacity") or raw.get("容量"), field="capacity", label="容量")
        if error:
            errors.append({"rowIndex": row_index, **error})
            continue
        gender = GENDER_MAP.get(gender_raw)
        if not gender:
            errors.append({"rowIndex": row_index, "field": "genderLimit", "rawValue": gender_raw,
                           "message": "性别属性须为男/女/混合"})
            continue
        room_status = STATUS_MAP.get(status_raw)
        if not room_status:
            errors.append({"rowIndex": row_index, "field": "roomStatus", "rawValue": status_raw,
                           "message": "房间状态须为启用/停用/维修"})
            continue
        if capacity > 20:
            errors.append({"rowIndex": row_index, "field": "capacity", "rawValue": capacity,
                           "message": "单间容量不能超过 20"})
            continue

        building_def = (building_name, gender)
        if building_code in building_defs and building_defs[building_code] != building_def:
            errors.append({"rowIndex": row_index, "field": "buildingCode", "rawValue": building_code,
                           "message": "同一楼栋编码在文件内的名称或性别属性不一致"})
            continue
        building_defs[building_code] = building_def
        db_buildings = catalog["buildings"].get(building_code, [])
        if len(db_buildings) > 1:
            errors.append({"rowIndex": row_index, "field": "buildingCode", "rawValue": building_code,
                           "message": "本校存在重复楼栋编码，请先修复房源主数据"})
            continue
        if db_buildings:
            existing = db_buildings[0]
            if existing.building_name != building_name or existing.gender_limit != gender:
                errors.append({"rowIndex": row_index, "field": "buildingCode", "rawValue": building_code,
                               "message": "楼栋编码已存在，但名称或性别属性与现有房源不一致"})
                continue

        room_key = (building_code, room_no)
        room_def = (floor_no, capacity, room_type, room_status)
        if room_key in room_defs and room_defs[room_key] != room_def:
            errors.append({"rowIndex": row_index, "field": "roomNo", "rawValue": room_no,
                           "message": "同一房间在文件内的楼层、房型、容量或状态不一致"})
            continue
        room_defs[room_key] = room_def
        bed_key = (building_code, room_no, bed_no)
        if bed_key in seen_beds:
            errors.append({"rowIndex": row_index, "field": "bedNo", "rawValue": bed_no,
                           "message": "同一房间床号在文件内重复"})
            continue
        seen_beds.add(bed_key)

        existing_room = None
        if db_buildings:
            db_rooms = catalog["rooms"].get((int(db_buildings[0].id), room_no), [])
            if len(db_rooms) > 1:
                errors.append({"rowIndex": row_index, "field": "roomNo", "rawValue": room_no,
                               "message": "楼栋内存在重复房号，请先修复房源主数据"})
                continue
            if db_rooms:
                existing_room = db_rooms[0]
                if (int(existing_room.floor_no), int(existing_room.capacity),
                    existing_room.room_type or "STANDARD", existing_room.status) != room_def:
                    errors.append({"rowIndex": row_index, "field": "roomNo", "rawValue": room_no,
                                   "message": "房间已存在，但楼层、房型、容量或状态不一致"})
                    continue
                if catalog["beds"].get((int(existing_room.id), bed_no)):
                    errors.append({"rowIndex": row_index, "field": "bedNo", "rawValue": bed_no,
                                   "message": "该房间床号已存在"})
                    continue

        item = {
            "buildingCode": building_code, "buildingName": building_name,
            "genderLimit": gender, "floorNo": floor_no, "roomNo": room_no,
            "roomType": room_type, "capacity": capacity, "bedNo": bed_no,
            "roomStatus": room_status,
        }
        normalized.append(item)
        room_rows[room_key].append(item)

    # 一份房间导入必须恰好铺满容量；已有房间按“已有床 + 本次新床”核对。
    for room_key, room_def in room_defs.items():
        related = room_rows.get(room_key, [])
        if not related:
            continue
        existing_count = 0
        db_buildings = catalog["buildings"].get(room_key[0], [])
        if len(db_buildings) == 1:
            db_rooms = catalog["rooms"].get((int(db_buildings[0].id), room_key[1]), [])
            if len(db_rooms) == 1:
                existing_count = sum(
                    len(values) for (room_id, _), values in catalog["beds"].items()
                    if room_id == int(db_rooms[0].id)
                )
        capacity = int(room_def[1])
        if existing_count + len(related) != capacity:
            for item in related:
                source_index = next((idx for idx, source in enumerate(rows, start=2)
                                     if _text(source, "buildingCode", "楼栋编码") == room_key[0]
                                     and _text(source, "roomNo", "房号") == room_key[1]), 2)
                errors.append({"rowIndex": source_index, "field": "capacity", "rawValue": capacity,
                               "message": f"房间容量为 {capacity}，已有 {existing_count} 床，本次提供 {len(related)} 床，数量不一致"})
                break

    # 任一错误整批不能确认，避免“正确行先入库、错误行以后补”造成半套房源。
    batch_no = f"DORM{uuid.uuid4().hex[:10]}"
    status = "DRY_RUN_PASSED" if not errors else "DRY_RUN_FAILED"
    actor = user or get_current_user_ctx() or {}
    from app.services import shared_import_batch_service as shared
    shared.create(
        int(tenant_id), namespace, batch_no, status,
        {"domain": "dorm", "rows": normalized, "sourceRows": rows},
        errors=errors, operator_key=str(actor.get("userId") or ""),
    )
    return {
        "batchNo": batch_no, "status": status, "totalRows": len(rows),
        "okRows": len(normalized), "errorRows": len(errors), "errors": errors[:50],
        "errorWorkbookUrl": (
            f"/api/v1/import/domain/dorm/batches/{batch_no}/errors.xlsx" if errors else None
        ),
    }


def confirm(tenant_id: int, rows: list[dict]) -> dict:
    from app.models import AffairsAuditTrail, DormBed, DormBuilding, DormRoom

    db = get_sessionmaker()()
    try:
        buildings: dict[str, DormBuilding] = {}
        created_buildings = created_rooms = created_beds = 0
        rooms: dict[tuple[int, str], DormRoom] = {}
        for item in rows:
            building = buildings.get(item["buildingCode"])
            if not building:
                matches = list(db.scalars(select(DormBuilding).where(
                    DormBuilding.tenant_id == int(tenant_id),
                    DormBuilding.building_code == item["buildingCode"],
                    DormBuilding.is_deleted.is_(False),
                ).with_for_update()).all())
                if len(matches) > 1:
                    raise AppException(
                        "DATA_CONFLICT",
                        f"确认时发现重复楼栋编码：{item['buildingCode']}，请先修复房源主数据",
                    )
                building = matches[0] if matches else None
                if building and (
                    building.building_name != item["buildingName"]
                    or building.gender_limit != item["genderLimit"]
                ):
                    raise AppException(
                        "DATA_CONFLICT",
                        f"确认时楼栋编码已被其他任务占用：{item['buildingCode']}",
                    )
                if not building:
                    building = DormBuilding(
                        tenant_id=int(tenant_id), building_code=item["buildingCode"],
                        building_name=item["buildingName"], gender_limit=item["genderLimit"],
                        floor_count=item["floorNo"], status="ENABLED",
                    )
                    db.add(building)
                    db.flush()
                    created_buildings += 1
                buildings[item["buildingCode"]] = building
            building.floor_count = max(int(building.floor_count or 0), int(item["floorNo"]))
            room_key = (int(building.id), item["roomNo"])
            room = rooms.get(room_key)
            if not room:
                room = db.scalars(select(DormRoom).where(
                    DormRoom.tenant_id == int(tenant_id),
                    DormRoom.building_id == int(building.id),
                    DormRoom.room_no == item["roomNo"],
                    DormRoom.is_deleted.is_(False),
                ).with_for_update()).first()
                if not room:
                    room = DormRoom(
                        tenant_id=int(tenant_id), building_id=int(building.id),
                        floor_no=int(item["floorNo"]), room_no=item["roomNo"],
                        capacity=int(item["capacity"]), room_type=item["roomType"],
                        status=item["roomStatus"],
                    )
                    db.add(room)
                    db.flush()
                    created_rooms += 1
                rooms[room_key] = room
            duplicate = db.scalars(select(DormBed.id).where(
                DormBed.tenant_id == int(tenant_id), DormBed.room_id == int(room.id),
                DormBed.bed_no == item["bedNo"], DormBed.is_deleted.is_(False),
            ).with_for_update()).first()
            if duplicate:
                raise AppException("DATA_CONFLICT", f"确认时床号已被其他任务创建：{item['buildingCode']}/{item['roomNo']}/{item['bedNo']}")
            db.add(DormBed(
                tenant_id=int(tenant_id), building_id=int(building.id), room_id=int(room.id),
                bed_no=item["bedNo"], status="VACANT",
            ))
            created_beds += 1
        operator = get_current_user_ctx() or {}
        db.add(AffairsAuditTrail(
            tenant_id=int(tenant_id), biz_type="DORM_RESOURCE_IMPORT", action="IMPORT",
            operator=operator.get("realName") or str(operator.get("userId") or "系统"),
            role_name=str(operator.get("currentRoleCode") or ""),
            detail=f"楼栋{created_buildings}，房间{created_rooms}，床位{created_beds}",
        ))
        db.commit()
        return {
            "insertedRows": created_beds, "createdBuildings": created_buildings,
            "createdRooms": created_rooms, "createdBeds": created_beds,
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
