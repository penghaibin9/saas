"""A4 / P0-06 数据驾驶舱权威服务。

- context 只读真实租户/品牌/登录角色/StudentAffairsSecurityContext；
- 校级 BI 与现有 /stats/* 一致，仅 TENANT_ALL 可读，禁止把全校数字伪装成本班/本院数字；
- 专题报表当前工作副本持久化 MySQL，发布生成 append-only 快照；
- 发布/撤回/作废/编辑全部版本锁 + 同事务安全审计；
- 未接正式文件任务的导出能力 fail-closed，不再返回浏览器假 taskId。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, or_, select

from app.core.affairs_security import build_affairs_context, no_data_scope
from app.core.exceptions import AppException, not_found
from app.core.permissions import enforce_permission, has_permission
from app.models.audit import SecurityAuditLog
from app.models.data_center import DataCenterReport, DataCenterReportVersion
from app.models.org import College, Major, SchoolClass
from app.models.student import StudentProfile
from app.models.tenant import Tenant, TenantBrandConfig
from app.services import mock_audit_service as audit
from app.services import stats_service
from app.services.db_service import _iso, _tid, session

_REPORT_STATUS = {
    "DRAFT": "草稿",
    "PUBLISHED": "已发布",
    "WITHDRAWN": "已撤回",
    "VOIDED": "已作废",
}
_CATEGORY = {
    "EMPLOYMENT": "就业质量",
    "INTERNSHIP": "实习过程",
    "ACADEMIC": "教学质量",
    "SERVICE": "校园服务",
    "RISK": "风险治理",
}
_CYCLE = {"MONTHLY": "月度", "QUARTERLY": "季度", "ONCE": "一次性"}
_CALIBER = {"REGISTERED": "在册口径", "NATURAL": "自然口径"}
_ROLE_LABELS = {
    "SCHOOL_ADMIN": "学校管理员",
    "LEADER": "校级领导",
    "SCHOOL_LEADER": "校级领导",
    "COLLEGE_ADMIN": "学院管理员",
    "ACADEMIC_ADMIN": "教务管理员",
    "EMPLOYMENT_TEACHER": "就业老师",
    "STUDENT_AFFAIRS_ADMIN": "学工管理员",
    "STUDENT_AFFAIRS": "学工老师",
    "SYS_ADMIN": "系统管理员",
    "SECURITY_AUDITOR": "安全审计员",
    "PLATFORM_SUPER_ADMIN": "平台超级管理员",
}


def _permission_action(user: dict, code: str, *, scope_ok: bool, hidden: bool = False,
                       reason: str = "") -> dict:
    allowed = bool(scope_ok and has_permission(user, code))
    if not scope_ok:
        reason = reason or "数据驾驶舱校级指标仅对全校数据范围角色开放"
    elif not allowed:
        reason = reason or f"当前角色未获得 {code} 权限"
    return {"visible": not hidden, "allowed": allowed, "reason": "" if allowed else reason}


def _scope_payload(db, user: dict) -> tuple[dict, object]:
    ctx = build_affairs_context(user, db)
    if ctx.scope_type == "TENANT_ALL":
        name = "全校"
    elif ctx.scope_type == "COLLEGE":
        names = db.scalars(select(College.college_name).where(
            College.tenant_id == _tid(), College.id.in_(ctx.college_ids),
            College.is_deleted.is_(False))).all() if ctx.college_ids else []
        name = "、".join(names) or "未配置学院范围"
    elif ctx.scope_type == "CLASS":
        ids = ctx.allowed_class_ids(db) or set()
        names = db.scalars(select(SchoolClass.class_name).where(
            SchoolClass.tenant_id == _tid(), SchoolClass.id.in_(ids),
            SchoolClass.is_deleted.is_(False))).all() if ids else []
        name = "、".join(names[:5]) + (f" 等 {len(names)} 个班" if len(names) > 5 else "")
        name = name or "未配置班级范围"
    elif ctx.scope_type == "STUDENT":
        count = len(ctx.student_ids | ctx.psychology_student_ids)
        name = f"指定学生（{count} 人）" if count else "未配置学生范围"
    elif ctx.scope_type == "DORM_BUILDING":
        name = f"宿舍楼范围（{len(ctx.dorm_building_ids)} 栋）"
    elif ctx.scope_type == "SELF":
        name = "本人"
    else:
        name = "未配置数据范围"
    return {
        "scopeCode": ctx.scope_type,
        "scopeType": ctx.scope_type,
        "scopeName": name,
        "scopeSource": ctx.scope_source,
        "configured": bool(ctx.is_scope_configured),
    }, ctx


def _filter_options(db) -> dict:
    colleges = db.scalars(select(College).where(
        College.tenant_id == _tid(), College.is_deleted.is_(False), College.status == "ACTIVE")
        .order_by(College.college_name)).all()
    majors = db.scalars(select(Major).where(
        Major.tenant_id == _tid(), Major.is_deleted.is_(False), Major.status == "ACTIVE")
        .order_by(Major.major_name)).all()
    classes = db.scalars(select(SchoolClass).where(
        SchoolClass.tenant_id == _tid(), SchoolClass.is_deleted.is_(False), SchoolClass.status == "ACTIVE")
        .order_by(SchoolClass.class_name)).all()
    grades = sorted({str(x) for x in db.scalars(select(StudentProfile.grade).where(
        StudentProfile.tenant_id == _tid(), StudentProfile.is_deleted.is_(False))).all() if x})
    return {
        "colleges": [{"value": str(x.id), "label": x.college_name} for x in colleges],
        "majors": [{"value": str(x.id), "label": x.major_name, "collegeId": str(x.college_id or "")} for x in majors],
        "classes": [{"value": str(x.id), "label": x.class_name, "majorId": str(x.major_id or "")} for x in classes],
        "grades": [{"value": x, "label": f"{x} 级"} for x in grades],
        "timeRanges": [
            {"value": "THIS_TERM", "label": "本学期"},
            {"value": "THIS_YEAR", "label": "本学年"},
            {"value": "LAST_6M", "label": "近 6 个月"},
        ],
        "calibers": [{"value": k, "label": v} for k, v in _CALIBER.items()],
        "rankLevels": [
            {"value": "COLLEGE", "label": "按学院"},
            {"value": "MAJOR", "label": "按专业"},
            {"value": "CLASS", "label": "按班级"},
        ],
        "reportCategories": [{"value": k, "label": v} for k, v in _CATEGORY.items()],
        "riskSources": [
            {"value": "INTERNSHIP", "label": "岗位实习"},
            {"value": "ACADEMIC", "label": "学业过程"},
            {"value": "SERVICE", "label": "在校服务"},
            {"value": "GRADUATION", "label": "毕业设计"},
            {"value": "EMPLOYMENT", "label": "就业去向"},
            {"value": "ORIENTATION", "label": "迎新报到"},
        ],
    }


def get_context(user: dict) -> dict:
    with session() as db:
        tenant = db.get(Tenant, _tid())
        brand = db.scalars(select(TenantBrandConfig).where(
            TenantBrandConfig.tenant_id == _tid(), TenantBrandConfig.is_deleted.is_(False))).first()
        scope, security_ctx = _scope_payload(db, user)
        tenant_all = security_ctx.scope_type == "TENANT_ALL"
        role = str(user.get("currentRoleCode") or "")
        school_name = tenant.school_name if tenant else str(user.get("tenantName") or "学校")
        actions = {
            "viewDashboard": _permission_action(user, "dataCenter.dashboard.view", scope_ok=tenant_all),
            "viewLifecycle": _permission_action(user, "dataCenter.lifecycle.view", scope_ok=tenant_all),
            "viewRankings": _permission_action(user, "dataCenter.ranking.view", scope_ok=tenant_all),
            "viewRisk": _permission_action(user, "dataCenter.risk.view", scope_ok=tenant_all),
            "viewReports": _permission_action(user, "dataCenter.report.view", scope_ok=tenant_all),
            "createReport": _permission_action(user, "dataCenter.report.manage", scope_ok=tenant_all),
            "editReport": _permission_action(user, "dataCenter.report.manage", scope_ok=tenant_all),
            "publishReport": _permission_action(user, "dataCenter.report.publish", scope_ok=tenant_all),
            "withdrawReport": _permission_action(user, "dataCenter.report.publish", scope_ok=tenant_all),
            "voidReport": _permission_action(user, "dataCenter.report.void", scope_ok=tenant_all),
            "viewAuditLog": _permission_action(user, "dataCenter.audit.view", scope_ok=tenant_all),
            # A4 当前不伪造文件任务；正式导出任务接入前入口直接隐藏。
            "exportOverview": _permission_action(user, "dataCenter.export", scope_ok=False, hidden=True,
                                                   reason="驾驶舱导出尚未接入正式文件任务链"),
            "exportLifecycle": _permission_action(user, "dataCenter.export", scope_ok=False, hidden=True,
                                                    reason="驾驶舱导出尚未接入正式文件任务链"),
            "exportRanking": _permission_action(user, "dataCenter.export", scope_ok=False, hidden=True,
                                                  reason="驾驶舱导出尚未接入正式文件任务链"),
            "exportRisk": _permission_action(user, "dataCenter.export", scope_ok=False, hidden=True,
                                               reason="驾驶舱导出尚未接入正式文件任务链"),
            "exportReport": _permission_action(user, "dataCenter.export", scope_ok=False, hidden=True,
                                                 reason="驾驶舱导出尚未接入正式文件任务链"),
            "drilldownStudents": _permission_action(user, "dataCenter.drilldown.view", scope_ok=tenant_all),
            "batchRemind": _permission_action(user, "dataCenter.risk.remind", scope_ok=False, hidden=True,
                                                reason="驾驶舱批量提醒尚未接入正式消息任务链"),
        }
        return {
            "tenantBrandConfig": {
                "tenantId": str(_tid()),
                "schoolName": school_name,
                "platformDisplayName": (brand.platform_name if brand else None) or "高校学生全生命周期管理平台",
                "schoolLogo": "",
                "schoolBadge": "",
                "brandColor": (brand.primary_color if brand else None) or "#2563eb",
                "watermarkText": (brand.watermark_text if brand else None) or f"{school_name} · 内部数据",
            },
            "currentRole": {
                "userId": str(user.get("userId") or ""),
                "userName": user.get("realName") or user.get("loginName") or "",
                "roleCode": role,
                "roleName": _ROLE_LABELS.get(role, role or "未识别角色"),
            },
            "dataScope": scope,
            "visibleMetricKeys": [
                "studentTotal", "orientationRate", "serviceRate", "academicWarning",
                "internshipOnboardRate", "graduationPassRate", "employmentRate", "riskPending",
            ] if tenant_all else [],
            "permissionActions": actions,
            "statusOptions": {
                "reportStatus": [{"value": k, "label": v} for k, v in _REPORT_STATUS.items()],
                "reportCycles": [{"value": k, "label": v} for k, v in _CYCLE.items()],
                "riskLevel": [{"value": x, "label": y} for x, y in
                              (("HIGH", "高风险"), ("MEDIUM", "中风险"), ("LOW", "低风险"))],
                "lifecycleStages": [
                    {"value": "ORIENTATION", "label": "迎新报到"},
                    {"value": "SERVICE", "label": "在校服务"},
                    {"value": "ACADEMIC", "label": "学业过程"},
                    {"value": "INTERNSHIP", "label": "岗位实习"},
                    {"value": "GRADUATION", "label": "毕业设计"},
                    {"value": "EMPLOYMENT", "label": "就业去向"},
                ],
            },
            "filterOptions": _filter_options(db) if tenant_all else {
                "colleges": [], "majors": [], "classes": [], "grades": [],
                "timeRanges": [], "calibers": [], "rankLevels": [],
                "reportCategories": [], "riskSources": [],
            },
            "exportOptions": {
                "scopes": [], "purposes": [],
                "policyNote": "驾驶舱导出尚未接入正式文件任务链；系统不会返回假任务或假文件。",
            },
        }


def _require_bi_scope(db, user: dict) -> dict:
    scope, ctx = _scope_payload(db, user)
    if ctx.scope_type != "TENANT_ALL":
        raise no_data_scope("数据驾驶舱校级指标仅对全校数据范围角色开放")
    return scope


def _require_report_read(db, user: dict) -> dict:
    scope = _require_bi_scope(db, user)
    enforce_permission(user, "dataCenter.report.view")
    return scope


def _require_report_manage(db, user: dict, code: str) -> dict:
    scope = _require_bi_scope(db, user)
    enforce_permission(user, code)
    return scope


def _report(db, report_id, *, lock: bool = False) -> DataCenterReport:
    try:
        rid = int(report_id)
    except (TypeError, ValueError):
        raise not_found("专题报表不存在")
    stmt = select(DataCenterReport).where(
        DataCenterReport.id == rid,
        DataCenterReport.tenant_id == _tid(),
        DataCenterReport.is_deleted.is_(False),
    )
    if lock:
        stmt = stmt.with_for_update()
    row = db.scalars(stmt).first()
    if row is None:
        raise not_found("专题报表不存在")
    return row


def _check_version(row: DataCenterReport, expected) -> int:
    if expected is None:
        raise AppException("VALIDATION_ERROR", "version 必填，请刷新后重试")
    try:
        value = int(expected)
    except (TypeError, ValueError):
        raise AppException("VALIDATION_ERROR", "version 必须是整数")
    if value != int(row.version or 0):
        raise AppException("DATA_VERSION_CONFLICT", "报表已被他人修改，请刷新后重试", http_status=409)
    return value


def _report_row(row: DataCenterReport) -> dict:
    return {
        "id": str(row.id), "reportNo": row.report_no, "name": row.name,
        "category": row.category, "categoryLabel": _CATEGORY.get(row.category, row.category),
        "cycle": row.cycle, "cycleLabel": _CYCLE.get(row.cycle, row.cycle),
        "scopeName": row.scope_name or "全校", "description": row.description or "",
        "caliber": row.caliber_code, "caliberLabel": _CALIBER.get(row.caliber_code, row.caliber_code),
        "ownerName": row.owner_name or "", "status": row.status,
        "statusLabel": _REPORT_STATUS.get(row.status, row.status),
        "statusTone": {"DRAFT": "neutral", "PUBLISHED": "success", "WITHDRAWN": "warning", "VOIDED": "danger"}.get(row.status, "neutral"),
        "publishedVersion": row.published_version_no,
        "createdAt": _iso(row.created_at), "updatedAt": _iso(row.updated_at),
        "version": int(row.version or 0),
    }


def list_reports(user: dict, *, page: int = 1, page_size: int = 20, keyword: str | None = None,
                 category: str | None = None, status: str | None = None) -> tuple[list[dict], int]:
    with session() as db:
        _require_report_read(db, user)
        cond = [DataCenterReport.tenant_id == _tid(), DataCenterReport.is_deleted.is_(False)]
        if keyword and keyword.strip():
            text = f"%{keyword.strip()}%"
            cond.append(or_(DataCenterReport.name.like(text), DataCenterReport.report_no.like(text)))
        if category:
            cond.append(DataCenterReport.category == category)
        if status:
            cond.append(DataCenterReport.status == status)
        total = int(db.scalar(select(func.count()).select_from(DataCenterReport).where(*cond)) or 0)
        rows = db.scalars(select(DataCenterReport).where(*cond).order_by(
            DataCenterReport.updated_at.desc(), DataCenterReport.id.desc())
            .offset((max(1, page) - 1) * page_size).limit(page_size)).all()
        return [_report_row(x) for x in rows], total


def _version_row(db, report_id: int, version_no: int | None):
    if not version_no:
        return None
    return db.scalars(select(DataCenterReportVersion).where(
        DataCenterReportVersion.tenant_id == _tid(),
        DataCenterReportVersion.report_id == report_id,
        DataCenterReportVersion.version_no == version_no,
    )).first()


def get_report_detail(user: dict, report_id) -> dict:
    with session() as db:
        scope = _require_report_read(db, user)
        row = _report(db, report_id)
        published = _version_row(db, row.id, row.published_version_no)
        # 只有“当前已发布”状态读取冻结快照；撤回/草稿只展示工作副本，不伪装成仍发布。
        metrics = list(published.metrics_json or []) if published and row.status == "PUBLISHED" else []
        trend = published.trend_json if published and row.status == "PUBLISHED" else None
        meta = {
            "asOf": _iso(published.as_of) if published and row.status == "PUBLISHED" else None,
            "caliber": published.caliber_code if published and row.status == "PUBLISHED" else row.caliber_code,
            "caliberLabel": _CALIBER.get(published.caliber_code if published and row.status == "PUBLISHED" else row.caliber_code),
            "scope": published.scope_json if published and row.status == "PUBLISHED" else scope,
            "source": list(published.source_json or []) if published and row.status == "PUBLISHED" else [],
            "qualityFlags": list(published.quality_flags_json or []) if published and row.status == "PUBLISHED" else [
                {"code": "NOT_PUBLISHED", "severity": "INFO", "message": "当前工作副本尚未发布，不展示冻结指标值"}
            ],
        }
        out = _report_row(row)
        out.update({
            "metrics": metrics, "trend": trend, "meta": meta,
            "config": {
                "reportNo": row.report_no, "cycle": row.cycle,
                "cycleLabel": _CYCLE.get(row.cycle, row.cycle),
                "caliber": row.caliber_code, "caliberLabel": _CALIBER.get(row.caliber_code, row.caliber_code),
                "scopeName": row.scope_name or "全校", "ownerName": row.owner_name or "",
                "createdAt": _iso(row.created_at), "updatedAt": _iso(row.updated_at),
                "shareScope": "当前租户具备数据驾驶舱访问权限的校级角色",
                "version": int(row.version or 0),
            },
            "voidInfo": ({"reason": row.void_reason or "", "by": row.voided_by_name or "", "time": _iso(row.voided_at)}
                         if row.status == "VOIDED" else None),
        })
        return out


def _validate_payload(body: dict, *, partial: bool = False) -> dict:
    values = {}
    if not partial or "name" in body:
        name = str(body.get("name") or "").strip()
        if len(name) < 4 or len(name) > 200:
            raise AppException("VALIDATION_ERROR", "报表名称需 4-200 字")
        values["name"] = name
    if not partial or "category" in body:
        category = str(body.get("category") or "ACADEMIC").upper()
        if category not in _CATEGORY:
            raise AppException("VALIDATION_ERROR", "报表分类非法")
        values["category"] = category
    if not partial or "cycle" in body:
        cycle = str(body.get("cycle") or "MONTHLY").upper()
        if cycle not in _CYCLE:
            raise AppException("VALIDATION_ERROR", "统计周期非法")
        values["cycle"] = cycle
    if not partial or "caliber" in body or "caliberCode" in body:
        caliber = str(body.get("caliber") or body.get("caliberCode") or "REGISTERED").upper()
        if caliber not in _CALIBER:
            raise AppException("VALIDATION_ERROR", "统计口径非法")
        values["caliber_code"] = caliber
    if "scopeName" in body or not partial:
        values["scope_name"] = str(body.get("scopeName") or "全校").strip()[:300] or "全校"
    if "description" in body or not partial:
        values["description"] = str(body.get("description") or "").strip()[:5000] or None
    if "query" in body:
        values["query_json"] = body.get("query") if isinstance(body.get("query"), dict) else {}
    if "layout" in body:
        values["layout_json"] = body.get("layout") if isinstance(body.get("layout"), dict) else {}
    return values


def create_report(user: dict, body: dict) -> dict:
    values = _validate_payload(body)
    with session() as db:
        _require_report_manage(db, user, "dataCenter.report.manage")
        row = DataCenterReport(
            tenant_id=_tid(), report_no=f"DC-{datetime.utcnow():%Y%m%d}-{uuid.uuid4().hex[:8].upper()}",
            status="DRAFT", owner_id=str(user.get("userId") or ""),
            owner_name=user.get("realName") or user.get("loginName") or "", **values,
        )
        db.add(row); db.flush()
        audit.record_critical(
            "DATA_CENTER_REPORT_CREATE", target_type="data_center_report", target_id=str(row.id),
            detail={"reportNo": row.report_no, "name": row.name, "version": int(row.version or 0)}, db=db)
        db.commit(); db.refresh(row)
        return _report_row(row)


def update_report(user: dict, report_id, body: dict) -> dict:
    values = _validate_payload(body, partial=True)
    with session() as db:
        _require_report_manage(db, user, "dataCenter.report.manage")
        row = _report(db, report_id, lock=True)
        _check_version(row, body.get("version"))
        if row.status not in {"DRAFT", "WITHDRAWN"}:
            raise AppException("DATA_CONFLICT", "已发布报表需先撤回后才能编辑")
        if row.status == "VOIDED":
            raise AppException("DATA_CONFLICT", "已作废报表不可编辑")
        for key, value in values.items():
            setattr(row, key, value)
        row.version = int(row.version or 0) + 1
        audit.record_critical(
            "DATA_CENTER_REPORT_UPDATE", target_type="data_center_report", target_id=str(row.id),
            detail={"reportNo": row.report_no, "fields": sorted(values), "version": row.version}, db=db)
        db.commit(); db.refresh(row)
        return _report_row(row)


def _snapshot_metrics(caliber: str) -> tuple[list[dict], dict | None, list[dict], list[dict]]:
    overview = stats_service.get_overview(caliber)
    metrics = []
    sources = []
    for item in overview.get("metrics") or []:
        source = str(item.get("sourceModule") or "跨域统计")
        if source not in sources:
            sources.append(source)
        metrics.append({
            "id": item.get("key"), "key": item.get("key"), "name": item.get("label"),
            "value": item.get("value"), "unit": item.get("unit") or "",
            "mom": "—", "yoy": "—", "momQuality": "neutral", "yoyQuality": "neutral",
            "caliberLabel": _CALIBER.get(caliber, caliber), "source": source,
            "description": item.get("description") or "",
        })
    quality = [{
        "code": "TREND_SERIES_NOT_CONFIGURED", "severity": "INFO",
        "message": "当前报表尚未配置历史统计快照序列；趋势图不以 0 或演示数据填充。",
    }]
    return metrics, None, [{"module": x, "mode": "REALTIME_MYSQL"} for x in sources], quality


def publish_report(user: dict, report_id, body: dict) -> dict:
    # 指标先从真实统计服务取数；如果任何上游失败，发布整体失败，禁止生成半真半假的版本。
    caliber = None
    with session() as db:
        _require_report_manage(db, user, "dataCenter.report.publish")
        row = _report(db, report_id)
        _check_version(row, body.get("version"))
        caliber = row.caliber_code
    metrics, trend, sources, quality = _snapshot_metrics(caliber)
    now = datetime.utcnow()
    with session() as db:
        scope = _require_report_manage(db, user, "dataCenter.report.publish")
        row = _report(db, report_id, lock=True)
        _check_version(row, body.get("version"))
        if row.status not in {"DRAFT", "WITHDRAWN"}:
            raise AppException("DATA_CONFLICT", "当前状态不可发布")
        next_no = int(db.scalar(select(func.max(DataCenterReportVersion.version_no)).where(
            DataCenterReportVersion.tenant_id == _tid(),
            DataCenterReportVersion.report_id == row.id)) or 0) + 1
        snapshot = {
            "reportNo": row.report_no, "name": row.name, "category": row.category,
            "cycle": row.cycle, "scopeName": row.scope_name or "全校",
            "description": row.description or "", "caliber": row.caliber_code,
            "query": row.query_json or {}, "layout": row.layout_json or {},
        }
        version = DataCenterReportVersion(
            tenant_id=_tid(), report_id=row.id, version_no=next_no,
            snapshot_json=snapshot, metrics_json=metrics, trend_json=trend,
            as_of=now, caliber_code=row.caliber_code, scope_json=scope,
            source_json=sources, quality_flags_json=quality,
            published_by_id=str(user.get("userId") or ""),
            published_by_name=user.get("realName") or user.get("loginName") or "",
            published_at=now,
        )
        db.add(version)
        row.status = "PUBLISHED"; row.published_version_no = next_no
        row.published_at = now; row.withdrawn_at = None
        row.version = int(row.version or 0) + 1
        audit.record_critical(
            "DATA_CENTER_REPORT_PUBLISH", target_type="data_center_report", target_id=str(row.id),
            detail={"reportNo": row.report_no, "publishedVersion": next_no,
                    "configVersion": row.version, "asOf": _iso(now), "caliber": row.caliber_code}, db=db)
        db.commit(); db.refresh(row)
        return {**_report_row(row), "publishedVersion": next_no, "asOf": _iso(now)}


def withdraw_report(user: dict, report_id, body: dict) -> dict:
    with session() as db:
        _require_report_manage(db, user, "dataCenter.report.publish")
        row = _report(db, report_id, lock=True)
        _check_version(row, body.get("version"))
        if row.status != "PUBLISHED":
            raise AppException("DATA_CONFLICT", "仅已发布报表可以撤回")
        row.status = "WITHDRAWN"; row.withdrawn_at = datetime.utcnow()
        row.version = int(row.version or 0) + 1
        audit.record_critical(
            "DATA_CENTER_REPORT_WITHDRAW", target_type="data_center_report", target_id=str(row.id),
            detail={"reportNo": row.report_no, "publishedVersion": row.published_version_no,
                    "version": row.version}, db=db)
        db.commit(); db.refresh(row)
        return _report_row(row)


def void_report(user: dict, report_id, body: dict) -> dict:
    reason = str(body.get("reason") or "").strip()
    if len(reason) < 5 or len(reason) > 500:
        raise AppException("VALIDATION_ERROR", "作废原因需 5-500 字")
    with session() as db:
        _require_report_manage(db, user, "dataCenter.report.void")
        row = _report(db, report_id, lock=True)
        _check_version(row, body.get("version"))
        if row.status == "VOIDED":
            raise AppException("DATA_CONFLICT", "该报表已作废")
        row.status = "VOIDED"; row.void_reason = reason; row.voided_at = datetime.utcnow()
        row.voided_by_name = user.get("realName") or user.get("loginName") or ""
        row.version = int(row.version or 0) + 1
        audit.record_critical(
            "DATA_CENTER_REPORT_VOID", target_type="data_center_report", target_id=str(row.id),
            detail={"reportNo": row.report_no, "reason": reason, "version": row.version}, db=db)
        db.commit(); db.refresh(row)
        return _report_row(row)


def list_versions(user: dict, report_id) -> list[dict]:
    with session() as db:
        _require_report_read(db, user)
        row = _report(db, report_id)
        rows = db.scalars(select(DataCenterReportVersion).where(
            DataCenterReportVersion.tenant_id == _tid(), DataCenterReportVersion.report_id == row.id)
            .order_by(DataCenterReportVersion.version_no.desc())).all()
        return [{
            "id": str(x.id), "versionNo": x.version_no, "asOf": _iso(x.as_of),
            "caliber": x.caliber_code, "caliberLabel": _CALIBER.get(x.caliber_code, x.caliber_code),
            "publishedBy": x.published_by_name or "", "publishedAt": _iso(x.published_at),
            "scope": x.scope_json or {}, "source": x.source_json or [],
            "qualityFlags": x.quality_flags_json or [],
        } for x in rows]


def list_audits(user: dict, *, report_id=None, limit: int = 20) -> list[dict]:
    with session() as db:
        _require_report_read(db, user)
        cond = [
            SecurityAuditLog.tenant_id == _tid(),
            SecurityAuditLog.resource == "data_center_report",
            SecurityAuditLog.action.like("DATA_CENTER_REPORT_%"),
        ]
        if report_id is not None:
            cond.append(SecurityAuditLog.resource_id == str(report_id))
        rows = db.scalars(select(SecurityAuditLog).where(*cond)
                          .order_by(SecurityAuditLog.id.desc()).limit(max(1, min(100, limit)))).all()
        return [{
            "id": str(x.id), "userName": x.operator_name or "系统",
            "roleName": _ROLE_LABELS.get(x.current_role or "", x.current_role or ""),
            "time": _iso(x.created_at), "action": x.action,
            "target": x.resource_id or "", "targetId": x.resource_id,
            "detail": (x.detail_json or {}).get("reason") or (x.detail_json or {}).get("name")
                      or (x.detail_json or {}).get("reportNo") or "已记录",
            "rawDetail": x.detail_json or {},
        } for x in rows]
