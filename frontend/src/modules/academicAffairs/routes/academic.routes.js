/**
 * 04 学业过程中心 — 模块路由描述（不自动接入全局 router，避免并行任务冲突）。
 * 接入方式：在 src/router/index.js 的 routes 数组中 push 本文件导出的 academicRoutes 即可：
 *   import { academicRoutes } from '@/modules/academicAffairs/routes/academic.routes'
 *   routes: [ ...existing, academicRoutes ]
 * meta 口径与 workflow/student 模块一致，供统一路由守卫消费。
 */
export const academicRoutes = {
  path: '/admin/academic',
  component: () => import('@/modules/academicAffairs/views/AdminAcademicLayout.vue'),
  meta: { moduleCode: 'ACADEMIC' },
  children: [
    {
      path: '',
      name: 'academic-dashboard',
      component: () => import('@/modules/academicAffairs/views/AcademicDashboardView.vue'),
      meta: { moduleCode: 'ACADEMIC', requiresAuth: true, permissionKey: 'academic.dashboard.view', title: '学业过程中心' }
    },
    {
      path: 'students',
      name: 'academic-students',
      component: () => import('@/modules/academicAffairs/views/AcademicStudentListView.vue'),
      meta: { moduleCode: 'ACADEMIC', requiresAuth: true, permissionKey: 'academic.record.view', title: '学业学生' }
    },
    {
      path: 'students/:id',
      name: 'academic-student-detail',
      component: () => import('@/modules/academicAffairs/views/AcademicStudentDetailView.vue'),
      meta: { moduleCode: 'ACADEMIC', requiresAuth: true, permissionKey: 'academic.record.view', title: '学生学业详情' }
    },
    {
      path: 'grades',
      name: 'academic-grades',
      component: () => import('@/modules/academicAffairs/views/AcademicGradeListView.vue'),
      meta: { moduleCode: 'ACADEMIC', requiresAuth: true, permissionKey: 'academic.grade.view', title: '课程成绩' }
    },
    {
      path: 'credits',
      name: 'academic-credits',
      component: () => import('@/modules/academicAffairs/views/AcademicCreditListView.vue'),
      meta: { moduleCode: 'ACADEMIC', requiresAuth: true, permissionKey: 'academic.credit.view', title: '学分修读' }
    },
    {
      path: 'makeup-retake',
      name: 'academic-makeup-retake',
      component: () => import('@/modules/academicAffairs/views/AcademicMakeupRetakeView.vue'),
      meta: { moduleCode: 'ACADEMIC', requiresAuth: true, permissionKey: 'academic.makeup.view', title: '补考重修' }
    },
    {
      path: 'warnings',
      name: 'academic-warnings',
      component: () => import('@/modules/academicAffairs/views/AcademicWarningListView.vue'),
      meta: { moduleCode: 'ACADEMIC', requiresAuth: true, permissionKey: 'academic.warning.view', title: '学业预警' }
    },
    {
      path: 'warnings/:id',
      name: 'academic-warning-detail',
      component: () => import('@/modules/academicAffairs/views/AcademicWarningDetailView.vue'),
      meta: { moduleCode: 'ACADEMIC', requiresAuth: true, permissionKey: 'academic.warning.view', title: '预警跟进详情' }
    }
  ]
}

export default academicRoutes
