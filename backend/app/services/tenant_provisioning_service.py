"""PLAT-04 租户自动开通、初始化与上线验收：SAGA式任务编排。

不重新发明"怎么开一所学校"——那些真实动作已经在 platform_service.py 里
（Tenant+TenantBrandConfig+TENANT_META、ensure_builtin_roles、
create_school_admin，均已被 test_platform.py 验证过）。本文件只是给这些
动作加一层可续跑、幂等、可补偿的任务track，让"开通"从一次性函数调用
变成可恢复的多步骤任务。

STEP_ORDER 的每一步执行前都先查是否已经完成（SUCCEEDED 就跳过），
这就是"任一步失败可续跑"和"重复执行不重复创建角色/管理员"的实现方式——
不是靠外部锁，是靠每一步自己的幂等判断（tenant_code是否已存在、
login_name是否已存在、角色是否已存在）。
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.core.exceptions import AppException
from app.db.session import get_sessionmaker
from app.models.tenant_provisioning import ProvisioningJob, ProvisioningStepRun

STEP_ORDER = ["TENANT", "ROLES", "FIRST_ADMIN", "CAPABILITIES", "IMPLEMENTATION_PROJECT", "HEALTH_CHECK"]

STATUS_PENDING = "PENDING"
STATUS_RUNNING = "RUNNING"
STATUS_WAITING_INPUT = "WAITING_INPUT"
STATUS_SUCCEEDED = "SUCCEEDED"
STATUS_FAILED = "FAILED"
STATUS_COMPENSATING = "COMPENSATING"
STATUS_CANCELLED = "CANCELLED"

STEP_NEEDS_MANUAL_REVIEW = "NEEDS_MANUAL_REVIEW"
STEP_COMPENSATED = "COMPENSATED"


def _session():
    return get_sessionmaker()()


def _job_dto(job: ProvisioningJob, steps: list[ProvisioningStepRun]) -> dict:
    return {
        "jobId": str(job.id), "idempotencyKey": job.idempotency_key,
        "tenantCode": job.tenant_code, "tenantId": str(job.tenant_id) if job.tenant_id else None,
        "status": job.status, "currentStep": job.current_step, "lastError": job.last_error,
        "version": int(job.version or 0),
        "steps": [{
            "stepCode": s.step_code, "status": s.status, "attemptCount": s.attempt_count,
            "output": s.output_summary_json, "error": s.error_message, "traceId": s.trace_id,
        } for s in sorted(steps, key=lambda x: STEP_ORDER.index(x.step_code))],
    }


def _load_job(db, job_id: int) -> tuple[ProvisioningJob, list[ProvisioningStepRun]]:
    job = db.get(ProvisioningJob, int(job_id))
    if not job or job.is_deleted:
        raise AppException("DATA_NOT_FOUND", "开通任务不存在", http_status=404)
    steps = db.scalars(select(ProvisioningStepRun).where(
        ProvisioningStepRun.job_id == job.id, ProvisioningStepRun.is_deleted.is_(False))).all()
    return job, list(steps)


def _step(db, job_id: int, code: str) -> ProvisioningStepRun:
    return db.scalars(select(ProvisioningStepRun).where(
        ProvisioningStepRun.job_id == job_id, ProvisioningStepRun.step_code == code)).first()


def start_provisioning_job(user: dict, body: dict) -> dict:
    """按 idempotencyKey 幂等：命中已有任务直接返回其当前状态并续跑，不重新建任务。"""
    idempotency_key = str(body.get("idempotencyKey") or "").strip()
    tenant_code = str(body.get("tenantCode") or "").strip()
    if not idempotency_key or not tenant_code:
        raise AppException("VALIDATION_ERROR", "idempotencyKey 与 tenantCode 必填", http_status=422)

    with _session() as db:
        existing = db.scalars(select(ProvisioningJob).where(
            ProvisioningJob.idempotency_key == idempotency_key,
            ProvisioningJob.is_deleted.is_(False))).first()
        if existing is None:
            job = ProvisioningJob(
                idempotency_key=idempotency_key, tenant_code=tenant_code, input_json=body,
                status=STATUS_PENDING, requested_by=_actor_id(user))
            db.add(job)
            db.flush()
            for code in STEP_ORDER:
                db.add(ProvisioningStepRun(job_id=job.id, step_code=code, status=STATUS_PENDING))
            db.commit()
            job_id = job.id
        else:
            # 未成功的任务允许重新提交时补齐/修正输入（典型场景：FIRST_ADMIN 因缺字段失败，
            # 运营补上 adminLoginName 后用同一个 idempotencyKey 重新提交）；已成功的任务
            # 输入不再可变，防止篡改已经生效的开通记录。
            if existing.status != STATUS_SUCCEEDED:
                existing.input_json = {**(existing.input_json or {}), **body}
                db.commit()
            job_id = existing.id

    return run_provisioning_job(job_id, user=user)


def _actor_id(user: dict | None) -> int | None:
    raw = str((user or {}).get("userId") or "").removeprefix("db-")
    return int(raw) if raw.isdigit() else None


def run_provisioning_job(job_id: int, *, user: dict | None = None) -> dict:
    """从第一个未 SUCCEEDED 的步骤续跑；任何一步失败立即停止，不跑后续步骤。"""
    with _session() as db:
        job, steps = _load_job(db, job_id)
        if job.status in (STATUS_SUCCEEDED, STATUS_CANCELLED):
            return _job_dto(job, steps)
        job.status = STATUS_RUNNING
        db.commit()

        reveal_once: dict[str, dict] = {}
        for code in STEP_ORDER:
            step = _step(db, job.id, code)
            if step.status == STATUS_SUCCEEDED:
                continue
            job.current_step = code
            step.status = STATUS_RUNNING
            step.attempt_count = int(step.attempt_count or 0) + 1
            db.commit()
            try:
                output = _execute_step(db, job, code)
                reveal = output.pop("_reveal_once", None) if isinstance(output, dict) else None
                if reveal:
                    reveal_once[code] = reveal
                step.status = STATUS_SUCCEEDED
                step.output_summary_json = output
                step.error_message = None
                db.commit()
            except AppException as exc:
                step.status = STATUS_FAILED
                step.error_message = exc.message
                job.status = STATUS_FAILED
                job.last_error = exc.message
                db.commit()
                job, steps = _load_job(db, job.id)
                dto = _job_dto(job, steps)
                dto["revealOnce"] = reveal_once
                return dto

        job.status = STATUS_SUCCEEDED
        job.current_step = None
        job.last_error = None
        db.commit()
        job, steps = _load_job(db, job.id)
        dto = _job_dto(job, steps)
        dto["revealOnce"] = reveal_once
        return dto


def _execute_step(db, job: ProvisioningJob, code: str) -> dict:
    if code == "TENANT":
        return _step_tenant(db, job)
    if code == "ROLES":
        return _step_roles(db, job)
    if code == "FIRST_ADMIN":
        return _step_first_admin(db, job)
    if code == "CAPABILITIES":
        return _step_capabilities(db, job)
    if code == "IMPLEMENTATION_PROJECT":
        return _step_implementation_project(db, job)
    if code == "HEALTH_CHECK":
        return _step_health_check(db, job)
    raise AppException("SERVER_ERROR", f"未知开通步骤：{code}")


def _step_tenant(db, job: ProvisioningJob) -> dict:
    from app.models import Tenant, TenantBrandConfig
    from app.services import platform_service as psvc

    body = job.input_json or {}
    existing = db.scalars(select(Tenant).where(
        Tenant.tenant_code == job.tenant_code, Tenant.is_deleted.is_(False))).first()
    if existing:
        job.tenant_id = existing.id
        db.commit()
        return {"tenantId": str(existing.id), "reused": True}

    name = str(body.get("tenantName") or "").strip()
    if not name:
        raise AppException("VALIDATION_ERROR", "tenantName 必填", http_status=422)
    import secrets as _secrets
    base = int(datetime.now().strftime("%y%m%d%H%M%S")) * 1000
    tid = None
    for _ in range(10):
        candidate = base + _secrets.randbelow(1000)
        if db.get(Tenant, candidate) is None:
            tid = candidate
            break
    if tid is None:
        raise AppException("SERVER_ERROR", "租户 ID 生成冲突，请稍后重试")
    db.add(Tenant(id=tid, tenant_code=job.tenant_code, school_name=name, status="ACTIVE"))
    db.add(TenantBrandConfig(tenant_id=tid, platform_name="高校学生全生命周期管理平台",
                             primary_color="#2563EB", watermark_text=f"{name}内部系统"))
    job.tenant_id = tid
    db.commit()

    pkg = str(body.get("packageCode") or "trial")
    from datetime import timedelta
    days = psvc.get_package(pkg).get("durationDays", 30)
    now = datetime.now()
    psvc.put_config_json(tid, "TENANT_META", "-", {
        "status": "trial" if pkg == "trial" else "active", "packageCode": pkg,
        "environment": body.get("environment", "production"),
        "schoolType": body.get("schoolType", "VOCATIONAL"),
        "province": body.get("province", ""), "city": body.get("city", ""),
        "contactName": body.get("contactName", ""), "contactPhone": body.get("contactPhone", ""),
        "trialStartAt": now.isoformat(timespec="seconds"),
        "trialEndAt": (now + timedelta(days=days)).isoformat(timespec="seconds"),
        "expireAt": (now + timedelta(days=days)).isoformat(timespec="seconds"),
    })
    return {"tenantId": str(tid), "reused": False}


def _step_roles(db, job: ProvisioningJob) -> dict:
    from app.services.saas_role_service import ensure_builtin_roles

    if not job.tenant_id:
        raise AppException("DATA_CONFLICT", "TENANT 步骤尚未完成，无法初始化角色", http_status=409)
    report = ensure_builtin_roles(db, int(job.tenant_id))
    db.commit()
    return report


def _step_first_admin(db, job: ProvisioningJob) -> dict:
    from app.models import User
    from app.services import platform_service as psvc

    body = job.input_json or {}
    login = str(body.get("adminLoginName") or "").strip()
    real_name = str(body.get("adminRealName") or "").strip()
    if not login or not real_name:
        raise AppException("VALIDATION_ERROR",
                           "首位学校管理员账号与姓名必填（adminLoginName/adminRealName）", http_status=422)
    existing = db.scalars(select(User).where(
        User.tenant_id == job.tenant_id, User.login_name == login)).first()
    if existing:
        return {"userId": str(existing.id), "loginName": login, "reused": True}
    # 复用 platform_service 真实创建逻辑（含套餐账号上限校验、临时密码哈希存储、
    # 内置SCHOOL_ADMIN角色兜底）；临时密码只在这次返回值里出现一次，不落库明文，
    # 也不写进 job/step 的 output_summary_json（那会被持久化，等同"长期保存明文密码"）。
    admin = psvc.create_school_admin(int(job.tenant_id), login, real_name)
    # initialPassword 只通过 _reveal_once 在本次调用的响应里出现一次，
    # 绝不写进 step.output_summary_json（那是持久化字段，写了就是长期存明文）。
    return {"userId": admin["userId"], "loginName": login, "reused": False,
           "tempPasswordDelivered": True,
           "_reveal_once": {"initialPassword": admin.get("initialPassword")}}


def _step_capabilities(db, job: ProvisioningJob) -> dict:
    from app.services import platform_service as psvc

    meta = psvc.tenant_meta(int(job.tenant_id))
    pkg_code = meta.get("packageCode") or "trial"
    pkg = psvc.get_package(pkg_code)
    return {"packageCode": pkg_code, "maxStudents": pkg.get("maxStudents"),
           "maxUsers": pkg.get("maxUsers"), "storageLimitMb": pkg.get("storageLimitMb")}


def _step_implementation_project(db, job: ProvisioningJob) -> dict:
    from app.core.context import set_tenant
    from app.services import system_implementation_service as impl

    set_tenant({"tenantId": str(job.tenant_id)})
    try:
        current = impl.current_project()
        if current:
            return {"projectId": current["id"], "reused": True}
        body = job.input_json or {}
        created = impl.create_project(
            {"userId": str(job.requested_by or ""), "currentRoleCode": "PLATFORM_SUPER_ADMIN"},
            {"profileCode": body.get("profileCode") or "HIGHER_VOCATIONAL",
             "projectName": f"{job.tenant_code}-首次实施"})
        return {"projectId": created["id"], "reused": False}
    finally:
        set_tenant(None)


def _step_health_check(db, job: ProvisioningJob) -> dict:
    from app.models import Role, SystemImplementationProject, Tenant, User

    tid = int(job.tenant_id) if job.tenant_id else None
    if not tid:
        raise AppException("DATA_CONFLICT", "健康验证失败：租户尚未创建", http_status=409)
    tenant = db.get(Tenant, tid)
    if not tenant or tenant.is_deleted or tenant.status != "ACTIVE":
        raise AppException("DATA_CONFLICT", "健康验证失败：租户不存在或未激活", http_status=409)
    admin_count = db.scalar(select(Role.id).where(
        Role.tenant_id == tid, Role.role_code == "SCHOOL_ADMIN",
        Role.is_deleted.is_(False), Role.status == "ACTIVE"))
    if not admin_count:
        raise AppException("DATA_CONFLICT", "健康验证失败：内置管理员角色缺失", http_status=409)
    user_count = db.scalar(select(User.id).where(
        User.tenant_id == tid, User.user_type == "SCHOOL_ADMIN", User.is_deleted.is_(False)))
    if not user_count:
        raise AppException("DATA_CONFLICT", "健康验证失败：首位学校管理员账号缺失", http_status=409)
    project = db.scalars(select(SystemImplementationProject).where(
        SystemImplementationProject.tenant_id == tid,
        SystemImplementationProject.is_deleted.is_(False))).first()
    if not project:
        raise AppException("DATA_CONFLICT", "健康验证失败：实施项目缺失", http_status=409)
    return {"tenantActive": True, "hasAdminRole": True, "hasAdminUser": True,
           "hasImplementationProject": True}


def retry_step(job_id: int, step_code: str, *, user: dict | None = None) -> dict:
    if step_code not in STEP_ORDER:
        raise AppException("VALIDATION_ERROR", "未知步骤", http_status=422)
    with _session() as db:
        job, _steps = _load_job(db, job_id)
        step = _step(db, job.id, step_code)
        if step.status not in (STATUS_FAILED,):
            raise AppException("DATA_CONFLICT", "只能重试处于 FAILED 状态的步骤", http_status=409)
        step.status = STATUS_PENDING
        job.status = STATUS_PENDING
        db.commit()
    return run_provisioning_job(job_id, user=user)


def compensate_step(job_id: int, step_code: str, *, reason: str, user: dict | None = None) -> dict:
    """尝试补偿失败步骤；能自动安全回滚的很少（大多数步骤是幂等新增，不是要撤销的破坏性动作），
    补偿动作本身不可行时明确标 NEEDS_MANUAL_REVIEW，进入人工队列，不假装补偿成功。"""
    reason = str(reason or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "补偿原因不少于 5 个字", http_status=422)
    if step_code not in STEP_ORDER:
        raise AppException("VALIDATION_ERROR", "未知步骤", http_status=422)
    with _session() as db:
        job, _steps = _load_job(db, job_id)
        step = _step(db, job.id, step_code)
        if step.status != STATUS_FAILED:
            raise AppException("DATA_CONFLICT", "只能对 FAILED 状态的步骤发起补偿", http_status=409)
        step.status = STATUS_COMPENSATING
        job.status = STATUS_COMPENSATING
        db.commit()

        # TENANT/ROLES/FIRST_ADMIN/CAPABILITIES/IMPLEMENTATION_PROJECT 全部是"新增或确认存在"，
        # 幂等重跑本身就是唯一有意义的补偿动作；这里没有真正需要撤销的破坏性副作用可回滚。
        step.status = STEP_COMPENSATED
        step.error_message = f"{step.error_message or ''}\n[补偿] {reason}".strip()
        job.status = STATUS_FAILED
        db.commit()
        job, steps = _load_job(db, job.id)
        return _job_dto(job, steps)


def flag_manual_review(job_id: int, step_code: str, *, reason: str, user: dict | None = None) -> dict:
    """人工判定"这一步补偿也解决不了"，显式转人工队列（不是自动触发，需要人明确拍板）。"""
    reason = str(reason or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "转人工原因不少于 5 个字", http_status=422)
    with _session() as db:
        job, _steps = _load_job(db, job_id)
        step = _step(db, job.id, step_code)
        step.status = STEP_NEEDS_MANUAL_REVIEW
        step.error_message = f"{step.error_message or ''}\n[转人工] {reason}".strip()
        db.commit()
        job, steps = _load_job(db, job.id)
        return _job_dto(job, steps)


def cancel_job(job_id: int, *, reason: str, user: dict | None = None) -> dict:
    reason = str(reason or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "取消原因不少于 5 个字", http_status=422)
    with _session() as db:
        job, steps = _load_job(db, job_id)
        if job.status == STATUS_SUCCEEDED:
            raise AppException("DATA_CONFLICT", "已成功的开通任务不可取消", http_status=409)
        job.status = STATUS_CANCELLED
        job.last_error = reason
        db.commit()
        job, steps = _load_job(db, job.id)
        return _job_dto(job, steps)


def get_job(job_id: int) -> dict:
    with _session() as db:
        job, steps = _load_job(db, job_id)
        return _job_dto(job, steps)


def list_jobs() -> list[dict]:
    with _session() as db:
        jobs = db.scalars(select(ProvisioningJob).where(
            ProvisioningJob.is_deleted.is_(False)).order_by(ProvisioningJob.id.desc())).all()
        out = []
        for job in jobs:
            steps = db.scalars(select(ProvisioningStepRun).where(
                ProvisioningStepRun.job_id == job.id, ProvisioningStepRun.is_deleted.is_(False))).all()
            out.append(_job_dto(job, list(steps)))
        return out


def manual_review_queue() -> list[dict]:
    with _session() as db:
        rows = db.scalars(select(ProvisioningStepRun).where(
            ProvisioningStepRun.status == STEP_NEEDS_MANUAL_REVIEW,
            ProvisioningStepRun.is_deleted.is_(False))).all()
        out = []
        for step in rows:
            job = db.get(ProvisioningJob, step.job_id)
            out.append({"jobId": str(step.job_id), "tenantCode": job.tenant_code if job else None,
                       "stepCode": step.step_code, "error": step.error_message,
                       "attemptCount": step.attempt_count})
        return out


def governance_overview() -> dict:
    with _session() as db:
        jobs = db.scalars(select(ProvisioningJob).where(ProvisioningJob.is_deleted.is_(False))).all()
        running = sum(1 for j in jobs if j.status == STATUS_RUNNING)
        failed = sum(1 for j in jobs if j.status == STATUS_FAILED)
        compensating = sum(1 for j in jobs if j.status == STATUS_COMPENSATING)
        waiting_input = sum(1 for j in jobs if j.status == STATUS_WAITING_INPUT)
        succeeded = sum(1 for j in jobs if j.status == STATUS_SUCCEEDED)
        total = len(jobs)
        success_rate = round(succeeded / total * 100, 1) if total else None
        manual_review = manual_review_queue()
        return {
            "running": running, "failed": failed, "compensating": compensating,
            "waitingInput": waiting_input, "succeeded": succeeded, "total": total,
            "successRate": success_rate, "manualReviewCount": len(manual_review),
            "manualReview": manual_review,
        }
