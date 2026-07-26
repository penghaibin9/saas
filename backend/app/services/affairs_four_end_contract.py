"""学工中心四端契约加固层。

本模块不重做任何学工业务状态机，只补齐四端接线层此前没有继承的公共契约：
- 移动端写操作必须携带用户当前看到的 version，禁止包装层查询最新 version 代替；
- 教师移动端复用 PC 同名 permissionCode；
- 点名 STUDENT 范围不得扩大为整班；
- 心理明细审计失败时禁止返回原文；
- 学生请假自视图返回 version/allowedActions；
- 已有床学生不得通过自选入口绕过正式调宿流程；
- 学生端旧 MANUAL 活动签到入口关闭，改走短时签名凭证。

安装时机：api/v1/router.py 在 register_all_routes() 之后调用 install()。
"""
from __future__ import annotations

import json
import sys
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

import jwt
from sqlalchemy import select

from app.core.config import settings
from app.core.exceptions import AppException, no_permission
from app.core.permissions import has_permission
from app.services.db_service import _tid, session

_REQUEST_PATH: ContextVar[str] = ContextVar("affairs_four_end_path", default="")
_REQUEST_METHOD: ContextVar[str] = ContextVar("affairs_four_end_method", default="")
_REQUEST_VERSION: ContextVar[Any] = ContextVar("affairs_four_end_version", default=None)
_REQUEST_BODY: ContextVar[dict] = ContextVar("affairs_four_end_body", default={})

_INSTALLED = False
_ORIGINALS: dict[str, Any] = {}


def request_path() -> str:
    return _REQUEST_PATH.get() or ""


def request_body() -> dict:
    return dict(_REQUEST_BODY.get() or {})


def request_version() -> Any:
    return _REQUEST_VERSION.get()


def _is_affairs_mobile_path(path: str) -> bool:
    return (
        path.startswith("/api/v1/mobile/affairs/")
        or path.startswith("/api/v1/mobile/teacher/affairs")
        or path.startswith("/api/v1/mobile/teacher/talk")
        or path.startswith("/api/v1/mobile/teacher/mental")
    )


def _extract_version(request, body: dict) -> Any:
    value = body.get("version")
    if value is None:
        value = body.get("expectedVersion")
    if value is None:
        raw = request.headers.get("if-match") or request.headers.get("x-expected-version")
        if raw:
            value = raw.strip().strip('"')
    return value


def _patch_request_context() -> None:
    from app.middleware.context import RequestContextMiddleware

    if getattr(RequestContextMiddleware.dispatch, "_affairs_four_end_patched", False):
        return
    original = RequestContextMiddleware.dispatch
    _ORIGINALS["context_dispatch"] = original

    async def dispatch(self, request, call_next):
        path = request.url.path
        method = request.method.upper()
        body: dict = {}
        if _is_affairs_mobile_path(path) and method not in ("GET", "HEAD", "OPTIONS"):
            raw = await request.body()
            if raw:
                try:
                    parsed = json.loads(raw.decode("utf-8"))
                    if isinstance(parsed, dict):
                        body = parsed
                except (UnicodeDecodeError, json.JSONDecodeError):
                    body = {}
            sent = False

            async def receive():
                nonlocal sent
                if sent:
                    return {"type": "http.request", "body": b"", "more_body": False}
                sent = True
                return {"type": "http.request", "body": raw, "more_body": False}

            request._receive = receive

        t_path = _REQUEST_PATH.set(path)
        t_method = _REQUEST_METHOD.set(method)
        t_body = _REQUEST_BODY.set(body)
        t_version = _REQUEST_VERSION.set(_extract_version(request, body))
        try:
            return await original(self, request, call_next)
        finally:
            _REQUEST_VERSION.reset(t_version)
            _REQUEST_BODY.reset(t_body)
            _REQUEST_METHOD.reset(t_method)
            _REQUEST_PATH.reset(t_path)

    dispatch._affairs_four_end_patched = True
    RequestContextMiddleware.dispatch = dispatch


def _patch_optimistic_lock() -> None:
    from app.core import exceptions as exc_mod
    from app.core import optimistic_lock

    original_atomic = optimistic_lock.atomic_claim_version
    original_check = exc_mod.check_version
    _ORIGINALS["atomic_claim_version"] = original_atomic
    _ORIGINALS["check_version"] = original_check

    def atomic_claim_version(db, entity, expected_version):
        path = request_path()
        if _is_affairs_mobile_path(path) and _REQUEST_METHOD.get() not in ("GET", "HEAD", "OPTIONS"):
            expected_version = request_version()
        return original_atomic(db, entity, expected_version)

    def check_version(current_version, expected_version):
        path = request_path()
        if _is_affairs_mobile_path(path) and _REQUEST_METHOD.get() not in ("GET", "HEAD", "OPTIONS"):
            expected_version = request_version()
        return original_check(current_version, expected_version)

    optimistic_lock.atomic_claim_version = atomic_claim_version
    exc_mod.check_version = check_version

    modules = [
        "affairs_leave_service", "affairs_aid_service", "affairs_funding_service",
        "affairs_discipline_service", "affairs_dorm_service", "affairs_risk_service",
        "affairs_mental_service", "affairs_talk_service", "affairs_activity_service",
        "affairs_club_service", "affairs_org_service", "affairs_league_service",
        "affairs_archive_service", "affairs_counselor_service",
    ]
    for name in modules:
        module = __import__(f"app.services.{name}", fromlist=[name])
        if hasattr(module, "atomic_claim_version"):
            module.atomic_claim_version = atomic_claim_version
        if hasattr(module, "check_version"):
            module.check_version = check_version


def _teacher_permissions(path: str, method: str) -> tuple[str, ...]:
    """把教师移动端入口映射到 PC 已冻结的 permissionCode。任一命中即可。"""
    write = method not in ("GET", "HEAD", "OPTIONS")

    if path.startswith("/api/v1/mobile/teacher/talk"):
        return ("studentAffairs.talk.create",) if write else ("studentAffairs.talk.view",)
    if path.startswith("/api/v1/mobile/teacher/mental"):
        return ("studentAffairs.mental.manage",) if write else (
            "studentAffairs.risk.psyDetail.view", "studentAffairs.stats.view",
        )
    if not path.startswith("/api/v1/mobile/teacher/affairs"):
        return ()

    tail = path[len("/api/v1/mobile/teacher/affairs"):]
    if not tail or tail == "/":
        return ("studentAffairs.dashboard.view",)
    if tail.startswith("/family-contacts"):
        return ("studentAffairs.homeSchool.record.create",) if write else (
            "studentAffairs.homeSchool.view",
        )
    if tail.startswith("/leaves"):
        if not write:
            return ("studentAffairs.leave.view",)
        if tail.endswith("/cancel-confirm") or tail.endswith("/proxy-cancel"):
            return ("studentAffairs.leave.cancelLeaveConfirm",)
        if tail.endswith("/overdue-handle"):
            return ("studentAffairs.leave.overdue.handle",)
        if tail.endswith("/extension-approve"):
            return ("studentAffairs.leave.extension.approve",)
        return ("studentAffairs.leave.approve",)
    if tail.startswith("/aid"):
        return (
            ("studentAffairs.aid.approve", "studentAffairs.aid.counselorReview")
            if write else ("studentAffairs.aid.view",)
        )
    if tail.startswith("/funding"):
        return ("studentAffairs.funding.approve",) if write else (
            "studentAffairs.funding.view",
        )
    if tail.startswith("/discipline"):
        return ("studentAffairs.discipline.approve",) if write else (
            "studentAffairs.discipline.view",
        )
    if tail.startswith("/risk"):
        if not write:
            return ("studentAffairs.risk.view",)
        if tail.endswith("/close"):
            return ("studentAffairs.risk.close", "studentAffairs.risk.handle")
        return ("studentAffairs.risk.handle",)
    if tail.startswith("/dorm"):
        if not write:
            return ("studentAffairs.dorm.view",)
        if "/transfers/" in tail:
            return ("studentAffairs.dorm.transfer.approve",)
        if "/exceptions/" in tail:
            return ("studentAffairs.dorm.exception.handle",)
        return ("studentAffairs.dorm.allocation.manage",)
    if tail.startswith("/classes"):
        if not write:
            return ("studentAffairs.class.view",)
        if "/cadres" in tail:
            return ("studentAffairs.class.cadre.manage",)
        return ("studentAffairs.class.create",)
    return ("studentAffairs.dashboard.view",)


def _patch_teacher_permission() -> None:
    from app.services import mobile_teacher_service as tea

    original = tea._require_teacher
    _ORIGINALS["mobile_require_teacher"] = original

    def require_teacher(user):
        u = original(user)
        required = _teacher_permissions(request_path(), _REQUEST_METHOD.get())
        if required and not any(has_permission(u, code) for code in required):
            raise no_permission("当前身份无权执行该学工移动端操作")
        return u

    tea._require_teacher = require_teacher

    from app.services import mobile_affairs_service as aff
    original_card = aff.teacher_affairs
    _ORIGINALS["teacher_affairs"] = original_card

    def teacher_affairs(user):
        if not has_permission(user, "studentAffairs.dashboard.view"):
            raise no_permission("当前身份无权查看学工待办")
        return original_card(user)

    aff.teacher_affairs = teacher_affairs


def _patch_student_scope() -> None:
    from app.core import affairs_security

    original = affairs_security.build_affairs_context
    _ORIGINALS["build_affairs_context"] = original

    def build_affairs_context(user, db=None):
        ctx = original(user, db)
        if (
            ctx.scope_type == "CLASS"
            and ctx.student_ids
            and not ctx.class_ids
            and not ctx.college_ids
        ):
            ctx.scope_type = "STUDENT"
            ctx.is_scope_configured = True
            ctx.scope_source = "SCOPE_TABLE_STUDENT"
        return ctx

    affairs_security.build_affairs_context = build_affairs_context
    for module in list(sys.modules.values()):
        if module is not None and getattr(module, "build_affairs_context", None) is original:
            module.build_affairs_context = build_affairs_context


def _strict_sensitive_view_audit(student_id, reason: str, resource: str) -> None:
    """强敏感详情必须先成功写审计，审计不可用则拒绝返回明文。"""
    from app.services import audit_log

    try:
        audit_log.record(
            "SENSITIVE_VIEW",
            resource,
            detail={
                "domain": "MENTAL",
                "studentId": str(student_id),
                "reason": str(reason)[:200],
            },
            result="SUCCESS",
        )
    except Exception as exc:  # noqa: BLE001
        raise AppException(
            "SERVER_ERROR",
            "敏感信息访问审计暂不可用，已拒绝返回心理明细",
            http_status=503,
        ) from exc


def _patch_mental_audit() -> None:
    from app.services import affairs_mental_service as mental

    _ORIGINALS["mental_sensitive_view_audit"] = mental._sensitive_view_audit
    mental._sensitive_view_audit = _strict_sensitive_view_audit


def _patch_student_views() -> None:
    from app.services import mobile_affairs_service as aff

    original_leave_my = aff.leave_my
    original_aid_my = aff.aid_my
    original_funding_my = aff.funding_my
    original_overview = aff.overview_my
    original_dorm_my = aff.dorm_my
    original_dorm_beds = aff.dorm_beds
    original_self_select = aff.dorm_self_select

    _ORIGINALS.update({
        "leave_my": original_leave_my,
        "aid_my": original_aid_my,
        "funding_my": original_funding_my,
        "overview_my": original_overview,
        "dorm_my": original_dorm_my,
        "dorm_beds": original_dorm_beds,
        "dorm_self_select": original_self_select,
    })

    def leave_my(user):
        data = original_leave_my(user)
        ids = [int(x["leaveId"]) for x in data.get("items", []) if str(x.get("leaveId", "")).isdigit()]
        versions = {}
        if ids:
            from app.models import CsLeave
            with session() as db:
                versions = {
                    int(row.id): int(row.version or 0)
                    for row in db.scalars(select(CsLeave).where(
                        CsLeave.tenant_id == _tid(),
                        CsLeave.id.in_(ids),
                        CsLeave.is_deleted.is_(False),
                    )).all()
                }
        for item in data.get("items", []):
            lid = int(item["leaveId"]) if str(item.get("leaveId", "")).isdigit() else 0
            item["version"] = versions.get(lid, 0)
            actions = []
            if item.get("canResubmit"):
                actions.extend(["EDIT_RETURNED", "RESUBMIT"])
            if item.get("canCancel"):
                actions.append("SUBMIT_CANCEL")
            if item.get("canExtend"):
                actions.append("SUBMIT_EXTENSION")
            item["allowedActions"] = actions
        return data

    def aid_my(user):
        data = original_aid_my(user)
        ids = [int(x["applyId"]) for x in data.get("items", []) if str(x.get("applyId", "")).isdigit()]
        versions = {}
        if ids:
            from app.models import AidApply
            with session() as db:
                versions = {
                    int(row.id): int(row.version or 0)
                    for row in db.scalars(select(AidApply).where(
                        AidApply.tenant_id == _tid(), AidApply.id.in_(ids),
                        AidApply.is_deleted.is_(False),
                    )).all()
                }
        for item in data.get("items", []):
            aid = int(item["applyId"]) if str(item.get("applyId", "")).isdigit() else 0
            item["version"] = versions.get(aid, 0)
            item["canResubmit"] = item.get("status") == "RETURNED"
            item["allowedActions"] = (
                ["EDIT_RETURNED", "RESUBMIT"] if item["canResubmit"] else
                (["SUBMIT_OBJECTION"] if item.get("canObject") else [])
            )
        return data

    def funding_my(user):
        data = original_funding_my(user)
        ids = [
            int(x["applicationId"]) for x in data.get("items", [])
            if str(x.get("applicationId", "")).isdigit()
        ]
        versions = {}
        if ids:
            from app.models import FundingApplication
            with session() as db:
                versions = {
                    int(row.id): int(row.version or 0)
                    for row in db.scalars(select(FundingApplication).where(
                        FundingApplication.tenant_id == _tid(),
                        FundingApplication.id.in_(ids),
                        FundingApplication.is_deleted.is_(False),
                    )).all()
                }
        for item in data.get("items", []):
            app_id = int(item["applicationId"]) if str(item.get("applicationId", "")).isdigit() else 0
            item["version"] = versions.get(app_id, 0)
            item["canResubmit"] = item.get("status") == "RETURNED"
            item["allowedActions"] = (
                ["EDIT_RETURNED", "RESUBMIT"] if item["canResubmit"] else
                (["SUBMIT_APPEAL"] if item.get("canAppeal") else [])
            )
        return data

    def overview_my(user):
        data = original_overview(user)
        data.pop("riskOpen", None)
        data["careActionCount"] = 0
        return data

    def dorm_my(user):
        data = original_dorm_my(user)
        data["canSelfSelect"] = bool(data.get("selfSelectEnabled")) and not bool(data.get("hasBed"))
        data["canRequestTransfer"] = bool(data.get("hasBed"))
        if data.get("hasBed") and data.get("selfSelectEnabled"):
            data["studentNotice"] = "你已有床位，如需调整请提交调宿申请，不能直接重新选床。"
        return data

    def dorm_beds(user, room_id):
        data = original_dorm_beds(user, room_id)
        for item in data.get("items", []):
            item.pop("studentId", None)
            item.pop("occupantName", None)
        return data

    def dorm_self_select(user, bed_id):
        from app.models import DormBed
        from app.services.mobile_student_service import resolve_student
        with session() as db:
            stu = resolve_student(db, user)
            if not stu:
                raise no_permission("尚未建立你的学生档案")
            occupied = db.scalars(select(DormBed).where(
                DormBed.tenant_id == _tid(),
                DormBed.student_id == int(stu.id),
                DormBed.status == "OCCUPIED",
                DormBed.is_deleted.is_(False),
            )).first()
            if occupied:
                raise AppException(
                    "DATA_CONFLICT",
                    "你已有床位，调整床位必须提交调宿申请并完成辅导员、宿管审批",
                )
        return original_self_select(user, bed_id)

    aff.leave_my = leave_my
    aff.aid_my = aid_my
    aff.funding_my = funding_my
    aff.overview_my = overview_my
    aff.dorm_my = dorm_my
    aff.dorm_beds = dorm_beds
    aff.dorm_self_select = dorm_self_select


def _patch_student_dorm_scope() -> None:
    """允许学生在开放自选/调宿流程中读取房源，写命令仍校验本人、性别和空床。"""
    from app.services import affairs_dorm_service as dorm

    original = dorm._dorm_scope_building_ids
    _ORIGINALS["dorm_scope_building_ids"] = original

    def dorm_scope_building_ids(db, user):
        if (user or {}).get("userType", "").upper() == "STUDENT":
            return None
        return original(db, user)

    dorm._dorm_scope_building_ids = dorm_scope_building_ids


def _patch_insecure_activity_checkin() -> None:
    from app.services import affairs_activity_service as activity

    original = activity.checkin
    _ORIGINALS["activity_checkin"] = original

    def checkin(activity_id, user, method="MANUAL"):
        path = request_path()
        if (
            path.startswith("/api/v1/mobile/affairs/activities/")
            and path.endswith("/checkin")
            and str(method or "MANUAL").upper() == "MANUAL"
        ):
            raise AppException(
                "VALIDATION_ERROR",
                "学生手工签到入口已停用，请扫描老师现场生成的动态签到码",
            )
        return original(activity_id, user, method)

    activity.checkin = checkin


def original_activity_checkin() -> Callable:
    return _ORIGINALS.get("activity_checkin")


def issue_activity_token(activity_id: int, user: dict) -> dict:
    from app.models import AffairsActivity
    with session() as db:
        activity = db.get(AffairsActivity, int(activity_id))
        if not activity or activity.is_deleted or activity.tenant_id != _tid():
            raise AppException("DATA_NOT_FOUND", "活动不存在")
        if activity.status != "ONGOING":
            raise AppException("DATA_CONFLICT", "只有进行中的活动才能生成签到码")
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=5)
    import uuid
    payload = {
        "typ": "AFFAIRS_ACTIVITY_CHECKIN",
        "tenantId": str(_tid()),
        "activityId": str(activity_id),
        "nonce": uuid.uuid4().hex,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "issuerUserId": str((user or {}).get("userId") or ""),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return {
        "activityId": str(activity_id),
        "token": token,
        "expiresAt": exp.isoformat(),
        "validSeconds": 300,
    }


def secure_activity_checkin(activity_id: int, token: str, user: dict) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise AppException("DATA_CONFLICT", "签到码已过期，请重新扫码") from exc
    except jwt.PyJWTError as exc:
        raise AppException("VALIDATION_ERROR", "签到码无效") from exc
    if payload.get("typ") != "AFFAIRS_ACTIVITY_CHECKIN":
        raise AppException("VALIDATION_ERROR", "签到码类型不正确")
    if str(payload.get("tenantId") or "") != str(_tid()):
        raise no_permission("签到码不属于当前学校")
    if str(payload.get("activityId") or "") != str(activity_id):
        raise AppException("VALIDATION_ERROR", "签到码与活动不匹配")
    original = original_activity_checkin()
    if original is None:
        raise AppException("SERVER_ERROR", "签到服务尚未初始化", http_status=503)
    return original(activity_id, user, "QR")


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return
    _patch_request_context()
    _patch_optimistic_lock()
    _patch_teacher_permission()
    _patch_student_scope()
    _patch_mental_audit()
    _patch_student_dorm_scope()
    _patch_student_views()
    _patch_insecure_activity_checkin()
    _INSTALLED = True
