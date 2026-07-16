"""域级请求权限裁决（生产级审计 P1-1/P1-2 整改）。

迎新 / 就业 / 旧学业域此前仅有身份门禁（require_staff 只拦学生），租户内任意
教职工（宿管、任课老师、实习导师…）都能读全量新生隐私、改就业去向。本模块
按毕设中心 require_graduation_request_permission 的成熟模式收口：

- 读请求（GET/HEAD/OPTIONS）→ <domain>.view
- 导出（路径含 /export）    → <domain>.export
- 其余写请求                → <domain>.manage（fail-closed：新写端点不登记也默认要 manage）

授予关系沿用 core/permissions.py 的 ROLE_PERMISSIONS 通配体系：
- studentAffairs.orientation.* → 学工处/学院/校管理员命中 studentAffairs.* 通配；
- employment.*                 → 就业老师 EMPLOYMENT_TEACHER 已有 employment.* 授予；
- academicAffairs.*            → 教务老师/教务处/学院命中 academicAffairs.* 通配。
宿管（仅 dorm 域）、实习导师、任课教师等不再命中——这正是本次要堵住的越权面。
数据范围（本班/本院）另由各 service 层 scope 收敛，本模块只裁能力边界。
"""
from __future__ import annotations

from fastapi import Depends, Request

from app.core.permissions import enforce_permission
from app.core.security import get_current_user, require_staff


def make_domain_request_permission(domain: str, *, staff_only: bool = True):
    """返回 FastAPI 依赖：按请求方法/路径裁决 <domain>.view/export/manage。

    staff_only=True 时先过 require_staff（学生令牌一律 403），
    与既有端点级 require_staff 叠加是幂等的。
    """

    def _permission_for(method: str, path: str) -> str:
        if (method or "GET").upper() in {"GET", "HEAD", "OPTIONS"}:
            return f"{domain}.view"
        if "/export" in (path or ""):
            return f"{domain}.export"
        return f"{domain}.manage"

    if staff_only:
        def dep(request: Request, user: dict = Depends(require_staff)) -> dict:
            return enforce_permission(user, _permission_for(request.method, request.url.path))
    else:
        def dep(request: Request, user: dict = Depends(get_current_user)) -> dict:
            return enforce_permission(user, _permission_for(request.method, request.url.path))
    return dep


require_orientation_request_permission = make_domain_request_permission("studentAffairs.orientation")
require_employment_request_permission = make_domain_request_permission("employment")
# /api/v1/academic/*（学业过程：学业台账/成绩/补考重修/预警）——教务域能力
require_academic_process_request_permission = make_domain_request_permission("academicAffairs.process")
