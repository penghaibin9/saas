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
      // 分角色浏览器测试发现：旧版 LeaveApprovalView 调用 /campus-service/leaves/*，
      // 对走新版 13A 工作流提交的请假（affairs_status 非空）返回 student:null 且后端拒绝写操作
      // （DATA_CONFLICT "该请假已接入新版多级审批流程"），导致老师在此页面无法处理任何新提交的
      // 请假。新版初审工作台见 LeaveApprovalWorkbenchView，真实对接 /student-affairs/leave/*。
      component: () => import('@/modules/studentAffairs/views/leave/LeaveApprovalWorkbenchView.vue'),
      meta: { moduleCode: 'CAMPUS_SERVICE', requiresAuth: true, permissionKey: 'campus.leave.view', title: '请假审批' }
    },
    {
      path: 'leave-extensions',
      name: 'campus-service-leave-extensions',
      component: () => import('@/modules/studentAffairs/views/leave/LeaveExtensionCancelView.vue'),
      meta: { moduleCode: 'CAMPUS_SERVICE', requiresAuth: true, permissionKey: 'campus.leave.view', title: '延期销假' }
    },
    {
      path: 'leave-ledger',
      name: 'campus-service-leave-ledger',
      component: () => import('@/modules/studentAffairs/views/leave/LeaveLedgerView.vue'),
      meta: { moduleCode: 'CAMPUS_SERVICE', requiresAuth: true, permissionKey: 'campus.leave.view', title: '请假台账' }
    },
    {
      path: 'leave-stats',
      name: 'campus-service-leave-stats',
      component: () => import('@/modules/studentAffairs/views/leave/LeaveStatsView.vue'),
      meta: { moduleCode: 'CAMPUS_SERVICE', requiresAuth: true, permissionKey: 'campus.leave.view', title: '请假统计' }
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
      path: 'dormitory',
      name: 'campus-service-dormitory',
      component: () => import('@/views/admin/campusService/DormitoryView.vue'),
      meta: { moduleCode: 'CAMPUS_SERVICE', requiresAuth: true, permissionKey: 'campus.dorm.view', title: '宿舍服务' }
    },
    {
      /* 第一批交互改造：单条住宿记录独立详情深链接（与住宿台账双栏复用同一详情组件）。权限沿用住宿台账 key，不扩大权限。 */
      path: 'dormitory/records/:recordId',
      name: 'campus-service-dorm-record-detail',
      component: () => import('@/views/admin/campusService/DormRecordDetailView.vue'),
      meta: { moduleCode: 'CAMPUS_SERVICE', requiresAuth: true, permissionKey: 'campus.dorm.view', title: '住宿详情' }
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
      path: 'work-orders',
      name: 'campus-service-work-orders',
      component: () => import('@/views/admin/campusService/WorkOrderView.vue'),
      meta: { moduleCode: 'CAMPUS_SERVICE', requiresAuth: true, permissionKey: 'campus.workorder.view', title: '服务工单' }
    }
  ]
}

export default campusServiceRoutes
