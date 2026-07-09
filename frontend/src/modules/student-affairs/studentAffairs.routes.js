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
        meta: {
          moduleCode: 'STUDENT_AFFAIRS',
          title: '学工看板',
          requiresAuth: true,
          permissionKey: 'studentAffairs.dashboard.view'
        }
      },
      {
        path: 'profile',
        name: 'student-affairs-profile',
        component: () => import('@/views/admin/student-affairs/StudentAffairsProfileListView.vue'),
        meta: {
          moduleCode: 'STUDENT_AFFAIRS',
          title: '学生画像',
          requiresAuth: true,
          permissionKey: 'studentAffairs.profile.view'
        }
      },
      {
        path: 'profile/:studentId',
        name: 'student-affairs-profile-detail',
        component: () => import('@/views/admin/student-affairs/StudentAffairsProfileDetailView.vue'),
        meta: {
          moduleCode: 'STUDENT_AFFAIRS',
          title: '学生画像详情',
          requiresAuth: true,
          permissionKey: 'studentAffairs.profile.view'
        }
      }
    ]
  }
]

export default studentAffairsRoutes

