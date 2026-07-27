/**
 * 旧在校服务中心兼容路由。
 *
 * 学工请假已迁入 /admin/student-affairs/leave*，本文件只保留旧书签重定向；
 * 旧地址不得再加载请假组件、声明 CAMPUS_SERVICE 权限或作为正式菜单入口。
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
      path: 'students',
      name: 'campus-service-students',
      redirect: '/admin/student/list'
    },
    {
      path: 'students/:id',
      name: 'campus-service-student-detail',
      redirect: '/admin/student/list'
    },
    {
      path: 'leave',
      name: 'campus-service-leave',
      redirect: '/admin/student-affairs/leave'
    },
    {
      path: 'leave-extensions',
      name: 'campus-service-leave-extensions',
      redirect: '/admin/student-affairs/leave/followup'
    },
    {
      path: 'leave-ledger',
      name: 'campus-service-leave-ledger',
      redirect: '/admin/student-affairs/leave/ledger'
    },
    {
      path: 'leave-stats',
      name: 'campus-service-leave-stats',
      redirect: '/admin/student-affairs/leave/stats'
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
      path: 'counselor-assignments',
      name: 'campus-service-counselor-assignments',
      redirect: '/admin/student-affairs/counselor-assignments'
    },
    {
      path: 'counselor-assessment',
      name: 'campus-service-counselor-assessment',
      redirect: '/admin/student-affairs/counselor-eval'
    },
    {
      path: 'grants',
      name: 'campus-service-grants',
      redirect: '/admin/student-affairs/funding'
    },
    {
      path: 'dormitory',
      name: 'campus-service-dormitory',
      redirect: '/admin/student-affairs/dorm/checkin'
    },
    {
      path: 'dormitory/records/:recordId',
      name: 'campus-service-dorm-record-detail',
      redirect: '/admin/student-affairs/dorm/checkin'
    },
    {
      path: 'discipline/:recordId',
      name: 'campus-service-discipline-detail',
      redirect: (to) => ({ path: '/admin/student-affairs/discipline', query: { caseId: to.params.recordId } })
    },
    {
      path: 'discipline',
      name: 'campus-service-discipline',
      redirect: '/admin/student-affairs/discipline'
    },
    {
      path: 'work-orders',
      name: 'campus-service-work-orders',
      redirect: '/admin/student-affairs/dashboard'
    }
  ]
}

export default campusServiceRoutes
