import { createRouter, createWebHistory } from 'vue-router'
import { guard } from '../platform/permissionGuard'

const optionalViews = import.meta.glob('../views/**/*.vue')
const optionalView = (relativePath, fallback) =>
  optionalViews[`../views/${relativePath}.vue`] || fallback

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

const routes = [
  { path: '/login', name: 'login', meta: { public: true }, component: () => import('../views/login/LoginView.vue') },
  // 家长端：独立只读子应用（手机验证码登录，与学生门户外壳物理隔离）。
  { path: '/guardian', name: 'guardian', meta: { public: true }, component: () => import('../views/guardian/GuardianView.vue') },
  {
    // history base 已经是 /portal/，业务路由不再重复写 portal 前缀。
    path: '/',
    component: () => import('../layouts/PortalLayout.vue'),
    children: [
      { path: '', redirect: '/home' },
      { path: 'home', name: 'home', component: () => import('../views/home/HomeView.vue') },
      { path: 'not-enabled', name: 'not-enabled', component: () => import('../components/NotEnabledView.vue') },
      { path: 'module-disabled/:module', name: 'module-disabled', component: () => import('../components/ModuleDisabledView.vue') },
      // 各二级模块专用工作台（消费 /portal/* 重活接口）。meta.modulePath 供守卫做模块开关门禁。
      { path: 'profile', name: 'profile', meta: { modulePath: 'profile' }, component: () => import('../views/profile/ProfileView.vue') },

      // V2 R6：学生 PC 教务从单一综合页拆为稳定独立路由。旧 /academic/all 只做兼容追溯。
      { path: 'academic', name: 'academic-home', meta: { modulePath: 'academic' }, component: () => import('../views/academic/StudentAcademicHomeView.vue') },
      { path: 'academic/schedule', name: 'academic-schedule', meta: { modulePath: 'academic' }, component: () => import('../views/academic/StudentScheduleView.vue') },
      { path: 'academic/grades', name: 'academic-grades', meta: { modulePath: 'academic' }, component: () => import('../views/academic/StudentGradesView.vue') },
      { path: 'academic/registration', name: 'academic-registration', meta: { modulePath: 'academic' }, component: () => import('../views/academic/StudentRegistrationView.vue') },
      academicSection('academic/selection', 'academic-selection', '选课中心', '网上选课', '查询可选课程、完成选课退课并核对已选记录'),
      { path: 'academic/evaluation', name: 'academic-evaluation', meta: { modulePath: 'academic' }, component: () => import('../views/academic/StudentEvaluationView.vue') },
      academicSection('academic/recheck', 'academic-recheck', '成绩复查', '成绩复查', '对本人已发布成绩申请复查并查看处理结果'),
      academicSection('academic/status', 'academic-status', '学籍异动', '学籍与异动', '查看当前学籍并发起休学、复学、转专业等申请'),
      academicSection('academic/exam', 'academic-exam', '考试/缓考/免修', '考试、缓考与补重修', '查看考试安排，处理缓考、补考、重修和免修事项'),
      academicSection('academic/makeup', 'academic-makeup', '考试/缓考/免修', '补考重修', '从当前有效未通过课程发起补考重修或免修申请', '补考重修申请'),
      academicSection('academic/attendance', 'academic-attendance', '我的考勤', '课堂考勤', '查看本人课堂考勤记录和汇总'),
      academicSection('academic/calendar', 'academic-calendar', '校历', '校历', '查看当前学期教学周、节假日和考试周'),
      academicSection('academic/clearance', 'academic-clearance', '清考结果', '清考结果', '查看本人清考课程和最终结果'),
      academicSection('academic/credits', 'academic-credits', '学分修读', '学分修读', '核对已获学分、绩点和培养要求达成情况'),
      academicSection('academic/warning', 'academic-warning', '学业预警', '学业预警', '查看预警原因、责任老师和后续处理要求'),
      academicSection('academic/textbook', 'academic-textbook', '教材领用', '教材领用', '查看教材、费用并完成本人签收'),
      academicSection('academic/level-exam', 'academic-level-exam', '等级考试', '等级考试', '报名开放中的等级考试并查看报名状态'),
      academicSection('academic/major-split', 'academic-major-split', '专业分流', '专业分流', '填写专业分流志愿并查看录取结果'),
      academicSection('academic/recognition', 'academic-recognition', '成绩认定', '成绩认定与课程替代', '提交校外课程成绩认定或课程替代申请'),
      academicSection('academic/graduation', 'academic-graduation', '毕业自查', '毕业资格自查', '逐项查看毕业条件、缺口和证据来源'),
      { path: 'academic/all', name: 'academic-all', meta: { modulePath: 'academic' }, component: () => import('../views/academic/AcademicLegacySafeView.vue') },

      { path: 'campus-service', name: 'campus-service', meta: { modulePath: 'campus-service' }, component: () => import('../views/affairs/AffairsView.vue') },
      { path: 'internship', name: 'internship', meta: { modulePath: 'internship' }, component: () => import('../views/internship/InternshipView.vue') },
      {
        path: 'internship/compliance',
        name: 'internship-compliance',
        meta: { modulePath: 'internship' },
        component: optionalView(
          'internship/InternshipComplianceView',
          () => import('../views/internship/InternshipView.vue')
        )
      },
      { path: 'employment', name: 'employment', meta: { modulePath: 'employment' }, component: () => import('../views/employment/EmploymentView.vue') },
      { path: 'orientation', name: 'orientation', meta: { modulePath: 'orientation' }, component: () => import('../views/orientation/OrientationView.vue') },
      { path: 'messages', name: 'messages', meta: { modulePath: 'messages' }, component: () => import('../views/messages/MessagesView.vue') },
      // 办事大厅：一站式聚合入口，始终可见（不含独立后端模块开关）。
      { path: 'service-hall', name: 'service-hall', component: () => import('../views/hall/ServiceHallView.vue') },
      // 毕设是学生端的重流程模块，使用专用工作台而非通用数据模板页。
      { path: 'graduation', name: 'graduation-workbench', meta: { modulePath: 'graduation' }, component: () => import('../views/graduation/GraduationWorkbenchView.vue') },
      { path: ':module', name: 'module', component: () => import('../views/template/ModuleTemplateView.vue') }
    ]
  },
  { path: '/:pathMatch(.*)*', redirect: '/home' }
]

// history base 取自 Vite base（默认 /portal/，可 VITE_BASE 覆盖），刷新子路由不 404（配合 nginx try_files）
const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

router.beforeEach(guard)

export default router
