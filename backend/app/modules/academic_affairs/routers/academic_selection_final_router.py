"""Stage D / D6：Selection Final 精确入口 + 选课域结构聚合锚点。

四条最终入口继续直接接 ``academic_affairs_selection_final_service``，确保 canonical
校验、行锁、Stage C2 学籍事实和 DecisionTrace 真正进入正式 API。D6-S 仅把其余
选课管理 HTTP owner 从历史大 Router Move Only 迁到 ``course_selection_router``；
canonical service、权限、DTO、状态机和 TeachingRoster 投影均不改变。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Path, Query

from app.core.permissions import require_permission
from app.modules.academic_affairs.routers import academic_affairs as base
from app.modules.academic_affairs.services import academic_affairs_selection_final_service as selection_final

router = APIRouter(prefix="/academic-affairs", tags=["教务中心·选课最终入口"])


@router.get("/selection/batches/{batchId}/preflight", summary="批次生命周期预检（纯读）")
def sel_batch_preflight(
    batchId: int = Path(...),
    action: str = Query(..., pattern="^(PUBLISH|OPEN|CLOSE|LOCK)$"),
    user=Depends(require_permission(base._SEL_VIEW)),
):
    return base.success(selection_final.batch_preflight(user, batchId, action))


@router.post("/selection/batches/{batchId}/publish", summary="发布批次（最终服务）")
def sel_batch_publish(
    batchId: int = Path(...),
    user=Depends(require_permission(base._SEL_MANAGE)),
):
    return base.success(selection_final.publish_batch(user, batchId), message="已发布")


@router.get("/selection/student/courses", summary="学生端可选课程+实时余量（最终服务）")
def sel_student_courses(
    batchId: Optional[str] = None,
    user=Depends(base._require_student),
):
    return base.success({"items": selection_final.student_courses(user, batchId)})


@router.post("/selection/student/preflight", summary="学生选课预检（纯读+DecisionTrace）")
def sel_student_preflight(
    body: base.EnrollBody,
    user=Depends(base._require_student),
):
    return base.success(selection_final.student_preflight(user, body))


@router.post("/selection/student/enroll", summary="学生选课（最终服务+DecisionTrace）")
def sel_student_enroll(
    body: base.EnrollBody,
    user=Depends(base._require_student),
):
    return base.success(selection_final.student_enroll(user, body), message="选课成功")


@router.post("/selection/student/drop", summary="学生退课（最终服务）")
def sel_student_drop(
    body: base.EnrollBody,
    user=Depends(base._require_student),
):
    return base.success(selection_final.student_drop(user, body), message="退课成功")


# D6-S Move Only：academic_affairs_bundle 已保证本模块整体先于 legacy 大 Router 挂载。
# 将非 Final 的选课管理路由作为同一域 surface 追加到此预 legacy 锚点；二者路径无重叠，
# 因而 Selection Final 四入口仍保持唯一 owner，其他 selection shape 则切到独立 Router。
from app.modules.academic_affairs.routers import course_selection_router as course_selection_router  # noqa: E402

router.routes.extend(course_selection_router.router.routes)
