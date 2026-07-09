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
      },
      {
        path: 'classes',
        name: 'student-affairs-classes',
        component: () => import('@/views/admin/student-affairs/StudentAffairsClassListView.vue'),
        meta: {
          moduleCode: 'STUDENT_AFFAIRS',
          title: '班级管理',
          requiresAuth: true,
          permissionKey: 'studentAffairs.classes.view'
        }
      },
      {
        path: 'classes/:classId',
        name: 'student-affairs-class-detail',
        component: () => import('@/views/admin/student-affairs/StudentAffairsClassDetailView.vue'),
        meta: {
          moduleCode: 'STUDENT_AFFAIRS',
          title: '班级详情',
          requiresAuth: true,
          permissionKey: 'studentAffairs.classes.view'
        }
      },
      {
        path: 'dormitory',
        name: 'student-affairs-dormitory',
        component: () => import('@/views/admin/student-affairs/StudentAffairsDormitoryView.vue'),
        meta: {
          moduleCode: 'STUDENT_AFFAIRS',
          title: '宿舍管理',
          requiresAuth: true,
          permissionKey: 'studentAffairs.dorm.view'
        }
      },
      {
        path: 'dormitory/:panel(buildings|rooms|beds|checks|absence)',
        name: 'student-affairs-dormitory-panel',
        component: () => import('@/views/admin/student-affairs/StudentAffairsDormitoryView.vue'),
        meta: {
          moduleCode: 'STUDENT_AFFAIRS',
          title: '宿舍管理',
          requiresAuth: true,
          permissionKey: 'studentAffairs.dorm.view'
        }
      }
    ]
  }
]

export default studentAffairsRoutes
