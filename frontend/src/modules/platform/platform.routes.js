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
  component: () => import('@/modules/platform/views/AdminPlatformLayout.vue'),
  meta: { moduleCode: 'PLATFORM' },
  children: [
    {
      path: '',
      name: 'platform-dashboard',
      component: () => import('@/modules/platform/views/PlatformDashboardView.vue'),
      meta: { moduleCode: 'PLATFORM', title: '平台运营看板', requiresAuth: true, permissionKey: 'platform.dashboard.view' }
    },
    {
      path: 'tenants',
      name: 'platform-tenants',
      component: () => import('@/modules/platform/views/control/PlatformControlTenants.vue'),
      meta: { moduleCode: 'PLATFORM', title: '租户学校管理', requiresAuth: true, permissionKey: 'platform.tenant.view' }
    },
    {
      path: 'tenants/:tenantId',
      name: 'platform-tenant-detail',
      component: () => import('@/modules/platform/views/control/PlatformControlTenantDetail.vue'),
      meta: { moduleCode: 'PLATFORM', title: '租户详情', requiresAuth: true, permissionKey: 'platform.tenant.view' }
    },
    {
      path: 'packages',
      name: 'platform-packages',
      component: () => import('@/modules/platform/views/control/PlatformControlPackages.vue'),
      meta: { moduleCode: 'PLATFORM', title: '套餐模块授权', requiresAuth: true, permissionKey: 'platform.package.view' }
    },
    {
      path: 'orders',
      name: 'platform-orders',
      component: () => import('@/modules/platform/views/control/PlatformControlOrders.vue'),
      meta: { moduleCode: 'PLATFORM', title: '订单续费授权', requiresAuth: true, permissionKey: 'platform.order.view' }
    },
    {
      path: 'integrations',
      name: 'platform-integrations',
      component: () => import('@/modules/platform/views/PlatformIntegrationView.vue'),
      meta: { moduleCode: 'PLATFORM', title: '集成开放管理', requiresAuth: true, permissionKey: 'platform.integration.view' }
    },
    {
      path: 'api-access',
      name: 'platform-api-access',
      component: () => import('@/modules/platform/views/PlatformApiAccessView.vue'),
      meta: { moduleCode: 'PLATFORM', title: 'API 访问与 Webhook', requiresAuth: true, permissionKey: 'platform.api.view' }
    },
    {
      path: 'overview',
      name: 'platform-control-overview',
      component: () => import('@/modules/platform/views/control/PlatformControlOverview.vue'),
      meta: { moduleCode: 'PLATFORM', title: '平台总控台', requiresAuth: true, permissionKey: 'platform.control.view' }
    },
    {
      path: 'tenants/create',
      name: 'platform-tenant-create',
      component: () => import('@/modules/platform/views/control/PlatformControlTenants.vue'),
      meta: { moduleCode: 'PLATFORM', title: '开通新学校', requiresAuth: true, permissionKey: 'platform.tenant.manage', openCreate: true }
    },
    {
      path: 'features',
      name: 'platform-features',
      component: () => import('@/modules/platform/views/control/PlatformControlTenants.vue'),
      props: { targetTab: 'features' },
      meta: { moduleCode: 'PLATFORM', title: '功能开关', requiresAuth: true, permissionKey: 'platform.feature.view' }
    },
    {
      path: 'rules',
      name: 'platform-rules',
      component: () => import('@/modules/platform/views/control/PlatformControlTenants.vue'),
      props: { targetTab: 'rules' },
      meta: { moduleCode: 'PLATFORM', title: '规则中心', requiresAuth: true, permissionKey: 'platform.rule.view' }
    },
    {
      path: 'workflows',
      name: 'platform-workflows',
      component: () => import('@/modules/platform/views/control/PlatformControlTenants.vue'),
      props: { targetTab: 'workflows' },
      meta: { moduleCode: 'PLATFORM', title: '流程配置', requiresAuth: true, permissionKey: 'platform.workflow.view' }
    },
    {
      path: 'brands',
      name: 'platform-brands',
      component: () => import('@/modules/platform/views/control/PlatformControlTenants.vue'),
      props: { targetTab: 'brand' },
      meta: { moduleCode: 'PLATFORM', title: '品牌配置', requiresAuth: true, permissionKey: 'platform.brand.view' }
    },
    {
      path: 'users',
      name: 'platform-users',
      component: () => import('@/modules/platform/views/control/PlatformControlTenants.vue'),
      props: { targetTab: 'users' },
      meta: { moduleCode: 'PLATFORM', title: '账号控制', requiresAuth: true, permissionKey: 'platform.user.view' }
    },
    {
      path: 'dictionaries',
      name: 'platform-dictionaries',
      component: () => import('@/modules/platform/views/control/PlatformControlDictionaries.vue'),
      meta: { moduleCode: 'PLATFORM', title: '字典管理', requiresAuth: true, permissionKey: 'platform.dict.view' }
    },
    {
      path: 'notices',
      name: 'platform-notices',
      component: () => import('@/modules/platform/views/control/PlatformControlNotices.vue'),
      meta: { moduleCode: 'PLATFORM', title: '平台公告', requiresAuth: true, permissionKey: 'platform.notice.view' }
    },
    {
      path: 'security',
      name: 'platform-security',
      component: () => import('@/modules/platform/views/control/PlatformControlSecurity.vue'),
      meta: { moduleCode: 'PLATFORM', title: '安全策略', requiresAuth: true, permissionKey: 'platform.security.view' }
    },
    {
      path: 'audit',
      name: 'platform-audit',
      component: () => import('@/modules/platform/views/control/PlatformControlAudit.vue'),
      meta: { moduleCode: 'PLATFORM', title: '全平台审计', requiresAuth: true, permissionKey: 'platform.audit.view' }
    },
    {
      path: 'settings',
      name: 'platform-settings',
      component: () => import('@/modules/platform/views/control/PlatformControlSettings.vue'),
      meta: { moduleCode: 'PLATFORM', title: '平台系统参数', requiresAuth: true, permissionKey: 'platform.settings.view' }
    },
    {
      path: 'file-storage',
      name: 'platform-file-storage',
      component: () => import('@/modules/platform/views/control/PlatformControlFileStorage.vue'),
      meta: { moduleCode: 'PLATFORM', title: '文件存储设置', requiresAuth: true, permissionKey: 'platform.settings.view' }
    },
    {
      path: 'sync',
      name: 'platform-sync',
      component: () => import('@/modules/platform/views/PlatformSyncTaskView.vue'),
      meta: { moduleCode: 'PLATFORM', title: '同步任务与平台日志', requiresAuth: true, permissionKey: 'platform.sync.view' }
    }
  ]
}

export default platformRoutes
