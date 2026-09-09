"""X1 宿舍/迎新生产台账的数据集定义。

本模块只组装已按 Data Scope 收敛的行，不负责写文件或创建 ExportTask；文件、安全
水印、用途、审计仍由 domain_export_service 统一处理。
"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import and_, select

from app.core.exceptions import AppException
from app.services.db_service import _iso, _tid, session

MAX_REPORT_ROWS = 5000

ORIENTATION_REPORTS = {
    "students": ("迎新新生台账", "迎新新生台账.xlsx"),
    "progress": ("报到进度", "报到进度.xlsx"),
    "materials": ("材料审核", "材料审核.xlsx"),
    "payment": ("缴费状态", "缴费状态.xlsx"),
    "green-channel": ("绿色通道", "绿色通道.xlsx"),
    "dorm": ("住宿安排", "住宿安排.xlsx"),
    "checkin": ("现场报到", "现场报到.xlsx"),
    "no-show": ("未报到", "未报到.xlsx"),
    "exceptions": ("迎新异常", "迎新异常.xlsx"),
}

DORM_REPORTS = {
    "resources": ("房源台账", "房源台账.xlsx"),
    "residents": ("住宿学生台账", "住宿学生台账.xlsx"),
    "vacant": ("空床台账", "空床台账.xlsx"),
    "allocation": ("住宿分配结果", "住宿分配结果.xlsx"),
    "transfer": ("调宿台账", "调宿台账.xlsx"),
    "checkout": ("退宿台账", "退宿台账.xlsx"),
    "inspection": ("检查整改台账", "检查整改台账.xlsx"),
    "exceptions": ("宿舍异常台账", "宿舍异常台账.xlsx"),
    "presence": ("归寝异常台账", "归寝异常台账.xlsx"),
}


def _bounded(items: list, total: int | None = None) -> list:
    count = len(items) if total is None else int(total)
    if count > MAX_REPORT_ROWS:
        raise AppException(
            "VALIDATION_ERROR",
            f"导出数据量 {count} 行超过单次上限 {MAX_REPORT_ROWS} 行，请缩小批次或范围后重试",
        )
    return items


def _collect(call) -> list[dict]:
    rows: list[dict] = []
    page = 1
    while True:
        items, total = call(page, 200)
        _bounded(items, total)
        rows.extend(items)
        if len(rows) >= int(total):
            return rows
        page += 1


def _orientation_students(user: dict, batch_id: int) -> list[dict]:
    from app.services import orientation_service
    return _collect(lambda page, size: orientation_service.list_students(
        page, size, batch_id=batch_id, user=user,
    ))


def _orientation_report(report_type: str, user: dict, batch_id) -> dict:
    if report_type not in ORIENTATION_REPORTS:
        raise AppException(
            "VALIDATION_ERROR", f"未知迎新报表类型：{report_type}",
            details={"allowed": sorted(ORIENTATION_REPORTS)},
        )
    try:
        bid = int(batch_id)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "迎新导出必须指定有效 batchId") from None
    from app.models import OrientationBatch
    with session() as db:
        batch = db.get(OrientationBatch, bid)
        if not batch or batch.is_deleted or int(batch.tenant_id) != int(_tid()):
            raise AppException("VALIDATION_ERROR", "迎新导出批次不存在或不属于本校")
        batch_no = batch.batch_no
    base = _orientation_students(user, bid)
    ids = [int(row["id"]) for row in base]
    by_id = {int(row["id"]): row for row in base}
    title, filename = ORIENTATION_REPORTS[report_type]

    # 综合台账/未报到/住宿安排只读 canonical process facts，不以 OrientationStudent
    # 的兼容投影自行裁决。
    from app.models import (DormBed, DormBuilding, DormRoom, DormStay,
                            OrientationCheckinRecord, OrientationPaymentAccount)
    with session() as db:
        payment_by_student = {
            int(row.orientation_student_id): row.status
            for row in db.scalars(select(OrientationPaymentAccount).where(
                OrientationPaymentAccount.tenant_id == _tid(),
                OrientationPaymentAccount.orientation_student_id.in_(ids or [-1]),
                OrientationPaymentAccount.is_deleted.is_(False),
            )).all()
        }
        checked_in_ids = set(db.scalars(select(OrientationCheckinRecord.orientation_student_id).where(
            OrientationCheckinRecord.tenant_id == _tid(),
            OrientationCheckinRecord.orientation_student_id.in_(ids or [-1]),
            OrientationCheckinRecord.status == "CONFIRMED",
            OrientationCheckinRecord.is_deleted.is_(False),
        )).all())
        profile_to_orientation = {
            int(row.get("profileStudentId")): sid for sid, row in by_id.items()
            if str(row.get("profileStudentId") or "").isdigit()
        }
        stays = db.execute(select(DormStay, DormBed, DormRoom, DormBuilding).join(
            DormBed, DormBed.id == DormStay.bed_id,
        ).join(DormRoom, DormRoom.id == DormStay.room_id).join(
            DormBuilding, DormBuilding.id == DormStay.building_id,
        ).where(
            DormStay.tenant_id == _tid(),
            DormStay.student_id.in_(list(profile_to_orientation) or [-1]),
            DormStay.status.in_(("ACTIVE", "RESERVED")), DormStay.is_deleted.is_(False),
            DormBed.is_deleted.is_(False), DormRoom.is_deleted.is_(False), DormBuilding.is_deleted.is_(False),
        )).all()
    dorm_by_orientation = {}
    for stay, bed, room, building in stays:
        orientation_id = profile_to_orientation.get(int(stay.student_id))
        if orientation_id:
            dorm_by_orientation[orientation_id] = {
                "authorityBuilding": building.building_name,
                "authorityRoom": room.room_no,
                "authorityBed": bed.bed_no,
                "authorityDormStatus": "已入住" if stay.status == "ACTIVE" else "已预留",
            }
    for sid, row in by_id.items():
        row["authorityPaymentStatus"] = payment_by_student.get(sid, "UNPAID")
        row["hasSignedCheckin"] = sid in {int(value) for value in checked_in_ids}
        row.update(dorm_by_orientation.get(sid, {
            "authorityBuilding": "", "authorityRoom": "", "authorityBed": "",
            "authorityDormStatus": "未形成住宿事实",
        }))

    if report_type == "students":
        columns = [
            ("迎新批次编号", "batchNo"), ("姓名", "name"), ("录取编号", "admissionNo"),
            ("学院", "collegeName"), ("专业", "majorName"), ("班级", "className"),
            ("签名现场报到", "signedCheckinLabel"), ("缴费事实", "authorityPaymentStatus"),
            ("住宿事实", "authorityDormStatus"), ("风险", "riskLabel"),
        ]
        items = [{**row, "batchNo": batch_no,
                  "signedCheckinLabel": "已报到" if row["hasSignedCheckin"] else "未报到"} for row in base]
    elif report_type == "progress":
        from app.models import OrientationStudentStep
        with session() as db:
            steps = db.scalars(select(OrientationStudentStep).where(
                OrientationStudentStep.tenant_id == _tid(),
                OrientationStudentStep.orientation_student_id.in_(ids or [-1]),
                OrientationStudentStep.is_deleted.is_(False),
            ).order_by(OrientationStudentStep.orientation_student_id, OrientationStudentStep.id)).all()
        grouped = defaultdict(list)
        for step in steps:
            grouped[int(step.orientation_student_id)].append(step)
        items = []
        for sid, student in by_id.items():
            student_steps = grouped.get(sid, [])
            done = sum(step.status in ("DONE", "WAIVED", "NOT_REQUIRED") for step in student_steps)
            items.append({
                **student, "batchNo": batch_no, "doneSteps": done,
                "totalSteps": len(student_steps),
                "blockedSteps": "；".join(
                    f"{step.step_key}:{step.blocked_reason or '受阻'}"
                    for step in student_steps if step.status == "BLOCKED"
                ),
            })
        columns = [
            ("迎新批次编号", "batchNo"), ("姓名", "name"), ("录取编号", "admissionNo"),
            ("班级", "className"), ("已完成环节", "doneSteps"), ("总环节", "totalSteps"),
            ("受阻环节", "blockedSteps"), ("签名现场报到", "signedCheckinLabel"),
        ]
        for item in items:
            item["signedCheckinLabel"] = "已报到" if item["hasSignedCheckin"] else "未报到"
    elif report_type == "materials":
        from app.models import OrientationMaterial
        with session() as db:
            rows = db.scalars(select(OrientationMaterial).where(
                OrientationMaterial.tenant_id == _tid(),
                OrientationMaterial.ori_student_id.in_(ids or [-1]),
                OrientationMaterial.is_current.is_(True),
                OrientationMaterial.is_deleted.is_(False),
            ).order_by(OrientationMaterial.ori_student_id, OrientationMaterial.material_type)).all()
        items = [{
            "batchNo": batch_no, "name": by_id[int(row.ori_student_id)]["name"],
            "admissionNo": by_id[int(row.ori_student_id)]["admissionNo"],
            "materialType": row.material_type, "fileName": row.file_name or "",
            "submissionNo": int(row.submission_no or 1), "status": row.status,
            "reviewer": row.reviewer or "", "reviewTime": _iso(row.review_time) or "",
            "returnReason": row.return_reason or "",
        } for row in rows]
        columns = [
            ("迎新批次编号", "batchNo"), ("姓名", "name"), ("录取编号", "admissionNo"),
            ("材料类型", "materialType"), ("文件名", "fileName"), ("提交版本", "submissionNo"),
            ("审核状态", "status"), ("审核人", "reviewer"), ("审核时间", "reviewTime"),
            ("退回原因", "returnReason"),
        ]
    elif report_type == "payment":
        from app.models import OrientationPaymentAccount
        with session() as db:
            accounts = db.scalars(select(OrientationPaymentAccount).where(
                OrientationPaymentAccount.tenant_id == _tid(),
                OrientationPaymentAccount.orientation_student_id.in_(ids or [-1]),
                OrientationPaymentAccount.is_deleted.is_(False),
            ).order_by(OrientationPaymentAccount.orientation_student_id)).all()
        account_by_student = {int(row.orientation_student_id): row for row in accounts}
        items = []
        for sid, student in by_id.items():
            row = account_by_student.get(sid)
            items.append({
                "batchNo": batch_no, "name": student["name"],
                "admissionNo": student["admissionNo"],
                "payableAmount": float(row.payable_amount or 0) if row else 0,
                "paidAmount": float(row.paid_amount or 0) if row else 0,
                "status": row.status if row else "MISSING",
                "sourceType": row.source_type if row else "未同步缴费事实",
                "syncedAt": (_iso(row.synced_at) or "") if row else "",
            })
        columns = [
            ("迎新批次编号", "batchNo"), ("姓名", "name"), ("录取编号", "admissionNo"),
            ("应缴金额", "payableAmount"), ("实缴金额", "paidAmount"), ("缴费状态", "status"),
            ("事实来源", "sourceType"), ("同步时间", "syncedAt"),
        ]
    elif report_type == "green-channel":
        from app.models import GreenChannelApplication
        with session() as db:
            rows = db.scalars(select(GreenChannelApplication).where(
                GreenChannelApplication.tenant_id == _tid(),
                GreenChannelApplication.ori_student_id.in_(ids or [-1]),
                GreenChannelApplication.is_deleted.is_(False),
            ).order_by(GreenChannelApplication.id)).all()
        items = [{
            "batchNo": batch_no, "name": by_id[int(row.ori_student_id)]["name"],
            "admissionNo": by_id[int(row.ori_student_id)]["admissionNo"],
            "applyType": row.apply_type, "applyAmount": float(row.apply_amount or 0),
            "status": row.status, "submitTime": _iso(row.submit_time) or "",
            "reviewer": row.reviewer or "", "reviewTime": _iso(row.review_time) or "",
            "rejectReason": row.reject_reason or "",
        } for row in rows]
        columns = [
            ("迎新批次编号", "batchNo"), ("姓名", "name"), ("录取编号", "admissionNo"),
            ("申请类型", "applyType"), ("申请金额", "applyAmount"), ("状态", "status"),
            ("提交时间", "submitTime"), ("审核人", "reviewer"), ("审核时间", "reviewTime"),
            ("驳回原因", "rejectReason"),
        ]
    elif report_type == "dorm":
        items = [{**row, "batchNo": batch_no} for row in base]
        columns = [
            ("迎新批次编号", "batchNo"), ("姓名", "name"), ("录取编号", "admissionNo"),
            ("学院", "collegeName"), ("班级", "className"), ("楼栋", "authorityBuilding"),
            ("房间", "authorityRoom"), ("床号", "authorityBed"), ("住宿状态", "authorityDormStatus"),
        ]
    elif report_type == "checkin":
        from app.models import OrientationCheckinPoint, OrientationCheckinRecord
        with session() as db:
            rows = db.execute(select(OrientationCheckinRecord, OrientationCheckinPoint).join(
                OrientationCheckinPoint,
                and_(OrientationCheckinPoint.id == OrientationCheckinRecord.checkin_point_id,
                     OrientationCheckinPoint.tenant_id == OrientationCheckinRecord.tenant_id),
            ).where(
                OrientationCheckinRecord.tenant_id == _tid(),
                OrientationCheckinRecord.orientation_student_id.in_(ids or [-1]),
                OrientationCheckinRecord.is_deleted.is_(False),
                OrientationCheckinPoint.is_deleted.is_(False),
            ).order_by(OrientationCheckinRecord.checked_in_at)).all()
        items = [{
            "batchNo": batch_no, "name": by_id[int(record.orientation_student_id)]["name"],
            "admissionNo": by_id[int(record.orientation_student_id)]["admissionNo"],
            "pointName": point.name, "location": point.location or "",
            "checkedInAt": _iso(record.checked_in_at) or "", "method": record.checkin_method,
            "status": record.status,
        } for record, point in rows]
        columns = [
            ("迎新批次编号", "batchNo"), ("姓名", "name"), ("录取编号", "admissionNo"),
            ("报到点", "pointName"), ("地点", "location"), ("报到时间", "checkedInAt"),
            ("核验方式", "method"), ("状态", "status"),
        ]
    elif report_type == "no-show":
        items = [{**row, "batchNo": batch_no} for row in base if not row["hasSignedCheckin"]]
        columns = [
            ("迎新批次编号", "batchNo"), ("姓名", "name"), ("录取编号", "admissionNo"),
            ("学院", "collegeName"), ("专业", "majorName"), ("班级", "className"),
            ("报到状态", "reportStatusLabel"), ("卡点", "blockedReason"),
        ]
    else:
        from app.models import OrientationException
        with session() as db:
            rows = db.scalars(select(OrientationException).where(
                OrientationException.tenant_id == _tid(),
                OrientationException.ori_student_id.in_(ids or [-1]),
                OrientationException.is_deleted.is_(False),
            ).order_by(OrientationException.id.desc())).all()
        items = [{
            "batchNo": batch_no, "name": by_id[int(row.ori_student_id)]["name"],
            "admissionNo": by_id[int(row.ori_student_id)]["admissionNo"],
            "exceptionType": row.exception_type, "description": row.description or "",
            "riskLevel": row.risk_level, "status": row.status,
            "handler": row.handler or "", "lastFollowTime": _iso(row.last_follow_time) or "",
        } for row in rows]
        columns = [
            ("迎新批次编号", "batchNo"), ("姓名", "name"), ("录取编号", "admissionNo"),
            ("异常类型", "exceptionType"), ("异常说明", "description"), ("风险等级", "riskLevel"),
            ("状态", "status"), ("处理人", "handler"), ("最近跟进", "lastFollowTime"),
        ]
    _bounded(items)
    return {"title": title, "fileName": filename, "columns": columns, "items": items,
            "scopeLabel": f"迎新批次 {batch_no} + 当前角色学生范围"}


def _dorm_resource_rows(user: dict, *, vacant_only: bool = False) -> list[dict]:
    from app.models import DormBed, DormBuilding, DormRoom, StudentProfile
    from app.services import affairs_dorm_service
    with session() as db:
        scope = affairs_dorm_service._dorm_scope_building_ids(db, user)
        conds = [
            DormBed.tenant_id == _tid(), DormBed.is_deleted.is_(False),
            DormRoom.tenant_id == _tid(), DormRoom.is_deleted.is_(False),
            DormBuilding.tenant_id == _tid(), DormBuilding.is_deleted.is_(False),
        ]
        if scope is not None:
            conds.append(DormBed.building_id.in_(scope or {-1}))
        if vacant_only:
            conds.extend([DormBed.status == "VACANT", DormBed.student_id.is_(None)])
        rows = db.execute(select(DormBuilding, DormRoom, DormBed, StudentProfile).join(
            DormRoom, DormRoom.building_id == DormBuilding.id,
        ).join(DormBed, DormBed.room_id == DormRoom.id).outerjoin(
            StudentProfile,
            and_(StudentProfile.id == DormBed.student_id, StudentProfile.tenant_id == _tid(),
                 StudentProfile.is_deleted.is_(False)),
        ).where(*conds).order_by(DormBuilding.building_code, DormRoom.floor_no,
                                 DormRoom.room_no, DormBed.bed_no).limit(MAX_REPORT_ROWS + 1)).all()
    return _bounded([{
        "buildingCode": building.building_code or "", "buildingName": building.building_name,
        "genderLimit": building.gender_limit, "floorNo": room.floor_no, "roomNo": room.room_no,
        "roomType": room.room_type or "", "capacity": room.capacity, "roomStatus": room.status,
        "bedNo": bed.bed_no, "bedStatus": bed.status,
        "studentNo": student.student_no if student else "",
        "studentName": student.real_name if student else "", "occupiedAt": _iso(bed.occupied_at) or "",
    } for building, room, bed, student in rows])


def _dorm_report(report_type: str, user: dict) -> dict:
    if report_type not in DORM_REPORTS:
        raise AppException(
            "VALIDATION_ERROR", f"未知宿舍报表类型：{report_type}",
            details={"allowed": sorted(DORM_REPORTS)},
        )
    title, filename = DORM_REPORTS[report_type]
    scope_label = "当前角色宿舍楼栋范围"
    if report_type in ("resources", "vacant"):
        items = _dorm_resource_rows(user, vacant_only=report_type == "vacant")
        columns = [
            ("楼栋编码", "buildingCode"), ("楼栋名称", "buildingName"), ("性别属性", "genderLimit"),
            ("楼层", "floorNo"), ("房号", "roomNo"), ("房型", "roomType"), ("容量", "capacity"),
            ("床号", "bedNo"), ("床位状态", "bedStatus"), ("学号", "studentNo"),
            ("姓名", "studentName"), ("入住时间", "occupiedAt"),
        ]
    elif report_type == "residents":
        from app.services import affairs_dorm_stay_service
        items = _collect(lambda page, size: affairs_dorm_stay_service.list_stays(
            user, status="ACTIVE", page=page, page_size=size,
        ))
        columns = [
            ("学号", "studentNo"), ("姓名", "studentName"), ("楼栋", "building"),
            ("房间", "room"), ("床号", "bedNo"), ("入住时间", "checkinAt"),
            ("住宿类型", "stayType"), ("来源", "sourceType"), ("状态", "status"),
        ]
    elif report_type == "allocation":
        from app.models import (DormAllocationBatch, DormAllocationItem, DormBed,
                                DormBuilding, DormRoom, StudentProfile)
        from app.services import affairs_dorm_service
        with session() as db:
            scope = affairs_dorm_service._dorm_scope_building_ids(db, user)
            conds = [DormAllocationItem.tenant_id == _tid(), DormAllocationItem.is_deleted.is_(False)]
            if scope is not None:
                conds.append(DormBed.building_id.in_(scope or {-1}))
            rows = db.execute(select(
                DormAllocationBatch, DormAllocationItem, StudentProfile, DormBed, DormRoom, DormBuilding,
            ).join(DormAllocationBatch, and_(
                DormAllocationBatch.id == DormAllocationItem.allocation_batch_id,
                DormAllocationBatch.tenant_id == _tid(), DormAllocationBatch.is_deleted.is_(False),
            )).join(StudentProfile, and_(
                StudentProfile.id == DormAllocationItem.student_id,
                StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False),
            )).outerjoin(DormBed, and_(
                DormBed.id == DormAllocationItem.bed_id,
                DormBed.tenant_id == _tid(), DormBed.is_deleted.is_(False),
            )).outerjoin(DormRoom, and_(
                DormRoom.id == DormBed.room_id,
                DormRoom.tenant_id == _tid(), DormRoom.is_deleted.is_(False),
            )).outerjoin(DormBuilding, and_(
                DormBuilding.id == DormBed.building_id,
                DormBuilding.tenant_id == _tid(), DormBuilding.is_deleted.is_(False),
            ))
             .where(*conds).order_by(DormAllocationBatch.id.desc(), DormAllocationItem.id)
             .limit(MAX_REPORT_ROWS + 1)).all()
        items = _bounded([{
            "batchNo": batch.batch_no, "batchName": batch.name, "studentNo": student.student_no,
            "studentName": student.real_name, "building": building.building_name if building else "",
            "room": room.room_no if room else "", "bedNo": bed.bed_no if bed else "",
            "status": item.status, "source": item.source, "conflictCode": item.conflict_code or "",
            "confirmedAt": _iso(item.confirmed_at) or "",
        } for batch, item, student, bed, room, building in rows])
        columns = [
            ("分配批次编号", "batchNo"), ("分配批次", "batchName"), ("学号", "studentNo"),
            ("姓名", "studentName"), ("楼栋", "building"), ("房间", "room"), ("床号", "bedNo"),
            ("分配状态", "status"), ("来源", "source"), ("冲突代码", "conflictCode"),
            ("确认时间", "confirmedAt"),
        ]
    elif report_type == "transfer":
        from app.services import affairs_dorm_service
        items = _collect(lambda page, size: affairs_dorm_service.list_transfers(
            user, page=page, page_size=size,
        ))
        columns = [
            ("学号", "studentNo"), ("姓名", "realName"), ("原床位ID", "fromBedId"),
            ("目标床位ID", "toBedId"), ("原因", "reason"), ("状态", "status"),
            ("当前节点", "currentNode"),
        ]
    elif report_type == "checkout":
        from app.services import affairs_dorm_stay_service
        items = _collect(lambda page, size: affairs_dorm_stay_service.list_checkout_requests(
            user, page=page, page_size=size,
        ))
        columns = [
            ("学号", "studentNo"), ("姓名", "studentName"), ("原床位", "bedLabel"),
            ("退宿类型", "requestType"),
            ("原因", "reason"), ("状态", "status"), ("申请时间", "requestedAt"),
            ("确认时间", "confirmedAt"),
        ]
    elif report_type == "inspection":
        from app.services import dorm_inspection_service
        items = _collect(lambda page, size: dorm_inspection_service.list_rectifications(
            user, page=page, page_size=size,
        ))
        columns = [
            ("检查任务", "taskName"), ("检查类型", "checkType"), ("楼栋", "buildingName"),
            ("房间", "roomNo"), ("学号", "studentNo"), ("姓名", "studentName"),
            ("严重度", "severity"), ("整改要求", "requirement"), ("截止时间", "deadlineAt"),
            ("状态", "status"), ("整改说明", "rectifyNote"), ("复检说明", "recheckNote"),
        ]
    elif report_type == "exceptions":
        from app.services import affairs_dorm_service
        items = _collect(lambda page, size: affairs_dorm_service.list_exceptions(
            user, page=page, page_size=size,
        ))
        items = [{
            **row,
            "riskLevel": (row.get("relatedRisk") or {}).get("riskLevel") or "",
        } for row in items]
        columns = [
            ("学号", "studentNo"), ("姓名", "realName"), ("异常类型", "excType"),
            ("异常说明", "detail"), ("风险等级", "riskLevel"), ("状态", "status"),
            ("发生时间", "createdAt"),
        ]
    else:
        from app.services import dorm_presence_service
        items = []
        page = 1
        while True:
            page_items, total, _counts = dorm_presence_service.list_presence(
                user, status=None, page=page, page_size=200,
            )
            _bounded(page_items, total)
            items.extend(row for row in page_items if row.get("status") in (
                "OUT", "LATE_RETURN", "NOT_RETURNED", "UNKNOWN",
            ))
            if page * 200 >= int(total):
                break
            page += 1
        columns = [
            ("学号", "studentNo"), ("姓名", "studentName"), ("楼栋", "buildingName"),
            ("房间", "roomNo"), ("床号", "bedNo"), ("归寝状态", "statusLabel"),
            ("最近事件", "lastEventType"), ("最近事件时间", "lastEventAt"),
            ("研判原因", "reason"), ("规则版本", "policyVersion"),
        ]
    _bounded(items)
    return {"title": title, "fileName": filename, "columns": columns, "items": items,
            "scopeLabel": scope_label}


def build_report(domain: str, report_type: str | None, *, user: dict, batch_id=None) -> dict:
    normalized = str(report_type or ("students" if domain == "orientation" else "resources")).strip()
    if domain == "orientation":
        return _orientation_report(normalized, user, batch_id)
    if domain == "dorm":
        return _dorm_report(normalized, user)
    raise AppException("VALIDATION_ERROR", f"域 {domain} 不支持分类台账导出")
