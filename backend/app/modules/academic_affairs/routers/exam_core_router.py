"""D7-S/D7-U 考务主链 Router。

D7-S 迁出 legacy 大 Router 已有考务主链；D7-U 只叠加候选/preview/readiness 便利性，
最终考试写入仍复用原 canonical exam facade，不接管 mobile exam-v2 或异常 resolve 扩展入口。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel

from app.core.permissions import require_any_permission, require_permission
from app.core.response import paginate, success
from app.modules.academic_affairs.routers import academic_affairs as legacy
from app.modules.academic_affairs.services import exam_convenience_service as exam_convenience

router = APIRouter(prefix="/academic-affairs", tags=["教务中心-考务"])

ExamBatchBody = legacy.ExamBatchBody
ExamCourseBody = legacy.ExamCourseBody
ExamConfirmBody = legacy.ExamConfirmBody
ExamScheduleBody = legacy.ExamScheduleBody
ExamRoomBody = legacy.ExamRoomBody
SeatAssignBody = legacy.SeatAssignBody
InvigilatorBody = legacy.InvigilatorBody
ChangeInvigilatorBody = legacy.ChangeInvigilatorBody
ExamAutoTimesBody = legacy.ExamAutoTimesBody
PatrolBody = legacy.PatrolBody
ChangePatrolBody = legacy.ChangePatrolBody
IncidentBody = legacy.IncidentBody
DeferApplyBody = legacy.DeferApplyBody
DeferReviewBody = legacy.DeferReviewBody

exam_svc = legacy.exam_svc
autoexam_svc = legacy.autoexam_svc
_require_student = legacy._require_student
_EXAM_MANAGE = legacy._EXAM_MANAGE
_EXAM_ARRANGE = legacy._EXAM_ARRANGE
_EXAM_PUBLISH = legacy._EXAM_PUBLISH
_EXAM_VIEW = legacy._EXAM_VIEW
_EXAM_ABNORMAL = legacy._EXAM_ABNORMAL
_DEFER_COUNSELOR = legacy._DEFER_COUNSELOR
_DEFER_REVIEW = legacy._DEFER_REVIEW


class BulkCourseBody(BaseModel):
    teachingTaskIds: list[int | str]


class PreviewConfirmBody(BaseModel):
    previewToken: str


@router.post("/exam/batches", summary="建考试批次")
def exam_batch_create(body: ExamBatchBody, user=Depends(require_permission(_EXAM_MANAGE))):
    return success(exam_svc.create_batch(user, body), message="已创建")


@router.get("/exam/batches", summary="考试批次列表")
def exam_batches(
    status: Optional[str] = None,
    page: int = 1,
    pageSize: int = 20,
    user=Depends(require_permission(_EXAM_VIEW)),
):
    items, total = exam_svc.list_batches(user, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/exam/batches/{bid}", summary="批次详情")
def exam_batch_detail(bid: int = Path(...), user=Depends(require_permission(_EXAM_VIEW))):
    return success(exam_svc.get_batch(user, bid))


@router.post("/exam/batches/{bid}/courses", summary="圈定考试课程（从教学任务）")
def exam_course_add(
    body: ExamCourseBody,
    bid: int = Path(...),
    user=Depends(require_permission(_EXAM_MANAGE)),
):
    return success(exam_svc.add_exam_course(user, bid, body), message="已圈定")


@router.get("/exam/batches/{bid}/courses", summary="批次考试课程列表")
def exam_courses(
    bid: int = Path(...),
    page: int = 1,
    pageSize: int = 100,
    user=Depends(require_permission(_EXAM_VIEW)),
):
    items, total = exam_convenience.list_courses(user, bid, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/exam/batches/{bid}/course-candidates", summary="批量圈定应考课程候选")
def exam_course_candidates(
    bid: int = Path(...),
    keyword: Optional[str] = None,
    page: int = 1,
    pageSize: int = 20,
    user=Depends(require_permission(_EXAM_MANAGE)),
):
    items, total = exam_convenience.list_course_candidates(
        bid, user, keyword=keyword, page=page, page_size=pageSize
    )
    return success(paginate(items, total, page, pageSize))


@router.post("/exam/batches/{bid}/course-candidates/preview", summary="批量圈课预览")
def exam_course_preview(
    body: BulkCourseBody,
    bid: int = Path(...),
    user=Depends(require_permission(_EXAM_MANAGE)),
):
    return success(exam_convenience.bulk_course_preview(bid, user, body.teachingTaskIds))


@router.post("/exam/batches/{bid}/course-candidates/confirm", summary="批量圈课确认")
def exam_course_confirm_bulk(
    body: PreviewConfirmBody,
    bid: int = Path(...),
    user=Depends(require_permission(_EXAM_MANAGE)),
):
    return success(exam_convenience.bulk_course_confirm(bid, user, body.previewToken))


@router.get("/exam/batches/{bid}/readiness", summary="考务批次发布就绪摘要")
def exam_batch_readiness(bid: int = Path(...), user=Depends(require_permission(_EXAM_VIEW))):
    return success(exam_convenience.batch_readiness(bid, user))


@router.post("/exam/courses/{cid}/confirm", summary="学院确认/退回考试课程")
def exam_course_confirm(
    body: ExamConfirmBody,
    cid: int = Path(...),
    user=Depends(require_permission(_EXAM_MANAGE)),
):
    return success(exam_svc.confirm_course(user, cid, body.action), message="已处理")


@router.put("/exam/courses/{cid}/schedule", summary="设置考试时间/时长")
def exam_course_schedule(
    body: ExamScheduleBody,
    cid: int = Path(...),
    user=Depends(require_permission(_EXAM_ARRANGE)),
):
    return success(exam_svc.set_course_schedule(user, cid, body), message="已保存")


@router.post("/exam/batches/{bid}/confirm-courses", summary="课程确认完成，推进 DRAFT→COURSE_CONFIRMED")
def exam_confirm_courses(bid: int = Path(...), user=Depends(require_permission(_EXAM_MANAGE))):
    return success(exam_svc.confirm_batch_courses(user, bid), message="已推进")


@router.post("/exam/courses/{cid}/rooms", summary="添加考场")
def exam_room_add(
    body: ExamRoomBody,
    cid: int = Path(...),
    user=Depends(require_permission(_EXAM_ARRANGE)),
):
    return success(exam_svc.add_room(user, cid, body), message="已添加")


@router.get("/exam/courses/{cid}/rooms", summary="考场列表")
def exam_rooms(cid: int = Path(...), user=Depends(require_permission(_EXAM_VIEW))):
    return success({"items": exam_svc.list_rooms(user, cid)})


@router.post("/exam/rooms/{roomId}/seats", summary="一键铺位（按学号/随机）")
def exam_seats_assign(
    body: SeatAssignBody,
    roomId: int = Path(...),
    user=Depends(require_permission(_EXAM_ARRANGE)),
):
    return success(exam_svc.assign_seats(user, roomId, body.studentIds), message="已铺位")


@router.get("/exam/rooms/{roomId}/seats", summary="座位表")
def exam_seats(roomId: int = Path(...), user=Depends(require_permission(_EXAM_VIEW))):
    return success({"items": exam_svc.room_seats(user, roomId)})


@router.post("/exam/rooms/{roomId}/invigilators", summary="指定监考（同时段冲突409）")
def exam_invig_add(
    body: InvigilatorBody,
    roomId: int = Path(...),
    user=Depends(require_permission(_EXAM_ARRANGE)),
):
    return success(
        exam_svc.assign_invigilator(
            user,
            roomId,
            body.teacherKey,
            body.teacherName,
            body.role,
        ),
        message="已指定",
    )


@router.get("/exam/rooms/{roomId}/invigilators", summary="监考列表")
def exam_invigs(roomId: int = Path(...), user=Depends(require_permission(_EXAM_VIEW))):
    return success({"items": exam_svc.list_invigilators(user, roomId)})


@router.post("/exam/rooms/{roomId}/invigilators/change", summary="发布后调整监考（唯一合法变更入口，必填原因）")
def exam_invig_change(
    body: ChangeInvigilatorBody,
    roomId: int = Path(...),
    user=Depends(require_permission(_EXAM_ARRANGE)),
):
    return success(
        exam_svc.change_invigilator(
            user,
            roomId,
            body.oldTeacherKey,
            body.newTeacherKey,
            body.newTeacherName,
            body.reason,
            body.newRole,
        ),
        message="已调整",
    )


@router.post("/exam/batches/{bid}/auto-times", summary="自动编排考试时间（日期×场次网格；班级/教师不撞；dryRun 试排）")
def exam_auto_times(
    body: ExamAutoTimesBody,
    bid: int = Path(...),
    dryRun: bool = False,
    user=Depends(require_permission(_EXAM_ARRANGE)),
):
    r = autoexam_svc.auto_assign_times(user, bid, body, dry_run=dryRun)
    msg = "试排完成（未落库）" if dryRun else f"已定时 {r['assigned']} 门，无可用时段 {r['missed']} 门"
    return success(r, message=msg)


@router.post("/exam/batches/{bid}/auto-arrange", summary="自动排考（增量：已有考场的课程跳过）")
def exam_auto_arrange(
    bid: int = Path(...),
    dryRun: bool = False,
    user=Depends(require_permission(_EXAM_ARRANGE)),
):
    r = autoexam_svc.auto_arrange(user, bid, dry_run=dryRun)
    msg = "试排完成（未落库）" if dryRun else f"已编排 {r['arrangedCourses']} 门，漏排 {r['missedCourses']} 门"
    return success(r, message=msg)


@router.delete("/exam/batches/{bid}/auto-arrange", summary="清除自动排考结果（仅 AUTO 考场，人工编排保留）")
def exam_auto_clear(bid: int = Path(...), user=Depends(require_permission(_EXAM_ARRANGE))):
    return success(autoexam_svc.clear_auto(user, bid), message="已清除自动排考结果")


@router.post("/exam/batches/{bid}/patrols", summary="排巡考（同时段/与监考冲突409）")
def exam_patrol_add(
    body: PatrolBody,
    bid: int = Path(...),
    user=Depends(require_permission(_EXAM_ARRANGE)),
):
    return success(
        exam_svc.assign_patrol(
            user,
            bid,
            body.teacherKey,
            body.teacherName,
            body.patrolDate,
            body.startTime,
            body.endTime,
            body.areaScope,
        ),
        message="已排巡考",
    )


@router.post("/exam/patrols/{patrolId}/change", summary="发布后调整巡考（唯一合法变更入口，必填原因）")
def exam_patrol_change(
    body: ChangePatrolBody,
    patrolId: int = Path(...),
    user=Depends(require_permission(_EXAM_ARRANGE)),
):
    return success(
        exam_svc.change_patrol(
            user,
            patrolId,
            body.newTeacherKey,
            body.newTeacherName,
            body.reason,
            body.newPatrolDate,
            body.newStartTime,
            body.newEndTime,
        ),
        message="已调整",
    )


@router.get("/exam/batches/{bid}/patrols", summary="巡考列表")
def exam_patrols(bid: int = Path(...), user=Depends(require_permission(_EXAM_VIEW))):
    return success({"items": exam_svc.list_patrols(user, bid)})


@router.post("/exam/batches/{bid}/publish", summary="发布批次（通知考生+监考）")
def exam_publish(bid: int = Path(...), user=Depends(require_permission(_EXAM_PUBLISH))):
    return success(exam_svc.publish_batch(user, bid), message="已发布")


@router.post("/exam/batches/{bid}/finish", summary="结束考试")
def exam_finish(bid: int = Path(...), user=Depends(require_permission(_EXAM_MANAGE))):
    return success(exam_svc.finish_batch(user, bid), message="已结束")


@router.post("/exam/batches/{bid}/archive", summary="归档批次")
def exam_archive(bid: int = Path(...), user=Depends(require_permission(_EXAM_MANAGE))):
    return success(exam_svc.archive_batch(user, bid), message="已归档")


@router.post("/exam/incidents", summary="登记考场异常（缺考触发风险）")
def exam_incident_record(body: IncidentBody, user=Depends(require_permission(_EXAM_ABNORMAL))):
    return success(exam_svc.record_incident(user, body), message="已登记")


@router.get("/exam/incidents", summary="考场异常记录列表")
def exam_incidents(
    batchId: Optional[str] = None,
    page: int = 1,
    pageSize: int = 50,
    user=Depends(require_permission(_EXAM_VIEW)),
):
    items, total = exam_svc.list_incidents(user, batchId, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/exam/batches/{bid}/stats", summary="考务统计")
def exam_stats(bid: int = Path(...), user=Depends(require_permission(_EXAM_VIEW))):
    return success(exam_svc.batch_stats(user, bid))


@router.get("/exam/archive", summary="考务归档批次列表（12号卡，只读，ARCHIVED）")
def exam_archive_list(
    termId: Optional[str] = None,
    collegeId: Optional[str] = None,
    page: int = 1,
    pageSize: int = 20,
    user=Depends(require_permission(_EXAM_VIEW)),
):
    items, total = exam_svc.list_archived_batches(user, termId, collegeId, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/deferred-exams", summary="学生申请缓考")
def defer_apply(body: DeferApplyBody, user=Depends(_require_student)):
    return success(exam_svc.defer_apply(user, body), message="缓考申请已提交")


@router.get("/deferred-exams/my", summary="我的缓考申请")
def defer_my(status: Optional[str] = None, user=Depends(_require_student)):
    items, total = exam_svc.defer_list(user, status, student_only=True)
    return success(paginate(items, total, 1, len(items) or 1))


@router.post("/deferred-exams/{deferId}/resubmit", summary="退回后补材料重提")
def defer_resubmit(deferId: int = Path(...), user=Depends(_require_student)):
    return success(exam_svc.defer_resubmit(user, deferId), message="已重提")


@router.get("/deferred-exams", summary="缓考审批列表（教务/学院/教师/辅导员）")
def defer_list(
    status: Optional[str] = None,
    page: int = 1,
    pageSize: int = 50,
    user=Depends(require_any_permission(_DEFER_COUNSELOR, _DEFER_REVIEW, "academicAffairs.exam.view")),
):
    items, total = exam_svc.defer_list(
        user,
        status,
        student_only=False,
        page=page,
        page_size=pageSize,
    )
    return success(paginate(items, total, page, pageSize))


@router.post("/deferred-exams/{deferId}/counselor-review", summary="缓考辅导员首级审批")
def defer_counselor_review(
    body: DeferReviewBody,
    deferId: int = Path(...),
    user=Depends(require_permission(_DEFER_COUNSELOR)),
):
    return success(exam_svc.defer_review(user, deferId, body.action, body.reason), message="已处理")


@router.post("/deferred-exams/{deferId}/review", summary="缓考教师/学院/教务处审批")
def defer_review(
    body: DeferReviewBody,
    deferId: int = Path(...),
    user=Depends(require_permission(_DEFER_REVIEW)),
):
    return success(exam_svc.defer_review(user, deferId, body.action, body.reason), message="已处理")
