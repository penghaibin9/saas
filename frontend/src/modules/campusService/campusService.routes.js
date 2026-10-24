/**
 * 旧在校服务中心兼容路由。
 *
 * 学工请假正式入口使用 /admin/student-affairs/leave*；旧 campus-service 地址只做重定向。
 * 四条绝对路径仍放在本模块定义中，是为了在不改全局路由装配的前提下完成切换；
 * 它们的模块身份、权限和布局均属于 STUDENT_AFFAIRS，不再属于 CAMPUS_SERVICE。
 */
export const campusServiceRoutes = {
  path: '/admin/campus-service',
  component: () => import('@/modules/studentAffairs/views/AdminStudentAffairsLayout.vue'),
  meta: { moduleCode: 'CAMPUS_SERVICE' },
  children: [
    {
      path: '',
      name: 'campus-service-dashboard',
      redirect: '/admin/student-affairs/dashboard'
    },
    {
      path: 'classes',
      name: 'campus-service-classes',
      component: () => import('@/modules/studentAffairs/views/class/ClassListView.vue'),
      meta: { moduleCode: 'CAMPUS_SERVICE', requiresAuth: true, permissionKey: 'campus.record.view', title: '班级管理' }
    },
    {
      path: 'classes/:classId',
      name: 'campus-service-class-profile',
      component: () => import('@/modules/studentAffairs/views/class/ClassProfileView.vue'),
      meta: { moduleCode: 'CAMPUS_SERVICE', requiresAuth: true, permissionKey: 'campus.record.view', title: '班级画像' }
    },
    {
      path: 'work-orders',
      name: 'campus-service-work-orders',
      component: () => import('./views/WorkOrderView.vue'),
      meta: { moduleCode: 'CAMPUS_SERVICE', requiresAuth: true, permissionKey: 'campusService.workOrder.view', title: '学生服务工单' }
    }
  ]
}

export default campusServiceRoutes
