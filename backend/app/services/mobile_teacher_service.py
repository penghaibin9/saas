"""移动教师聚合安全门面。

原聚合实现保留在 ``_mobile_teacher_service_impl``；本门面统一施加学校教职工
白名单、对象范围和聚合错误可见性，同时保持既有 Router/API 合同。
"""
from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import func, or_, select

from app.core.exceptions import AppException
from app.core.security import MOBILE_STAFF_USER_TYPES
from app.services import _mobile_teacher_service_impl as _impl
from app.services import affairs_leave_service

_LOG = logging.getLogger(__name__)

# 阶段 A 静态合同和运行时均明确复用权威学工请假服务，禁止复制第二份请假事实。
_authoritative_leave_loader = affairs_leave_service.list_leaves


def is_teacher_user(user: dict | None) -> bool:
    u = user or {}
    return bool(u.get("userId")) and (u.get("userType") or "").strip().upper() in MOBILE_STAFF_USER_TYPES


def _require_teacher(user: dict | None):
    """移动教师端统一白名单；空类型、未知类型、学生、家长和平台身份全部拒绝。"""
    u = user or {}
    if not is_teacher_user(u):
        raise AppException("NO_PERMISSION", "该接口仅学校教职工移动端可用", http_status=403)
    return u


def _strict_real_name_is_ambiguous(real_name: str) -> bool:
    """姓名仅作历史兼容：同租户明确重名或查询故障时禁止姓名授权。"""
    name = (real_name or "").strip()
    if not name:
        return True
    try:
        with _impl._session() as db:
            from app.models import User
            rows = db.scalars(select(User.id).where(
                User.tenant_id == _impl._tid(),
                User.real_name == name,
                User.is_deleted.is_(False),
            ).limit(2)).all()
        # 无账号的历史/外聘导师不能据此证明“重名”；只有明确命中两人时判歧义。
        return len(rows) >= 2
    except Exception:  # noqa: BLE001
        _LOG.exception("mobile_teacher_identity_uniqueness_unavailable")
        return True


def resolve_teacher_scope(user: dict) -> dict:
    """复用既有范围解析，但校级审计角色不能被当成业务全校管理员。"""
    u = _require_teacher(user)
    return _impl._original_resolve_teacher_scope(u)


def _parse_class_id(value) -> int | None:
    if value in (None, ""):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "classId 必须为正整数", http_status=400)
    if parsed <= 0:
        raise AppException("VALIDATION_ERROR", "classId 必须为正整数", http_status=400)
    return parsed


def _authorize_requested_class(scope_mode: str, requested: int | None,
                               allowed_class_ids: set[int]) -> int | None:
    """非全校管理员传入的 classId 必须属于本人关系集合。"""
    if scope_mode == "ADMIN_TENANT":
        return requested
    if requested is not None and requested not in allowed_class_ids:
        raise AppException("NO_DATA_SCOPE", "该班级不在你的负责范围内", http_status=403)
    return requested


def my_students(user: dict, class_id=None) -> dict:
    """我的学生：先求 allowed_class_ids，再接受客户端 classId，禁止跨班枚举。"""
    u = _require_teacher(user)
    if not _impl.db_enabled():
        return {"hasData": False, "items": [], "total": 0, "note": "演示模式"}
    scope = resolve_teacher_scope(u)
    requested = _parse_class_id(class_id)
    tid = _impl._tid()
    with _impl._session() as db:
        from app.models import SchoolClass, StudentProfile

        allowed_class_ids: set[int] = set()
        if scope["mode"] != "ADMIN_TENANT":
            numeric_uid = _impl._teacher_numeric_id(u)
            if numeric_uid is None:
                return {"hasData": False, "items": [], "total": 0,
                        "note": "未识别到教师身份，无法匹配班级"}
            allowed_class_ids = set(db.scalars(select(SchoolClass.id).where(
                SchoolClass.tenant_id == tid,
                SchoolClass.is_deleted.is_(False),
                or_(SchoolClass.counselor_id == numeric_uid,
                    SchoolClass.head_teacher_id == numeric_uid),
            )).all())

        _authorize_requested_class(scope["mode"], requested, allowed_class_ids)
        conds = [StudentProfile.tenant_id == tid, StudentProfile.is_deleted.is_(False)]
        if requested is not None:
            conds.append(StudentProfile.class_id == requested)
        elif scope["mode"] != "ADMIN_TENANT":
            if not allowed_class_ids:
                return {"hasData": False, "items": [], "total": 0, "note": "暂无负责班级"}
            conds.append(StudentProfile.class_id.in_(allowed_class_ids))

        total = db.scalar(select(func.count()).select_from(StudentProfile).where(*conds)) or 0
        rows = db.scalars(select(StudentProfile).where(*conds)
                          .order_by(StudentProfile.id.desc()).limit(200)).all()
        class_ids = {row.class_id for row in rows if row.class_id}
        class_map = {}
        if class_ids:
            class_map = {row.id: row.class_name for row in db.scalars(select(SchoolClass).where(
                SchoolClass.tenant_id == tid,
                SchoolClass.is_deleted.is_(False),
                SchoolClass.id.in_(class_ids),
            )).all()}
        items = [{
            "studentId": str(row.id),
            "studentNo": row.student_no,
            "name": row.real_name,
            "className": class_map.get(row.class_id, ""),
            "gender": row.gender or "",
            "stage": row.current_stage,
            "status": row.student_status,
        } for row in rows]
        return {"hasData": bool(items), "items": items, "total": int(total)}


def _error_payload(source: str, exc: Exception) -> dict:
    code = getattr(exc, "code", None) or "METRIC_UNAVAILABLE"
    _LOG.exception("mobile_teacher_aggregate_unavailable source=%s code=%s", source, code)
    return {"source": source, "errorCode": str(code), "available": False}


def _read_metric(source: str, fn, *args, **kwargs) -> tuple[int | None, dict | None]:
    """单个指标故障不拖垮工作台；value=None 且 errorCode 明确，不伪装成业务 0。"""
    try:
        result = fn(*args, **kwargs)
        if not isinstance(result, tuple) or len(result) != 2:
            raise RuntimeError(f"{source} 返回值不符合 (rows, total) 合同")
        return int(result[1] or 0), None
    except Exception as exc:  # noqa: BLE001
        return None, _error_payload(source, exc)


def overview(user: dict) -> dict:
    u = _require_teacher(user)
    if not _impl.db_enabled():
        return {"hasData": False, "note": "演示模式"}
    scope = resolve_teacher_scope(u)
    specs = [
        ("leave", "待审请假", "campus-service", _authoritative_leave_loader,
         (u,), {"status": "PENDING", "page": 1, "page_size": 1}),
        ("grant", "待审资助", "campus-service", _impl.campus_service_service.list_grants,
         (1, 1), {"status": "REVIEWING"}),
        ("report", "待批周报", "internship", _impl.internship_service.list_weekly_reports,
         (1, 1), {"status": "PENDING_REVIEW"}),
        ("checkin", "打卡异常", "internship", _impl.internship_service.list_attendance_exceptions,
         (1, 1), {"status": "PENDING_HANDLE"}),
        ("warning", "学业预警待处理", "academic", _impl.academic_service.list_warnings,
         (1, 1), {"status": "PENDING_HANDLE"}),
        ("proposal", "开题待审", "graduation", _impl.graduation_service.list_proposals,
         (1, 1), {"status": "PENDING_REVIEW"}),
        ("oriExc", "迎新异常", "orientation", _impl.orientation_service.list_exceptions,
         (1, 1), {"status": "OPEN"}),
        ("workorder", "待处理工单", "campus-service", _impl.campus_service_service.list_work_orders,
         (1, 1), {"status": "PENDING_HANDLE"}),
        ("unemployed", "未就业学生", "employment", _impl.employment_service.list_unemployed,
         (1, 1), {}),
    ]
    metrics, errors = [], []
    calculated_at = _impl._iso(datetime.now())
    for key, label, route, fn, args, kwargs in specs:
        value, error = _read_metric(key, fn, *args, **kwargs)
        # 包 13 指标合同：value/available/calculatedAt/scope/errorCode 五件套齐全。
        # scope 必须逐指标带上——同一块工作台，校级管理员和辅导员看到的 12 是完全
        # 不同含义的 12，前端和使用者都需要知道这个数是在多大范围内算出来的。
        metric = {"key": key, "label": label, "value": value, "route": route,
                  "available": error is None, "calculatedAt": calculated_at,
                  "scope": scope["mode"],
                  "errorCode": None if error is None else error["errorCode"]}
        metrics.append(metric)
        if error:
            errors.append(error)
    return {
        "hasData": True,
        "available": not errors,
        "role": u.get("currentRoleCode"),
        "scopeMode": scope["mode"],
        "updatedAt": _impl._iso(datetime.now()),
        "metrics": metrics,
        "pendingTotal": sum(m["value"] for m in metrics if m["value"] is not None and m["key"] != "unemployed"),
        "errors": errors,
    }


def _safe_list(fn, page, ps, **kw):
    try:
        return fn(page, ps, **kw)
    except Exception as exc:  # noqa: BLE001
        raise AppException("METRIC_UNAVAILABLE", "移动工作台数据暂不可用，请稍后重试",
                           http_status=503) from exc


def _total(fn, **kw):
    rows, total = _safe_list(fn, 1, 1, **kw)
    return total


def todos(user: dict) -> dict:
    """待办按来源隔离故障；错误显式返回，不能把异常来源伪装成 0 条。"""
    u = _require_teacher(user)
    if not _impl.db_enabled():
        return {"hasData": False, "filters": [], "list": [], "total": 0,
                "pendingCount": 0, "note": "演示模式"}
    scope = resolve_teacher_scope(u)
    items, errors = [], []

    def add(source, fn, label, module, group, **kw):
        try:
            rows, _ = fn(1, 20, **kw)
        except Exception as exc:  # noqa: BLE001
            errors.append(_error_payload(source, exc))
            return
        for row in rows:
            if not _impl.scope_match_row(scope, student_no=row.get("studentNo"),
                                         class_name=row.get("className"),
                                         advisor_name=row.get("advisorName")):
                continue
            items.append({"id": row.get("id"), "group": group,
                          "title": f"{label}：{row.get('name') or row.get('studentName') or row.get('title', '')}",
                          "student": row.get("name") or row.get("studentName") or "",
                          "module": module, "status": row.get("status") or row.get("statusLabel", ""),
                          "level": "high" if row.get("riskLevel") in ("HIGH", "URGENT") else "normal",
                          "deadline": row.get("deadline") or row.get("dueAt") or ""})

    add("leave", lambda page, ps, **_kw: _authoritative_leave_loader(
        u, status="PENDING", page=page, page_size=ps),
        "待审请假", "student-affairs", "approve")
    add("weeklyReport", _impl.internship_service.list_weekly_reports,
        "待批周报", "internship", "review", status="PENDING_REVIEW")
    add("attendanceException", _impl.internship_service.list_attendance_exceptions,
        "打卡异常", "internship", "risk", status="PENDING_HANDLE")
    add("academicWarning", _impl.academic_service.list_warnings,
        "学业预警", "academic", "risk", status="PENDING_HANDLE")
    add("graduationProposal", _impl.graduation_service.list_proposals,
        "开题待审", "graduation", "review", status="PENDING_REVIEW")
    filters = [{"key": "all", "label": "全部"}, {"key": "approve", "label": "待审批"},
               {"key": "review", "label": "待批阅"}, {"key": "risk", "label": "待处理风险"},
               {"key": "confirm", "label": "待确认"}, {"key": "done", "label": "已处理"}]
    return {"hasData": bool(items), "available": not errors, "filters": filters,
            "list": items[:60], "total": len(items), "pendingCount": len(items),
            "scopeMode": scope["mode"], "errors": errors}


def internship(user: dict, batch_id=None) -> dict:
    """教师实习聚合从 domain 第一层就带 actor，保证“列表可见”与“写操作可处理”同一范围合同。"""
    u = _require_teacher(user)
    if not _impl.db_enabled():
        return {"hasData": False, "weeklyReports": [], "abnormalCheckins": [], "stats": {}}
    scope = resolve_teacher_scope(u)
    source_errors: list[dict] = []

    def _src(source: str, fn, **kw):
        try:
            return fn(1, 50, user=u, **kw)
        except Exception as exc:  # noqa: BLE001
            code = getattr(exc, "code", None) or "SOURCE_UNAVAILABLE"
            _LOG.warning("mobile_teacher_internship_source_unavailable source=%s code=%s",
                         source, code)
            source_errors.append({"source": source, "errorCode": str(code), "available": False})
            return [], 0

    batch_kw = {"batch_id": batch_id} if batch_id else {}
    reports, _ = _src("weeklyReportPending", _impl.internship_service.list_weekly_reports,
                      status="PENDING_REVIEW", **batch_kw)
    overdue, _ = _src("weeklyReportOverdue", _impl.internship_service.list_weekly_reports,
                      status="OVERDUE", **batch_kw)
    excs, _ = _src("attendanceException", _impl.internship_service.list_attendance_exceptions,
                   status="PENDING_HANDLE", **batch_kw)

    seen = {str(r.get("id")) for r in reports}
    for row in overdue:
        if str(row.get("id")) not in seen:
            reports.append(row)
            seen.add(str(row.get("id")))

    # domain 已按同一 actor 收敛；这里再做一次门面级匹配作为纵深防御，不扩大任何范围。
    if scope["mode"] == "SCOPED":
        advisor_map = _impl._advisor_map(
            [int(r.get("internId") or 0) for r in reports]
            + [int(e.get("internId") or e.get("internshipId") or 0) for e in excs]
        )
        reports = [r for r in reports if _impl.scope_match_row(
            scope,
            class_name=r.get("className"),
            advisor_name=advisor_map.get(int(r.get("internId") or 0)),
            student_no=r.get("studentNo"),
        )]
        excs = [e for e in excs if _impl.scope_match_row(
            scope,
            class_name=e.get("className"),
            advisor_name=advisor_map.get(int(e.get("internId") or e.get("internshipId") or 0)),
            student_no=e.get("studentNo"),
        )]

    try:
        stats = _impl.internship_service.get_dashboard_summary()
    except Exception:  # noqa: BLE001
        stats = {"pendingReports": len(reports), "abnormal": len(excs)}
    return {
        "hasData": bool(reports or excs),
        "weeklyReports": reports,
        "abnormalCheckins": excs,
        "stats": stats,
        "scopeMode": scope["mode"],
        "available": not source_errors,
        "errors": source_errors,
    }


def weekly_review(user: dict, report_id: str, action: str, comment: str | None = None,
                  expected_version=None) -> dict:
    """周报写链显式透传 actor + 客户端版本，保留 owner 校验与乐观锁。"""
    u = _require_teacher(user)
    if not _impl.db_enabled():
        raise AppException("VALIDATION_ERROR", "演示模式不支持真实批阅")
    scope = resolve_teacher_scope(u)
    if scope.get("mode") == "SCOPED":
        detail = _impl.internship_service.get_weekly_report_detail(report_id, user=u)
        if not _impl.scope_match_row(scope, class_name=detail.get("className"),
                                     advisor_name=detail.get("advisorName"),
                                     student_no=detail.get("studentNo")):
            allowed = False
            try:
                with _impl._session() as db:
                    from app.models import InternshipRecord, StudentProfile, WeeklyReport
                    w = db.get(WeeklyReport, int(report_id))
                    rec = db.get(InternshipRecord, w.internship_id) if w else None
                    if rec and (rec.advisor_name or "").strip() in scope["advisorNames"]:
                        allowed = True
                    if rec and rec.student_id:
                        stu = db.get(StudentProfile, rec.student_id)
                        if stu is not None and _impl.can_teacher_view_student({}, stu, scope=scope, db=db):
                            allowed = True
            except Exception:  # noqa: BLE001
                allowed = False
            if not allowed:
                raise AppException("NO_PERMISSION", "该周报不在你的负责范围内")
    result = _impl.internship_service.review_weekly_report(
        report_id, action, comment or "", user=u, expected_version=expected_version)
    _impl._audit_write("MOBILE_WEEKLY_REVIEW", f"internship/weekly:{report_id}",
                       {"operator": u.get("realName"), "action": action,
                        "comment": (comment or "")[:200]})
    return result


# 保存原入口（模块重载时不把门面自身保存成 original），再把实现模块引用到安全函数。
if not hasattr(_impl, "_original_resolve_teacher_scope"):
    _impl._original_resolve_teacher_scope = _impl.resolve_teacher_scope
_impl._ADMIN_ROLES = set(_impl._ADMIN_ROLES) - {"SECURITY_AUDITOR"}
_impl.is_teacher_user = is_teacher_user
_impl._require_teacher = _require_teacher
_impl._real_name_is_ambiguous = _strict_real_name_is_ambiguous
_impl.resolve_teacher_scope = resolve_teacher_scope
_impl.my_students = my_students
_impl.overview = overview
_impl.todos = todos
_impl.internship = internship
_impl.weekly_review = weekly_review
_impl._total = _total
_impl._safe_list = _safe_list

# 保持原模块的全部公开/私有属性兼容，既有 Router 和测试无需改 import。
for _name in dir(_impl):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_impl, _name)


def __getattr__(name: str):
    return getattr(_impl, name)


__all__ = [name for name in dir(_impl) if not name.startswith("__")]
