"""企业投诉的安全审计员精确只读范围。

SECURITY_AUDITOR 不再属于业务管理员后，不能依赖 ADMIN_TENANT 获得隐式全权；
但其已被显式授予 ``internship.complaint.view``，应能在当前租户内读取审计材料，
并继续由投诉服务的 sensitive 权限判断强制脱敏。

这里只扩展读取范围，不授予登记、流转、转风险或回访等写权限。
"""
from __future__ import annotations

from functools import wraps

from . import internship_complaint_service as complaint_service


_ORIGINAL_IN_SCOPE = getattr(
    complaint_service,
    "_package0_original_complaint_in_scope",
    complaint_service._complaint_in_scope,
)


@wraps(_ORIGINAL_IN_SCOPE)
def complaint_in_scope_with_auditor(db, complaint, user) -> bool:
    current = user or {}
    role = str(current.get("currentRoleCode") or current.get("roleCode") or "").upper()
    if role == "SECURITY_AUDITOR":
        # complaint 已由 _get/list 查询限定 tenant_id=_tid()；这里只恢复租户内审计只读。
        return True
    return bool(_ORIGINAL_IN_SCOPE(db, complaint, user))


complaint_in_scope_with_auditor._auditor_scope_guard = True


def install() -> None:
    if not hasattr(complaint_service, "_package0_original_complaint_in_scope"):
        complaint_service._package0_original_complaint_in_scope = complaint_service._complaint_in_scope
    if not getattr(complaint_service._complaint_in_scope, "_auditor_scope_guard", False):
        complaint_service._complaint_in_scope = complaint_in_scope_with_auditor
