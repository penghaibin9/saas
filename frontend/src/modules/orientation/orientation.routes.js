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
