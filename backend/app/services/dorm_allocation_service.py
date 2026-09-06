"""D3 dorm allocation plan authority: dry-run, publish, self-select and projections."""
from __future__ import annotations

from datetime import datetime
from io import BytesIO

from sqlalchemy import and_, func, or_, select, update

from app.core.exceptions import AppException, no_permission, not_found
from app.core.tenant_scoped import tenant_get
from app.models import (DormAllocationBatch, DormAllocationItem, DormBed, DormBuilding,
                        DormRoom, DormStay, OrientationBatch, OrientationStudent,
                        OrientationStudentStep, StudentProfile)
from app.services.db_service import _iso, _tid, session

MODES = {"ADMIN_AUTO", "ADMIN_MANUAL", "STUDENT_SELECT", "POST_CHECKIN_PUBLISH"}
ACTIVE_ITEM_STATUSES = {"PENDING", "PROPOSED", "RESERVED", "CONFIRMED", "CONFLICT"}
SENSITIVE_RULE_KEYS = {"ethnicity", "nation", "nationality", "origin", "nativeplace", "religion"}


def _parse_dt(value, field: str) -> datetime:
    raw = str(value or "").strip().replace("Z", "").replace("/", "-")
    try:
        return datetime.fromisoformat(raw[:19])
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", f"{field} 必须为有效日期时间")


def _ids(value) -> list[int]:
    out = []
    for item in value or []:
        try:
            parsed = int(item)
        except (TypeError, ValueError):
            raise AppException("VALIDATION_ERROR", "资源和学生范围必须使用稳定数字 ID")
        if parsed <= 0 or parsed in out:
            if parsed <= 0:
                raise AppException("VALIDATION_ERROR", "范围 ID 必须大于 0")
            continue
        out.append(parsed)
    return out


def _batch(db, batch_id: int) -> DormAllocationBatch:
    row = db.get(DormAllocationBatch, int(batch_id))
    if not row or row.is_deleted or int(row.tenant_id) != int(_tid()):
        raise not_found("住宿分配批次不存在")
    return row


def _scope_context(db, user):
    from app.core.affairs_security import build_affairs_context
    return build_affairs_context(user or {}, db)


def _assert_rules(rules: dict) -> dict:
    value = dict(rules or {})
    lowered = {str(key).replace("_", "").lower() for key in value}
    if lowered & SENSITIVE_RULE_KEYS:
        raise AppException(
            "VALIDATION_ERROR", "D3 不允许启用民族、籍贯、宗教等敏感分寝规则"
        )
    allowed = {"sameCollege", "sameMajor", "sameClass", "minimizeVacancy", "balanceFloor"}
    unknown = set(value) - allowed
    if unknown:
        raise AppException("VALIDATION_ERROR", f"未知分配规则：{', '.join(sorted(unknown))}")
    return {key: bool(value.get(key, False)) for key in sorted(allowed)}


def _resource_rows(
    db, resource_scope: dict, user, *, vacant_only: bool = False,
    enforce_management_scope: bool = True,
):
    from app.services.affairs_dorm_service import _require_dorm_scope

    scope = resource_scope or {}
    building_ids = _ids(scope.get("buildingIds"))
    room_ids = _ids(scope.get("roomIds"))
    explicit_bed_ids = _ids(scope.get("bedIds"))
    resolved_bed_ids = _ids(scope.get("resolvedBedIds"))
    if not (building_ids or room_ids or explicit_bed_ids or resolved_bed_ids):
        raise AppException("VALIDATION_ERROR", "至少选择一个楼栋、房间或床位作为资源池")
    # Published batches keep building/room ids only as summaries. The exact bed ids are the
    # frozen authority and must not expand when a room gains new beds after publication.
    if "resolvedBedIds" in scope:
        if not resolved_bed_ids:
            raise AppException("DATA_CONFLICT", "已发布分配批次的冻结床位资源池为空")
        cond = [DormBed.id.in_(resolved_bed_ids)]
    else:
        cond = []
        if building_ids:
            cond.append(DormBed.building_id.in_(building_ids))
        if room_ids:
            cond.append(DormBed.room_id.in_(room_ids))
        if explicit_bed_ids:
            cond.append(DormBed.id.in_(explicit_bed_ids))
    q = (select(DormBed, DormRoom, DormBuilding)
         .join(DormRoom, DormRoom.id == DormBed.room_id)
         .join(DormBuilding, DormBuilding.id == DormBed.building_id)
         .where(
             DormBed.tenant_id == _tid(), DormRoom.tenant_id == _tid(),
             DormBuilding.tenant_id == _tid(), DormBed.is_deleted.is_(False),
             DormRoom.is_deleted.is_(False), DormBuilding.is_deleted.is_(False),
             DormRoom.status == "ENABLED", DormBuilding.status == "ENABLED",
             or_(*cond),
         ))
    if vacant_only:
        q = q.where(DormBed.status == "VACANT", DormBed.student_id.is_(None))
    rows = db.execute(q.order_by(DormBuilding.id, DormRoom.floor_no,
                                 DormRoom.room_no, DormBed.bed_no)).all()
    if not rows:
        raise AppException("DATA_CONFLICT", "资源池内没有有效床位")
    if enforce_management_scope:
        for bed, _room, _building in rows:
            _require_dorm_scope(db, int(bed.building_id), user)
    return rows


def _candidate_students(db, row: DormAllocationBatch, user):
    scope = dict(row.student_scope_json or {})
    requested_ids = _ids(scope.get("studentIds") or scope.get("resolvedStudentIds"))
    missing_identity = 0
    if row.orientation_batch_id:
        orientation = db.get(OrientationBatch, int(row.orientation_batch_id))
        if not orientation or orientation.is_deleted or int(orientation.tenant_id) != int(_tid()):
            raise AppException("DATA_CONFLICT", "关联迎新批次不存在或租户链不一致")
        ori_rows = db.execute(select(
            OrientationStudent.student_id, OrientationStudent.id,
        ).where(
            OrientationStudent.tenant_id == _tid(),
            OrientationStudent.batch_id == orientation.id,
            OrientationStudent.is_deleted.is_(False),
            OrientationStudent.record_status == "ACTIVE",
        )).all()
        missing_identity = sum(1 for item in ori_rows if not item.student_id)
        batch_ids = {int(item.student_id) for item in ori_rows if item.student_id}
        requested_ids = [sid for sid in requested_ids if sid in batch_ids] if requested_ids else sorted(batch_ids)
    if not requested_ids:
        return [], missing_identity
    q = select(StudentProfile).where(
        StudentProfile.tenant_id == _tid(), StudentProfile.id.in_(requested_ids),
        StudentProfile.is_deleted.is_(False),
    )
    for field, column in (
        ("collegeIds", StudentProfile.college_id),
        ("majorIds", StudentProfile.major_id),
        ("classIds", StudentProfile.class_id),
    ):
        values = _ids(scope.get(field))
        if values:
            q = q.where(column.in_(values))
    ctx = _scope_context(db, user)
    allowed_classes = ctx.allowed_class_ids(db)
    if allowed_classes is not None:
        if not allowed_classes:
            raise AppException("NO_DATA_SCOPE", "当前账号没有可用于住宿分配的学生范围")
        q = q.where(StudentProfile.class_id.in_(allowed_classes))
    rows = db.scalars(q.order_by(StudentProfile.college_id, StudentProfile.major_id,
                                 StudentProfile.class_id, StudentProfile.id)).all()
    return rows, missing_identity


def _gender_ok(building, student) -> bool:
    from app.services.affairs_dorm_reliability_service import _strict_gender_ok
    return _strict_gender_ok(building.gender_limit, student.gender)


def _batch_row(row: DormAllocationBatch) -> dict:
    return {
        "batchId": str(row.id), "batchNo": row.batch_no, "name": row.name,
        "academicYear": row.academic_year, "sourceType": row.source_type,
        "orientationBatchId": str(row.orientation_batch_id or ""), "mode": row.mode,
        "openAt": _iso(row.open_at), "closeAt": _iso(row.close_at),
        "status": row.status, "rules": row.rules_json or {},
        "resourceScope": row.resource_scope_json or {}, "studentScope": row.student_scope_json or {},
        "publishedAt": _iso(row.published_at), "version": int(row.version or 0),
    }


def create_batch(body: dict, user) -> dict:
    no = str(body.get("batchNo") or "").strip()
    name = str(body.get("name") or "").strip()
    year = str(body.get("academicYear") or "").strip()
    mode = str(body.get("mode") or "").upper()
    if not no or not name or not year or mode not in MODES:
        raise AppException("VALIDATION_ERROR", "批次编号、名称、学年和有效分配模式必填")
    open_at, close_at = _parse_dt(body.get("openAt"), "openAt"), _parse_dt(body.get("closeAt"), "closeAt")
    if open_at >= close_at:
        raise AppException("VALIDATION_ERROR", "开放时间必须早于关闭时间")
    resource = dict(body.get("resourceScope") or {})
    student_scope = dict(body.get("studentScope") or {})
    with session() as db:
        if db.scalars(select(DormAllocationBatch).where(
            DormAllocationBatch.tenant_id == _tid(), DormAllocationBatch.batch_no == no,
            DormAllocationBatch.is_deleted.is_(False),
        )).first():
            raise AppException("DATA_CONFLICT", "住宿分配批次编号已存在")
        orientation_id = body.get("orientationBatchId")
        if orientation_id not in (None, ""):
            try:
                orientation_id = int(orientation_id)
            except (TypeError, ValueError):
                raise AppException("VALIDATION_ERROR", "orientationBatchId 必须为稳定数字 ID")
            ori = db.get(OrientationBatch, orientation_id)
            if not ori or ori.is_deleted or int(ori.tenant_id) != int(_tid()):
                raise AppException("VALIDATION_ERROR", "关联迎新批次不存在")
        elif str(body.get("sourceType") or "ORIENTATION").upper() == "ORIENTATION":
            raise AppException("VALIDATION_ERROR", "迎新来源分配批次必须关联 orientationBatchId")
        resources = _resource_rows(db, resource, user)
        normalized_resource = {
            "buildingIds": sorted({int(b.id) for _bed, _room, b in resources}),
            "roomIds": _ids(resource.get("roomIds")),
            "bedIds": _ids(resource.get("bedIds")),
        }
        row = DormAllocationBatch(
            tenant_id=_tid(), batch_no=no, name=name, academic_year=year,
            source_type=str(body.get("sourceType") or "ORIENTATION").upper(),
            orientation_batch_id=orientation_id, mode=mode, open_at=open_at, close_at=close_at,
            status="DRAFT", rules_json=_assert_rules(body.get("rules") or {}),
            resource_scope_json=normalized_resource, student_scope_json=student_scope,
        )
        db.add(row); db.flush()
        from app.services import affairs_dorm_service as dorm
        dorm._audit(db, "DORM_ALLOCATION_BATCH", row.id, "CREATE", f"mode={mode}")
        db.commit()
        return _batch_row(row)


def list_batches(user, page=1, page_size=20, status=None):
    page, page_size = max(1, int(page)), max(1, min(int(page_size), 200))
    with session() as db:
        q = select(DormAllocationBatch).where(
            DormAllocationBatch.tenant_id == _tid(), DormAllocationBatch.is_deleted.is_(False),
        )
        if status:
            q = q.where(DormAllocationBatch.status == str(status).upper())
        rows = db.scalars(q.order_by(DormAllocationBatch.id.desc())).all()
        ctx = _scope_context(db, user)
        if ctx.scope_type != "TENANT_ALL":
            allowed = set(ctx.dorm_building_ids)
            rows = [row for row in rows if allowed & set(_ids((row.resource_scope_json or {}).get("buildingIds")))]
        total = len(rows)
        rows = rows[(page - 1) * page_size: page * page_size]
        return [_batch_row(row) for row in rows], total


def _upsert_item(db, batch, student, *, bed=None, status="PENDING", source="AUTO", conflict=None):
    item = db.scalars(select(DormAllocationItem).where(
        DormAllocationItem.tenant_id == _tid(),
        DormAllocationItem.allocation_batch_id == batch.id,
        DormAllocationItem.student_id == student.id,
        DormAllocationItem.is_deleted.is_(False),
    )).first()
    if not item:
        item = DormAllocationItem(
            tenant_id=_tid(), allocation_batch_id=batch.id, student_id=student.id,
            status=status, source=source,
        )
        db.add(item)
    item.bed_id = bed.id if bed else None
    item.status = status
    item.source = source
    item.conflict_code = conflict
    item.confirmed_at = None
    item.version = int(item.version or 0) + 1
    return item


def _dry_run(db, batch: DormAllocationBatch, user) -> dict:
    if batch.status != "DRAFT":
        raise AppException("INVALID_STATE", "仅草稿分配批次可执行 Dry Run")
    students, missing = _candidate_students(db, batch, user)
    resources = _resource_rows(db, batch.resource_scope_json or {}, user, vacant_only=True)
    occupied_students = set(db.scalars(select(DormBed.student_id).where(
        DormBed.tenant_id == _tid(), DormBed.student_id.in_([s.id for s in students] or [-1]),
        DormBed.status == "OCCUPIED", DormBed.is_deleted.is_(False),
    )).all())
    reserved_students = set(db.scalars(select(DormStay.student_id).where(
        DormStay.tenant_id == _tid(), DormStay.student_id.in_([s.id for s in students] or [-1]),
        DormStay.status.in_(["RESERVED", "ACTIVE"]), DormStay.is_deleted.is_(False),
    )).all())
    available = list(resources)
    rules = dict(batch.rules_json or {})
    room_profiles: dict[int, list[StudentProfile]] = {}
    room_ids = sorted({int(room.id) for _bed, room, _building in resources})
    for room_id, profile in db.execute(
        select(DormBed.room_id, StudentProfile)
        .join(StudentProfile, StudentProfile.id == DormBed.student_id)
        .where(
            DormBed.tenant_id == _tid(), DormBed.room_id.in_(room_ids or [-1]),
            DormBed.status == "OCCUPIED", DormBed.is_deleted.is_(False),
            StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
        )
    ).all():
        room_profiles.setdefault(int(room_id), []).append(profile)
    remaining_by_room: dict[int, int] = {}
    floor_population: dict[tuple[int, int], int] = {}
    room_meta = {}
    for _bed, room, building in resources:
        room_id = int(room.id)
        room_meta[room_id] = (room, building)
        remaining_by_room[room_id] = remaining_by_room.get(room_id, 0) + 1
        floor_key = (int(building.id), int(room.floor_no or 0))
        floor_population.setdefault(floor_key, 0)
    for room_id, profiles in room_profiles.items():
        room, building = room_meta.get(room_id, (None, None))
        if room is not None and building is not None:
            floor_population[(int(building.id), int(room.floor_no or 0))] += len(profiles)

    def soft_score(candidate, student):
        bed, room, building = candidate
        peers = room_profiles.get(int(room.id), [])
        affinity = 0
        if rules.get("sameClass") and student.class_id:
            affinity += 8 * sum(peer.class_id == student.class_id for peer in peers)
        if rules.get("sameMajor") and student.major_id:
            affinity += 4 * sum(peer.major_id == student.major_id for peer in peers)
        if rules.get("sameCollege") and student.college_id:
            affinity += 2 * sum(peer.college_id == student.college_id for peer in peers)
        fill_score = -remaining_by_room.get(int(room.id), 0) if rules.get("minimizeVacancy") else 0
        floor_key = (int(building.id), int(room.floor_no or 0))
        balance_score = -floor_population.get(floor_key, 0) if rules.get("balanceFloor") else 0
        return affinity, fill_score, balance_score, -int(bed.id)

    assigned = conflicts = 0
    current_ids = set()
    reasons = {"ALREADY_HAS_BED": 0, "NO_COMPATIBLE_BED": 0, "DATA_MISSING": missing}
    for student in students:
        current_ids.add(int(student.id))
        if student.id in occupied_students or student.id in reserved_students:
            _upsert_item(db, batch, student, status="CONFLICT", conflict="ALREADY_HAS_BED")
            conflicts += 1; reasons["ALREADY_HAS_BED"] += 1
            continue
        compatible = [(index, candidate) for index, candidate in enumerate(available)
                      if _gender_ok(candidate[2], student)]
        chosen_index = max(compatible, key=lambda pair: soft_score(pair[1], student))[0] if compatible else None
        if chosen_index is None:
            _upsert_item(db, batch, student, status="CONFLICT", conflict="NO_COMPATIBLE_BED")
            conflicts += 1; reasons["NO_COMPATIBLE_BED"] += 1
            continue
        bed, _room, _building = available.pop(chosen_index)
        _upsert_item(db, batch, student, bed=bed, status="PROPOSED", source="AUTO")
        room_profiles.setdefault(int(_room.id), []).append(student)
        remaining_by_room[int(_room.id)] -= 1
        floor_key = (int(_building.id), int(_room.floor_no or 0))
        floor_population[floor_key] = floor_population.get(floor_key, 0) + 1
        assigned += 1
    stale = db.scalars(select(DormAllocationItem).where(
        DormAllocationItem.tenant_id == _tid(), DormAllocationItem.allocation_batch_id == batch.id,
        DormAllocationItem.is_deleted.is_(False),
        DormAllocationItem.student_id.not_in(current_ids or {-1}),
    )).all()
    for item in stale:
        item.status, item.bed_id, item.conflict_code = "CANCELLED", None, "OUT_OF_SCOPE"
    summary = {
        "totalStudents": len(students) + missing, "eligibleStudents": len(students),
        "proposed": assigned, "unassigned": conflicts + missing,
        "reasonCounts": reasons, "availableBeds": len(resources),
        "appliedRules": sorted(key for key, enabled in rules.items()
                               if enabled is True and not key.startswith("_")),
    }
    rules["_dryRun"] = summary
    batch.rules_json = rules
    batch.version = int(batch.version or 0) + 1
    return summary


def dry_run(batch_id: int, user) -> dict:
    with session() as db:
        batch = _batch(db, batch_id)
        summary = _dry_run(db, batch, user)
        from app.services import affairs_dorm_service as dorm
        dorm._audit(db, "DORM_ALLOCATION_BATCH", batch.id, "DRY_RUN", str(summary))
        db.commit()
        return {"batch": _batch_row(batch), "summary": summary}


def manual_assign(batch_id: int, student_id: int, bed_id: int, user) -> dict:
    with session() as db:
        batch = _batch(db, batch_id)
        if batch.status != "DRAFT":
            raise AppException("INVALID_STATE", "仅草稿批次可人工调整分配")
        students, _missing = _candidate_students(db, batch, user)
        student = next((row for row in students if int(row.id) == int(student_id)), None)
        if not student:
            raise AppException("NO_DATA_SCOPE", "学生不在该批次稳定学生范围内")
        resources = _resource_rows(db, batch.resource_scope_json or {}, user, vacant_only=True)
        selected = next((row for row in resources if int(row[0].id) == int(bed_id)), None)
        if not selected:
            raise AppException("DATA_CONFLICT", "床位不在资源池内或已不可用")
        bed, _room, building = selected
        if not _gender_ok(building, student):
            raise AppException("DATA_CONFLICT", "学生性别信息缺失或与楼栋限制不符")
        other = db.scalars(select(DormAllocationItem).where(
            DormAllocationItem.tenant_id == _tid(),
            DormAllocationItem.allocation_batch_id == batch.id,
            DormAllocationItem.bed_id == bed.id,
            DormAllocationItem.student_id != student.id,
            DormAllocationItem.status.not_in(["CANCELLED", "CONFLICT"]),
            DormAllocationItem.is_deleted.is_(False),
        )).first()
        if other:
            raise AppException("DATA_CONFLICT", "该床位已在本批次分配给其他学生")
        item = _upsert_item(db, batch, student, bed=bed, status="PROPOSED", source="MANUAL")
        db.flush()
        from app.services import affairs_dorm_service as dorm
        dorm._audit(db, "DORM_ALLOCATION_ITEM", item.id, "MANUAL_PROPOSE",
                    f"student={student.id};bed={bed.id}")
        db.commit()
        return {"itemId": str(item.id), "status": item.status}


def _link_orientation(db, batch, item, bed, room, building):
    if not batch.orientation_batch_id:
        return
    ori = db.scalars(select(OrientationStudent).where(
        OrientationStudent.tenant_id == _tid(),
        OrientationStudent.batch_id == batch.orientation_batch_id,
        OrientationStudent.student_id == item.student_id,
        OrientationStudent.is_deleted.is_(False),
    )).first()
    if not ori:
        return
    ori.dorm_status = "ASSIGNED"
    ori.building = building.building_name
    ori.room = f"{room.room_no}室 {bed.bed_no}床"
    canonical = db.scalars(select(OrientationStudentStep).where(
        OrientationStudentStep.tenant_id == _tid(),
        OrientationStudentStep.orientation_student_id == ori.id,
        OrientationStudentStep.step_key == "DORM",
        OrientationStudentStep.is_deleted.is_(False),
    )).first()
    if canonical:
        from app.services.orientation_flow_service import set_student_step_status
        set_student_step_status(
            db, ori, "DORM", "DONE", status_source="PROCESS_FACT",
            source_biz_id=f"dorm-allocation:{item.id}",
        )


def _lock_unassigned_student(db, student_id: int) -> None:
    """Serialize every reservation for one student and recheck the canonical stay ledger."""
    locked = db.scalar(select(StudentProfile.id).where(
        StudentProfile.id == int(student_id),
        StudentProfile.tenant_id == _tid(),
        StudentProfile.is_deleted.is_(False),
    ).with_for_update())
    if not locked:
        raise AppException("DATA_CONFLICT", "学生档案已失效，不能确认床位")
    active_stay = db.scalar(select(DormStay.id).where(
        DormStay.tenant_id == _tid(), DormStay.student_id == int(student_id),
        DormStay.status.in_(["RESERVED", "ACTIVE"]),
        DormStay.is_deleted.is_(False),
    ).limit(1))
    occupied_bed = db.scalar(select(DormBed.id).where(
        DormBed.tenant_id == _tid(), DormBed.student_id == int(student_id),
        DormBed.status == "OCCUPIED", DormBed.is_deleted.is_(False),
    ).limit(1))
    if active_stay or occupied_bed:
        raise AppException("DATA_CONFLICT", "该学生已有生效或预留床位，不能重复分配")


def _reserve(db, batch, item, user):
    _lock_unassigned_student(db, int(item.student_id))
    bed = db.get(DormBed, int(item.bed_id)) if item.bed_id else None
    if not bed:
        raise AppException("DATA_CONFLICT", f"分配项 {item.id} 缺少床位")
    claimed = db.execute(update(DormBed).where(
        DormBed.id == bed.id, DormBed.tenant_id == _tid(), DormBed.status == "VACANT",
        DormBed.student_id.is_(None), DormBed.version == bed.version,
        DormBed.is_deleted.is_(False),
    ).values(status="LOCKED", version=DormBed.version + 1))
    if int(claimed.rowcount or 0) != 1:
        raise AppException("DATA_CONFLICT", f"床位 {bed.id} 已被其他流程占用，请重新 Dry Run")
    room, building = db.get(DormRoom, int(bed.room_id)), db.get(DormBuilding, int(bed.building_id))
    stay = DormStay(
        tenant_id=_tid(), student_id=item.student_id, bed_id=bed.id,
        building_id=bed.building_id, room_id=bed.room_id, stay_type="ALLOCATION",
        source_type="ALLOCATION", source_biz_id=str(item.id), status="RESERVED",
    )
    db.add(stay)
    item.status = "RESERVED"
    item.version = int(item.version or 0) + 1
    _link_orientation(db, batch, item, bed, room, building)


def publish(batch_id: int, user) -> dict:
    with session() as db:
        batch = _batch(db, batch_id)
        if batch.status != "DRAFT":
            raise AppException("INVALID_STATE", "仅草稿分配批次可发布")
        students, missing = _candidate_students(db, batch, user)
        resources = _resource_rows(db, batch.resource_scope_json or {}, user, vacant_only=True)
        if not students:
            raise AppException("DATA_CONFLICT", "学生范围内没有可分配的稳定学生")
        overlapping = db.scalars(select(DormAllocationBatch).where(
            DormAllocationBatch.tenant_id == _tid(),
            DormAllocationBatch.id != batch.id,
            DormAllocationBatch.status == "PUBLISHED",
            DormAllocationBatch.open_at < batch.close_at,
            DormAllocationBatch.close_at > batch.open_at,
            DormAllocationBatch.is_deleted.is_(False),
        )).all()
        if overlapping:
            overlapping_ids = [row.id for row in overlapping]
            duplicated_student = db.scalars(select(DormAllocationItem.student_id).where(
                DormAllocationItem.tenant_id == _tid(),
                DormAllocationItem.allocation_batch_id.in_(overlapping_ids),
                DormAllocationItem.student_id.in_([student.id for student in students]),
                DormAllocationItem.status.in_(["PENDING", "PROPOSED", "RESERVED", "CONFIRMED"]),
                DormAllocationItem.is_deleted.is_(False),
            )).first()
            if duplicated_student:
                raise AppException("DATA_CONFLICT", "学生范围与同时段已发布分配批次重叠")
            bed_ids = {int(bed.id) for bed, _room, _building in resources}
            for other_batch in overlapping:
                frozen = _ids((other_batch.resource_scope_json or {}).get("resolvedBedIds"))
                if bed_ids & set(frozen):
                    raise AppException("DATA_CONFLICT", "床位资源池与同时段已发布分配批次重叠")
        if batch.mode in {"ADMIN_AUTO", "POST_CHECKIN_PUBLISH"}:
            dry_summary = dict(batch.rules_json or {}).get("_dryRun")
            if not dry_summary:
                raise AppException("INVALID_STATE", "自动分配批次发布前必须先执行 Dry Run")
            proposed = db.scalar(select(func.count()).select_from(DormAllocationItem).where(
                DormAllocationItem.tenant_id == _tid(),
                DormAllocationItem.allocation_batch_id == batch.id,
                DormAllocationItem.status == "PROPOSED",
                DormAllocationItem.is_deleted.is_(False),
            )) or 0
            if not proposed:
                raise AppException("DATA_CONFLICT", "Dry Run 没有产生可发布的床位提议")
        if batch.mode == "STUDENT_SELECT":
            for old in db.scalars(select(DormAllocationItem).where(
                DormAllocationItem.tenant_id == _tid(),
                DormAllocationItem.allocation_batch_id == batch.id,
                DormAllocationItem.is_deleted.is_(False),
            )).all():
                old.bed_id = None
                old.status = "CANCELLED"
            db.flush()
            for student in students:
                _upsert_item(db, batch, student, status="PENDING", source="STUDENT_SELECT")
        elif batch.mode == "ADMIN_MANUAL":
            if not db.scalars(select(DormAllocationItem).where(
                DormAllocationItem.tenant_id == _tid(),
                DormAllocationItem.allocation_batch_id == batch.id,
                DormAllocationItem.status == "PROPOSED",
                DormAllocationItem.is_deleted.is_(False),
            )).first():
                raise AppException("DATA_CONFLICT", "人工分配批次至少需要一条已核对的床位提议")
        exact_beds = sorted({int(bed.id) for bed, _room, _building in resources})
        batch.resource_scope_json = {
            "buildingIds": sorted({int(building.id) for _bed, _room, building in resources}),
            "roomIds": sorted({int(room.id) for _bed, room, _building in resources}),
            "resolvedBedIds": exact_beds,
        }
        batch.student_scope_json = {
            **dict(batch.student_scope_json or {}),
            "resolvedStudentIds": sorted(int(student.id) for student in students),
            "missingIdentityCount": int(missing),
        }
        for item in db.scalars(select(DormAllocationItem).where(
            DormAllocationItem.tenant_id == _tid(),
            DormAllocationItem.allocation_batch_id == batch.id,
            DormAllocationItem.status == "PROPOSED",
            DormAllocationItem.is_deleted.is_(False),
        ).order_by(DormAllocationItem.id)).all():
            _reserve(db, batch, item, user)
        batch.status = "PUBLISHED"
        batch.published_at = datetime.utcnow()
        batch.version = int(batch.version or 0) + 1
        from app.services import affairs_dorm_service as dorm
        dorm._audit(db, "DORM_ALLOCATION_BATCH", batch.id, "PUBLISH",
                    f"mode={batch.mode};students={len(students)};beds={len(exact_beds)}")
        db.commit()
        return _batch_row(batch)


def detail(batch_id: int, user) -> dict:
    with session() as db:
        batch = _batch(db, batch_id)
        _resource_rows(db, batch.resource_scope_json or {}, user)
        rows = db.execute(select(DormAllocationItem, StudentProfile, DormBed, DormRoom, DormBuilding)
            .join(StudentProfile, StudentProfile.id == DormAllocationItem.student_id)
            .outerjoin(DormBed, DormBed.id == DormAllocationItem.bed_id)
            .outerjoin(DormRoom, DormRoom.id == DormBed.room_id)
            .outerjoin(DormBuilding, DormBuilding.id == DormBed.building_id)
            .where(
                DormAllocationItem.tenant_id == _tid(),
                DormAllocationItem.allocation_batch_id == batch.id,
                DormAllocationItem.is_deleted.is_(False),
            ).order_by(DormAllocationItem.id)).all()
        items = [{
            "itemId": str(item.id), "studentId": str(student.id),
            "studentNo": student.student_no, "studentName": student.real_name,
            "classId": str(student.class_id or ""), "status": item.status,
            "source": item.source, "conflictCode": item.conflict_code or "",
            "bedId": str(item.bed_id or ""),
            "bedLabel": " / ".join(x for x in (
                building.building_name if building else "",
                f"{room.room_no}室" if room else "",
                f"{bed.bed_no}床" if bed else "",
            ) if x),
        } for item, student, bed, room, building in rows]
        return {"batch": _batch_row(batch), "items": items, "total": len(items)}


def _student_item(db, student_id: int, *, require_open=False):
    now = datetime.utcnow()
    q = (select(DormAllocationItem, DormAllocationBatch)
         .join(DormAllocationBatch, DormAllocationBatch.id == DormAllocationItem.allocation_batch_id)
         .where(
             DormAllocationItem.tenant_id == _tid(),
             DormAllocationItem.student_id == int(student_id),
             DormAllocationItem.status.in_(["PENDING", "RESERVED", "CONFIRMED"]),
             DormAllocationItem.is_deleted.is_(False),
             DormAllocationBatch.tenant_id == _tid(),
             DormAllocationBatch.status.in_(["PUBLISHED", "CLOSED"]),
             DormAllocationBatch.is_deleted.is_(False),
         ))
    if require_open:
        q = q.where(DormAllocationBatch.status == "PUBLISHED",
                    DormAllocationBatch.open_at <= now, DormAllocationBatch.close_at >= now)
    return db.execute(q.order_by(DormAllocationBatch.published_at.desc(),
                                 DormAllocationBatch.id.desc())).first()


def current_student_allocation(db, student_id: int) -> dict | None:
    found = _student_item(db, student_id)
    if not found:
        return None
    item, batch = found
    hidden = False
    if batch.mode == "POST_CHECKIN_PUBLISH" and batch.orientation_batch_id:
        ori = db.scalars(select(OrientationStudent).where(
            OrientationStudent.tenant_id == _tid(),
            OrientationStudent.batch_id == batch.orientation_batch_id,
            OrientationStudent.student_id == int(student_id),
            OrientationStudent.is_deleted.is_(False),
        )).first()
        hidden = not ori or ori.report_status not in ("CHECKED_IN", "COLLEGE_CONFIRMED")
    result = {
        "batchId": str(batch.id), "batchName": batch.name, "mode": batch.mode,
        "status": item.status, "hiddenUntilCheckin": hidden,
        "openAt": _iso(batch.open_at), "closeAt": _iso(batch.close_at),
    }
    if item.bed_id and not hidden:
        bed = tenant_get(db, DormBed, int(item.bed_id))
        room = tenant_get(db, DormRoom, int(bed.room_id)) if bed else None
        building = tenant_get(db, DormBuilding, int(bed.building_id)) if bed else None
        result.update({
            "bedId": str(bed.id) if bed else "", "bedNo": bed.bed_no if bed else "",
            "room": room.room_no if room else "", "building": building.building_name if building else "",
        })
    return result


def _student_config_row(db, student) -> dict:
    allocation = current_student_allocation(db, student.id)
    opened = _student_item(db, student.id, require_open=True)
    can_select = bool(opened and opened[1].mode == "STUDENT_SELECT" and opened[0].status == "PENDING")
    if allocation and allocation.get("hiddenUntilCheckin"):
        notice = "宿舍已安排，完成现场报到后可查看具体楼栋、房间和床位。"
    elif allocation and allocation.get("bedId"):
        notice = "床位已确认，不能自行更换；如需调整请走正式调宿流程。"
    elif can_select:
        notice = "当前住宿分配批次已开放，请先选房间、核对设施与床位后确认。"
    else:
        notice = "当前没有可用的学生自选住宿批次，请按学校安排等待分配。"
    return {
        "selfSelectEnabled": can_select,
        "canSelfSelect": can_select,
        "assignMode": opened[1].mode if opened else (allocation or {}).get("mode", "DISABLED"),
        "studentNotice": notice, "allocation": allocation,
        "hasAllocation": bool(allocation),
    }


def student_config(user) -> dict:
    from app.services.mobile_student_service import resolve_student
    with session() as db:
        student = resolve_student(db, user)
        if not student:
            raise no_permission("尚未建立你的学生档案")
        return _student_config_row(db, student)


def public_config() -> dict:
    now = datetime.utcnow()
    with session() as db:
        batch = db.scalars(select(DormAllocationBatch).where(
            DormAllocationBatch.tenant_id == _tid(), DormAllocationBatch.status == "PUBLISHED",
            DormAllocationBatch.mode == "STUDENT_SELECT", DormAllocationBatch.open_at <= now,
            DormAllocationBatch.close_at >= now, DormAllocationBatch.is_deleted.is_(False),
        ).order_by(DormAllocationBatch.published_at.desc())).first()
        return {
            "selfSelectEnabled": bool(batch), "assignMode": batch.mode if batch else "BATCH_CONTROLLED",
            "studentNotice": "学生自选由住宿分配批次和时间窗口控制。",
            "activeBatchId": str(batch.id) if batch else "",
        }


def student_options(user) -> dict:
    from app.services.mobile_student_service import resolve_student
    with session() as db:
        student = resolve_student(db, user)
        if not student:
            raise no_permission("尚未建立你的学生档案")
        found = _student_item(db, student.id, require_open=True)
        if not found or found[1].mode != "STUDENT_SELECT" or found[0].status != "PENDING":
            return {**_student_config_row(db, student), "buildings": []}
        _item, batch = found
        resources = _resource_rows(
            db, batch.resource_scope_json or {}, user, vacant_only=True,
            enforce_management_scope=False,
        )
        buildings = {}
        for _bed, _room, building in resources:
            if not _gender_ok(building, student):
                continue
            value = buildings.setdefault(int(building.id), {
                "buildingId": str(building.id), "buildingName": building.building_name,
                "genderLimit": building.gender_limit, "vacantBeds": 0,
            })
            value["vacantBeds"] += 1
        return {**_student_config_row(db, student), "batchId": str(batch.id), "buildings": list(buildings.values())}


def student_rooms(user, building_id: int) -> dict:
    from app.services.mobile_student_service import resolve_student
    with session() as db:
        student = resolve_student(db, user)
        found = _student_item(db, student.id, require_open=True) if student else None
        if not found or found[1].mode != "STUDENT_SELECT" or found[0].status != "PENDING":
            raise no_permission("当前没有可用的学生自选住宿批次")
        resources = _resource_rows(
            db, found[1].resource_scope_json or {}, user, vacant_only=True,
            enforce_management_scope=False,
        )
        rooms = {}
        for bed, room, building in resources:
            if int(building.id) != int(building_id) or not _gender_ok(building, student):
                continue
            value = rooms.setdefault(int(room.id), {
                "roomId": str(room.id), "buildingId": str(building.id), "floorNo": room.floor_no,
                "roomNo": room.room_no, "capacity": room.capacity, "roomType": room.room_type or "",
                "status": room.status, "vacantBeds": 0,
            })
            value["vacantBeds"] += 1
        return {"items": list(rooms.values()), "total": len(rooms)}


def student_beds(user, room_id: int) -> dict:
    from app.services.mobile_student_service import resolve_student
    with session() as db:
        student = resolve_student(db, user)
        found = _student_item(db, student.id, require_open=True) if student else None
        if not found or found[1].mode != "STUDENT_SELECT" or found[0].status != "PENDING":
            raise no_permission("当前没有可用的学生自选住宿批次")
        resources = _resource_rows(
            db, found[1].resource_scope_json or {}, user, vacant_only=True,
            enforce_management_scope=False,
        )
        items = [{"bedId": str(bed.id), "roomId": str(room.id), "bedNo": bed.bed_no,
                  "status": bed.status}
                 for bed, room, building in resources
                 if int(room.id) == int(room_id) and _gender_ok(building, student)]
        return {"items": items}


def student_select_bed(user, bed_id: int) -> dict:
    from app.services.mobile_student_service import resolve_student
    with session() as db:
        student = resolve_student(db, user)
        if not student:
            raise no_permission("尚未建立你的学生档案")
        found = _student_item(db, student.id, require_open=True)
        if not found or found[1].mode != "STUDENT_SELECT":
            raise no_permission("当前没有可用的学生自选住宿批次")
        item, batch = found
        if item.status != "PENDING" or item.bed_id is not None:
            raise AppException("DATA_CONFLICT", "你已确认床位，不能重复自选")
        resources = _resource_rows(
            db, batch.resource_scope_json or {}, user, vacant_only=True,
            enforce_management_scope=False,
        )
        selected = next((row for row in resources if int(row[0].id) == int(bed_id)), None)
        if not selected:
            raise AppException("DATA_CONFLICT", "床位不在当前资源池内或刚刚已被选择")
        bed, room, building = selected
        if not _gender_ok(building, student):
            raise AppException("DATA_CONFLICT", "学生性别信息缺失或与楼栋限制不符")
        _lock_unassigned_student(db, int(student.id))
        # 先原子锁床，再改本人分配项。同床竞争在床位行上统一输出 409，
        # 避免由 allocation-item 唯一约束抢先抛出未分类的 IntegrityError。
        bed_claim = db.execute(update(DormBed).where(
            DormBed.id == bed.id, DormBed.tenant_id == _tid(), DormBed.status == "VACANT",
            DormBed.student_id.is_(None), DormBed.version == bed.version,
            DormBed.is_deleted.is_(False),
        ).values(status="LOCKED", version=DormBed.version + 1))
        if int(bed_claim.rowcount or 0) != 1:
            raise AppException("DATA_CONFLICT", "该床位刚刚已被其他学生选择，请刷新后重试")
        item_claim = db.execute(update(DormAllocationItem).where(
            DormAllocationItem.id == item.id, DormAllocationItem.tenant_id == _tid(),
            DormAllocationItem.status == "PENDING", DormAllocationItem.bed_id.is_(None),
            DormAllocationItem.version == item.version, DormAllocationItem.is_deleted.is_(False),
        ).values(
            bed_id=bed.id, status="CONFIRMED", source="STUDENT_SELECT",
            confirmed_at=datetime.utcnow(), version=DormAllocationItem.version + 1,
        ))
        if int(item_claim.rowcount or 0) != 1:
            raise AppException("DATA_CONFLICT", "选床状态已变化，请刷新后重试")
        db.refresh(item)
        stay = DormStay(
            tenant_id=_tid(), student_id=student.id, bed_id=bed.id,
            building_id=building.id, room_id=room.id, stay_type="ALLOCATION",
            source_type="ALLOCATION", source_biz_id=str(item.id), status="RESERVED",
        )
        db.add(stay)
        _link_orientation(db, batch, item, bed, room, building)
        from app.services import affairs_dorm_service as dorm
        dorm._audit(db, "DORM_ALLOCATION_ITEM", item.id, "STUDENT_CONFIRM", f"bed={bed.id}")
        db.commit()
        return {
            "batchId": str(batch.id), "itemId": str(item.id), "status": "CONFIRMED",
            "bedId": str(bed.id), "building": building.building_name,
            "room": room.room_no, "bedNo": bed.bed_no,
        }


def teacher_summary(user) -> dict:
    now = datetime.utcnow()
    with session() as db:
        rows = db.scalars(select(DormAllocationBatch).where(
            DormAllocationBatch.tenant_id == _tid(), DormAllocationBatch.status == "PUBLISHED",
            DormAllocationBatch.is_deleted.is_(False),
        )).all()
        ctx = _scope_context(db, user)
        scoped_student_ids = None
        if ctx.scope_type == "DORM_BUILDING":
            allowed = set(ctx.dorm_building_ids)
            rows = [row for row in rows if allowed & set(_ids((row.resource_scope_json or {}).get("buildingIds")))]
        elif ctx.scope_type != "TENANT_ALL":
            allowed_classes = ctx.allowed_class_ids(db)
            if not allowed_classes:
                rows = []
                scoped_student_ids = set()
            else:
                scoped_student_ids = set(db.scalars(select(StudentProfile.id).where(
                    StudentProfile.tenant_id == _tid(),
                    StudentProfile.class_id.in_(allowed_classes),
                    StudentProfile.is_deleted.is_(False),
                )).all())
                visible_batch_ids = set(db.scalars(select(DormAllocationItem.allocation_batch_id).where(
                    DormAllocationItem.tenant_id == _tid(),
                    DormAllocationItem.student_id.in_(scoped_student_ids or {-1}),
                    DormAllocationItem.is_deleted.is_(False),
                )).all())
                rows = [row for row in rows if row.id in visible_batch_ids]
        ids = [row.id for row in rows]
        counts = {status: 0 for status in ("PENDING", "RESERVED", "CONFIRMED", "CONFLICT")}
        if ids:
            count_query = select(
                DormAllocationItem.status, func.count(DormAllocationItem.id),
            ).where(
                DormAllocationItem.tenant_id == _tid(),
                DormAllocationItem.allocation_batch_id.in_(ids),
                DormAllocationItem.is_deleted.is_(False),
            )
            if scoped_student_ids is not None:
                count_query = count_query.where(
                    DormAllocationItem.student_id.in_(scoped_student_ids or {-1})
                )
            for status, count in db.execute(count_query.group_by(DormAllocationItem.status)).all():
                if status in counts:
                    counts[status] = int(count)
        return {
            "activeBatchCount": sum(1 for row in rows if row.open_at <= now <= row.close_at),
            "publishedBatchCount": len(rows), "pendingSelectionCount": counts["PENDING"],
            "reservedCount": counts["RESERVED"] + counts["CONFIRMED"],
            "conflictCount": counts["CONFLICT"],
        }


def conflict_workbook(batch_id: int, user) -> bytes:
    data = detail(batch_id, user)
    missing_rows = []
    orientation_batch_id = data["batch"].get("orientationBatchId")
    if orientation_batch_id:
        with session() as db:
            missing_rows = db.scalars(select(OrientationStudent).where(
                OrientationStudent.tenant_id == _tid(),
                OrientationStudent.batch_id == int(orientation_batch_id),
                OrientationStudent.student_id.is_(None),
                OrientationStudent.record_status == "ACTIVE",
                OrientationStudent.is_deleted.is_(False),
            ).order_by(OrientationStudent.id)).all()
    from openpyxl import Workbook
    from openpyxl.styles import Font
    wb = Workbook(); ws = wb.active; ws.title = "住宿分配异常"
    headers = ["批次", "学号", "姓名", "学生ID", "冲突码"]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for item in data["items"]:
        if item["status"] == "CONFLICT":
            ws.append([data["batch"]["name"], item["studentNo"], item["studentName"],
                       item["studentId"], item["conflictCode"]])
    for row in missing_rows:
        ws.append([data["batch"]["name"], row.admission_no or row.source_record_id or "",
                   row.name or "", "", "DATA_MISSING"])
    ws.append(["导出用途", "住宿分配 Dry Run 异常核对", "导出时间", datetime.utcnow().isoformat(), "已按当前账号范围过滤"])
    stream = BytesIO(); wb.save(stream)
    from app.services import affairs_dorm_service as dorm
    with session() as db:
        dorm._audit(db, "DORM_ALLOCATION_BATCH", batch_id, "EXPORT_CONFLICTS",
                    f"rows={sum(1 for item in data['items'] if item['status'] == 'CONFLICT') + len(missing_rows)}")
        db.commit()
    return stream.getvalue()
