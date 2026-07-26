/**
 * 03 在校服务中心 — 模块路由描述（不自动接入全局 router，避免并行任务冲突）。
 * 接入方式：在 src/router/index.js 的 routes 数组中 push 本文件导出的 campusServiceRoutes 即可：
 *   import { campusServiceRoutes } from '@/modules/campusService/campusService.routes'
 *   routes: [ ...existing, campusServiceRoutes ]
 * meta 口径与 workflow/student 模块一致，供统一路由守卫消费。
 */
export const campusServiceRoutes = {
  path: '/admin/campus-service',
  // 老「在校服务」父布局的身份上下文来自本模块的 mock（角色名/数据范围都是假的），
  // 旧页面退役后只剩请假四页与班级两页仍住在这个 path 下，它们本就是学工中心的页面，
  // 因此改用学工中心真实布局：品牌/角色/数据范围/权限模式走 /rbac/current-context。
  component: () => import('@/modules/studentAffairs/views/AdminStudentAffairsLayout.vue'),
  meta: { moduleCode: 'CAMPUS_SERVICE' },
  children: [
    {
      // 老系统「在校服务中心」已整体退役，业务由学工中心接管。保留 path 只做 redirect，
      // 保证老书签/外链刷新不 404（CLAUDE.md §6.4）。
      path: '',
      name: 'campus-service-dashboard',
      redirect: '/admin/student-affairs/dashboard'
    },
    {
      // 旧「学生服务台账」是影子学生台账，已由学生主档列表取代
      path: 'students',
      name: 'campus-service-students',
      redirect: '/admin/student/list'
    },
    {
      // 只回列表、不带 id 跳详情：旧 id 是台账主键，不是学籍档案 id，
      // 直接当 studentId 用会打开另一个学生（正是本次整改要消灭的身份混用）。
      path: 'students/:id',
      name: 'campus-service-student-detail',
      redirect: '/admin/student/list'
    },
    {
      path: 'leave',
      name: 'campus-service-leave',
      // 分角色浏览器测试发现：旧版 LeaveApprovalView 调用 /campus-service/leaves/*，
      // 对走新版 13A 工作流提交的请假（affairs_status 非空）返回 student:null 且后端拒绝写操作
      // （DATA_CONFLICT "该请假已接入新版多级审批流程"），导致老师在此页面无法处理任何新提交的
      // 请假。新版初审工作台见 LeaveApprovalWorkbenchView，真实对接 /student-affairs/leave/*。
      component: () => import('@/modules/studentAffairs/views/leave/LeaveApprovalWorkbenchView.vue'),
      meta: { moduleCode: 'CAMPUS_SERVICE', requiresAuth: true, permissionKey: 'studentAffairs.leave.view', title: '请假审批' }
    },
    {
      path: 'leave-extensions',
      name: 'campus-service-leave-extensions',
      component: () => import('@/modules/studentAffairs/views/leave/LeaveExtensionCancelView.vue'),
      meta: { moduleCode: 'CAMPUS_SERVICE', requiresAuth: true, permissionKey: 'studentAffairs.leave.view', title: '延期销假' }
    },
    {
      path: 'leave-ledger',
      name: 'campus-service-leave-ledger',
      component: () => import('@/modules/studentAffairs/views/leave/LeaveLedgerView.vue'),
      meta: { moduleCode: 'CAMPUS_SERVICE', requiresAuth: true, permissionKey: 'studentAffairs.leave.view', title: '请假台账' }
    },
    {
      path: 'leave-stats',
      name: 'campus-service-leave-stats',
      component: () => import('@/modules/studentAffairs/views/leave/LeaveStatsView.vue'),
      meta: { moduleCode: 'CAMPUS_SERVICE', requiresAuth: true, permissionKey: 'studentAffairs.leave.view', title: '请假统计' }
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
      // 旧页已迁正式考评；保留 path 避免书签/外链 404
      path: 'counselor-assessment',
      name: 'campus-service-counselor-assessment',
      redirect: '/admin/student-affairs/counselor-eval'
    },
    {
      // 旧 mock 奖助页停用，统一走 13A 奖助工作台
      path: 'grants',
      name: 'campus-service-grants',
      redirect: '/admin/student-affairs/funding'
    },
    {
      // 旧宿舍服务页停用，统一走学工中心「宿舍与公寓」
      path: 'dormitory',
      name: 'campus-service-dormitory',
      redirect: '/admin/student-affairs/dorm/checkin'
    },
    {
      // 同上；旧住宿记录 id 在新宿舍模块无对应，只回入住管理列表
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
      // 旧 mock 违纪页停用，统一走 13A 处分工作台
      path: 'discipline',
      name: 'campus-service-discipline',
      redirect: '/admin/student-affairs/discipline'
    },
    {
      // 「服务工单」是老系统业务，新系统不再提供该功能，学工中心无继任页面。
      // 表与后端接口保留（历史数据不删），前端入口退役后回学工总览。
      path: 'work-orders',
      name: 'campus-service-work-orders',
      redirect: '/admin/student-affairs/dashboard'
    }
  ]
}

export default campusServiceRoutes
