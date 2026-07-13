/**
 * 学工中心 B 包 · 独立 studentAffairs 模块路由（捞自 student-affairs-b 分支）。
 * 仅保留 master 缺的 4 块：学工看板 / 学生画像 / 宿舍管理 / 风险预警。
 * 班级/请假已由 master 正式模块承接（/admin/campus-service/classes、/leave 系列），此处不重复。
 * 页面真打 /student-affairs/* 端点；与 master 现行后端字段的对齐见历史欠账（B包·第3步收口）。
 */
const studentAffairsRoutes = [
  {
    path: '/admin/student-affairs',
    component: () => import('@/modules/studentAffairs/views/AdminStudentAffairsLayout.vue'),
    meta: { moduleCode: 'STUDENT_AFFAIRS' },
    children: [
      { path: '', redirect: '/admin/student-affairs/dashboard' },
      {
        path: 'dashboard',
        name: 'student-affairs-dashboard',
        component: () => import('@/modules/studentAffairs/views/StudentAffairsDashboardView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '学工看板', requiresAuth: true, permissionKey: 'studentAffairs.dashboard.view' }
      },
      {
        path: 'profile',
        name: 'student-affairs-profile',
        component: () => import('@/modules/studentAffairs/views/StudentAffairsProfileListView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '学生画像', requiresAuth: true, permissionKey: 'studentAffairs.profile.view' }
      },
      {
        path: 'profile/:studentId',
        name: 'student-affairs-profile-detail',
        component: () => import('@/modules/studentAffairs/views/StudentAffairsProfileDetailView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '学生画像详情', requiresAuth: true, permissionKey: 'studentAffairs.profile.view' }
      },
      {
        path: 'dormitory',
        name: 'student-affairs-dormitory',
        component: () => import('@/modules/studentAffairs/views/StudentAffairsDormitoryView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '宿舍管理', requiresAuth: true, permissionKey: 'studentAffairs.dorm.view' }
      },
      {
        path: 'risk',
        name: 'student-affairs-risk',
        component: () => import('@/modules/studentAffairs/views/StudentAffairsRiskListView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '风险预警', requiresAuth: true, permissionKey: 'studentAffairs.risk.view' }
      },
      {
        path: 'risk/:riskId',
        name: 'student-affairs-risk-detail',
        component: () => import('@/modules/studentAffairs/views/StudentAffairsRiskDetailView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '风险处置', requiresAuth: true, permissionKey: 'studentAffairs.risk.view' }
      },
      /* 以下 7 个工作台捞自 feat/student-affairs-13a-frontend（Chrome 真机验证版，master 此前缺）；
       * 页面文件在 views/admin/studentAffairs/（驼峰），统一挂到本 /admin/student-affairs/* 一棵路由树，不再另开路径。 */
      {
        path: 'aid',
        name: 'student-affairs-aid',
        component: () => import('@/modules/studentAffairs/views/AidWorkbenchView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '困难认定', requiresAuth: true, permissionKey: 'studentAffairs.aid.view' }
      },
      {
        path: 'aid/batches',
        name: 'student-affairs-aid-batches',
        component: () => import('@/modules/studentAffairs/views/aid/AidBatchView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '认定批次', requiresAuth: true, permissionKey: 'studentAffairs.aid.view' }
      },
      {
        path: 'aid/difficult-students',
        name: 'student-affairs-aid-difficult',
        component: () => import('@/modules/studentAffairs/views/aid/DifficultStudentsView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '困难学生库', requiresAuth: true, permissionKey: 'studentAffairs.aid.view' }
      },
      {
        path: 'aid/publicity',
        name: 'student-affairs-aid-publicity',
        component: () => import('@/modules/studentAffairs/views/aid/AidPublicityView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '认定公示待办', requiresAuth: true, permissionKey: 'studentAffairs.aid.view' }
      },
      {
        path: 'aid/ledger',
        name: 'student-affairs-aid-ledger',
        component: () => import('@/modules/studentAffairs/views/aid/AidLedgerView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '认定台账', requiresAuth: true, permissionKey: 'studentAffairs.aid.view' }
      },
      {
        path: 'aid/stats',
        name: 'student-affairs-aid-stats',
        component: () => import('@/modules/studentAffairs/views/aid/AidStatsView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '认定统计', requiresAuth: true, permissionKey: 'studentAffairs.stats.view' }
      },
      {
        path: 'funding',
        name: 'student-affairs-funding',
        component: () => import('@/modules/studentAffairs/views/FundingWorkbenchView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '奖助勤贷补', requiresAuth: true, permissionKey: 'studentAffairs.funding.view' }
      },
      {
        path: 'funding/projects',
        name: 'student-affairs-funding-projects',
        component: () => import('@/modules/studentAffairs/views/funding/FundingProjectView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '资助项目', requiresAuth: true, permissionKey: 'studentAffairs.funding.view' }
      },
      {
        path: 'funding/batches',
        name: 'student-affairs-funding-batches',
        component: () => import('@/modules/studentAffairs/views/funding/FundingBatchView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '资助批次', requiresAuth: true, permissionKey: 'studentAffairs.funding.view' }
      },
      {
        path: 'funding/publicity',
        name: 'student-affairs-funding-publicity',
        component: () => import('@/modules/studentAffairs/views/funding/FundingPublicityView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '资助公示待办', requiresAuth: true, permissionKey: 'studentAffairs.funding.view' }
      },
      {
        path: 'funding/ledger',
        name: 'student-affairs-funding-ledger',
        component: () => import('@/modules/studentAffairs/views/funding/FundingLedgerView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '资助台账', requiresAuth: true, permissionKey: 'studentAffairs.funding.view' }
      },
      {
        path: 'funding/stats',
        name: 'student-affairs-funding-stats',
        component: () => import('@/modules/studentAffairs/views/funding/FundingStatsView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '资助统计', requiresAuth: true, permissionKey: 'studentAffairs.stats.view' }
      },
      {
        path: 'discipline/stats',
        name: 'student-affairs-discipline-stats',
        component: () => import('@/modules/studentAffairs/views/discipline/DisciplineStatsView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '处分统计', requiresAuth: true, permissionKey: 'studentAffairs.stats.view' }
      },
      {
        path: 'discipline/ledger',
        name: 'student-affairs-discipline-ledger',
        component: () => import('@/modules/studentAffairs/views/discipline/DisciplineLedgerView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '违纪台账', requiresAuth: true, permissionKey: 'studentAffairs.discipline.view' }
      },
      {
        path: 'discipline',
        name: 'student-affairs-discipline',
        component: () => import('@/modules/studentAffairs/views/DisciplineWorkbenchView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '违纪处分', requiresAuth: true, permissionKey: 'studentAffairs.discipline.view' }
      },
      {
        path: 'talk',
        name: 'student-affairs-talk',
        component: () => import('@/modules/studentAffairs/views/TalkWorkbenchView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '谈心谈话', requiresAuth: true, permissionKey: 'studentAffairs.talk.view' }
      },
      {
        path: 'talk/stats',
        name: 'student-affairs-talk-stats',
        component: () => import('@/modules/studentAffairs/views/talk/TalkStatsView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '谈话统计', requiresAuth: true, permissionKey: 'studentAffairs.stats.view' }
      },
      {
        path: 'talk/ledger',
        name: 'student-affairs-talk-ledger',
        component: () => import('@/modules/studentAffairs/views/talk/TalkLedgerView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '谈话台账', requiresAuth: true, permissionKey: 'studentAffairs.talk.view' }
      },
      {
        path: 'activity',
        name: 'student-affairs-activity',
        component: () => import('@/modules/studentAffairs/views/activity/ActivityWorkbenchView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '学生活动', requiresAuth: true, permissionKey: 'studentAffairs.activity.view' }
      },
      {
        path: 'activity/second-class',
        name: 'student-affairs-second-class',
        component: () => import('@/modules/studentAffairs/views/activity/SecondClassLedgerView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '第二课堂积分', requiresAuth: true, permissionKey: 'studentAffairs.stats.view' }
      },
      {
        path: 'family',
        name: 'student-affairs-family',
        component: () => import('@/modules/studentAffairs/views/FamilyContactView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '家校联系', requiresAuth: true, permissionKey: 'studentAffairs.homeSchool.view' }
      },
      {
        path: 'archive',
        name: 'student-affairs-archive',
        component: () => import('@/modules/studentAffairs/views/ArchiveManageView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '学工归档', requiresAuth: true, permissionKey: 'studentAffairs.archive.view' }
      },
      {
        path: 'stats',
        name: 'student-affairs-stats',
        component: () => import('@/modules/studentAffairs/views/StudentAffairsStatsView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '学工统计', requiresAuth: true, permissionKey: 'studentAffairs.stats.view' }
      },
      /* 心理关注 5 页（强敏感·PSY_STUDENT·危机接风险中枢）——对接 /student-affairs/mental/* 后端 */
      {
        path: 'mental',
        name: 'student-affairs-mental',
        component: () => import('@/modules/studentAffairs/views/mental/MentalAttentionListView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '心理关注名单', requiresAuth: true, permissionKey: 'studentAffairs.risk.psyDetail.view' }
      },
      {
        path: 'mental/summary',
        name: 'student-affairs-mental-summary',
        component: () => import('@/modules/studentAffairs/views/mental/MentalWarningSummaryView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '心理预警摘要', requiresAuth: true, permissionKey: 'studentAffairs.risk.view' }
      },
      {
        path: 'mental/referrals',
        name: 'student-affairs-mental-referrals',
        component: () => import('@/modules/studentAffairs/views/mental/MentalReferralFollowView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '谈话转介与回访', requiresAuth: true, permissionKey: 'studentAffairs.risk.psyDetail.view' }
      },
      {
        path: 'mental/crisis',
        name: 'student-affairs-mental-crisis',
        component: () => import('@/modules/studentAffairs/views/mental/MentalCrisisView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '心理危机升级', requiresAuth: true, permissionKey: 'studentAffairs.risk.psyDetail.view' }
      },
      {
        path: 'mental/stats',
        name: 'student-affairs-mental-stats',
        component: () => import('@/modules/studentAffairs/views/mental/MentalStatsView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '心理统计', requiresAuth: true, permissionKey: 'studentAffairs.stats.view' }
      },
      /* 宿舍与公寓 6 页（房源/入住/调宿退宿/检查/异常/统计）——对接 /student-affairs/dorm/* 后端，宿管 DORM_BUILDING 范围 */
      {
        path: 'dorm/resource',
        name: 'student-affairs-dorm-resource',
        component: () => import('@/modules/studentAffairs/views/dorm/DormResourceView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '房源管理', requiresAuth: true, permissionKey: 'studentAffairs.dorm.view' }
      },
      {
        path: 'dorm/checkin',
        name: 'student-affairs-dorm-checkin',
        component: () => import('@/modules/studentAffairs/views/dorm/DormCheckinView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '入住管理', requiresAuth: true, permissionKey: 'studentAffairs.dorm.view' }
      },
      {
        path: 'dorm/transfer',
        name: 'student-affairs-dorm-transfer',
        component: () => import('@/modules/studentAffairs/views/dorm/DormTransferView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '调宿与退宿', requiresAuth: true, permissionKey: 'studentAffairs.dorm.view' }
      },
      {
        path: 'dorm/check',
        name: 'student-affairs-dorm-check',
        component: () => import('@/modules/studentAffairs/views/dorm/DormCheckView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '宿舍检查', requiresAuth: true, permissionKey: 'studentAffairs.dorm.view' }
      },
      {
        path: 'dorm/exception',
        name: 'student-affairs-dorm-exception',
        component: () => import('@/modules/studentAffairs/views/dorm/DormExceptionView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '宿舍异常', requiresAuth: true, permissionKey: 'studentAffairs.dorm.view' }
      },
      {
        path: 'dorm/stats',
        name: 'student-affairs-dorm-stats',
        component: () => import('@/modules/studentAffairs/views/dorm/DormStatsView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '宿舍统计', requiresAuth: true, permissionKey: 'studentAffairs.dorm.view' }
      }
    ]
  }
]

export default studentAffairsRoutes
export { studentAffairsRoutes }
