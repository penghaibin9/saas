import '@/modules/studentAffairs/api/fundingExtensionIntegrity.api'

const StudentAffairsWorkbench = () => import('@/modules/studentAffairs/views/StudentAffairsWorkbench.vue')

const studentAffairsRoutes = [
  {
    path: '/admin/student-affairs',
    component: StudentAffairsWorkbench,
    meta: { moduleCode: 'STUDENT_AFFAIRS', title: '学工中心', requiresAuth: true, permissionKey: 'studentAffairs.dashboard.view' },
    children: [
      {
        path: '',
        redirect: '/admin/student-affairs/dashboard'
      },
      {
        path: 'dashboard',
        name: 'student-affairs-dashboard',
        component: () => import('@/modules/studentAffairs/views/StudentAffairsDashboardView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '学工工作台', requiresAuth: true, permissionKey: 'studentAffairs.dashboard.view' }
      },
      {
        path: 'student-list',
        name: 'student-affairs-student-list',
        component: () => import('@/modules/studentAffairs/views/StudentAffairsProfileListView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '学生画像台账', requiresAuth: true, permissionKey: 'studentAffairs.student.view' }
      },
      {
        path: 'students/:id/profile',
        name: 'student-affairs-student-profile',
        component: () => import('@/modules/studentAffairs/views/StudentAffairsProfileView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '学生学工画像', requiresAuth: true, permissionKey: 'studentAffairs.student.view' }
      },
      {
        path: 'class-list',
        name: 'student-affairs-class-list',
        component: () => import('@/modules/studentAffairs/views/ClassListView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '班级台账', requiresAuth: true, permissionKey: 'studentAffairs.class.view' }
      },
      {
        path: 'classes/:id/profile',
        name: 'student-affairs-class-profile',
        component: () => import('@/modules/studentAffairs/views/ClassProfileView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '班级画像', requiresAuth: true, permissionKey: 'studentAffairs.class.view' }
      },
      {
        path: 'counselor-workbench',
        name: 'student-affairs-counselor-workbench',
        component: () => import('@/modules/studentAffairs/views/CounselorWorkbenchView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '辅导员工作台', requiresAuth: true, permissionKey: 'studentAffairs.dashboard.view' }
      },
      {
        path: 'counselor-assignments',
        name: 'student-affairs-counselor-assignments',
        component: () => import('@/modules/studentAffairs/views/CounselorAssignmentView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '辅导员责任关系', requiresAuth: true, permissionKey: 'studentAffairs.class.view' }
      },
      {
        path: 'counselor-eval',
        name: 'student-affairs-counselor-eval',
        component: () => import('@/modules/studentAffairs/views/CounselorEvalView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '辅导员考评', requiresAuth: true, permissionKey: 'studentAffairs.counselorEval.view' }
      },
      {
        path: 'leave',
        name: 'student-affairs-leave',
        component: () => import('@/modules/studentAffairs/views/leave/LeaveWorkbenchView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '请销假管理', requiresAuth: true, permissionKey: 'studentAffairs.leave.view' }
      },
      {
        path: 'leave/ledger',
        name: 'student-affairs-leave-ledger',
        component: () => import('@/modules/studentAffairs/views/leave/LeaveLedgerView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '请销假台账', requiresAuth: true, permissionKey: 'studentAffairs.leave.view' }
      },
      {
        path: 'aid',
        name: 'student-affairs-aid',
        component: () => import('@/modules/studentAffairs/views/aid/AidWorkbenchView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '困难认定', requiresAuth: true, permissionKey: 'studentAffairs.aid.view' }
      },
      {
        path: 'aid/objections',
        name: 'student-affairs-aid-objections',
        component: () => import('@/modules/studentAffairs/views/aid/AidObjectionView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '困难认定异议', requiresAuth: true, permissionKey: 'studentAffairs.aid.objection.review' }
      },
      {
        path: 'funding',
        name: 'student-affairs-funding',
        component: () => import('@/modules/studentAffairs/views/funding/FundingWorkbenchView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '奖助管理', requiresAuth: true, permissionKey: 'studentAffairs.funding.view' }
      },
      {
        path: 'funding/appeals',
        name: 'student-affairs-funding-appeals',
        component: () => import('@/modules/studentAffairs/views/funding/FundingAppealView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '奖助申诉', requiresAuth: true, permissionKey: 'studentAffairs.funding.appeal.review' }
      },
      {
        path: 'funding/disbursements',
        name: 'student-affairs-funding-disbursements',
        component: () => import('@/modules/studentAffairs/views/funding/FundingDisbursementView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '资助发放台账', requiresAuth: true, permissionKey: 'studentAffairs.funding.disburse.view' }
      },
      {
        path: 'funding/work-study',
        name: 'student-affairs-work-study',
        component: () => import('@/modules/studentAffairs/views/funding/WorkStudyView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '勤工助学', requiresAuth: true, permissionKey: 'studentAffairs.funding.workstudy.view' }
      },
      {
        path: 'funding/loans',
        name: 'student-affairs-loans',
        component: () => import('@/modules/studentAffairs/views/funding/StudentLoanView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '助学贷款', requiresAuth: true, permissionKey: 'studentAffairs.funding.loan.view' }
      },
      {
        path: 'funding/fee-reduction',
        name: 'student-affairs-fee-reduction',
        component: () => import('@/modules/studentAffairs/views/funding/FeeReductionView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '学费减免与临时补助', requiresAuth: true, permissionKey: 'studentAffairs.funding.reduction.view' }
      },
      {
        path: 'discipline',
        name: 'student-affairs-discipline',
        component: () => import('@/modules/studentAffairs/views/discipline/DisciplineWorkbenchView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '违纪处分', requiresAuth: true, permissionKey: 'studentAffairs.discipline.view' }
      },
      {
        path: 'discipline/appeals',
        name: 'student-affairs-discipline-appeals',
        component: () => import('@/modules/studentAffairs/views/discipline/DisciplineAppealView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '处分送达与申诉', requiresAuth: true, permissionKey: 'studentAffairs.discipline.appeal.review' }
      },
      {
        path: 'risk',
        name: 'student-affairs-risk',
        component: () => import('@/modules/studentAffairs/views/risk/RiskWorkbenchView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '风险预警', requiresAuth: true, permissionKey: 'studentAffairs.risk.view' }
      },
      {
        path: 'risk/:id',
        name: 'student-affairs-risk-detail',
        component: () => import('@/modules/studentAffairs/views/risk/RiskDetailView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '风险详情', requiresAuth: true, permissionKey: 'studentAffairs.risk.view' }
      },
      {
        path: 'talks',
        name: 'student-affairs-talks',
        component: () => import('@/modules/studentAffairs/views/talk/TalkWorkbenchView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '谈心谈话', requiresAuth: true, permissionKey: 'studentAffairs.talk.view' }
      },
      {
        path: 'activities',
        name: 'student-affairs-activities',
        component: () => import('@/modules/studentAffairs/views/activity/ActivityWorkbenchView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '学生活动', requiresAuth: true, permissionKey: 'studentAffairs.activity.view' }
      },
      {
        path: 'activities/second-class',
        name: 'student-affairs-second-class',
        component: () => import('@/modules/studentAffairs/views/activity/SecondClassView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '第二课堂', requiresAuth: true, permissionKey: 'studentAffairs.activity.view' }
      },
      {
        path: 'activities/appeals',
        name: 'student-affairs-credit-appeals',
        component: () => import('@/modules/studentAffairs/views/activity/CreditAppealView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '第二课堂申诉', requiresAuth: true, permissionKey: 'studentAffairs.activity.confirm' }
      },
      {
        path: 'activities/volunteer',
        name: 'student-affairs-volunteer',
        component: () => import('@/modules/studentAffairs/views/activity/VolunteerRecordView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '志愿服务时长', requiresAuth: true, permissionKey: 'studentAffairs.activity.view' }
      },
      {
        path: 'activities/clubs',
        name: 'student-affairs-clubs',
        component: () => import('@/modules/studentAffairs/views/club/ClubWorkbenchView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '社团管理', requiresAuth: true, permissionKey: 'studentAffairs.club.view' }
      },
      {
        path: 'activities/organizations',
        name: 'student-affairs-organizations',
        component: () => import('@/modules/studentAffairs/views/org/StudentOrgView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '学生干部与组织', requiresAuth: true, permissionKey: 'studentAffairs.org.view' }
      },
      {
        path: 'activities/party-league',
        name: 'student-affairs-party-league',
        component: () => import('@/modules/studentAffairs/views/league/PartyLeagueView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '党团建设', requiresAuth: true, permissionKey: 'studentAffairs.league.view' }
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
      {
        path: 'stats/cockpit',
        name: 'student-affairs-cockpit',
        component: () => import('@/modules/studentAffairs/views/StudentAffairsCockpitView.vue'),
        meta: { moduleCode: 'STUDENT_AFFAIRS', title: '统计驾驶舱', requiresAuth: true, permissionKey: 'studentAffairs.stats.view' }
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
