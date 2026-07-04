/**
 * 平台运营中心 / 集成开放中心 模块路由描述（PC-SYSTEM-PLATFORM-RUN）。
 * ⚠️ 本文件不自动接入全局 router（避免与并行任务冲突）。
 * 接入方式：在 src/router/index.js 的 routes 数组中加入：
 *   import platformRoutes from '@/modules/platform/platform.routes'
 *   routes: [..., platformRoutes]
 * meta 口径与既有模块一致（moduleCode / permissionKey / requiresAuth），供统一路由守卫消费。
 */
const platformRoutes = {
  path: '/admin/platform',
  component: () => import('@/views/admin/platform/AdminPlatformLayout.vue'),
  meta: { moduleCode: 'PLATFORM' },
  children: [
    {
      path: '',
      name: 'platform-dashboard',
      component: () => import('@/views/admin/platform/PlatformDashboardView.vue'),
      meta: { moduleCode: 'PLATFORM', title: '平台运营看板', requiresAuth: true, permissionKey: 'platform.dashboard.view' }
    },
    {
      path: 'tenants',
      name: 'platform-tenants',
      component: () => import('@/views/admin/platform/PlatformTenantListView.vue'),
      meta: { moduleCode: 'PLATFORM', title: '租户学校管理', requiresAuth: true, permissionKey: 'platform.tenant.view' }
    },
    {
      path: 'tenants/:id',
      name: 'platform-tenant-detail',
      component: () => import('@/views/admin/platform/PlatformTenantDetailView.vue'),
      meta: { moduleCode: 'PLATFORM', title: '租户详情', requiresAuth: true, permissionKey: 'platform.tenant.view' }
    },
    {
      path: 'packages',
      name: 'platform-packages',
      component: () => import('@/views/admin/platform/PlatformPackageView.vue'),
      meta: { moduleCode: 'PLATFORM', title: '套餐模块授权', requiresAuth: true, permissionKey: 'platform.package.view' }
    },
    {
      path: 'orders',
      name: 'platform-orders',
      component: () => import('@/views/admin/platform/PlatformOrderView.vue'),
      meta: { moduleCode: 'PLATFORM', title: '订单续费授权', requiresAuth: true, permissionKey: 'platform.order.view' }
    },
    {
      path: 'integrations',
      name: 'platform-integrations',
      component: () => import('@/views/admin/platform/PlatformIntegrationView.vue'),
      meta: { moduleCode: 'PLATFORM', title: '集成开放管理', requiresAuth: true, permissionKey: 'platform.integration.view' }
    },
    {
      path: 'api-access',
      name: 'platform-api-access',
      component: () => import('@/views/admin/platform/PlatformApiAccessView.vue'),
      meta: { moduleCode: 'PLATFORM', title: 'API 访问与 Webhook', requiresAuth: true, permissionKey: 'platform.api.view' }
    },
    {
      path: 'sync',
      name: 'platform-sync',
      component: () => import('@/views/admin/platform/PlatformSyncTaskView.vue'),
      meta: { moduleCode: 'PLATFORM', title: '同步任务与平台日志', requiresAuth: true, permissionKey: 'platform.sync.view' }
    }
  ]
}

export default platformRoutes
