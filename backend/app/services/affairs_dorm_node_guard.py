"""调宿节点安全门：学生本人提交、辅导员待办、宿管楼栋待办与执行副作用。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.services.db_service import _tid, session

_INSTALLED = False


def _user_id(user) -> int:
    raw = str((user or {}).get("userId") or "")
    if raw.startswith("db-"):
        raw = raw[3:]
    return int(raw) if raw.isdigit() else 0


def _require_pending_assignee(db, transfer_id: int, user, todo_type: str) -> None:
    from app.models import UnifiedTodo
    uid = _user_id(user)
    if uid <= 0:
        raise AppException("NO_PERMISSION", "当前账号未绑定可核验的审批人ID")
    todo = db.scalars(select(UnifiedTodo).where(
        UnifiedTodo.tenant_id == _tid(),
        UnifiedTodo.source_module == "student-affairs",
        UnifiedTodo.source_biz_type == "DORM_TRANSFER",
        UnifiedTodo.source_biz_id == int(transfer_id),
        UnifiedTodo.todo_type == todo_type,
        UnifiedTodo.status == "PENDING",
        UnifiedTodo.is_deleted.is_(False),
    ).order_by(UnifiedTodo.id.desc())).first()
    if not todo or int(todo.assignee_id or 0) != uid:
        raise AppException("NO_PERMISSION", "当前调宿待办未指派给您")


def _notify(db, student_id: int, transfer_id: int, title: str, content: str, event_code: str) -> None:
    from app.services.message_event_outbox_service import emit_receiver_notice
    emit_receiver_notice(
        db, event_code=event_code, source_module="student-affairs",
        source_biz_type="DORM_TRANSFER", source_biz_id=int(transfer_id),
        receiver_id=int(student_id), receiver_as="student",
        title=title, content=content, dedup_extra=event_code,
    )


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    from app.models import (
        DormBed, DormBuilding, DormRoom, DormTransfer, StudentProfile, StudentStageEvent,
    )
    from app.services import affairs_dorm_service as dorm

    def submit_transfer(user, student_id, to_bed_id, reason=""):
        reason = str(reason or "").strip()
        if not 5 <= len(reason) <= 500:
            raise AppException("VALIDATION_ERROR", "调宿原因需5-500字")
        with session() as db:
            student = db.scalars(select(StudentProfile).where(
                StudentProfile.tenant_id == _tid(), StudentProfile.id == int(student_id),
                StudentProfile.is_deleted.is_(False),
            ).with_for_update()).first()
            if not student:
                raise not_found("学生不存在")
            from app.core.affairs_security import build_affairs_context
            context = build_affairs_context(user, db)
            if (user or {}).get("userType", "").upper() == "STUDENT":
                from app.services.mobile_student_service import resolve_student
                own = resolve_student(db, user or {})
                if not own or int(own.id) != int(student.id):
                    raise AppException("NO_PERMISSION", "学生只能提交本人的调宿申请")
            elif context.scope_type in ("CLASS", "COLLEGE", "TENANT_ALL"):
                context.require_student(db, int(student.id))

            current_beds = db.scalars(select(DormBed).where(
                DormBed.tenant_id == _tid(), DormBed.student_id == int(student.id),
                DormBed.status == "OCCUPIED", DormBed.is_deleted.is_(False),
            ).with_for_update()).all()
            if len(current_beds) != 1:
                raise AppException("DATA_CONFLICT", "当前有效床位异常，请先由宿管核对")
            current = current_beds[0]
            target = db.scalars(select(DormBed).where(
                DormBed.tenant_id == _tid(), DormBed.id == int(to_bed_id),
                DormBed.is_deleted.is_(False),
            ).with_for_update()).first()
            if not target:
                raise not_found("目标床位不存在")
            if int(target.id) == int(current.id):
                raise AppException("DATA_CONFLICT", "目标床位不能与当前床位相同")
            if context.scope_type == "DORM_BUILDING":
                dorm._require_dorm_scope(db, current.building_id, user)
                dorm._require_dorm_scope(db, target.building_id, user)
            elif context.scope_type not in ("SELF", "CLASS", "COLLEGE", "TENANT_ALL"):
                raise AppException("NO_PERMISSION", "当前身份无权发起调宿")
            if target.status != "VACANT" or target.student_id is not None:
                raise AppException("DATA_CONFLICT", "目标床位已被占用或锁定")
            building = db.get(DormBuilding, int(target.building_id))
            room = db.get(DormRoom, int(target.room_id))
            if not building or building.is_deleted or building.tenant_id != _tid() \
                    or not room or room.is_deleted or room.tenant_id != _tid():
                raise AppException("DATA_INCONSISTENT", "目标房源信息不完整")
            if not dorm._gender_ok(building.gender_limit, student.gender):
                raise AppException("DATA_CONFLICT", "学生性别与目标楼栋限制不符")
            duplicate = db.scalars(select(DormTransfer.id).where(
                DormTransfer.tenant_id == _tid(), DormTransfer.student_id == int(student.id),
                DormTransfer.status.in_(dorm.TRANSFER_NODES), DormTransfer.is_deleted.is_(False),
            ).limit(1)).first()
            if duplicate:
                raise AppException("DATA_CONFLICT", "已有调宿申请正在处理中，请勿重复提交")
            first = dorm.TRANSFER_NODES[0]
            transfer = DormTransfer(
                tenant_id=_tid(), student_id=student.id, from_bed_id=current.id,
                to_bed_id=target.id, reason=reason, status=first, current_node=first,
            )
            db.add(transfer); db.flush()
            assignee = dorm._counselor_assignee_id(db, student.id)
            dorm._todo_upsert(
                db, transfer.id, assignee, student.id,
                f"调宿待审：{student.real_name or ''}", dorm.TODO_TRANSFER,
                biz_type="DORM_TRANSFER",
            )
            dorm._audit(db, "DORM_TRANSFER", transfer.id, "SUBMIT", reason)
            db.commit(); db.refresh(transfer)
            return dorm._transfer_row(transfer)

    def review_transfer(transfer_id, user, action, reason="", expected_version=None):
        action = str(action or "").upper()
        if action not in ("APPROVE", "REJECT"):
            raise AppException("VALIDATION_ERROR", "无效审批动作")
        with session() as db:
            transfer = db.scalars(select(DormTransfer).where(
                DormTransfer.tenant_id == _tid(), DormTransfer.id == int(transfer_id),
                DormTransfer.is_deleted.is_(False),
            ).with_for_update()).first()
            if not transfer:
                raise not_found("调宿申请不存在")
            node = transfer.current_node or transfer.status
            if node not in dorm.TRANSFER_NODES or transfer.status not in dorm.TRANSFER_NODES:
                raise AppException("APPROVAL_VERSION_CONFLICT", "该调宿当前状态不可审批")
            dorm.atomic_claim_version(db, transfer, expected_version)
            student = db.scalars(select(StudentProfile).where(
                StudentProfile.tenant_id == _tid(), StudentProfile.id == int(transfer.student_id),
                StudentProfile.is_deleted.is_(False),
            ).with_for_update()).first()
            if not student:
                raise not_found("调宿学生不存在")
            target = db.scalars(select(DormBed).where(
                DormBed.tenant_id == _tid(), DormBed.id == int(transfer.to_bed_id),
                DormBed.is_deleted.is_(False),
            ).with_for_update()).first()
            if not target:
                raise not_found("目标床位不存在")
            from app.core.affairs_security import build_affairs_context
            context = build_affairs_context(user, db)
            if context.scope_type != "TENANT_ALL":
                if node == "COUNSELOR_REVIEW":
                    if context.scope_type not in ("CLASS", "COLLEGE"):
                        raise AppException("NO_PERMISSION", "当前节点仅辅导员/学院学工可审批")
                    context.require_student(db, int(student.id))
                    _require_pending_assignee(db, transfer.id, user, dorm.TODO_TRANSFER)
                elif node == "DORM_MANAGER_REVIEW":
                    if context.scope_type != "DORM_BUILDING":
                        raise AppException("NO_PERMISSION", "当前节点仅目标楼栋宿管可审批")
                    dorm._require_dorm_scope(db, target.building_id, user)
                    _require_pending_assignee(db, transfer.id, user, dorm.TODO_TRANSFER)

            if action == "REJECT":
                text = str(reason or "").strip()
                if not 5 <= len(text) <= 500:
                    raise AppException("VALIDATION_ERROR", "驳回原因需5-500字")
                transfer.status, transfer.current_node = "REJECTED", "REJECTED"
                transfer.return_reason = text
                transfer.version = int(transfer.version or 0) + 1
                dorm._todo_done(db, transfer.id, dorm.TODO_TRANSFER)
                dorm._audit(db, "DORM_TRANSFER", transfer.id, "REJECTED", text)
                _notify(db, student.id, transfer.id, "调宿申请未通过", text, "DORM.TRANSFER.REJECTED")
            elif node == "COUNSELOR_REVIEW":
                transfer.status = transfer.current_node = "DORM_MANAGER_REVIEW"
                transfer.version = int(transfer.version or 0) + 1
                dorm._todo_done(db, transfer.id, dorm.TODO_TRANSFER)
                dorm._push_dorm_manager_todos(
                    db, biz_id=transfer.id, building_id=target.building_id,
                    student_id=student.id, title=f"调宿待审（宿管）：{student.real_name or ''}",
                    todo_type=dorm.TODO_TRANSFER, biz_type="DORM_TRANSFER",
                )
                dorm._audit(db, "DORM_TRANSFER", transfer.id, "STEP", "COUNSELOR_REVIEW->DORM_MANAGER_REVIEW")
            else:
                if target.status != "VACANT" or target.student_id is not None:
                    raise AppException("DATA_CONFLICT", "目标床位已被占用，调宿无法执行")
                building = db.get(DormBuilding, int(target.building_id))
                room = db.get(DormRoom, int(target.room_id))
                if not building or building.is_deleted or building.tenant_id != _tid() \
                        or not room or room.is_deleted or room.tenant_id != _tid():
                    raise AppException("DATA_INCONSISTENT", "目标房源信息不完整")
                if not dorm._gender_ok(building.gender_limit, student.gender):
                    raise AppException("DATA_CONFLICT", "学生性别与目标楼栋限制不符")
                current_beds = db.scalars(select(DormBed).where(
                    DormBed.tenant_id == _tid(), DormBed.student_id == int(student.id),
                    DormBed.status == "OCCUPIED", DormBed.is_deleted.is_(False),
                ).with_for_update()).all()
                if len(current_beds) != 1 or int(current_beds[0].id) != int(transfer.from_bed_id):
                    raise AppException("DATA_CONFLICT", "学生当前床位已变化，请重新申请")
                old_bed = current_beds[0]
                target.student_id, target.status, target.occupied_at = int(student.id), "OCCUPIED", datetime.utcnow()
                target.version = int(target.version or 0) + 1
                target.cs_dorm_record_id = dorm._writeback_dorm_record(
                    db, student.id, building.building_name, room.room_no, target.bed_no,
                )
                old_bed.student_id, old_bed.status, old_bed.occupied_at = None, "VACANT", None
                old_bed.cs_dorm_record_id = None
                old_bed.version = int(old_bed.version or 0) + 1
                transfer.status = transfer.current_node = "EXECUTED"
                transfer.version = int(transfer.version or 0) + 1
                dorm._todo_done(db, transfer.id, dorm.TODO_TRANSFER)
                db.add(StudentStageEvent(
                    tenant_id=_tid(), student_id=int(student.id), from_stage=None,
                    to_stage="DORM_TRANSFER_EXECUTED", reason="调宿已执行",
                    source_module="student-affairs",
                ))
                dorm._audit(db, "DORM_TRANSFER", transfer.id, "EXECUTED")
                _notify(
                    db, student.id, transfer.id, "调宿已完成",
                    f"已调入 {building.building_name} {room.room_no} {target.bed_no}",
                    "DORM.TRANSFER.EXECUTED",
                )
            db.commit(); db.refresh(transfer)
            return dorm._transfer_row(transfer)

    dorm.submit_transfer = submit_transfer
    dorm.review_transfer = review_transfer
    _INSTALLED = True
