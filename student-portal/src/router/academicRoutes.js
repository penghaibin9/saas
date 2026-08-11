const academicSection = (path, name, tab, title, description, subTab = '') => ({
  path,
  name,
  meta: {
    modulePath: 'academic',
    academicTab: tab,
    academicSubTab: subTab,
    academicTitle: title,
    academicDescription: description
  },
  component: () => import('../views/academic/AcademicSectionRouteView.vue')
})

const academicReadOnly = (path, name, academicReadModel) => ({
  path,
  name,
  meta: { modulePath: 'academic', academicReadModel },
  component: () => import('../views/academic/StudentAcademicReadOnlyView.vue')
})

export const academicRoute = {
  path: '/academic',
  name: 'academic-shell',
  component: () => import('../layouts/PortalLayout.vue'),
  children: [
    { path: '', name: 'academic-home', meta: { modulePath: 'academic' }, component: () => import('../views/academic/StudentAcademicHomeView.vue') },
    { path: 'schedule', name: 'academic-schedule', meta: { modulePath: 'academic' }, component: () => import('../views/academic/StudentScheduleView.vue') },
    { path: 'grades', name: 'academic-grades', meta: { modulePath: 'academic' }, component: () => import('../views/academic/StudentGradesView.vue') },
    { path: 'registration', name: 'academic-registration', meta: { modulePath: 'academic' }, component: () => import('../views/academic/StudentRegistrationView.vue') },
    { path: 'selection', name: 'academic-selection', meta: { modulePath: 'academic' }, component: () => import('../views/academic/StudentSelectionView.vue') },
    { path: 'evaluation', name: 'academic-evaluation', meta: { modulePath: 'academic' }, component: () => import('../views/academic/StudentEvaluationView.vue') },
    { path: 'recheck', name: 'academic-recheck', meta: { modulePath: 'academic' }, component: () => import('../views/academic/StudentRecheckView.vue') },
    academicSection('status', 'academic-status', '学籍异动', '学籍与异动', '查看当前学籍并发起休学、复学、转专业等申请'),
    { path: 'exam', name: 'academic-exam', meta: { modulePath: 'academic' }, component: () => import('../views/academic/StudentExamView.vue') },
    { path: 'makeup', name: 'academic-makeup', meta: { modulePath: 'academic' }, component: () => import('../views/academic/StudentMakeupView.vue') },
    academicReadOnly('attendance', 'academic-attendance', 'attendance'),
    academicReadOnly('calendar', 'academic-calendar', 'calendar'),
    academicReadOnly('clearance', 'academic-clearance', 'clearance'),
    academicReadOnly('credits', 'academic-credits', 'credits'),
    academicReadOnly('warning', 'academic-warning', 'warning'),
    { path: 'textbook', name: 'academic-textbook', meta: { modulePath: 'academic' }, component: () => import('../views/academic/StudentTextbookView.vue') },
    { path: 'level-exam', name: 'academic-level-exam', meta: { modulePath: 'academic' }, component: () => import('../views/academic/StudentLevelExamView.vue') },
    { path: 'major-split', name: 'academic-major-split', meta: { modulePath: 'academic' }, component: () => import('../views/academic/StudentMajorSplitView.vue') },
    academicSection('recognition', 'academic-recognition', '成绩认定', '成绩认定与课程替代', '提交校外课程成绩认定或课程替代申请'),
    { path: 'graduation', name: 'academic-graduation', meta: { modulePath: 'academic' }, component: () => import('../views/academic/StudentGraduationAuditView.vue') },
    { path: 'all', name: 'academic-all', meta: { modulePath: 'academic' }, component: () => import('../views/academic/AcademicLegacySafeView.vue') }
  ]
}

export function installAcademicRoutes(router) {
  if (router.hasRoute('academic')) router.removeRoute('academic')
  if (!router.hasRoute('academic-shell')) router.addRoute(academicRoute)
}

export default installAcademicRoutes
