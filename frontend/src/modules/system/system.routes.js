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
      path: 'accounts/staff',
      name: 'system-staff-accounts',
      component: () => import('@/modules/system/views/SystemUserListView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '教职工账号', accountType: 'STAFF', requiresAuth: true,
        permissionKey: 'systemAdmin.user.view' }
    },
    {
      path: 'accounts/students',
      name: 'system-student-accounts',
      component: () => import('@/modules/system/views/SystemUserListView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '学生账号', accountType: 'STUDENT', requiresAuth: true,
        permissionKey: 'systemAdmin.user.view' }
    },
    {
      /* 旧混合账号地址保留兼容，但不再展示师生混合列表。 */
      path: 'users',
      name: 'system-users',
      redirect: '/admin/system/accounts/staff'
    },
    {
      /* 学生与教师导入拆成两个真实路由：刷新后状态不丢、菜单可正确高亮、
         权限与模板各自独立，不用 query 伪装成两个页面。 */
      path: 'identity-import/students',
      name: 'system-student-import',
      component: () => import('@/modules/system/views/SystemStudentImportView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '学生导入与账号开通', requiresAuth: true,
        permissionKey: 'systemAdmin.user.import' }
    },
    {
      path: 'identity-import/teachers',
      name: 'system-teacher-import',
      component: () => import('@/modules/system/views/SystemTeacherImportView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '教职工导入', requiresAuth: true,
        permissionKey: 'systemAdmin.user.import' }
    },
    {
      path: 'data-exchange',
      name: 'system-data-exchange',
      component: () => import('@/modules/system/views/SystemDataExchangeView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '数据交换任务中心', requiresAuth: true,
        permissionKey: 'systemAdmin.user.import' }
    },
    {
      path: 'file-storage-governance',
      name: 'system-file-storage-governance',
      component: () => import('@/modules/system/views/SystemFileStorageGovernanceView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '文件存储治理', requiresAuth: true,
        permissionKey: 'systemAdmin.file.manage' }
    },
    {
      /* 旧的师生混合入口：保留路由避免既有链接 404，直接落到学生导入页。 */
      path: 'identity-import',
      redirect: '/admin/system/identity-import/students'
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
      // SYS-02：唯一正式实施入口。项目阶段/未确认政策/未安装对象/上线阻断/验收证据
      // 收在这一个工作区里；下面的分步页面保留为作业入口，不再各自当总览。
      path: 'implementation/overview', name: 'system-implementation-overview',
      component: () => import('@/modules/system/views/SystemImplementationWorkspaceView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '实施项目工作区', requiresAuth: true, permissionKey: 'systemAdmin.implementation.view', implementationPageKey: 'overview' }
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
      meta: { moduleCode: 'SYSTEM', title: '账号异常排查', requiresAuth: true, permissionKey: 'systemAdmin.user.exception.view' }
    },
    {
      path: 'login-policy', name: 'system-login-policy',
      component: () => import('@/modules/system/views/SystemLoginPolicyView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '登录与安全策略', requiresAuth: true, permissionKey: 'systemAdmin.security.policy.manage' }
    },
    {
      path: 'staff-affiliations', name: 'system-staff-affiliations',
      component: () => import('@/modules/system/views/SystemStaffAffiliationView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '教职工任职归属查询', requiresAuth: true, permissionKey: 'systemAdmin.org.affiliation.manage' }
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
      // SYS-14：节点动作与版本变更策略、人工推进。文档写的"唯一正式路由"是
      // /admin/workflow/processes，但那条路由已经在 router/index.js 里指向另一个
      // 既有页面（WorkflowProcessesView.vue），两个文件都不在本卡白名单内，不能改。
      // 挂在 /admin/system/* 家族下，跟 SYS-05/07/17 同样的处理方式，不留假入口。
      path: 'workflow-governance', name: 'system-workflow-governance',
      component: () => import('@/modules/system/views/SystemWorkflowGovernanceView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '流程安全与运行治理', requiresAuth: true, permissionKey: 'systemAdmin.workflow.view' }
    },
    {
      // SYS-15：消息/待办/通知注册表治理（第一阶段只做只读注册表 + adapter，不建统一大表）
      path: 'communications', name: 'system-communications',
      component: () => import('@/modules/system/views/SystemCommunicationGovernanceView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '统一消息、待办与通知治理', requiresAuth: true, permissionKey: 'systemAdmin.communication.view' }
    },
    {
      // SYS-16：批处理/调度/后台任务治理面板。跨5张既有任务表只读聚合 + 有限重试/取消
      path: 'jobs', name: 'system-jobs',
      component: () => import('@/modules/system/views/SystemJobCenterView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '批处理与后台任务', requiresAuth: true, permissionKey: 'systemAdmin.job.view' }
    },
    {
      // SYS-17：数据域责任人、质量规则、问题闭环与合并预览（不代业务部门确认业务事实）
      path: 'master-data', name: 'system-master-data',
      component: () => import('@/modules/system/views/SystemMasterDataView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '主数据责任与数据质量', requiresAuth: true, permissionKey: 'systemAdmin.config.view' }
    },
    {
      // SYS-07：固定角色成员的有效期/来源/复核，以及由业务表实时计算的自动业务身份
      path: 'role-assignments', name: 'system-role-assignments',
      component: () => import('@/modules/system/views/SystemRoleAssignmentView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '角色成员与业务身份', requiresAuth: true, permissionKey: 'systemAdmin.role.view' }
    },
    {
      // SYS-05：业务关系只在这里"发现与治理"，真实编辑仍回各业务模块（本页不写业务终态）
      path: 'business-relations', name: 'system-business-relations',
      component: () => import('@/modules/system/views/SystemBusinessRelationView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '业务关系中心', requiresAuth: true, permissionKey: 'systemAdmin.org.view' }
    },
    {
      // SYS-12：全校统一的学年学期与业务日历。学期主数据仍在教务维护，
      // 这里负责"全校何时切换"以及各模块的业务窗口。
      path: 'academic-calendar', name: 'system-academic-calendar',
      component: () => import('@/modules/system/views/SystemAcademicCalendarView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '学年学期与业务日历', requiresAuth: true, permissionKey: 'systemAdmin.academicCalendar.view' }
    },
    {
      // SYS-10：解释为什么能/不能访问。结论来自真实鉴权核心，页面不重算
      path: 'access-governance', name: 'system-access-governance',
      component: () => import('@/modules/system/views/SystemAccessGovernanceView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '访问治理', requiresAuth: true, permissionKey: 'systemAdmin.access.explain' }
    },
    {
      // SYS-09：安全变更的草稿/审核/排期都不改变真实权限，只有激活才生效
      path: 'security-changes', name: 'system-security-changes',
      component: () => import('@/modules/system/views/SystemSecurityChangeView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '安全变更', requiresAuth: true, permissionKey: 'systemAdmin.security.view' }
    },
    {
      path: 'numbering-rules', name: 'system-numbering-rules',
      redirect: '/admin/system/config?tab=system'
    },
    {
      path: 'dictionaries-fields', name: 'system-dictionaries-fields',
      redirect: '/admin/system/config?tab=system'
    },
    {
      path: 'process-rules', name: 'system-process-rules',
      redirect: '/admin/workflow/processes'
    },
    {
      path: 'process-monitor', name: 'system-process-monitor',
      redirect: '/admin/workflow/processes'
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
