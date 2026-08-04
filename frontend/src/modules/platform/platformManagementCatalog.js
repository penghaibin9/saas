/**
 * SaaS 平台运营控制面能力目录（唯一口径）。
 *
 * 仅平台角色可见。它管理跨学校的租户生命周期、授权、交付、运行和合规，
 * 不提供直接浏览或修改学校业务数据的入口。导航、路由和后续平台角色授权均消费本目录。
 */
const action = (key, label, risk = 'NORMAL') => ({ key, label, risk })

export const PLATFORM_MANAGEMENT_CATALOG = [
  {
    key: 'plt-command', label: '平台总控', icon: '◎', description: '经营、租户生命周期和运行事件的跨租户总览。',
    items: [
      { key: 'plt-overview', label: '平台经营总览', path: '/admin/platform/overview', permissionKey: 'platform.control.view', view: 'overview', actions: [action('platform:overview:view', '查看平台总览')] },
      { key: 'plt-service-catalog', label: '服务目录、依赖与租户影响地图', path: '/admin/platform/services', permissionKey: 'platform.control.view', view: 'services', actions: [action('service:manage', '维护服务目录/依赖', 'HIGH')] },
      { key: 'plt-foundations', label: '公共底座运行中心', path: '/admin/platform/foundations', permissionKey: 'platform.control.view', view: 'foundations', actions: [action('foundation:overview:view', '查看公共底座运行总览')] },
      { key: 'plt-governance', label: '数据治理、集成目录与合规证据', path: '/admin/platform/governance', permissionKey: 'platform.control.view', view: 'governance', actions: [action('governance:overview:view', '查看数据治理与合规证据总览')] },
      { key: 'plt-customer-success', label: '客户健康、工单、培训与续费', path: '/admin/platform/customer-success', permissionKey: 'platform.control.view', view: 'customer-success', actions: [action('ticket:manage', '处理工单'), action('training:manage', '登记培训'), action('renewal:manage', '跟进续费')] },
      { key: 'plt-lifecycle-board', label: '租户生命周期看板', path: '/admin/platform/tenant-lifecycle', permissionKey: 'platform.tenant.lifecycle.view', view: 'capability', actions: [action('tenant:lifecycle:view', '查看生命周期')] },
      { key: 'plt-incidents', label: '告警与事件中心', path: '/admin/platform/incidents', permissionKey: 'platform.incident.view', view: 'incidents', actions: [action('incident:acknowledge', '确认告警'), action('incident:resolve', '关闭事件', 'HIGH'), action('incident:publish', '发布通知', 'HIGH')] },
      { key: 'plt-problems', label: '问题管理、已知错误与事故复盘', path: '/admin/platform/problems', permissionKey: 'platform.incident.view', view: 'problems', actions: [action('problem:manage', '流转问题/发布已知错误', 'HIGH'), action('postmortem:publish', '发布复盘', 'HIGH')] }
    ]
  },
  {
    key: 'plt-tenancy', label: '租户生命周期', icon: '♜', description: '学校从试用、开通、运营、到期、停用到归档的全生命周期管理。',
    items: [
      { key: 'plt-tenants', label: '租户学校', path: '/admin/platform/tenants', permissionKey: 'platform.tenant.view', view: 'tenants', actions: [action('tenant:create', '创建租户', 'HIGH'), action('tenant:update', '修改租户'), action('tenant:suspend', '停用租户', 'HIGH')] },
      { key: 'plt-trials', label: '试用与线索', path: '/admin/platform/tenants?status=trial', permissionKey: 'platform.tenant.trial.manage', view: 'tenants', actions: [action('tenant:trial:create', '创建试用租户', 'HIGH'), action('tenant:trial:extend', '延长试用', 'HIGH'), action('tenant:trial:convert', '转为正式', 'HIGH')] },
      { key: 'plt-tenant-transitions', label: '开通、停用与归档', path: '/admin/platform/tenant-transitions', permissionKey: 'platform.tenant.lifecycle.manage', view: 'capability', actions: [action('tenant:activate', '正式开通', 'HIGH'), action('tenant:readonly', '切换只读', 'HIGH'), action('tenant:archive', '归档租户', 'HIGH')] },
      { key: 'plt-tenant-contacts', label: '学校联系人与平台主管理员', path: '/admin/platform/tenant-contacts', permissionKey: 'platform.tenant.contact.manage', view: 'capability', actions: [action('tenant:contact:manage', '维护联系人'), action('tenant:admin:reset', '重置学校管理员', 'HIGH')] }
    ]
  },
  {
    key: 'plt-commercial', label: '产品、合同与授权', icon: '❖', description: '产品和套餐定义与学校实际授权分离；订单生效才触发功能开通。',
    items: [
      { key: 'plt-products', label: '产品与增值能力', path: '/admin/platform/products', permissionKey: 'platform.product.view', view: 'capability', actions: [action('product:feature:manage', '维护产品能力', 'HIGH')] },
      { key: 'plt-commercial-control', label: '商业授权与计量对账', path: '/admin/platform/commercial-control', permissionKey: 'platform.commercial.view', view: 'commercial-control', actions: [action('commercial:reconcile:view', '查看商业对账')] },
      { key: 'plt-packages', label: '套餐与价格版本', path: '/admin/platform/packages', permissionKey: 'platform.package.view', view: 'packages', actions: [action('package:create', '新增套餐', 'HIGH'), action('package:version:publish', '发布价格版本', 'HIGH')] },
      { key: 'plt-orders', label: '合同、订单与续费', path: '/admin/platform/orders', permissionKey: 'platform.order.view', view: 'orders', actions: [action('order:create', '创建订单', 'HIGH'), action('order:activate', '确认并开通订单', 'HIGH'), action('order:void', '作废订单', 'HIGH')] },
      { key: 'plt-entitlements', label: '租户授权、配额与到期策略', path: '/admin/platform/features', permissionKey: 'platform.feature.view', view: 'tenant-features', actions: [action('entitlement:grant', '授予能力', 'HIGH'), action('entitlement:revoke', '回收能力', 'HIGH'), action('quota:adjust', '调整配额', 'HIGH')] }
    ]
  },
  {
    key: 'plt-delivery', label: '自动交付', icon: '⇪', description: '订单确认后自动初始化学校，减少实施人员逐校配置。',
    items: [
      { key: 'plt-init-templates', label: '初始化模板', path: '/admin/platform/init-templates', permissionKey: 'platform.provision.template.manage', view: 'capability', actions: [action('provision:template:publish', '发布初始化模板', 'HIGH')] },
      { key: 'plt-provisioning', label: '自动开通任务', path: '/admin/platform/provisioning', permissionKey: 'platform.provision.run.view', view: 'provisioning', actions: [action('provision:run:retry', '重试开通任务', 'HIGH'), action('provision:run:compensate', '发起补偿', 'HIGH'), action('provision:run:cancel', '取消开通任务', 'HIGH')] },
      { key: 'plt-onboarding-check', label: '学校开通与首次开户', path: '/admin/platform/onboarding-check', permissionKey: 'platform.onboarding.view', view: 'onboarding', actions: [action('onboarding:check:run', '查看开通进度'), action('onboarding:accept', '确认上线验收', 'HIGH')] },
      { key: 'plt-tenant-migration', label: '租户数据迁移进度', path: '/admin/platform/tenant-migration', permissionKey: 'platform.tenant.migration.view', view: 'tenant-migration', actions: [action('tenant:migration:view', '查看迁移进度')] }
    ]
  },
  {
    key: 'plt-standards', label: '全局标准与发布', icon: '☲', description: '统一角色模板、全局规则和版本发布，学校只能在受控范围内使用。',
    items: [
      { key: 'plt-role-templates', label: '平台角色模板', path: '/admin/platform/role-templates', permissionKey: 'platform.role-template.manage', view: 'capability', actions: [action('role-template:publish', '发布角色模板', 'HIGH')] },
      { key: 'plt-global-rules', label: '全局字典与规则', path: '/admin/platform/dictionaries', permissionKey: 'platform.dict.view', view: 'dictionaries', actions: [action('rule:global:update', '更新全局规则', 'HIGH')] },
      { key: 'plt-releases', label: '版本发布与灰度开关', path: '/admin/platform/releases', permissionKey: 'platform.release.manage', view: 'capability', actions: [action('release:canary:start', '开始灰度发布', 'HIGH'), action('release:rollback', '回滚发布', 'HIGH')] },
      { key: 'plt-changes', label: '变更、发布、兼容性、灰度与回滚', path: '/admin/platform/changes', permissionKey: 'platform.change.manage', view: 'changes', actions: [action('change:approve', '审批变更', 'HIGH'), action('change:schedule', '排期变更', 'HIGH'), action('change:rollback', '回滚变更', 'HIGH')] }
    ]
  },
  {
    key: 'plt-success', label: '客户成功与支持', icon: '♡', description: '让少量运营人员通过健康度、工单和受控协助服务更多学校。',
    items: [
      { key: 'plt-support-tickets', label: '工单与服务请求', path: '/admin/platform/support-tickets', permissionKey: 'platform.support.ticket.manage', view: 'capability', actions: [action('support:ticket:assign', '分派工单'), action('support:ticket:close', '关闭工单')] },
      { key: 'plt-support-sessions', label: '受控远程协助', path: '/admin/platform/support-sessions', permissionKey: 'platform.support.session.manage', view: 'capability', actions: [action('support:session:request', '发起协助授权', 'HIGH'), action('support:session:terminate', '终止协助会话', 'HIGH')] },
      { key: 'plt-tenant-health', label: '租户健康度与客户沟通', path: '/admin/platform/tenant-health', permissionKey: 'platform.customer-health.view', view: 'capability', actions: [action('customer-health:review', '复核健康度'), action('customer:notice:publish', '发布客户公告', 'HIGH')] }
    ]
  },
  {
    key: 'plt-reliability', label: '集成与运行保障', icon: '↔', description: '平台连接、密钥、同步、存储和运行健康必须可观测、可重试、可审计。',
    items: [
      { key: 'plt-integrations', label: '平台级接口与连接', path: '/admin/platform/integrations', permissionKey: 'platform.integration.view', view: 'integrations', actions: [action('integration:connection:manage', '维护接口连接', 'HIGH'), action('integration:test', '测试连接')] },
      { key: 'plt-api-access', label: 'API、密钥与 Webhook', path: '/admin/platform/api-access', permissionKey: 'platform.api.view', view: 'api-access', actions: [action('api:credential:rotate', '轮换密钥', 'HIGH'), action('webhook:redeliver', '重新投递 Webhook')] },
      { key: 'plt-operations', label: '同步任务、资源与服务健康', path: '/admin/platform/sync', permissionKey: 'platform.sync.view', view: 'sync', actions: [action('operation:job:retry', '重试运行任务', 'HIGH'), action('operation:storage:test', '测试文件存储', 'HIGH')] }
    ]
  },
  {
    key: 'plt-security', label: '安全与合规', icon: '☖', description: '平台人员分权、跨租户审计与安全策略是控制面不可绕过的底座。',
    items: [
      { key: 'plt-operator-access', label: '平台人员与职责权限', path: '/admin/platform/access', permissionKey: 'platform.access.review', view: 'access', actions: [action('platform-role:assign', '分配平台职责', 'HIGH'), action('platform-role:revoke', '回收平台职责', 'HIGH')] },
      { key: 'plt-audit', label: '跨租户审计日志', path: '/admin/platform/audit', permissionKey: 'platform.audit.view', view: 'audit', actions: [action('platform-audit:view', '查看审计'), action('platform-audit:export', '导出审计', 'HIGH')] },
      { key: 'plt-security-policy', label: '安全策略与数据留存', path: '/admin/platform/security', permissionKey: 'platform.security.view', view: 'security', actions: [action('security:policy:update', '更新安全策略', 'HIGH'), action('retention:policy:update', '更新留存策略', 'HIGH')] }
    ]
  }
]

export const PLATFORM_MANAGEMENT_ITEMS = PLATFORM_MANAGEMENT_CATALOG.flatMap((group) =>
  group.items.map((item) => ({ ...item, groupKey: group.key, groupLabel: group.label, groupDescription: group.description }))
)

export const PLATFORM_MANAGEMENT_ITEM_MAP = Object.fromEntries(
  PLATFORM_MANAGEMENT_ITEMS.map((item) => [item.key, item])
)

