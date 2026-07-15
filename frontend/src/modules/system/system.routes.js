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
    /* 8 组 26 项学校级系统管理中尚未有独立业务页的治理能力。
       统一进入 SystemCapabilityView，不伪造写接口；真实服务按 meta.systemCapabilityKey 接入。 */
    {
      path: 'account-exceptions', name: 'system-account-exceptions',
      component: () => import('@/modules/system/views/SystemCapabilityView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '账号异常中心', requiresAuth: true, permissionKey: 'systemAdmin.user.exception.view', systemCapabilityKey: 'sys-account-exceptions' }
    },
    {
      path: 'login-policy', name: 'system-login-policy',
      component: () => import('@/modules/system/views/SystemCapabilityView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '登录与安全策略', requiresAuth: true, permissionKey: 'systemAdmin.security.policy.manage', systemCapabilityKey: 'sys-login-policy' }
    },
    {
      path: 'staff-affiliations', name: 'system-staff-affiliations',
      component: () => import('@/modules/system/views/SystemCapabilityView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '教职工岗位与归属', requiresAuth: true, permissionKey: 'systemAdmin.org.affiliation.manage', systemCapabilityKey: 'sys-staff-affiliations' }
    },
    {
      path: 'delegations', name: 'system-delegations',
      component: () => import('@/modules/system/views/SystemCapabilityView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '临时授权与工作移交', requiresAuth: true, permissionKey: 'systemAdmin.delegation.manage', systemCapabilityKey: 'sys-delegations' }
    },
    {
      path: 'module-entitlements', name: 'system-module-entitlements',
      component: () => import('@/modules/system/views/SystemCapabilityView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '模块授权与业务开关', requiresAuth: true, permissionKey: 'systemAdmin.config.feature.view', systemCapabilityKey: 'sys-module-entitlements' }
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
      component: () => import('@/modules/system/views/SystemCapabilityView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '敏感与导入导出审计', requiresAuth: true, permissionKey: 'systemAdmin.audit.sensitive.view', systemCapabilityKey: 'sys-sensitive-audit' }
    },
    {
      path: 'integrations', name: 'system-integrations',
      component: () => import('@/modules/system/views/SystemCapabilityView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '接口、凭证与 Webhook', requiresAuth: true, permissionKey: 'systemAdmin.integration.manage', systemCapabilityKey: 'sys-integration-connections' }
    },
    {
      path: 'sync-jobs', name: 'system-sync-jobs',
      component: () => import('@/modules/system/views/SystemCapabilityView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '同步任务与失败中心', requiresAuth: true, permissionKey: 'systemAdmin.integration.sync.view', systemCapabilityKey: 'sys-sync-jobs' }
    }
  ]
}

export default systemRoutes
