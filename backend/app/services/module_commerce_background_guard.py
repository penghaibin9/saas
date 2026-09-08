"""Commercial lifecycle fence for recurring module business writers.

HTTP routes receive the M4 final-commit fence through the canonical module gate.
Recurring schedulers do not have HTTP request intent or a durable task generation,
so their current-generation business calls are wrapped here. Unpurchased/frozen
modules are expected skips; authority/storage failures still propagate fail-closed.

Only module-owned business writers belong in ``_TARGETS``. Shared approval export,
message/outbox delivery, document derivatives, frozen-package integrity workers and
control-plane maintenance remain outside this guard: stopping one purchased module
must never stop cross-module compliance evidence or another module's shared job.
Those shared resources are resolved by object ownership/dependency policy during M5.
"""
from __future__ import annotations

import functools
import importlib
import logging

_LOG = logging.getLogger("platform.module-commerce-background")

_TARGETS: tuple[tuple[str, str, str], ...] = (
    # Internship business state.
    ("app.modules.internship.services.internship_leave_service", "refresh_overdue", "internship"),

    # Student-affairs business state and tenant-scoped business exports. Generic
    # approval/file/message workers are intentionally not included because they are
    # shared foundations and require object-bound ownership rather than a broad gate.
    ("app.services.affairs_appeal_repair_service", "repair_pending", "studentAffairs"),
    ("app.services.affairs_leave_export_service", "run_pending", "studentAffairs"),
    ("app.services.affairs_funding_export_service", "run_pending", "studentAffairs"),
    ("app.services.affairs_archive_service", "run_pending_packages", "studentAffairs"),
    ("app.services.affairs_leave_service", "scan_overdue", "studentAffairs"),
    ("app.services.affairs_risk_service", "scan_timeout", "studentAffairs"),
    ("app.services.affairs_counselor_service", "scan_expired_temps", "studentAffairs"),

    # Academic-affairs recurring writers. These can create durable academic facts or
    # deadline state, so a tenant being writable is not enough: the purchased module
    # and the same module generation must still be writable at final commit.
    (
        "app.modules.academic_affairs.services.academic_affairs_change_temporal_guard",
        "apply_due_changes",
        "academicAffairs",
    ),
    (
        "app.modules.academic_affairs.services.academic_affairs_grade_deadline_scheduler_service",
        "scan_grade_deadlines",
        "academicAffairs",
    ),
)


def _current_tenant_id() -> int:
    from app.core.context import current_tenant_id

    try:
        tid = int(current_tenant_id() or 0)
    except (TypeError, ValueError, OverflowError):
        tid = 0
    return tid


def _run_guarded(module_key: str, target, *args, **kwargs):
    tenant_id = _current_tenant_id()
    if tenant_id <= 0:
        # These functions are tenant-scoped writers; no tenant must never become
        # an implicit all-tenant/background write.
        from app.core.exceptions import AppException
        raise AppException(
            "TENANT_CONTEXT_REQUIRED",
            "后台模块任务缺少学校上下文，已拒绝执行",
            http_status=403,
        )

    from app.services import module_access_service
    state = module_access_service.module_access_state(tenant_id, module_key)
    if not bool(state.get("writable")):
        _LOG.info(
            "module_background_skipped tenant=%s module=%s reason=%s",
            tenant_id, module_key, state.get("reasonCode") or "NOT_WRITABLE",
        )
        return None

    generation = int(state.get("generation") or 0)
    if generation <= 0:
        # Legacy commercial readers have no module-generation row. They still pass
        # the canonical authority above; M4 generation fencing begins after V2 cutover.
        return target(*args, **kwargs)

    from app.services.module_commerce_access_guard import module_write_fence
    with module_write_fence(tenant_id, module_key, generation):
        return target(*args, **kwargs)


def _wrap(module, function_name: str, module_key: str) -> bool:
    original = getattr(module, function_name, None)
    if not callable(original):
        return False
    if getattr(original, "_module_commerce_background_fenced", False):
        return False

    @functools.wraps(original)
    def guarded(*args, **kwargs):
        return _run_guarded(module_key, original, *args, **kwargs)

    guarded._module_commerce_background_fenced = True
    guarded._module_commerce_module_key = module_key
    setattr(module, function_name, guarded)
    return True


def install() -> int:
    """Install every reviewed module-owned recurring writer exactly once.

    Import/name drift is a deployment error, not a reason to silently leave a
    production writer unfenced. Therefore missing target modules/functions fail
    startup instead of being swallowed.
    """
    installed = 0
    for module_name, function_name, module_key in _TARGETS:
        module = importlib.import_module(module_name)
        original = getattr(module, function_name, None)
        if not callable(original):
            raise RuntimeError(
                f"module commerce background writer missing: {module_name}.{function_name}"
            )
        installed += int(_wrap(module, function_name, module_key))
    return installed
