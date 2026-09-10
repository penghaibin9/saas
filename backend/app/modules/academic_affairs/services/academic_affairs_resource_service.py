"""13B-R4 教务中心 · 教学资源（教室字典最小闭环）。

方案A：教室字典独立成表 t_aa_classroom；课表 t_aa_schedule_item.classroom_text 保持自由文本快照
不改列（classroom_id 外键化留 backlog）。排课 UI 从本字典选择、容量非阻断 warning（options 端点供数）。

口径：租户级基础数据（tenant_id 行级隔离 + is_deleted=false 逻辑删除）；写操作幂等去重
（同租户 building_code+room_code 唯一，重复 409）；乐观锁 version；全部写操作落 AffairsAuditTrail 审计。
容量校验：capacity >= 0 且 <= 1000（非法 422）。状态机：AVAILABLE ⇄ DISABLED ⇄ MAINTENANCE。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.core.context import get_current_user_ctx
from app.core.exceptions import AppException, not_found
from app.services.db_service import _iso, _tid, session

ROOM_TYPES = {"LECTURE", "MULTIMEDIA", "COMPUTER", "LAB", "OTHER"}
ROOM_TYPE_LABEL = {"LECTURE": "普通教室", "MULTIMEDIA": "多媒体教室", "COMPUTER": "机房",
                   "LAB": "实验室", "OTHER": "其他"}
STATUS_VALUES = {"AVAILABLE", "DISABLED", "MAINTENANCE"}
STATUS_LABEL = {"AVAILABLE": "可用", "DISABLED": "停用", "MAINTENANCE": "维修中"}
MAX_CAPACITY = 1000


def _op():
    u = get_current_user_ctx() or {}
    return (u.get("realName") or "系统"), (u.get("currentRoleCode") or ""), str(u.get("userId") or "")


def _audit(db, biz_id, action, detail="", biz_type="AA_CLASSROOM"):
    from app.models import AffairsAuditTrail
    n, r, uid = _op()
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type=biz_type,
                             biz_id=int(biz_id) if biz_id else None, action=action,
                             operator=n or uid, role_name=r, detail=detail,
                             occurred_at=datetime.utcnow()))


def _row(c) -> dict:
    return {
        "classroomId": str(c.id), "buildingCode": c.building_code, "buildingName": c.building_name,
        "roomCode": c.room_code, "roomName": c.room_name or f"{c.building_name}{c.room_code}",
        "buildingId": str(c.building_id) if c.building_id else None, "floorNo": c.floor_no,
        "examSeats": c.exam_seats, "isExclusive": c.is_exclusive,
        "allowSchedule": c.allow_schedule, "allowExam": c.allow_exam, "allowBorrow": c.allow_borrow,
        "capacity": int(c.capacity or 0), "roomType": c.room_type,
        "roomTypeLabel": ROOM_TYPE_LABEL.get(c.room_type, c.room_type),
        "campusCode": c.campus_code or "", "remark": c.remark or "",
        "status": c.status, "statusLabel": STATUS_LABEL.get(c.status, c.status),
        "createdAt": _iso(c.created_at), "updatedAt": _iso(c.updated_at), "version": c.version,
    }


def _norm_type(v):
    v = (v or "LECTURE").upper()
    if v not in ROOM_TYPES:
        raise AppException("VALIDATION_ERROR", f"教室类型非法（合法值：{'/'.join(sorted(ROOM_TYPES))}）")
    return v


def _norm_capacity(v):
    try:
        n = int(v if v is not None else 0)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "容量必须为整数")
    if n < 0 or n > MAX_CAPACITY:
        raise AppException("VALIDATION_ERROR", f"容量须在 0~{MAX_CAPACITY} 之间")
    return n


def _load(db, classroom_id):
    from app.models import AaClassroom
    c = db.scalar(select(AaClassroom).where(
        AaClassroom.id == int(classroom_id), AaClassroom.tenant_id == _tid(),
    ).with_for_update().execution_options(populate_existing=True)) if classroom_id else None
    if not c or c.is_deleted or c.tenant_id != _tid():
        raise not_found("教室不存在")
    return c


# ═══════════ 查询 ═══════════

def list_classrooms(user, keyword=None, building_code=None, room_type=None, status=None,
                    page=1, page_size=20, building_id=None, floor_no=None):
    from app.models import AaClassroom
    page_size = max(1, min(100, page_size))
    with session() as db:
        conds = [AaClassroom.tenant_id == _tid(), AaClassroom.is_deleted.is_(False)]
        if building_id:
            conds.append(AaClassroom.building_id == int(building_id))
        if floor_no == 0:
            conds.append(AaClassroom.floor_no.is_(None))
        elif floor_no:
            conds.append(AaClassroom.floor_no == floor_no)
        if building_code:
            conds.append(AaClassroom.building_code == building_code)
        if room_type:
            conds.append(AaClassroom.room_type == room_type)
        if status:
            conds.append(AaClassroom.status == status)
        if keyword:
            kw = f"%{keyword.strip()}%"
            conds.append((AaClassroom.building_name.like(kw)) | (AaClassroom.room_code.like(kw)) |
                         (AaClassroom.room_name.like(kw)) | (AaClassroom.building_code.like(kw)))
        total = db.scalar(select(func.count()).select_from(AaClassroom).where(*conds)) or 0
        offset = (max(1, page) - 1) * page_size
        rows = db.scalars(select(AaClassroom).where(*conds)
                          .order_by(AaClassroom.building_code, AaClassroom.floor_no, AaClassroom.room_code, AaClassroom.id)
                          .offset(offset).limit(page_size)).all()
        return [_row(c) for c in rows], total


def get_classroom(classroom_id, user) -> dict:
    with session() as db:
        return _row(_load(db, classroom_id))


def list_options(user, keyword=None, purpose=None):
    """排课 UI 供数：仅返回可用(AVAILABLE)教室的精简项（含 capacity 供非阻断容量 warning）。"""
    from app.models import AaClassroom
    with session() as db:
        conds = [AaClassroom.tenant_id == _tid(), AaClassroom.is_deleted.is_(False),
                 AaClassroom.status == "AVAILABLE"]
        rule = {"SCHEDULE": AaClassroom.allow_schedule, "EXAM": AaClassroom.allow_exam,
                "BORROW": AaClassroom.allow_borrow}.get(purpose)
        if rule is not None:
            conds.append(rule.is_(True))
        if keyword:
            kw = f"%{keyword.strip()}%"
            conds.append((AaClassroom.building_name.like(kw)) | (AaClassroom.room_code.like(kw)) |
                         (AaClassroom.room_name.like(kw)))
        rows = db.scalars(select(AaClassroom).where(*conds)
                          .order_by(AaClassroom.building_code, AaClassroom.room_code)
                          .limit(500)).all()
        return [{"classroomId": str(c.id),
                 "label": (c.room_name or f"{c.building_name}{c.room_code}"),
                 "buildingName": c.building_name, "roomCode": c.room_code,
                 "allowSchedule": c.allow_schedule, "allowExam": c.allow_exam, "allowBorrow": c.allow_borrow,
                 "examSeats": c.exam_seats,
                 "capacity": int(c.capacity or 0), "roomType": c.room_type} for c in rows]


# ═══════════ 写侧 ═══════════

def create_classroom(body, user) -> dict:
    from app.models import AaClassroom
    building_code = (getattr(body, "buildingCode", None) or "").strip()
    building_name = (getattr(body, "buildingName", None) or "").strip()
    room_code = (getattr(body, "roomCode", None) or "").strip()
    if not building_code or not building_name or not room_code:
        raise AppException("VALIDATION_ERROR", "楼栋编码、楼栋名称、教室编号均必填")
    room_type = _norm_type(getattr(body, "roomType", None))
    capacity = _norm_capacity(getattr(body, "capacity", None))
    with session() as db:
        from app.modules.academic_affairs.services.academic_affairs_classroom_catalog_service import bind_location
        location = bind_location(db, body)
        # 含逻辑删除一并查（唯一约束 uk_aa_classroom 覆盖已删行，需就地复活而非再插入）
        existing = db.scalars(select(AaClassroom).where(
            AaClassroom.tenant_id == _tid(), AaClassroom.building_code == building_code,
            AaClassroom.room_code == room_code)).first()
        if existing and not existing.is_deleted:
            raise AppException("DATA_CONFLICT", "该楼栋下已存在同编号教室")
        room_name = getattr(body, "roomName", None) or None
        campus_code = getattr(body, "campusCode", None) or None
        remark = getattr(body, "remark", None) or None
        if existing and existing.is_deleted:
            # 复活：覆盖为本次录入并重置为可用
            existing.building_name, existing.room_name = building_name, room_name
            existing.capacity, existing.room_type = capacity, room_type
            existing.campus_code, existing.remark = campus_code, remark
            existing.status, existing.is_deleted = "AVAILABLE", False
            existing.version += 1
            c = existing
            _audit(db, c.id, "CREATE", f"{building_name}{room_code}(复活)")
        else:
            c = AaClassroom(tenant_id=_tid(), building_code=building_code, building_name=building_name,
                            room_code=room_code, room_name=room_name, capacity=capacity,
                            room_type=room_type, campus_code=campus_code, remark=remark,
                            status="AVAILABLE")
            db.add(c)
            db.flush()
            _audit(db, c.id, "CREATE", f"{building_name}{room_code}")
        c.building_id, c.floor_no = location
        c.exam_seats = getattr(body, "examSeats", None)
        c.is_exclusive = bool(getattr(body, "isExclusive", False))
        c.allow_schedule = getattr(body, "allowSchedule", True)
        c.allow_exam = getattr(body, "allowExam", True)
        c.allow_borrow = getattr(body, "allowBorrow", False)
        db.commit()
        db.refresh(c)
        return _row(c)


def update_classroom(classroom_id, body, user) -> dict:
    with session() as db:
        from app.models import AaClassroom
        c = _load(db, classroom_id)
        expected = getattr(body, "expectedVersion", None)
        if expected is not None and expected != c.version:
            raise AppException("DATA_CONFLICT", "教室资料已变化，请重新读取后核对修改")
        from app.modules.academic_affairs.services.academic_affairs_classroom_catalog_service import bind_location
        c.building_id, c.floor_no = bind_location(db, body, c)
        if "examSeats" in body.model_fields_set:
            c.exam_seats = body.examSeats
        if getattr(body, "isExclusive", None) is not None:
            c.is_exclusive = body.isExclusive
        for field, attr in (("allowSchedule", "allow_schedule"), ("allowExam", "allow_exam"), ("allowBorrow", "allow_borrow")):
            if getattr(body, field, None) is not None:
                setattr(c, attr, getattr(body, field))
        building_code = (getattr(body, "buildingCode", None) or c.building_code).strip()
        room_code = (getattr(body, "roomCode", None) or c.room_code).strip()
        # 改动唯一键需再次去重（排除自身）
        if building_code != c.building_code or room_code != c.room_code:
            dup = db.scalars(select(AaClassroom).where(
                AaClassroom.tenant_id == _tid(), AaClassroom.building_code == building_code,
                AaClassroom.room_code == room_code, AaClassroom.id != c.id,
                AaClassroom.is_deleted.is_(False))).first()
            if dup:
                raise AppException("DATA_CONFLICT", "该楼栋下已存在同编号教室")
        c.building_code = building_code
        c.room_code = room_code
        if getattr(body, "buildingName", None):
            c.building_name = body.buildingName.strip()
        if getattr(body, "roomName", None) is not None:
            c.room_name = body.roomName or None
        if getattr(body, "roomType", None):
            c.room_type = _norm_type(body.roomType)
        if getattr(body, "capacity", None) is not None:
            c.capacity = _norm_capacity(body.capacity)
        if getattr(body, "campusCode", None) is not None:
            c.campus_code = body.campusCode or None
        if getattr(body, "remark", None) is not None:
            c.remark = body.remark or None
        c.version += 1
        _audit(db, c.id, "UPDATE", f"{c.building_name}{c.room_code}")
        db.commit()
        db.refresh(c)
        return _row(c)


def set_status(classroom_id, target_status, user, reason="") -> dict:
    target = (target_status or "").upper()
    if target not in STATUS_VALUES:
        raise AppException("VALIDATION_ERROR", f"状态非法（合法值：{'/'.join(sorted(STATUS_VALUES))}）")
    with session() as db:
        c = _load(db, classroom_id)
        if c.status == target:
            return _row(c)  # 幂等
        old = c.status
        c.status = target
        c.version += 1
        _audit(db, c.id, "STATUS", f"{old}->{target}" + (f"（{reason.strip()}）" if reason else ""))
        db.commit()
        db.refresh(c)
        return _row(c)


def delete_classroom(classroom_id, user) -> dict:
    """逻辑删除教室字典项。占用校验为非阻断（方案A课表用文本快照，删字典不影响历史课表）。"""
    with session() as db:
        c = _load(db, classroom_id)
        c.is_deleted = True
        c.version += 1
        _audit(db, c.id, "DELETE", f"{c.building_name}{c.room_code}")
        db.commit()
        return {"classroomId": str(classroom_id), "deleted": True}


# ══════════ 教室预约（占用登记 + 冲突检测 + 审核） ══════════

def _bkg_dto(b):
    return {"bookingId": str(b.id), "classroomId": str(b.classroom_id), "classroomText": b.classroom_text,
            "bookingDate": b.booking_date, "slotNo": b.slot_no, "purpose": b.purpose,
            "applicantKey": b.applicant_key, "applicantName": b.applicant_name,
            "reviewReason": b.review_reason, "status": b.status}


def book_classroom(user, body, *, command_key=None):
    """申请教室预约。同教室同日同节次已 APPROVED → 409（占用冲突）。"""
    from app.models import AaClassroomBooking, AaClassroom
    from . import academic_affairs_grade_command_receipt as receipts
    with session() as db:
        receipt, cached = receipts.begin(db, user, "RESOURCE_CLASSROOM_BOOK", command_key, body.model_dump())
        if cached is not None:
            return cached
        cid = int(body.classroomId)
        c = db.query(AaClassroom).filter(AaClassroom.id == cid, AaClassroom.tenant_id == _tid(),
                                         AaClassroom.is_deleted.is_(False)).with_for_update().first()
        if not c:
            raise not_found("教室不存在")
        if c.status != "AVAILABLE":
            raise AppException("DATA_CONFLICT", "该教室不可用（停用/维修中）", http_status=409)
        if not c.allow_borrow:
            raise AppException("DATA_CONFLICT", "该教室未开放借用", http_status=409)
        date = (getattr(body, "bookingDate", None) or "").strip()
        slot = int(getattr(body, "slotNo", 0) or 0)
        if not date or not slot:
            raise AppException("VALIDATION_ERROR", "预约日期与节次必填")
        conflict = db.query(AaClassroomBooking).filter(AaClassroomBooking.tenant_id == _tid(),
                                                       AaClassroomBooking.classroom_id == cid,
                                                       AaClassroomBooking.booking_date == date,
                                                       AaClassroomBooking.slot_no == slot,
                                                       AaClassroomBooking.status == "APPROVED",
                                                       AaClassroomBooking.is_deleted.is_(False)).first()
        if conflict:
            raise AppException("DATA_CONFLICT", "该教室该时段已被预约占用", http_status=409)
        name, _r, uid = _op()
        b = AaClassroomBooking(tenant_id=_tid(), classroom_id=cid,
                               classroom_text=f"{c.building_name}{c.room_code}", booking_date=date, slot_no=slot,
                               purpose=getattr(body, "purpose", None), applicant_key=uid or name,
                               applicant_name=name, status="PENDING")
        db.add(b); db.flush()
        _audit(db, b.id, "BOOKING_APPLY", f"预约 {b.classroom_text} {date} 第{slot}节")
        result = _bkg_dto(b)
        receipts.finish(db, receipt, result)
        db.commit()
        return result


def list_bookings(user, classroom_id=None, date=None, status=None, page=1, page_size=50, *, booking_id=None):
    from app.models import AaClassroomBooking
    with session() as db:
        q = db.query(AaClassroomBooking).filter(AaClassroomBooking.tenant_id == _tid(),
                                                AaClassroomBooking.is_deleted.is_(False))
        if classroom_id:
            q = q.filter(AaClassroomBooking.classroom_id == int(classroom_id))
        if date:
            q = q.filter(AaClassroomBooking.booking_date == date)
        if status:
            q = q.filter(AaClassroomBooking.status == status)
        if booking_id is not None:
            q = q.filter(AaClassroomBooking.id == int(booking_id))
        total = q.count()
        rows = q.order_by(AaClassroomBooking.id.desc()).offset((max(1, page) - 1) * page_size).limit(page_size).all()
        return [_bkg_dto(b) for b in rows], total


def _require_no_open_repair(db, kind, resource_id):
    from app.models import AaResourceRepair
    repair = db.query(AaResourceRepair).filter(
        AaResourceRepair.tenant_id == _tid(), AaResourceRepair.resource_kind == kind,
        AaResourceRepair.resource_id == int(resource_id),
        AaResourceRepair.status.in_(["REPORTED", "IN_REPAIR"]),
        AaResourceRepair.is_deleted.is_(False),
    ).with_for_update().populate_existing().first()
    if repair:
        raise AppException("DATA_CONFLICT", "资源仍有未完成维修工单，不能批准借用", http_status=409,
                           details={"repairId": str(repair.id), "resourceKind": kind, "resourceId": str(resource_id)})


def review_booking(user, booking_id, action, reason="", *, command_key=None):
    """审核预约：APPROVE(再查冲突)/REJECT(原因≥5字)。"""
    from app.models import AaClassroomBooking
    from . import academic_affairs_grade_command_receipt as receipts
    with session() as db:
        receipt, cached = receipts.begin(db, user, "RESOURCE_CLASSROOM_REVIEW", command_key, {"bookingId": str(booking_id), "action": action, "reason": reason, "identity": None})
        if cached is not None:
            return cached
        resource_id = db.scalar(select(AaClassroomBooking.classroom_id).where(
            AaClassroomBooking.id == booking_id, AaClassroomBooking.tenant_id == _tid(),
            AaClassroomBooking.is_deleted.is_(False),
        ))
        if resource_id is None:
            raise not_found("预约不存在")
        # One resource mutex before booking rows, so concurrent approvals of two
        # different requests cannot each hold a booking row while waiting on the other.
        classroom = _load(db, resource_id) if action == "APPROVE" else None
        b = db.query(AaClassroomBooking).filter(AaClassroomBooking.id == booking_id,
                                                AaClassroomBooking.tenant_id == _tid(),
                                                AaClassroomBooking.is_deleted.is_(False)).with_for_update().populate_existing().first()
        if not b:
            raise not_found("预约不存在")
        if b.status != "PENDING":
            raise AppException("DATA_CONFLICT", "该预约已处理", http_status=409)
        if b.classroom_id != resource_id:
            raise AppException("DATA_CONFLICT", "预约资源已变化，请重新核对", http_status=409)
        if action == "APPROVE":
            if classroom.status != "AVAILABLE" or not classroom.allow_borrow:
                raise AppException("DATA_CONFLICT", "该教室当前不可用或未开放借用，请重新核对", http_status=409)
            _require_no_open_repair(db, "CLASSROOM", b.classroom_id)
            conflict = db.query(AaClassroomBooking).filter(AaClassroomBooking.tenant_id == _tid(),
                                                           AaClassroomBooking.classroom_id == b.classroom_id,
                                                           AaClassroomBooking.booking_date == b.booking_date,
                                                           AaClassroomBooking.slot_no == b.slot_no,
                                                           AaClassroomBooking.status == "APPROVED",
                                                           AaClassroomBooking.id != b.id,
                                                           AaClassroomBooking.is_deleted.is_(False)).with_for_update().populate_existing().first()
            if conflict:
                raise AppException("DATA_CONFLICT", "该时段已有通过的预约，冲突", http_status=409)
            from .academic_affairs_schedule_resource_guard import require_booking_slot_free
            require_booking_slot_free(b.classroom_id, b.booking_date, b.slot_no)
            from .academic_affairs_lab_room_service import require_no_lab_booking
            require_no_lab_booking(db, b.classroom_id, b.booking_date, b.slot_no)
            b.status = "APPROVED"
        elif action == "REJECT":
            reason = (reason or "").strip()
            if len(reason) < 5:
                raise AppException("VALIDATION_ERROR", "驳回原因必填且不少于5字")
            b.status = "REJECTED"
            b.review_reason = reason
        else:
            raise AppException("VALIDATION_ERROR", "非法动作")
        _audit(db, b.id, "BOOKING_REVIEW", action)
        result = _bkg_dto(b)
        receipts.finish(db, receipt, result)
        db.commit()
        return result


# ══════════════════════════════════════════════════════════════════════════════
# 教学资源续卡（实训室资源/设备资源/实训室预约/资源占用/资源冲突/资源维修/资源统计）
# 复用上方教室字典+教室预约已验证的字段口径/状态机/冲突检测算法，不改动已上线的
# t_aa_classroom / t_aa_classroom_booking 结构与既有端点行为。
# 设计来源：见 docs/03-业务模块设计/教务中心/施工包/教学资源-生产级施工包.md §续卡
# 与 docs/03-业务模块设计/教务中心/施工包/外部对标证据/01-教学资源-外部对标证据包.md §续卡新增证据
# ══════════════════════════════════════════════════════════════════════════════

LAB_TYPES = {"SKILL", "COMPUTER", "MECHANICAL", "ELECTRICAL", "OTHER"}
LAB_TYPE_LABEL = {"SKILL": "技能实训室", "COMPUTER": "计算机实训室", "MECHANICAL": "机械实训室",
                  "ELECTRICAL": "电气实训室", "OTHER": "其他"}

EQUIPMENT_STATUS_VALUES = {"IN_USE", "IDLE", "MAINTENANCE", "SCRAPPED"}
EQUIPMENT_STATUS_LABEL = {"IN_USE": "在用", "IDLE": "闲置", "MAINTENANCE": "维修中", "SCRAPPED": "已报废"}
OWNER_KINDS = {"CLASSROOM", "LAB", "NONE"}

REPAIR_STATUS_VALUES = {"REPORTED", "IN_REPAIR", "DONE", "CANCELLED"}
REPAIR_STATUS_LABEL = {"REPORTED": "已报修", "IN_REPAIR": "维修中", "DONE": "已完成", "CANCELLED": "已取消"}
REPAIR_RESOURCE_KINDS = {"CLASSROOM", "LAB", "EQUIPMENT"}


# ─────────── 实训室资源（结构对齐教室字典，另加责任人字段） ───────────

def _lab_row(lab) -> dict:
    return {
        "labId": str(lab.id), "labCode": lab.lab_code, "labName": lab.lab_name,
        "classroomId": str(lab.classroom_id) if lab.classroom_id else None,
        "buildingName": lab.building_name or "", "capacity": int(lab.capacity or 0),
        "labType": lab.lab_type, "labTypeLabel": LAB_TYPE_LABEL.get(lab.lab_type, lab.lab_type),
        "responsibleName": lab.responsible_name or "", "responsibleKey": lab.responsible_key or "",
        "remark": lab.remark or "", "status": lab.status,
        "statusLabel": STATUS_LABEL.get(lab.status, lab.status),
        "createdAt": _iso(lab.created_at), "updatedAt": _iso(lab.updated_at), "version": lab.version,
    }


def _norm_lab_type(v):
    v = (v or "SKILL").upper()
    if v not in LAB_TYPES:
        raise AppException("VALIDATION_ERROR", f"实训室类型非法（合法值：{'/'.join(sorted(LAB_TYPES))}）")
    return v


def _load_lab(db, lab_id, *, lock=False):
    from app.models import AaLabResource
    query = select(AaLabResource).where(AaLabResource.id == int(lab_id or 0), AaLabResource.tenant_id == _tid())
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    lab = db.scalar(query) if lab_id else None
    if not lab or lab.is_deleted or lab.tenant_id != _tid():
        raise not_found("实训室不存在")
    return lab


def list_labs(user, keyword=None, lab_type=None, status=None, page=1, page_size=20):
    from app.models import AaLabResource
    with session() as db:
        conds = [AaLabResource.tenant_id == _tid(), AaLabResource.is_deleted.is_(False)]
        if lab_type:
            conds.append(AaLabResource.lab_type == lab_type)
        if status:
            conds.append(AaLabResource.status == status)
        if keyword:
            kw = f"%{keyword.strip()}%"
            conds.append((AaLabResource.lab_name.like(kw)) | (AaLabResource.lab_code.like(kw)) |
                         (AaLabResource.building_name.like(kw)))
        total = db.scalar(select(func.count()).select_from(AaLabResource).where(*conds)) or 0
        offset = (max(1, page) - 1) * page_size
        rows = db.scalars(select(AaLabResource).where(*conds)
                          .order_by(AaLabResource.lab_code)
                          .offset(offset).limit(page_size)).all()
        return [_lab_row(c) for c in rows], total


def get_lab(lab_id, user) -> dict:
    with session() as db:
        return _lab_row(_load_lab(db, lab_id))


def list_lab_options(user, keyword=None):
    """实训室预约表单供数：仅返回可用(AVAILABLE)实训室的精简项。"""
    from app.models import AaLabResource
    with session() as db:
        conds = [AaLabResource.tenant_id == _tid(), AaLabResource.is_deleted.is_(False),
                 AaLabResource.status == "AVAILABLE"]
        if keyword:
            kw = f"%{keyword.strip()}%"
            conds.append((AaLabResource.lab_name.like(kw)) | (AaLabResource.lab_code.like(kw)))
        rows = db.scalars(select(AaLabResource).where(*conds)
                          .order_by(AaLabResource.lab_code).limit(500)).all()
        return [{"labId": str(c.id), "label": c.lab_name, "labCode": c.lab_code,
                 "capacity": int(c.capacity or 0), "labType": c.lab_type} for c in rows]


def create_lab(body, user) -> dict:
    from app.models import AaLabResource
    lab_code = (getattr(body, "labCode", None) or "").strip()
    lab_name = (getattr(body, "labName", None) or "").strip()
    if not lab_code or not lab_name:
        raise AppException("VALIDATION_ERROR", "实训室编号、名称均必填")
    lab_type = _norm_lab_type(getattr(body, "labType", None))
    capacity = _norm_capacity(getattr(body, "capacity", None))
    with session() as db:
        existing = db.scalars(select(AaLabResource).where(
            AaLabResource.tenant_id == _tid(), AaLabResource.lab_code == lab_code)).first()
        if existing and not existing.is_deleted:
            raise AppException("DATA_CONFLICT", "该实训室编号已存在")
        building_name = getattr(body, "buildingName", None) or None
        responsible_name = getattr(body, "responsibleName", None) or None
        responsible_key = getattr(body, "responsibleKey", None) or None
        remark = getattr(body, "remark", None) or None
        if existing and existing.is_deleted:
            existing.lab_name, existing.building_name = lab_name, building_name
            existing.capacity, existing.lab_type = capacity, lab_type
            existing.responsible_name, existing.responsible_key = responsible_name, responsible_key
            existing.remark = remark
            existing.status, existing.is_deleted = "AVAILABLE", False
            existing.version += 1
            lab = existing
            _audit(db, lab.id, "CREATE", f"{lab_name}(复活)", biz_type="AA_LAB")
        else:
            lab = AaLabResource(tenant_id=_tid(), lab_code=lab_code, lab_name=lab_name,
                                building_name=building_name, capacity=capacity, lab_type=lab_type,
                                responsible_name=responsible_name, responsible_key=responsible_key,
                                remark=remark, status="AVAILABLE")
            db.add(lab)
            db.flush()
            _audit(db, lab.id, "CREATE", lab_name, biz_type="AA_LAB")
        db.commit()
        db.refresh(lab)
        return _lab_row(lab)


def update_lab(lab_id, body, user) -> dict:
    with session() as db:
        from app.models import AaLabResource
        lab = _load_lab(db, lab_id, lock=True)
        lab_code = (getattr(body, "labCode", None) or lab.lab_code).strip()
        if lab_code != lab.lab_code:
            dup = db.scalars(select(AaLabResource).where(
                AaLabResource.tenant_id == _tid(), AaLabResource.lab_code == lab_code,
                AaLabResource.id != lab.id, AaLabResource.is_deleted.is_(False))).first()
            if dup:
                raise AppException("DATA_CONFLICT", "该实训室编号已存在")
        lab.lab_code = lab_code
        if getattr(body, "labName", None):
            lab.lab_name = body.labName.strip()
        if getattr(body, "buildingName", None) is not None:
            lab.building_name = body.buildingName or None
        if getattr(body, "labType", None):
            lab.lab_type = _norm_lab_type(body.labType)
        if getattr(body, "capacity", None) is not None:
            lab.capacity = _norm_capacity(body.capacity)
        if getattr(body, "responsibleName", None) is not None:
            lab.responsible_name = body.responsibleName or None
        if getattr(body, "responsibleKey", None) is not None:
            lab.responsible_key = body.responsibleKey or None
        if getattr(body, "remark", None) is not None:
            lab.remark = body.remark or None
        lab.version += 1
        _audit(db, lab.id, "UPDATE", lab.lab_name, biz_type="AA_LAB")
        db.commit()
        db.refresh(lab)
        return _lab_row(lab)


def set_lab_status(lab_id, target_status, user, reason="") -> dict:
    target = (target_status or "").upper()
    if target not in STATUS_VALUES:
        raise AppException("VALIDATION_ERROR", f"状态非法（合法值：{'/'.join(sorted(STATUS_VALUES))}）")
    with session() as db:
        lab = _load_lab(db, lab_id)
        if lab.status == target:
            return _lab_row(lab)  # 幂等
        old = lab.status
        lab.status = target
        lab.version += 1
        _audit(db, lab.id, "STATUS", f"{old}->{target}" + (f"（{reason.strip()}）" if reason else ""),
              biz_type="AA_LAB")
        db.commit()
        db.refresh(lab)
        return _lab_row(lab)


def delete_lab(lab_id, user) -> dict:
    with session() as db:
        lab = _load_lab(db, lab_id)
        lab.is_deleted = True
        lab.version += 1
        _audit(db, lab.id, "DELETE", lab.lab_name, biz_type="AA_LAB")
        db.commit()
        return {"labId": str(lab_id), "deleted": True}


# ─────────── 设备资源（教学/实训设备台账） ───────────

def _equip_row(e) -> dict:
    return {
        "equipmentId": str(e.id), "equipmentCode": e.equipment_code, "equipmentName": e.equipment_name,
        "specModel": e.spec_model or "", "quantity": int(e.quantity or 1),
        "ownerKind": e.owner_kind, "ownerId": str(e.owner_id) if e.owner_id else "",
        "ownerLabel": e.owner_label or "", "responsibleName": e.responsible_name or "",
        "purchaseDate": e.purchase_date or "", "status": e.status,
        "statusLabel": EQUIPMENT_STATUS_LABEL.get(e.status, e.status), "remark": e.remark or "",
        "createdAt": _iso(e.created_at), "updatedAt": _iso(e.updated_at), "version": e.version,
    }


def _norm_equipment_status(v):
    v = (v or "IN_USE").upper()
    if v not in EQUIPMENT_STATUS_VALUES:
        raise AppException("VALIDATION_ERROR", f"设备状态非法（合法值：{'/'.join(sorted(EQUIPMENT_STATUS_VALUES))}）")
    return v


def _resolve_owner_label(db, owner_kind, owner_id):
    """把 owner_kind+owner_id 解析为位置文本快照（引用教室/实训室字典只读，不建外键约束）。"""
    if not owner_id or owner_kind == "NONE":
        return None
    from app.models import AaClassroom, AaLabResource
    if owner_kind == "CLASSROOM":
        c = db.get(AaClassroom, int(owner_id))
        return f"{c.building_name}{c.room_code}" if c else None
    if owner_kind == "LAB":
        lab = db.get(AaLabResource, int(owner_id))
        return lab.lab_name if lab else None
    return None


def _load_equipment(db, equipment_id):
    from app.models import AaEquipment
    e = db.get(AaEquipment, int(equipment_id)) if equipment_id else None
    if not e or e.is_deleted or e.tenant_id != _tid():
        raise not_found("设备不存在")
    return e


def list_equipment(user, keyword=None, owner_kind=None, status=None, page=1, page_size=20):
    from app.models import AaEquipment
    with session() as db:
        conds = [AaEquipment.tenant_id == _tid(), AaEquipment.is_deleted.is_(False)]
        if owner_kind:
            conds.append(AaEquipment.owner_kind == owner_kind)
        if status:
            conds.append(AaEquipment.status == status)
        if keyword:
            kw = f"%{keyword.strip()}%"
            conds.append((AaEquipment.equipment_name.like(kw)) | (AaEquipment.equipment_code.like(kw)) |
                         (AaEquipment.spec_model.like(kw)))
        total = db.scalar(select(func.count()).select_from(AaEquipment).where(*conds)) or 0
        offset = (max(1, page) - 1) * page_size
        rows = db.scalars(select(AaEquipment).where(*conds)
                          .order_by(AaEquipment.equipment_code)
                          .offset(offset).limit(page_size)).all()
        return [_equip_row(e) for e in rows], total


def get_equipment(equipment_id, user) -> dict:
    with session() as db:
        return _equip_row(_load_equipment(db, equipment_id))


def create_equipment(body, user) -> dict:
    from app.models import AaEquipment
    code = (getattr(body, "equipmentCode", None) or "").strip()
    name = (getattr(body, "equipmentName", None) or "").strip()
    if not code or not name:
        raise AppException("VALIDATION_ERROR", "资产编号、设备名称均必填")
    owner_kind = (getattr(body, "ownerKind", None) or "NONE").upper()
    if owner_kind not in OWNER_KINDS:
        raise AppException("VALIDATION_ERROR", f"所属位置类型非法（合法值：{'/'.join(sorted(OWNER_KINDS))}）")
    qty_raw = getattr(body, "quantity", None)
    try:
        qty = int(qty_raw) if qty_raw is not None else 1
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "数量必须为整数")
    if qty <= 0:
        raise AppException("VALIDATION_ERROR", "数量必须大于0")
    status = _norm_equipment_status(getattr(body, "status", None) or "IN_USE")
    with session() as db:
        existing = db.scalars(select(AaEquipment).where(
            AaEquipment.tenant_id == _tid(), AaEquipment.equipment_code == code)).first()
        if existing and not existing.is_deleted:
            raise AppException("DATA_CONFLICT", "该资产编号已存在")
        owner_id_raw = getattr(body, "ownerId", None) or None
        try:
            owner_id = int(owner_id_raw) if owner_id_raw else None
        except (TypeError, ValueError):
            raise AppException("VALIDATION_ERROR", "所在位置ID必须为数字")
        owner_label = _resolve_owner_label(db, owner_kind, owner_id) if owner_id else None
        spec_model = getattr(body, "specModel", None) or None
        responsible_name = getattr(body, "responsibleName", None) or None
        purchase_date = getattr(body, "purchaseDate", None) or None
        remark = getattr(body, "remark", None) or None
        if existing and existing.is_deleted:
            existing.equipment_name, existing.spec_model = name, spec_model
            existing.quantity, existing.owner_kind = qty, owner_kind
            existing.owner_id, existing.owner_label = owner_id, owner_label
            existing.responsible_name, existing.purchase_date = responsible_name, purchase_date
            existing.remark, existing.status = remark, status
            existing.is_deleted = False
            existing.version += 1
            e = existing
            _audit(db, e.id, "CREATE", f"{name}(复活)", biz_type="AA_EQUIPMENT")
        else:
            e = AaEquipment(tenant_id=_tid(), equipment_code=code, equipment_name=name,
                            spec_model=spec_model, quantity=qty, owner_kind=owner_kind,
                            owner_id=owner_id, owner_label=owner_label, responsible_name=responsible_name,
                            purchase_date=purchase_date, status=status, remark=remark)
            db.add(e)
            db.flush()
            _audit(db, e.id, "CREATE", name, biz_type="AA_EQUIPMENT")
        db.commit()
        db.refresh(e)
        return _equip_row(e)


def update_equipment(equipment_id, body, user) -> dict:
    with session() as db:
        from app.models import AaEquipment
        e = _load_equipment(db, equipment_id)
        code = (getattr(body, "equipmentCode", None) or e.equipment_code).strip()
        if code != e.equipment_code:
            dup = db.scalars(select(AaEquipment).where(
                AaEquipment.tenant_id == _tid(), AaEquipment.equipment_code == code,
                AaEquipment.id != e.id, AaEquipment.is_deleted.is_(False))).first()
            if dup:
                raise AppException("DATA_CONFLICT", "该资产编号已存在")
        e.equipment_code = code
        if getattr(body, "equipmentName", None):
            e.equipment_name = body.equipmentName.strip()
        if getattr(body, "specModel", None) is not None:
            e.spec_model = body.specModel or None
        if getattr(body, "quantity", None) is not None:
            try:
                q = int(body.quantity)
            except (TypeError, ValueError):
                raise AppException("VALIDATION_ERROR", "数量必须为整数")
            if q <= 0:
                raise AppException("VALIDATION_ERROR", "数量必须大于0")
            e.quantity = q
        if getattr(body, "ownerKind", None):
            ok = body.ownerKind.upper()
            if ok not in OWNER_KINDS:
                raise AppException("VALIDATION_ERROR", f"所属位置类型非法（合法值：{'/'.join(sorted(OWNER_KINDS))}）")
            e.owner_kind = ok
        if getattr(body, "ownerId", None) is not None:
            try:
                e.owner_id = int(body.ownerId) if body.ownerId else None
            except (TypeError, ValueError):
                raise AppException("VALIDATION_ERROR", "所在位置ID必须为数字")
            e.owner_label = _resolve_owner_label(db, e.owner_kind, e.owner_id) if e.owner_id else None
        if getattr(body, "responsibleName", None) is not None:
            e.responsible_name = body.responsibleName or None
        if getattr(body, "purchaseDate", None) is not None:
            e.purchase_date = body.purchaseDate or None
        if getattr(body, "remark", None) is not None:
            e.remark = body.remark or None
        e.version += 1
        _audit(db, e.id, "UPDATE", e.equipment_name, biz_type="AA_EQUIPMENT")
        db.commit()
        db.refresh(e)
        return _equip_row(e)


def set_equipment_status(equipment_id, target_status, user, reason="") -> dict:
    target = _norm_equipment_status(target_status)
    with session() as db:
        e = _load_equipment(db, equipment_id)
        if e.status == target:
            return _equip_row(e)  # 幂等
        old = e.status
        e.status = target
        e.version += 1
        _audit(db, e.id, "STATUS", f"{old}->{target}" + (f"（{reason.strip()}）" if reason else ""),
              biz_type="AA_EQUIPMENT")
        db.commit()
        db.refresh(e)
        return _equip_row(e)


def delete_equipment(equipment_id, user) -> dict:
    with session() as db:
        e = _load_equipment(db, equipment_id)
        e.is_deleted = True
        e.version += 1
        _audit(db, e.id, "DELETE", e.equipment_name, biz_type="AA_EQUIPMENT")
        db.commit()
        return {"equipmentId": str(equipment_id), "deleted": True}


# ─────────── 实训室预约（占用登记+冲突检测+审核；与教室预约同一算法，表结构独立） ───────────

def _lab_bkg_dto(b, lab=None):
    return {"bookingId": str(b.id), "labId": str(b.lab_id), "labText": b.lab_text,
            "classroomId": str(b.classroom_id) if b.classroom_id else None,
            "mappedClassroomId": str(lab.classroom_id) if lab and lab.classroom_id else None,
            "labVersion": int(lab.version or 0) if lab else None,
            "bookingDate": b.booking_date, "slotNo": b.slot_no, "purpose": b.purpose,
            "applicantKey": b.applicant_key, "applicantName": b.applicant_name,
            "reviewReason": b.review_reason, "status": b.status}


def book_lab(user, body, *, command_key=None):
    """申请实训室预约。同实训室同日同节次已 APPROVED → 409（占用冲突），与 book_classroom 同一算法。"""
    from app.models import AaLabBooking, AaLabResource
    from . import academic_affairs_grade_command_receipt as receipts
    with session() as db:
        receipt, cached = receipts.begin(db, user, "RESOURCE_LAB_BOOK", command_key, body.model_dump())
        if cached is not None:
            return cached
        lid = int(body.labId)
        lab = db.query(AaLabResource).filter(AaLabResource.id == lid, AaLabResource.tenant_id == _tid(),
                                             AaLabResource.is_deleted.is_(False)).first()
        if not lab:
            raise not_found("实训室不存在")
        if lab.status != "AVAILABLE":
            raise AppException("DATA_CONFLICT", "该实训室不可用（停用/维修中）", http_status=409)
        date = (getattr(body, "bookingDate", None) or "").strip()
        slot = int(getattr(body, "slotNo", 0) or 0)
        if not date or not slot:
            raise AppException("VALIDATION_ERROR", "预约日期与节次必填")
        conflict = db.query(AaLabBooking).filter(AaLabBooking.tenant_id == _tid(),
                                                  AaLabBooking.lab_id == lid,
                                                  AaLabBooking.booking_date == date,
                                                  AaLabBooking.slot_no == slot,
                                                  AaLabBooking.status == "APPROVED",
                                                  AaLabBooking.is_deleted.is_(False)).first()
        if conflict:
            raise AppException("DATA_CONFLICT", "该实训室该时段已被预约占用", http_status=409)
        name, _r, uid = _op()
        b = AaLabBooking(tenant_id=_tid(), lab_id=lid, lab_text=lab.lab_name, booking_date=date, slot_no=slot,
                         purpose=getattr(body, "purpose", None), applicant_key=uid or name,
                         applicant_name=name, status="PENDING")
        db.add(b); db.flush()
        _audit(db, b.id, "BOOKING_APPLY", f"预约 {b.lab_text} {date} 第{slot}节", biz_type="AA_LAB_BOOKING")
        result = _lab_bkg_dto(b, lab)
        receipts.finish(db, receipt, result)
        db.commit()
        return result


def list_lab_bookings(user, lab_id=None, date=None, status=None, page=1, page_size=50, *, booking_id=None):
    from app.models import AaLabBooking
    with session() as db:
        q = db.query(AaLabBooking).filter(AaLabBooking.tenant_id == _tid(), AaLabBooking.is_deleted.is_(False))
        if lab_id:
            q = q.filter(AaLabBooking.lab_id == int(lab_id))
        if date:
            q = q.filter(AaLabBooking.booking_date == date)
        if status:
            q = q.filter(AaLabBooking.status == status)
        if booking_id is not None:
            q = q.filter(AaLabBooking.id == int(booking_id))
        total = q.count()
        rows = q.order_by(AaLabBooking.id.desc()).offset((max(1, page) - 1) * page_size).limit(page_size).all()
        from app.models import AaLabResource
        labs = {lab.id: lab for lab in db.scalars(select(AaLabResource).where(
            AaLabResource.tenant_id == _tid(), AaLabResource.is_deleted.is_(False),
            AaLabResource.id.in_({b.lab_id for b in rows}),
        )).all()}
        return [_lab_bkg_dto(b, labs.get(b.lab_id)) for b in rows], total


def review_lab_booking(user, booking_id, action, reason="", *, identity=None, command_key=None):
    """审核实训室预约：APPROVE(再查冲突)/REJECT(原因≥5字)，与 review_booking 同一算法。"""
    from app.models import AaLabBooking
    from . import academic_affairs_grade_command_receipt as receipts
    with session() as db:
        receipt, cached = receipts.begin(db, user, "RESOURCE_LAB_REVIEW", command_key, {"bookingId": str(booking_id), "action": action, "reason": reason, "identity": identity.model_dump() if identity is not None else None})
        if cached is not None:
            return cached
        resource_id = db.scalar(select(AaLabBooking.lab_id).where(
            AaLabBooking.id == booking_id, AaLabBooking.tenant_id == _tid(),
            AaLabBooking.is_deleted.is_(False),
        ))
        if resource_id is None:
            raise not_found("预约不存在")
        from . import academic_affairs_lab_room_service as lab_rooms
        lab, room = lab_rooms.lock_room(db, resource_id) if action == "APPROVE" else (None, None)
        if action == "APPROVE" and (getattr(identity, "expectedLabVersion", None) != int(lab.version or 0)
                or getattr(identity, "expectedClassroomId", None) != lab.classroom_id):
            raise AppException("DATA_CONFLICT", "实训室版本或关联场地已变化，请重新确认", http_status=409)
        b = db.query(AaLabBooking).filter(AaLabBooking.id == booking_id,
                                          AaLabBooking.tenant_id == _tid(),
                                          AaLabBooking.is_deleted.is_(False)).with_for_update().populate_existing().first()
        if not b:
            raise not_found("预约不存在")
        if b.status != "PENDING":
            raise AppException("DATA_CONFLICT", "该预约已处理", http_status=409)
        if b.lab_id != resource_id:
            raise AppException("DATA_CONFLICT", "预约资源已变化，请重新核对", http_status=409)
        if action == "APPROVE":
            if lab.status != "AVAILABLE":
                raise AppException("DATA_CONFLICT", "实训室当前不可用，请重新核对", http_status=409)
            _require_no_open_repair(db, "LAB", b.lab_id)
            if room.status != "AVAILABLE" or not room.allow_borrow:
                raise AppException("DATA_CONFLICT", "关联场地不可用或未开放借用", http_status=409)
            _require_no_open_repair(db, "CLASSROOM", room.id)
            lab_rooms.require_no_lab_booking(db, room.id, b.booking_date, b.slot_no, exclude_id=b.id)
            from app.models import AaClassroomBooking
            other = db.scalar(select(AaClassroomBooking.id).where(
                AaClassroomBooking.tenant_id == _tid(), AaClassroomBooking.is_deleted.is_(False),
                AaClassroomBooking.classroom_id == room.id, AaClassroomBooking.status == "APPROVED",
                AaClassroomBooking.booking_date == b.booking_date, AaClassroomBooking.slot_no == b.slot_no,
            ).limit(1).with_for_update(read=True))
            if other is not None:
                raise AppException("DATA_CONFLICT", "关联场地该时段已有教室借用", http_status=409)
            from .academic_affairs_schedule_resource_guard import require_booking_slot_free
            require_booking_slot_free(room.id, b.booking_date, b.slot_no)
            conflict = db.query(AaLabBooking).filter(AaLabBooking.tenant_id == _tid(),
                                                      AaLabBooking.lab_id == b.lab_id,
                                                      AaLabBooking.booking_date == b.booking_date,
                                                      AaLabBooking.slot_no == b.slot_no,
                                                      AaLabBooking.status == "APPROVED",
                                                      AaLabBooking.id != b.id,
                                                      AaLabBooking.is_deleted.is_(False)).with_for_update().populate_existing().first()
            if conflict:
                raise AppException("DATA_CONFLICT", "该时段已有通过的预约，冲突", http_status=409)
            b.classroom_id = room.id
            b.status = "APPROVED"
        elif action == "REJECT":
            reason = (reason or "").strip()
            if len(reason) < 5:
                raise AppException("VALIDATION_ERROR", "驳回原因必填且不少于5字")
            b.status = "REJECTED"
            b.review_reason = reason
        else:
            raise AppException("VALIDATION_ERROR", "非法动作")
        _audit(db, b.id, "BOOKING_REVIEW", action, biz_type="AA_LAB_BOOKING")
        result = _lab_bkg_dto(b, lab)
        receipts.finish(db, receipt, result)
        db.commit()
        return result


# ─────────── 资源占用（教室+实训室已批准预约 + 当日课表占用，统一只读聚合视图，无新表） ───────────

def _schedule_occurrences_on_date(db, date_str, *, resource_kind=None):
    """Read formal schedule occurrences using the existing calendar authority.

    This is a read projection; approval may consume it only under the room mutex
    in an independent fresh Session, as coordinated by schedule_resource_guard.
    An unknown calendar/head is an error, not evidence of resource availability.
    """
    from datetime import date as date_type, datetime, time
    from sqlalchemy import or_
    from app.models import AaScheduleItem, AaScheduleScopeHead, AaTerm
    from . import academic_affairs_attendance_occurrence_consumer as occurrence
    from . import academic_affairs_schedule_truth_service as truth_service

    try:
        target = date_type.fromisoformat(str(date_str or "").strip())
    except ValueError as error:
        raise AppException("VALIDATION_ERROR", "日期格式须为 YYYY-MM-DD") from error
    if resource_kind not in (None, "", "CLASSROOM"):
        return []
    terms = db.scalars(select(AaTerm).where(
        AaTerm.tenant_id == _tid(), AaTerm.is_deleted.is_(False),
        or_(AaTerm.start_date.is_(None), AaTerm.start_date <= datetime.combine(target, time.max)),
        or_(AaTerm.end_date.is_(None), AaTerm.end_date >= datetime.combine(target, time.min)),
    ).order_by(AaTerm.id)).all()
    term_ids = [term.id for term in terms]
    if not term_ids:
        return []
    active_by_term = truth_service.active_batch_ids_by_term(db, term_ids)
    heads = db.scalars(select(AaScheduleScopeHead).where(
        AaScheduleScopeHead.tenant_id == _tid(), AaScheduleScopeHead.term_id.in_(term_ids),
        AaScheduleScopeHead.active_batch_id.is_not(None), AaScheduleScopeHead.is_deleted.is_(False),
    )).all()
    for head in heads:
        if int(head.active_batch_id) not in active_by_term.get(int(head.term_id), []):
            raise AppException("DATA_CONFLICT", "课表正式版本指向异常，无法核对资源占用",
                               details={"scopeHeadId": str(head.id), "termId": str(head.term_id)}, http_status=409)
    no_class = {"该日期为校历调休停课日，不能创建普通课堂考勤",
                "该日期为节假日，不能创建普通课堂考勤"}
    result = []
    for term in terms:
        batch_ids = active_by_term.get(int(term.id), [])
        if not batch_ids:
            continue
        try:
            logical_date, calendar_source, event_id = occurrence._calendar_logical_date(db, term, target, lock=False)
            week_no, weekday = occurrence._week_and_weekday(term, logical_date)
        except AppException as error:
            if error.message in no_class:
                continue
            raise AppException("DATA_CONFLICT", "校历事实无法确定资源占用，请先核对正式校历",
                               details={"termId": str(term.id), "reason": error.message}, http_status=409) from error
        rows = db.scalars(select(AaScheduleItem).where(
            AaScheduleItem.tenant_id == _tid(), AaScheduleItem.is_deleted.is_(False),
            AaScheduleItem.batch_id.in_(batch_ids), AaScheduleItem.status == "EFFECTIVE",
            AaScheduleItem.weekday == weekday, AaScheduleItem.start_week <= week_no,
            AaScheduleItem.end_week >= week_no,
        ).order_by(AaScheduleItem.id)).all()
        for item in rows:
            if occurrence._parity_allows(item.week_parity, week_no):
                result.append((item, {
                    "scheduleItemId": str(item.id), "batchId": str(item.batch_id), "termId": str(term.id),
                    "classId": str(item.class_id) if item.class_id is not None else None,
                    "taskId": str(item.task_id) if item.task_id is not None else None,
                    "logicalDate": logical_date.isoformat(), "calendarSource": calendar_source,
                    "calendarEventId": str(event_id) if event_id else None, "weekNo": week_no, "weekday": weekday,
                }))
    return result


def _schedule_items_on_date(db, date_str, *, resource_kind=None, active_only=False):
    # Keep the existing call shape; drafts and superseded versions never become
    # formal occupancy, including for the formerly unrestricted conflict reader.
    return [item for item, _facts in _schedule_occurrences_on_date(db, date_str, resource_kind=resource_kind)]


def get_resource_occupancy(user, date, resource_kind=None):
    """Project physical occupancy using explicit catalog bindings and frozen approvals."""
    from app.models import AaClassroomBooking, AaLabBooking, AaLabResource
    date = (date or "").strip()
    if not date or resource_kind not in (None, "", "CLASSROOM", "LAB"):
        raise AppException("VALIDATION_ERROR", "请选择有效日期与资源类型")
    items = []
    with session() as db:
        occurrences = _schedule_occurrences_on_date(db, date)
        labs = db.scalars(select(AaLabResource).where(
            AaLabResource.tenant_id == _tid(), AaLabResource.is_deleted.is_(False),
        ).order_by(AaLabResource.id)).all()
        labs_by_room = {}
        for lab in labs:
            if lab.classroom_id is not None:
                labs_by_room.setdefault(int(lab.classroom_id), []).append(lab)
        unmapped_labs = sum(1 for lab in labs if lab.classroom_id is None)
        unmapped_bookings = 0
        for model, kind in ((AaClassroomBooking, "CLASSROOM"), (AaLabBooking, "LAB")):
            bookings = db.scalars(select(model).where(
                model.tenant_id == _tid(), model.booking_date == date,
                model.status == "APPROVED", model.is_deleted.is_(False),
            ).order_by(model.id)).all()
            for booking in bookings:
                room_id = booking.classroom_id
                if kind == "LAB" and room_id is None:
                    unmapped_bookings += 1
                source_id = booking.lab_id if kind == "LAB" else room_id
                label = booking.lab_text if kind == "LAB" else booking.classroom_text
                row = {"resourceKind": kind, "resourceId": str(source_id),
                       "classroomId": str(room_id) if room_id is not None else None,
                       "resourceLabel": label, "slotNo": booking.slot_no, "source": "BOOKING",
                       "bookingResourceKind": kind, "bookingId": str(booking.id),
                       "occupant": booking.applicant_name, "purpose": booking.purpose or ""}
                if resource_kind in (None, "", kind):
                    items.append(row)
                elif resource_kind == "CLASSROOM" and room_id is not None:
                    items.append({**row, "resourceKind": "CLASSROOM", "resourceId": str(room_id)})
                elif resource_kind == "LAB" and room_id is not None:
                    for lab in labs_by_room.get(int(room_id), []):
                        items.append({**row, "resourceKind": "LAB", "resourceId": str(lab.id),
                                      "resourceLabel": lab.lab_name})
        for item, facts in occurrences:
            row = {"resourceKind": "CLASSROOM", "resourceId": str(item.classroom_id) if item.classroom_id is not None else "",
                   "classroomId": str(item.classroom_id) if item.classroom_id is not None else None,
                   "resourceLabel": item.classroom_text or "", "slotNo": item.slot_no,
                   "source": "SCHEDULE", **facts, "occupant": item.teacher_name or "",
                   "purpose": item.course_name or item.class_name or ""}
            if resource_kind != "LAB":
                items.append(row)
            elif item.classroom_id is not None:
                for lab in labs_by_room.get(int(item.classroom_id), []):
                    items.append({**row, "resourceKind": "LAB", "resourceId": str(lab.id),
                                  "resourceLabel": lab.lab_name})
        unmapped_schedule = sum(1 for item, _facts in occurrences if item.classroom_id is None)
    items.sort(key=lambda row: (row["slotNo"], row["resourceLabel"] or ""))
    return {"date": date, "items": items, "total": len(items),
            "coverage": {"classroomSchedule": "FORMAL_SCOPE_HEAD_CALENDAR", "labSchedule": "EXPLICIT_ROOM_BINDING",
                         "unmappedScheduleItems": unmapped_schedule, "unmappedLabs": unmapped_labs,
                         "unmappedLabBookings": unmapped_bookings}}


# ─────────── 资源冲突（预约 vs 已发布课表跨源冲突台账；区别于排课批次内冲突检测，无新表） ───────────

def list_resource_conflicts(user, date_from, date_to=None):
    """资源冲突台账：在指定日期范围内，若教室已批准预约与当日正式课表在同一时段
    命中同一稳定 classroom_id，判定为一条跨源冲突记录（只读计算，不落表）。与排课模块批次内冲突检测
    （_detect_conflict，只查同批次课表内部）互补——这里查"预约 vs 已发布课表"，是前者覆盖不到的盲区。
    日期范围最多 31 天（工程防护，非业务限制）。"""
    from datetime import date as _date, timedelta as _td
    from app.models import AaClassroomBooking, AaLabBooking, AaLabResource
    date_from = (date_from or "").strip()
    if not date_from:
        raise AppException("VALIDATION_ERROR", "dateFrom 必填（YYYY-MM-DD）")
    try:
        y, m, d = [int(x) for x in date_from.split("-")]
        d0 = _date(y, m, d)
    except (ValueError, AttributeError):
        raise AppException("VALIDATION_ERROR", "dateFrom 格式须为 YYYY-MM-DD")
    if date_to:
        try:
            y2, m2, d2 = [int(x) for x in date_to.split("-")]
            d1 = _date(y2, m2, d2)
        except (ValueError, AttributeError):
            raise AppException("VALIDATION_ERROR", "dateTo 格式须为 YYYY-MM-DD")
    else:
        d1 = d0
    if d1 < d0:
        raise AppException("VALIDATION_ERROR", "dateTo 不能早于 dateFrom")
    if (d1 - d0).days > 31:
        raise AppException("VALIDATION_ERROR", "查询范围不超过31天")
    conflicts = []
    unmapped = 0
    unmapped_bookings = 0
    with session() as db:
        unmapped_labs = db.query(AaLabResource).filter(
            AaLabResource.tenant_id == _tid(), AaLabResource.is_deleted.is_(False),
            AaLabResource.classroom_id.is_(None),
        ).count()
        cur = d0
        while cur <= d1:
            ds = cur.isoformat()
            sched_by_room = {}
            for it, facts in _schedule_occurrences_on_date(db, ds):
                if it.classroom_id is None:
                    unmapped += 1
                    continue
                sched_by_room.setdefault((int(it.classroom_id), it.slot_no), []).append((it, facts))
            for model, kind in ((AaClassroomBooking, "CLASSROOM"), (AaLabBooking, "LAB")):
                bookings = db.scalars(select(model).where(
                    model.tenant_id == _tid(), model.booking_date == ds,
                    model.status == "APPROVED", model.is_deleted.is_(False),
                ).order_by(model.id)).all()
                for booking in bookings:
                    if booking.classroom_id is None:
                        unmapped_bookings += 1
                        continue
                    for item, facts in sched_by_room.get((int(booking.classroom_id), booking.slot_no), []):
                        conflicts.append({
                            "date": ds, "resourceKind": kind,
                            "resourceId": str(booking.lab_id if kind == "LAB" else booking.classroom_id),
                            "classroomId": str(booking.classroom_id),
                            "resourceLabel": booking.lab_text if kind == "LAB" else booking.classroom_text, **facts,
                            "slotNo": booking.slot_no, "bookingId": str(booking.id), "applicantName": booking.applicant_name,
                            "purpose": booking.purpose or "", "scheduleCourseName": item.course_name or "",
                            "scheduleClassName": item.class_name or "", "scheduleTeacherName": item.teacher_name or "",
                        })
            cur += _td(days=1)
    return {"dateFrom": date_from, "dateTo": d1.isoformat(), "items": conflicts, "total": len(conflicts),
            "coverage": {"classroomSchedule": "FORMAL_SCOPE_HEAD_CALENDAR",
                         "labSchedule": "EXPLICIT_ROOM_BINDING", "unmappedScheduleItems": unmapped,
                         "unmappedLabs": unmapped_labs, "unmappedLabBookings": unmapped_bookings}}


# ─────────── 资源维修（教室/实训室/设备共用工单台账；报修→维修中→完成，联动资源状态） ───────────

def _repair_row(r) -> dict:
    return {
        "repairId": str(r.id), "resourceKind": r.resource_kind, "resourceId": str(r.resource_id),
        "resourceLabel": r.resource_label or "", "faultDesc": r.fault_desc,
        "reporterName": r.reporter_name or "", "repairNote": r.repair_note or "",
        "status": r.status, "statusLabel": REPAIR_STATUS_LABEL.get(r.status, r.status),
        "createdAt": _iso(r.created_at), "resolvedAt": _iso(r.resolved_at) if r.resolved_at else None,
    }


def _resource_obj_and_label(db, kind, rid, *, lock=False):
    from app.models import AaClassroom, AaEquipment, AaLabResource
    model = {"CLASSROOM": AaClassroom, "LAB": AaLabResource, "EQUIPMENT": AaEquipment}.get(kind)
    if model is None:
        return None, None
    query = select(model).where(model.id == int(rid), model.tenant_id == _tid())
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    obj = db.scalar(query)
    if kind == "CLASSROOM":
        return obj, (f"{obj.building_name}{obj.room_code}" if obj else None)
    if kind == "LAB":
        return obj, (obj.lab_name if obj else None)
    if kind == "EQUIPMENT":
        return obj, (obj.equipment_name if obj else None)
    return None, None


def report_repair(user, body):
    """登记故障报修：教室/实训室/设备均可，任一在职员工均可报修（比照教室预约申请侧口径，端点挂
    require_staff）。自动把资源状态联动置为 MAINTENANCE——简化自真实高职院校"报告→组织维修"核心链
    （外部证据：广州科技职业技术大学/湖南城建职业技术学院设备维修管理办法，见续卡§5）。"""
    kind = (getattr(body, "resourceKind", None) or "").upper()
    if kind not in REPAIR_RESOURCE_KINDS:
        raise AppException("VALIDATION_ERROR", f"资源类型非法（合法值：{'/'.join(sorted(REPAIR_RESOURCE_KINDS))}）")
    rid = getattr(body, "resourceId", None)
    fault = (getattr(body, "faultDesc", None) or "").strip()
    if not rid or not fault:
        raise AppException("VALIDATION_ERROR", "资源ID与故障描述均必填")
    with session() as db:
        from app.models import AaResourceRepair
        obj, label = _resource_obj_and_label(db, kind, rid, lock=True)
        if not obj or getattr(obj, "is_deleted", False) or obj.tenant_id != _tid():
            raise not_found("资源不存在")
        name, _r, uid = _op()
        rec = AaResourceRepair(tenant_id=_tid(), resource_kind=kind, resource_id=int(rid),
                               resource_label=label, fault_desc=fault, reporter_key=uid or name,
                               reporter_name=name, status="REPORTED")
        db.add(rec); db.flush()
        if getattr(obj, "status", None) != "MAINTENANCE":
            obj.status = "MAINTENANCE"
            obj.version += 1
        _audit(db, rec.id, "REPAIR_REPORT", f"{label}：{fault[:50]}", biz_type="AA_RESOURCE_REPAIR")
        db.commit()
        db.refresh(rec)
        return _repair_row(rec)


def list_repairs(user, resource_kind=None, status=None, page=1, page_size=50):
    from app.models import AaResourceRepair
    with session() as db:
        q = db.query(AaResourceRepair).filter(AaResourceRepair.tenant_id == _tid(),
                                              AaResourceRepair.is_deleted.is_(False))
        if resource_kind:
            q = q.filter(AaResourceRepair.resource_kind == resource_kind)
        if status:
            q = q.filter(AaResourceRepair.status == status)
        rows = q.order_by(AaResourceRepair.id.desc()).all()
        total = len(rows)
        return [_repair_row(r) for r in rows[(page - 1) * page_size: page * page_size]], total


def _lock_repair_resource(db, repair_id):
    """报修/完工与预约批准统一 resource→request 锁序。"""
    from app.models import AaResourceRepair
    identity = db.execute(select(AaResourceRepair.resource_kind, AaResourceRepair.resource_id).where(
        AaResourceRepair.id == repair_id, AaResourceRepair.tenant_id == _tid(),
        AaResourceRepair.is_deleted.is_(False),
    )).first()
    if not identity:
        raise not_found("维修工单不存在")
    kind, resource_id = identity
    obj, _label = _resource_obj_and_label(db, kind, resource_id, lock=True)
    repair = db.query(AaResourceRepair).filter(
        AaResourceRepair.id == repair_id, AaResourceRepair.tenant_id == _tid(),
        AaResourceRepair.is_deleted.is_(False),
    ).with_for_update().populate_existing().first()
    if not repair:
        raise not_found("维修工单不存在")
    if (repair.resource_kind, repair.resource_id) != (kind, resource_id):
        raise AppException("DATA_CONFLICT", "维修工单关联资源已变化", http_status=409)
    return repair, obj


def start_repair(user, repair_id):
    with session() as db:
        r, _obj = _lock_repair_resource(db, repair_id)
        if r.status != "REPORTED":
            raise AppException("DATA_CONFLICT", "仅「已报修」状态可开始维修", http_status=409)
        r.status = "IN_REPAIR"
        r.version += 1
        _audit(db, r.id, "REPAIR_START", r.resource_label or "", biz_type="AA_RESOURCE_REPAIR")
        db.commit()
        return _repair_row(r)


def complete_repair(user, repair_id, repair_note=""):
    with session() as db:
        from app.models import AaResourceRepair
        r, obj = _lock_repair_resource(db, repair_id)
        if r.status not in ("REPORTED", "IN_REPAIR"):
            raise AppException("DATA_CONFLICT", "该工单已完成或已取消", http_status=409)
        r.status = "DONE"
        r.repair_note = (repair_note or "").strip() or None
        r.resolved_at = datetime.utcnow()
        r.version += 1
        if obj and not getattr(obj, "is_deleted", False):
            other_open = db.query(AaResourceRepair).filter(
                AaResourceRepair.tenant_id == _tid(), AaResourceRepair.resource_kind == r.resource_kind,
                AaResourceRepair.resource_id == r.resource_id, AaResourceRepair.id != r.id,
                AaResourceRepair.status.in_(["REPORTED", "IN_REPAIR"]),
                AaResourceRepair.is_deleted.is_(False)).with_for_update().populate_existing().first()
            if not other_open and getattr(obj, "status", None) == "MAINTENANCE":
                obj.status = "AVAILABLE" if r.resource_kind in ("CLASSROOM", "LAB") else "IN_USE"
                obj.version += 1
        _audit(db, r.id, "REPAIR_DONE", r.resource_label or "", biz_type="AA_RESOURCE_REPAIR")
        db.commit()
        return _repair_row(r)


def cancel_repair(user, repair_id, reason=""):
    with session() as db:
        r, _obj = _lock_repair_resource(db, repair_id)
        if r.status in ("DONE", "CANCELLED"):
            raise AppException("DATA_CONFLICT", "该工单已完成或已取消", http_status=409)
        r.status = "CANCELLED"
        r.repair_note = (reason or "").strip() or None
        r.version += 1
        _audit(db, r.id, "REPAIR_CANCEL", reason or "", biz_type="AA_RESOURCE_REPAIR")
        db.commit()
        return _repair_row(r)


# ─────────── 资源统计（教室/实训室/设备数量与状态分布 + 预约审批率 + 维修工单，只读聚合无新表） ───────────

def _pct(num, den):
    if not den:
        return None
    return round(num * 100.0 / den, 1)


def get_resource_stats(user):
    from app.models import (AaClassroom, AaClassroomBooking, AaEquipment, AaLabBooking,
                            AaLabResource, AaResourceRepair)
    with session() as db:
        def _count_by_status(model):
            rows = db.query(model.status, func.count()).filter(
                model.tenant_id == _tid(), model.is_deleted.is_(False)).group_by(model.status).all()
            return {s: n for s, n in rows}

        classroom_by_status = _count_by_status(AaClassroom)
        lab_by_status = _count_by_status(AaLabResource)
        equipment_by_status = _count_by_status(AaEquipment)
        classroom_booking = _count_by_status(AaClassroomBooking)
        lab_booking = _count_by_status(AaLabBooking)
        repair_by_status = _count_by_status(AaResourceRepair)

        classroom_total = sum(classroom_by_status.values())
        lab_total = sum(lab_by_status.values())
        equipment_total = sum(equipment_by_status.values())

        def _approval_rate(booking_status):
            decided = sum(v for k, v in booking_status.items() if k in ("APPROVED", "REJECTED"))
            return _pct(booking_status.get("APPROVED", 0), decided)

        return {
            "classroom": {"total": classroom_total, "byStatus": classroom_by_status,
                         "availableRate": _pct(classroom_by_status.get("AVAILABLE", 0), classroom_total)},
            "lab": {"total": lab_total, "byStatus": lab_by_status,
                   "availableRate": _pct(lab_by_status.get("AVAILABLE", 0), lab_total)},
            "equipment": {"total": equipment_total, "byStatus": equipment_by_status,
                         "inUseRate": _pct(equipment_by_status.get("IN_USE", 0), equipment_total)},
            "classroomBooking": {"total": sum(classroom_booking.values()), "byStatus": classroom_booking,
                                "approvalRate": _approval_rate(classroom_booking)},
            "labBooking": {"total": sum(lab_booking.values()), "byStatus": lab_booking,
                          "approvalRate": _approval_rate(lab_booking)},
            "repair": {"total": sum(repair_by_status.values()), "byStatus": repair_by_status,
                      "openCount": repair_by_status.get("REPORTED", 0) + repair_by_status.get("IN_REPAIR", 0)},
        }
