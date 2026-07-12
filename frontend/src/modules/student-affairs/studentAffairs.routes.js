/**
 * 学工中心 B 包 · 独立 studentAffairs 模块路由（捞自 student-affairs-b 分支）。
 * 仅保留 master 缺的 4 块：学工看板 / 学生画像 / 宿舍管理 / 风险预警。
 * 班级/请假已由 master 正式模块承接（/admin/campus-service/classes、/leave 系列），此处不重复。
 * 页面真打 /student-affairs/* 端点；与 master 现行后端字段的对齐见历史欠账（B包·第3步收口）。
 */
const studentAffairsRoutes = [
  {
    path: '/admin/student-affairs',
    component: () => import('@/views/admin/student-affairs/AdminStudentAffairsLayout.vue'),
    meta: { moduleCode: 'STUDENT_AFFAIRS' },
    children: [
      { path: '', redirect: '/admin/student-affairs/dashboard' },
      {
        path: 'dashboard',
        name: 'student-affairs-dashboard',
        component: () => import('@/views/admin/student-affairs/StudentAffairsDashboardView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '学工看板', requiresAuth: true, permissionKey: 'studentAffairs.dashboard.view' }
      },
      {
        path: 'profile',
        name: 'student-affairs-profile',
        component: () => import('@/views/admin/student-affairs/StudentAffairsProfileListView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '学生画像', requiresAuth: true, permissionKey: 'studentAffairs.profile.view' }
      },
      {
        path: 'profile/:studentId',
        name: 'student-affairs-profile-detail',
        component: () => import('@/views/admin/student-affairs/StudentAffairsProfileDetailView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '学生画像详情', requiresAuth: true, permissionKey: 'studentAffairs.profile.view' }
      },
      {
        path: 'dormitory',
        name: 'student-affairs-dormitory',
        component: () => import('@/views/admin/student-affairs/StudentAffairsDormitoryView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '宿舍管理', requiresAuth: true, permissionKey: 'studentAffairs.dorm.view' }
      },
      {
        path: 'risk',
        name: 'student-affairs-risk',
        component: () => import('@/views/admin/student-affairs/StudentAffairsRiskListView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '风险预警', requiresAuth: true, permissionKey: 'studentAffairs.risk.view' }
      },
      {
        path: 'risk/:riskId',
        name: 'student-affairs-risk-detail',
        component: () => import('@/views/admin/student-affairs/StudentAffairsRiskDetailView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '风险处置', requiresAuth: true, permissionKey: 'studentAffairs.risk.view' }
      },
      /* 以下 7 个工作台捞自 feat/student-affairs-13a-frontend（Chrome 真机验证版，master 此前缺）；
       * 页面文件在 views/admin/studentAffairs/（驼峰），统一挂到本 /admin/student-affairs/* 一棵路由树，不再另开路径。 */
      {
        path: 'aid',
        name: 'student-affairs-aid',
        component: () => import('@/views/admin/studentAffairs/AidWorkbenchView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '困难认定', requiresAuth: true, permissionKey: 'studentAffairs.aid.view' }
      },
      {
        path: 'funding',
        name: 'student-affairs-funding',
        component: () => import('@/views/admin/studentAffairs/FundingWorkbenchView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '奖助勤贷补', requiresAuth: true, permissionKey: 'studentAffairs.funding.view' }
      },
      {
        path: 'discipline',
        name: 'student-affairs-discipline',
        component: () => import('@/views/admin/studentAffairs/DisciplineWorkbenchView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '违纪处分', requiresAuth: true, permissionKey: 'studentAffairs.discipline.view' }
      },
      {
        path: 'talk',
        name: 'student-affairs-talk',
        component: () => import('@/views/admin/studentAffairs/TalkWorkbenchView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '谈心谈话', requiresAuth: true, permissionKey: 'studentAffairs.talk.view' }
      },
      {
        path: 'family',
        name: 'student-affairs-family',
        component: () => import('@/views/admin/studentAffairs/FamilyContactView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '家校联系', requiresAuth: true, permissionKey: 'studentAffairs.homeSchool.view' }
      },
      {
        path: 'archive',
        name: 'student-affairs-archive',
        component: () => import('@/views/admin/studentAffairs/ArchiveManageView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '学工归档', requiresAuth: true, permissionKey: 'studentAffairs.archive.view' }
      },
      {
        path: 'stats',
        name: 'student-affairs-stats',
        component: () => import('@/views/admin/studentAffairs/StudentAffairsStatsView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '学工统计', requiresAuth: true, permissionKey: 'studentAffairs.stats.view' }
      },
      /* 心理关注 5 页（强敏感·PSY_STUDENT·危机接风险中枢）——对接 /student-affairs/mental/* 后端 */
      {
        path: 'mental',
        name: 'student-affairs-mental',
        component: () => import('@/views/admin/student-affairs/mental/MentalAttentionListView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '心理关注名单', requiresAuth: true, permissionKey: 'studentAffairs.risk.psyDetail.view' }
      },
      {
        path: 'mental/summary',
        name: 'student-affairs-mental-summary',
        component: () => import('@/views/admin/student-affairs/mental/MentalWarningSummaryView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '心理预警摘要', requiresAuth: true, permissionKey: 'studentAffairs.risk.view' }
      },
      {
        path: 'mental/referrals',
        name: 'student-affairs-mental-referrals',
        component: () => import('@/views/admin/student-affairs/mental/MentalReferralFollowView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '谈话转介与回访', requiresAuth: true, permissionKey: 'studentAffairs.risk.psyDetail.view' }
      },
      {
        path: 'mental/crisis',
        name: 'student-affairs-mental-crisis',
        component: () => import('@/views/admin/student-affairs/mental/MentalCrisisView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '心理危机升级', requiresAuth: true, permissionKey: 'studentAffairs.risk.psyDetail.view' }
      },
      {
        path: 'mental/stats',
        name: 'student-affairs-mental-stats',
        component: () => import('@/views/admin/student-affairs/mental/MentalStatsView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '心理统计', requiresAuth: true, permissionKey: 'studentAffairs.stats.view' }
      }
    ]
  }
]

export default studentAffairsRoutes
export { studentAffairsRoutes }
