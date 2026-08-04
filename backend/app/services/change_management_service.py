"""PLAT-11 变更、发布、兼容性、灰度与回滚。

影响计算复用 PLAT-08 的 service_catalog_service.compute_service_impact；
冻结窗口判定复用 academic_calendar_service.py 已经维护的
t_calendar_window（EXAM/ORIENTATION/GRADUATION/INTERNSHIP 等各校窗口，
本文件只读，不改动那个服务本身），叠加平台自己声明的 t_maintenance_window
（不挂靠任何单一学校日历的全局冻结期）。

平台只记录 Git SHA/PR/CI 证据，不直接执行 GitHub 合并——本文件不调用任何
外部 Git/CI API，start_wave/report_wave_result 记录的是"运维手工执行后
上报的结果"，不是自动化流水线本身。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.models.change_management import (ChangeExecution, ChangeImpact, ChangeRequest,
                                           MaintenanceWindow)

STATUS_ORDER = ["DRAFT", "ASSESSED", "APPROVED", "SCHEDULED", "IMPLEMENTING"]
TERMINAL_STATUSES = ("VERIFIED", "FAILED", "ROLLED_BACK")
FREEZE_WINDOW_TYPES = ("EXAM", "ORIENTATION", "GRADUATION", "INTERNSHIP")


def _session():
    return get_sessionmaker()()


def _actor_id(user: dict | None) -> int | None:
    raw = str((user or {}).get("userId") or "").removeprefix("db-")
    return int(raw) if raw.isdigit() else None


def _change_dto(change: ChangeRequest, impacts: list[ChangeImpact] | None = None,
                executions: list[ChangeExecution] | None = None) -> dict:
    dto = {
        "changeId": str(change.id), "title": change.title, "changeType": change.change_type,
        "status": change.status, "isEmergency": change.is_emergency,
        "isIrreversible": change.is_irreversible, "gitSha": change.git_sha, "prUrl": change.pr_url,
        "ciEvidence": change.ci_evidence_json, "minClientVersion": change.min_client_version,
        "packageCodes": change.package_codes_json or [],
        "affectedServiceCodes": change.affected_service_codes_json or [],
        "rollbackPlan": change.rollback_plan,
        "scheduledAt": change.scheduled_at.isoformat() if change.scheduled_at else None,
        "approvedAt": change.approved_at.isoformat() if change.approved_at else None,
        "verifiedAt": change.verified_at.isoformat() if change.verified_at else None,
        "rolledBackAt": change.rolled_back_at.isoformat() if change.rolled_back_at else None,
        "lastError": change.last_error, "version": int(change.version or 0),
    }
    if impacts is not None:
        dto["affectedTenants"] = [{"tenantId": str(i.tenant_id), "impactType": i.impact_type}
                                  for i in impacts]
    if executions is not None:
        dto["waves"] = [{
            "waveNo": e.wave_no, "tenantIds": e.tenant_ids_json, "status": e.status,
            "startedAt": e.started_at.isoformat() if e.started_at else None,
            "finishedAt": e.finished_at.isoformat() if e.finished_at else None,
            "error": e.error_message,
        } for e in sorted(executions, key=lambda x: x.wave_no)]
    return dto


def create_change(user: dict, body: dict) -> dict:
    title = str(body.get("title") or "").strip()
    if len(title) < 2:
        raise AppException("VALIDATION_ERROR", "变更标题必填", http_status=422)
    change_type = str(body.get("changeType") or "").upper()
    if change_type not in ("CODE", "MIGRATION", "PLATFORM_CONFIG", "PACKAGE",
                           "COMMON_FOUNDATION", "HOTFIX"):
        raise AppException("VALIDATION_ERROR", "changeType 非法", http_status=422)
    service_codes = [str(c).strip() for c in (body.get("affectedServiceCodes") or []) if str(c).strip()]
    if not service_codes:
        raise AppException("VALIDATION_ERROR", "至少登记一个受影响服务", http_status=422)
    is_irreversible = bool(body.get("isIrreversible"))
    rollback_plan = str(body.get("rollbackPlan") or "").strip() or None

    with _session() as db:
        change = ChangeRequest(
            title=title, change_type=change_type, status="DRAFT",
            is_emergency=bool(body.get("isEmergency")), is_irreversible=is_irreversible,
            git_sha=body.get("gitSha"), pr_url=body.get("prUrl"),
            ci_evidence_json=body.get("ciEvidence") or None,
            min_client_version=body.get("minClientVersion"),
            package_codes_json=body.get("packageCodes") or [],
            affected_service_codes_json=service_codes, rollback_plan=rollback_plan,
            requested_by=_actor_id(user))
        db.add(change)
        db.commit()
        return _change_dto(change)


def _load(db, change_id: int) -> ChangeRequest:
    change = db.get(ChangeRequest, int(change_id))
    if not change or change.is_deleted:
        raise AppException("DATA_NOT_FOUND", "变更请求不存在", http_status=404)
    return change


def get_change(change_id: int) -> dict:
    with _session() as db:
        change = _load(db, change_id)
        impacts = db.scalars(select(ChangeImpact).where(
            ChangeImpact.change_id == change.id, ChangeImpact.is_deleted.is_(False))).all()
        executions = db.scalars(select(ChangeExecution).where(
            ChangeExecution.change_id == change.id, ChangeExecution.is_deleted.is_(False))).all()
        return _change_dto(change, list(impacts), list(executions))


def list_changes(*, status: str | None = None) -> list[dict]:
    with _session() as db:
        q = select(ChangeRequest).where(ChangeRequest.is_deleted.is_(False))
        if status:
            q = q.where(ChangeRequest.status == status)
        rows = db.scalars(q.order_by(ChangeRequest.id.desc())).all()
        return [_change_dto(r) for r in rows]


def assess(change_id: int, *, user: dict | None = None) -> dict:
    """PLAT11-T01：发布前列出服务和租户影响——冻结成快照，评估后不再随依赖图变化改写。"""
    from app.services import service_catalog_service as svcat

    with _session() as db:
        change = _load(db, change_id)
        if change.status != "DRAFT":
            raise AppException("DATA_CONFLICT", "只能评估 DRAFT 状态的变更", http_status=409)

        direct: set[str] = set()
        indirect: set[str] = set()
        for code in change.affected_service_codes_json or []:
            impact = svcat.compute_service_impact(code)
            direct.update(impact["directTenants"])
            indirect.update(impact["indirectTenants"])
        indirect -= direct

        for tid in sorted(direct):
            db.add(ChangeImpact(change_id=change.id, tenant_id=int(tid), impact_type="DIRECT"))
        for tid in sorted(indirect):
            db.add(ChangeImpact(change_id=change.id, tenant_id=int(tid), impact_type="INDIRECT"))
        change.status = "ASSESSED"
        change.version = int(change.version or 0) + 1
        db.commit()
        impacts = db.scalars(select(ChangeImpact).where(ChangeImpact.change_id == change.id)).all()
        return _change_dto(change, list(impacts))


def approve(change_id: int, *, user: dict, reason: str) -> dict:
    """发起与审批必须是不同的人（一人阶段加强控制）。"""
    reason = str(reason or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "审批意见不少于 5 个字", http_status=422)
    with _session() as db:
        change = _load(db, change_id)
        if change.status != "ASSESSED":
            raise AppException("DATA_CONFLICT", "只能审批 ASSESSED 状态的变更", http_status=409)
        approver_id = _actor_id(user)
        if approver_id is not None and approver_id == change.requested_by:
            raise AppException("NO_PERMISSION", "发起人不能审批自己提交的变更", http_status=403)
        change.status = "APPROVED"
        change.approved_by = approver_id
        change.approved_at = datetime.utcnow()
        change.version = int(change.version or 0) + 1
        db.commit()
        return _change_dto(change)


def _affected_tenant_ids(db, change_id: int) -> list[int]:
    return [int(t) for t in db.scalars(select(ChangeImpact.tenant_id).where(
        ChangeImpact.change_id == change_id, ChangeImpact.is_deleted.is_(False))).all()]


def check_freeze_conflicts(tenant_ids: list[int], *, at: datetime | None = None) -> list[dict]:
    """返回冲突列表；空列表=没有冻结冲突。平台全局冻结优先于逐校窗口判断。"""
    from app.models.academic_calendar import CalendarWindow

    now = at or datetime.utcnow()
    conflicts: list[dict] = []
    with _session() as db:
        platform_hits = db.scalars(select(MaintenanceWindow).where(
            MaintenanceWindow.is_deleted.is_(False),
            MaintenanceWindow.start_at <= now, MaintenanceWindow.end_at >= now)).all()
        for w in platform_hits:
            conflicts.append({"scope": "PLATFORM", "title": w.title, "reason": w.reason})

        if tenant_ids:
            hits = db.scalars(select(CalendarWindow).where(
                CalendarWindow.tenant_id.in_(tenant_ids),
                CalendarWindow.window_type.in_(FREEZE_WINDOW_TYPES),
                CalendarWindow.is_deleted.is_(False),
                CalendarWindow.start_at <= now, CalendarWindow.end_at >= now)).all()
            for w in hits:
                conflicts.append({"scope": "TENANT", "tenantId": str(w.tenant_id),
                                 "windowType": w.window_type, "moduleCode": w.module_code})
    return conflicts


def schedule(change_id: int, *, user: dict | None = None, scheduled_at: datetime | None = None) -> dict:
    """PLAT11-T02：冻结窗口阻断普通变更；PLAT11-T04：不可逆迁移必须有替代恢复方案。

    is_emergency（HOTFIX 等）豁免冻结窗口——真正紧急的安全修复不能被"考试期间"卡死，
    但审批环节（approve）本身已经要求发起人与审批人分离且走平台超管硬门槛，
    紧急变更并不会绕开"必须有人审过"这一关，只是不受冻结时间限制。"""
    with _session() as db:
        change = _load(db, change_id)
        if change.status != "APPROVED":
            raise AppException("DATA_CONFLICT", "只能排期 APPROVED 状态的变更", http_status=409)
        if change.is_irreversible and not (change.rollback_plan or "").strip():
            raise AppException(
                "VALIDATION_ERROR",
                "不可逆迁移必须先登记替代恢复方案（rollbackPlan）才能排期", http_status=422)

        tenant_ids = _affected_tenant_ids(db, change.id)
        at = scheduled_at or datetime.utcnow()
        if not change.is_emergency:
            conflicts = check_freeze_conflicts(tenant_ids, at=at)
            if conflicts:
                raise AppException(
                    "DATA_CONFLICT", "排期时间落在冻结窗口内，普通变更禁止在此期间发布",
                    http_status=409, details={"conflicts": conflicts})

        change.status = "SCHEDULED"
        change.scheduled_at = at
        change.version = int(change.version or 0) + 1
        db.commit()
        return _change_dto(change)


def start_wave(change_id: int, *, wave_no: int, tenant_ids: list[int],
              user: dict | None = None) -> dict:
    """开始一个灰度批次；上一波失败过就不允许开新的一波（PLAT11-T03 的"停止扩展"部分）。

    排期时间和真正执行时间可能相隔很久（运维手工触发），排期时没有冻结冲突不代表
    执行这一刻也没有——这里对本批次实际覆盖的租户重新查一次，不是只信排期时的判断。"""
    with _session() as db:
        change = _load(db, change_id)
        if change.status not in ("SCHEDULED", "IMPLEMENTING"):
            raise AppException("DATA_CONFLICT", "只能在 SCHEDULED/IMPLEMENTING 状态下执行灰度批次",
                               http_status=409)
        if not change.is_emergency:
            conflicts = check_freeze_conflicts([int(t) for t in tenant_ids])
            if conflicts:
                raise AppException(
                    "DATA_CONFLICT", "当前处于冻结窗口，普通变更禁止执行灰度批次",
                    http_status=409, details={"conflicts": conflicts})
        prior_failed = db.scalars(select(ChangeExecution).where(
            ChangeExecution.change_id == change.id, ChangeExecution.status == "FAILED")).first()
        if prior_failed:
            raise AppException("DATA_CONFLICT",
                               "已有灰度批次失败，禁止继续扩展新批次，请先处理回滚", http_status=409)
        existing = db.scalars(select(ChangeExecution).where(
            ChangeExecution.change_id == change.id, ChangeExecution.wave_no == wave_no)).first()
        if existing:
            raise AppException("DATA_CONFLICT", f"第 {wave_no} 批已存在", http_status=409)

        execution = ChangeExecution(change_id=change.id, wave_no=wave_no,
                                    tenant_ids_json=[int(t) for t in tenant_ids],
                                    status="RUNNING", started_at=datetime.utcnow())
        db.add(execution)
        change.status = "IMPLEMENTING"
        change.version = int(change.version or 0) + 1
        db.commit()
        return {"waveNo": execution.wave_no, "status": execution.status,
               "tenantIds": execution.tenant_ids_json}


def report_wave_result(change_id: int, wave_no: int, *, status: str, error: str | None = None,
                       user: dict | None = None) -> dict:
    """PLAT11-T03：灰度失败停止扩展并回滚——失败这一波标 FAILED，
    整个变更立即转 ROLLED_BACK，start_wave 会因为"已有失败批次"拒绝任何后续批次。"""
    if status not in ("SUCCEEDED", "FAILED"):
        raise AppException("VALIDATION_ERROR", "status 必须是 SUCCEEDED/FAILED", http_status=422)
    with _session() as db:
        change = _load(db, change_id)
        execution = db.scalars(select(ChangeExecution).where(
            ChangeExecution.change_id == change.id, ChangeExecution.wave_no == wave_no)).first()
        if not execution:
            raise AppException("DATA_NOT_FOUND", "该灰度批次不存在", http_status=404)
        execution.status = status
        execution.finished_at = datetime.utcnow()
        execution.error_message = error
        if status == "FAILED":
            change.status = "ROLLED_BACK"
            change.rolled_back_at = datetime.utcnow()
            change.last_error = error
            change.version = int(change.version or 0) + 1
        db.commit()
        return {"waveNo": execution.wave_no, "status": execution.status,
               "changeStatus": change.status}


def verify(change_id: int, *, user: dict | None = None) -> dict:
    with _session() as db:
        change = _load(db, change_id)
        if change.status != "IMPLEMENTING":
            raise AppException("DATA_CONFLICT", "只能验证 IMPLEMENTING 状态的变更", http_status=409)
        executions = db.scalars(select(ChangeExecution).where(
            ChangeExecution.change_id == change.id)).all()
        if not executions or any(e.status != "SUCCEEDED" for e in executions):
            raise AppException("DATA_CONFLICT", "存在未成功的灰度批次，不能标记验证通过", http_status=409)
        change.status = "VERIFIED"
        change.verified_at = datetime.utcnow()
        change.version = int(change.version or 0) + 1
        db.commit()
        return _change_dto(change)


def fail(change_id: int, *, reason: str, user: dict | None = None) -> dict:
    reason = str(reason or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "失败原因不少于 5 个字", http_status=422)
    with _session() as db:
        change = _load(db, change_id)
        if change.status in TERMINAL_STATUSES:
            raise AppException("DATA_CONFLICT", "变更已处于终态", http_status=409)
        change.status = "FAILED"
        change.last_error = reason
        change.version = int(change.version or 0) + 1
        db.commit()
        return _change_dto(change)


def rollback(change_id: int, *, reason: str, user: dict | None = None) -> dict:
    reason = str(reason or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "回滚原因不少于 5 个字", http_status=422)
    with _session() as db:
        change = _load(db, change_id)
        if change.status == "ROLLED_BACK":
            raise AppException("DATA_CONFLICT", "已经是回滚状态", http_status=409)
        change.status = "ROLLED_BACK"
        change.rolled_back_at = datetime.utcnow()
        change.last_error = reason
        change.version = int(change.version or 0) + 1
        db.commit()
        return _change_dto(change)


def upsert_maintenance_window(user: dict, body: dict) -> dict:
    title = str(body.get("title") or "").strip()
    if len(title) < 2:
        raise AppException("VALIDATION_ERROR", "冻结期标题必填", http_status=422)
    start_at = body.get("startAt")
    end_at = body.get("endAt")
    if not start_at or not end_at:
        raise AppException("VALIDATION_ERROR", "startAt/endAt 必填", http_status=422)
    start_dt = datetime.fromisoformat(str(start_at))
    end_dt = datetime.fromisoformat(str(end_at))
    if end_dt <= start_dt:
        raise AppException("VALIDATION_ERROR", "结束时间必须晚于开始时间", http_status=422)
    with _session() as db:
        window = MaintenanceWindow(title=title, start_at=start_dt, end_at=end_dt,
                                   reason=body.get("reason"))
        db.add(window)
        db.commit()
        return {"id": str(window.id), "title": window.title,
               "startAt": window.start_at.isoformat(), "endAt": window.end_at.isoformat()}


def list_maintenance_windows() -> list[dict]:
    with _session() as db:
        rows = db.scalars(select(MaintenanceWindow).where(
            MaintenanceWindow.is_deleted.is_(False)).order_by(MaintenanceWindow.start_at.desc())).all()
        return [{"id": str(r.id), "title": r.title, "startAt": r.start_at.isoformat(),
                "endAt": r.end_at.isoformat(), "reason": r.reason} for r in rows]


def governance_overview() -> dict:
    with _session() as db:
        today = datetime.utcnow().date()
        changes = db.scalars(select(ChangeRequest).where(ChangeRequest.is_deleted.is_(False))).all()
        today_changes = [c for c in changes if c.created_at and c.created_at.date() == today]
        pending_approval = [c for c in changes if c.status == "ASSESSED"]
        high_risk = [c for c in changes if c.is_irreversible or c.change_type in ("MIGRATION", "HOTFIX")]
        failed = [c for c in changes if c.status in ("FAILED", "ROLLED_BACK")]
        # 复审：原写法把 status 过滤放在两层 for 之后，等价于对每个 change 都先跑一次
        # ChangeImpact 查询、事后再按 status 丢弃结果——多余的 N 次查询。先筛 change 再
        # 一次性按 change_id IN (...) 批量查，避免为不相关的 change 也打一次数据库。
        pending_change_ids = [c.id for c in changes if c.status in ("APPROVED", "SCHEDULED")]
        freeze_conflicts = []
        if pending_change_ids:
            impact_tenant_ids = db.scalars(select(ChangeImpact.tenant_id).where(
                ChangeImpact.change_id.in_(pending_change_ids),
                ChangeImpact.is_deleted.is_(False))).all()
            freeze_conflicts = check_freeze_conflicts([int(t) for t in impact_tenant_ids])
        return {
            "todayChangeCount": len(today_changes), "pendingApprovalCount": len(pending_approval),
            "highRiskCount": len(high_risk), "freezeConflictCount": len(freeze_conflicts),
            "freezeConflicts": freeze_conflicts, "failedChangeCount": len(failed),
        }
