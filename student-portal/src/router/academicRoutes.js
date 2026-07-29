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
    academicSection('exam', 'academic-exam', '考试/缓考/免修', '考试、缓考与补重修', '查看考试安排，处理缓考、补考、重修和免修事项'),
    academicSection('makeup', 'academic-makeup', '考试/缓考/免修', '补考重修', '从当前有效未通过课程发起补考重修或免修申请', '补考重修申请'),
    academicSection('attendance', 'academic-attendance', '我的考勤', '课堂考勤', '查看本人课堂考勤记录和汇总'),
    academicSection('calendar', 'academic-calendar', '校历', '校历', '查看当前学期教学周、节假日和考试周'),
    academicSection('clearance', 'academic-clearance', '清考结果', '清考结果', '查看本人清考课程和最终结果'),
    academicSection('credits', 'academic-credits', '学分修读', '学分修读', '核对已获学分、绩点和达成情况'),
    academicSection('warning', 'academic-warning', '学业预警', '学业预警', '查看预警原因、责任老师和后续处理要求'),
    academicSection('textbook', 'academic-textbook', '教材领用', '教材领用', '查看教材、费用并完成本人签收'),
    academicSection('level-exam', 'academic-level-exam', '等级考试', '等级考试', '报名开放中的等级考试并查看报名状态'),
    academicSection('major-split', 'academic-major-split', '专业分流', '专业分流', '填写专业分流志愿并查看录取结果'),
    academicSection('recognition', 'academic-recognition', '成绩认定', '成绩认定与课程替代', '提交校外课程成绩认定或课程替代申请'),
    academicSection('graduation', 'academic-graduation', '毕业自查', '毕业资格自查', '逐项查看毕业条件、缺口和证据来源'),
    { path: 'all', name: 'academic-all', meta: { modulePath: 'academic' }, component: () => import('../views/academic/AcademicLegacySafeView.vue') }
  ]
}

export function installAcademicRoutes(router) {
  if (router.hasRoute('academic')) router.removeRoute('academic')
  if (!router.hasRoute('academic-shell')) router.addRoute(academicRoute)
}

export default installAcademicRoutes
