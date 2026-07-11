/**
 * 学工中心（13A）— 模块路由描述文件（仅导出配置，由 src/router/index.js 统一并入）。
 *
 * 本轮范围 = 学工首页（/admin/student-affairs）。父布局 AdminStudentAffairsLayout
 * 采用 navPlan 驱动的侧栏三级树（传 ctx、不传 menus/#menu 插槽），与毕设/实习中心同构。
 * 后续 P3 起的请假/困难认定/风险等业务页在此 children 内逐个追加，不新开一级。
 */
export const studentAffairsRoutes = {
  path: '/admin/student-affairs',
  component: () => import('@/views/admin/studentAffairs/AdminStudentAffairsLayout.vue'),
  meta: { moduleCode: 'STUDENT_AFFAIRS' },
  children: [
    {
      path: '',
      name: 'student-affairs-home',
      component: () => import('@/views/admin/studentAffairs/StudentAffairsHomeView.vue'),
      meta: {
        moduleCode: 'STUDENT_AFFAIRS',
        title: '学工首页',
        requiresAuth: true,
        permissionKey: 'studentAffairs.home.view'
      }
    },
    {
      path: 'leave',
      name: 'student-affairs-leave',
      component: () => import('@/views/admin/studentAffairs/LeaveWorkbenchView.vue'),
      meta: {
        moduleCode: 'STUDENT_AFFAIRS',
        title: '请假审批工作台',
        requiresAuth: true,
        permissionKey: 'studentAffairs.leave.view'
      }
    },
    {
      path: 'risk',
      name: 'student-affairs-risk',
      component: () => import('@/views/admin/studentAffairs/RiskWorkbenchView.vue'),
      meta: {
        moduleCode: 'STUDENT_AFFAIRS',
        title: '风险预警处置工作台',
        requiresAuth: true,
        permissionKey: 'studentAffairs.risk.view'
      }
    },
    {
      path: 'discipline',
      name: 'student-affairs-discipline',
      component: () => import('@/views/admin/studentAffairs/DisciplineWorkbenchView.vue'),
      meta: {
        moduleCode: 'STUDENT_AFFAIRS',
        title: '违纪处分工作台',
        requiresAuth: true,
        permissionKey: 'studentAffairs.discipline.view'
      }
    },
    {
      path: 'aid',
      name: 'student-affairs-aid',
      component: () => import('@/views/admin/studentAffairs/AidWorkbenchView.vue'),
      meta: {
        moduleCode: 'STUDENT_AFFAIRS',
        title: '困难认定工作台',
        requiresAuth: true,
        permissionKey: 'studentAffairs.aid.view'
      }
    },
    {
      path: 'classes',
      name: 'student-affairs-classes',
      component: () => import('@/views/admin/studentAffairs/ClassManageView.vue'),
      meta: {
        moduleCode: 'STUDENT_AFFAIRS',
        title: '班级管理',
        requiresAuth: true,
        permissionKey: 'studentAffairs.classes.view'
      }
    },
    {
      path: 'talks',
      name: 'student-affairs-talks',
      component: () => import('@/views/admin/studentAffairs/TalkWorkbenchView.vue'),
      meta: {
        moduleCode: 'STUDENT_AFFAIRS',
        title: '谈心谈话工作台',
        requiresAuth: true,
        permissionKey: 'studentAffairs.talk.view'
      }
    },
    {
      path: 'profile',
      name: 'student-affairs-profile',
      component: () => import('@/views/admin/studentAffairs/StudentProfileView.vue'),
      meta: {
        moduleCode: 'STUDENT_AFFAIRS',
        title: '学生画像 360',
        requiresAuth: true,
        permissionKey: 'studentAffairs.profile.view'
      }
    },
    {
      path: 'funding',
      name: 'student-affairs-funding',
      component: () => import('@/views/admin/studentAffairs/FundingWorkbenchView.vue'),
      meta: {
        moduleCode: 'STUDENT_AFFAIRS',
        title: '奖助管理工作台',
        requiresAuth: true,
        permissionKey: 'studentAffairs.funding.view'
      }
    },
    {
      path: 'family',
      name: 'student-affairs-family',
      component: () => import('@/views/admin/studentAffairs/FamilyContactView.vue'),
      meta: {
        moduleCode: 'STUDENT_AFFAIRS',
        title: '家校联系',
        requiresAuth: true,
        permissionKey: 'studentAffairs.family.view'
      }
    },
    {
      path: 'dorm',
      name: 'student-affairs-dorm',
      component: () => import('@/views/admin/studentAffairs/DormManageView.vue'),
      meta: {
        moduleCode: 'STUDENT_AFFAIRS',
        title: '宿舍管理',
        requiresAuth: true,
        permissionKey: 'studentAffairs.dorm.view'
      }
    },
    {
      path: 'archive',
      name: 'student-affairs-archive',
      component: () => import('@/views/admin/studentAffairs/ArchiveManageView.vue'),
      meta: {
        moduleCode: 'STUDENT_AFFAIRS',
        title: '学工归档',
        requiresAuth: true,
        permissionKey: 'studentAffairs.archive.view'
      }
    },
    {
      path: 'stats',
      name: 'student-affairs-stats',
      component: () => import('@/views/admin/studentAffairs/StudentAffairsStatsView.vue'),
      meta: {
        moduleCode: 'STUDENT_AFFAIRS',
        title: '学工统计',
        requiresAuth: true,
        permissionKey: 'studentAffairs.stats.view'
      }
    }
  ]
}

export default studentAffairsRoutes
