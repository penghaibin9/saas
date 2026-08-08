"""教师移动端实习周报工作区与版本化批阅权威路由。

该路由必须先于历史 ``mobile.router`` 注册。旧聚合路由暂保留兼容，但本入口负责：

- GET 工作区显式要求 ``batchId``，从领域第一层就透传 authenticated actor；
- 领域服务按稳定 ``advisor_user_id`` / 数据范围收敛，避免 legacy 二次姓名过滤把
  已正确授权的指导教师记录误删成空队列；
- 列表返回的 ``version`` 原样作为 ``expectedVersion`` 送入领域乐观锁，避免并发
  批阅时由服务端偷取最新版本而绕过 stale-client 检测。
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query

from app.core.permissions import require_module
from app.core.response import success
from app.core.security import get_current_user
from app.modules.internship.services import internship_service
from app.services import mobile_teacher_service as tea

router = APIRouter(
    prefix="/mobile/teacher/internship",
    tags=["教师移动端-岗位实习"],
    dependencies=[Depends(require_module("internship"))],
)


@router.get("", summary="教师·实习批阅工作区（显式批次、权威范围）")
def teacher_internship_dashboard_versioned(
    batchId: str = Query(..., min_length=1),
    user=Depends(get_current_user),
):
    """返回当前教师在指定批次真正可处理的周报/打卡异常。

    ``list_weekly_reports`` / ``list_attendance_exceptions`` 自己就是岗位实习域的
    权威范围入口，内部优先按 ``advisor_user_id`` 等稳定关系判定。这里不再做第二轮
    仅姓名过滤；否则会把领域层已经正确授权的记录重新误判为空。
    """
    scope = tea.resolve_teacher_scope(user)
    reports, _ = internship_service.list_weekly_reports(
        1, 50, status="PENDING_REVIEW", batch_id=batchId, user=user)
    overdue, _ = internship_service.list_weekly_reports(
        1, 50, status="OVERDUE", batch_id=batchId, user=user)
    exceptions, _ = internship_service.list_attendance_exceptions(
        1, 50, status="PENDING_HANDLE", batch_id=batchId, user=user)

    seen = {str(row.get("id")) for row in reports}
    for row in overdue:
        key = str(row.get("id"))
        if key not in seen:
            reports.append(row)
            seen.add(key)

    return success({
        "hasData": bool(reports or exceptions),
        "weeklyReports": reports,
        "abnormalCheckins": exceptions,
        # 只返回当前 actor + 当前 batch 的真实队列计数，不混入租户全局统计。
        "stats": {
            "pendingReports": len(reports),
            "abnormal": len(exceptions),
        },
        "scopeMode": scope.get("mode"),
        "available": True,
        "errors": [],
        "batchId": str(batchId),
    })


@router.post(
    "/weekly/{report_id}/review",
    summary="教师·实习周报批阅（版本化、范围校验+审计）",
)
def teacher_weekly_review_versioned(
    report_id: str,
    body: dict = Body(...),
    user=Depends(get_current_user),
):
    """直接复用岗位实习领域的稳定主体范围校验与乐观锁。

    权威领域服务已经按 ``advisor_user_id`` 判定 owner；这里不得再经过 legacy facade
    的姓名二次校验，否则两名同名指导教师会把合法的稳定 ID 授权误判成 403。
    """
    action = str(body.get("action") or "").upper()
    comment = body.get("comment") or ""
    result = internship_service.review_weekly_report(
        report_id,
        action,
        comment,
        user=user,
        expected_version=body.get("expectedVersion"),
    )
    # 保留移动端操作审计；领域内部同时写 InternshipAuditTrail，二者职责不同。
    from app.services import audit_log
    audit_log.record(
        "MOBILE_WEEKLY_REVIEW",
        f"internship/weekly:{report_id}",
        detail={
            "operator": user.get("realName"),
            "action": action,
            "comment": comment[:200],
        },
    )
    return success(result, message="批阅完成")
