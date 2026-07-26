"""学工中心四端补充 API。

只增加现有移动/门户接线层缺少的本人编辑、正式调宿、可信签到和正式二课成绩单，
核心审批状态机仍由 affairs_*_service.py 提供。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.exceptions import AppException, no_permission, not_found
from app.core.optimistic_lock import atomic_claim_version
from app.core.permissions import require_permission
from app.core.response import paginate, success
from app.core.security import get_current_user
from app.services.db_service import _tid, session

router = APIRouter(tags=["学工中心·四端契约"])


class ReturnedLeaveUpdate(BaseModel):
    leaveType: Optional[str] = Field(None, description="SICK/PERSONAL/HOME/HOSPITAL/GOOUT/OTHER")
    startTime: Optional[str] = None
    endTime: Optional[str] = None
    reason: Optional[str] = Field(None, max_length=500)
    version: int = Field(..., description="当前页面看到的乐观锁版本")


class SelfDormTransferBody(BaseModel):
    toBedId: int = Field(..., ge=1)
    reason: str = Field(..., min_length=5, max_length=500)


class SecureCheckinBody(BaseModel):
    token: str = Field(..., min_length=20)


def _self_student(db, user):
    from app.services.mobile_student_service import resolve_student
    stu = resolve_student(db, user)
    if not stu:
        raise no_permission("尚未建立你的学生档案")
    return stu


def _self_leave(db, leave_id: int, user):
    from app.models import CsLeave
    stu = _self_student(db, user)
    row = db.get(CsLeave, int(leave_id))
    if (
        not row
        or row.is_deleted
        or row.tenant_id != _tid()
        or int(row.student_id or 0) != int(stu.id)
    ):
        raise not_found("请假申请不存在或不属于本人")
    return row, stu


@router.get("/mobile/affairs/leave/{leave_id}/editable", summary="本人读取退回请假的可编辑内容")
def leave_editable(leave_id: int = Path(...), user=Depends(get_current_user)):
    from app.services import affairs_leave_service as leave_svc
    with session() as db:
        row, stu = _self_leave(db, leave_id, user)
        if row.affairs_status != "RETURNED":
            raise AppException("DATA_CONFLICT", "只有已退回申请可以修改")
        data = leave_svc._row(row, stu)
        data["allowedActions"] = ["EDIT_RETURNED", "RESUBMIT"]
        return success(data)


@router.put("/mobile/affairs/leave/{leave_id}/returned", summary="本人修改已退回请假")
def leave_update_returned(
    body: ReturnedLeaveUpdate,
    leave_id: int = Path(...),
    user=Depends(get_current_user),
):
    from app.models import CsLeave
    from app.services import affairs_leave_service as leave_svc

    with session() as db:
        row, stu = _self_leave(db, leave_id, user)
        if row.affairs_status != "RETURNED":
            raise AppException("DATA_CONFLICT", "只有已退回申请可以修改")
        atomic_claim_version(db, row, body.version)

        leave_type = body.leaveType or row.leave_type
        if leave_type not in leave_svc.L_TYPE:
            raise AppException("VALIDATION_ERROR", "请假类型非法")
        start = leave_svc._parse_dt(body.startTime) if body.startTime is not None else row.start_time
        end = leave_svc._parse_dt(body.endTime) if body.endTime is not None else row.end_time
        if not start or not end or end <= start:
            raise AppException("VALIDATION_ERROR", "结束时间必须晚于开始时间")
        reason = (body.reason if body.reason is not None else row.reason or "").strip()
        if len(reason) < 2:
            raise AppException("VALIDATION_ERROR", "请假事由至少填写2个字")

        active_states = (
            "SUBMITTED", "COUNSELOR_REVIEW", "COLLEGE_REVIEW",
            "STUDENT_AFFAIRS_REVIEW", "APPROVED", "EXTENSION_REVIEW",
            "WAIT_CANCEL_LEAVE", "OVERDUE",
        )
        others = db.scalars(select(CsLeave).where(
            CsLeave.tenant_id == _tid(),
            CsLeave.student_id == int(stu.id),
            CsLeave.id != int(row.id),
            CsLeave.affairs_status.in_(active_states),
            CsLeave.is_deleted.is_(False),
        )).all()
        if any(leave_svc._overlap(start, end, x.start_time, x.end_time) for x in others):
            raise AppException("DATA_CONFLICT", "该时间段与已有请假记录重叠")

        before = (
            f"type={row.leave_type};start={row.start_time};"
            f"end={row.end_time};reason={row.reason or ''}"
        )
        row.leave_type = leave_type
        row.start_time = start
        row.end_time = end
        row.days = leave_svc._days(start, end)
        row.reason = reason
        row.version = int(row.version or 0) + 1
        after = f"type={leave_type};start={start};end={end};reason={reason}"
        leave_svc._audit(db, row.id, "STUDENT_EDIT_RETURNED", before=before, after=after)
        db.commit()
        db.refresh(row)
        data = leave_svc._row(row, stu)
        data["allowedActions"] = ["RESUBMIT"]
        return success(data, message="已保存修改，请重新提交")


@router.post("/mobile/affairs/dorm/transfers", summary="本人提交调宿申请")
def dorm_transfer_self(body: SelfDormTransferBody, user=Depends(get_current_user)):
    from app.models import DormBed, DormBuilding, DormTransfer
    from app.services import affairs_dorm_service as dorm

    with session() as db:
        stu = _self_student(db, user)
        current = db.scalars(select(DormBed).where(
            DormBed.tenant_id == _tid(),
            DormBed.student_id == int(stu.id),
            DormBed.status == "OCCUPIED",
            DormBed.is_deleted.is_(False),
        )).first()
        if not current:
            raise AppException("DATA_CONFLICT", "你当前没有床位，请使用首次自选入住")
        target = db.get(DormBed, int(body.toBedId))
        if not target or target.is_deleted or target.tenant_id != _tid():
            raise not_found("目标床位不存在")
        if target.status != "VACANT":
            raise AppException("DATA_CONFLICT", "目标床位已被占用或锁定")
        if int(target.id) == int(current.id):
            raise AppException("VALIDATION_ERROR", "目标床位不能与当前床位相同")
        building = db.get(DormBuilding, int(target.building_id))
        if building and not dorm._gender_ok(building.gender_limit, stu.gender):
            raise AppException("DATA_CONFLICT", "学生性别与目标楼栋限制不符")
        pending = db.scalars(select(DormTransfer).where(
            DormTransfer.tenant_id == _tid(),
            DormTransfer.student_id == int(stu.id),
            DormTransfer.status.in_(("SUBMITTED", "COUNSELOR_REVIEW", "DORM_MANAGER_REVIEW", "RETURNED")),
            DormTransfer.is_deleted.is_(False),
        )).first()
        if pending:
            raise AppException("DATA_CONFLICT", "已有调宿申请正在处理中，请勿重复提交")
        sid = int(stu.id)

    result = dorm.submit_transfer(user, sid, body.toBedId, body.reason.strip())
    return success(result, message="调宿申请已提交")


@router.get("/mobile/affairs/dorm/transfers/my", summary="本人调宿申请列表")
def dorm_transfer_my(
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    user=Depends(get_current_user),
):
    from app.services import affairs_dorm_service as dorm
    with session() as db:
        stu = _self_student(db, user)
        sid = int(stu.id)
    items, total = dorm.list_transfers(user, page=page, page_size=pageSize, student_id=sid)
    return success(paginate(items, total, page, pageSize))


@router.get(
    "/mobile/teacher/affairs/activities/{activity_id}/checkin-token",
    summary="教师生成5分钟动态活动签到码",
)
def activity_checkin_token(
    activity_id: int = Path(...),
    user=Depends(require_permission("studentAffairs.activity.publish")),
):
    from app.services.affairs_four_end_contract import issue_activity_token
    return success(issue_activity_token(activity_id, user))


@router.post(
    "/mobile/affairs/activities/{activity_id}/secure-checkin",
    summary="学生使用动态签到码签到",
)
def activity_secure_checkin(
    body: SecureCheckinBody,
    activity_id: int = Path(...),
    user=Depends(get_current_user),
):
    from app.services.affairs_four_end_contract import secure_activity_checkin
    return success(secure_activity_checkin(activity_id, body.token, user), message="签到成功")


@router.get("/mobile/affairs/second-class/report", summary="本人正式第二课堂成绩单")
def second_class_report_my(user=Depends(get_current_user)):
    from app.services import affairs_activity_service as activity
    with session() as db:
        stu = _self_student(db, user)
        sid = int(stu.id)
    return success(activity.student_report(sid, user))
