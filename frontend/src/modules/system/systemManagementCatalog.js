/**
 * 学校级系统管理能力目录（唯一业务口径）。
 *
 * 收口为 9 个二级工作区；既有真实能力归入对应工作区，不删除。
 * 平台运营的租户、套餐、全局权限点维护不在这里。
 */
const action = (key, label, risk = 'NORMAL') => ({ key, label, risk })

const RAW_SYSTEM_MANAGEMENT_CATALOG = [
  {
    key: 'sys-overview', label: '系统总览', icon: '◫',
    description: '模块健康、配置缺口、同步失败、安全风险与待处理事项。',
    items: [
      { key: 'sys-overview-readiness', label: '系统总览', path: '/admin/system/overview', permissionKey: 'system.dashboard.view', view: 'dashboard', actions: [action('system:overview:view', '查看概览')] }
    ]
  },
  {
    key: 'sys-implementation', label: '实施与验收', icon: '⌘',
    description: '学校初始化、基础数据与权限检查、模块准备度和上线检查。',
    items: [
      { key: 'sys-implementation-overview', label: '实施总览', path: '/admin/system/implementation/overview', permissionKey: 'systemAdmin.implementation.view', view: 'implementation', actions: [action('systemAdmin.implementation.create', '创建实施项目'), action('systemAdmin.implementation.view', '查看实施进度')] },
      { key: 'sys-implementation-wizard', label: '首次开局向导', path: '/admin/system/implementation/wizard', permissionKey: 'systemAdmin.implementation.configure', view: 'implementation', actions: [action('systemAdmin.implementation.configure', '保存问答配置'), action('systemAdmin.implementation.preview', '生成安装预览', 'HIGH')] },
      { key: 'sys-implementation-presets', label: '预设方案', path: '/admin/system/implementation/presets', permissionKey: 'systemAdmin.implementation.preset.view', view: 'implementation', actions: [action('systemAdmin.implementation.preset.view', '选择预设方案', 'HIGH')] },
      { key: 'sys-implementation-standards', label: '职业教育国家标准库', path: '/admin/system/implementation/standards', permissionKey: 'systemAdmin.implementation.preset.view', view: 'national-standards', actions: [action('systemAdmin.implementation.preset.view', '检索国家标准'), action('systemAdmin.implementation.configure', '绑定学校专业', 'HIGH')] },
      { key: 'sys-implementation-mapping', label: '数据导入与智能匹配', path: '/admin/system/implementation/data-mapping', permissionKey: 'systemAdmin.implementation.mapping.manage', view: 'implementation', actions: [action('systemAdmin.implementation.mapping.manage', '盘点与确认匹配', 'HIGH'), action('systemAdmin.implementation.mapping.apply', '安装组织与角色', 'HIGH')] },
      { key: 'sys-implementation-installed', label: '已安装配置', path: '/admin/system/implementation/installed', permissionKey: 'systemAdmin.implementation.installed.view', view: 'implementation', actions: [action('systemAdmin.implementation.installed.view', '查看安装版本')] },
      { key: 'sys-implementation-changes', label: '变更与升级', path: '/admin/system/implementation/changes', permissionKey: 'systemAdmin.implementation.change.manage', view: 'implementation', actions: [action('systemAdmin.implementation.change.manage', '创建变更项目', 'HIGH')] },
      { key: 'sys-implementation-acceptance', label: '上线检查与验收', path: '/admin/system/implementation/acceptance', permissionKey: 'systemAdmin.implementation.check.run', view: 'implementation', actions: [action('systemAdmin.implementation.check.run', '运行上线检查'), action('systemAdmin.implementation.accept', '验收封板', 'HIGH')] }
    ]
  },
  {
    key: 'sys-identity', label: '身份与账号', icon: '☰',
    description: '账号共用统一认证底座；教职工与学生按不同主数据、角色和操作边界分别管理。',
    items: [
      { key: 'sys-staff-accounts', label: '教职工账号', path: '/admin/system/accounts/staff', permissionKey: 'system.user.view', view: 'staff-accounts', actions: [action('user:update', '编辑账号'), action('user:disable', '停用/启用账号', 'HIGH'), action('user:reset-password', '重置密码', 'HIGH'), action('user:assign-role', '分配角色', 'HIGH'), action('user:export', '脱敏导出', 'HIGH')] },
      { key: 'sys-student-accounts', label: '学生账号', path: '/admin/system/accounts/students', permissionKey: 'system.user.view', view: 'student-accounts', actions: [action('user:disable', '停用/启用账号', 'HIGH'), action('user:reset-password', '重置密码', 'HIGH'), action('user:export', '脱敏导出', 'HIGH')] },
      /* 学生与教职工拆成两个独立入口：模板字段、结果统计与后续流程完全不同，
         混在一张表里靠「账号类型」列区分，学校填表极易串列。 */
      { key: 'sys-teacher-import', label: '教职工导入', path: '/admin/system/identity-import/teachers', permissionKey: 'system.user.import', view: 'teacher-import', actions: [action('user:import', '批量创建账号', 'HIGH')] },
      { key: 'sys-student-import', label: '学生导入与账号开通', path: '/admin/system/identity-import/students', permissionKey: 'system.user.import', view: 'student-import', actions: [action('user:import', '批量创建账号', 'HIGH')] },
      { key: 'sys-account-exceptions', label: '账号异常排查', path: '/admin/system/account-exceptions', permissionKey: 'system.user.exception.view', view: 'account-exceptions', actions: [] },
      { key: 'sys-login-policy', label: '登录与安全策略', path: '/admin/system/login-policy', permissionKey: 'system.security.policy.manage', view: 'login-policy', actions: [action('security:login-policy:update', '修改登录策略', 'HIGH')] }
    ]
  },
  {
    key: 'sys-org', label: '组织与任职', icon: '♜',
    description: '学院、专业、班级与教职工任职关系是四大业务中心共用的唯一主数据。',
    items: [
      { key: 'sys-org-colleges', label: '学院与部门', path: '/admin/system/org?tab=college', permissionKey: 'system.org.view', view: 'org', actions: [action('org:create', '新增组织'), action('org:update', '编辑组织'), action('org:disable', '停用组织', 'HIGH')] },
      { key: 'sys-org-majors', label: '专业管理', path: '/admin/system/org?tab=major', permissionKey: 'system.org.major.manage', view: 'org', actions: [action('org:major:manage', '维护专业')] },
      { key: 'sys-org-classes', label: '年级与班级', path: '/admin/system/org?tab=class', permissionKey: 'system.org.class.manage', view: 'org', actions: [action('org:class:manage', '维护班级')] },
      { key: 'sys-staff-affiliations', label: '教职工任职归属查询', path: '/admin/system/staff-affiliations', permissionKey: 'system.org.affiliation.manage', view: 'staff-affiliations', actions: [] }
    ]
  },
  {
    key: 'sys-access', label: '角色权限与数据范围', icon: '❖',
    description: '学校从平台角色模板启用并裁剪权限；数据范围使用结构化规则。',
    items: [
      { key: 'sys-role-templates', label: '预设角色模板', path: '/admin/system/roles?tab=templates', permissionKey: 'system.role.template.view', view: 'roles', actions: [action('role:template:enable', '启用角色模板', 'HIGH')] },
      { key: 'sys-role-members', label: '学校角色与成员', path: '/admin/system/roles?tab=members', permissionKey: 'system.role.view', view: 'roles', actions: [action('role:create', '新增角色', 'HIGH'), action('role:member:assign', '分配角色成员', 'HIGH'), action('role:deprecate', '停用角色', 'HIGH')] },
      { key: 'sys-role-permissions', label: '菜单与操作权限', path: '/admin/system/roles?tab=permissions', permissionKey: 'system.role.permission.manage', view: 'roles', actions: [action('role:config', '配置菜单与操作权限', 'HIGH')] },
      { key: 'sys-data-scopes', label: '数据范围规则', path: '/admin/system/scopes', permissionKey: 'system.scope.view', view: 'scopes', actions: [action('scope:create', '新增数据范围规则', 'HIGH'), action('scope:update', '修改数据范围规则', 'HIGH'), action('scope:deprecate', '停用数据范围规则', 'HIGH')] },
      { key: 'sys-delegations', label: '临时授权与工作移交', path: '/admin/system/delegations', permissionKey: 'system.delegation.manage', view: 'delegations', actions: [action('delegation:create', '创建临时授权', 'HIGH'), action('delegation:revoke', '提前回收授权', 'HIGH')] }
    ]
  },
  {
    key: 'sys-modules', label: '模块与学校配置', icon: '✦',
    description: '学校可在已购范围内启停模块，并维护本校可配置项。',
    items: [
      { key: 'sys-school-brand', label: '学校信息与品牌', path: '/admin/system/config?tab=brand', permissionKey: 'system.config.brand.manage', view: 'config', actions: [action('config:brand:update', '修改品牌配置', 'HIGH')] },
      { key: 'sys-module-entitlements', label: '模块授权与业务开关', path: '/admin/system/module-entitlements', permissionKey: 'system.config.feature.view', view: 'module-entitlements', actions: [action('config:feature:toggle', '调整业务开关', 'HIGH')] }
    ]
  },
  {
    key: 'sys-workflow', label: '流程配置与运行', icon: '⧉',
    description: '流程只引用系统统一角色；审批任务归工作台。',
    items: [
      { key: 'sys-process-templates', label: '流程模板与运行', path: '/admin/workflow/processes', permissionKey: 'workflow.process.view', view: 'workflow', actions: [action('workflow:template:manage', '维护流程模板', 'HIGH')] }
    ]
  },
  {
    key: 'sys-security-audit', label: '安全与审计', icon: '≡',
    description: '审计日志只增不删；敏感查看、导入导出与权限变更必须可追溯。',
    items: [
      { key: 'sys-operation-audit', label: '操作与权限审计', path: '/admin/system/logs?tab=operation', permissionKey: 'system.audit.operation.view', view: 'logs', actions: [action('audit:operation:view', '查看操作审计'), action('audit:operation:export', '导出操作审计', 'HIGH')] },
      { key: 'sys-login-audit', label: '登录与安全审计', path: '/admin/system/logs?tab=login', permissionKey: 'system.audit.login.view', view: 'logs', actions: [action('audit:login:view', '查看登录审计'), action('audit:login:export', '导出登录审计', 'HIGH')] },
      { key: 'sys-sensitive-audit', label: '敏感与导入导出审计', path: '/admin/system/sensitive-audit', permissionKey: 'system.audit.sensitive.view', view: 'sensitive-audit', actions: [action('audit:sensitive:view', '查看敏感审计'), action('audit:export:view', '查看导入导出审计')] }
    ]
  },
  {
    key: 'sys-integration-migration', label: '接口同步与数据迁移', icon: '↔',
    description: '接口凭证加密可测；同步失败进入失败中心；老系统迁移全程留痕。',
    items: [
      { key: 'sys-integration-connections', label: '接口、凭证与 Webhook', path: '/admin/system/integrations', permissionKey: 'system.integration.manage', view: 'integrations', actions: [action('integration:connection:manage', '维护接口连接', 'HIGH'), action('integration:credential:rotate', '轮换接口凭证', 'HIGH')] },
      { key: 'sys-sync-jobs', label: '同步任务与失败中心', path: '/admin/system/sync-jobs', permissionKey: 'system.integration.sync.view', view: 'sync-jobs', actions: [action('integration:sync:retry', '重试同步任务', 'HIGH'), action('integration:sync:cancel', '取消同步任务', 'HIGH')] },
      { key: 'sys-migration-workbench', label: '老系统数据迁移', path: '/admin/system/migration', permissionKey: 'system.migration.view', view: 'migration', actions: [action('migration:template:download', '下载迁移模板'), action('migration:validate', '上传并校验'), action('migration:confirm', '确认导入', 'HIGH')] }
    ]
  }
]

/**
 * 学校级系统管理的后端权限域统一为 systemAdmin.*。
 * 早期菜单使用 system.*，学校管理员的全量权限会掩盖这个差异；而系统管理员/审计员会被错误拒绝。
 * 在目录入口统一迁移，保证导航、角色授权树和路由消费同一套可执行权限码。
 */
const normalizePermissionKey = (permissionKey) => String(permissionKey || '').replace(/^system\./, 'systemAdmin.')

export const SYSTEM_MANAGEMENT_CATALOG = RAW_SYSTEM_MANAGEMENT_CATALOG.map((group) => ({
  ...group,
  items: group.items.map((item) => ({ ...item, permissionKey: normalizePermissionKey(item.permissionKey) }))
}))

export const SYSTEM_MANAGEMENT_ITEMS = SYSTEM_MANAGEMENT_CATALOG.flatMap((group) =>
  group.items.map((item) => ({ ...item, groupKey: group.key, groupLabel: group.label, groupDescription: group.description }))
)

export const SYSTEM_MANAGEMENT_ITEM_MAP = Object.fromEntries(
  SYSTEM_MANAGEMENT_ITEMS.map((item) => [item.key, item])
)

export const SYSTEM_MANAGEMENT_MENU_KEYS = SYSTEM_MANAGEMENT_ITEMS.map((item) => item.key)

/**
 * 角色配置页使用的 UI 节点 → 后端 permissionCode 映射。
 * UI 的层级 key 仅供渲染，保存时绝不直接当作后端权限码。
 */
export const SYSTEM_MENU_PERMISSION_BY_KEY = Object.fromEntries(
  SYSTEM_MANAGEMENT_ITEMS.map((item) => [item.key, item.permissionKey])
)

const ACTION_CODE_OVERRIDES = {
  'user:disable': 'systemAdmin.user.manage',
  'user:reset-password': 'systemAdmin.user.manage',
  'user:update': 'systemAdmin.user.manage',
  'user:create': 'systemAdmin.user.import',
  'role:config': 'systemAdmin.role.config',
  'audit:operation:view': 'systemAdmin.audit.view',
  'audit:login:view': 'systemAdmin.audit.view',
  'config:brand:update': 'systemAdmin.config.manage'
}

export const SYSTEM_ACTION_PERMISSION_BY_KEY = Object.fromEntries(
  SYSTEM_MANAGEMENT_ITEMS.flatMap((item) => item.actions.map((entry) => [
    entry.key,
    ACTION_CODE_OVERRIDES[entry.key] || `systemAdmin.${entry.key.replaceAll(':', '.')}`
  ]))
)
