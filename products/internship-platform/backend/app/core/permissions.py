from __future__ import annotations
from fastapi import Depends
from app.core.exceptions import no_permission
from app.core.security import get_current_user

ROLE_PERMISSIONS={
 "PLATFORM_SUPER_ADMIN":{"*"},
 "SCHOOL_ADMIN":{"internship.*"},
 "COLLEGE_ADMIN":{"internship.*"},
 "PROFESSIONAL_LEADER":{"internship.batch.view","internship.dashboard.view","internship.student.view","internship.plan.view","internship.plan.manage","internship.task.view","internship.task.review","internship.report.view","internship.report.review","internship.stats.view"},
 "MAJOR_LEADER":{"internship.batch.view","internship.dashboard.view","internship.student.view","internship.plan.view","internship.plan.manage","internship.task.view","internship.task.review","internship.report.view","internship.report.review","internship.stats.view"},
 "INTERN_MENTOR":{"internship.batch.view","internship.dashboard.view","internship.student.view","internship.student.password.reset","internship.rotation.manage","internship.payroll.view","internship.payroll.review","internship.application.view","internship.application.review","internship.attendance.view","internship.attendance.review","internship.leave.view","internship.leave.review","internship.report.view","internship.report.review","internship.guidance.view","internship.guidance.manage","internship.visit.view","internship.visit.manage","internship.risk.view","internship.risk.handle","internship.score.view","internship.score.manage","internship.agreement.view","internship.archive.view","internship.plan.view","internship.task.view","internship.task.review"},
 "COUNSELOR":{"internship.batch.view","internship.dashboard.view","internship.student.view","internship.attendance.view","internship.leave.view","internship.report.view","internship.risk.view","internship.guidance.view","internship.visit.view","internship.score.view","internship.agreement.view","internship.archive.view","internship.plan.view"},
 "LEADER":{"internship.batch.view","internship.dashboard.view","internship.student.view","internship.stats.view","internship.archive.view"},
 "SECURITY_AUDITOR":{"internship.batch.view","internship.dashboard.view","internship.student.view","internship.attendance.view","internship.risk.view","internship.archive.view","internship.stats.view"},
 "STUDENT":set(),
}
def _role(user):return str((user or {}).get("currentRoleCode") or (user or {}).get("roleCode") or (user or {}).get("userType") or "").upper()
def _granted(user):
    explicit=(user or {}).get("permissions") or (user or {}).get("permissionCodes")
    return {str(x) for x in explicit} if isinstance(explicit,(list,tuple,set)) else set(ROLE_PERMISSIONS.get(_role(user),set()))
def _matches(pattern,code):return pattern=="*" or pattern==code or (pattern.endswith(".*") and code.startswith(pattern[:-1]))
def is_super_admin(user):return _role(user)=="PLATFORM_SUPER_ADMIN"
def has_permission(user,code):return any(_matches(p,code) for p in _granted(user))
def enforce_permission(user,code):
    if not has_permission(user,code):raise no_permission(f"缺少权限：{code}")
    return user
def require_permission(code):
    def dep(user=Depends(get_current_user)):return enforce_permission(user,code)
    return dep
def require_any_permission(*codes):
    def dep(user=Depends(get_current_user)):
        if not any(has_permission(user,c) for c in codes):raise no_permission("缺少所需权限")
        return user
    return dep
def require_module(module_key):
    def dep(user=Depends(get_current_user)):
        if module_key!="internship":raise no_permission("Standalone 仅开放岗位实习模块")
        return user
    return dep
def require_staff(user=Depends(get_current_user)):
    if _role(user)=="STUDENT":raise no_permission("该接口仅教职工可用")
    return user
def get_effective_access_context(user):
    return {"roleCode":_role(user),"permissions":sorted(_granted(user)),"module":"internship"}
