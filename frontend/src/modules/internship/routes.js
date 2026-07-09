/**
 * 岗位实习中心模块路由（自包含，未接入全局 router）。
 * 接入方式（由负责全局 router 的任务/人执行）：
 *   import internshipRoutes from '@/modules/internship/routes'
 *   routes: [...existing, internshipRoutes]
 */
const internshipRoutes = {
  path: '/admin/internship',
  component: () => import('@/views/admin/internship/AdminInternshipLayout.vue'),
  meta: { moduleCode: 'INTERNSHIP' },
  children: [
    {
      path: '',
      name: 'internship-dashboard',
      component: () => import('@/views/admin/internship/InternshipDashboardView.vue'),
      meta: { moduleCode: 'INTERNSHIP', title: '岗位实习中心', requiresAuth: true, permissionKey: 'internship.dashboard.view' }
    },
    {
      path: 'batches',
      name: 'internship-batches',
      component: () => import('@/views/admin/internship/InternshipBatchListView.vue'),
      meta: { moduleCode: 'INTERNSHIP', title: '实习批次', requiresAuth: true, permissionKey: 'internship.batch.manage' }
    },
    {
      path: 'students',
      name: 'internship-students',
      component: () => import('@/views/admin/internship/InternshipStudentListView.vue'),
      meta: { moduleCode: 'INTERNSHIP', title: '实习学生列表', requiresAuth: true, permissionKey: 'internship.student.view' }
    },
    {
      path: 'students/:id',
      name: 'internship-student-detail',
      component: () => import('@/views/admin/internship/InternshipStudentDetailView.vue'),
      meta: { moduleCode: 'INTERNSHIP', title: '实习学生详情', requiresAuth: true, permissionKey: 'internship.student.view' }
    },
    {
      path: 'attendance',
      name: 'internship-attendance',
      component: () => import('@/views/admin/internship/AttendanceView.vue'),
      meta: { moduleCode: 'INTERNSHIP', title: '打卡与补卡', requiresAuth: true, permissionKey: 'internship.checkin.handle' }
    },
    {
      path: 'exceptions',
      name: 'internship-exceptions',
      component: () => import('@/views/admin/internship/AttendanceExceptionListView.vue'),
      meta: { moduleCode: 'INTERNSHIP', title: '打卡异常列表', requiresAuth: true, permissionKey: 'internship.checkin.handle' }
    },
    {
      path: 'exceptions/:id',
      name: 'internship-exception-detail',
      component: () => import('@/views/admin/internship/AttendanceExceptionDetailView.vue'),
      meta: { moduleCode: 'INTERNSHIP', title: '打卡异常处理', requiresAuth: true, permissionKey: 'internship.checkin.handle' }
    },
    {
      path: 'guidance',
      name: 'internship-guidance',
      component: () => import('@/views/admin/internship/GuidanceVisitView.vue'),
      meta: { moduleCode: 'INTERNSHIP', title: '指导与巡访', requiresAuth: true, permissionKey: 'internship.guidance.view' }
    },
    {
      path: 'reports',
      name: 'internship-reports',
      component: () => import('@/views/admin/internship/WeeklyReportListView.vue'),
      meta: { moduleCode: 'INTERNSHIP', title: '周报批阅列表', requiresAuth: true, permissionKey: 'internship.report.review' }
    },
    {
      path: 'reports/:id',
      name: 'internship-report-detail',
      component: () => import('@/views/admin/internship/WeeklyReportDetailView.vue'),
      meta: { moduleCode: 'INTERNSHIP', title: '周报批阅详情', requiresAuth: true, permissionKey: 'internship.report.review' }
    },
    {
      path: 'risks',
      name: 'internship-risks',
      component: () => import('@/views/admin/internship/InternshipRiskView.vue'),
      meta: { moduleCode: 'INTERNSHIP', title: '实习风险学生', requiresAuth: true, permissionKey: 'internship.risk.view' }
    },
    {
      path: 'enterprises',
      name: 'internship-enterprises',
      component: () => import('@/views/admin/internship/InternshipEnterpriseListView.vue'),
      meta: { moduleCode: 'INTERNSHIP', title: '企业库', requiresAuth: true, permissionKey: 'internship.enterprise.view' }
    },
    {
      path: 'enterprises/:id',
      name: 'internship-enterprise-detail',
      component: () => import('@/views/admin/internship/InternshipEnterpriseDetailView.vue'),
      meta: { moduleCode: 'INTERNSHIP', title: '企业详情', requiresAuth: true, permissionKey: 'internship.enterprise.view' }
    },
    {
      path: 'positions',
      name: 'internship-positions',
      component: () => import('@/views/admin/internship/InternshipPositionListView.vue'),
      meta: { moduleCode: 'INTERNSHIP', title: '岗位库', requiresAuth: true, permissionKey: 'internship.position.view' }
    },
    {
      path: 'positions/:id',
      name: 'internship-position-detail',
      component: () => import('@/views/admin/internship/InternshipPositionDetailView.vue'),
      meta: { moduleCode: 'INTERNSHIP', title: '岗位详情', requiresAuth: true, permissionKey: 'internship.position.view' }
    },
    {
      path: 'agreement-templates',
      name: 'internship-agreement-templates',
      component: () => import('@/views/admin/internship/InternshipAgreementTemplateListView.vue'),
      meta: { moduleCode: 'INTERNSHIP', title: '实习协议模板库', requiresAuth: true, permissionKey: 'internship.agreementTemplate.view' }
    },
    {
      path: 'match',
      name: 'internship-match',
      component: () => import('@/views/admin/internship/InternshipMatchListView.vue'),
      meta: { moduleCode: 'INTERNSHIP', title: '岗位匹配', requiresAuth: true, permissionKey: 'internship.match.view' }
    }
  ]
}

export default internshipRoutes
