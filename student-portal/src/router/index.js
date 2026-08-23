import { createRouter, createWebHistory } from 'vue-router'
import { guard } from '../platform/permissionGuard'

const routes = [
  { path: '/login', name: 'login', meta: { public: true }, component: () => import('../views/login/LoginView.vue') },
  { path: '/force-password-change', name: 'force-password-change', component: () => import('../views/login/ForcePasswordChangeView.vue') },
  { path: '/guardian', name: 'guardian', meta: { public: true }, component: () => import('../views/guardian/GuardianView.vue') },
  {
    path: '/',
    component: () => import('../layouts/PortalLayout.vue'),
    children: [
      { path: '', redirect: '/home' },
      { path: 'home', name: 'home', component: () => import('../views/home/HomeView.vue') },
      { path: 'not-enabled', name: 'not-enabled', component: () => import('../components/NotEnabledView.vue') },
      { path: 'module-disabled/:module', name: 'module-disabled', component: () => import('../components/ModuleDisabledView.vue') },
      { path: 'profile', name: 'profile', meta: { modulePath: 'profile' }, component: () => import('../views/profile/ProfileView.vue') },
      { path: 'academic', name: 'academic', meta: { modulePath: 'academic' }, component: () => import('../views/academic/AcademicView.vue') },
      { path: 'campus-service', name: 'campus-service', meta: { modulePath: 'campus-service' }, component: () => import('../views/affairs/AffairsFourEndView.vue') },
      { path: 'materials', name: 'material-supplement', meta: { modulePath: 'campus-service' }, component: () => import('../views/affairs/MaterialSupplementView.vue') },
      { path: 'internship', name: 'internship', meta: { modulePath: 'internship' }, component: () => import('../views/internship/InternshipView.vue') },
      { path: 'internship/selection', name: 'internship-selection', meta: { modulePath: 'internship' }, component: () => import('../views/internship/InternshipSelectionView.vue') },
      { path: 'internship/selection/company/:companyId', name: 'internship-selection-company', meta: { modulePath: 'internship' }, component: () => import('../views/internship/EnterprisePublicView.vue') },
      { path: 'internship/profile', name: 'internship-profile', meta: { modulePath: 'internship' }, component: () => import('../views/internship/InternshipProfileView.vue') },
      { path: 'internship/compliance', name: 'internship-compliance', meta: { modulePath: 'internship' }, component: () => import('../views/internship/InternshipComplianceView.vue') },
      { path: 'employment', name: 'employment', meta: { modulePath: 'employment' }, component: () => import('../views/employment/EmploymentView.vue') },
      { path: 'orientation', name: 'orientation', meta: { modulePath: 'orientation' }, component: () => import('../views/orientation/OrientationView.vue') },
      // SP-D04：离校与迎新相隔整个学制，权限、路由与消息 target 都不该混在一起。
      // 正式入口独立成 /departure；Orientation 的旧「离校」tab 保留为兼容入口并引导过来，
      // 不删除历史路径。（不使用 /clearance——仓库里那是"清考"语义。）
      { path: 'departure', name: 'departure', component: () => import('../views/departure/DepartureView.vue') },
      { path: 'messages', name: 'messages', meta: { modulePath: 'messages' }, component: () => import('../views/messages/MessagesView.vue') },
      { path: 'service-hall', name: 'service-hall', component: () => import('../views/hall/ServiceHallView.vue') },
      { path: 'graduation/materials', name: 'graduation-material-library', meta: { modulePath: 'graduation' }, component: () => import('../views/graduation/GraduationMaterialsView.vue') },
      { path: 'graduation/feedback', name: 'graduation-feedback', meta: { modulePath: 'graduation' }, component: () => import('../views/graduation/GraduationFeedbackResubmitView.vue') },
      { path: 'graduation', name: 'graduation-workbench', meta: { modulePath: 'graduation' }, component: () => import('../views/graduation/GraduationStudentClosureView.vue') },
      { path: ':module', name: 'module', component: () => import('../views/template/ModuleTemplateView.vue') }
    ]
  },
  { path: '/:pathMatch(.*)*', redirect: '/home' }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

router.beforeEach(guard)

export default router