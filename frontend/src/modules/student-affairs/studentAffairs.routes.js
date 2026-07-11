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
      }
    ]
  }
]

export default studentAffairsRoutes
export { studentAffairsRoutes }
