/**
 * 学校级系统管理能力目录（唯一业务口径）。
 *
 * 平台运营的租户、套餐、全局权限点维护不在这里；本目录只描述学校管理员可见的
 * 8 组 26 个三级能力。导航、路由、角色授权树和能力说明页均应消费本目录，
 * 避免再出现「侧边栏、权限树、路由」三份菜单各自维护的情况。
 */
const action = (key, label, risk = 'NORMAL') => ({ key, label, risk })

const RAW_SYSTEM_MANAGEMENT_CATALOG = [
  {
    key: 'sys-overview', label: '系统概览', icon: '◫',
    description: '学校初始化检查、账号与组织完整性、模块开通状态及异常提醒。',
    items: [
      { key: 'sys-overview-readiness', label: '系统概览与初始化检查', path: '/admin/system/overview', permissionKey: 'system.dashboard.view', view: 'dashboard', actions: [action('system:overview:view', '查看概览')] }
    ]
  },
  {
    key: 'sys-identity', label: '身份与账号', icon: '☰',
    description: '师生账号只在统一入口创建，业务模块只能关联既有身份。',
    items: [
      { key: 'sys-accounts', label: '师生账号', path: '/admin/system/users', permissionKey: 'system.user.view', view: 'users', actions: [action('user:create', '新增账号', 'HIGH'), action('user:update', '编辑账号'), action('user:disable', '停用/启用账号', 'HIGH'), action('user:reset-password', '重置密码', 'HIGH'), action('user:assign-role', '分配角色', 'HIGH'), action('user:export', '脱敏导出', 'HIGH')] },
      { key: 'sys-identity-import', label: '导入老师和学生', path: '/admin/system/identity-import', permissionKey: 'system.user.import', view: 'identity-import', actions: [action('user:import', '批量创建账号', 'HIGH')] },
      { key: 'sys-account-exceptions', label: '账号异常中心', path: '/admin/system/account-exceptions', permissionKey: 'system.user.exception.view', view: 'capability', actions: [action('user:exception:resolve', '处理账号异常', 'HIGH')] },
      { key: 'sys-login-policy', label: '登录与安全策略', path: '/admin/system/login-policy', permissionKey: 'system.security.policy.manage', view: 'capability', actions: [action('security:login-policy:update', '修改登录策略', 'HIGH')] }
    ]
  },
  {
    key: 'sys-master-data', label: '组织主数据', icon: '♜',
    description: '学院、专业、班级与教职工任职关系是四大业务中心共用的唯一主数据。',
    items: [
      { key: 'sys-org-colleges', label: '学院与部门', path: '/admin/system/org?tab=college', permissionKey: 'system.org.view', view: 'org', actions: [action('org:create', '新增组织'), action('org:update', '编辑组织'), action('org:disable', '停用组织', 'HIGH')] },
      { key: 'sys-org-majors', label: '专业管理', path: '/admin/system/org?tab=major', permissionKey: 'system.org.major.manage', view: 'org', actions: [action('org:major:manage', '维护专业')] },
      { key: 'sys-org-classes', label: '年级与班级', path: '/admin/system/org?tab=class', permissionKey: 'system.org.class.manage', view: 'org', actions: [action('org:class:manage', '维护班级')] },
      { key: 'sys-staff-affiliations', label: '教职工岗位与归属', path: '/admin/system/staff-affiliations', permissionKey: 'system.org.affiliation.manage', view: 'capability', actions: [action('org:affiliation:manage', '维护任职关系', 'HIGH')] }
    ]
  },
  {
    key: 'sys-access', label: '角色与权限', icon: '❖',
    description: '学校从平台角色模板启用并裁剪权限；不能新建平台菜单或越权授予。',
    items: [
      { key: 'sys-role-templates', label: '预设角色模板', path: '/admin/system/roles?tab=templates', permissionKey: 'system.role.template.view', view: 'roles', actions: [action('role:template:enable', '启用角色模板', 'HIGH')] },
      { key: 'sys-role-members', label: '学校角色与成员', path: '/admin/system/roles?tab=members', permissionKey: 'system.role.view', view: 'roles', actions: [action('role:create', '新增角色', 'HIGH'), action('role:member:assign', '分配角色成员', 'HIGH'), action('role:deprecate', '停用角色', 'HIGH')] },
      { key: 'sys-role-permissions', label: '菜单与操作权限', path: '/admin/system/roles?tab=permissions', permissionKey: 'system.role.permission.manage', view: 'roles', actions: [action('role:config', '配置菜单与操作权限', 'HIGH')] },
      { key: 'sys-data-scopes', label: '数据范围规则', path: '/admin/system/scopes', permissionKey: 'system.scope.view', view: 'scopes', actions: [action('scope:create', '新增数据范围规则', 'HIGH'), action('scope:update', '修改数据范围规则', 'HIGH'), action('scope:deprecate', '停用数据范围规则', 'HIGH')] },
      { key: 'sys-delegations', label: '临时授权与工作移交', path: '/admin/system/delegations', permissionKey: 'system.delegation.manage', view: 'capability', actions: [action('delegation:create', '创建临时授权', 'HIGH'), action('delegation:revoke', '提前回收授权', 'HIGH')] }
    ]
  },
  {
    key: 'sys-school-config', label: '学校配置', icon: '✦',
    description: '学校可维护本校可配置项；套餐和租户授权只读，仍由平台运营侧管理。',
    items: [
      { key: 'sys-school-brand', label: '学校信息与品牌', path: '/admin/system/config?tab=brand', permissionKey: 'system.config.brand.manage', view: 'config', actions: [action('config:brand:update', '修改品牌配置', 'HIGH')] },
      { key: 'sys-module-entitlements', label: '模块授权与业务开关', path: '/admin/system/module-entitlements', permissionKey: 'system.config.feature.view', view: 'capability', actions: [action('config:feature:toggle', '调整业务开关', 'HIGH')] },
      { key: 'sys-numbering-rules', label: '编号规则', path: '/admin/system/numbering-rules', permissionKey: 'system.config.numbering.manage', view: 'capability', actions: [action('config:numbering:update', '修改编号规则', 'HIGH')] },
      { key: 'sys-dictionaries-fields', label: '字典与扩展字段', path: '/admin/system/dictionaries-fields', permissionKey: 'system.config.dictionary.manage', view: 'capability', actions: [action('config:dictionary:manage', '维护字典'), action('config:extension-field:manage', '维护扩展字段', 'HIGH')] }
    ]
  },
  {
    key: 'sys-workflow', label: '流程配置', icon: '⧉',
    description: '流程只引用系统统一角色；审批任务归工作台，不在这里重复维护。',
    items: [
      { key: 'sys-process-templates', label: '流程模板', path: '/admin/workflow/processes', permissionKey: 'workflow.process.view', view: 'workflow', actions: [action('workflow:template:manage', '维护流程模板', 'HIGH')] },
      { key: 'sys-process-rules', label: '节点与规则配置', path: '/admin/system/process-rules', permissionKey: 'workflow.rule.manage', view: 'capability', actions: [action('workflow:rule:manage', '维护节点与规则', 'HIGH')] },
      { key: 'sys-process-monitor', label: '流程运行与异常处理', path: '/admin/system/process-monitor', permissionKey: 'workflow.instance.monitor', view: 'capability', actions: [action('workflow:instance:intervene', '受控干预流程', 'HIGH')] }
    ]
  },
  {
    key: 'sys-security-audit', label: '安全与审计', icon: '≡',
    description: '审计日志只增不删；敏感查看、导入导出与权限变更必须可追溯到自然人。',
    items: [
      { key: 'sys-operation-audit', label: '操作与权限审计', path: '/admin/system/logs?tab=operation', permissionKey: 'system.audit.operation.view', view: 'logs', actions: [action('audit:operation:view', '查看操作审计'), action('audit:operation:export', '导出操作审计', 'HIGH')] },
      { key: 'sys-login-audit', label: '登录与安全审计', path: '/admin/system/logs?tab=login', permissionKey: 'system.audit.login.view', view: 'logs', actions: [action('audit:login:view', '查看登录审计'), action('audit:login:export', '导出登录审计', 'HIGH')] },
      { key: 'sys-sensitive-audit', label: '敏感与导入导出审计', path: '/admin/system/sensitive-audit', permissionKey: 'system.audit.sensitive.view', view: 'capability', actions: [action('audit:sensitive:view', '查看敏感审计'), action('audit:export:view', '查看导入导出审计')] }
    ]
  },
  {
    key: 'sys-integrations', label: '接口与同步', icon: '↔',
    description: '接口凭证必须加密、可测试、可审计；同步失败进入统一失败中心。',
    items: [
      { key: 'sys-integration-connections', label: '接口、凭证与 Webhook', path: '/admin/system/integrations', permissionKey: 'system.integration.manage', view: 'capability', actions: [action('integration:connection:manage', '维护接口连接', 'HIGH'), action('integration:credential:rotate', '轮换接口凭证', 'HIGH')] },
      { key: 'sys-sync-jobs', label: '同步任务与失败中心', path: '/admin/system/sync-jobs', permissionKey: 'system.integration.sync.view', view: 'capability', actions: [action('integration:sync:retry', '重试同步任务', 'HIGH'), action('integration:sync:cancel', '取消同步任务', 'HIGH')] }
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

export const SYSTEM_ACTION_PERMISSION_BY_KEY = Object.fromEntries(
  SYSTEM_MANAGEMENT_ITEMS.flatMap((item) => item.actions.map((entry) => [
    entry.key,
    `systemAdmin.${entry.key.replaceAll(':', '.')}`
  ]))
)
