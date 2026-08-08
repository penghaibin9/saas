"""教师移动端实习周报版本化批阅权威路由。

该路由必须先于历史 ``mobile.router`` 注册。旧聚合路由暂保留兼容，但本入口负责
把列表返回的 ``version`` 原样作为 ``expectedVersion`` 送入领域乐观锁，避免并发
批阅时由服务端偷取最新版本而绕过 stale-client 检测。
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends

from app.core.permissions import require_module
from app.core.response import success
from app.core.security import get_current_user
from app.services import mobile_teacher_service as tea

router = APIRouter(
    prefix="/mobile/teacher/internship",
    tags=["教师移动端-岗位实习"],
    dependencies=[Depends(require_module("internship"))],
)


@router.post(
    "/weekly/{report_id}/review",
    summary="教师·实习周报批阅（版本化、范围校验+审计）",
)
def teacher_weekly_review_versioned(
    report_id: str,
    body: dict = Body(...),
    user=Depends(get_current_user),
):
    return success(
        tea.weekly_review(
            user,
            report_id,
            str(body.get("action") or "").upper(),
            body.get("comment") or "",
            expected_version=body.get("expectedVersion"),
        ),
        message="批阅完成",
    )
