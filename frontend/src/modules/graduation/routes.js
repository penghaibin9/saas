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
      path: 'topic-lib',
      name: 'graduation-topic-lib',
      component: () => import('@/views/admin/graduation/TopicLibListView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '题目库', requiresAuth: true, permissionKey: 'graduation.topic.lib' }
    },
    {
      path: 'topic-rounds',
      name: 'graduation-topic-rounds',
      component: () => import('@/views/admin/graduation/TopicRoundListView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '选题轮次', requiresAuth: true, permissionKey: 'graduation.topic.round' }
    },
    {
      path: 'topics',
      name: 'graduation-topics',
      component: () => import('@/views/admin/graduation/TopicManageView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '选题管理', requiresAuth: true, permissionKey: 'graduation.topic.manage' }
    },
    {
      path: 'topic-changes',
      name: 'graduation-topic-changes',
      component: () => import('@/views/admin/graduation/TopicChangeRequestListView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '题目调整（选题变更申请）', requiresAuth: true, permissionKey: 'graduation.topic.change' }
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
    },
    {
      path: 'stats-report',
      name: 'graduation-stats-report',
      component: () => import('@/views/admin/graduation/GraduationStatsView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '毕设统计报表', requiresAuth: true, permissionKey: 'graduation.stats.view' }
    },
    {
      path: 'more',
      name: 'graduation-more',
      component: () => import('@/views/admin/graduation/GraduationMoreView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '互查/专家/申诉', requiresAuth: true, permissionKey: 'graduation.more.manage' }
    },
    {
      path: 'templates',
      name: 'graduation-templates',
      component: () => import('@/views/admin/graduation/GraduationTemplateView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '毕设模板中心', requiresAuth: true, permissionKey: 'graduation.template.manage' }
    },
    {
      path: 'batches',
      name: 'graduation-batches',
      component: () => import('@/views/admin/graduation/GraduationBatchListView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '毕设批次', requiresAuth: true, permissionKey: 'graduation.batch.manage' }
    },
    {
      path: 'mentors',
      name: 'graduation-mentors',
      component: () => import('@/views/admin/graduation/GraduationMentorListView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '导师管理与分配', requiresAuth: true, permissionKey: 'graduation.mentor.manage' }
    },
    {
      path: 'process',
      name: 'graduation-process',
      component: () => import('@/views/admin/graduation/GraduationProcessView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '过程指导（任务书/指导记录/中期检查）', requiresAuth: true, permissionKey: 'graduation.process.manage' }
    },
    {
      path: 'defense-grade',
      name: 'graduation-defense-grade',
      component: () => import('@/views/admin/graduation/GraduationDefenseGradeView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '答辩与成绩（查重/评阅/答辩评分/成绩评定）', requiresAuth: true, permissionKey: 'graduation.defenseGrade.manage' }
    },
    {
      path: 'risk-archive',
      name: 'graduation-risk-archive',
      component: () => import('@/views/admin/graduation/GraduationRiskArchiveView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '问题预警/毕设归档/毕设统计', requiresAuth: true, permissionKey: 'graduation.riskArchive.manage' }
    }
  ]
}

export default graduationRoutes
