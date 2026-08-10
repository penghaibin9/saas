"""Stage D：选课最终服务精确路径适配 Router。

历史大 Router 仍保留原路由定义以降低长期分支冲突；本 Router 由
``academic_affairs_bundle`` 在历史 Router 之前注册，只遮蔽最终服务已明确
收口的四条路径。这里不执行任何选课规则、不构造 DecisionTrace，只把 HTTP
入口接到 ``academic_affairs_selection_final_service``，确保 canonical 校验、
行锁、Stage C2 学籍事实和 Stage D 解释层真正进入正式 API。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Path

from app.core.permissions import require_permission
from app.modules.academic_affairs.routers import academic_affairs as base
from app.modules.academic_affairs.services import academic_affairs_selection_final_service as selection_final

router = APIRouter(prefix="/academic-affairs", tags=["教务中心·选课最终入口"])


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
