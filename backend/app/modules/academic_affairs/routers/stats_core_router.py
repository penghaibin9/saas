"""D9-S6 教务统计公开 Router：从 legacy academic_affairs Move Only。

同步 `/stats/export` 不在本 Router 接管，继续由 academic_export_compat_router
进入 ExportJob/FileObject；冻结快照继续由 stats_snapshot_router 持有。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.core.permissions import require_permission
from app.core.response import paginate, success
from app.modules.academic_affairs.services import academic_affairs_stats_service as stats_svc


router = APIRouter(prefix="/academic-affairs", tags=["教务中心"])
_STATS_VIEW = "academicAffairs.stats.view"


@router.get("/stats/overview", summary="教务统计总览（15 项指标，真实聚合）")
def stats_overview(termId: Optional[int] = None, collegeId: Optional[int] = None,
                   majorId: Optional[int] = None, user=Depends(require_permission(_STATS_VIEW))):
    return success(stats_svc.overview(user, termId, collegeId, majorId))


@router.get("/stats/filters", summary="统计筛选器候选（学期/学院/专业，受数据范围收敛）")
def stats_filters(user=Depends(require_permission(_STATS_VIEW))):
    return success(stats_svc.filters(user))


@router.get("/stats/registration", summary="注册统计下钻：未注册学生名单（脱敏+审计）")
def stats_registration(termId: Optional[int] = None, collegeId: Optional[int] = None,
                       majorId: Optional[int] = None, page: int = Query(1, ge=1),
                       pageSize: int = Query(20, ge=1, le=200),
                       user=Depends(require_permission(_STATS_VIEW))):
    items, total = stats_svc.registration_unregistered(user, termId, collegeId, majorId, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/stats/status-change", summary="学籍统计下钻：EFFECTIVE 异动明细")
def stats_status_change(changeType: Optional[str] = None, termId: Optional[int] = None,
                        collegeId: Optional[int] = None, page: int = Query(1, ge=1),
                        pageSize: int = Query(20, ge=1, le=200),
                        user=Depends(require_permission(_STATS_VIEW))):
    items, total = stats_svc.status_change_detail(user, changeType, termId, collegeId, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/stats/warning", summary="学业预警统计下钻：非 CLOSED 预警明细（脱敏+审计）")
def stats_warning(level: Optional[str] = None, source: Optional[str] = None,
                  collegeId: Optional[int] = None, page: int = Query(1, ge=1),
                  pageSize: int = Query(20, ge=1, le=200),
                  user=Depends(require_permission(_STATS_VIEW))):
    items, total = stats_svc.warning_detail(user, level, source, collegeId, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/stats/status-change/summary", summary="学籍统计聚合（按 change_type 分组）")
def stats_status_change_summary(termId: Optional[int] = None, collegeId: Optional[int] = None,
                                user=Depends(require_permission(_STATS_VIEW))):
    return success(stats_svc.status_change_stats(user, termId, collegeId))


@router.get("/stats/registration/summary", summary="注册统计聚合（完成率）")
def stats_registration_summary(termId: Optional[int] = None, collegeId: Optional[int] = None,
                               majorId: Optional[int] = None,
                               user=Depends(require_permission(_STATS_VIEW))):
    return success(stats_svc.registration_stats(user, termId, collegeId, majorId))


@router.get("/stats/course", summary="课程统计聚合（按类别/学院双维）")
def stats_course(category: Optional[str] = None, collegeId: Optional[int] = None,
                 user=Depends(require_permission(_STATS_VIEW))):
    return success(stats_svc.course_stats(user, category, collegeId))


@router.get("/stats/course/detail", summary="课程统计下钻：ENABLED 课程明细")
def stats_course_detail(category: Optional[str] = None, collegeId: Optional[int] = None,
                        page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                        user=Depends(require_permission(_STATS_VIEW))):
    items, total = stats_svc.course_detail(user, category, collegeId, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/stats/teaching-task", summary="教学任务统计聚合（确认完成率）")
def stats_teaching_task(collegeId: Optional[int] = None, termId: Optional[int] = None,
                        user=Depends(require_permission(_STATS_VIEW))):
    return success(stats_svc.teaching_task_stats(user, collegeId, termId))


@router.get("/stats/teaching-task/pending", summary="教学任务统计下钻：未确认任务清单")
def stats_teaching_task_pending(collegeId: Optional[int] = None, termId: Optional[int] = None,
                                page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                                user=Depends(require_permission(_STATS_VIEW))):
    items, total = stats_svc.teaching_task_pending(user, collegeId, termId, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/stats/schedule", summary="课表统计聚合（发布覆盖率+未解决冲突数）")
def stats_schedule(collegeId: Optional[int] = None, termId: Optional[int] = None,
                   user=Depends(require_permission(_STATS_VIEW))):
    return success(stats_svc.schedule_stats(user, collegeId, termId))


@router.get("/stats/schedule/conflicts", summary="课表统计下钻：冲突明细")
def stats_schedule_conflicts(collegeId: Optional[int] = None, termId: Optional[int] = None,
                             page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                             user=Depends(require_permission(_STATS_VIEW))):
    items, total = stats_svc.schedule_conflicts(user, collegeId, termId, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/stats/grade", summary="成绩统计聚合（挂科率+录入发布率+补考重修人数）")
def stats_grade(termId: Optional[int] = None, collegeId: Optional[int] = None,
                user=Depends(require_permission(_STATS_VIEW))):
    return success(stats_svc.grade_stats(user, termId, collegeId))


@router.get("/stats/grade/detail", summary="成绩统计下钻：挂科学生明细（脱敏+审计）")
def stats_grade_detail(termId: Optional[int] = None, collegeId: Optional[int] = None,
                       courseName: Optional[str] = None, page: int = Query(1, ge=1),
                       pageSize: int = Query(20, ge=1, le=200),
                       user=Depends(require_permission(_STATS_VIEW))):
    items, total = stats_svc.grade_detail(user, termId, collegeId, courseName, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/stats/warning/summary", summary="学业预警统计聚合（按等级/来源双维）")
def stats_warning_summary(termId: Optional[int] = None, collegeId: Optional[int] = None,
                          user=Depends(require_permission(_STATS_VIEW))):
    return success(stats_svc.warning_stats(user, termId, collegeId))


@router.get("/stats/graduation", summary="毕业资格统计聚合（通过率+异常项分布）")
def stats_graduation(batchId: Optional[int] = None, collegeId: Optional[int] = None,
                     user=Depends(require_permission(_STATS_VIEW))):
    return success(stats_svc.graduation_stats(user, batchId, collegeId))


@router.get("/stats/graduation/abnormal", summary="毕业资格统计下钻：异常项学生名单（脱敏+审计）")
def stats_graduation_abnormal(batchId: Optional[int] = None, collegeId: Optional[int] = None,
                              itemType: Optional[str] = None, page: int = Query(1, ge=1),
                              pageSize: int = Query(20, ge=1, le=200),
                              user=Depends(require_permission(_STATS_VIEW))):
    items, total = stats_svc.graduation_abnormal(user, batchId, collegeId, itemType, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/stats/workload", summary="教师工作量统计聚合（基础参考非正式核算）")
def stats_workload(termId: Optional[int] = None, collegeId: Optional[int] = None,
                   user=Depends(require_permission(_STATS_VIEW))):
    return success(stats_svc.workload_stats(user, termId, collegeId))


@router.get("/stats/workload/detail", summary="教师工作量统计下钻：单教师授课明细")
def stats_workload_detail(teacherKey: str, collegeId: Optional[int] = None,
                          page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                          user=Depends(require_permission(_STATS_VIEW))):
    items, total = stats_svc.workload_detail(user, teacherKey, collegeId, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/stats/course-selection", summary="选课统计聚合（跨批次容量/已选/填充率）")
def stats_course_selection(termId: Optional[int] = None, collegeId: Optional[int] = None,
                           user=Depends(require_permission(_STATS_VIEW))):
    return success(stats_svc.course_selection_stats(user, termId, collegeId))


@router.get("/stats/course-selection/detail", summary="选课统计下钻：低人数课程清单")
def stats_course_selection_detail(termId: Optional[int] = None, collegeId: Optional[int] = None,
                                  page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                                  user=Depends(require_permission(_STATS_VIEW))):
    items, total = stats_svc.course_selection_detail(user, termId, collegeId, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/stats/exam", summary="考务统计聚合（跨批次课程确认率+缺考/违纪）")
def stats_exam(termId: Optional[int] = None, collegeId: Optional[int] = None,
               user=Depends(require_permission(_STATS_VIEW))):
    return success(stats_svc.exam_stats(user, termId, collegeId))


@router.get("/stats/exam/detail", summary="考务统计下钻：缺考/违纪明细（脱敏+审计）")
def stats_exam_detail(termId: Optional[int] = None, collegeId: Optional[int] = None,
                      incidentType: Optional[str] = None, page: int = Query(1, ge=1),
                      pageSize: int = Query(20, ge=1, le=200),
                      user=Depends(require_permission(_STATS_VIEW))):
    items, total = stats_svc.exam_detail(user, termId, collegeId, incidentType, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/stats/resource", summary="教学资源统计聚合（教室状态/类型+预约状态分布）")
def stats_resource(user=Depends(require_permission(_STATS_VIEW))):
    return success(stats_svc.resource_stats(user))


@router.get("/stats/resource/detail", summary="教学资源统计下钻：待审核教室预约清单")
def stats_resource_detail(page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=200),
                          user=Depends(require_permission(_STATS_VIEW))):
    items, total = stats_svc.resource_detail(user, page, pageSize)
    return success(paginate(items, total, page, pageSize))
