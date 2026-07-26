"""学工异议/申诉四端移动接口。"""
from __future__ import annotations

from types import SimpleNamespace

from fastapi import APIRouter, Body, Depends, Path, Query
from sqlalchemy import select

from app.core.exceptions import AppException, no_permission
from app.core.permissions import has_permission
from app.core.response import success
from app.core.security import get_current_user
from app.services.db_service import _tid, session

router = APIRouter(tags=["学工中心·异议申诉"])

_KINDS = {
    "AID_OBJECTION": {
        "view": ("studentAffairs.aid.view",),
        "review": ("studentAffairs.aid.approve", "studentAffairs.aid.schoolReview"),
        "model": "AidObjection", "id_key": "objectionId",
    },
    "FUNDING_APPEAL": {
        "view": ("studentAffairs.funding.view",),
        "review": ("studentAffairs.funding.approve",),
        "model": "FundingAppeal", "id_key": "appealId",
    },
    "DISCIPLINE_APPEAL": {
        "view": ("studentAffairs.discipline.view",),
        "review": ("studentAffairs.discipline.approve",),
        "model": "DisciplineAppeal", "id_key": "appealId",
    },
    "SECOND_CLASS_APPEAL": {
        "view": ("studentAffairs.activity.view",),
        "review": ("studentAffairs.activity.manage", "studentAffairs.activity.credit.review"),
        "model": "AffairsCreditAppeal", "id_key": "appealId",
    },
}


def _kind(value: str) -> tuple[str, dict]:
    key = (value or "").upper()
    spec = _KINDS.get(key)
    if not spec:
        raise AppException("VALIDATION_ERROR", "不支持的异议/申诉类型")
    return key, spec


def _require_any(user: dict, codes: tuple[str, ...]) -> None:
    if not any(has_permission(user, code) for code in codes):
        raise no_permission("当前身份无权处理该异议/申诉")


def _versions(kind: str, items: list[dict]) -> dict[int, int]:
    from app import models
    spec = _KINDS[kind]
    ids = []
    for item in items:
        value = item.get(spec["id_key"])
        if str(value or "").isdigit():
            ids.append(int(value))
    if not ids:
        return {}
    model = getattr(models, spec["model"])
    with session() as db:
        return {
            int(row.id): int(row.version or 0)
            for row in db.scalars(select(model).where(
                model.tenant_id == _tid(), model.id.in_(ids), model.is_deleted.is_(False)
            )).all()
        }


@router.get("/mobile/teacher/affairs/appeals/{kind}", summary="教师异议/申诉待处理列表")
def appeal_pending(
    kind: str = Path(...),
    page: int = Query(1, ge=1),
    pageSize: int = Query(50, ge=1, le=100),
    user=Depends(get_current_user),
):
    key, spec = _kind(kind)
    _require_any(user, spec["view"])
    if key == "AID_OBJECTION":
        from app.services import affairs_aid_service as service
        items, total = service.list_objections(user, status="SUBMITTED", page=page, page_size=pageSize)
    elif key == "FUNDING_APPEAL":
        from app.services import affairs_funding_service as service
        items, total = service.list_appeals(user, status="SUBMITTED", page=page, page_size=pageSize)
    elif key == "DISCIPLINE_APPEAL":
        from app.services import affairs_discipline_service as service
        items, total = service.list_appeals(user, status="SUBMITTED", page=page, page_size=pageSize)
    else:
        from app.services import affairs_activity_service as service
        items, total, _counts = service.list_credit_appeals(user, status="SUBMITTED", page=page, page_size=pageSize)
    versions = _versions(key, items)
    for item in items:
        raw = item.get(spec["id_key"])
        item["version"] = versions.get(int(raw), 0) if str(raw or "").isdigit() else 0
        item["appealKind"] = key
    return success({"items": items, "total": total, "page": page, "pageSize": pageSize})


@router.post("/mobile/teacher/affairs/appeals/{kind}/{appeal_id}/review", summary="教师复核异议/申诉")
def appeal_review(
    kind: str = Path(...),
    appeal_id: int = Path(...),
    body: dict = Body(...),
    user=Depends(get_current_user),
):
    key, spec = _kind(kind)
    _require_any(user, spec["review"])
    version = body.get("version")
    opinion = str(body.get("opinion") or body.get("reason") or "").strip()
    if len(opinion) < 5:
        raise AppException("VALIDATION_ERROR", "复核意见至少5字")
    if key == "AID_OBJECTION":
        from app.services import affairs_aid_service as service
        result = service.review_objection(appeal_id, {
            "result": str(body.get("result") or "").upper(), "opinion": opinion, "version": version,
        }, user)
    elif key == "FUNDING_APPEAL":
        from app.services import affairs_funding_service as service
        result = service.review_appeal(appeal_id, {
            "result": str(body.get("result") or "").upper(), "opinion": opinion, "version": version,
        }, user)
    elif key == "DISCIPLINE_APPEAL":
        from app.services import affairs_discipline_service as service
        result = service.review_appeal(appeal_id, SimpleNamespace(
            result=str(body.get("result") or "").upper(), opinion=opinion, version=version,
        ), user)
    else:
        from app.services import affairs_activity_service as service
        result = service.review_credit_appeal(appeal_id, SimpleNamespace(
            action=str(body.get("action") or "").upper(), opinion=opinion, version=version,
        ), user)
    return success(result, message="已完成复核")


def _self_student(db, user):
    from app.services.mobile_student_service import _require_student, resolve_student
    _require_student(user)
    student = resolve_student(db, user)
    if not student:
        raise AppException("DATA_NOT_FOUND", "未找到你的学生档案")
    return student


@router.get("/mobile/affairs/second-class/appeals/my", summary="本人第二课堂积分申诉")
def credit_appeals_my(user=Depends(get_current_user)):
    from app.models import AffairsCreditAppeal
    from app.services.affairs_activity_service import _cappeal_row
    with session() as db:
        student = _self_student(db, user)
        rows = db.scalars(select(AffairsCreditAppeal).where(
            AffairsCreditAppeal.tenant_id == _tid(),
            AffairsCreditAppeal.student_id == student.id,
            AffairsCreditAppeal.is_deleted.is_(False),
        ).order_by(AffairsCreditAppeal.id.desc()).limit(100)).all()
        return success({"items": [_cappeal_row(x, student) | {"version": int(x.version or 0)} for x in rows]})


@router.post("/mobile/affairs/second-class/appeals", summary="本人提交第二课堂积分申诉")
def credit_appeal_submit(body: dict = Body(...), user=Depends(get_current_user)):
    from app.models import AffairsCreditAppeal
    from app.services import affairs_activity_service as service
    reason = str(body.get("reason") or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "申诉理由至少5字")
    appeal_type = str(body.get("appealType") or "MISSING").upper()
    activity_id = body.get("activityId")
    with session() as db:
        student = _self_student(db, user)
        duplicate = db.scalars(select(AffairsCreditAppeal).where(
            AffairsCreditAppeal.tenant_id == _tid(),
            AffairsCreditAppeal.student_id == student.id,
            AffairsCreditAppeal.activity_id == (int(activity_id) if str(activity_id or "").isdigit() else None),
            AffairsCreditAppeal.appeal_type == appeal_type,
            AffairsCreditAppeal.status == "SUBMITTED",
            AffairsCreditAppeal.is_deleted.is_(False),
        )).first()
        if duplicate:
            raise AppException("DATA_CONFLICT", "该记录已有待审核申诉")
        sid = int(student.id)
    result = service.submit_credit_appeal(SimpleNamespace(
        studentId=sid,
        activityId=(int(activity_id) if str(activity_id or "").isdigit() else None),
        appealType=appeal_type,
        claimCreditType=str(body.get("claimCreditType") or "SECOND_CLASS"),
        claimValue=body.get("claimValue"),
        reason=reason,
    ), user)
    return success(result, message="积分申诉已提交")
