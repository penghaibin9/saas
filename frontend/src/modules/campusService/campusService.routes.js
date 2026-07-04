/**
 * 03 在校服务中心 — 模块路由描述（不自动接入全局 router，避免并行任务冲突）。
 * 接入方式：在 src/router/index.js 的 routes 数组中 push 本文件导出的 campusServiceRoutes 即可：
 *   import { campusServiceRoutes } from '@/modules/campusService/campusService.routes'
 *   routes: [ ...existing, campusServiceRoutes ]
 * meta 口径与 workflow/student 模块一致，供统一路由守卫消费。
 */
export const campusServiceRoutes = {
  path: '/admin/campus-service',
  component: () => import('@/views/admin/campusService/AdminCampusServiceLayout.vue'),
  meta: { moduleCode: 'CAMPUS_SERVICE' },
  children: [
    {
      path: '',
      name: 'campus-service-dashboard',
      component: () => import('@/views/admin/campusService/CampusServiceDashboardView.vue'),
      meta: { moduleCode: 'CAMPUS_SERVICE', requiresAuth: true, permissionKey: 'campus.dashboard.view', title: '在校服务中心' }
    },
    {
      path: 'students',
      name: 'campus-service-students',
      component: () => import('@/views/admin/campusService/ServiceStudentListView.vue'),
      meta: { moduleCode: 'CAMPUS_SERVICE', requiresAuth: true, permissionKey: 'campus.record.view', title: '学生服务' }
    },
    {
      path: 'students/:id',
      name: 'campus-service-student-detail',
      component: () => import('@/views/admin/campusService/ServiceStudentDetailView.vue'),
      meta: { moduleCode: 'CAMPUS_SERVICE', requiresAuth: true, permissionKey: 'campus.record.view', title: '学生服务详情' }
    },
    {
      path: 'leave',
      name: 'campus-service-leave',
      component: () => import('@/views/admin/campusService/LeaveApprovalView.vue'),
      meta: { moduleCode: 'CAMPUS_SERVICE', requiresAuth: true, permissionKey: 'campus.leave.view', title: '请假审批' }
    },
    {
      path: 'grants',
      name: 'campus-service-grants',
      component: () => import('@/views/admin/campusService/GrantApplicationView.vue'),
      meta: { moduleCode: 'CAMPUS_SERVICE', requiresAuth: true, permissionKey: 'campus.grant.view', title: '奖助资助' }
    },
    {
      path: 'dormitory',
      name: 'campus-service-dormitory',
      component: () => import('@/views/admin/campusService/DormitoryView.vue'),
      meta: { moduleCode: 'CAMPUS_SERVICE', requiresAuth: true, permissionKey: 'campus.dorm.view', title: '宿舍服务' }
    },
    {
      path: 'discipline',
      name: 'campus-service-discipline',
      component: () => import('@/views/admin/campusService/DisciplineView.vue'),
      meta: { moduleCode: 'CAMPUS_SERVICE', requiresAuth: true, permissionKey: 'campus.discipline.view', title: '违纪处分' }
    },
    {
      path: 'work-orders',
      name: 'campus-service-work-orders',
      component: () => import('@/views/admin/campusService/WorkOrderView.vue'),
      meta: { moduleCode: 'CAMPUS_SERVICE', requiresAuth: true, permissionKey: 'campus.workorder.view', title: '服务工单' }
    }
  ]
}

export default campusServiceRoutes
