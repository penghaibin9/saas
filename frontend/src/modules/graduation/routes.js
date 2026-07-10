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
    // ── 毕设学生（子路由须在 :id 之前）──
    {
      path: 'students/create',
      name: 'graduation-student-create',
      component: () => import('@/views/admin/graduation/GraduationStudentFormView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '毕设学生建档', requiresAuth: true, permissionKey: 'graduation.student.manage' }
    },
    {
      path: 'students/_batch/group',
      name: 'graduation-student-batch-group',
      component: () => import('@/views/admin/graduation/GraduationStudentGroupView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '批量设置分组', requiresAuth: true, permissionKey: 'graduation.student.manage' }
    },
    {
      path: 'students/:id/assign-topic',
      name: 'graduation-student-assign-topic',
      component: () => import('@/views/admin/graduation/GraduationStudentAssignTopicView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '分配选题', requiresAuth: true, permissionKey: 'graduation.student.manage' }
    },
    {
      path: 'students/:id/group',
      name: 'graduation-student-group',
      component: () => import('@/views/admin/graduation/GraduationStudentGroupView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '过程分组', requiresAuth: true, permissionKey: 'graduation.student.manage' }
    },
    {
      path: 'students/:id/defense-group',
      name: 'graduation-student-defense-group',
      component: () => import('@/views/admin/graduation/GraduationStudentDefenseView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '分配答辩组', requiresAuth: true, permissionKey: 'graduation.student.manage' }
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
    // ── 题目库（子路由内嵌在列表筛选栏下方）──
    {
      path: 'topic-lib',
      name: 'graduation-topic-lib',
      component: () => import('@/views/admin/graduation/TopicLibListView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '题目库', requiresAuth: true, permissionKey: 'graduation.topic.lib' },
      children: [
        {
          path: 'create',
          name: 'graduation-topic-lib-create',
          component: () => import('@/views/admin/graduation/TopicLibFormView.vue'),
          meta: { moduleCode: 'GRADUATION', title: '申报题目', requiresAuth: true, permissionKey: 'graduation.topic.lib' }
        },
        {
          path: ':id/edit',
          name: 'graduation-topic-lib-edit',
          component: () => import('@/views/admin/graduation/TopicLibFormView.vue'),
          meta: { moduleCode: 'GRADUATION', title: '编辑题目', requiresAuth: true, permissionKey: 'graduation.topic.lib' }
        },
        {
          path: ':id/capacity',
          name: 'graduation-topic-lib-capacity',
          component: () => import('@/views/admin/graduation/TopicLibCapacityView.vue'),
          meta: { moduleCode: 'GRADUATION', title: '调整题目容量', requiresAuth: true, permissionKey: 'graduation.topic.lib' }
        },
        {
          path: ':id/requirements',
          name: 'graduation-topic-lib-requirements',
          component: () => import('@/views/admin/graduation/TopicLibRequirementsView.vue'),
          meta: { moduleCode: 'GRADUATION', title: '维护题目要求', requiresAuth: true, permissionKey: 'graduation.topic.lib' }
        },
        {
          path: ':id/attachments',
          name: 'graduation-topic-lib-attachments',
          component: () => import('@/views/admin/graduation/TopicLibAttachmentsView.vue'),
          meta: { moduleCode: 'GRADUATION', title: '题目附件管理', requiresAuth: true, permissionKey: 'graduation.topic.lib' }
        },
        {
          path: ':id/category',
          name: 'graduation-topic-lib-category',
          component: () => import('@/views/admin/graduation/TopicLibCategoryView.vue'),
          meta: { moduleCode: 'GRADUATION', title: '调整题目分类', requiresAuth: true, permissionKey: 'graduation.topic.lib' }
        },
        {
          path: ':id',
          name: 'graduation-topic-lib-detail',
          component: () => import('@/views/admin/graduation/TopicLibDetailView.vue'),
          meta: { moduleCode: 'GRADUATION', title: '题目详情', requiresAuth: true, permissionKey: 'graduation.topic.lib' }
        }
      ]
    },
    // ── 选题轮次 ──
    {
      path: 'topic-rounds/create',
      name: 'graduation-topic-round-create',
      component: () => import('@/views/admin/graduation/TopicRoundFormView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '新建选题轮次', requiresAuth: true, permissionKey: 'graduation.topic.round' }
    },
    {
      path: 'topic-rounds',
      name: 'graduation-topic-rounds',
      component: () => import('@/views/admin/graduation/TopicRoundListView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '选题轮次', requiresAuth: true, permissionKey: 'graduation.topic.round' }
    },
    // ── 选题管理 ──
    {
      path: 'topics/:id/edit',
      name: 'graduation-topic-edit',
      component: () => import('@/views/admin/graduation/TopicManageFormView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '编辑课题', requiresAuth: true, permissionKey: 'graduation.topic.manage' }
    },
    {
      path: 'topics/:id',
      name: 'graduation-topic-detail',
      component: () => import('@/views/admin/graduation/TopicManageDetailView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '课题详情', requiresAuth: true, permissionKey: 'graduation.topic.manage' }
    },
    {
      path: 'topics',
      name: 'graduation-topics',
      component: () => import('@/views/admin/graduation/TopicManageView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '选题管理', requiresAuth: true, permissionKey: 'graduation.topic.manage' }
    },
    // ── 题目变更 ──
    {
      path: 'topic-changes/:id',
      name: 'graduation-topic-change-detail',
      component: () => import('@/views/admin/graduation/TopicChangeDetailView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '变更申请详情', requiresAuth: true, permissionKey: 'graduation.topic.change' }
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
    // ── 答辩安排 ──
    {
      path: 'defense/groups/create',
      name: 'graduation-defense-group-create',
      component: () => import('@/views/admin/graduation/DefenseGroupFormView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '新增答辩组', requiresAuth: true, permissionKey: 'graduation.defense.manage' }
    },
    {
      path: 'defense/groups/:id/edit',
      name: 'graduation-defense-group-edit',
      component: () => import('@/views/admin/graduation/DefenseGroupFormView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '编辑答辩组', requiresAuth: true, permissionKey: 'graduation.defense.manage' }
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
    // ── 互查/专家 ──
    {
      path: 'more/peer-assign',
      name: 'graduation-more-peer',
      component: () => import('@/views/admin/graduation/GraduationMorePeerView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '分配成果互查', requiresAuth: true, permissionKey: 'graduation.more.manage' }
    },
    {
      path: 'more/expert/create',
      name: 'graduation-more-expert',
      component: () => import('@/views/admin/graduation/GraduationMoreExpertView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '新增答辩专家', requiresAuth: true, permissionKey: 'graduation.more.manage' }
    },
    {
      path: 'more',
      name: 'graduation-more',
      component: () => import('@/views/admin/graduation/GraduationMoreView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '互查/专家/申诉', requiresAuth: true, permissionKey: 'graduation.more.manage' }
    },
    // ── 模板 ──
    {
      path: 'templates/create',
      name: 'graduation-template-create',
      component: () => import('@/views/admin/graduation/GraduationTemplateFormView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '新建模板', requiresAuth: true, permissionKey: 'graduation.template.manage' }
    },
    {
      path: 'templates/:id/edit',
      name: 'graduation-template-edit',
      component: () => import('@/views/admin/graduation/GraduationTemplateFormView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '编辑模板', requiresAuth: true, permissionKey: 'graduation.template.manage' }
    },
    {
      path: 'templates',
      name: 'graduation-templates',
      component: () => import('@/views/admin/graduation/GraduationTemplateView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '毕设模板中心', requiresAuth: true, permissionKey: 'graduation.template.manage' }
    },
    // ── 批次 ──
    {
      path: 'batches/create',
      name: 'graduation-batch-create',
      component: () => import('@/views/admin/graduation/GraduationBatchFormView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '新建毕设批次', requiresAuth: true, permissionKey: 'graduation.batch.manage' }
    },
    {
      path: 'batches/:id/edit',
      name: 'graduation-batch-edit',
      component: () => import('@/views/admin/graduation/GraduationBatchFormView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '编辑批次', requiresAuth: true, permissionKey: 'graduation.batch.manage' }
    },
    {
      path: 'batches/:id',
      name: 'graduation-batch-detail',
      component: () => import('@/views/admin/graduation/GraduationBatchDetailView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '批次详情', requiresAuth: true, permissionKey: 'graduation.batch.manage' }
    },
    {
      path: 'batches',
      name: 'graduation-batches',
      component: () => import('@/views/admin/graduation/GraduationBatchListView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '毕设批次', requiresAuth: true, permissionKey: 'graduation.batch.manage' }
    },
    // ── 导师 ──
    {
      path: 'mentors/create',
      name: 'graduation-mentor-create',
      component: () => import('@/views/admin/graduation/GraduationMentorFormView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '申报导师', requiresAuth: true, permissionKey: 'graduation.mentor.manage' }
    },
    {
      path: 'mentors/conflicts',
      name: 'graduation-mentor-conflicts',
      component: () => import('@/views/admin/graduation/GraduationMentorConflictsView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '分配冲突检测', requiresAuth: true, permissionKey: 'graduation.mentor.manage' }
    },
    {
      path: 'mentors/assign/:studentId',
      name: 'graduation-mentor-assign',
      component: () => import('@/views/admin/graduation/GraduationMentorAssignView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '分配导师', requiresAuth: true, permissionKey: 'graduation.mentor.manage' }
    },
    {
      path: 'mentors/:id/edit',
      name: 'graduation-mentor-edit',
      component: () => import('@/views/admin/graduation/GraduationMentorFormView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '编辑导师', requiresAuth: true, permissionKey: 'graduation.mentor.manage' }
    },
    {
      path: 'mentors/:id/eval',
      name: 'graduation-mentor-eval',
      component: () => import('@/views/admin/graduation/GraduationMentorEvalView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '导师评价', requiresAuth: true, permissionKey: 'graduation.mentor.manage' }
    },
    {
      path: 'mentors/:id',
      name: 'graduation-mentor-detail',
      component: () => import('@/views/admin/graduation/GraduationMentorDetailView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '导师详情', requiresAuth: true, permissionKey: 'graduation.mentor.manage' }
    },
    {
      path: 'mentors',
      name: 'graduation-mentors',
      component: () => import('@/views/admin/graduation/GraduationMentorListView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '导师管理与分配', requiresAuth: true, permissionKey: 'graduation.mentor.manage' }
    },
    // ── 过程指导 ──
    {
      path: 'process/:studentId/:action',
      name: 'graduation-process-action',
      component: () => import('@/views/admin/graduation/GraduationProcessActionView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '过程指导操作', requiresAuth: true, permissionKey: 'graduation.process.manage' }
    },
    {
      path: 'process',
      name: 'graduation-process',
      component: () => import('@/views/admin/graduation/GraduationProcessView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '过程指导（任务书/指导记录/中期检查）', requiresAuth: true, permissionKey: 'graduation.process.manage' }
    },
    // ── 答辩与成绩 ──
    {
      path: 'defense-grade/form',
      name: 'graduation-defense-grade-form',
      component: () => import('@/views/admin/graduation/GraduationDefenseGradeFormView.vue'),
      meta: { moduleCode: 'GRADUATION', title: '答辩成绩操作', requiresAuth: true, permissionKey: 'graduation.defenseGrade.manage' }
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
