import { createRouter, createWebHistory } from 'vue-router'
import { guard } from '../platform/permissionGuard'

const routes = [
  { path: '/login', name: 'login', meta: { public: true }, component: () => import('../views/login/LoginView.vue') },
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
      { path: 'internship/compliance', name: 'internship-compliance', meta: { modulePath: 'internship' }, component: () => import('../views/internship/InternshipComplianceView.vue') },
      { path: 'employment', name: 'employment', meta: { modulePath: 'employment' }, component: () => import('../views/employment/EmploymentView.vue') },
      { path: 'orientation', name: 'orientation', meta: { modulePath: 'orientation' }, component: () => import('../views/orientation/OrientationView.vue') },
      { path: 'messages', name: 'messages', meta: { modulePath: 'messages' }, component: () => import('../views/messages/MessagesView.vue') },
      { path: 'service-hall', name: 'service-hall', component: () => import('../views/hall/ServiceHallView.vue') },
      { path: 'graduation', name: 'graduation-workbench', meta: { modulePath: 'graduation' }, component: () => import('../views/graduation/GraduationWorkbenchView.vue') },
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
