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
      path: '/admin/student-affairs/leave',
      name: 'student-affairs-leave',
      component: () => import('@/modules/studentAffairs/views/leave/LeaveApprovalWorkbenchView.vue'),
      meta: { moduleCode: 'STUDENT_AFFAIRS', requiresAuth: true, permissionKey: 'studentAffairs.leave.view', title: '请假审批' }
    },
    {
      path: '/admin/student-affairs/leave/followup',
      name: 'student-affairs-leave-followup',
      component: () => import('@/modules/studentAffairs/views/leave/LeaveExtensionCancelView.vue'),
      meta: { moduleCode: 'STUDENT_AFFAIRS', requiresAuth: true, permissionKey: 'studentAffairs.leave.view', title: '销假与续假' }
    },
    {
      path: '/admin/student-affairs/leave/ledger',
      name: 'student-affairs-leave-ledger',
      component: () => import('@/modules/studentAffairs/views/leave/LeaveLedgerView.vue'),
      meta: { moduleCode: 'STUDENT_AFFAIRS', requiresAuth: true, permissionKey: 'studentAffairs.leave.view', title: '请假台账' }
    },
    {
      path: '/admin/student-affairs/leave/stats',
      name: 'student-affairs-leave-stats',
      component: () => import('@/modules/studentAffairs/views/leave/LeaveStatsView.vue'),
      meta: { moduleCode: 'STUDENT_AFFAIRS', requiresAuth: true, permissionKey: 'studentAffairs.leave.view', title: '请假统计' }
    },
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
