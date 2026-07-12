"""13B 教务中心 API（/api/v1/academic-affairs/*）—— P1：首页 + 学年学期/校历/节次 + 学籍名册 + 入学注册。"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Path
from pydantic import BaseModel, Field

from app.core.response import paginate, success
from app.core.security import require_staff
from app.modules.academic_affairs.services import academic_affairs_change_service as change_svc
from app.modules.academic_affairs.services import academic_affairs_course_service as course_svc
from app.modules.academic_affairs.services import academic_affairs_grade_service as grade_svc
from app.modules.academic_affairs.services import academic_affairs_graduation_service as grad_svc
from app.modules.academic_affairs.services import academic_affairs_program_service as prog_svc
from app.modules.academic_affairs.services import academic_affairs_schedule_service as sched_svc
from app.modules.academic_affairs.services import academic_affairs_warning_service as warn_svc
from app.modules.academic_affairs.services import academic_affairs_service as svc
from app.modules.academic_affairs.services import academic_affairs_task_service as task_svc

router = APIRouter(prefix="/academic-affairs", tags=["教务中心"])


@router.get("/dashboard", summary="教务首页（当前学期 + 模块卡）")
def dashboard(user=Depends(require_staff)):
    return success(svc.dashboard(user))


# ── 学年学期 ──
class TermCreate(BaseModel):
    yearCode: str = Field(..., min_length=1, description="学年 如 2026-2027")
    termNo: int = Field(..., ge=1, le=2)
    termName: Optional[str] = None
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    teachingWeeks: Optional[int] = None
    examWeekStart: Optional[int] = None


@router.post("/terms", summary="新建学年学期")
def term_create(body: TermCreate, user=Depends(require_staff)):
    return success(svc.create_term(body, user), message="已创建")


@router.get("/terms", summary="学期列表")
def terms(status: Optional[str] = None, page: int = 1, pageSize: int = 50, user=Depends(require_staff)):
    items, total = svc.list_terms(user, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/terms/current", summary="当前学期")
def term_current(user=Depends(require_staff)):
    return success(svc.current_term(user))


@router.post("/terms/{termId}/publish", summary="发布学期（设为当前，幂等）")
def term_publish(termId: int = Path(...), user=Depends(require_staff)):
    return success(svc.publish_term(termId, user), message="已发布")


class CalendarEventBody(BaseModel):
    eventType: str = Field("TEACHING", description="TEACHING/EXAM/INTERNSHIP/HOLIDAY/SWAP")
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    swapToDate: Optional[str] = None
    remark: Optional[str] = None


@router.post("/terms/{termId}/calendar", summary="添加校历事件")
def calendar_add(body: CalendarEventBody, termId: int = Path(...), user=Depends(require_staff)):
    return success(svc.add_calendar_event(termId, user, body), message="已添加")


@router.get("/terms/{termId}/calendar", summary="校历事件列表")
def calendar_list(termId: int = Path(...), user=Depends(require_staff)):
    return success({"items": svc.list_calendar(termId, user)})


# ── 作息节次 ──
class TimeSlotCreate(BaseModel):
    slotNo: int = Field(..., ge=1)
    slotName: Optional[str] = None
    startTime: Optional[str] = Field(None, description="HH:MM")
    endTime: Optional[str] = None


@router.post("/time-slots", summary="新建作息节次")
def time_slot_create(body: TimeSlotCreate, user=Depends(require_staff)):
    return success(svc.create_time_slot(body, user), message="已创建")


@router.get("/time-slots", summary="作息节次列表")
def time_slots(user=Depends(require_staff)):
    return success({"items": svc.list_time_slots(user)})


# ── 学籍名册 ──
@router.get("/roster", summary="学籍名册（只读主档，脱敏）")
def roster(keyword: Optional[str] = None, status: Optional[str] = None,
           page: int = 1, pageSize: int = 20, user=Depends(require_staff)):
    items, total = svc.roster(user, keyword, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


# ── 入学/学年注册 ──
class RegBatchCreate(BaseModel):
    batchName: str = Field(..., min_length=1)
    registerType: str = Field("ENROLL", description="ENROLL 入学 / ANNUAL 学年")
    termId: Optional[str] = None
    windowStart: Optional[str] = None
    windowEnd: Optional[str] = None
    open: bool = Field(False)


class RegisterBody(BaseModel):
    studentId: str = Field(..., min_length=1)


@router.post("/registration-batches", summary="新建注册批次")
def reg_batch_create(body: RegBatchCreate, user=Depends(require_staff)):
    return success(svc.create_registration_batch(body, user), message="已创建")


@router.get("/registration-batches", summary="注册批次列表")
def reg_batches(status: Optional[str] = None, page: int = 1, pageSize: int = 20, user=Depends(require_staff)):
    items, total = svc.list_registration_batches(user, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/registration-batches/{batchId}/register", summary="学生注册（经 change_student_status 单一入口）")
def register(body: RegisterBody, batchId: int = Path(...), user=Depends(require_staff)):
    return success(svc.register_student(batchId, user, body.studentId), message="注册成功")


@router.get("/registration-batches/{batchId}/registrations", summary="注册记录列表")
def registrations(batchId: int = Path(...), page: int = 1, pageSize: int = 50, user=Depends(require_staff)):
    items, total = svc.list_registrations(batchId, user, page, pageSize)
    return success(paginate(items, total, page, pageSize))


# ═══════════ 学籍异动（P2，休学/复学/退学/转专业/留级）═══════════

class StatusChangeSubmit(BaseModel):
    studentId: str = Field(..., min_length=1)
    changeType: str = Field(..., description="SUSPEND/RESUME/WITHDRAW/RETAIN/TRANSFER_MAJOR")
    reason: Optional[str] = Field("", max_length=500)
    toCollegeId: Optional[str] = None
    toMajorId: Optional[str] = None
    toClassId: Optional[str] = None


class AaReviewBody(BaseModel):
    action: str = Field(..., description="APPROVE/REJECT/RETURN")
    reason: Optional[str] = Field("", max_length=500)


@router.post("/status-changes", summary="发起学籍异动")
def status_change_submit(body: StatusChangeSubmit, user=Depends(require_staff)):
    return success(change_svc.submit(body, user), message="异动已提交")


@router.get("/status-changes", summary="学籍异动列表")
def status_changes(changeType: Optional[str] = None, status: Optional[str] = None,
                   studentId: Optional[str] = None, page: int = 1, pageSize: int = 20,
                   user=Depends(require_staff)):
    items, total = change_svc.list_changes(user, changeType, status, studentId, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/status-changes/{changeId}", summary="异动详情")
def status_change_detail(changeId: int = Path(...), user=Depends(require_staff)):
    return success(change_svc.get_change(changeId, user))


@router.post("/status-changes/{changeId}/review", summary="异动审批（多节点，终审经单一入口生效）")
def status_change_review(body: AaReviewBody, changeId: int = Path(...), user=Depends(require_staff)):
    return success(change_svc.review(changeId, user, body.action, body.reason or ""), message="已处理")


# ═══════════ 培养方案（P2 编制骨架，审批发布 P3）═══════════

class ProgramCreate(BaseModel):
    programName: str = Field(..., min_length=1)
    majorId: Optional[str] = None
    gradeYear: Optional[str] = None
    totalCredits: Optional[int] = None
    requirement: Optional[dict] = Field(default_factory=dict)


class ProgramUpdate(BaseModel):
    programName: Optional[str] = None
    totalCredits: Optional[int] = None
    requirement: Optional[dict] = None


class ProgramCourseBody(BaseModel):
    courseId: Optional[str] = None
    courseName: str = Field(..., min_length=1)
    openTermNo: Optional[int] = None
    module: Optional[str] = None
    credit: Optional[int] = None


@router.post("/programs", summary="新建培养方案")
def program_create(body: ProgramCreate, user=Depends(require_staff)):
    return success(prog_svc.create_program(body, user), message="已创建")


@router.get("/programs", summary="培养方案列表")
def programs(majorId: Optional[str] = None, status: Optional[str] = None,
             page: int = 1, pageSize: int = 20, user=Depends(require_staff)):
    items, total = prog_svc.list_programs(user, majorId, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/programs/{programId}", summary="方案详情（含课程明细+学分差额）")
def program_detail(programId: int = Path(...), user=Depends(require_staff)):
    return success(prog_svc.get_program(programId, user))


@router.put("/programs/{programId}", summary="编辑方案（编制态）")
def program_update(body: ProgramUpdate, programId: int = Path(...), user=Depends(require_staff)):
    return success(prog_svc.update_program(programId, user, body), message="已保存")


@router.post("/programs/{programId}/courses", summary="方案增课程明细")
def program_add_course(body: ProgramCourseBody, programId: int = Path(...), user=Depends(require_staff)):
    return success(prog_svc.add_course(programId, user, body), message="已添加")


@router.post("/programs/{programId}/submit", summary="提交方案审核（发布前校验学分达标）")
def program_submit(programId: int = Path(...), user=Depends(require_staff)):
    return success(prog_svc.submit_program(programId, user), message="已提交")


@router.post("/programs/{programId}/review", summary="方案两级审核（学院→教务→PUBLISHED）")
def program_review(body: AaReviewBody, programId: int = Path(...), user=Depends(require_staff)):
    return success(prog_svc.review_program(programId, user, body.action, body.reason or ""), message="已处理")


class BindGradeBody(BaseModel):
    gradeYear: str = Field(..., min_length=1)
    classId: Optional[str] = None


@router.post("/programs/{programId}/bind", summary="已发布方案绑定年级（锁旧版本）")
def program_bind(body: BindGradeBody, programId: int = Path(...), user=Depends(require_staff)):
    return success(prog_svc.bind_grade(programId, user, body.gradeYear, body.classId), message="已绑定")


# ═══════════ 课程库（P3，两级审核，商业级全字段）═══════════

class CourseCreate(BaseModel):
    courseCode: str = Field(..., min_length=1)
    courseName: str = Field(..., min_length=1)
    courseNameEn: Optional[str] = None
    category: str = Field("MAJOR_CORE", description="PUBLIC_BASIC/DISCIPLINE_BASIC/MAJOR_CORE/MAJOR_ELECTIVE/PRACTICE")
    nature: str = Field("REQUIRED", description="REQUIRED/ELECTIVE/LIMITED_ELECTIVE/PUBLIC_ELECTIVE")
    credit: float = Field(0)
    hoursTotal: Optional[int] = None
    hoursTheory: Optional[int] = None
    hoursPractice: Optional[int] = None
    hoursExperiment: Optional[int] = None
    hoursComputer: Optional[int] = None
    examMode: str = Field("EXAM", description="EXAM/CHECK")
    ownerCollegeId: Optional[str] = None
    isCore: bool = Field(False)
    prerequisiteCodes: Optional[list] = Field(default_factory=list)


@router.post("/courses", summary="新建课程（草稿）")
def course_create(body: CourseCreate, user=Depends(require_staff)):
    return success(course_svc.create_course(body, user), message="已创建")


@router.get("/courses", summary="课程库列表")
def courses(keyword: Optional[str] = None, category: Optional[str] = None, nature: Optional[str] = None,
            status: Optional[str] = None, page: int = 1, pageSize: int = 20, user=Depends(require_staff)):
    items, total = course_svc.list_courses(user, keyword, category, nature, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/courses/{courseId}", summary="课程详情")
def course_detail(courseId: int = Path(...), user=Depends(require_staff)):
    return success(course_svc.get_course(courseId, user))


@router.put("/courses/{courseId}", summary="编辑课程（已启用改动强制新版本）")
def course_update(body: CourseCreate, courseId: int = Path(...), user=Depends(require_staff)):
    return success(course_svc.update_course(courseId, user, body), message="已保存")


@router.post("/courses/{courseId}/submit", summary="提交课程审核")
def course_submit(courseId: int = Path(...), user=Depends(require_staff)):
    return success(course_svc.submit_course(courseId, user), message="已提交")


@router.post("/courses/{courseId}/review", summary="课程两级审核（学院→教务→ENABLED）")
def course_review(body: AaReviewBody, courseId: int = Path(...), user=Depends(require_staff)):
    return success(course_svc.review_course(courseId, user, body.action, body.reason or ""), message="已处理")


# ═══════════ 教学任务（P3）═══════════

class TaskBatchGenerate(BaseModel):
    termId: str = Field(..., min_length=1)
    collegeId: Optional[str] = None
    batchName: Optional[str] = None


class AssignBody(BaseModel):
    teacherId: Optional[str] = None
    teacherKey: Optional[str] = None
    teacherName: str = Field(..., min_length=1)
    weeklyHours: Optional[int] = None
    expectedStudents: Optional[int] = None
    isMerged: Optional[bool] = None


class TeacherActBody(BaseModel):
    action: str = Field(..., description="CONFIRM/REJECT")
    reason: Optional[str] = Field("", max_length=500)


@router.post("/teaching-task-batches/generate", summary="生成教学任务批次（按已发布方案，幂等）")
def task_generate(body: TaskBatchGenerate, user=Depends(require_staff)):
    return success(task_svc.generate_batch(body, user), message="已生成")


@router.get("/teaching-task-batches", summary="教学任务批次列表")
def task_batches(termId: Optional[str] = None, status: Optional[str] = None,
                 page: int = 1, pageSize: int = 20, user=Depends(require_staff)):
    items, total = task_svc.list_batches(user, termId, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/teaching-task-batches/{batchId}/submit", summary="提交批次审核（要求全部已分配）")
def task_batch_submit(batchId: int = Path(...), user=Depends(require_staff)):
    return success(task_svc.submit_batch(batchId, user), message="已提交")


@router.get("/teaching-task-batches/{batchId}/tasks", summary="批次内教学任务列表")
def task_list(batchId: int = Path(...), status: Optional[str] = None,
              page: int = 1, pageSize: int = 50, user=Depends(require_staff)):
    items, total = task_svc.list_tasks(batchId, user, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/teaching-tasks/{taskId}/assign", summary="分配授课教师")
def task_assign(body: AssignBody, taskId: int = Path(...), user=Depends(require_staff)):
    return success(task_svc.assign_teacher(taskId, user, body), message="已分配")


@router.post("/teaching-tasks/{taskId}/teacher-act", summary="教师确认/退回教学任务")
def task_teacher_act(body: TeacherActBody, taskId: int = Path(...), user=Depends(require_staff)):
    return success(task_svc.teacher_act(taskId, user, body.action, body.reason or ""), message="已处理")


# ═══════════ 课表（P4，三重冲突检测 + 单双周 + 三视图）═══════════

class ScheduleBatchCreate(BaseModel):
    termId: str = Field(..., min_length=1)
    batchName: Optional[str] = None
    collegeId: Optional[str] = None


class ScheduleItemBody(BaseModel):
    taskId: Optional[str] = None
    courseName: Optional[str] = None
    classId: Optional[str] = None
    className: Optional[str] = None
    teacherKey: Optional[str] = None
    teacherName: Optional[str] = None
    weekday: int = Field(..., ge=1, le=7, description="星期 1-7")
    slotNo: int = Field(..., ge=1, description="节次")
    startWeek: int = Field(1, ge=1)
    endWeek: int = Field(18, ge=1)
    weekParity: str = Field("ALL", description="ALL/ODD/EVEN 全周/单周/双周")
    classroom: Optional[str] = None


class ScheduleImportBody(BaseModel):
    items: list[dict] = Field(..., description="课表行数组（同一冲突检测器逐行校验）")


class VoidBody(BaseModel):
    reason: str = Field(..., min_length=1)


@router.post("/schedule-batches", summary="新建课表批次")
def schedule_batch_create(body: ScheduleBatchCreate, user=Depends(require_staff)):
    return success(sched_svc.create_batch(body, user), message="已创建")


@router.get("/schedule-batches", summary="课表批次列表")
def schedule_batches(termId: Optional[str] = None, status: Optional[str] = None,
                     page: int = 1, pageSize: int = 20, user=Depends(require_staff)):
    items, total = sched_svc.list_batches(user, termId, status, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.post("/schedule-batches/{batchId}/items", summary="手工排课（三重冲突检测→409）")
def schedule_add_item(body: ScheduleItemBody, batchId: int = Path(...), user=Depends(require_staff)):
    return success(sched_svc.add_item(batchId, user, body), message="已排课")


@router.post("/schedule-batches/{batchId}/import", summary="导入课表（同一冲突检测器，返回冲突清单）")
def schedule_import(body: ScheduleImportBody, batchId: int = Path(...), user=Depends(require_staff)):
    return success(sched_svc.import_items(batchId, user, body.items), message="导入完成")


@router.post("/schedule-batches/{batchId}/pre-publish", summary="课表预发布")
def schedule_pre_publish(batchId: int = Path(...), user=Depends(require_staff)):
    return success(sched_svc.pre_publish(batchId, user), message="已预发布")


@router.post("/schedule-batches/{batchId}/publish", summary="课表发布（通知师生）")
def schedule_publish(batchId: int = Path(...), user=Depends(require_staff)):
    return success(sched_svc.publish(batchId, user), message="已发布")


@router.post("/schedule-batches/{batchId}/void-reissue", summary="作废重发（调停课运维通道，留审计）")
def schedule_void(body: VoidBody, batchId: int = Path(...), user=Depends(require_staff)):
    return success(sched_svc.void_and_reissue(batchId, user, body.reason), message="已作废")


@router.get("/schedule-batches/{batchId}/class-view", summary="班级课表视图")
def schedule_class_view(batchId: int = Path(...), classId: str = "", user=Depends(require_staff)):
    return success(sched_svc.class_view(batchId, user, classId))


@router.get("/schedule-batches/{batchId}/teacher-view", summary="教师课表视图")
def schedule_teacher_view(batchId: int = Path(...), teacherKey: str = "", user=Depends(require_staff)):
    return success(sched_svc.teacher_view(batchId, user, teacherKey))


@router.get("/schedule-batches/{batchId}/student-view", summary="学生课表视图（按行政班服务端推导）")
def schedule_student_view(batchId: int = Path(...), studentId: str = "", user=Depends(require_staff)):
    return success(sched_svc.student_view(batchId, user, studentId))


# ═══════════ 成绩录入 + 读侧视图（P5，平时+期末按比例）═══════════

class GradeTaskCreate(BaseModel):
    teachingTaskId: Optional[str] = None
    termId: Optional[str] = None
    termCode: Optional[str] = None
    courseName: str = Field(..., min_length=1)
    classId: Optional[str] = None
    credit: Optional[float] = None
    usualRatio: int = Field(30, ge=0, le=100, description="平时占比%")
    finalRatio: int = Field(70, ge=0, le=100, description="期末占比%")
    passLine: int = Field(60, ge=0, le=100)


class ScoreBody(BaseModel):
    studentId: str = Field(..., min_length=1)
    usualScore: Optional[int] = Field(None, ge=0, le=100)
    finalScore: Optional[int] = Field(None, ge=0, le=100)


@router.post("/grade-tasks", summary="新建成绩录入任务（配平时/期末占比）")
def grade_task_create(body: GradeTaskCreate, user=Depends(require_staff)):
    return success(grade_svc.create_grade_task(body, user), message="已创建")


@router.post("/grade-tasks/{taskId}/scores", summary="录入平时/期末分（实时合成总评）")
def grade_enter_score(body: ScoreBody, taskId: int = Path(...), user=Depends(require_staff)):
    return success(grade_svc.enter_score(taskId, user, body), message="已录入")


@router.post("/grade-tasks/{taskId}/publish", summary="发布成绩（合成→原子回写 t_acad_grade）")
def grade_publish(taskId: int = Path(...), user=Depends(require_staff)):
    return success(grade_svc.publish_grades(taskId, user), message="已发布")


@router.get("/students/{studentId}/transcript", summary="学生成绩单（读侧）")
def grade_transcript(studentId: int = Path(...), user=Depends(require_staff)):
    return success(grade_svc.transcript(studentId, user))


@router.get("/grade-views/fail-list", summary="挂科清单（读侧下钻）")
def grade_fail_list(term: Optional[str] = None, page: int = 1, pageSize: int = 50, user=Depends(require_staff)):
    items, total = grade_svc.fail_list(user, term, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/grade-views/analysis", summary="成绩分析（分数段分布+及格率）")
def grade_analysis(term: Optional[str] = None, user=Depends(require_staff)):
    return success(grade_svc.grade_analysis(user, term))


# ═══════════ 学业预警规则引擎（P5）═══════════

@router.post("/warnings/scan", summary="学业预警扫描（挂科规则，幂等）")
def warning_scan(user=Depends(require_staff)):
    return success(warn_svc.scan_warnings(user))


@router.get("/warnings", summary="学业预警列表")
def warnings(level: Optional[str] = None, status: Optional[str] = None, sourceCode: Optional[str] = None,
             page: int = 1, pageSize: int = 20, user=Depends(require_staff)):
    items, total = warn_svc.list_warnings(user, level, status, sourceCode, page, pageSize)
    return success(paginate(items, total, page, pageSize))


# ═══════════ 毕业资格预审（P6，七项供数三态判定）═══════════

class GradAuditBatchCreate(BaseModel):
    batchName: str = Field(..., min_length=1)
    gradeYear: Optional[str] = None
    majorId: Optional[str] = None


class GenerateStudentsBody(BaseModel):
    studentIds: Optional[list[str]] = None


class GradReviewBody(BaseModel):
    action: str = Field(..., description="APPROVE/REJECT")
    note: Optional[str] = Field("", max_length=500)


class GradFinalBody(BaseModel):
    conclusion: str = Field(..., description="GRADUATED/COMPLETED/DELAYED")
    confirm: bool = Field(False, description="二次确认(涉学籍终态)")


@router.post("/graduation-audit-batches", summary="新建毕业预审批次")
def grad_batch_create(body: GradAuditBatchCreate, user=Depends(require_staff)):
    return success(grad_svc.create_batch(body, user), message="已创建")


@router.post("/graduation-audit-batches/{batchId}/generate", summary="圈定应届生生成预审行（幂等）")
def grad_generate(body: GenerateStudentsBody = GenerateStudentsBody(), batchId: int = Path(...),
                  user=Depends(require_staff)):
    return success(grad_svc.generate(batchId, user, body.studentIds), message="已生成")


@router.post("/graduation-audit-batches/{batchId}/precheck", summary="七项供数三态预审（幂等，覆盖）")
def grad_precheck(batchId: int = Path(...), user=Depends(require_staff)):
    return success(grad_svc.precheck(batchId, user), message="预审完成")


@router.get("/graduation-audit-batches/{batchId}/results", summary="预审结果列表")
def grad_results(batchId: int = Path(...), status: Optional[str] = None, overall: Optional[str] = None,
                 page: int = 1, pageSize: int = 50, user=Depends(require_staff)):
    items, total = grad_svc.list_results(batchId, user, status, overall, page, pageSize)
    return success(paginate(items, total, page, pageSize))


@router.get("/graduation-audit-batches/{batchId}/rosters", summary="三名单（毕业/结业/延毕）")
def grad_rosters(batchId: int = Path(...), user=Depends(require_staff)):
    return success(grad_svc.rosters(batchId, user))


@router.get("/graduation-results/{resultId}", summary="预审结果详情（七项证据）")
def grad_result_detail(resultId: int = Path(...), user=Depends(require_staff)):
    return success(grad_svc.get_result(resultId, user))


@router.post("/graduation-results/{resultId}/college-review", summary="学院初审")
def grad_college_review(body: GradReviewBody, resultId: int = Path(...), user=Depends(require_staff)):
    return success(grad_svc.college_review(resultId, user, body.action, body.note or ""), message="已处理")


@router.post("/graduation-results/{resultId}/final", summary="教务终审（结论→经单一入口写学籍，强制二次确认）")
def grad_final(body: GradFinalBody, resultId: int = Path(...), user=Depends(require_staff)):
    return success(grad_svc.academic_final(resultId, user, body.conclusion, body.confirm), message="已终审")
