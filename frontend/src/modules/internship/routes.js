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
    }
  ]
}

export default internshipRoutes
