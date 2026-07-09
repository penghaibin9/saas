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
          title: 'Student Affairs Dashboard',
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
          title: 'Student Profile',
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
          title: 'Student Profile Detail',
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
          title: 'Class Management',
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
          title: 'Class Detail',
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
          title: 'Dormitory Management',
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
          title: 'Dormitory Management',
          requiresAuth: true,
          permissionKey: 'studentAffairs.dorm.view'
        }
      },
      {
        path: 'leave',
        name: 'student-affairs-leave',
        component: () => import('@/views/admin/student-affairs/StudentAffairsLeaveView.vue'),
        meta: {
          moduleCode: 'STUDENT_AFFAIRS',
          title: 'Leave Management',
          requiresAuth: true,
          permissionKey: 'studentAffairs.leave.view'
        }
      },
      {
        path: 'leave/:panel(approvals|exceptions|rules)',
        name: 'student-affairs-leave-panel',
        component: () => import('@/views/admin/student-affairs/StudentAffairsLeaveView.vue'),
        meta: {
          moduleCode: 'STUDENT_AFFAIRS',
          title: 'Leave Management',
          requiresAuth: true,
          permissionKey: 'studentAffairs.leave.view'
        }
      },
      {
        path: 'risk',
        name: 'student-affairs-risk',
        component: () => import('@/views/admin/student-affairs/StudentAffairsRiskListView.vue'),
        meta: {
          moduleCode: 'STUDENT_AFFAIRS',
          title: 'Risk Warning',
          requiresAuth: true,
          permissionKey: 'studentAffairs.risk.view'
        }
      },
      {
        path: 'risk/rules',
        name: 'student-affairs-risk-rules',
        component: () => import('@/views/admin/student-affairs/StudentAffairsRiskListView.vue'),
        meta: {
          moduleCode: 'STUDENT_AFFAIRS',
          title: 'Risk Rules',
          requiresAuth: true,
          permissionKey: 'studentAffairs.risk.view'
        }
      },
      {
        path: 'risk/:riskId',
        name: 'student-affairs-risk-detail',
        component: () => import('@/views/admin/student-affairs/StudentAffairsRiskDetailView.vue'),
        meta: {
          moduleCode: 'STUDENT_AFFAIRS',
          title: 'Risk Detail',
          requiresAuth: true,
          permissionKey: 'studentAffairs.risk.view'
        }
      }
    ]
  }
]

export default studentAffairsRoutes
