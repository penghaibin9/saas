"""宿舍入住、退宿与调宿的并发可靠性收口。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException, not_found
from app.core.optimistic_lock import atomic_claim_version
from app.services.db_service import _tid, session


def _strict_gender_ok(building_gender, student_gender) -> bool:
    limit = str(building_gender or "MIXED").upper()
    if limit == "MIXED":
        return True
    gender = str(student_gender or "").upper()
    male = gender in ("M", "MALE", "男", "1")
    female = gender in ("F", "FEMALE", "女", "2")
    if not male and not female:
        return False
    return (limit == "MALE" and male) or (limit == "FEMALE" and female)


def install() -> None:
    from app.models import (
        DormBed, DormBuilding, DormRoom, DormTransfer, StudentProfile,
        WorkflowTask,
    )
    from app.services import affairs_dorm_service as dorm

    def checkin(bed_id, user, student_id):
        with session() as db:
            student = db.scalars(select(StudentProfile).where(
                StudentProfile.tenant_id == _tid(),
                StudentProfile.id == int(student_id),
                StudentProfile.is_deleted.is_(False),
            ).with_for_update()).first()
            if not student:
                raise not_found("学生不存在")
            existing = db.scalars(select(DormBed).where(
                DormBed.tenant_id == _tid(),
                DormBed.student_id == int(student.id),
                DormBed.status == "OCCUPIED",
                DormBed.is_deleted.is_(False),
            ).with_for_update()).all()
            target = db.scalars(select(DormBed).where(
                DormBed.tenant_id == _tid(),
                DormBed.id == int(bed_id),
                DormBed.is_deleted.is_(False),
            ).with_for_update()).first()
            if not target:
                raise not_found("床位不存在")
            dorm._require_dorm_scope(db, target.building_id, user)
            if any(int(row.id) != int(target.id) for row in existing):
                raise AppException("DATA_CONFLICT", "该学生已有床位，请通过正式调宿流程变更")
            if existing and int(existing[0].id) == int(target.id):
                raise AppException("DATA_CONFLICT", "该学生已入住此床位")
            if target.status != "VACANT" or target.student_id is not None:
                raise AppException("DATA_CONFLICT", "该床位已被占用或锁定")
            building = db.get(DormBuilding, int(target.building_id))
            if not building or building.is_deleted or building.tenant_id != _tid():
                raise not_found("楼栋不存在")
            if not _strict_gender_ok(building.gender_limit, student.gender):
                raise AppException("DATA_CONFLICT", "学生性别信息缺失或与楼栋限制不符")
            room = db.get(DormRoom, int(target.room_id))
            if not room or room.is_deleted or room.tenant_id != _tid():
                raise not_found("房间不存在")
            target.student_id = int(student.id)
            target.status = "OCCUPIED"
            target.occupied_at = datetime.utcnow()
            target.version = int(target.version or 0) + 1
            record_id = dorm._writeback_dorm_record(
                db, student.id, building.building_name, room.room_no, target.bed_no,
            )
            target.cs_dorm_record_id = record_id
            dorm._audit(db, "DORM_BED", target.id, "CHECKIN", f"student={student.id}")
            db.commit()
            return {
                "bedId": str(target.id), "bedNo": target.bed_no,
                "studentId": str(student.id), "building": building.building_name,
                "room": room.room_no, "status": "OCCUPIED",
            }

    def checkout(bed_id, user):
        from app.models import CsDormRecord
        with session() as db:
            bed = db.scalars(select(DormBed).where(
                DormBed.tenant_id == _tid(), DormBed.id == int(bed_id),
                DormBed.is_deleted.is_(False),
            ).with_for_update()).first()
            if not bed:
                raise not_found("床位不存在")
            dorm._require_dorm_scope(db, bed.building_id, user)
            if bed.status != "OCCUPIED" or not bed.student_id:
                raise AppException("DATA_CONFLICT", "该床位无人入住")
            expected = None
            try:
                from app.services.affairs_four_end_contract import request_version
                expected = request_version()
            except Exception:
                expected = None
            if expected is None:
                raise AppException("APPROVAL_VERSION_CONFLICT", "退宿必须提供当前床位version")
            atomic_claim_version(db, bed, expected)
            student_id = int(bed.student_id)
            if bed.cs_dorm_record_id:
                record = db.get(CsDormRecord, int(bed.cs_dorm_record_id))
                if record and record.tenant_id == _tid():
                    record.status, record.record_status = "OUT", "INACTIVE"
                    record.version = int(record.version or 0) + 1
            bed.student_id = None
            bed.status = "VACANT"
            bed.occupied_at = None
            bed.cs_dorm_record_id = None
            bed.version = int(bed.version or 0) + 1
            dorm._audit(db, "DORM_BED", bed.id, "CHECKOUT", f"student={student_id}")
            db.commit()
            return {"bedId": str(bed.id), "status": "VACANT", "version": bed.version}

    def submit_transfer(user, student_id, to_bed_id, reason=""):
        reason = str(reason or "").strip()
        if len(reason) < 5:
            raise AppException("VALIDATION_ERROR", "调宿原因不少于5字")
        with session() as db:
            student = db.scalars(select(StudentProfile).where(
                StudentProfile.tenant_id == _tid(),
                StudentProfile.id == int(student_id),
                StudentProfile.is_deleted.is_(False),
            ).with_for_update()).first()
            if not student:
                raise not_found("学生不存在")
            from_beds = db.scalars(select(DormBed).where(
                DormBed.tenant_id == _tid(), DormBed.student_id == int(student.id),
                DormBed.status == "OCCUPIED", DormBed.is_deleted.is_(False),
            ).with_for_update()).all()
            if len(from_beds) != 1:
                raise AppException("DATA_CONFLICT", "当前有效床位异常，请先由宿管核对后再申请调宿")
            from_bed = from_beds[0]
            to_bed = db.scalars(select(DormBed).where(
                DormBed.tenant_id == _tid(), DormBed.id == int(to_bed_id),
                DormBed.is_deleted.is_(False),
            ).with_for_update()).first()
            if not to_bed:
                raise not_found("目标床位不存在")
            if int(to_bed.id) == int(from_bed.id):
                raise AppException("DATA_CONFLICT", "目标床位不能与当前床位相同")
            dorm._require_dorm_scope(db, from_bed.building_id, user)
            dorm._require_dorm_scope(db, to_bed.building_id, user)
            if to_bed.status != "VACANT" or to_bed.student_id is not None:
                raise AppException("DATA_CONFLICT", "目标床位已被占用")
            building = db.get(DormBuilding, int(to_bed.building_id))
            if not building or not _strict_gender_ok(building.gender_limit, student.gender):
                raise AppException("DATA_CONFLICT", "学生性别信息缺失或与目标楼栋限制不符")
            duplicate = db.scalars(select(DormTransfer.id).where(
                DormTransfer.tenant_id == _tid(),
                DormTransfer.student_id == int(student.id),
                DormTransfer.status.in_(("SUBMITTED", "COUNSELOR_REVIEW", "DORM_MANAGER_REVIEW")),
                DormTransfer.is_deleted.is_(False),
            ).limit(1)).first()
            if duplicate:
                raise AppException("DATA_CONFLICT", "你已有进行中的调宿申请，请勿重复提交")
            first = dorm.TRANSFER_NODES[0]
            transfer = DormTransfer(
                tenant_id=_tid(), student_id=student.id,
                from_bed_id=from_bed.id, to_bed_id=to_bed.id,
                reason=reason, status=first, current_node=first,
            )
            db.add(transfer)
            db.flush()
            counselor = dorm._counselor_assignee_id(db, student.id)
            dorm._todo_upsert(
                db, transfer.id, counselor, student.id,
                f"调宿待审：{student.real_name or ''}", dorm.TODO_TRANSFER,
                biz_type="DORM_TRANSFER",
            )
            dorm._audit(db, "DORM_TRANSFER", transfer.id, "SUBMIT", reason)
            db.commit()
            db.refresh(transfer)
            return dorm._transfer_row(transfer)

    def review_transfer(transfer_id, user, action, reason="", expected_version=None):
        action = str(action or "").upper()
        with session() as db:
            transfer = db.scalars(select(DormTransfer).where(
                DormTransfer.tenant_id == _tid(),
                DormTransfer.id == int(transfer_id),
                DormTransfer.is_deleted.is_(False),
            ).with_for_update()).first()
            if not transfer:
                raise not_found("调宿申请不存在")
            if transfer.status not in dorm.TRANSFER_NODES:
                raise AppException("APPROVAL_VERSION_CONFLICT", "该调宿当前状态不可审批")
            atomic_claim_version(db, transfer, expected_version)
            student = db.scalars(select(StudentProfile).where(
                StudentProfile.tenant_id == _tid(),
                StudentProfile.id == int(transfer.student_id),
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
            dorm._require_dorm_scope(db, target.building_id, user)
            if action == "REJECT":
                if len(str(reason or "").strip()) < 5:
                    raise AppException("VALIDATION_ERROR", "驳回原因不少于5字")
                transfer.status = "REJECTED"
                transfer.return_reason = str(reason).strip()
                transfer.version = int(transfer.version or 0) + 1
                dorm._todo_done(db, transfer.id, dorm.TODO_TRANSFER)
                dorm._audit(db, "DORM_TRANSFER", transfer.id, "REJECTED", transfer.return_reason)
            elif action == "APPROVE":
                index = dorm.TRANSFER_NODES.index(transfer.current_node)
                if index + 1 < len(dorm.TRANSFER_NODES):
                    next_node = dorm.TRANSFER_NODES[index + 1]
                    transfer.current_node = next_node
                    transfer.status = next_node
                    transfer.version = int(transfer.version or 0) + 1
                    dorm._todo_done(db, transfer.id, dorm.TODO_TRANSFER)
                    dorm._push_dorm_manager_todos(
                        db, biz_id=transfer.id, building_id=target.building_id,
                        student_id=student.id, title=f"调宿待审（宿管）：{student.real_name or ''}",
                        todo_type=dorm.TODO_TRANSFER, biz_type="DORM_TRANSFER",
                    )
                    dorm._audit(db, "DORM_TRANSFER", transfer.id, "STEP", f"->{next_node}")
                else:
                    if target.status != "VACANT" or target.student_id is not None:
                        raise AppException("DATA_CONFLICT", "目标床位已被占用，调宿无法执行")
                    building = db.get(DormBuilding, int(target.building_id))
                    room = db.get(DormRoom, int(target.room_id))
                    if not building or not room:
                        raise AppException("DATA_INCONSISTENT", "目标房源信息不完整")
                    if not _strict_gender_ok(building.gender_limit, student.gender):
                        raise AppException("DATA_CONFLICT", "学生性别信息缺失或与目标楼栋限制不符")
                    current_beds = db.scalars(select(DormBed).where(
                        DormBed.tenant_id == _tid(),
                        DormBed.student_id == int(student.id),
                        DormBed.status == "OCCUPIED",
                        DormBed.is_deleted.is_(False),
                    ).with_for_update()).all()
                    if len(current_beds) != 1 or int(current_beds[0].id) != int(transfer.from_bed_id):
                        raise AppException("DATA_CONFLICT", "学生当前床位已变化，请重新发起调宿")
                    old_bed = current_beds[0]
                    # 先在同一事务内锁定并占用目标床，再释放原床；任何异常整体回滚。
                    target.student_id = int(student.id)
                    target.status = "OCCUPIED"
                    target.occupied_at = datetime.utcnow()
                    target.version = int(target.version or 0) + 1
                    record_id = dorm._writeback_dorm_record(
                        db, student.id, building.building_name, room.room_no, target.bed_no,
                    )
                    target.cs_dorm_record_id = record_id
                    old_bed.student_id = None
                    old_bed.status = "VACANT"
                    old_bed.occupied_at = None
                    old_bed.cs_dorm_record_id = None
                    old_bed.version = int(old_bed.version or 0) + 1
                    transfer.status = "EXECUTED"
                    transfer.current_node = "EXECUTED"
                    transfer.version = int(transfer.version or 0) + 1
                    dorm._todo_done(db, transfer.id, dorm.TODO_TRANSFER)
                    dorm._audit(db, "DORM_TRANSFER", transfer.id, "EXECUTED")
            else:
                raise AppException("VALIDATION_ERROR", "无效操作")
            db.commit()
            db.refresh(transfer)
            return dorm._transfer_row(transfer)

    dorm._gender_ok = _strict_gender_ok
    dorm.checkin = checkin
    dorm.checkout = checkout
    dorm.submit_transfer = submit_transfer
    dorm.review_transfer = review_transfer
