"""SYS-16 后台任务授权分类：USER_DELEGATED / SERVICE_POLICY / TENANT_SYSTEM_TASK。

不新建授权表——一次任务动作（retry/cancel）触发时，实时判定当前操作者持有
所需权限是走"自身角色的常规授权"还是"临时授权"(system_governance_service 的
DELEGATIONS)。命中临时授权时立即附带该授权的可核验证据；一旦授权被回收，
active_delegation_permission_patterns() 立刻不再返回它，下一次同样的动作会
在这里被拒绝——这就是"吊销门禁"：不需要给每个任务快照一份授权历史，
用实时重新判定天然做到"回收即失效"。

范围快照(scopeSnapshot)不在这里管，直接读各任务表已有的
data_scope_snapshot_json / data_scope_snapshot 字段（见 job-registry.yaml）。
"""
from __future__ import annotations

from app.core.exceptions import AppException

POLICY_USER_DELEGATED = "USER_DELEGATED"
POLICY_SERVICE_POLICY = "SERVICE_POLICY"
POLICY_TENANT_SYSTEM_TASK = "TENANT_SYSTEM_TASK"


def _actor_id(actor) -> str:
    if isinstance(actor, dict):
        return str(actor.get("userId") or "")
    return str(getattr(actor, "userId", "") or "")


def classify(actor, required_permission: str) -> dict | None:
    """判定 actor 对 required_permission 的授权来源；不持有任一来源时返回 None（不抛异常）。

    SERVICE_POLICY 只在 actor 显式带 serviceIdentity 标记（内部调度/系统任务自己设置，
    真人 HTTP 请求不会有这个字段）时才成立，并且仍然要求 servicePermissions 里
    真的包含 required_permission——"没有 userId" 本身绝不能当成自动放行的理由，
    否则任何构造出的空 actor 都会绕过鉴权。没有 userId 也没有 serviceIdentity 时
    直接判定未授权（None），交给调用方 fail-closed。
    """
    from app.core.permissions import _match, get_base_permission_patterns
    from app.services import system_governance_service as gov

    aid = _actor_id(actor)
    if not aid:
        service_identity = actor.get("serviceIdentity") if isinstance(actor, dict) else None
        service_permissions = (actor.get("servicePermissions") or []) if isinstance(actor, dict) else []
        if service_identity and _match(required_permission, service_permissions):
            return {
                "policyType": POLICY_SERVICE_POLICY, "delegatedSubject": service_identity,
                "grantedPermission": required_permission,
            }
        return None

    base_patterns = get_base_permission_patterns(actor)
    if _match(required_permission, base_patterns):
        return {
            "policyType": POLICY_TENANT_SYSTEM_TASK, "delegatedSubject": None,
            "grantedPermission": required_permission,
        }

    delegated_patterns = gov.active_delegation_permission_patterns(actor)
    if _match(required_permission, delegated_patterns):
        matched = next((
            item for item in gov.list_delegations()
            if item.get("status") == "ACTIVE" and item.get("effective", True)
            and str(item.get("granteeUserId") or "") == aid.removeprefix("db-")
        ), None)
        return {
            "policyType": POLICY_USER_DELEGATED,
            "delegatedSubject": matched.get("id") if matched else None,
            "delegationRoleCode": matched.get("roleCode") if matched else None,
            "delegationExpiresAt": matched.get("expiresAt") if matched else None,
            "grantedPermission": required_permission,
        }

    return None


def classify_and_authorize(actor, required_permission: str) -> dict:
    """判定并强制要求 actor 持有 required_permission（自身角色或临时授权任一命中）。

    没有任一来源命中时 fail-closed 抛 NO_PERMISSION——这是"吊销门禁"的落点：
    临时授权一旦被回收，active_delegation_permission_patterns() 立刻不再包含它，
    下一次调用这里就会直接失败，不需要额外补一次撤销检查。
    """
    evidence = classify(actor, required_permission)
    if evidence is None:
        raise AppException("NO_PERMISSION", f"当前无权执行该任务动作（需要 {required_permission}）",
                           http_status=403)
    return evidence
