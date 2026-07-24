/**
 * 系统管理中心 模块路由描述（PC-SYSTEM-PLATFORM-RUN）。
 * ⚠️ 本文件不自动接入全局 router（避免与并行任务冲突）。
 * 接入方式：在 src/router/index.js 的 routes 数组中加入：
 *   import systemRoutes from '@/modules/system/system.routes'
 *   routes: [...,  systemRoutes]
 * meta 口径与既有模块一致（moduleCode / permissionKey / requiresAuth），供统一路由守卫消费。
 */
const systemRoutes = {
  path: '/admin/system',
  component: () => import('@/modules/system/views/AdminSystemLayout.vue'),
  meta: { moduleCode: 'SYSTEM' },
  children: [
    {
      path: '',
      redirect: '/admin/system/overview'
    },
    {
      path: 'overview',
      name: 'system-overview',
      component: () => import('@/modules/system/views/SystemDashboardView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '系统管理中心', requiresAuth: true, permissionKey: 'systemAdmin.dashboard.view' }
    },
    {
      path: 'users',
      name: 'system-users',
      component: () => import('@/modules/system/views/SystemUserListView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '师生账号管理', requiresAuth: true,
        permissionKey: 'systemAdmin.user.view' }
    },
    {
      path: 'identity-import',
      name: 'system-identity-import',
      component: () => import('@/modules/system/views/SystemUserListView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '导入老师和学生', requiresAuth: true,
        permissionKey: 'systemAdmin.user.import', openImport: true }
    },
    {
      path: 'roles',
      name: 'system-roles',
      component: () => import('@/modules/system/views/SystemRoleListView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '角色权限管理', requiresAuth: true, permissionKey: 'systemAdmin.role.view' }
    },
    {
      path: 'menus',
      name: 'system-menus',
      redirect: '/admin/system/roles?tab=permissions'
    },
    {
      path: 'scopes',
      name: 'system-scopes',
      component: () => import('@/modules/system/views/SystemDataScopeView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '数据范围管理', requiresAuth: true, permissionKey: 'systemAdmin.scope.view' }
    },
    {
      path: 'org',
      name: 'system-org',
      component: () => import('@/modules/system/views/SystemOrgView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '组织结构管理', requiresAuth: true, permissionKey: 'systemAdmin.org.view' }
    },
    {
      path: 'config',
      name: 'system-config',
      component: () => import('@/modules/system/views/SystemConfigView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '系统与品牌配置', requiresAuth: true, permissionKey: 'systemAdmin.config.view' }
    },
    {
      path: 'logs',
      name: 'system-logs',
      component: () => import('@/modules/system/views/SystemLogView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '日志中心', requiresAuth: true, permissionKey: 'systemAdmin.audit.view' }
    },
    {
      path: 'migration',
      name: 'system-migration',
      component: () => import('@/modules/system/views/SystemMigrationView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '老系统数据迁移', requiresAuth: true,
        permissionKey: 'systemAdmin.migration.view' }
    },
    {
      path: 'implementation/overview', name: 'system-implementation-overview',
      component: () => import('@/modules/system/views/SystemImplementationView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '实施总览', requiresAuth: true, permissionKey: 'systemAdmin.implementation.view', implementationPageKey: 'overview' }
    },
    {
      path: 'implementation/wizard', name: 'system-implementation-wizard',
      component: () => import('@/modules/system/views/SystemImplementationView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '首次开局向导', requiresAuth: true, permissionKey: 'systemAdmin.implementation.configure', implementationPageKey: 'wizard' }
    },
    {
      path: 'implementation/presets', name: 'system-implementation-presets',
      component: () => import('@/modules/system/views/SystemImplementationView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '预设方案', requiresAuth: true, permissionKey: 'systemAdmin.implementation.preset.view', implementationPageKey: 'presets' }
    },
    {
      path: 'implementation/standards', name: 'system-implementation-standards',
      component: () => import('@/modules/system/views/NationalStandardsView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '职业教育国家标准库', requiresAuth: true, permissionKey: 'systemAdmin.implementation.preset.view' }
    },
    {
      path: 'implementation/data-mapping', name: 'system-implementation-mapping',
      component: () => import('@/modules/system/views/SystemImplementationView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '数据导入与智能匹配', requiresAuth: true, permissionKey: 'systemAdmin.implementation.mapping.manage', implementationPageKey: 'mapping' }
    },
    {
      path: 'implementation/installed', name: 'system-implementation-installed',
      component: () => import('@/modules/system/views/SystemImplementationView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '已安装配置', requiresAuth: true, permissionKey: 'systemAdmin.implementation.installed.view', implementationPageKey: 'installed' }
    },
    {
      path: 'implementation/changes', name: 'system-implementation-changes',
      component: () => import('@/modules/system/views/SystemImplementationView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '变更与升级', requiresAuth: true, permissionKey: 'systemAdmin.implementation.change.manage', implementationPageKey: 'changes' }
    },
    {
      path: 'implementation/acceptance', name: 'system-implementation-acceptance',
      component: () => import('@/modules/system/views/SystemImplementationView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '上线检查与验收', requiresAuth: true, permissionKey: 'systemAdmin.implementation.check.run', implementationPageKey: 'acceptance' }
    },
    {
      path: 'account-exceptions', name: 'system-account-exceptions',
      component: () => import('@/modules/system/views/SystemAccountExceptionView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '账号异常中心', requiresAuth: true, permissionKey: 'systemAdmin.user.exception.view' }
    },
    {
      path: 'login-policy', name: 'system-login-policy',
      component: () => import('@/modules/system/views/SystemLoginPolicyView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '登录与安全策略', requiresAuth: true, permissionKey: 'systemAdmin.security.policy.manage' }
    },
    {
      path: 'staff-affiliations', name: 'system-staff-affiliations',
      component: () => import('@/modules/system/views/SystemStaffAffiliationView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '教职工岗位与归属', requiresAuth: true, permissionKey: 'systemAdmin.org.affiliation.manage' }
    },
    {
      path: 'delegations', name: 'system-delegations',
      component: () => import('@/modules/system/views/SystemDelegationView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '临时授权与工作移交', requiresAuth: true, permissionKey: 'systemAdmin.delegation.manage' }
    },
    {
      path: 'module-entitlements', name: 'system-module-entitlements',
      component: () => import('@/modules/system/views/SystemModuleFeatureView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '模块授权与业务开关', requiresAuth: true, permissionKey: 'systemAdmin.config.feature.view' }
    },
    {
      path: 'numbering-rules', name: 'system-numbering-rules',
      component: () => import('@/modules/system/views/SystemCapabilityView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '编号规则', requiresAuth: true, permissionKey: 'systemAdmin.config.numbering.manage', systemCapabilityKey: 'sys-numbering-rules' }
    },
    {
      path: 'dictionaries-fields', name: 'system-dictionaries-fields',
      component: () => import('@/modules/system/views/SystemCapabilityView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '字典与扩展字段', requiresAuth: true, permissionKey: 'systemAdmin.config.dictionary.manage', systemCapabilityKey: 'sys-dictionaries-fields' }
    },
    {
      path: 'process-rules', name: 'system-process-rules',
      component: () => import('@/modules/system/views/SystemCapabilityView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '节点与规则配置', requiresAuth: true, permissionKey: 'workflow.rule.manage', systemCapabilityKey: 'sys-process-rules' }
    },
    {
      path: 'process-monitor', name: 'system-process-monitor',
      component: () => import('@/modules/system/views/SystemCapabilityView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '流程运行与异常处理', requiresAuth: true, permissionKey: 'workflow.instance.monitor', systemCapabilityKey: 'sys-process-monitor' }
    },
    {
      path: 'sensitive-audit', name: 'system-sensitive-audit',
      component: () => import('@/modules/system/views/SystemSensitiveAuditView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '敏感与导入导出审计', requiresAuth: true, permissionKey: 'systemAdmin.audit.sensitive.view' }
    },
    {
      path: 'integrations', name: 'system-integrations',
      component: () => import('@/modules/system/views/SystemIntegrationView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '接口、凭证与 Webhook', requiresAuth: true, permissionKey: 'systemAdmin.integration.manage' }
    },
    {
      path: 'sync-jobs', name: 'system-sync-jobs',
      component: () => import('@/modules/system/views/SystemSyncJobView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '同步任务与失败中心', requiresAuth: true, permissionKey: 'systemAdmin.integration.sync.view' }
    }
  ]
}

export default systemRoutes
