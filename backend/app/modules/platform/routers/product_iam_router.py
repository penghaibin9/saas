"""B6 Platform Product IAM endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends

from app.core.platform_principal import require_platform_principal, assert_platform_root
from app.core.response import success
from app.modules.platform.services import platform_product_iam_service as svc

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
