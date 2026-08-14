import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/login', name: 'enterprise-login', component: () => import('../views/EnterpriseLoginView.vue'), meta: { public: true } },
  { path: '/invite/:token', name: 'invite-accept', component: () => import('../views/InviteAcceptView.vue'), meta: { public: true } },
  {
    path: '/',
    component: () => import('../layouts/EnterprisePortalLayout.vue'),
    children: [
      { path: '', redirect: '/home' },
      { path: 'home', name: 'enterprise-home', component: () => import('../views/EnterpriseHomeView.vue') },
      { path: 'company', name: 'company-profile', component: () => import('../views/CompanyProfileView.vue') },
      { path: 'positions', name: 'position-list', component: () => import('../views/PositionListView.vue') },
      { path: 'positions/new', name: 'position-new', component: () => import('../views/PositionFormView.vue') },
      { path: 'positions/:id/edit', name: 'position-edit', component: () => import('../views/PositionFormView.vue') },
      { path: 'applications', name: 'application-list', component: () => import('../views/ApplicantListView.vue') },
      { path: 'applications/:id', name: 'application-detail', component: () => import('../views/ApplicantListView.vue') },
      { path: 'students', name: 'internship-students', component: () => import('../views/InternshipStudentListView.vue') },
      { path: 'evaluations', name: 'evaluation-tasks', component: () => import('../views/EvaluationTaskListView.vue') },
    ],
  },
  { path: '/:pathMatch(.*)*', redirect: '/home' },
]

export default createRouter({ history: createWebHistory(import.meta.env.BASE_URL), routes })
