/**
 * 就业服务中心 — 模块路由描述文件（仅导出配置，不自行接入全局 router）。
 * A3：permissionKey 与后端 require_permission 精确同源，禁止继续使用旧 mock UI 权限码。
 */
export const employmentRoutes = {
  path: '/admin/employment',
  component: () => import('@/views/admin/employment/AdminEmploymentLayout.vue'),
  meta: { moduleCode: 'EMPLOYMENT' },
  children: [
    {
      path: '',
      name: 'employment-dashboard',
      component: () => import('@/views/admin/employment/EmploymentDashboardView.vue'),
      meta: { moduleCode: 'EMPLOYMENT', title: '就业服务管理看板', requiresAuth: true, permissionKey: 'employment.dashboard.view' }
    },
    {
      path: 'students',
      name: 'employment-students',
      component: () => import('@/views/admin/employment/EmploymentStudentListView.vue'),
      meta: { moduleCode: 'EMPLOYMENT', title: '就业学生列表', requiresAuth: true, permissionKey: 'employment.student.view' }
    },
    {
      path: 'students/:studentId',
      name: 'employment-student-detail',
      component: () => import('@/views/admin/employment/EmploymentStudentDetailView.vue'),
      meta: { moduleCode: 'EMPLOYMENT', title: '学生就业详情', requiresAuth: true, permissionKey: 'employment.student.view' }
    },
    {
      path: 'materials',
      name: 'employment-materials',
      component: () => import('@/views/admin/employment/EmploymentMaterialListView.vue'),
      meta: { moduleCode: 'EMPLOYMENT', title: '就业材料审核', requiresAuth: true, permissionKey: 'employment.material.view' }
    },
    {
      path: 'materials/:materialId',
      name: 'employment-material-detail',
      component: () => import('@/views/admin/employment/EmploymentMaterialDetailView.vue'),
      meta: { moduleCode: 'EMPLOYMENT', title: '材料审核详情', requiresAuth: true, permissionKey: 'employment.material.view' }
    },
    {
      path: 'unemployed',
      name: 'employment-unemployed',
      component: () => import('@/views/admin/employment/UnemployedStudentListView.vue'),
      meta: { moduleCode: 'EMPLOYMENT', title: '未就业学生帮扶', requiresAuth: true, permissionKey: 'employment.unemployed.view' }
    },
    {
      path: 'followups',
      name: 'employment-followups',
      component: () => import('@/views/admin/employment/EmploymentFollowUpView.vue'),
      meta: { moduleCode: 'EMPLOYMENT', title: '就业跟进记录', requiresAuth: true, permissionKey: 'employment.followup.view' }
    }
  ]
}

export default employmentRoutes
