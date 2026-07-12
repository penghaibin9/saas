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
      path: 'counselor-assessment',
      name: 'campus-service-counselor-assessment',
      component: () => import('@/modules/studentAffairs/views/class/CounselorAssessmentView.vue'),
      meta: { moduleCode: 'CAMPUS_SERVICE', requiresAuth: true, permissionKey: 'campus.record.view', title: '辅导员考评' }
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
      /* 第一批交互改造：单条住宿记录独立详情深链接（与住宿台账双栏复用同一详情组件）。权限沿用住宿台账 key，不扩大权限。 */
      path: 'dormitory/records/:recordId',
      name: 'campus-service-dorm-record-detail',
      component: () => import('@/views/admin/campusService/DormRecordDetailView.vue'),
      meta: { moduleCode: 'CAMPUS_SERVICE', requiresAuth: true, permissionKey: 'campus.dorm.view', title: '住宿详情' }
    },
    {
      /* 第一批交互改造：违纪详情独立页（完整违纪业务不再放右侧抽屉）。权限沿用违纪台账 key，不扩大权限。 */
      path: 'discipline/:recordId',
      name: 'campus-service-discipline-detail',
      component: () => import('@/views/admin/campusService/DisciplineDetailView.vue'),
      meta: { moduleCode: 'CAMPUS_SERVICE', requiresAuth: true, permissionKey: 'campus.discipline.view', title: '违纪详情' }
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
