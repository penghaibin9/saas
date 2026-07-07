/**
 * 数字迎新中心 — 模块路由描述文件（仅导出配置，不自行接入全局 router）。
 *
 * 接入建议（由集成负责人统一在 src/router/index.js 中追加，避免并行任务冲突）：
 *   import { orientationRoutes } from '@/modules/orientation/orientation.routes'
 *   routes: [ ...existingRoutes, orientationRoutes ]
 */
export const orientationRoutes = {
  path: '/admin/orientation',
  component: () => import('@/views/admin/orientation/AdminOrientationLayout.vue'),
  meta: { moduleCode: 'ORIENTATION' },
  children: [
    {
      path: '',
      name: 'orientation-dashboard',
      component: () => import('@/views/admin/orientation/OrientationDashboardView.vue'),
      meta: { moduleCode: 'ORIENTATION', title: '数字迎新管理看板', requiresAuth: true, permissionKey: 'orientation.student.view' }
    },
    {
      path: 'batches',
      name: 'orientation-batches',
      component: () => import('@/views/admin/orientation/OrientationBatchListView.vue'),
      meta: { moduleCode: 'ORIENTATION', title: '迎新批次', requiresAuth: true, permissionKey: 'orientation.student.view' }
    },
    {
      path: 'green-channels',
      name: 'orientation-green-channels',
      component: () => import('@/views/admin/orientation/OrientationGreenChannelView.vue'),
      meta: { moduleCode: 'ORIENTATION', title: '绿色通道', requiresAuth: true, permissionKey: 'orientation.student.view' }
    },
    {
      path: 'no-show',
      name: 'orientation-no-show',
      component: () => import('@/views/admin/orientation/OrientationNoShowView.vue'),
      meta: { moduleCode: 'ORIENTATION', title: '未报到学生', requiresAuth: true, permissionKey: 'orientation.student.view' }
    },
    {
      path: 'statistics',
      name: 'orientation-statistics',
      component: () => import('@/views/admin/orientation/OrientationStatsView.vue'),
      meta: { moduleCode: 'ORIENTATION', title: '迎新统计', requiresAuth: true, permissionKey: 'orientation.student.view' }
    },
    {
      path: 'verify',
      name: 'orientation-verify',
      component: () => import('@/views/admin/orientation/OrientationVerifyView.vue'),
      meta: { moduleCode: 'ORIENTATION', title: '新生信息核验', requiresAuth: true, permissionKey: 'orientation.student.view' }
    },
    {
      path: 'qualification',
      name: 'orientation-qualification',
      component: () => import('@/views/admin/orientation/OrientationQualificationView.vue'),
      meta: { moduleCode: 'ORIENTATION', title: '报到资格', requiresAuth: true, permissionKey: 'orientation.student.view' }
    },
    {
      path: 'data',
      name: 'orientation-data',
      component: () => import('@/views/admin/orientation/OrientationDataView.vue'),
      meta: { moduleCode: 'ORIENTATION', title: '新生数据', requiresAuth: true, permissionKey: 'orientation.student.view' }
    },
    {
      path: 'flow-config',
      name: 'orientation-flow-config',
      component: () => import('@/views/admin/orientation/OrientationFlowConfigView.vue'),
      meta: { moduleCode: 'ORIENTATION', title: '报到流程配置', requiresAuth: true, permissionKey: 'orientation.student.view' }
    },
    {
      path: 'dorm-preassign',
      name: 'orientation-dorm-preassign',
      component: () => import('@/views/admin/orientation/OrientationDormPreassignView.vue'),
      meta: { moduleCode: 'ORIENTATION', title: '宿舍预分配', requiresAuth: true, permissionKey: 'orientation.student.view' }
    },
    {
      path: 'checkin-points',
      name: 'orientation-checkin-points',
      component: () => import('@/views/admin/orientation/OrientationCheckinPointView.vue'),
      meta: { moduleCode: 'ORIENTATION', title: '现场报到点', requiresAuth: true, permissionKey: 'orientation.student.view' }
    },
    {
      path: 'notices',
      name: 'orientation-notices',
      component: () => import('@/views/admin/orientation/OrientationNoticeView.vue'),
      meta: { moduleCode: 'ORIENTATION', title: '迎新通知', requiresAuth: true, permissionKey: 'orientation.student.view' }
    },
    {
      path: 'archive',
      name: 'orientation-archive',
      component: () => import('@/views/admin/orientation/OrientationArchiveView.vue'),
      meta: { moduleCode: 'ORIENTATION', title: '迎新归档', requiresAuth: true, permissionKey: 'orientation.student.view' }
    },
    {
      path: 'students',
      name: 'orientation-students',
      component: () => import('@/views/admin/orientation/OrientationStudentListView.vue'),
      meta: { moduleCode: 'ORIENTATION', title: '新生报到学生列表', requiresAuth: true, permissionKey: 'orientation.student.view' }
    },
    {
      path: 'students/:studentId',
      name: 'orientation-student-detail',
      component: () => import('@/views/admin/orientation/OrientationStudentDetailView.vue'),
      meta: { moduleCode: 'ORIENTATION', title: '新生报到详情', requiresAuth: true, permissionKey: 'orientation.student.view' }
    },
    {
      path: 'progress',
      name: 'orientation-progress',
      component: () => import('@/views/admin/orientation/RegistrationProgressView.vue'),
      meta: { moduleCode: 'ORIENTATION', title: '报到进度跟踪', requiresAuth: true, permissionKey: 'orientation.student.view' }
    },
    {
      path: 'payment',
      name: 'orientation-payment',
      component: () => import('@/views/admin/orientation/PaymentGreenChannelView.vue'),
      meta: { moduleCode: 'ORIENTATION', title: '缴费与绿色通道', requiresAuth: true, permissionKey: 'orientation.payment.view' }
    },
    {
      path: 'materials',
      name: 'orientation-materials',
      component: () => import('@/views/admin/orientation/OrientationMaterialReviewView.vue'),
      meta: { moduleCode: 'ORIENTATION', title: '迎新材料审核', requiresAuth: true, permissionKey: 'orientation.material.review' }
    },
    {
      path: 'dorm',
      name: 'orientation-dorm',
      component: () => import('@/views/admin/orientation/DormCheckinView.vue'),
      meta: { moduleCode: 'ORIENTATION', title: '宿舍入住确认', requiresAuth: true, permissionKey: 'orientation.dorm.confirm' }
    },
    {
      path: 'exceptions',
      name: 'orientation-exceptions',
      component: () => import('@/views/admin/orientation/OrientationExceptionView.vue'),
      meta: { moduleCode: 'ORIENTATION', title: '迎新异常学生', requiresAuth: true, permissionKey: 'orientation.exception.handle' }
    }
  ]
}

export default orientationRoutes
