import { createRouter, createWebHistory } from 'vue-router'
import { guard } from '../platform/permissionGuard'

const routes = [
  { path: '/login', name: 'login', meta: { public: true }, component: () => import('../views/login/LoginView.vue') },
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
      { path: 'academic', name: 'academic', meta: { modulePath: 'academic' }, component: () => import('../views/academic/AcademicView.vue') },
      { path: 'campus-service', name: 'campus-service', meta: { modulePath: 'campus-service' }, component: () => import('../views/affairs/AffairsView.vue') },
      { path: 'internship', name: 'internship', meta: { modulePath: 'internship' }, component: () => import('../views/internship/InternshipView.vue') },
      { path: 'employment', name: 'employment', meta: { modulePath: 'employment' }, component: () => import('../views/employment/EmploymentView.vue') },
      { path: 'orientation', name: 'orientation', meta: { modulePath: 'orientation' }, component: () => import('../views/orientation/OrientationView.vue') },
      { path: 'messages', name: 'messages', meta: { modulePath: 'messages' }, component: () => import('../views/messages/MessagesView.vue') },
      // 办事大厅：一站式聚合入口，始终可见（不含独立后端模块开关）。
      { path: 'service-hall', name: 'service-hall', component: () => import('../views/hall/ServiceHallView.vue') },
      // 毕设是学生端的重流程模块，使用专用工作台而非通用数据模板页。
      { path: 'graduation', name: 'graduation-workbench', component: () => import('../views/graduation/GraduationWorkbenchView.vue') },
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
