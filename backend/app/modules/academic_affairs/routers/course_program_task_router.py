"""D4-S 课程 / 培养方案 / 教学任务 Move Only 正式 Router。

只迁 legacy base 仍持有的 program/course/teaching-task 入口。
program_quality_router 与 teaching_class_router 已是独立正式 extension，本 Router 不复制它们；
canonical service、权限、DTO、状态机、schema 均保持不变。
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Path

from app.core.permissions import require_permission
from app.core.response import paginate, success
from app.modules.academic_affairs.routers import academic_affairs as legacy

router = APIRouter(prefix="/academic-affairs", tags=["教务中心"])

# Move Only：沿用历史 DTO / permission dependency / service 对象，避免 Pydantic、OpenAPI、
# 权限和业务入口在结构拆分时漂移。
ProgramCreate = legacy.ProgramCreate
ProgramUpdate = legacy.ProgramUpdate
ProgramCourseBody = legacy.ProgramCourseBody
ProgramCourseUpdate = legacy.ProgramCourseUpdate
AaReviewBody = legacy.AaReviewBody
BindGradeBody = legacy.BindGradeBody
CreditRequirementsBody = legacy.CreditRequirementsBody
GraduationRequirementCreate = legacy.GraduationRequirementCreate
GraduationRequirementUpdate = legacy.GraduationRequirementUpdate
PracticeSegmentCreate = legacy.PracticeSegmentCreate
PracticeSegmentUpdate = legacy.PracticeSegmentUpdate
ProgramChangeStatusBody = legacy.ProgramChangeStatusBody
ProgramChangeBody = legacy.ProgramChangeBody
CourseCreate = legacy.CourseCreate
CourseMaterialCreate = legacy.CourseMaterialCreate
TaskBatchGenerate = legacy.TaskBatchGenerate
AssignBody = legacy.AssignBody
TeacherActBody = legacy.TeacherActBody
MergeTasksBody = legacy.MergeTasksBody
AdjustTaskBody = legacy.AdjustTaskBody

_PROG_VIEW = legacy._PROG_VIEW
_PROG_MANAGE = legacy._PROG_MANAGE
_PROG_SUBMIT = legacy._PROG_SUBMIT
_PROG_REVIEW = legacy._PROG_REVIEW
_PROG_PUBLISH = legacy._PROG_PUBLISH
_PROG_CHANGE = legacy._PROG_CHANGE

_COURSE_VIEW = legacy._COURSE_VIEW
_COURSE_MANAGE = legacy._COURSE_MANAGE
_COURSE_APPROVE = legacy._COURSE_APPROVE

prog_svc = legacy.prog_svc
course_svc = legacy.course_svc
task_svc = legacy.task_svc


# ═══════════ 培养方案 ════════════

@router.post("/programs", summary="新建培养方案")
def program_create(body: ProgramCreate, user=Depends(_PROG_MANAGE)):
    return success(prog_svc.create_program(body, user), message="已创建")


@router.get("/programs", summary="培养方案列表（statusIn 支持逗号分隔多状态，供审核/发布工作台筛选）")
def programs(
    majorId: Optional[str] = None,
    status: Optional[str] = None,
    statusIn: Optional[str] = None,
    page: int = 1,
    pageSize: int = 20,
    user=Depends(_PROG_VIEW),
):
    items, total = prog_svc.list_programs(user, majorId, status, page, pageSize, statusIn)
    return success(paginate(items, total, page, pageSize))


@router.get("/programs/{programId}", summary="方案详情（含课程明细+学分差额）")
def program_detail(programId: int = Path(...), user=Depends(_PROG_VIEW)):
    return success(prog_svc.get_program(programId, user))


@router.put("/programs/{programId}", summary="编辑方案（编制态）")
def program_update(body: ProgramUpdate, programId: int = Path(...), user=Depends(_PROG_MANAGE)):
    return success(prog_svc.update_program(programId, user, body), message="已保存")


@router.post("/programs/{programId}/courses", summary="方案增课程明细")
def program_add_course(body: ProgramCourseBody, programId: int = Path(...), user=Depends(_PROG_MANAGE)):
    return success(prog_svc.add_course(programId, user, body), message="已添加")


@router.put("/programs/courses/{programCourseId}", summary="方案课程模块：编辑课程明细（编制态）")
def program_course_update(
    body: ProgramCourseUpdate,
    programCourseId: int = Path(...),
    user=Depends(_PROG_MANAGE),
):
    return success(prog_svc.update_course(programCourseId, user, body), message="已保存")


@router.delete("/programs/courses/{programCourseId}", summary="方案课程模块：删除课程明细（编制态）")
def program_course_delete(programCourseId: int = Path(...), user=Depends(_PROG_MANAGE)):
    return success(prog_svc.delete_course(programCourseId, user), message="已删除")


@router.post("/programs/{programId}/submit", summary="提交方案审核（发布前校验学分达标）")
def program_submit(programId: int = Path(...), user=Depends(_PROG_SUBMIT)):
    return success(prog_svc.submit_program(programId, user), message="已提交")


@router.post("/programs/{programId}/review", summary="方案两级审核（学院→教务→PUBLISHED）")
def program_review(body: AaReviewBody, programId: int = Path(...), user=Depends(_PROG_REVIEW)):
    return success(prog_svc.review_program(programId, user, body.action, body.reason or ""), message="已处理")


@router.post("/programs/{programId}/bind", summary="已发布方案绑定年级（锁旧版本）")
def program_bind(body: BindGradeBody, programId: int = Path(...), user=Depends(_PROG_PUBLISH)):
    return success(prog_svc.bind_grade(programId, user, body.gradeYear, body.classId), message="已绑定")


@router.get("/programs/{programId}/bindings", summary="方案发布：已绑定年级记录（含历史 SUPERSEDED）")
def program_bindings(programId: int = Path(...), user=Depends(_PROG_VIEW)):
    return success({"items": prog_svc.list_program_bindings(programId, user)})


@router.get("/programs/{programId}/credit-requirements", summary="学分要求：分模块学分结构读取")
def program_credit_requirements(programId: int = Path(...), user=Depends(_PROG_VIEW)):
    return success(prog_svc.get_credit_requirements(programId, user))


@router.put("/programs/{programId}/credit-requirements", summary="学分要求：保存分模块学分结构（编制态）")
def program_credit_requirements_save(
    body: CreditRequirementsBody,
    programId: int = Path(...),
    user=Depends(_PROG_MANAGE),
):
    items = [i.model_dump() for i in body.items]
    return success(prog_svc.save_credit_requirements(programId, user, items), message="已保存")


@router.get("/programs/{programId}/graduation-requirements", summary="毕业要求：条目列表")
def program_grad_requirements(programId: int = Path(...), user=Depends(_PROG_VIEW)):
    return success({"items": prog_svc.list_graduation_requirements(programId, user)})


@router.post("/programs/{programId}/graduation-requirements", summary="毕业要求：新增条目（编制态）")
def program_grad_requirement_create(
    body: GraduationRequirementCreate,
    programId: int = Path(...),
    user=Depends(_PROG_MANAGE),
):
    return success(prog_svc.create_graduation_requirement(programId, user, body), message="已添加")


@router.put("/programs/graduation-requirements/{requirementId}", summary="毕业要求：编辑条目（编制态）")
def program_grad_requirement_update(
    body: GraduationRequirementUpdate,
    requirementId: int = Path(...),
    user=Depends(_PROG_MANAGE),
):
    return success(prog_svc.update_graduation_requirement(requirementId, user, body), message="已保存")


@router.delete("/programs/graduation-requirements/{requirementId}", summary="毕业要求：删除条目（编制态）")
def program_grad_requirement_delete(requirementId: int = Path(...), user=Depends(_PROG_MANAGE)):
    return success(prog_svc.delete_graduation_requirement(requirementId, user), message="已删除")


@router.get("/programs/{programId}/versions", summary="方案版本：同一方案谱系全部版本链")
def program_versions(programId: int = Path(...), user=Depends(_PROG_VIEW)):
    return success({"items": prog_svc.list_program_versions(programId, user)})


@router.post("/programs/{programId}/new-version", summary="方案版本：基于已发布/启用/冻结版本新建 DRAFT 新版本")
def program_new_version(programId: int = Path(...), user=Depends(_PROG_MANAGE)):
    return success(prog_svc.create_new_version(programId, user), message="已新建版本")


@router.get("/programs/{programId}/practice-segments", summary="实践环节：条目列表（集中性实践教学环节，编制态可写）")
def program_practice_segments(programId: int = Path(...), user=Depends(_PROG_VIEW)):
    return success({"items": prog_svc.list_practice_segments(programId, user)})


@router.post("/programs/{programId}/practice-segments", summary="实践环节：新增条目（编制态）")
def program_practice_segment_create(
    body: PracticeSegmentCreate,
    programId: int = Path(...),
    user=Depends(_PROG_MANAGE),
):
    return success(prog_svc.create_practice_segment(programId, user, body), message="已添加")


@router.put("/programs/practice-segments/{segmentId}", summary="实践环节：编辑条目（编制态）")
def program_practice_segment_update(
    body: PracticeSegmentUpdate,
    segmentId: int = Path(...),
    user=Depends(_PROG_MANAGE),
):
    return success(prog_svc.update_practice_segment(segmentId, user, body), message="已保存")


@router.delete("/programs/practice-segments/{segmentId}", summary="实践环节：删除条目（编制态）")
def program_practice_segment_delete(segmentId: int = Path(...), user=Depends(_PROG_MANAGE)):
    return success(prog_svc.delete_practice_segment(segmentId, user), message="已删除")


@router.post("/programs/{programId}/change-status", summary="方案变更：状态生命周期（FREEZE 冻结/RESUME 恢复/DISABLE 停用，原因必填）")
def program_change_status(
    body: ProgramChangeStatusBody,
    programId: int = Path(...),
    user=Depends(_PROG_CHANGE),
):
    return success(prog_svc.change_program_status(programId, user, body.action, body.reason), message="已处理")


@router.get("/programs/{programId}/change-log", summary="方案变更：生命周期变更记录（冻结/恢复/停用/新建版本/退回）")
def program_change_log(programId: int = Path(...), user=Depends(_PROG_VIEW)):
    return success({"items": prog_svc.list_program_lifecycle_log(programId, user)})


@router.get("/program-archive", summary="方案归档：已停用方案 + 已被取代历史版本（只读）")
def programs_archived(page: int = 1, pageSize: int = 20, user=Depends(_PROG_VIEW)):
    items, total = prog_svc.list_archived_programs(user, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/programs/{programId}/change", summary="计划变更：基于已发布/启用/冻结版本新建新版本并记录变更原因")
def program_change(body: ProgramChangeBody, programId: int = Path(...), user=Depends(_PROG_MANAGE)):
    return success(prog_svc.create_new_version(programId, user, body.reason), message="变更已生效，已生成新版本")


# ═══════════ 课程库 ════════════

@router.post("/courses", summary="新建课程（草稿）")
def course_create(body: CourseCreate, user=Depends(_COURSE_MANAGE)):
    return success(course_svc.create_course(body, user), message="已创建")


@router.get("/courses", summary="课程库列表")
def courses(
    keyword: Optional[str] = None,
    category: Optional[str] = None,
    nature: Optional[str] = None,
    status: Optional[str] = None,
    ownerTeacherId: Optional[str] = None,
    ownerCollegeId: Optional[str] = None,
    page: int = 1,
    pageSize: int = 20,
    user=Depends(_COURSE_VIEW),
):
    items, total = course_svc.list_courses(
        user,
        keyword,
        category,
        nature,
        status,
        page,
        pageSize,
        owner_teacher_id=ownerTeacherId,
        owner_college_id=ownerCollegeId,
    )
    return success(paginate(items, total, page, pageSize))


@router.get("/courses/teachers/search", summary="课程负责人检索（在职教师，供选择器）")
def course_teacher_search(keyword: Optional[str] = None, user=Depends(_COURSE_VIEW)):
    return success({"items": course_svc.search_teachers(keyword or "")})


@router.get("/courses/{courseId}", summary="课程详情")
def course_detail(courseId: int = Path(...), user=Depends(_COURSE_VIEW)):
    return success(course_svc.get_course(courseId, user))


@router.get("/courses/{courseId}/references", summary="课程引用情况（被哪些培养方案引用，供停用前提示）")
def course_references(courseId: int = Path(...), user=Depends(_COURSE_VIEW)):
    return success({"items": course_svc.get_course_references(courseId, user)})


@router.get("/courses/{courseId}/materials", summary="课程材料/大纲列表（materialType=SYLLABUS 即课程大纲）")
def course_materials(
    courseId: int = Path(...),
    materialType: Optional[str] = None,
    page: int = 1,
    pageSize: int = 50,
    user=Depends(_COURSE_VIEW),
):
    items, total = course_svc.list_course_materials(courseId, user, materialType, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/courses/{courseId}/materials", summary="新增课程材料/大纲")
def course_material_add(
    body: CourseMaterialCreate,
    courseId: int = Path(...),
    user=Depends(_COURSE_MANAGE),
):
    return success(course_svc.add_course_material(courseId, user, body), message="已新增")


@router.delete("/courses/materials/{materialId}", summary="作废课程材料（逻辑删除）")
def course_material_void(materialId: int = Path(...), user=Depends(_COURSE_MANAGE)):
    return success(course_svc.void_course_material(materialId, user), message="已作废")


@router.put("/courses/{courseId}", summary="编辑课程（已启用改动强制新版本）")
def course_update(body: CourseCreate, courseId: int = Path(...), user=Depends(_COURSE_MANAGE)):
    return success(course_svc.update_course(courseId, user, body), message="已保存")


@router.post("/courses/{courseId}/submit", summary="提交课程审核")
def course_submit(courseId: int = Path(...), user=Depends(_COURSE_MANAGE)):
    return success(course_svc.submit_course(courseId, user), message="已提交")


@router.post("/courses/{courseId}/review", summary="课程两级审核（学院→教务→ENABLED）")
def course_review(body: AaReviewBody, courseId: int = Path(...), user=Depends(_COURSE_APPROVE)):
    return success(course_svc.review_course(courseId, user, body.action, body.reason or ""), message="已处理")


@router.post("/courses/{courseId}/enable", summary="启用课程（DISABLED→ENABLED）")
def course_enable(courseId: int = Path(...), user=Depends(_COURSE_APPROVE)):
    return success(course_svc.set_course_status(courseId, user, True), message="已启用")


@router.post("/courses/{courseId}/disable", summary="停用课程（ENABLED→DISABLED；被在途/生效培养方案引用时 400 拦截）")
def course_disable(courseId: int = Path(...), user=Depends(_COURSE_APPROVE)):
    return success(course_svc.set_course_status(courseId, user, False), message="已停用")


# ═══════════ 教学任务 ════════════

@router.post("/teaching-task-batches/generate", summary="生成教学任务批次（按已发布方案，幂等）")
def task_generate(
    body: TaskBatchGenerate,
    user=Depends(require_permission("academicAffairs.teachingTask.manage")),
):
    return success(task_svc.generate_batch(body, user), message="已生成")


@router.get("/teaching-task-batches", summary="教学任务批次列表")
def task_batches(
    termId: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    pageSize: int = 20,
    user=Depends(require_permission("academicAffairs.teachingTask.view")),
):
    items, total = task_svc.list_batches(user, termId, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/teaching-task-batches/{batchId}/submit", summary="提交批次审核（要求全部已分配）")
def task_batch_submit(
    batchId: int = Path(...),
    user=Depends(require_permission("academicAffairs.teachingTask.confirm")),
):
    return success(task_svc.submit_batch(batchId, user), message="已提交")


@router.get("/teaching-task-batches/{batchId}/tasks", summary="批次内教学任务列表")
def task_list(
    batchId: int = Path(...),
    status: Optional[str] = None,
    page: int = 1,
    pageSize: int = 50,
    user=Depends(require_permission("academicAffairs.teachingTask.view")),
):
    items, total = task_svc.list_tasks(batchId, user, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/teaching-tasks/{taskId}/assign", summary="分配授课教师")
def task_assign(
    body: AssignBody,
    taskId: int = Path(...),
    user=Depends(require_permission("academicAffairs.teachingTask.manage")),
):
    return success(task_svc.assign_teacher(taskId, user, body), message="已分配")


@router.post("/teaching-tasks/{taskId}/teacher-act", summary="教师确认/退回教学任务")
def task_teacher_act(
    body: TeacherActBody,
    taskId: int = Path(...),
    user=Depends(require_permission("academicAffairs.teachingTask.view")),
):
    return success(task_svc.teacher_act(taskId, user, body.action, body.reason or ""), message="已处理")


@router.post("/teaching-task-batches/{batchId}/college-confirm", summary="学院核对确认（DRAFT→COLLEGE_CONFIRMED）")
def task_batch_college_confirm(
    batchId: int = Path(...),
    user=Depends(require_permission("academicAffairs.teachingTask.confirm")),
):
    return success(task_svc.college_confirm_batch(batchId, user), message="已确认")


@router.post("/teaching-task-batches/{batchId}/review", summary="教务终审（COLLEGE_CONFIRMED→APPROVED/RETURNED）")
def task_batch_review(
    body: AaReviewBody,
    batchId: int = Path(...),
    user=Depends(require_permission("academicAffairs.teachingTask.confirm")),
):
    return success(task_svc.review_batch(batchId, user, body.action, body.reason or ""), message="已处理")


@router.get("/teaching-tasks", summary="跨批次教学任务列表（分配队列/合班候选/我的任务）")
def task_all_list(
    batchId: Optional[int] = None,
    courseId: Optional[int] = None,
    status: Optional[str] = None,
    mergeable: bool = False,
    mine: bool = False,
    page: int = 1,
    pageSize: int = 50,
    user=Depends(require_permission("academicAffairs.teachingTask.view")),
):
    items, total = task_svc.list_all_tasks(
        user,
        batchId,
        courseId,
        status,
        mergeable,
        mine,
        page,
        pageSize,
    )
    return success(paginate(items, total, page, pageSize))


@router.post("/teaching-tasks/merge", summary="合班（同批次同课程 2+ 条任务合并为一条教学班任务）")
def task_merge(
    body: MergeTasksBody,
    user=Depends(require_permission("academicAffairs.teachingTask.merge")),
):
    return success(task_svc.merge_tasks(body, user), message="已合班")


@router.post("/teaching-tasks/{taskId}/split", summary="拆班（还原合班前的独立教学任务）")
def task_split(
    taskId: int = Path(...),
    user=Depends(require_permission("academicAffairs.teachingTask.merge")),
):
    return success(task_svc.split_task(taskId, user), message="已拆班")


@router.post("/teaching-tasks/{taskId}/adjust", summary="教学任务调整（管理员更正教师/学时/周次/人数，理由必填+审计）")
def task_adjust(
    body: AdjustTaskBody,
    taskId: int = Path(...),
    user=Depends(require_permission("academicAffairs.teachingTask.adjust")),
):
    return success(task_svc.adjust_task(taskId, user, body), message="已调整")


@router.get("/teaching-task-batches/stats", summary="教学任务统计（批次/任务状态分布+分配率+教师确认率）")
def task_stats(
    termId: Optional[str] = None,
    user=Depends(require_permission("academicAffairs.teachingTask.stats")),
):
    return success(task_svc.get_task_stats(user, termId))
