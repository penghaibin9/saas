"""学工异议/申诉四端移动接口。"""
from __future__ import annotations

from types import SimpleNamespace

from fastapi import APIRouter, Body, Depends, Path, Query
from sqlalchemy import func, select

from app.core.exceptions import AppException, no_permission
from app.core.permissions import has_permission
from app.core.response import success
from app.core.security import get_current_user
from app.services.db_service import _tid, session

router = APIRouter(tags=["学工中心·异议申诉"])

_KINDS = {
    "AID_OBJECTION": {
        "view": ("studentAffairs.aid.view",),
        "review": ("studentAffairs.aid.approve",),
        "model": "AidObjection", "id_key": "objectionId",
    },
    "FUNDING_APPEAL": {
        "view": ("studentAffairs.funding.view",),
        "review": ("studentAffairs.funding.publicity.manage",),
        "model": "FundingAppeal", "id_key": "appealId",
    },
    "DISCIPLINE_APPEAL": {
        "view": ("studentAffairs.discipline.view",),
        "review": ("studentAffairs.discipline.appeal.review",),
        "model": "DisciplineAppeal", "id_key": "appealId",
    },
    "SECOND_CLASS_APPEAL": {
        "view": ("studentAffairs.activity.view",),
        "review": ("studentAffairs.activity.confirm",),
        "model": "AffairsCreditAppeal", "id_key": "appealId",
    },
}
_DISC_LABELS = {
    "WARNING": "警告", "SERIOUS_WARNING": "严重警告", "DEMERIT": "记过",
    "PROBATION": "留校察看", "EXPEL": "开除学籍",
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
    ids = {
        int(item.get(spec["id_key"]))
        for item in items
        if str(item.get(spec["id_key"]) or "").isdigit()
    }
    if not ids:
        return {}
    model = getattr(models, spec["model"])
    with session() as db:
        result = {
            int(row.id): int(row.version or 0)
            for row in db.scalars(select(model).where(
                model.tenant_id == _tid(), model.id.in_(ids), model.is_deleted.is_(False),
            )).all()
        }
    missing = ids - set(result)
    if missing:
        raise AppException(
            "DATA_INCONSISTENT",
            "异议/申诉版本信息不完整，请刷新后重试",
            http_status=503,
        )
    return result


def _attach_discipline_types(items: list[dict]) -> None:
    from app.models import DisciplineCase
    case_ids = {
        int(item.get("caseId")) for item in items
        if str(item.get("caseId") or "").isdigit()
    }
    if not case_ids:
        return
    with session() as db:
        cases = db.scalars(select(DisciplineCase).where(
            DisciplineCase.tenant_id == _tid(), DisciplineCase.id.in_(case_ids),
            DisciplineCase.is_deleted.is_(False),
        )).all()
    case_map = {int(row.id): row.disc_type for row in cases}
    for item in items:
        raw = item.get("caseId")
        disc_type = case_map.get(int(raw)) if str(raw or "").isdigit() else None
        if not disc_type:
            raise AppException("DATA_INCONSISTENT", "申诉关联的原处分不存在", http_status=503)
        item["discType"] = disc_type
        item["discTypeLabel"] = _DISC_LABELS.get(disc_type, disc_type)


@router.get("/mobile/teacher/affairs/appeals/{kind}", summary="教师异议/申诉待处理列表")
def appeal_pending(
    kind: str = Path(...),
    page: int = Query(1, ge=1),
    pageSize: int = Query(50, ge=1, le=100),
    user=Depends(get_current_user),
):
    key, spec = _kind(kind)
    # 待处理入口不是普通台账查看，必须持有真实复核动作权限。
    _require_any(user, spec["review"])
    if key == "AID_OBJECTION":
        from app.services import affairs_aid_service as service
        items, total = service.list_objections(user, status="SUBMITTED", page=page, page_size=pageSize)
    elif key == "FUNDING_APPEAL":
        from app.services import affairs_funding_service as service
        items, total = service.list_appeals(user, status="SUBMITTED", page=page, page_size=pageSize)
    elif key == "DISCIPLINE_APPEAL":
        from app.services import affairs_discipline_service as service
        items, total = service.list_appeals(user, status="SUBMITTED", page=page, page_size=pageSize)
        _attach_discipline_types(items)
    else:
        from app.services import affairs_activity_service as service
        items, total, _counts = service.list_credit_appeals(user, status="SUBMITTED", page=page, page_size=pageSize)
    versions = _versions(key, items)
    for item in items:
        raw = item.get(spec["id_key"])
        if not str(raw or "").isdigit():
            raise AppException("DATA_INCONSISTENT", "异议/申诉编号缺失", http_status=503)
        item["version"] = versions[int(raw)]
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
            revisedDiscType=str(body.get("revisedDiscType") or "").upper(),
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
def credit_appeals_my(
    page: int = Query(1, ge=1),
    pageSize: int = Query(20, ge=1, le=100),
    user=Depends(get_current_user),
):
    from app.models import AffairsCreditAppeal
    from app.services.affairs_activity_service import _cappeal_row
    with session() as db:
        student = _self_student(db, user)
        conds = [
            AffairsCreditAppeal.tenant_id == _tid(),
            AffairsCreditAppeal.student_id == int(student.id),
            AffairsCreditAppeal.is_deleted.is_(False),
        ]
        total = int(db.scalar(select(func.count()).select_from(AffairsCreditAppeal).where(*conds)) or 0)
        rows = db.scalars(select(AffairsCreditAppeal).where(*conds)
                          .order_by(AffairsCreditAppeal.id.desc())
                          .offset((page - 1) * pageSize).limit(pageSize)).all()
        items = [_cappeal_row(x, student) | {"version": int(x.version or 0)} for x in rows]
        return success({"items": items, "total": total, "page": page, "pageSize": pageSize})


@router.post("/mobile/affairs/second-class/appeals", summary="本人提交第二课堂积分申诉")
def credit_appeal_submit(body: dict = Body(...), user=Depends(get_current_user)):
    from app.services import affairs_activity_service as service
    reason = str(body.get("reason") or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "申诉理由至少5字")
    appeal_type = str(body.get("appealType") or "MISSING").upper()
    activity_id = body.get("activityId")
    with session() as db:
        student = _self_student(db, user)
        sid = int(student.id)
    # 重复判断、学生行锁、活动引用与数值校验由同事务核心实现统一完成。
    result = service.submit_credit_appeal(SimpleNamespace(
        studentId=sid,
        activityId=(int(activity_id) if str(activity_id or "").isdigit() else None),
        appealType=appeal_type,
        claimCreditType=str(body.get("claimCreditType") or "SECOND_CLASS"),
        claimValue=body.get("claimValue"),
        reason=reason,
    ), user)
    return success(result, message="积分申诉已提交")
