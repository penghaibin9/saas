"""D4 canonical DormStay history and formal checkout workflow.

DormBed remains the current occupancy pointer.  Every check-in, transfer and
checkout must update that pointer and the immutable stay timeline in one
transaction.  Checkout is deliberately two-step: request first, manager
confirmation second.
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import and_, func, select

from app.core.exceptions import AppException, not_found
from app.core.optimistic_lock import atomic_claim_version
from app.services.db_service import _iso, _tid, session

ACTIVE_TRANSFER_STATUSES = ("COUNSELOR_REVIEW", "DORM_MANAGER_REVIEW")
CHECKOUT_REQUEST_TYPES = (
    "GRADUATION", "LEAVE_OF_ABSENCE", "WITHDRAWAL", "DAY_STUDENT", "SPECIAL",
)
CHECKOUT_STATUSES = ("PENDING_CONFIRMATION", "BLOCKED", "CONFIRMED", "CANCELLED")


def _actor_id(db, user) -> int:
    from app.models import User

    raw = str((user or {}).get("userId") or "")
    for prefix in ("db-", "u_"):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
    if raw.isdigit():
        row = db.get(User, int(raw))
        if row and row.tenant_id == _tid() and not row.is_deleted:
            return int(row.id)
    login = str(
        (user or {}).get("loginName") or (user or {}).get("username")
        or (user or {}).get("sub") or ""
    ).strip()
    if login:
        row = db.scalars(select(User).where(
            User.tenant_id == _tid(), User.login_name == login,
            User.status == "ACTIVE", User.is_deleted.is_(False),
        )).first()
        if row:
            return int(row.id)
    raise AppException("NO_PERMISSION", "当前账号未绑定可核验的操作人ID")


def _active_stays(db, *, student_id: int | None = None, bed_id: int | None = None,
                  for_update: bool = False):
    from app.models import DormStay

    conds = [
        DormStay.tenant_id == _tid(), DormStay.status == "ACTIVE",
        DormStay.is_deleted.is_(False),
    ]
    if student_id is not None:
        conds.append(DormStay.student_id == int(student_id))
    if bed_id is not None:
        conds.append(DormStay.bed_id == int(bed_id))
    query = select(DormStay).where(*conds).order_by(DormStay.id)
    if for_update:
        query = query.with_for_update()
    return list(db.scalars(query).all())


def _reserved_stays(db, *, student_id: int, for_update: bool = False):
    from app.models import DormStay

    query = select(DormStay).where(
        DormStay.tenant_id == _tid(), DormStay.student_id == int(student_id),
        DormStay.status == "RESERVED", DormStay.is_deleted.is_(False),
    ).order_by(DormStay.id)
    if for_update:
        query = query.with_for_update()
    return list(db.scalars(query).all())


def require_active_stay(db, *, student_id: int, bed_id: int, for_update: bool = True):
    stays = _active_stays(
        db, student_id=int(student_id), bed_id=int(bed_id), for_update=for_update,
    )
    student_stays = _active_stays(db, student_id=int(student_id), for_update=for_update)
    bed_stays = _active_stays(db, bed_id=int(bed_id), for_update=for_update)
    if len(stays) != 1 or len(student_stays) != 1 or len(bed_stays) != 1:
        raise AppException(
            "DATA_INCONSISTENT", "当前床位与 DormStay 历史不一致，请先完成一致性核对",
        )
    return stays[0]


def activate_checkin(db, *, bed, student, user, stay_type: str = "CURRENT_OCCUPANCY",
                     source_type: str = "MANUAL", source_biz_id: str | None = None):
    """Promote an allocation reservation or create a manual ACTIVE stay."""
    from app.models import DormAllocationItem, DormStay

    if _active_stays(db, student_id=int(student.id), for_update=True):
        raise AppException("DATA_CONFLICT", "该学生已有生效住宿，不能再次入住")
    if _active_stays(db, bed_id=int(bed.id), for_update=True):
        raise AppException("DATA_CONFLICT", "该床位已有生效住宿，不能重复入住")
    reservations = _reserved_stays(db, student_id=int(student.id), for_update=True)
    matching = [row for row in reservations if int(row.bed_id) == int(bed.id)]
    if bed.status == "LOCKED":
        if len(matching) != 1:
            raise AppException("DATA_CONFLICT", "锁定床位不属于该学生的已发布分配计划")
        stay = matching[0]
    elif bed.status == "VACANT" and bed.student_id is None:
        if reservations:
            raise AppException("DATA_CONFLICT", "该学生已有预留床位，请按分配计划办理入住")
        stay = DormStay(
            tenant_id=_tid(), student_id=int(student.id), bed_id=int(bed.id),
            building_id=int(bed.building_id), room_id=int(bed.room_id),
            stay_type=stay_type, source_type=source_type,
            source_biz_id=source_biz_id or f"manual-checkin:{uuid4().hex}",
            status="ACTIVE",
        )
        db.add(stay)
    else:
        raise AppException("DATA_CONFLICT", "该床位已被占用或锁定")

    now = datetime.utcnow()
    stay.status = "ACTIVE"
    stay.checkin_at = now
    stay.checkin_operator_id = _actor_id(db, user)
    stay.version = int(stay.version or 0) + 1
    bed.student_id = int(student.id)
    bed.status = "OCCUPIED"
    bed.occupied_at = now
    bed.version = int(bed.version or 0) + 1
    if stay.source_type == "ALLOCATION" and str(stay.source_biz_id).isdigit():
        item = db.get(DormAllocationItem, int(stay.source_biz_id))
        if item and item.tenant_id == _tid() and not item.is_deleted:
            item.status = "CONFIRMED"
            item.confirmed_at = now
            item.version = int(item.version or 0) + 1
    db.flush()
    return stay


def execute_transfer(db, *, transfer, student, old_bed, target_bed, user):
    """Close the old ACTIVE stay and open the transfer stay atomically."""
    from app.models import DormStay

    old_stay = require_active_stay(
        db, student_id=int(student.id), bed_id=int(old_bed.id), for_update=True,
    )
    if _active_stays(db, bed_id=int(target_bed.id), for_update=True):
        raise AppException("DATA_CONFLICT", "目标床位已有生效住宿")
    now = datetime.utcnow()
    actor = _actor_id(db, user)
    old_stay.status = "ENDED"
    old_stay.checkout_at = now
    old_stay.checkout_operator_id = actor
    old_stay.version = int(old_stay.version or 0) + 1
    new_stay = DormStay(
        tenant_id=_tid(), student_id=int(student.id), bed_id=int(target_bed.id),
        building_id=int(target_bed.building_id), room_id=int(target_bed.room_id),
        stay_type="TRANSFER", source_type="TRANSFER", source_biz_id=str(transfer.id),
        checkin_at=now, status="ACTIVE", checkin_operator_id=actor,
    )
    db.add(new_stay)
    db.flush()
    return old_stay, new_stay


def _blockers(db, *, student_id: int, stay_id: int, bed_id: int,
              lock_authority: bool = False) -> list[dict]:
    from app.models import DormBed, DormStay, DormTransfer, StudentProfile

    lock = lambda q: q.with_for_update() if lock_authority else q
    student = db.scalars(lock(select(StudentProfile).where(
        StudentProfile.tenant_id == _tid(), StudentProfile.id == int(student_id),
        StudentProfile.is_deleted.is_(False),
    ))).first()
    stay = db.scalars(lock(select(DormStay).where(
        DormStay.tenant_id == _tid(), DormStay.id == int(stay_id),
        DormStay.is_deleted.is_(False),
    ))).first()
    bed = db.scalars(lock(select(DormBed).where(
        DormBed.tenant_id == _tid(), DormBed.id == int(bed_id),
        DormBed.is_deleted.is_(False),
    ))).first()
    out: list[dict] = []
    if not student:
        out.append({"code": "STUDENT_MISSING", "message": "学生档案已失效"})
    if not stay or stay.status != "ACTIVE" or int(stay.student_id) != int(student_id) \
            or int(stay.bed_id) != int(bed_id):
        out.append({"code": "STAY_CHANGED", "message": "当前住宿历史已变化"})
    if not bed or bed.status != "OCCUPIED" or int(bed.student_id or 0) != int(student_id):
        out.append({"code": "BED_CHANGED", "message": "当前床位占用已变化"})
    transfer = db.scalars(select(DormTransfer).where(
        DormTransfer.tenant_id == _tid(), DormTransfer.student_id == int(student_id),
        DormTransfer.status.in_(ACTIVE_TRANSFER_STATUSES),
        DormTransfer.is_deleted.is_(False),
    ).order_by(DormTransfer.id).limit(1)).first()
    if transfer:
        out.append({
            "code": "TRANSFER_IN_PROGRESS",
            "message": f"调宿申请 #{transfer.id} 正在审批，不能同时退宿",
        })
    return out


def _checkout_row(row, *, student=None, bed=None, room=None, building=None,
                  blockers: list[dict] | None = None) -> dict:
    live_blockers = list(row.blockers_json or []) if blockers is None else blockers
    pending = row.status in ("PENDING_CONFIRMATION", "BLOCKED")
    return {
        "requestId": str(row.id), "studentId": str(row.student_id),
        "studentName": student.real_name if student else "",
        "studentNo": student.student_no if student else "",
        "stayId": str(row.stay_id), "bedId": str(row.bed_id),
        "buildingId": str(row.building_id), "roomId": str(row.room_id),
        "bedLabel": " / ".join(x for x in (
            building.building_name if building else "",
            f"{room.room_no}室" if room else "",
            f"{bed.bed_no}床" if bed else "",
        ) if x),
        "requestType": row.request_type, "sourceType": row.source_type,
        "sourceBizId": row.source_biz_id or "", "reason": row.reason,
        "status": row.status, "blockers": live_blockers,
        "requestedAt": _iso(row.requested_at), "confirmedAt": _iso(row.confirmed_at),
        "version": int(row.version or 0),
        "allowedActions": (["CONFIRM", "CANCEL"] if pending else []),
    }


def create_checkout_request(*, bed_id: int, expected_bed_version, request_type: str,
                            reason: str, client_request_id: str, user,
                            source_type: str = "MANUAL", source_biz_id: str | None = None) -> dict:
    from app.models import (DormBed, DormBuilding, DormCheckoutRequest, DormRoom,
                            StudentProfile)
    from app.services import affairs_dorm_service as dorm

    request_type = str(request_type or "").upper()
    source_type = str(source_type or "MANUAL").upper()
    reason = str(reason or "").strip()
    client_request_id = str(client_request_id or "").strip()
    if request_type not in CHECKOUT_REQUEST_TYPES:
        raise AppException("VALIDATION_ERROR", "退宿类型非法")
    if source_type not in ("MANUAL", "GRADUATION_BATCH"):
        raise AppException("VALIDATION_ERROR", "退宿来源非法")
    if not 5 <= len(reason) <= 500:
        raise AppException("VALIDATION_ERROR", "退宿原因需5-500字")
    if not 8 <= len(client_request_id) <= 100:
        raise AppException("VALIDATION_ERROR", "clientRequestId 需8-100字")
    if source_type == "GRADUATION_BATCH" and not str(source_biz_id or "").strip():
        raise AppException("VALIDATION_ERROR", "毕业批量退宿必须提供稳定来源键")

    with session() as db:
        existing = db.scalars(select(DormCheckoutRequest).where(
            DormCheckoutRequest.tenant_id == _tid(),
            DormCheckoutRequest.client_request_id == client_request_id,
            DormCheckoutRequest.is_deleted.is_(False),
        )).first()
        if existing:
            same = (
                int(existing.bed_id) == int(bed_id)
                and existing.request_type == request_type
                and existing.reason == reason
                and existing.source_type == source_type
                and (existing.source_biz_id or "") == (str(source_biz_id or ""))
            )
            if not same:
                raise AppException("IDEMPOTENCY_CONFLICT", "clientRequestId 已用于另一退宿请求")
            return _checkout_row(existing)

        bed = db.scalars(select(DormBed).where(
            DormBed.tenant_id == _tid(), DormBed.id == int(bed_id),
            DormBed.is_deleted.is_(False),
        ).with_for_update()).first()
        if not bed:
            raise not_found("床位不存在")
        dorm._require_dorm_scope(db, int(bed.building_id), user)
        try:
            expected = int(expected_bed_version)
        except (TypeError, ValueError):
            raise AppException("VALIDATION_ERROR", "必须提供当前床位 version")
        if int(bed.version or 0) != expected:
            raise AppException("APPROVAL_VERSION_CONFLICT", "床位状态已变化，请刷新后重试")
        if bed.status != "OCCUPIED" or not bed.student_id:
            raise AppException("DATA_CONFLICT", "该床位当前无人入住")
        student = db.scalars(select(StudentProfile).where(
            StudentProfile.tenant_id == _tid(), StudentProfile.id == int(bed.student_id),
            StudentProfile.is_deleted.is_(False),
        ).with_for_update()).first()
        if not student:
            raise AppException("DATA_INCONSISTENT", "床位指向的学生不存在")
        stay = require_active_stay(
            db, student_id=int(student.id), bed_id=int(bed.id), for_update=True,
        )
        duplicate = db.scalars(select(DormCheckoutRequest).where(
            DormCheckoutRequest.tenant_id == _tid(),
            DormCheckoutRequest.stay_id == int(stay.id),
            DormCheckoutRequest.status.in_(("PENDING_CONFIRMATION", "BLOCKED")),
            DormCheckoutRequest.is_deleted.is_(False),
        ).with_for_update()).first()
        if duplicate:
            raise AppException("DATA_CONFLICT", "该住宿已有待确认退宿单，请勿重复发起")
        blockers = _blockers(
            db, student_id=int(student.id), stay_id=int(stay.id), bed_id=int(bed.id),
        )
        actor = _actor_id(db, user)
        row = DormCheckoutRequest(
            tenant_id=_tid(), student_id=int(student.id), stay_id=int(stay.id),
            bed_id=int(bed.id), building_id=int(bed.building_id), room_id=int(bed.room_id),
            request_type=request_type, source_type=source_type,
            source_biz_id=str(source_biz_id) if source_biz_id is not None else None,
            client_request_id=client_request_id, reason=reason,
            blockers_json=blockers,
            status="BLOCKED" if blockers else "PENDING_CONFIRMATION",
            requested_at=datetime.utcnow(), requested_by=actor,
        )
        db.add(row); db.flush()
        dorm._audit(
            db, "DORM_CHECKOUT", row.id, "REQUEST",
            f"student={student.id};stay={stay.id};blockers={len(blockers)}",
        )
        db.commit(); db.refresh(row)
        return _checkout_row(
            row, student=student, bed=bed,
            room=db.get(DormRoom, int(bed.room_id)),
            building=db.get(DormBuilding, int(bed.building_id)), blockers=blockers,
        )


def confirm_checkout(request_id: int, *, expected_version, user) -> dict:
    from app.models import (CsDormRecord, DormBed, DormBuilding, DormCheckoutRequest,
                            DormRoom, DormStay, StudentProfile, StudentStageEvent)
    from app.services import affairs_dorm_service as dorm

    blocked_message = None
    with session() as db:
        row = db.scalars(select(DormCheckoutRequest).where(
            DormCheckoutRequest.tenant_id == _tid(), DormCheckoutRequest.id == int(request_id),
            DormCheckoutRequest.is_deleted.is_(False),
        ).with_for_update()).first()
        if not row:
            raise not_found("退宿单不存在")
        dorm._require_dorm_scope(db, int(row.building_id), user)
        if row.status not in ("PENDING_CONFIRMATION", "BLOCKED"):
            raise AppException("APPROVAL_VERSION_CONFLICT", "该退宿单当前状态不可确认")
        atomic_claim_version(db, row, expected_version)
        blockers = _blockers(
            db, student_id=int(row.student_id), stay_id=int(row.stay_id),
            bed_id=int(row.bed_id), lock_authority=True,
        )
        if blockers:
            row.status = "BLOCKED"
            row.blockers_json = blockers
            row.version = int(row.version or 0) + 1
            dorm._audit(db, "DORM_CHECKOUT", row.id, "BLOCKED", blockers[0]["code"])
            db.commit()
            blocked_message = "；".join(item["message"] for item in blockers)
        else:
            actor = _actor_id(db, user)
            student = db.get(StudentProfile, int(row.student_id))
            stay = db.get(DormStay, int(row.stay_id))
            bed = db.get(DormBed, int(row.bed_id))
            now = datetime.utcnow()
            stay.status = "ENDED"
            stay.checkout_at = now
            stay.checkout_operator_id = actor
            stay.version = int(stay.version or 0) + 1
            if bed.cs_dorm_record_id:
                record = db.get(CsDormRecord, int(bed.cs_dorm_record_id))
                if record and record.tenant_id == _tid():
                    record.status = "OUT"
                    record.record_status = "INACTIVE"
                    record.version = int(record.version or 0) + 1
            bed.student_id = None
            bed.status = "VACANT"
            bed.occupied_at = None
            bed.cs_dorm_record_id = None
            bed.version = int(bed.version or 0) + 1
            row.status = "CONFIRMED"
            row.blockers_json = []
            row.confirmed_at = now
            row.confirmed_by = actor
            row.version = int(row.version or 0) + 1
            db.add(StudentStageEvent(
                tenant_id=_tid(), student_id=int(row.student_id), from_stage=None,
                to_stage="DORM_CHECKOUT_CONFIRMED", reason=row.reason,
                source_module="student-affairs",
            ))
            from app.services.message_event_outbox_service import emit_receiver_notice
            emit_receiver_notice(
                db, event_code="DORM.CHECKOUT.CONFIRMED",
                source_module="student-affairs", source_biz_type="DORM_CHECKOUT",
                source_biz_id=int(row.id), receiver_id=int(row.student_id),
                receiver_as="student", title="退宿已办理",
                content="住宿关系已结束，原床位已释放。",
                dedup_extra="DORM.CHECKOUT.CONFIRMED",
            )
            dorm._audit(
                db, "DORM_CHECKOUT", row.id, "CONFIRMED",
                f"student={row.student_id};stay={row.stay_id};bed={row.bed_id}",
            )
            room = db.get(DormRoom, int(row.room_id))
            building = db.get(DormBuilding, int(row.building_id))
            db.commit(); db.refresh(row)
            return _checkout_row(
                row, student=student, bed=bed, room=room, building=building, blockers=[],
            )
    if blocked_message:
        raise AppException("DATA_CONFLICT", "退宿存在阻断事项：" + blocked_message)
    raise AppException("DATA_CONFLICT", "退宿未完成")


def cancel_checkout(request_id: int, *, expected_version, reason: str, user) -> dict:
    from app.models import DormCheckoutRequest
    from app.services import affairs_dorm_service as dorm

    reason = str(reason or "").strip()
    if not 5 <= len(reason) <= 500:
        raise AppException("VALIDATION_ERROR", "取消原因需5-500字")
    with session() as db:
        row = db.scalars(select(DormCheckoutRequest).where(
            DormCheckoutRequest.tenant_id == _tid(), DormCheckoutRequest.id == int(request_id),
            DormCheckoutRequest.is_deleted.is_(False),
        ).with_for_update()).first()
        if not row:
            raise not_found("退宿单不存在")
        dorm._require_dorm_scope(db, int(row.building_id), user)
        if row.status not in ("PENDING_CONFIRMATION", "BLOCKED"):
            raise AppException("APPROVAL_VERSION_CONFLICT", "该退宿单当前状态不可取消")
        atomic_claim_version(db, row, expected_version)
        row.status = "CANCELLED"
        row.cancel_reason = reason
        row.cancelled_at = datetime.utcnow()
        row.cancelled_by = _actor_id(db, user)
        row.version = int(row.version or 0) + 1
        dorm._audit(db, "DORM_CHECKOUT", row.id, "CANCELLED", reason)
        db.commit(); db.refresh(row)
        return _checkout_row(row)


def _teacher_scope(db, user):
    from app.core.affairs_security import build_affairs_context
    return build_affairs_context(user, db)


def list_checkout_requests(user, *, status: str | None = None,
                           student_id: int | None = None, page: int = 1,
                           page_size: int = 50):
    from app.models import (DormBed, DormBuilding, DormCheckoutRequest, DormRoom,
                            StudentProfile)

    page, page_size = max(1, int(page)), max(1, min(int(page_size), 200))
    with session() as db:
        context = _teacher_scope(db, user)
        conds = [
            DormCheckoutRequest.tenant_id == _tid(),
            DormCheckoutRequest.is_deleted.is_(False),
        ]
        if status:
            if str(status).upper() not in CHECKOUT_STATUSES:
                return [], 0
            conds.append(DormCheckoutRequest.status == str(status).upper())
        if student_id:
            conds.append(DormCheckoutRequest.student_id == int(student_id))
        if context.scope_type == "DORM_BUILDING":
            allowed = list(context.dorm_building_ids)
            conds.append(DormCheckoutRequest.building_id.in_(allowed or [-1]))
        elif context.scope_type in ("CLASS", "COLLEGE"):
            allowed = context.allowed_class_ids(db)
            conds.append(StudentProfile.class_id.in_(list(allowed or {-1})))
        elif context.scope_type != "TENANT_ALL":
            return [], 0
        join_student = and_(
            StudentProfile.id == DormCheckoutRequest.student_id,
            StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
        )
        total = int(db.scalar(
            select(func.count()).select_from(DormCheckoutRequest)
            .join(StudentProfile, join_student).where(*conds)
        ) or 0)
        rows = db.execute(
            select(DormCheckoutRequest, StudentProfile, DormBed, DormRoom, DormBuilding)
            .join(StudentProfile, join_student)
            .outerjoin(DormBed, and_(
                DormBed.id == DormCheckoutRequest.bed_id,
                DormBed.tenant_id == _tid(), DormBed.is_deleted.is_(False),
            ))
            .outerjoin(DormRoom, and_(
                DormRoom.id == DormCheckoutRequest.room_id,
                DormRoom.tenant_id == _tid(), DormRoom.is_deleted.is_(False),
            ))
            .outerjoin(DormBuilding, and_(
                DormBuilding.id == DormCheckoutRequest.building_id,
                DormBuilding.tenant_id == _tid(), DormBuilding.is_deleted.is_(False),
            ))
            .where(*conds).order_by(DormCheckoutRequest.id.desc())
            .offset((page - 1) * page_size).limit(page_size)
        ).all()
        return [
            _checkout_row(row, student=student, bed=bed, room=room, building=building)
            for row, student, bed, room, building in rows
        ], total


def _stay_row(stay, *, student=None, bed=None, room=None, building=None) -> dict:
    return {
        "stayId": str(stay.id), "studentId": str(stay.student_id),
        "studentName": student.real_name if student else "",
        "studentNo": student.student_no if student else "",
        "bedId": str(stay.bed_id),
        "buildingId": str(stay.building_id), "roomId": str(stay.room_id),
        "building": building.building_name if building else "",
        "room": room.room_no if room else "", "bedNo": bed.bed_no if bed else "",
        "bedLabel": " / ".join(x for x in (
            building.building_name if building else "",
            f"{room.room_no}室" if room else "", f"{bed.bed_no}床" if bed else "",
        ) if x),
        "stayType": stay.stay_type, "sourceType": stay.source_type,
        "sourceBizId": stay.source_biz_id, "status": stay.status,
        "checkinAt": _iso(stay.checkin_at), "checkoutAt": _iso(stay.checkout_at),
        "version": int(stay.version or 0),
    }


def list_stays(user, *, student_id: int | None = None, status: str | None = None,
               page: int = 1, page_size: int = 50):
    from app.models import DormBed, DormBuilding, DormRoom, DormStay, StudentProfile

    page, page_size = max(1, int(page)), max(1, min(int(page_size), 200))
    with session() as db:
        context = _teacher_scope(db, user)
        conds = [DormStay.tenant_id == _tid(), DormStay.is_deleted.is_(False)]
        if student_id:
            conds.append(DormStay.student_id == int(student_id))
        if status:
            conds.append(DormStay.status == str(status).upper())
        if context.scope_type == "DORM_BUILDING":
            conds.append(DormStay.building_id.in_(list(context.dorm_building_ids) or [-1]))
        elif context.scope_type in ("CLASS", "COLLEGE"):
            allowed = context.allowed_class_ids(db)
            conds.append(StudentProfile.class_id.in_(list(allowed or {-1})))
        elif context.scope_type != "TENANT_ALL":
            return [], 0
        join_student = and_(
            StudentProfile.id == DormStay.student_id,
            StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
        )
        total = int(db.scalar(
            select(func.count()).select_from(DormStay)
            .join(StudentProfile, join_student).where(*conds)
        ) or 0)
        rows = db.execute(
            select(DormStay, StudentProfile, DormBed, DormRoom, DormBuilding)
            .join(StudentProfile, join_student)
            .outerjoin(DormBed, and_(
                DormBed.id == DormStay.bed_id, DormBed.tenant_id == _tid(),
                DormBed.is_deleted.is_(False),
            ))
            .outerjoin(DormRoom, and_(
                DormRoom.id == DormStay.room_id, DormRoom.tenant_id == _tid(),
                DormRoom.is_deleted.is_(False),
            ))
            .outerjoin(DormBuilding, and_(
                DormBuilding.id == DormStay.building_id, DormBuilding.tenant_id == _tid(),
                DormBuilding.is_deleted.is_(False),
            ))
            .where(*conds).order_by(DormStay.checkin_at.desc(), DormStay.id.desc())
            .offset((page - 1) * page_size).limit(page_size)
        ).all()
        return [
            _stay_row(stay, student=student, bed=bed, room=room, building=building)
            for stay, student, bed, room, building in rows
        ], total


def my_stays(user) -> dict:
    from app.models import DormBed, DormBuilding, DormRoom, DormStay, StudentProfile
    from app.services.mobile_student_service import resolve_student

    with session() as db:
        student = resolve_student(db, user)
        if not student:
            raise AppException("NO_PERMISSION", "尚未建立你的学生档案")
        rows = db.execute(
            select(DormStay, DormBed, DormRoom, DormBuilding)
            .outerjoin(DormBed, and_(
                DormBed.id == DormStay.bed_id, DormBed.tenant_id == _tid(),
                DormBed.is_deleted.is_(False),
            ))
            .outerjoin(DormRoom, and_(
                DormRoom.id == DormStay.room_id, DormRoom.tenant_id == _tid(),
                DormRoom.is_deleted.is_(False),
            ))
            .outerjoin(DormBuilding, and_(
                DormBuilding.id == DormStay.building_id, DormBuilding.tenant_id == _tid(),
                DormBuilding.is_deleted.is_(False),
            ))
            .where(
                DormStay.tenant_id == _tid(), DormStay.student_id == int(student.id),
                DormStay.is_deleted.is_(False),
            ).order_by(DormStay.checkin_at.desc(), DormStay.id.desc())
        ).all()
        items = [
            _stay_row(stay, student=student, bed=bed, room=room, building=building)
            for stay, bed, room, building in rows
        ]
        return {"items": items, "total": len(items)}
