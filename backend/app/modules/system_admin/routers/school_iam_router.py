"""B7 School IAM Workspace endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.core.permissions import require_any_permission, require_permission
from app.core.response import success
from app.modules.system_admin.services import school_iam_workspace_service as svc

router = APIRouter(prefix="/system/iam", tags=["15·学校IAM工作区"])

_VIEW = require_any_permission(
    "systemAdmin.role.view",
    "systemAdmin.user.view",
    "systemAdmin.scope.view",
    "systemAdmin.audit.view",
)


@router.get("/summary", summary="学校 IAM 工作区总览")
def iam_summary(user=Depends(_VIEW)):
    _ = user
    return success(svc.workspace_summary())


@router.get("/permission-catalog", summary="学校可分配权限目录")
def iam_permission_catalog(user=Depends(require_permission("systemAdmin.role.view"))):
    _ = user
    return success(svc.assignable_catalog())


@router.get("/role-templates", summary="学校可用已发布角色模板")
def iam_role_templates(user=Depends(require_permission("systemAdmin.role.view"))):
    _ = user
    return success({"items": svc.template_catalog()})


@router.get("/role-templates/{template_id}/impact", summary="角色模板对本校 pinned custom roles 的影响")
def iam_role_template_impact(
    template_id: int,
    user=Depends(require_permission("systemAdmin.role.view")),
):
    _ = user
    return success(svc.school_template_impact(template_id))


@router.get("/access-explain/{user_id}", summary="解释学校成员为什么能/不能访问具体业务资源")
def iam_access_explain(
    user_id: int,
    moduleKey: str = Query(default="internship", min_length=1, max_length=64),
    permissionCode: str = Query(default="internship.recruitment.manage", min_length=3, max_length=200),
    scopeTargetType: str | None = Query(default=None, min_length=3, max_length=32),
    scopeTargetId: str | None = Query(default=None, min_length=1, max_length=128),
    resourceType: str | None = Query(default=None, min_length=2, max_length=64),
    resourceId: str | None = Query(default=None, min_length=1, max_length=128),
    user=Depends(require_permission("systemAdmin.role.view")),
):
    _ = user
    return success(svc.explain_subject_access(
        user_id,
        module_key=moduleKey,
        permission_code=permissionCode,
        scope_target_type=scopeTargetType,
        scope_target_id=scopeTargetId,
        resource_type=resourceType,
        resource_id=resourceId,
    ))
