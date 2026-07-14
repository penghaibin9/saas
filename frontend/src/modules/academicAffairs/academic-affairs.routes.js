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
    { path: 'calendar', name: 'aa-calendar', component: () => import('@/modules/academicAffairs/views/AaCalendarView.vue'), meta: meta('academicAffairs.calendar.view', '校历管理') },
    { path: 'time-slots', name: 'aa-time-slots', component: () => import('@/modules/academicAffairs/views/AaTimeSlotView.vue'), meta: meta('academicAffairs.timeslot.view', '作息节次') },
    // ── W2 学籍写侧闭环 ──
    { path: 'roster', name: 'aa-roster', component: () => import('@/modules/academicAffairs/views/AaRosterListView.vue'), meta: meta('academicAffairs.roster.view', '学籍名册') },
    { path: 'registration', name: 'aa-registration', component: () => import('@/modules/academicAffairs/views/AaRegistrationBatchListView.vue'), meta: meta('academicAffairs.registration.view', '注册管理') },
    { path: 'registration/:batchId', name: 'aa-registration-detail', component: () => import('@/modules/academicAffairs/views/AaRegistrationDetailView.vue'), meta: meta('academicAffairs.registration.view', '注册名单') },
    { path: 'status-changes', name: 'aa-status-changes', component: () => import('@/modules/academicAffairs/views/AaStatusChangeListView.vue'), meta: meta('academicAffairs.statusChange.view', '学籍异动') },
    { path: 'status-changes/new', name: 'aa-status-change-new', component: () => import('@/modules/academicAffairs/views/AaStatusChangeFormView.vue'), meta: meta('academicAffairs.statusChange.manage', '发起异动') },
    { path: 'status-changes/:id', name: 'aa-status-change-detail', component: () => import('@/modules/academicAffairs/views/AaStatusChangeDetailView.vue'), meta: meta('academicAffairs.statusChange.view', '异动详情') },
    // ── W3 课程库 + 培养方案 ──
    { path: 'courses', name: 'aa-courses', component: () => import('@/modules/academicAffairs/views/AaCourseListView.vue'), meta: meta('academicAffairs.course.view', '课程库') },
    { path: 'courses/new', name: 'aa-course-new', component: () => import('@/modules/academicAffairs/views/AaCourseFormView.vue'), meta: meta('academicAffairs.course.manage', '新建课程') },
    { path: 'courses/:id', name: 'aa-course-detail', component: () => import('@/modules/academicAffairs/views/AaCourseDetailView.vue'), meta: meta('academicAffairs.course.view', '课程详情') },
    { path: 'courses/:id/edit', name: 'aa-course-edit', component: () => import('@/modules/academicAffairs/views/AaCourseFormView.vue'), meta: meta('academicAffairs.course.manage', '编辑课程') },
    { path: 'programs', name: 'aa-programs', component: () => import('@/modules/academicAffairs/views/AaProgramListView.vue'), meta: meta('academicAffairs.program.view', '培养方案') },
    { path: 'programs/:id', name: 'aa-program-editor', component: () => import('@/modules/academicAffairs/views/AaProgramEditorView.vue'), meta: meta('academicAffairs.program.view', '方案编制') },
    // ── W4 教学任务 + 课表 ──
    { path: 'teaching-tasks', name: 'aa-teaching-tasks', component: () => import('@/modules/academicAffairs/views/AaTaskBatchListView.vue'), meta: meta('academicAffairs.teachingTask.view', '教学任务') },
    { path: 'teaching-tasks/:batchId', name: 'aa-task-detail', component: () => import('@/modules/academicAffairs/views/AaTaskDetailView.vue'), meta: meta('academicAffairs.teachingTask.view', '教学任务明细') },
    { path: 'schedule', name: 'aa-schedule', component: () => import('@/modules/academicAffairs/views/AaScheduleBatchListView.vue'), meta: meta('academicAffairs.schedule.view', '课表管理') },
    { path: 'schedule/:batchId/edit', name: 'aa-schedule-edit', component: () => import('@/modules/academicAffairs/views/AaScheduleMaintainView.vue'), meta: meta('academicAffairs.schedule.manage', '课表维护') },
    { path: 'schedule/:batchId/views', name: 'aa-schedule-views', component: () => import('@/modules/academicAffairs/views/AaScheduleViewsView.vue'), meta: meta('academicAffairs.schedule.view', '课表三视图') },
    // ── W5 成绩 · 预警 · 毕业预审 ──
    { path: 'grade-overview', name: 'aa-grade-overview', component: () => import('@/modules/academicAffairs/views/AaGradeOverviewView.vue'), meta: meta('academicAffairs.grade.view', '成绩总览') },
    { path: 'grade-fail', name: 'aa-grade-fail', component: () => import('@/modules/academicAffairs/views/AaGradeFailListView.vue'), meta: meta('academicAffairs.grade.view', '挂科清单') },
    { path: 'transcript', name: 'aa-transcript', component: () => import('@/modules/academicAffairs/views/AaTranscriptView.vue'), meta: meta('academicAffairs.grade.view', '学生成绩单') },
    { path: 'grade-entry', name: 'aa-grade-entry', component: () => import('@/modules/academicAffairs/views/AaGradeEntryView.vue'), meta: meta('academicAffairs.grade.input', '成绩录入') },
    { path: 'grade-college-review', name: 'aa-grade-college-review', component: () => import('@/modules/academicAffairs/views/AaGradeCollegeReviewView.vue'), meta: meta('academicAffairs.grade.collegeReview', '学院审核') },
    { path: 'grade-publish', name: 'aa-grade-publish', component: () => import('@/modules/academicAffairs/views/AaGradePublishView.vue'), meta: meta('academicAffairs.grade.publish', '教务发布') },
    { path: 'grade-change', name: 'aa-grade-change', component: () => import('@/modules/academicAffairs/views/AaGradeChangeView.vue'), meta: meta('academicAffairs.gradeChange.apply', '成绩更正') },
    { path: 'warnings', name: 'aa-warnings', component: () => import('@/modules/academicAffairs/views/AaWarningView.vue'), meta: meta('academicAffairs.warning.view', '学业预警') },
    { path: 'graduation', name: 'aa-graduation', component: () => import('@/modules/academicAffairs/views/AaGraduationBatchView.vue'), meta: meta('academicAffairs.graduation.view', '毕业资格预审') },
    { path: 'graduation/:batchId/results', name: 'aa-graduation-results', component: () => import('@/modules/academicAffairs/views/AaGraduationResultView.vue'), meta: meta('academicAffairs.graduation.view', '毕业预审结果') }
  ]
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

export const academicAffairsRoutes = [layoutRoute, printStatusChangeRoute, printScheduleRoute, printTranscriptRoute]

export default academicAffairsRoutes
