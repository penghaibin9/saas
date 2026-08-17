"""D6-S 选课管理 Move Only 正式 Router。

Selection Final 的四条最终入口（批次发布、学生可选课程、选课、退课）继续由
``academic_selection_final_router`` + ``academic_affairs_selection_final_service``
唯一持有；本 Router 只迁 legacy base 中其余选课管理、课程供给、名单、补选、
统计、归档与轮次入口。

B-W4 起，课程供给写动作由 ``academic_affairs_selection_course_command_service``
单一持有：新增必须 TeachingTask 必填、READY、same-course、same-term；编辑容量/
取消开课也必须走 canonical term guard + locking command，不得回落 legacy core 写实现。
其余 canonical service、权限、DTO、状态机、TeachingRoster 投影保持不变。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Path, Query

from app.core.permissions import require_permission
from app.core.response import paginate, success
from app.modules.academic_affairs.routers import academic_affairs as legacy
from app.modules.academic_affairs.services import academic_affairs_production_audit_guard as production_guard
from app.modules.academic_affairs.services import academic_affairs_selection_course_command_service as selection_course_command_svc

# PR #101 production-audit hardening. Idempotent and read-side only: this tightens
# D6-D8 scope/page-size contracts without changing any canonical write owner.
production_guard.install()

router = APIRouter(prefix="/academic-affairs", tags=["教务中心·选课管理"])

# Move Only：沿用历史 DTO / permission key / canonical service 对象，结构拆分不得产生第二套业务真值。
SelectionBatchBody = legacy.SelectionBatchBody
SelectionRuleBody = legacy.SelectionRuleBody
SelectionCourseBody = legacy.SelectionCourseBody
SelectionCourseUpdate = legacy.SelectionCourseUpdate
AdjustBody = legacy.AdjustBody
SelectionRoundBody = legacy.SelectionRoundBody

_SEL_VIEW = legacy._SEL_VIEW
_SEL_MANAGE = legacy._SEL_MANAGE
_SEL_RULE = legacy._SEL_RULE
_SEL_ADJUST = legacy._SEL_ADJUST
_SEL_LOCK = legacy._SEL_LOCK
_SEL_ROSTER = legacy._SEL_ROSTER

_require_student = legacy._require_student
selection_svc = legacy.selection_svc
selection_round_svc = legacy.selection_round_svc


# ── 批次（发布由 Selection Final owner 持有） ──
@router.post("/selection/batches", summary="建选课批次")
def sel_batch_create(body: SelectionBatchBody, user=Depends(require_permission(_SEL_MANAGE))):
    return success(selection_svc.create_batch(user, body), message="已创建")


@router.get("/selection/batches", summary="选课批次列表")
def sel_batches(
    status: Optional[str] = None,
    termId: Optional[str] = None,
    page: int = 1,
    pageSize: int = 20,
    user=Depends(require_permission(_SEL_VIEW)),
):
    items, total = selection_svc.list_batches(user, status, termId, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/selection/batches/{batchId}", summary="批次详情")
def sel_batch_detail(batchId: int = Path(...), user=Depends(require_permission(_SEL_VIEW))):
    return success(selection_svc.get_batch(user, batchId))


@router.post("/selection/batches/{batchId}/open", summary="开选（PUBLISHED→OPEN）")
def sel_batch_open(batchId: int = Path(...), user=Depends(require_permission(_SEL_MANAGE))):
    return success(selection_svc.open_batch(user, batchId), message="已开选")


@router.post("/selection/batches/{batchId}/close", summary="截止（OPEN→CLOSED）")
def sel_batch_close(batchId: int = Path(...), user=Depends(require_permission(_SEL_MANAGE))):
    return success(selection_svc.close_batch(user, batchId), message="已截止")


@router.post("/selection/batches/{batchId}/lock", summary="锁定名单（CLOSED→LOCKED）")
def sel_batch_lock(batchId: int = Path(...), user=Depends(require_permission(_SEL_LOCK))):
    return success(selection_svc.lock_batch(user, batchId), message="已锁定")


@router.post("/selection/batches/{batchId}/archive", summary="归档（LOCKED→ARCHIVED）")
def sel_batch_archive(batchId: int = Path(...), user=Depends(require_permission(_SEL_MANAGE))):
    return success(selection_svc.archive_batch(user, batchId), message="已归档")


@router.put("/selection/batches/{batchId}/rule", summary="保存选课规则")
def sel_rule_save(
    body: SelectionRuleBody,
    batchId: int = Path(...),
    user=Depends(require_permission(_SEL_RULE)),
):
    return success(selection_svc.save_rule(user, batchId, body.rule), message="已保存")


# ── 课程供给 ──
@router.post("/selection/batches/{batchId}/courses", summary="新增可选课程（TeachingTask-bound）")
def sel_course_add(
    body: SelectionCourseBody,
    batchId: int = Path(...),
    user=Depends(require_permission(_SEL_MANAGE)),
):
    return success(selection_course_command_svc.add_course(user, batchId, body), message="已添加")


@router.get("/selection/batches/{batchId}/courses", summary="批次课程供给列表")
def sel_course_list(
    batchId: int = Path(...),
    page: int = 1,
    pageSize: int = 50,
    user=Depends(require_permission(_SEL_VIEW)),
):
    items, total = selection_svc.list_courses(user, batchId, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.put("/selection/courses/{courseId}", summary="编辑容量/下限")
def sel_course_update(
    body: SelectionCourseUpdate,
    courseId: int = Path(...),
    user=Depends(require_permission(_SEL_MANAGE)),
):
    return success(selection_course_command_svc.update_course(user, courseId, body), message="已保存")


@router.post("/selection/courses/{courseId}/cancel", summary="人工取消开课（人数不足）")
def sel_course_cancel(courseId: int = Path(...), user=Depends(require_permission(_SEL_MANAGE))):
    return success(selection_course_command_svc.cancel_course(user, courseId), message="已取消开课")


@router.get("/selection/courses/{courseId}/roster", summary="选课名单（教师按授课关系收敛）")
def sel_course_roster(
    courseId: int = Path(...),
    page: int = 1,
    pageSize: int = 50,
    user=Depends(require_permission(_SEL_ROSTER)),
):
    items, total = selection_svc.course_roster(user, courseId, page, pageSize)
    return success(paginate(items, total, page, pageSize))


# ── 学生读侧（可选课程/选课/退课由 Selection Final owner 持有） ──
@router.get("/selection/student/my", summary="我的选课记录")
def sel_student_my(batchId: Optional[str] = None, user=Depends(_require_student)):
    return success({"items": selection_svc.my_selections(user, batchId)})


# ── 教务处调整 / 补选 / 统计 ──
@router.post("/selection/records/{recordId}/adjust", summary="LOCKED 后人工调整退课（原因≥5字）")
def sel_record_adjust(
    body: AdjustBody,
    recordId: int = Path(...),
    user=Depends(require_permission(_SEL_ADJUST)),
):
    return success(selection_svc.adjust_record(user, recordId, body.reason), message="已调整")


@router.get("/selection/batches/{batchId}/reselect-guide", summary="补选指引（CLOSED 批次，教务处视角）")
def sel_reselect_guide(batchId: int = Path(...), user=Depends(require_permission(_SEL_VIEW))):
    return success(selection_svc.reselect_guide(user, batchId))


@router.get("/selection/student/reselect-guide", summary="补选指引（学生本人待补选记录+可选课程，06号卡）")
def sel_student_reselect_guide(batchId: Optional[str] = None, user=Depends(_require_student)):
    return success({"items": selection_svc.student_reselect_guide(user, batchId)})


@router.get("/selection/batches/{batchId}/stats", summary="选课统计")
def sel_stats(batchId: int = Path(...), user=Depends(require_permission(_SEL_VIEW))):
    return success(selection_svc.batch_stats(user, batchId))


@router.get("/selection/batches/{batchId}/conflict-report", summary="冲突预警报表（SQL 聚合 + 分页钻取）")
def sel_conflict_report(
    batchId: int = Path(...),
    studentNo: Optional[str] = Query(None, max_length=50),
    page: int = Query(1, ge=1),
    pageSize: int = Query(50, ge=1, le=200),
    user=Depends(require_permission(_SEL_VIEW)),
):
    return success(selection_svc.get_conflict_report(user, batchId, studentNo, page, pageSize))


@router.post("/selection/time-tick", summary="定时触发：到点自动开选/截止（供 cron 调度，幂等）")
def sel_time_tick(user=Depends(require_permission(_SEL_MANAGE))):
    return success(selection_svc.run_time_tick(user), message="已执行时间触发")


# ── 选课归档（导出由 academic_export_compat_router owner 持有） ──
@router.get("/selection/archive", summary="归档批次列表（仅 ARCHIVED，12号卡）")
def sel_archive_list(
    termId: Optional[str] = None,
    page: int = 1,
    pageSize: int = 20,
    user=Depends(require_permission(_SEL_MANAGE)),
):
    items, total = selection_svc.list_archived_batches(user, termId, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/selection/archive/{batchId}", summary="归档批次详情（含统计，非 ARCHIVED 409）")
def sel_archive_detail(batchId: int = Path(...), user=Depends(require_permission(_SEL_MANAGE))):
    return success(selection_svc.archive_detail(user, batchId))


# ── 选课轮次与抽签 ──
@router.post("/selection/batches/{bid}/rounds", summary="新增选课轮次")
def sel_round_create(
    body: SelectionRoundBody,
    bid: int = Path(...),
    user=Depends(require_permission(_SEL_RULE)),
):
    return success(selection_round_svc.create_round(user, bid, body), message="已创建轮次")


@router.get("/selection/batches/{bid}/rounds", summary="轮次列表")
def sel_rounds(bid: int = Path(...), user=Depends(require_permission(_SEL_VIEW))):
    return success({"items": selection_round_svc.list_rounds(user, bid)})


@router.post("/selection/rounds/{rid}/open", summary="开启轮次（同批次同时仅一个 OPEN）")
def sel_round_open(rid: int = Path(...), user=Depends(require_permission(_SEL_RULE))):
    return success(selection_round_svc.open_round(user, rid), message="轮次已开启")


@router.post("/selection/rounds/{rid}/close", summary="关闭轮次")
def sel_round_close(rid: int = Path(...), user=Depends(require_permission(_SEL_RULE))):
    return success(selection_round_svc.close_round(user, rid), message="轮次已关闭")


@router.post("/selection/rounds/{rid}/draw", summary="抽签摇号（仅 CLOSED 的 LOTTERY 轮，一次性）")
def sel_round_draw(rid: int = Path(...), user=Depends(require_permission(_SEL_RULE))):
    result = selection_round_svc.draw_round(user, rid)
    return success(result, message=f"摇号完成：中签 {result['totalWinners']}，未中签 {result['totalLosers']}")
