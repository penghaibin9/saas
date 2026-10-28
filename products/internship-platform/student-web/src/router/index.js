import { createRouter, createWebHistory } from 'vue-router'
import { pinia } from '../stores'
import { useSessionStore } from '../stores/session'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/login', name: 'login', meta: { public: true }, component: () => import('../views/LoginView.vue') },
    { path: '/account/security', component: () => import('../views/PasswordChangeView.vue') },
    { path: '/', redirect: '/internship' },
    { path: '/messages', name: 'messages', component: () => import('../views/MessagesView.vue') },
    { path: '/internship', name: 'internship', component: () => import('../views/internship/InternshipView.vue') },
    { path: '/internship/selection', meta: { internshipView: 'selection' }, component: () => import('../views/internship/InternshipSelectionView.vue') },
    { path: '/internship/profile', meta: { internshipView: 'profile' }, component: () => import('../views/internship/InternshipProfileView.vue') },
    { path: '/internship/selection/company/:companyId', meta: { internshipView: 'selection' }, component: () => import('../views/internship/EnterprisePublicView.vue') },
    { path: '/internship/volunteer-result', meta: { internshipView: 'selection' }, component: () => import('../views/internship/InternshipVolunteerResultView.vue') },
    { path: '/internship/compliance', meta: { internshipView: 'safety' }, component: () => import('../views/internship/InternshipComplianceView.vue') },
    { path: '/internship/materials', meta: { internshipView: 'materials' }, component: () => import('../views/internship/InternshipMaterialsView.vue') },
    { path: '/:pathMatch(.*)*', redirect: '/internship' }
  ]
})

router.beforeEach(async (to) => {
  if (to.meta.public) return true
  const session = useSessionStore(pinia)
  await session.restore()
  if (!session.isLoggedIn) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (session.user.mustChangePassword && to.path !== '/account/security') return '/account/security'
  return true
})

export default router
