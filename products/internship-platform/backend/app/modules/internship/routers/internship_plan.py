"""岗位实习中心 · 实习计划书 + 计划任务完成度 API（/api/v1/internship/plans/*、/plan-task-progress/*）。

计划书：按批次保存(草稿) → 发布(生成学生确认回执 + 任务进度) → 学生端确认/逐项打卡(mobile)。
完成度：教师/管理端列表 + 审核 + 批次汇总。数据范围与状态机由 service 处理。
PC 管理端（学生 403 由注册处 require_staff 统一门禁）。

权限（P3）：读取计划书/回执 internship.plan.view；保存/发布 internship.plan.manage；
任务完成度查询 internship.task.view；审核 internship.task.review。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Depends, Query

from app.core.permissions import require_permission
from app.core.response import paginate, success
from app.modules.internship.services import internship_plan_service as plan_svc
from app.modules.internship.services import internship_plan_task_service as task_svc

router = APIRouter(prefix="/internship", tags=["岗位实习-实习计划书"])

_P_PLAN_VIEW = "internship.plan.view"
_P_PLAN_MANAGE = "internship.plan.manage"
_P_TASK_VIEW = "internship.task.view"
_P_TASK_REVIEW = "internship.task.review"


@router.get("/plans/templates", summary="内置专业实习方案模板")
def plan_templates(user=Depends(require_permission(_P_PLAN_VIEW))):
    return success(plan_svc.list_plan_templates())


@router.get("/plans/batch/{batch_id}/context", summary="实习计划批次基本信息与同源规则")
def plan_context(batch_id: int, user=Depends(require_permission(_P_PLAN_VIEW))):
    return success(plan_svc.get_plan_context(batch_id, user=user))


@router.post("/plans/bulk-export.pdf", summary="批量导出实习计划 PDF")
def plans_bulk_export_pdf(
    body: dict = Body(...),
    user=Depends(require_permission(_P_PLAN_VIEW)),
):
    from app.modules.internship.services.internship_plan_export_options import record_export
    ids = (body or {}).get("batchIds") or []
    payload = plan_svc.bulk_export_plans_pdf(ids, user=user)
    return success(record_export(user, ids, "pdf", payload))


@router.post("/plans/bulk-export.xlsx", summary="批量导出实习计划 Excel")
def plans_bulk_export_xlsx(
    body: dict = Body(...),
    user=Depends(require_permission(_P_PLAN_VIEW)),
):
    from app.modules.internship.services.internship_plan_export_options import record_export
    ids = (body or {}).get("batchIds") or []
    payload = plan_svc.bulk_export_plans_xlsx(ids, user=user)
    return success(record_export(user, ids, "xlsx", payload))


@router.get("/plans/batch/{batch_id}", summary="按批次读取实习计划书")
def plan_get(batch_id: int, user=Depends(require_permission(_P_PLAN_VIEW))):
    return success(plan_svc.get_plan_by_batch(batch_id, user=user))


@router.post("/plans/batch/{batch_id}/export.pdf", summary="导出正式实习计划 PDF")
def plan_export_pdf(batch_id: int, user=Depends(require_permission(_P_PLAN_VIEW))):
    return success(plan_svc.export_plan_pdf(batch_id, user=user))


@router.post("/plans/batch/{batch_id}/export.xlsx", summary="导出正式实习计划 Excel")
def plan_export_xlsx(batch_id: int, user=Depends(require_permission(_P_PLAN_VIEW))):
    return success(plan_svc.export_plan_xlsx(batch_id, user=user))


@router.put("/plans/batch/{batch_id}", summary="保存/更新实习计划书（草稿；任务清单校验）")
def plan_save(batch_id: int, body: dict = Body(...), user=Depends(require_permission(_P_PLAN_MANAGE))):
    return success(plan_svc.save_plan(batch_id, body or {}, user=user))


@router.post("/plans/batch/{batch_id}/publish", summary="发布实习计划书（生成学生确认+任务进度）")
def plan_publish(batch_id: int, body: dict = Body(default={}), user=Depends(require_permission(_P_PLAN_MANAGE))):
    return success(plan_svc.publish_plan(batch_id, body or {}, user=user), message="计划书已发布")


@router.get("/plans/batch/{batch_id}/task-summary", summary="计划任务完成度汇总（按批次）")
def plan_task_summary(batch_id: int, user=Depends(require_permission(_P_TASK_VIEW))):
    return success(task_svc.batch_summary(batch_id, user=user))


@router.get("/plan-acks", summary="学生计划确认回执列表（教师/管理端，按数据范围）")
def plan_ack_list(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                  batchId: Optional[str] = None, status: Optional[str] = None,
                  keyword: Optional[str] = None, user=Depends(require_permission(_P_PLAN_VIEW))):
    items, total = plan_svc.list_acks(page, pageSize, batch_id=batchId, status=status,
                                      keyword=keyword, user=user)
    return success(paginate(items, total, page, pageSize))


@router.get("/plan-task-progress", summary="计划任务完成度列表（教师/管理端，按数据范围）")
def plan_task_progress_list(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                            batchId: Optional[str] = None, status: Optional[str] = None,
                            keyword: Optional[str] = None, taskSortOrder: Optional[int] = None,
                            user=Depends(require_permission(_P_TASK_VIEW))):
    items, total = task_svc.list_progress(page, pageSize, batch_id=batchId, status=status,
                                          keyword=keyword, task_sort_order=taskSortOrder, user=user)
    return success(paginate(items, total, page, pageSize))


@router.post("/plan-task-progress/{prog_id}/review", summary="审核学生任务完成度（APPROVE/RETURN）")
def plan_task_review(prog_id: int, body: dict = Body(...), user=Depends(require_permission(_P_TASK_REVIEW))):
    b = body or {}
    return success(task_svc.review_progress(prog_id, b.get("action", ""), b.get("comment", ""),
                                             user=user, expected_version=b.get("expectedVersion")))


@router.get('/plans/export-options', summary='批量导出计划选择器（同源权限、分页检索）')
def plan_export_options(
    page: int = Query(1, ge=1, le=100000),
    pageSize: int = Query(20, ge=1, le=50),
    keyword: str = Query('', max_length=100),
    user=Depends(require_permission(_P_PLAN_VIEW)),
):
    from app.modules.internship.services.internship_plan_export_options import list_options
    return success(list_options(user, page=page, page_size=pageSize, keyword=keyword))
