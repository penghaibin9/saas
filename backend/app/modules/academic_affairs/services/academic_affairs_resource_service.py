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


def _audit(db, biz_id, action, detail=""):
    from app.models import AffairsAuditTrail
    n, r, uid = _op()
    db.add(AffairsAuditTrail(tenant_id=_tid(), biz_type="AA_CLASSROOM",
                             biz_id=int(biz_id) if biz_id else None, action=action,
                             operator=n or uid, role_name=r, detail=detail,
                             occurred_at=datetime.utcnow()))


def _row(c) -> dict:
    return {
        "classroomId": str(c.id), "buildingCode": c.building_code, "buildingName": c.building_name,
        "roomCode": c.room_code, "roomName": c.room_name or f"{c.building_name}{c.room_code}",
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
    c = db.get(AaClassroom, int(classroom_id)) if classroom_id else None
    if not c or c.is_deleted or c.tenant_id != _tid():
        raise not_found("教室不存在")
    return c


# ═══════════ 查询 ═══════════

def list_classrooms(user, keyword=None, building_code=None, room_type=None, status=None,
                    page=1, page_size=20):
    from app.models import AaClassroom
    with session() as db:
        conds = [AaClassroom.tenant_id == _tid(), AaClassroom.is_deleted.is_(False)]
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
                          .order_by(AaClassroom.building_code, AaClassroom.room_code)
                          .offset(offset).limit(page_size)).all()
        return [_row(c) for c in rows], total


def get_classroom(classroom_id, user) -> dict:
    with session() as db:
        return _row(_load(db, classroom_id))


def list_options(user, keyword=None):
    """排课 UI 供数：仅返回可用(AVAILABLE)教室的精简项（含 capacity 供非阻断容量 warning）。"""
    from app.models import AaClassroom
    with session() as db:
        conds = [AaClassroom.tenant_id == _tid(), AaClassroom.is_deleted.is_(False),
                 AaClassroom.status == "AVAILABLE"]
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
        db.commit()
        db.refresh(c)
        return _row(c)


def update_classroom(classroom_id, body, user) -> dict:
    with session() as db:
        from app.models import AaClassroom
        c = _load(db, classroom_id)
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


def book_classroom(user, body):
    """申请教室预约。同教室同日同节次已 APPROVED → 409（占用冲突）。"""
    from app.models import AaClassroomBooking, AaClassroom
    with session() as db:
        cid = int(body.classroomId)
        c = db.query(AaClassroom).filter(AaClassroom.id == cid, AaClassroom.tenant_id == _tid(),
                                         AaClassroom.is_deleted.is_(False)).first()
        if not c:
            raise not_found("教室不存在")
        if c.status != "AVAILABLE":
            raise AppException("DATA_CONFLICT", "该教室不可用（停用/维修中）", http_status=409)
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
        db.commit()
        return _bkg_dto(b)


def list_bookings(user, classroom_id=None, date=None, status=None, page=1, page_size=50):
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
        rows = q.order_by(AaClassroomBooking.id.desc()).all()
        total = len(rows)
        return [_bkg_dto(b) for b in rows[(page - 1) * page_size: page * page_size]], total


def review_booking(user, booking_id, action, reason=""):
    """审核预约：APPROVE(再查冲突)/REJECT(原因≥5字)。"""
    from app.models import AaClassroomBooking
    with session() as db:
        b = db.query(AaClassroomBooking).filter(AaClassroomBooking.id == booking_id,
                                                AaClassroomBooking.tenant_id == _tid()).first()
        if not b:
            raise not_found("预约不存在")
        if b.status != "PENDING":
            raise AppException("DATA_CONFLICT", "该预约已处理", http_status=409)
        if action == "APPROVE":
            conflict = db.query(AaClassroomBooking).filter(AaClassroomBooking.tenant_id == _tid(),
                                                           AaClassroomBooking.classroom_id == b.classroom_id,
                                                           AaClassroomBooking.booking_date == b.booking_date,
                                                           AaClassroomBooking.slot_no == b.slot_no,
                                                           AaClassroomBooking.status == "APPROVED",
                                                           AaClassroomBooking.id != b.id,
                                                           AaClassroomBooking.is_deleted.is_(False)).first()
            if conflict:
                raise AppException("DATA_CONFLICT", "该时段已有通过的预约，冲突", http_status=409)
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
        db.commit()
        return _bkg_dto(b)
