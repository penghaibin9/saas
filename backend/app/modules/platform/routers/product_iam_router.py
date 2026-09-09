"""B6 Platform Product IAM endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends

from app.core.platform_principal import require_platform_principal, assert_platform_root
from app.core.platform_assurance import assert_recent_platform_auth
from app.core.response import success
from app.modules.platform.services import platform_product_iam_hardening as svc
from app.modules.system_admin.services import role_template_service as template_svc

router = APIRouter(prefix="/platform/product-iam", tags=["16·平台产品IAM"])


def _view(user: dict) -> dict:
    # Product IAM is platform-only. Until B8 exact platform permission migration,
    # Security Auditor can read through its canonical access-review capability;
    # only root can create/publish releases.
    from app.services import platform_access_governance_service as pam
    try:
        return pam.assert_platform_capability(user, "access.review")
    except Exception:
        return assert_platform_root(user)


@router.get("/source", summary="查看当前模块/权限/导航/角色模板真值")
def product_iam_source(user=Depends(require_platform_principal)):
    _view(user)
    return success(svc.source_snapshot())


@router.get("/releases", summary="Product IAM 发布版本")
def product_iam_releases(user=Depends(require_platform_principal)):
    _view(user)
    return success({"items": svc.list_releases()})


@router.post("/releases", summary="基于当前代码真值创建 Product IAM 发布草稿")
def product_iam_release_create(body: dict = Body(...), user=Depends(require_platform_principal)):
    assert_platform_root(user)
    return success(svc.create_release_draft(
        reason=body.get("reason") or "",
        source_commit_sha=body.get("sourceCommitSha") or "",
        request_id=body.get("requestId") or "",
        actor=user,
    ))


@router.get("/releases/{release_id}/impact", summary="Product IAM 版本影响分析")
def product_iam_release_impact(release_id: str, user=Depends(require_platform_principal)):
    _view(user)
    return success(svc.impact(release_id))


@router.post("/releases/{release_id}/publish", summary="发布 Product IAM 版本")
def product_iam_release_publish(release_id: str, body: dict = Body(...), user=Depends(require_platform_principal)):
    assert_platform_root(user)
    return success(svc.publish_release(
        release_id,
        expected_version=int(body.get("expectedVersion") or -1),
        actor=user,
    ))


def _actor_id(user: dict) -> int | None:
    value = user.get("userId") or user.get("id")
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _template_preview(row: dict) -> dict:
    source = svc.source_snapshot()
    surfaces = source.get("navigationSurfaces") or []
    menus = svc._base._menu_preview(set(row.get("permissions") or []), surfaces)
    return {**row, "menuPreview": menus, "menuCount": len(menus),
            "navigationDigest": source.get("navigationDigest"), "sourceDigest": source.get("sourceDigest")}


@router.get("/school-role-templates", summary="学校标准角色模板及不可变版本")
def school_role_templates(user=Depends(require_platform_principal)):
    _view(user)
    published = svc.source_snapshot().get("roleTemplates") or []
    return success({"items": published})


@router.get("/school-role-templates/{template_code}", summary="学校标准角色模板版本详情")
def school_role_template_detail(template_code: str, user=Depends(require_platform_principal)):
    _view(user)
    return success({"items": [_template_preview(row) for row in template_svc.list_versions(template_code)]})


@router.post("/school-role-templates/{template_code}/drafts", summary="从 Catalog 权限创建标准角色模板草稿")
def school_role_template_create_draft(template_code: str, body: dict = Body(...), user=Depends(require_platform_principal)):
    assert_platform_root(user)
    source = svc.source_snapshot()
    permissions = body.get("permissionCodes")
    if permissions is None:
        versions = template_svc.list_versions(template_code)
        permissions = versions[0].get("permissions") if versions else []
    row = template_svc.create_draft(
        template_code=template_code,
        template_name=body.get("templateName") or template_code,
        permission_codes=permissions,
        change_reason=body.get("reason") or "",
        source_commit_sha=source.get("provenance", {}).get("deployedCommitSha") or "",
        actor_user_id=_actor_id(user),
    )
    return success(_template_preview(row))


@router.put("/school-role-templates/{template_code}/drafts/{template_id}", summary="乐观锁更新标准角色模板草稿")
def school_role_template_update_draft(template_code: str, template_id: int, body: dict = Body(...), user=Depends(require_platform_principal)):
    assert_platform_root(user)
    current = next((row for row in template_svc.list_versions(template_code) if int(row["id"]) == template_id), None)
    if current is None:
        from app.core.exceptions import AppException
        raise AppException("DATA_NOT_FOUND", "角色模板草稿不存在", http_status=404)
    row = template_svc.update_draft(
        template_id,
        expected_version=int(body.get("expectedVersion") if body.get("expectedVersion") is not None else -1),
        permission_codes=body.get("permissionCodes") or [],
        change_reason=body.get("reason") or "",
        actor_user_id=_actor_id(user),
    )
    return success(_template_preview(row))


@router.get("/school-role-templates/{template_code}/drafts/{template_id}/impact", summary="标准角色模板权限、菜单及租户影响")
def school_role_template_impact(template_code: str, template_id: int, user=Depends(require_platform_principal)):
    _view(user)
    versions = template_svc.list_versions(template_code)
    current = next((row for row in versions if int(row["id"]) == template_id), None)
    if current is None:
        from app.core.exceptions import AppException
        raise AppException("DATA_NOT_FOUND", "角色模板版本不存在", http_status=404)
    previous = next((row for row in versions if str(row["id"]) == str(current.get("previousTemplateId"))), None)
    current_preview = _template_preview(current)
    previous_preview = _template_preview(previous) if previous else {"menuPreview": []}
    current_keys = {item["surfaceKey"] for item in current_preview["menuPreview"]}
    previous_keys = {item["surfaceKey"] for item in previous_preview["menuPreview"]}
    base = template_svc.impact(template_id)
    return success({**base, "menuAdded": sorted(current_keys - previous_keys),
                    "menuRemoved": sorted(previous_keys - current_keys),
                    "navigationDigest": current_preview["navigationDigest"],
                    "sourceDigest": current_preview["sourceDigest"]})


@router.post("/school-role-templates/{template_code}/drafts/{template_id}/publish", summary="MFA 发布不可变标准角色模板")
def school_role_template_publish(template_code: str, template_id: int, body: dict = Body(...), user=Depends(require_platform_principal)):
    assert_platform_root(user)
    assert_recent_platform_auth(user, require_mfa=True)
    from app.core.exceptions import AppException
    reason = str(body.get("reason") or "").strip()
    if len(reason) < 5:
        raise AppException("VALIDATION_ERROR", "发布原因至少 5 个字符", http_status=422)
    versions = template_svc.list_versions(template_code)
    current = next((row for row in versions if int(row["id"]) == template_id), None)
    if current is None:
        raise AppException("DATA_NOT_FOUND", "角色模板草稿不存在", http_status=404)
    source = svc.source_snapshot()
    deployed = source.get("provenance", {}).get("deployedCommitSha")
    if not deployed or current.get("sourceCommitSha") != deployed:
        raise AppException("PRODUCT_IAM_SOURCE_COMMIT_DRIFT", "模板草稿部署提交与当前服务端部署提交不一致", http_status=409)
    if body.get("sourceDigest") != source.get("sourceDigest") or body.get("navigationDigest") != source.get("navigationDigest"):
        raise AppException("PRODUCT_IAM_SOURCE_DRIFT", "权限或导航真值已变化，必须刷新 impact", http_status=409)
    if body.get("permissionDigest") != current.get("permissionDigest"):
        raise AppException("PRODUCT_IAM_TEMPLATE_DRIFT", "模板权限摘要已变化", http_status=409)
    return success(template_svc.publish_draft(
        template_id,
        expected_version=int(body.get("expectedVersion") if body.get("expectedVersion") is not None else -1),
        actor_user_id=_actor_id(user),
        change_reason=reason,
    ))


@router.post("/school-role-templates/{template_code}/rollback", summary="从已发布版本创建回滚草稿")
def school_role_template_rollback(template_code: str, body: dict = Body(...), user=Depends(require_platform_principal)):
    assert_platform_root(user)
    source_id = int(body.get("sourceTemplateId") or 0)
    source = next((row for row in template_svc.list_versions(template_code) if int(row["id"]) == source_id), None)
    if source is None:
        from app.core.exceptions import AppException
        raise AppException("DATA_NOT_FOUND", "回滚源模板不存在", http_status=404)
    row = template_svc.create_rollback_draft(
        source_id,
        change_reason=body.get("reason") or "",
        actor_user_id=_actor_id(user),
        source_commit_sha=svc.source_snapshot().get("provenance", {}).get("deployedCommitSha") or "",
    )
    return success(_template_preview(row))
