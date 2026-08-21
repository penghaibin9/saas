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
      path: 'commercial-control',
      name: 'platform-commercial-control',
      component: () => import('@/modules/platform/views/control/PlatformCommercialControlView.vue'),
      meta: { moduleCode: 'PLATFORM', title: '商业授权与计量对账', requiresAuth: true, permissionKey: 'platform.commercial.view' }
    },
    {
      path: 'access',
      name: 'platform-access',
      component: () => import('@/modules/platform/views/control/PlatformAccessView.vue'),
      meta: { moduleCode: 'PLATFORM', title: '平台人员职责与受控协助', requiresAuth: true, permissionKey: 'platform.access.review' }
    },
    {
      path: 'product-iam',
      name: 'platform-product-iam',
      component: () => import('@/modules/platform/views/control/PlatformProductIamView.vue'),
      meta: { moduleCode: 'PLATFORM', title: 'Product IAM', requiresAuth: true, permissionKey: 'platform.productIam.view' }
    },
    {
      // PLAT-08：服务目录、依赖与租户影响地图
      path: 'services',
      name: 'platform-services',
      component: () => import('@/modules/platform/views/control/PlatformServiceCatalogView.vue'),
      meta: { moduleCode: 'PLATFORM', title: '服务目录、依赖与租户影响地图', requiresAuth: true, permissionKey: 'platform.control.view' }
    },
    {
      // PLAT-06：公共底座运行中心（跨租户聚合 PR#25 文件底座 + PLAT-08 服务目录）
      path: 'foundations',
      name: 'platform-foundations',
      component: () => import('@/modules/platform/views/control/PlatformFoundationOpsView.vue'),
      meta: { moduleCode: 'PLATFORM', title: '公共底座运行中心', requiresAuth: true, permissionKey: 'platform.control.view' }
    },
    {
      // PLAT-14：数据治理、集成目录与合规证据（跨租户聚合）
      path: 'governance',
      name: 'platform-governance',
      component: () => import('@/modules/platform/views/control/PlatformGovernanceView.vue'),
      meta: { moduleCode: 'PLATFORM', title: '数据治理、集成目录与合规证据', requiresAuth: true, permissionKey: 'platform.control.view' }
    },
    {
      // PLAT-05：客户健康、工单、培训与续费；与 Platform Workforce customerSuccess.manage 同源。
      path: 'customer-success',
      name: 'platform-customer-success',
      component: () => import('@/modules/platform/views/control/PlatformCustomerSuccessView.vue'),
      meta: { moduleCode: 'PLATFORM', title: '客户健康、工单、培训与续费', requiresAuth: true, permissionKey: 'platform.customerSuccess.manage' }
    },
    {
      path: 'tenant-migration',
      name: 'platform-tenant-migration',
      component: () => import('@/modules/platform/views/PlatformTenantMigrationView.vue'),
      meta: { moduleCode: 'PLATFORM', title: '租户数据迁移进度', requiresAuth: true, permissionKey: 'platform.tenant.migration.view' }
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
    },

    /* Stage B / P1-09：以下旧 URL 仅保留兼容跳转，不再挂 PlatformCapabilityView 说明壳。
       真实业务能力尚未闭环时不得进入正式生产导航；旧书签跳到已经存在的上位真实工作区。 */
    {
      path: 'tenant-lifecycle', name: 'platform-tenant-lifecycle', redirect: '/admin/platform/tenants',
      meta: { moduleCode: 'PLATFORM', title: '租户生命周期看板（已下线说明壳）', requiresAuth: true, permissionKey: 'platform.tenant.lifecycle.view', legacyCapabilityRedirect: true }
    },
    {
      // PLAT-09：真实实现
      path: 'incidents', name: 'platform-incidents', component: () => import('@/modules/platform/views/control/PlatformIncidentView.vue'),
      meta: { moduleCode: 'PLATFORM', title: '告警与事件中心', requiresAuth: true, permissionKey: 'platform.incident.view' }
    },
    {
      path: 'tenant-transitions', name: 'platform-tenant-transitions', redirect: '/admin/platform/tenants',
      meta: { moduleCode: 'PLATFORM', title: '开通、停用与归档（兼容入口）', requiresAuth: true, permissionKey: 'platform.tenant.lifecycle.manage', legacyCapabilityRedirect: true }
    },
    {
      path: 'tenant-contacts', name: 'platform-tenant-contacts', redirect: '/admin/platform/tenants',
      meta: { moduleCode: 'PLATFORM', title: '学校联系人与平台主管理员（兼容入口）', requiresAuth: true, permissionKey: 'platform.tenant.contact.manage', legacyCapabilityRedirect: true }
    },
    {
      path: 'products', name: 'platform-products', redirect: '/admin/platform/packages',
      meta: { moduleCode: 'PLATFORM', title: '产品与增值能力（兼容入口）', requiresAuth: true, permissionKey: 'platform.product.view', legacyCapabilityRedirect: true }
    },
    {
      path: 'init-templates', name: 'platform-init-templates', redirect: '/admin/platform/provisioning',
      meta: { moduleCode: 'PLATFORM', title: '初始化模板（兼容入口）', requiresAuth: true, permissionKey: 'platform.provision.template.manage', legacyCapabilityRedirect: true }
    },
    {
      // PLAT-04：真实实现
      path: 'provisioning', name: 'platform-provisioning', component: () => import('@/modules/platform/views/control/PlatformProvisioningView.vue'),
      meta: { moduleCode: 'PLATFORM', title: '自动开通任务', requiresAuth: true, permissionKey: 'platform.provision.run.view' }
    },
    {
      path: 'onboarding-check', name: 'platform-onboarding-check', component: () => import('@/modules/platform/views/PlatformOnboardingCheckView.vue'),
      meta: { moduleCode: 'PLATFORM', title: '学校开通与首次开户', requiresAuth: true, permissionKey: 'platform.onboarding.view', platformCapabilityKey: 'plt-onboarding-check' }
    },
    {
      path: 'role-templates', name: 'platform-role-templates', redirect: '/admin/platform/product-iam',
      meta: { moduleCode: 'PLATFORM', title: '平台主管角色模板（兼容入口）', requiresAuth: true, permissionKey: 'platform.productIam.view', legacyCapabilityRedirect: true }
    },
    {
      path: 'releases', name: 'platform-releases', redirect: '/admin/platform/changes',
      meta: { moduleCode: 'PLATFORM', title: '版本发布与灰度开关（兼容入口）', requiresAuth: true, permissionKey: 'platform.release.manage', legacyCapabilityRedirect: true }
    },
    {
      // PLAT-10：问题管理、已知错误与事故复盘
      path: 'problems', name: 'platform-problems',
      component: () => import('@/modules/platform/views/control/PlatformProblemView.vue'),
      meta: { moduleCode: 'PLATFORM', title: '问题管理、已知错误与事故复盘', requiresAuth: true, permissionKey: 'platform.incident.view' }
    },
    {
      // PLAT-13：租户用量、容量、成本与公平使用
      path: 'fair-use', name: 'platform-fair-use',
      component: () => import('@/modules/platform/views/control/PlatformFairUseView.vue'),
      meta: { moduleCode: 'PLATFORM', title: '租户用量、容量、成本与公平使用', requiresAuth: true, permissionKey: 'platform.control.view' }
    },
    {
      // PLAT-12：备份恢复验证与灾备（证据元数据）
      path: 'disaster-recovery', name: 'platform-disaster-recovery',
      component: () => import('@/modules/platform/views/control/PlatformDisasterRecoveryView.vue'),
      meta: { moduleCode: 'PLATFORM', title: '备份恢复验证与灾备', requiresAuth: true, permissionKey: 'platform.control.view' }
    },
    {
      // PLAT-11：变更评估/审批/排期/灰度/回滚唯一正式业务面
      path: 'changes', name: 'platform-changes',
      component: () => import('@/modules/platform/views/control/PlatformChangeView.vue'),
      meta: { moduleCode: 'PLATFORM', title: '变更、发布、兼容性、灰度与回滚', requiresAuth: true, permissionKey: 'platform.change.manage' }
    },
    {
      path: 'support-tickets', name: 'platform-support-tickets', redirect: '/admin/platform/customer-success',
      meta: { moduleCode: 'PLATFORM', title: '工单与服务请求（兼容入口）', requiresAuth: true, permissionKey: 'platform.support.ticket.manage', legacyCapabilityRedirect: true }
    },
    {
      path: 'support-sessions', name: 'platform-support-sessions', redirect: '/admin/platform/access',
      meta: { moduleCode: 'PLATFORM', title: '受控远程协助（兼容入口）', requiresAuth: true, permissionKey: 'platform.support.session.manage', legacyCapabilityRedirect: true }
    },
    {
      path: 'tenant-health', name: 'platform-tenant-health', redirect: '/admin/platform/customer-success',
      meta: { moduleCode: 'PLATFORM', title: '租户健康度与客户沟通（兼容入口）', requiresAuth: true, permissionKey: 'platform.customer-health.view', legacyCapabilityRedirect: true }
    },
    {
      path: 'operator-access', name: 'platform-operator-access', redirect: '/admin/platform/access',
      meta: { moduleCode: 'PLATFORM', title: '平台人员与职责权限', requiresAuth: true, permissionKey: 'platform.access.review' }
    }
  ]
}

export default platformRoutes