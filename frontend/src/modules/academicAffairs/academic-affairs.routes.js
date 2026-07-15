/**
 * 教务中心（13B）— 模块路由描述（不自动接入全局 router，避免并行任务冲突）。
 * 接入方式：在 src/router/index.js 的 moduleRoutes 数组中加入本文件导出的 academicAffairsRoutes（数组，会被展平）。
 *   import { academicAffairsRoutes } from '@/modules/academicAffairs/academic-affairs.routes'
 * meta 口径与 internship/academic 模块一致（moduleCode='ACADEMIC_AFFAIRS'）。
 *
 * 说明：本模块与同目录「学业过程」旧路由（/admin/academic，routes/academic.routes.js）并存、互不覆盖。
 * 页面均接真实后端 /api/v1/academic-affairs/*（手册 D1，无 mock）。
 * 打印页为顶层独立路由（无导航布局，A4，D7）。
 */
const MOD = 'ACADEMIC_AFFAIRS'
const meta = (permissionKey, title) => ({ moduleCode: MOD, requiresAuth: true, permissionKey, title })

const layoutRoute = {
  path: '/admin/academic-affairs',
  component: () => import('@/modules/academicAffairs/views/AdminAcademicAffairsLayout.vue'),
  meta: { moduleCode: MOD },
  children: [
    // ── W1 骨架与时间轴 ──
    { path: '', name: 'aa-dashboard', component: () => import('@/modules/academicAffairs/views/AaDashboardView.vue'), meta: meta('academicAffairs.dashboard.view', '教务看板') },
    { path: 'terms', name: 'aa-terms', component: () => import('@/modules/academicAffairs/views/AaTermListView.vue'), meta: meta('academicAffairs.term.view', '学年学期') },
    { path: 'terms/new', name: 'aa-term-new', component: () => import('@/modules/academicAffairs/views/AaTermFormView.vue'), meta: meta('academicAffairs.term.manage', '新建学期') },
    // ── Tier1-R2：当前学期设置 / 学期周次 / 教学周配置 / 学期状态 / 学期归档（续工，只加叶子不改既有4端点语义） ──
    { path: 'terms/current', name: 'aa-term-current', component: () => import('@/modules/academicAffairs/views/AaTermCurrentView.vue'), meta: meta('academicAffairs.term.view', '当前学期设置') },
    { path: 'terms/weeks', name: 'aa-term-weeks', component: () => import('@/modules/academicAffairs/views/AaTermWeeksView.vue'), meta: meta('academicAffairs.term.view', '学期周次') },
    { path: 'terms/teaching-weeks', name: 'aa-term-teaching-weeks', component: () => import('@/modules/academicAffairs/views/AaTeachingWeekConfigView.vue'), meta: meta('academicAffairs.term.manage', '教学周配置') },
    { path: 'terms/status', name: 'aa-term-status', component: () => import('@/modules/academicAffairs/views/AaTermStatusView.vue'), meta: meta('academicAffairs.term.manage', '学期状态') },
    { path: 'terms/archive-status', name: 'aa-term-archive-status', component: () => import('@/modules/academicAffairs/views/AaTermArchiveView.vue'), meta: meta('academicAffairs.term.view', '学期归档') },
    // ── 续工 R3：学年管理（按学年汇总） / 学期切换记录（当前学期切换审计，只读，不新增写端点） ──
    { path: 'terms/years', name: 'aa-term-years', component: () => import('@/modules/academicAffairs/views/AaAcademicYearView.vue'), meta: meta('academicAffairs.term.view', '学年管理') },
    { path: 'terms/switch-log', name: 'aa-term-switch-log', component: () => import('@/modules/academicAffairs/views/AaTermSwitchLogView.vue'), meta: meta('academicAffairs.term.view', '学期切换记录') },
    { path: 'calendar', name: 'aa-calendar', component: () => import('@/modules/academicAffairs/views/AaCalendarView.vue'), meta: meta('academicAffairs.calendar.view', '校历管理') },
    { path: 'time-slots', name: 'aa-time-slots', component: () => import('@/modules/academicAffairs/views/AaTimeSlotView.vue'), meta: meta('academicAffairs.timeslot.view', '作息节次') },
    // ── W2 学籍写侧闭环 ──
    { path: 'roster', name: 'aa-roster', component: () => import('@/modules/academicAffairs/views/AaRosterListView.vue'), meta: meta('academicAffairs.roster.view', '学籍名册') },
    // ── 学籍管理 Tier1 R2：学籍档案 / 学籍状态 / 学籍异动记录（只读复用） / 学籍导入导出（静态子路由须在 roster/:studentId 之前声明） ──
    { path: 'roster/status', name: 'aa-roster-status', component: () => import('@/modules/academicAffairs/views/AaRosterStatusView.vue'), meta: meta('academicAffairs.roster.view', '学籍状态') },
    { path: 'roster/changes', name: 'aa-roster-changes', component: () => import('@/modules/academicAffairs/views/AaRosterChangeRecordsView.vue'), meta: meta('academicAffairs.statusChange.view', '学籍异动记录') },
    { path: 'roster/import-export', name: 'aa-roster-import-export', component: () => import('@/modules/academicAffairs/views/AaRosterImportExportView.vue'), meta: meta('academicAffairs.roster.import', '学籍导入导出') },
    // ── 学籍管理 Tier1 R3：休学/退学/保留学籍=名册状态过滤（AaRosterListView ?status=），复用无需新路由；
    // 复学/转专业因终态回落 REGISTERED、无法用 student_status 区分，走异动流水结果视图（共用组件+changeType meta）；
    // 学籍信息更正=新增只读+审核工作区（区别于「学籍异动」，见组件头注释）。三者均为静态子路由，须在
    // roster/:studentId 之前声明（与上方既有约定一致）。 ──
    { path: 'roster/resumed-students', name: 'aa-roster-resumed', component: () => import('@/modules/academicAffairs/views/AaRosterChangeResultListView.vue'), meta: { ...meta('academicAffairs.statusChange.view', '复学学生'), changeType: 'RESUME' } },
    { path: 'roster/transferred-major-students', name: 'aa-roster-transferred-major', component: () => import('@/modules/academicAffairs/views/AaRosterChangeResultListView.vue'), meta: { ...meta('academicAffairs.statusChange.view', '转专业学生'), changeType: 'TRANSFER_MAJOR' } },
    { path: 'roster/corrections', name: 'aa-roster-corrections', component: () => import('@/modules/academicAffairs/views/AaRosterCorrectionListView.vue'), meta: meta('academicAffairs.roster.correction.view', '学籍信息更正') },
    { path: 'roster/:studentId', name: 'aa-roster-detail', component: () => import('@/modules/academicAffairs/views/AaRosterDetailView.vue'), meta: meta('academicAffairs.roster.view', '学籍档案') },
    { path: 'registration', name: 'aa-registration', component: () => import('@/modules/academicAffairs/views/AaRegistrationBatchListView.vue'), meta: meta('academicAffairs.registration.view', '注册管理') },
    { path: 'registration/workbench', name: 'aa-registration-workbench', component: () => import('@/modules/academicAffairs/views/AaRegistrationWorkbenchView.vue'), meta: meta('academicAffairs.registration.eligibility.view', '注册工作台') },
    { path: 'registration/:batchId', name: 'aa-registration-detail', component: () => import('@/modules/academicAffairs/views/AaRegistrationDetailView.vue'), meta: meta('academicAffairs.registration.view', '注册名单') },
    { path: 'status-changes', name: 'aa-status-changes', component: () => import('@/modules/academicAffairs/views/AaStatusChangeListView.vue'), meta: meta('academicAffairs.statusChange.view', '学籍异动') },
    { path: 'status-changes/new', name: 'aa-status-change-new', component: () => import('@/modules/academicAffairs/views/AaStatusChangeFormView.vue'), meta: meta('academicAffairs.statusChange.manage', '发起异动') },
    // ── Tier1 R1：分类申请入口（休学/复学/退学/转专业，共用 AaStatusChangeTypedListView + changeType meta） ──
    { path: 'status-changes/suspend', name: 'aa-status-change-suspend', component: () => import('@/modules/academicAffairs/views/AaStatusChangeTypedListView.vue'), meta: { ...meta('academicAffairs.statusChange.apply', '休学申请'), changeType: 'SUSPEND' } },
    { path: 'status-changes/resume', name: 'aa-status-change-resume', component: () => import('@/modules/academicAffairs/views/AaStatusChangeTypedListView.vue'), meta: { ...meta('academicAffairs.statusChange.apply', '复学申请'), changeType: 'RESUME' } },
    { path: 'status-changes/withdraw', name: 'aa-status-change-withdraw', component: () => import('@/modules/academicAffairs/views/AaStatusChangeTypedListView.vue'), meta: { ...meta('academicAffairs.statusChange.apply', '退学申请'), changeType: 'WITHDRAW' } },
    { path: 'status-changes/transfer-major', name: 'aa-status-change-transfer-major', component: () => import('@/modules/academicAffairs/views/AaStatusChangeTypedListView.vue'), meta: { ...meta('academicAffairs.statusChange.apply', '转专业申请'), changeType: 'TRANSFER_MAJOR' } },
    // ── 学籍异动三级模块续工（第三轮补缺）：转班申请 / 留级(保留学籍)申请，共用 AaStatusChangeTypedListView ──
    { path: 'status-changes/transfer-class', name: 'aa-status-change-transfer-class', component: () => import('@/modules/academicAffairs/views/AaStatusChangeTypedListView.vue'), meta: { ...meta('academicAffairs.statusChange.apply', '转班申请'), changeType: 'TRANSFER_CLASS' } },
    { path: 'status-changes/retain', name: 'aa-status-change-retain', component: () => import('@/modules/academicAffairs/views/AaStatusChangeTypedListView.vue'), meta: { ...meta('academicAffairs.statusChange.apply', '保留学籍申请'), changeType: 'RETAIN' } },
    { path: 'status-changes/approval', name: 'aa-status-change-approval', component: () => import('@/modules/academicAffairs/views/AaStatusChangeApprovalView.vue'), meta: meta('academicAffairs.statusChange.collegeReview', '异动审批') },
    { path: 'status-changes/effective', name: 'aa-status-change-effective', component: () => import('@/modules/academicAffairs/views/AaStatusChangeEffectiveView.vue'), meta: meta('academicAffairs.statusChange.view', '异动生效') },
    { path: 'status-changes/stats', name: 'aa-status-change-stats', component: () => import('@/modules/academicAffairs/views/AaStatusChangeStatsView.vue'), meta: meta('academicAffairs.statusChange.view', '异动统计') },
    { path: 'status-changes/archive', name: 'aa-status-change-archive', component: () => import('@/modules/academicAffairs/views/AaStatusChangeArchiveView.vue'), meta: meta('academicAffairs.statusChange.view', '异动归档') },
    { path: 'status-changes/:id', name: 'aa-status-change-detail', component: () => import('@/modules/academicAffairs/views/AaStatusChangeDetailView.vue'), meta: meta('academicAffairs.statusChange.view', '异动详情') },
    // ── W3 课程库 + 培养方案 ──
    { path: 'courses', name: 'aa-courses', component: () => import('@/modules/academicAffairs/views/AaCourseListView.vue'), meta: meta('academicAffairs.course.view', '课程库') },
    { path: 'courses/new', name: 'aa-course-new', component: () => import('@/modules/academicAffairs/views/AaCourseFormView.vue'), meta: meta('academicAffairs.course.manage', '新建课程') },
    // Tier1 续工（2026-07-15）：课程分类/课程性质/学分学时/课程负责人/课程停用 5 个三级模块共用一个控制台（?tab= 深链接，对齐 programs/orgs 既有模式）
    { path: 'courses/console', name: 'aa-courses-console', component: () => import('@/modules/academicAffairs/views/AaCourseConsoleView.vue'), meta: meta('academicAffairs.course.view', '课程库控制台') },
    { path: 'courses/:id', name: 'aa-course-detail', component: () => import('@/modules/academicAffairs/views/AaCourseDetailView.vue'), meta: meta('academicAffairs.course.view', '课程详情') },
    { path: 'courses/:id/edit', name: 'aa-course-edit', component: () => import('@/modules/academicAffairs/views/AaCourseFormView.vue'), meta: meta('academicAffairs.course.manage', '编辑课程') },
    { path: 'programs', name: 'aa-programs', component: () => import('@/modules/academicAffairs/views/AaProgramListView.vue'), meta: meta('academicAffairs.program.view', '培养方案') },
    // Tier1 续工：方案制定/方案版本/课程模块/学分要求/毕业要求/方案审核/方案发布 共用一个控制台（?tab= 深链接，对齐 orgs/textbooks 既有模式）
    { path: 'programs/console', name: 'aa-programs-console', component: () => import('@/modules/academicAffairs/views/AaProgramConsoleView.vue'), meta: meta('academicAffairs.program.view', '培养方案控制台') },
    { path: 'programs/:id', name: 'aa-program-editor', component: () => import('@/modules/academicAffairs/views/AaProgramEditorView.vue'), meta: meta('academicAffairs.program.view', '方案编制') },
    // ── W4 教学任务 + 课表 ──
    { path: 'teaching-tasks', name: 'aa-teaching-tasks', component: () => import('@/modules/academicAffairs/views/AaTaskBatchListView.vue'), meta: meta('academicAffairs.teachingTask.view', '教学任务') },
    { path: 'teaching-tasks/assign', name: 'aa-teaching-task-assign', component: () => import('@/modules/academicAffairs/views/AaTeacherAssignConsoleView.vue'), meta: meta('academicAffairs.teachingTask.assign', '任课教师分配') },
    { path: 'teaching-tasks/merge-split', name: 'aa-teaching-task-merge-split', component: () => import('@/modules/academicAffairs/views/AaTaskMergeSplitView.vue'), meta: meta('academicAffairs.teachingTask.merge', '合班拆班') },
    { path: 'teaching-tasks/confirm', name: 'aa-teaching-task-confirm', component: () => import('@/modules/academicAffairs/views/AaTaskConfirmView.vue'), meta: meta('academicAffairs.teachingTask.confirm', '教学任务确认') },
    { path: 'teaching-tasks/teacher-confirm', name: 'aa-teaching-task-teacher-confirm', component: () => import('@/modules/academicAffairs/views/AaTeacherTaskConfirmView.vue'), meta: meta('academicAffairs.teachingTask.teacherConfirm', '教师任务确认') },
    { path: 'teaching-tasks/stats', name: 'aa-teaching-task-stats', component: () => import('@/modules/academicAffairs/views/AaTaskStatsView.vue'), meta: meta('academicAffairs.teachingTask.stats', '教学任务统计') },
    { path: 'teaching-tasks/:batchId', name: 'aa-task-detail', component: () => import('@/modules/academicAffairs/views/AaTaskDetailView.vue'), meta: meta('academicAffairs.teachingTask.view', '教学任务明细') },
    { path: 'schedule', name: 'aa-schedule', component: () => import('@/modules/academicAffairs/views/AaScheduleBatchListView.vue'), meta: meta('academicAffairs.schedule.view', '课表管理') },
    { path: 'schedule/:batchId/edit', name: 'aa-schedule-edit', component: () => import('@/modules/academicAffairs/views/AaScheduleMaintainView.vue'), meta: meta('academicAffairs.schedule.manage', '课表维护') },
    { path: 'schedule/:batchId/views', name: 'aa-schedule-views', component: () => import('@/modules/academicAffairs/views/AaScheduleViewsView.vue'), meta: meta('academicAffairs.schedule.view', '课表三视图') },
    // ── 课表管理 Tier1 R2：班级/教师/教室独立课表 + 发布 + 导出（自动取当前已发布批次，不需先选批次） ──
    { path: 'schedule/class/:classId?', name: 'aa-schedule-class', component: () => import('@/modules/academicAffairs/views/AaClassScheduleView.vue'), meta: meta('academicAffairs.schedule.view', '班级课表') },
    { path: 'schedule/teacher/:teacherKey?', name: 'aa-schedule-teacher', component: () => import('@/modules/academicAffairs/views/AaTeacherScheduleView.vue'), meta: meta('academicAffairs.schedule.view', '教师课表') },
    { path: 'schedule/room/:classroomId?', name: 'aa-schedule-room', component: () => import('@/modules/academicAffairs/views/AaRoomScheduleView.vue'), meta: meta('academicAffairs.classroom.view', '教室课表') },
    { path: 'schedule/publish', name: 'aa-schedule-publish', component: () => import('@/modules/academicAffairs/views/AaSchedulePublishView.vue'), meta: meta('academicAffairs.schedule.view', '课表发布') },
    { path: 'schedule/export', name: 'aa-schedule-export', component: () => import('@/modules/academicAffairs/views/AaScheduleExportView.vue'), meta: meta('academicAffairs.schedule.export', '课表导出') },
    // ── W5 成绩 · 预警 · 毕业预审 ──
    { path: 'grade-overview', name: 'aa-grade-overview', component: () => import('@/modules/academicAffairs/views/AaGradeOverviewView.vue'), meta: meta('academicAffairs.grade.view', '成绩总览') },
    { path: 'grade-fail', name: 'aa-grade-fail', component: () => import('@/modules/academicAffairs/views/AaGradeFailListView.vue'), meta: meta('academicAffairs.grade.view', '挂科清单') },
    { path: 'transcript', name: 'aa-transcript', component: () => import('@/modules/academicAffairs/views/AaTranscriptView.vue'), meta: meta('academicAffairs.grade.view', '学生成绩单') },
    { path: 'grade-entry', name: 'aa-grade-entry', component: () => import('@/modules/academicAffairs/views/AaGradeEntryView.vue'), meta: meta('academicAffairs.grade.input', '成绩录入') },
    { path: 'grade-college-review', name: 'aa-grade-college-review', component: () => import('@/modules/academicAffairs/views/AaGradeCollegeReviewView.vue'), meta: meta('academicAffairs.grade.collegeReview', '学院审核') },
    { path: 'grade-publish', name: 'aa-grade-publish', component: () => import('@/modules/academicAffairs/views/AaGradePublishView.vue'), meta: meta('academicAffairs.grade.publish', '教务发布') },
    { path: 'grade-change', name: 'aa-grade-change', component: () => import('@/modules/academicAffairs/views/AaGradeChangeView.vue'), meta: meta('academicAffairs.gradeChange.apply', '成绩更正') },
    { path: 'warnings', name: 'aa-warnings', component: () => import('@/modules/academicAffairs/views/AaWarningView.vue'), meta: meta('academicAffairs.warning.view', '学业预警') },
    // ── 学业预警二级模块 Tier1：看板/多维分类(学分·挂科·绩点·补考重修·毕业风险)/规则/跟进/统计，单控制台按 ?tab= 切换 ──
    { path: 'warnings/console', name: 'aa-warnings-console', component: () => import('@/modules/academicAffairs/views/AaWarningConsoleView.vue'), meta: meta('academicAffairs.warning.view', '学业预警控制台') },
    { path: 'graduation', name: 'aa-graduation', component: () => import('@/modules/academicAffairs/views/AaGraduationBatchView.vue'), meta: meta('academicAffairs.graduation.view', '毕业资格预审') },
    { path: 'graduation/:batchId/results', name: 'aa-graduation-results', component: () => import('@/modules/academicAffairs/views/AaGraduationResultView.vue'), meta: meta('academicAffairs.graduation.view', '毕业预审结果') },
    // ── Tier1（审核批次续建）：学分/课程/实践达成审核 + 毕设/实习/处分状态联动 + 终审/结果/归档，单控制台按 ?tab= 切换 ──
    { path: 'graduation/audit-console', name: 'aa-graduation-audit-console', component: () => import('@/modules/academicAffairs/views/AaGraduationAuditConsoleView.vue'), meta: meta('academicAffairs.graduation.view', '毕业资格审核工作台') },
    // ── 教务统计（只读聚合，11 项指标 + 下钻 + 导出） ──
    { path: 'stats', name: 'aa-stats', component: () => import('@/modules/academicAffairs/views/AaStatsOverviewView.vue'), meta: meta('academicAffairs.stats.view', '教务统计') },
    // ── R3 学院专业班级（组织架构，单控制台按 ?tab= 切换 学院/专业/年级/行政班/教学班/组织树/统计） ──
    { path: 'orgs', name: 'aa-orgs', component: () => import('@/modules/academicAffairs/views/AaOrgConsole.vue'), meta: meta('academicAffairs.org.view', '学院专业班级') },
    // ── R4 教学资源 · 教室字典 ──
    { path: 'classrooms', name: 'aa-classrooms', component: () => import('@/modules/academicAffairs/views/AaClassroomListView.vue'), meta: meta('academicAffairs.classroom.view', '教室资源') },
    { path: 'classroom-bookings', name: 'aa-classroom-bookings', component: () => import('@/modules/academicAffairs/views/AaClassroomBookingView.vue'), meta: meta('academicAffairs.classroom.view', '教室预约') },
    // ── R2 调停课（台账/发起/审批，通知单为独立打印路由） ──
    { path: 'schedule-change', name: 'aa-schedule-change-ledger', component: () => import('@/modules/academicAffairs/views/AaScheduleChangeLedgerView.vue'), meta: meta('academicAffairs.scheduleChange.view', '调停课台账') },
    { path: 'schedule-change/apply', name: 'aa-schedule-change-apply', component: () => import('@/modules/academicAffairs/views/AaScheduleChangeApplyView.vue'), meta: meta('academicAffairs.scheduleChange.apply', '发起调停课') },
    { path: 'schedule-change/approval', name: 'aa-schedule-change-approval', component: () => import('@/modules/academicAffairs/views/AaScheduleChangeApprovalView.vue'), meta: meta('academicAffairs.scheduleChange.collegeReview', '调停课审批') },
    // ── R2 调停课续工（冲突检测/统计/归档，Tier1 三级施工卡 07/08/09） ──
    { path: 'schedule-change/stats', name: 'aa-schedule-change-stats', component: () => import('@/modules/academicAffairs/views/AaScheduleChangeStatsView.vue'), meta: meta('academicAffairs.scheduleChange.view', '调停课统计') },
    { path: 'schedule-change/archive', name: 'aa-schedule-change-archive', component: () => import('@/modules/academicAffairs/views/AaScheduleChangeArchiveView.vue'), meta: meta('academicAffairs.scheduleChange.view', '调停课归档') },
    // ── 选课管理（教务处控制台 + 学生自助 + 归档） ──
    { path: 'selection', name: 'aa-selection', component: () => import('@/modules/academicAffairs/views/AaSelectionConsoleView.vue'), meta: meta('academicAffairs.selection.view', '选课管理') },
    { path: 'my-selection', name: 'aa-my-selection', component: () => import('@/modules/academicAffairs/views/AaSelectionStudentView.vue'), meta: meta('academicAffairs.selection.enroll', '我的选课') },
    { path: 'selection/archive', name: 'aa-selection-archive', component: () => import('@/modules/academicAffairs/views/AaSelectionArchiveView.vue'), meta: meta('academicAffairs.selection.manage', '选课归档') },
    // ── 考务管理（教务处控制台） ──
    { path: 'exam', name: 'aa-exam', component: () => import('@/modules/academicAffairs/views/AaExamConsoleView.vue'), meta: meta('academicAffairs.exam.view', '考务管理') },
    // ── 补考重修缓考免修 ──
    { path: 'makeup', name: 'aa-makeup', component: () => import('@/modules/academicAffairs/views/AaMakeupConsoleView.vue'), meta: meta('academicAffairs.makeup.view', '补考重修缓考免修') },
    { path: 'my-makeup', name: 'aa-my-makeup', component: () => import('@/modules/academicAffairs/views/AaMakeupStudentView.vue'), meta: meta('academicAffairs.retake.apply', '重修免修申请') },
    // ── 三级：统计分析 / 材料归档（三级施工卡 10/11） ──
    { path: 'makeup/stats', name: 'aa-makeup-stats', component: () => import('@/modules/academicAffairs/views/AaMakeupStatsView.vue'), meta: meta('academicAffairs.makeup.view', '补考重修缓考免修统计分析') },
    { path: 'exemption/archive', name: 'aa-exemption-archive', component: () => import('@/modules/academicAffairs/views/AaExemptionArchiveView.vue'), meta: meta('academicAffairs.makeup.archive', '免修材料归档') },
    // ── 教材管理（控制台） ──
    { path: 'textbooks', name: 'aa-textbooks', component: () => import('@/modules/academicAffairs/views/AaTextbookConsoleView.vue'), meta: meta('academicAffairs.textbook.view', '教材管理') },
    // ── 排课管理增强（规则/可用时间/冲突报告） ──
    { path: 'scheduling', name: 'aa-scheduling', component: () => import('@/modules/academicAffairs/views/AaSchedulingConsoleView.vue'), meta: meta('academicAffairs.schedule.view', '排课管理') },
    // ── 教学评价（控制台） ──
    { path: 'evaluation', name: 'aa-evaluation', component: () => import('@/modules/academicAffairs/views/AaEvaluationConsoleView.vue'), meta: meta('academicAffairs.evaluation.view', '教学评价') },
    // ── 教学质量（运行质量看板，零新表聚合） ──
    { path: 'quality', name: 'aa-quality', component: () => import('@/modules/academicAffairs/views/AaQualityDashboardView.vue'), meta: meta('academicAffairs.quality.dashboard.view', '教学质量') },
    // ── 教务归档（批次+完整性检查+封存；10/11/12 三级卡：缺失提醒/批量归档/导出） ──
    { path: 'archive', name: 'aa-archive', component: () => import('@/modules/academicAffairs/views/AaArchiveConsoleView.vue'), meta: meta('academicAffairs.archive.view', '教务归档') },
    { path: 'archive/precheck', name: 'aa-archive-precheck', component: () => import('@/modules/academicAffairs/views/ArchivePrecheckView.vue'), meta: meta('academicAffairs.archive.view', '归档缺失提醒') },
    { path: 'archive/export', name: 'aa-archive-export', component: () => import('@/modules/academicAffairs/views/ArchiveExportView.vue'), meta: meta('academicAffairs.archive.export', '归档导出') }
  ]
}

const printExamSeatingRoute = {
  path: '/admin/academic-affairs/exam/print/seating',
  name: 'aa-exam-seating-print',
  component: () => import('@/modules/academicAffairs/views/AaExamSeatingPrintView.vue'),
  meta: { moduleCode: MOD, requiresAuth: true, permissionKey: 'academicAffairs.exam.view', title: '座位表/准考证打印' }
}

const printScheduleChangeNoticeRoute = {
  path: '/admin/academic-affairs/print/schedule-change/:id/notice',
  name: 'aa-schedule-change-notice',
  component: () => import('@/modules/academicAffairs/views/AaScheduleChangeNoticePrintView.vue'),
  meta: { moduleCode: MOD, requiresAuth: true, permissionKey: 'academicAffairs.scheduleChange.view', title: '调停课通知单' }
}

const printScheduleRoute = {
  path: '/admin/academic-affairs/print/schedule/:batchId',
  name: 'aa-print-schedule',
  component: () => import('@/modules/academicAffairs/views/AaPrintScheduleView.vue'),
  meta: { moduleCode: MOD, requiresAuth: true, permissionKey: 'academicAffairs.schedule.view', title: '课表打印' }
}

const printStatusChangeRoute = {
  path: '/admin/academic-affairs/print/status-change/:id',
  name: 'aa-print-status-change',
  component: () => import('@/modules/academicAffairs/views/AaStatusChangePrintView.vue'),
  meta: { moduleCode: MOD, requiresAuth: true, permissionKey: 'academicAffairs.statusChange.view', title: '异动审批表打印' }
}

const printTranscriptRoute = {
  path: '/admin/academic-affairs/print/transcript/:studentId',
  name: 'aa-print-transcript',
  component: () => import('@/modules/academicAffairs/views/AaTranscriptPrintView.vue'),
  meta: { moduleCode: MOD, requiresAuth: true, permissionKey: 'academicAffairs.grade.view', title: '成绩单打印' }
}

const printMakeupBatchRoute = {
  path: '/admin/academic-affairs/makeup/batches/:id/print',
  name: 'aa-makeup-print',
  component: () => import('@/modules/academicAffairs/views/AaMakeupPrintView.vue'),
  meta: { moduleCode: MOD, requiresAuth: true, permissionKey: 'academicAffairs.makeup.archive', title: '补考安排表打印' }
}

export const academicAffairsRoutes = [layoutRoute, printStatusChangeRoute, printScheduleRoute, printTranscriptRoute, printScheduleChangeNoticeRoute, printExamSeatingRoute, printMakeupBatchRoute]

export default academicAffairsRoutes
