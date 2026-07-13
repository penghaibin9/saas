"""毕业设计中心请求级权限裁决。

所有 PC 毕设 router 都挂载本依赖：读请求默认 view，已冻结的业务动作使用
独立 permissionCode，其余写请求默认 manage。这使未登记的新写接口 fail-closed。
"""
from __future__ import annotations

from fastapi import Depends, Request

from app.core.permissions import enforce_permission
from app.core.exceptions import no_permission
from app.core.security import get_current_user


_ACTION_RULES: tuple[tuple[str, str, str], ...] = (
    ("/gd-plagiarism/", "/result", "graduationDesign.plagiarism.result"),
    ("/gd-plagiarism/", "/dispute/review", "graduationDesign.plagiarism.dispute.review"),
    ("/gd-plagiarism/", "/submit", "graduationDesign.plagiarism.submit"),
    ("/gd-topics/", "/submit-review", "graduationDesign.topic.submit"),
    ("/gd-topics/", "/review", "graduationDesign.topic.review"),
    ("/proposals/", "/review", "graduationDesign.proposal.review"),
    ("/finals/", "/review", "graduationDesign.final.review"),
    ("/defense-groups/", "/publish", "graduationDesign.defense.publish"),
    ("/gd-defense-scores", "", "graduationDesign.defense.score"),
    ("/gd-grades/", "/publish", "graduationDesign.grade.publish"),
    ("/gd-archives/", "/submit", "graduationDesign.archive.submit"),
    ("/gd-guidances", "", "graduationDesign.guide.manage"),
    ("/gd-reviews/", "/submit", "graduationDesign.final.review"),
)

_READ_RULES: tuple[tuple[str, str], ...] = (
    ("/graduation/batches", "graduationDesign.manage"),
    ("/graduation/gd-mentors", "graduationDesign.manage"),
    ("/graduation/gd-defense-experts", "graduationDesign.manage"),
    ("/graduation/gd-templates", "graduationDesign.manage"),
    ("/graduation/audit-logs", "graduationDesign.manage"),
    ("/gd-topic-rounds/", "graduationDesign.view"),
)


def graduation_permission_for(method: str, path: str) -> str:
    """返回请求所需 permissionCode；顺序是具体动作优先，然后通用读/写兜底。"""
    method = (method or "GET").upper()
    path = path or ""
    if method in {"GET", "HEAD", "OPTIONS"}:
        if "/gd-topic-rounds/" in path and (
            path.endswith("/capacity-conflicts") or path.endswith("/stats")
        ):
            return "graduationDesign.manage"
        for contains, code in _READ_RULES:
            if contains in path:
                return code
        return "graduationDesign.view"

    if "/export" in path or path.endswith("/export"):
        return "graduationDesign.export"

    for contains, suffix, code in _ACTION_RULES:
        if contains in path and (not suffix or path.endswith(suffix)):
            return code

    return "graduationDesign.manage"


def require_graduation_request_permission(
    request: Request,
    user: dict = Depends(get_current_user),
) -> dict:
    role = (user.get("currentRoleCode") or user.get("userType") or "").strip().upper()
    if role in {"GD_COLLEGE_ADMIN", "GD_MAJOR_ADMIN"}:
        required_claim = "collegeId" if role == "GD_COLLEGE_ADMIN" else "majorId"
        if not user.get(required_claim):
            raise no_permission(
                f"Graduation organizational scope is missing the required {required_claim} claim"
            )
    code = graduation_permission_for(request.method, request.url.path)
    return enforce_permission(user, code)
