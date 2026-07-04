/**
 * 毕业设计中心模块路由（自包含，未接入全局 router）。
 * 接入方式（由负责全局 router 的任务/人执行）：
 *   import graduationRoutes from '@/modules/graduation/routes'
 *   routes: [...existing, graduationRoutes]
 */
const graduationRoutes = {
  path: '/admin/graduation',
  component: () => import('@/views/admin/graduation/AdminGraduationLayout.vue'),
  meta: { moduleCode: 'GRADUATION' },
  children: [
    {
      path: '',
      name: 'graduation-dashboard',
      component: () => import('@/views/admin/graduation/GraduationDashboardView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '毕业设计中心', requiresAuth: true, permissionKey: 'graduation.dashboard.view' }
    },
    {
      path: 'students',
      name: 'graduation-students',
      component: () => import('@/views/admin/graduation/GraduationStudentListView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '毕设学生列表', requiresAuth: true, permissionKey: 'graduation.student.view' }
    },
    {
      path: 'students/:id',
      name: 'graduation-student-detail',
      component: () => import('@/views/admin/graduation/GraduationStudentDetailView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '毕设学生详情', requiresAuth: true, permissionKey: 'graduation.student.view' }
    },
    {
      path: 'topics',
      name: 'graduation-topics',
      component: () => import('@/views/admin/graduation/TopicManageView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '选题管理', requiresAuth: true, permissionKey: 'graduation.topic.manage' }
    },
    {
      path: 'proposals',
      name: 'graduation-proposals',
      component: () => import('@/views/admin/graduation/ProposalListView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '开题材料列表', requiresAuth: true, permissionKey: 'graduation.proposal.view' }
    },
    {
      path: 'proposals/:id',
      name: 'graduation-proposal-detail',
      component: () => import('@/views/admin/graduation/ProposalReviewDetailView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '开题批阅详情', requiresAuth: true, permissionKey: 'graduation.proposal.view' }
    },
    {
      path: 'finals',
      name: 'graduation-finals',
      component: () => import('@/views/admin/graduation/FinalSubmissionListView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '成果提交列表', requiresAuth: true, permissionKey: 'graduation.final.view' }
    },
    {
      path: 'defense',
      name: 'graduation-defense',
      component: () => import('@/views/admin/graduation/DefenseScheduleView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '答辩安排管理', requiresAuth: true, permissionKey: 'graduation.defense.manage' }
    }
  ]
}

export default graduationRoutes
