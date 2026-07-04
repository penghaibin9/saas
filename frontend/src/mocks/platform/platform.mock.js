/**
 * 平台运营中心 / 集成开放中心 mock 数据（12 集成开放中心深化设计 V1.0 + 11 单模块销售设计口径）。
 * 视角：SaaS 运营方（多租户），租户学校名称均为虚构演示数据。
 * 页面禁止直接 import 本文件，必须经 modules/platform/api/platform.api.js 获取。
 * 安全底线：AppSecret / Token / 签名密钥一律仅存脱敏形态，mock 中不出现明文密钥。
 */

export const tenantBrandConfig = {
  tenantId: 'platform-operator',
  operatorName: '平台运营方（演示）',
  schoolName: '',
  platformDisplayName: '高校学生全生命周期管理平台',
  schoolLogo: '',
  schoolBadge: '',
  brandColor: '#2563eb',
  watermarkText: '平台运营数据 · 严禁外传'
}

/** 当前登录角色（mock：平台运营视角，体现与平台管理员的权限差异） */
export const currentRole = {
  userId: 'plt-u-002',
  userName: '陈立群',
  roleCode: 'PLATFORM_OPS',
  roleName: '平台运营'
}

export const dataScope = {
  scopeCode: 'REGION_EAST',
  scopeName: '负责区域（华东 12 所院校）'
}

export const permissionActions = {
  // 租户 / 学校
  createTenant: { visible: true, allowed: true, reason: '' },
  editTenant: { visible: true, allowed: true, reason: '' },
  disableTenant: { visible: true, allowed: false, reason: '停用租户需「平台管理员」角色并双人复核' },
  configTenantBrand: { visible: true, allowed: true, reason: '' },
  configTenantLicense: { visible: true, allowed: true, reason: '' },
  importTenants: { visible: true, allowed: true, reason: '' },
  exportTenants: { visible: true, allowed: true, reason: '' },
  batchRemindRenew: { visible: true, allowed: true, reason: '' },
  // 套餐
  createPackage: { visible: true, allowed: false, reason: '套餐定义需「平台管理员」角色' },
  editPackage: { visible: true, allowed: false, reason: '套餐定义需「平台管理员」角色' },
  disablePackage: { visible: true, allowed: false, reason: '停用套餐需「平台管理员」角色' },
  exportPackageConfig: { visible: true, allowed: true, reason: '' },
  // 订单 / 授权
  createOrder: { visible: true, allowed: true, reason: '' },
  editOrderRemark: { visible: true, allowed: true, reason: '' },
  voidOrder: { visible: true, allowed: false, reason: '作废订单需「平台管理员」角色' },
  activateOrder: { visible: true, allowed: true, reason: '' },
  renewOrder: { visible: true, allowed: true, reason: '' },
  exportOrders: { visible: true, allowed: true, reason: '' },
  // 集成开放
  createIntegration: { visible: true, allowed: true, reason: '' },
  editIntegration: { visible: true, allowed: true, reason: '' },
  disableIntegration: { visible: true, allowed: true, reason: '' },
  testIntegration: { visible: true, allowed: true, reason: '' },
  viewIntegrationLogs: { visible: true, allowed: true, reason: '' },
  exportIntegrations: { visible: true, allowed: true, reason: '' },
  // API / Webhook
  createApiAccess: { visible: true, allowed: true, reason: '' },
  editApiAccess: { visible: true, allowed: true, reason: '' },
  resetApiSecret: { visible: true, allowed: false, reason: '重置密钥需「平台管理员」角色并双人复核' },
  disableApiAccess: { visible: true, allowed: true, reason: '' },
  viewApiLogs: { visible: true, allowed: true, reason: '' },
  exportApiLogs: { visible: true, allowed: true, reason: '' },
  viewSecretFull: { visible: false, allowed: false, reason: '明文密钥不在任何页面展示（仅重置时一次性下发）' },
  createWebhook: { visible: true, allowed: true, reason: '' },
  editWebhook: { visible: true, allowed: true, reason: '' },
  disableWebhook: { visible: true, allowed: true, reason: '' },
  redeliverWebhook: { visible: true, allowed: true, reason: '' },
  // 同步任务 / 日志
  retrySyncTask: { visible: true, allowed: true, reason: '' },
  disableSyncTask: { visible: true, allowed: true, reason: '' },
  exportSyncLogs: { visible: true, allowed: true, reason: '' },
  viewPlatformLogs: { visible: true, allowed: true, reason: '' },
  exportPlatformLogs: { visible: true, allowed: true, reason: '' },
  deleteAuditLogs: { visible: false, allowed: false, reason: '审计日志不允许删除（平台冻结规则）' }
}

export const statusOptions = {
  tenantStatus: [
    { value: 'TRIAL', label: '试用中' },
    { value: 'ACTIVE', label: '正式有效' },
    { value: 'EXPIRING', label: '即将到期' },
    { value: 'EXPIRED', label: '已到期（锁写）' },
    { value: 'SUSPENDED', label: '已停用' }
  ],
  orderStatus: [
    { value: 'PENDING_ACTIVATE', label: '待开通' },
    { value: 'ACTIVE', label: '已开通' },
    { value: 'VOID', label: '已作废' }
  ],
  orderTypes: [
    { value: 'NEW', label: '新购' },
    { value: 'RENEW', label: '续费' },
    { value: 'UPGRADE', label: '扩容/升级' }
  ],
  integrationHealth: [
    { value: 'HEALTHY', label: '正常' },
    { value: 'WARNING', label: '警告' },
    { value: 'FAILED', label: '失败' }
  ],
  enableStatus: [
    { value: 'ENABLED', label: '启用中' },
    { value: 'DISABLED', label: '已停用' }
  ],
  syncStatus: [
    { value: 'ENABLED', label: '运行中' },
    { value: 'PAUSED', label: '已暂停' },
    { value: 'FAILED', label: '最近失败' }
  ]
}

export const filterOptions = {
  regions: [
    { value: 'EAST', label: '华东' },
    { value: 'SOUTH', label: '华南' },
    { value: 'NORTH', label: '华北' },
    { value: 'WEST', label: '西南' }
  ],
  packages: [
    { value: 'pkg-01', label: '岗位实习单模块包' },
    { value: 'pkg-02', label: '毕业设计单模块包' },
    { value: 'pkg-03', label: '实践教学组合包' },
    { value: 'pkg-04', label: '全生命周期旗舰包' }
  ],
  csOwners: [
    { value: 'cs-01', label: '苏婉（客户成功）' },
    { value: 'cs-02', label: '高翔（客户成功）' }
  ],
  integrationTypes: [
    { value: 'JW', label: '教务系统' },
    { value: 'XG', label: '学工系统' },
    { value: 'SSO', label: '统一身份认证' },
    { value: 'SMS', label: '短信平台' },
    { value: 'OSS', label: '对象存储' },
    { value: 'WXMP', label: '微信小程序平台' }
  ],
  syncObjects: [
    { value: 'STUDENT', label: '学生' },
    { value: 'TEACHER', label: '教师' },
    { value: 'ORG', label: '组织架构' },
    { value: 'ENTERPRISE', label: '企业' }
  ]
}

export const fieldColumns = {
  tenants: [
    { key: 'tenant', title: '租户 / 学校', locked: true, defaultVisible: true },
    { key: 'region', title: '区域', locked: false, defaultVisible: true },
    { key: 'packageName', title: '套餐', locked: false, defaultVisible: true },
    { key: 'usage', title: '学生数 / 上限', locked: false, defaultVisible: true },
    { key: 'expireAt', title: '到期日', locked: false, defaultVisible: true },
    { key: 'status', title: '状态', locked: false, defaultVisible: true },
    { key: 'csOwnerName', title: '客户成功', locked: false, defaultVisible: false },
    { key: 'createdAt', title: '开通时间', locked: false, defaultVisible: false },
    { key: 'actions', title: '操作', locked: true, defaultVisible: true }
  ]
}

export const batchActions = {
  tenants: [
    { key: 'batchRemindRenew', label: '批量续费提醒', permissionKey: 'batchRemindRenew' },
    { key: 'exportSelected', label: '导出所选', permissionKey: 'exportTenants' }
  ]
}

export const importTemplates = {
  tenants: {
    key: 'tenants',
    name: '租户开通导入模板',
    version: 'v1.4',
    fileName: '租户开通导入模板_v1.4.xlsx',
    fields: ['学校名称', '租户编码', '区域', '套餐编码', '学生数上限', '有效期起止', '客户成功负责人', '联系人', '联系电话'],
    rules: ['租户编码全平台唯一', '套餐编码必须已上架', '联系人手机号导入后默认脱敏', '导入仅创建「待开通」租户，正式开通需在订单授权中确认']
  }
}

export const exportOptions = {
  tenants: {
    scopes: [
      { value: 'FILTERED', label: '当前筛选结果' },
      { value: 'SELECTED', label: '仅所选记录' },
      { value: 'ALL', label: '数据范围内全部' }
    ],
    fields: [
      { key: 'name', label: '学校名称', sensitive: false, defaultChecked: true },
      { key: 'code', label: '租户编码', sensitive: false, defaultChecked: true },
      { key: 'packageName', label: '套餐', sensitive: false, defaultChecked: true },
      { key: 'expireAt', label: '到期日', sensitive: false, defaultChecked: true },
      { key: 'contact', label: '联系人电话', sensitive: true, defaultChecked: false, maskNote: '默认脱敏（139****0000）' },
      { key: 'amount', label: '合同金额', sensitive: true, defaultChecked: false, maskNote: '默认脱敏（仅区间）' }
    ],
    watermark: true,
    note: '导出文件自动附加水印（平台运营数据 · 操作人 · 时间）；联系人与金额默认脱敏，明文导出需平台管理员审批。'
  },
  orders: {
    scopes: [
      { value: 'FILTERED', label: '当前筛选结果' },
      { value: 'RANGE_90D', label: '近 90 天' }
    ],
    fields: [
      { key: 'orderNo', label: '订单号', sensitive: false, defaultChecked: true },
      { key: 'tenantName', label: '租户', sensitive: false, defaultChecked: true },
      { key: 'typeLabel', label: '类型', sensitive: false, defaultChecked: true },
      { key: 'amount', label: '金额', sensitive: true, defaultChecked: false, maskNote: '默认脱敏（仅区间）' },
      { key: 'period', label: '服务期', sensitive: false, defaultChecked: true },
      { key: 'statusLabel', label: '状态', sensitive: false, defaultChecked: true }
    ],
    watermark: true,
    note: '订单导出含水印并写入审计日志；金额字段默认脱敏为区间。'
  },
  logs: {
    scopes: [
      { value: 'FILTERED', label: '当前筛选结果' },
      { value: 'RANGE_30D', label: '近 30 天' }
    ],
    fields: [
      { key: 'time', label: '时间', sensitive: false, defaultChecked: true },
      { key: 'who', label: '操作人', sensitive: false, defaultChecked: true },
      { key: 'action', label: '动作', sensitive: false, defaultChecked: true },
      { key: 'target', label: '对象', sensitive: false, defaultChecked: true },
      { key: 'ip', label: 'IP（脱敏）', sensitive: true, defaultChecked: true, maskNote: '固定脱敏' }
    ],
    watermark: true,
    note: '平台审计日志仅支持导出，不支持删除或修改；导出动作本身写入审计日志。'
  }
}

/** 平台可售模块清单（11 冻结口径：11/12 为公共底座随任意套餐必含） */
export const moduleLicenseList = [
  { code: 'M01', name: '学生主档与身份中心', category: '底座', required: true, description: '最小学生主档，任何模块的依赖基座' },
  { code: 'M02', name: '数字迎新中心', category: '业务', required: false, description: '迎新报到 / 缴费 / 分班' },
  { code: 'M03', name: '在校服务中心', category: '业务', required: false, description: '学生服务申请与办理' },
  { code: 'M04', name: '学业过程中心', category: '业务', required: false, description: '学业预警与过程管理' },
  { code: 'M05', name: '毕业设计中心', category: '业务', required: false, description: '选题 / 开题 / 批阅 / 答辩 / 归档' },
  { code: 'M06', name: '岗位实习中心', category: '业务', required: false, description: '打卡 / 周报 / 风险 / 巡访 / 归档' },
  { code: 'M07', name: '毕业与就业中心', category: '业务', required: false, description: '就业去向与三方协议' },
  { code: 'M08A', name: '学生小程序', category: '端', required: false, description: '学生移动端入口' },
  { code: 'M08B', name: '教师移动工作台', category: '端', required: false, description: '教师移动端批阅与处理' },
  { code: 'M09', name: 'PC 管理端', category: '端', required: true, description: '管理端基座' },
  { code: 'M10', name: '数据驾驶舱', category: '增值', required: false, description: '校级 / 学院级数据洞察' },
  { code: 'M11', name: '权限与流程中心', category: '底座', required: true, description: '账号 / 角色 / 数据范围 / 审批 / 审计' },
  { code: 'M12', name: '集成开放中心', category: '底座', required: true, description: '对接 / 导入 / API / 消息 / 文件' }
]

export const packageList = [
  {
    id: 'pkg-01', name: '岗位实习单模块包', positioning: '实习就业处首购切入',
    modules: ['M01', 'M06', 'M08A', 'M08B', 'M09', 'M11', 'M12'],
    limits: { students: 3000, teachers: 300, storageGB: 100, apiQpd: 50000 },
    priceNote: '按年订阅 · 3~5 万/年（演示口径）', status: 'ENABLED', statusLabel: '上架中', tenantCount: 3, updatedAt: '2026-05-20'
  },
  {
    id: 'pkg-02', name: '毕业设计单模块包', positioning: '教务处毕设管理切入',
    modules: ['M01', 'M05', 'M08A', 'M08B', 'M09', 'M11', 'M12'],
    limits: { students: 3000, teachers: 300, storageGB: 200, apiQpd: 50000 },
    priceNote: '按年订阅 · 3~5 万/年（演示口径）', status: 'ENABLED', statusLabel: '上架中', tenantCount: 1, updatedAt: '2026-05-20'
  },
  {
    id: 'pkg-03', name: '实践教学组合包', positioning: '毕设 + 实习 + 驾驶舱组合',
    modules: ['M01', 'M05', 'M06', 'M08A', 'M08B', 'M09', 'M10', 'M11', 'M12'],
    limits: { students: 8000, teachers: 800, storageGB: 500, apiQpd: 200000 },
    priceNote: '按年订阅 · 8~12 万/年（演示口径）', status: 'ENABLED', statusLabel: '上架中', tenantCount: 2, updatedAt: '2026-06-11'
  },
  {
    id: 'pkg-04', name: '全生命周期旗舰包', positioning: '01–12 全中心 + 专属实施',
    modules: ['M01', 'M02', 'M03', 'M04', 'M05', 'M06', 'M07', 'M08A', 'M08B', 'M09', 'M10', 'M11', 'M12'],
    limits: { students: 20000, teachers: 2000, storageGB: 2048, apiQpd: 1000000 },
    priceNote: '按年订阅 · 20 万+/年（演示口径）', status: 'ENABLED', statusLabel: '上架中', tenantCount: 2, updatedAt: '2026-06-11'
  }
]

export const packageDetailMap = {
  'pkg-03': {
    id: 'pkg-03',
    auditTrail: [
      { who: '平台管理员 · 罗一舟', time: '2026-06-11 14:20', action: '调整套餐限制', affected: '存储 300GB → 500GB（随对象存储降价）' },
      { who: '平台管理员 · 罗一舟', time: '2026-02-01 09:00', action: '套餐上架', affected: '含 9 个模块' }
    ]
  }
}

export const tenantList = [
  {
    id: 'tenant-demo-a', code: 'DEMO-A', name: '演示职业技术学院', region: 'EAST', regionLabel: '华东',
    packageId: 'pkg-04', packageName: '全生命周期旗舰包', moduleCount: 13,
    studentCount: 12800, studentLimit: 20000, teacherCount: 860,
    expireAt: '2027-03-01', status: 'ACTIVE', statusLabel: '正式有效',
    csOwner: 'cs-01', csOwnerName: '苏婉', contactName: '周文彬', contactPhone: '13812340101', createdAt: '2025-03-01'
  },
  {
    id: 'tenant-02', code: 'JC-GC', name: '江城工程职业学院（演示）', region: 'EAST', regionLabel: '华东',
    packageId: 'pkg-03', packageName: '实践教学组合包', moduleCount: 9,
    studentCount: 6200, studentLimit: 8000, teacherCount: 420,
    expireAt: '2026-07-28', status: 'EXPIRING', statusLabel: '即将到期',
    csOwner: 'cs-01', csOwnerName: '苏婉', contactName: '林处长', contactPhone: '13912340202', createdAt: '2025-07-28'
  },
  {
    id: 'tenant-03', code: 'BH-XX', name: '滨湖信息职业技术学院（演示）', region: 'EAST', regionLabel: '华东',
    packageId: 'pkg-01', packageName: '岗位实习单模块包', moduleCount: 7,
    studentCount: 2400, studentLimit: 3000, teacherCount: 180,
    expireAt: '2027-01-15', status: 'ACTIVE', statusLabel: '正式有效',
    csOwner: 'cs-02', csOwnerName: '高翔', contactName: '王老师', contactPhone: '13712340303', createdAt: '2026-01-15'
  },
  {
    id: 'tenant-04', code: 'YL-SM', name: '云岭商贸职业学院（演示）', region: 'WEST', regionLabel: '西南',
    packageId: 'pkg-01', packageName: '岗位实习单模块包', moduleCount: 7,
    studentCount: 980, studentLimit: 3000, teacherCount: 96,
    expireAt: '2026-08-10', status: 'TRIAL', statusLabel: '试用中',
    csOwner: 'cs-02', csOwnerName: '高翔', contactName: '陈主任', contactPhone: '15012340404', createdAt: '2026-05-10'
  },
  {
    id: 'tenant-05', code: 'QY-JD', name: '青阳机电职业技术学院（演示）', region: 'EAST', regionLabel: '华东',
    packageId: 'pkg-02', packageName: '毕业设计单模块包', moduleCount: 7,
    studentCount: 2100, studentLimit: 3000, teacherCount: 150,
    expireAt: '2026-06-20', status: 'EXPIRED', statusLabel: '已到期（锁写）',
    csOwner: 'cs-01', csOwnerName: '苏婉', contactName: '刘老师', contactPhone: '13312340505', createdAt: '2025-06-20'
  },
  {
    id: 'tenant-06', code: 'LG-JT', name: '临港交通职业学院（演示）', region: 'EAST', regionLabel: '华东',
    packageId: 'pkg-03', packageName: '实践教学组合包', moduleCount: 9,
    studentCount: 5100, studentLimit: 8000, teacherCount: 350,
    expireAt: '2027-05-30', status: 'ACTIVE', statusLabel: '正式有效',
    csOwner: 'cs-01', csOwnerName: '苏婉', contactName: '张处长', contactPhone: '18612340606', createdAt: '2026-05-30'
  },
  {
    id: 'tenant-07', code: 'LZ-WS', name: '鹭洲卫生健康职业学院（演示）', region: 'SOUTH', regionLabel: '华南',
    packageId: 'pkg-04', packageName: '全生命周期旗舰包', moduleCount: 13,
    studentCount: 9400, studentLimit: 20000, teacherCount: 610,
    expireAt: '2027-09-01', status: 'ACTIVE', statusLabel: '正式有效',
    csOwner: 'cs-02', csOwnerName: '高翔', contactName: '黄科长', contactPhone: '13112340707', createdAt: '2025-09-01'
  },
  {
    id: 'tenant-08', code: 'SL-NL', name: '示例农林职业学院（演示）', region: 'NORTH', regionLabel: '华北',
    packageId: 'pkg-02', packageName: '毕业设计单模块包', moduleCount: 7,
    studentCount: 0, studentLimit: 3000, teacherCount: 0,
    expireAt: '—', status: 'SUSPENDED', statusLabel: '已停用',
    csOwner: 'cs-02', csOwnerName: '高翔', contactName: '赵老师', contactPhone: '15912340808', createdAt: '2024-09-01'
  }
]

export const tenantDetailMap = {
  'tenant-02': {
    id: 'tenant-02', code: 'JC-GC', name: '江城工程职业学院（演示）', regionLabel: '华东',
    status: 'EXPIRING', statusLabel: '即将到期', expireAt: '2026-07-28', remainDays: 24,
    packageId: 'pkg-03', packageName: '实践教学组合包',
    csOwnerName: '苏婉', implOwnerName: '孟凡（实施）', contactName: '林处长', contactPhone: '13912340202',
    usage: { students: '6,200 / 8,000', teachers: '420 / 800', storage: '212 GB / 500 GB', apiToday: '18,420 / 200,000' },
    brand: {
      schoolName: '江城工程职业学院（演示）', schoolShortName: '江城工院',
      brandColor: '#0e7490', loginSlogan: '工学并进，知行合一',
      watermarkText: '江城工程职业学院 · 内部数据', footerText: '技术支持：{{platformDisplayName}}'
    },
    moduleLicenses: [
      { code: 'M01', name: '学生主档与身份中心', enabled: true, locked: true, expireAt: '2026-07-28' },
      { code: 'M05', name: '毕业设计中心', enabled: true, locked: false, expireAt: '2026-07-28' },
      { code: 'M06', name: '岗位实习中心', enabled: true, locked: false, expireAt: '2026-07-28' },
      { code: 'M08A', name: '学生小程序', enabled: true, locked: false, expireAt: '2026-07-28' },
      { code: 'M08B', name: '教师移动工作台', enabled: true, locked: false, expireAt: '2026-07-28' },
      { code: 'M09', name: 'PC 管理端', enabled: true, locked: true, expireAt: '2026-07-28' },
      { code: 'M10', name: '数据驾驶舱', enabled: false, locked: false, expireAt: '—' },
      { code: 'M11', name: '权限与流程中心', enabled: true, locked: true, expireAt: '2026-07-28' },
      { code: 'M12', name: '集成开放中心', enabled: true, locked: true, expireAt: '2026-07-28' }
    ],
    orders: [
      { orderNo: 'ORD-20250728-011', typeLabel: '新购', packageName: '实践教学组合包', period: '2025-07-28 ~ 2026-07-28', statusLabel: '已开通' }
    ],
    auditTrail: [
      { who: '苏婉 · 客户成功', time: '2026-07-01 10:12', action: '发送续费提醒', affected: '短信 + 站内信触达租户管理员，30 天倒计时' },
      { who: '陈立群 · 平台运营', time: '2026-06-15 16:40', action: '关闭模块「数据驾驶舱」试用', affected: '试用期结束未转正，按策略降级为不可见' },
      { who: '孟凡 · 实施', time: '2025-08-02 09:30', action: '完成初始化', affected: '组织 / 学生 / 教师三类数据首次同步完成' }
    ]
  }
}

export const orderList = [
  {
    id: 'ord-001', orderNo: 'ORD-20260701-031', tenantId: 'tenant-02', tenantName: '江城工程职业学院（演示）',
    type: 'RENEW', typeLabel: '续费', packageName: '实践教学组合包', amountMasked: '¥ 8~12 万（脱敏）',
    period: '2026-07-28 ~ 2027-07-28', status: 'PENDING_ACTIVATE', statusLabel: '待开通',
    createdAt: '2026-07-01', createdBy: '苏婉', remark: '续费合同走款中，到账后开通'
  },
  {
    id: 'ord-002', orderNo: 'ORD-20260530-027', tenantId: 'tenant-06', tenantName: '临港交通职业学院（演示）',
    type: 'NEW', typeLabel: '新购', packageName: '实践教学组合包', amountMasked: '¥ 8~12 万（脱敏）',
    period: '2026-05-30 ~ 2027-05-30', status: 'ACTIVE', statusLabel: '已开通',
    createdAt: '2026-05-28', createdBy: '陈立群', remark: ''
  },
  {
    id: 'ord-003', orderNo: 'ORD-20260510-024', tenantId: 'tenant-04', tenantName: '云岭商贸职业学院（演示）',
    type: 'NEW', typeLabel: '新购（试用转化中）', packageName: '岗位实习单模块包', amountMasked: '¥ 0（试用）',
    period: '2026-05-10 ~ 2026-08-10', status: 'ACTIVE', statusLabel: '已开通',
    createdAt: '2026-05-10', createdBy: '高翔', remark: '90 天试用，8 月评估转正'
  },
  {
    id: 'ord-004', orderNo: 'ORD-20260420-019', tenantId: 'tenant-05', tenantName: '青阳机电职业技术学院（演示）',
    type: 'RENEW', typeLabel: '续费', packageName: '毕业设计单模块包', amountMasked: '¥ 3~5 万（脱敏）',
    period: '2026-06-20 ~ 2027-06-20', status: 'VOID', statusLabel: '已作废',
    createdAt: '2026-04-20', createdBy: '苏婉', remark: '作废原因：学校预算未批复，租户已按到期锁写'
  },
  {
    id: 'ord-005', orderNo: 'ORD-20260115-008', tenantId: 'tenant-03', tenantName: '滨湖信息职业技术学院（演示）',
    type: 'NEW', typeLabel: '新购', packageName: '岗位实习单模块包', amountMasked: '¥ 3~5 万（脱敏）',
    period: '2026-01-15 ~ 2027-01-15', status: 'ACTIVE', statusLabel: '已开通',
    createdAt: '2026-01-12', createdBy: '高翔', remark: ''
  },
  {
    id: 'ord-006', orderNo: 'ORD-20250901-003', tenantId: 'tenant-07', tenantName: '鹭洲卫生健康职业学院（演示）',
    type: 'UPGRADE', typeLabel: '扩容/升级', packageName: '全生命周期旗舰包', amountMasked: '¥ 20 万+（脱敏）',
    period: '2025-09-01 ~ 2027-09-01', status: 'ACTIVE', statusLabel: '已开通',
    createdAt: '2025-08-25', createdBy: '陈立群', remark: '由实践教学包升级，补差价'
  }
]

export const orderDetailMap = {
  'ord-001': {
    id: 'ord-001',
    auditTrail: [
      { who: '苏婉 · 客户成功', time: '2026-07-01 10:30', action: '创建续费订单', affected: '关联租户 JC-GC · 待合同款到账' },
      { who: '系统', time: '2026-06-28 08:00', action: '到期提醒触发', affected: '30 天倒计时提醒已发送客户成功与租户管理员' }
    ]
  }
}

/** 授权记录（模块级开通/关停/续期流水） */
export const authorizationList = [
  { id: 'auth-001', tenantName: '江城工程职业学院（演示）', moduleName: '数据驾驶舱', actionLabel: '关闭试用', validUntil: '—', operator: '陈立群', time: '2026-06-15 16:40' },
  { id: 'auth-002', tenantName: '临港交通职业学院（演示）', moduleName: '实践教学组合包（9 模块）', actionLabel: '整包开通', validUntil: '2027-05-30', operator: '陈立群', time: '2026-05-30 09:00' },
  { id: 'auth-003', tenantName: '云岭商贸职业学院（演示）', moduleName: '岗位实习单模块包（7 模块）', actionLabel: '试用开通', validUntil: '2026-08-10', operator: '高翔', time: '2026-05-10 14:20' },
  { id: 'auth-004', tenantName: '青阳机电职业技术学院（演示）', moduleName: '毕业设计单模块包', actionLabel: '到期锁写', validUntil: '2026-06-20', operator: '系统', time: '2026-06-21 00:05' }
]

export const integrationList = [
  {
    id: 'itg-001', name: '教务系统对接', tenantId: 'tenant-demo-a', tenantName: '演示职业技术学院',
    type: 'JW', typeLabel: '教务系统', authType: 'AppKey + 签名', health: 'HEALTHY', healthLabel: '正常',
    todayCalls: 4210, failCalls: 0, lastCallAt: '2026-07-04 10:40', owner: '孟凡（实施）',
    status: 'ENABLED', statusLabel: '启用中'
  },
  {
    id: 'itg-002', name: '统一身份认证（CAS）', tenantId: 'tenant-demo-a', tenantName: '演示职业技术学院',
    type: 'SSO', typeLabel: '统一身份认证', authType: 'OAuth2 / OIDC', health: 'HEALTHY', healthLabel: '正常',
    todayCalls: 1863, failCalls: 2, lastCallAt: '2026-07-04 10:38', owner: '孟凡（实施）',
    status: 'ENABLED', statusLabel: '启用中'
  },
  {
    id: 'itg-003', name: '学工系统对接', tenantId: 'tenant-02', tenantName: '江城工程职业学院（演示）',
    type: 'XG', typeLabel: '学工系统', authType: 'AppKey + 签名', health: 'WARNING', healthLabel: '警告',
    todayCalls: 960, failCalls: 41, lastCallAt: '2026-07-04 10:12', owner: '孟凡（实施）',
    status: 'ENABLED', statusLabel: '启用中'
  },
  {
    id: 'itg-004', name: '短信平台', tenantId: 'platform-operator', tenantName: '平台公共通道',
    type: 'SMS', typeLabel: '短信平台', authType: 'AppKey + Secret', health: 'HEALTHY', healthLabel: '正常',
    todayCalls: 2304, failCalls: 6, lastCallAt: '2026-07-04 10:41', owner: '平台运维',
    status: 'ENABLED', statusLabel: '启用中'
  },
  {
    id: 'itg-005', name: '对象存储（OSS）', tenantId: 'platform-operator', tenantName: '平台公共通道',
    type: 'OSS', typeLabel: '对象存储', authType: 'AccessKey（已加密）', health: 'HEALTHY', healthLabel: '正常',
    todayCalls: 18760, failCalls: 0, lastCallAt: '2026-07-04 10:41', owner: '平台运维',
    status: 'ENABLED', statusLabel: '启用中'
  },
  {
    id: 'itg-006', name: '旧就业数据平台', tenantId: 'tenant-05', tenantName: '青阳机电职业技术学院（演示）',
    type: 'XG', typeLabel: '学工系统', authType: 'AppKey + 签名', health: 'FAILED', healthLabel: '失败',
    todayCalls: 0, failCalls: 12, lastCallAt: '2026-07-03 22:00', owner: '孟凡（实施）',
    status: 'DISABLED', statusLabel: '已停用'
  }
]

export const integrationDetailMap = {
  'itg-003': {
    id: 'itg-003', name: '学工系统对接', tenantName: '江城工程职业学院（演示）', typeLabel: '学工系统',
    endpoint: 'https://xg.jcgc-demo.edu.cn/api（演示地址）', authType: 'AppKey + 签名',
    appKeyMasked: 'AK-7fd2****93aa', secretMasked: '••••••••（已加密存储，页面不展示明文）',
    ipWhitelist: ['10.24.*.*', '112.80.*.*'], signAlg: 'HMAC-SHA256', timeoutMs: 5000,
    healthChecks: [
      { item: '网络连通性', result: 'HEALTHY', resultLabel: '正常', detail: '平均耗时 86ms' },
      { item: '认证有效性', result: 'HEALTHY', resultLabel: '正常', detail: 'Token 有效期剩余 21 天' },
      { item: '接口响应', result: 'WARNING', resultLabel: '警告', detail: '学生接口错误率 4.1%（阈值 1%）' },
      { item: '字段格式', result: 'WARNING', resultLabel: '警告', detail: '字段 dept_name 出现未映射新值 3 个' }
    ],
    recentErrors: [
      { time: '2026-07-04 10:02', codeText: 'FIELD_MAPPING_MISS', message: 'dept_name=「智慧建造学院」未配置映射，41 行进入暂存区待处理' },
      { time: '2026-07-03 22:10', codeText: 'TIMEOUT', message: '学生接口超时 2 次，已自动重试成功' }
    ],
    auditTrail: [
      { who: '孟凡 · 实施', time: '2026-07-04 10:20', action: '执行健康检查', affected: '结果：警告（字段映射缺失）' },
      { who: '陈立群 · 平台运营', time: '2026-06-30 15:00', action: '编辑集成配置', affected: '超时时间 3000ms → 5000ms' }
    ]
  }
}

export const apiAccessList = [
  {
    id: 'api-001', appName: '教务系统（读学生）', tenantName: '演示职业技术学院',
    appKeyMasked: 'AK-2f8e****91c3', secretMasked: '••••••••（已加密存储）',
    apiScopes: ['student:read', 'org:read'], dataScopeLabel: '本校学生基础字段（脱敏档）',
    ipWhitelist: '10.24.*.*', validUntil: '2027-03-01', todayCalls: 4210, status: 'ENABLED', statusLabel: '启用中'
  },
  {
    id: 'api-002', appName: '省就业监测平台', tenantName: '演示职业技术学院',
    appKeyMasked: 'AK-9c17****devo', secretMasked: '••••••••（已加密存储）',
    apiScopes: ['employment:read'], dataScopeLabel: '就业去向汇总数（无个人明细）',
    ipWhitelist: '58.213.*.*', validUntil: '2026-12-31', todayCalls: 120, status: 'ENABLED', statusLabel: '启用中'
  },
  {
    id: 'api-003', appName: '江城工院数据中台', tenantName: '江城工程职业学院（演示）',
    appKeyMasked: 'AK-5ab0****3d7f', secretMasked: '••••••••（已加密存储）',
    apiScopes: ['student:read', 'intern:read'], dataScopeLabel: '本校实习过程数据（脱敏档）',
    ipWhitelist: '112.80.*.*', validUntil: '2026-07-28', todayCalls: 986, status: 'ENABLED', statusLabel: '启用中'
  },
  {
    id: 'api-004', appName: '旧报表工具（已停用）', tenantName: '青阳机电职业技术学院（演示）',
    appKeyMasked: 'AK-11f4****c2e8', secretMasked: '••••••••（已加密存储）',
    apiScopes: ['gd:read'], dataScopeLabel: '毕设汇总数',
    ipWhitelist: '—', validUntil: '2026-06-20', todayCalls: 0, status: 'DISABLED', statusLabel: '已停用'
  }
]

export const apiCallLogs = [
  { id: 'acl-001', time: '2026-07-04 10:40:12', appName: '教务系统（读学生）', api: 'GET /open/v1/students', status: 200, costMs: 84, resultLabel: '成功' },
  { id: 'acl-002', time: '2026-07-04 10:38:03', appName: '江城工院数据中台', api: 'GET /open/v1/intern/checkins', status: 200, costMs: 132, resultLabel: '成功' },
  { id: 'acl-003', time: '2026-07-04 10:21:44', appName: '省就业监测平台', api: 'GET /open/v1/employment/summary', status: 429, costMs: 3, resultLabel: '限流拦截' },
  { id: 'acl-004', time: '2026-07-04 09:58:20', appName: '江城工院数据中台', api: 'GET /open/v1/students', status: 403, costMs: 5, resultLabel: '越权拦截（数据范围外字段）' }
]

export const webhookList = [
  {
    id: 'wh-001', name: '实习风险事件推送', tenantName: '演示职业技术学院',
    urlMasked: 'https://jw.demo.edu.cn/hook/****', events: ['intern.risk.created', 'intern.checkin.abnormal'],
    signKeyMasked: 'SK-****（已加密存储）', retryPolicy: '指数退避 · 最多 5 次',
    lastDelivery: '2026-07-04 09:41 · 成功', failCount24h: 0, status: 'ENABLED', statusLabel: '启用中'
  },
  {
    id: 'wh-002', name: '毕设归档事件推送', tenantName: '演示职业技术学院',
    urlMasked: 'https://archive.demo.edu.cn/hook/****', events: ['gd.final.archived'],
    signKeyMasked: 'SK-****（已加密存储）', retryPolicy: '指数退避 · 最多 5 次',
    lastDelivery: '2026-07-02 18:20 · 成功', failCount24h: 0, status: 'ENABLED', statusLabel: '启用中'
  },
  {
    id: 'wh-003', name: '学工系统学生异动订阅', tenantName: '江城工程职业学院（演示）',
    urlMasked: 'https://xg.jcgc-demo.edu.cn/hook/****', events: ['student.status.changed'],
    signKeyMasked: 'SK-****（已加密存储）', retryPolicy: '固定间隔 5 分钟 · 最多 3 次',
    lastDelivery: '2026-07-04 08:00 · 失败（HTTP 502）', failCount24h: 6, status: 'ENABLED', statusLabel: '启用中'
  }
]

export const syncTaskList = [
  {
    id: 'sync-001', name: '学生主档增量同步', tenantName: '演示职业技术学院', source: '教务系统对接',
    object: 'STUDENT', objectLabel: '学生', schedule: '每日 02:00', lastRunAt: '2026-07-04 02:00',
    lastResult: '成功 12,742 行 · 失败 0', successRows: 12742, failRows: 0, status: 'ENABLED', statusLabel: '运行中'
  },
  {
    id: 'sync-002', name: '组织架构全量同步', tenantName: '演示职业技术学院', source: '教务系统对接',
    object: 'ORG', objectLabel: '组织架构', schedule: '每周一 01:00', lastRunAt: '2026-06-29 01:00',
    lastResult: '成功 386 行 · 失败 0', successRows: 386, failRows: 0, status: 'ENABLED', statusLabel: '运行中'
  },
  {
    id: 'sync-003', name: '学生主档增量同步', tenantName: '江城工程职业学院（演示）', source: '学工系统对接',
    object: 'STUDENT', objectLabel: '学生', schedule: '每日 02:30', lastRunAt: '2026-07-04 02:30',
    lastResult: '成功 6,159 行 · 失败 41（字段映射缺失）', successRows: 6159, failRows: 41, status: 'FAILED', statusLabel: '最近失败'
  },
  {
    id: 'sync-004', name: '教师账号同步', tenantName: '滨湖信息职业技术学院（演示）', source: '统一身份认证',
    object: 'TEACHER', objectLabel: '教师', schedule: '每日 03:00', lastRunAt: '2026-07-04 03:00',
    lastResult: '成功 182 行 · 失败 0', successRows: 182, failRows: 0, status: 'ENABLED', statusLabel: '运行中'
  },
  {
    id: 'sync-005', name: '合作企业同步（已暂停）', tenantName: '青阳机电职业技术学院（演示）', source: '旧就业数据平台',
    object: 'ENTERPRISE', objectLabel: '企业', schedule: '每日 04:00', lastRunAt: '2026-06-20 04:00',
    lastResult: '租户到期锁写，任务已暂停', successRows: 0, failRows: 0, status: 'PAUSED', statusLabel: '已暂停'
  }
]

export const syncTaskDetailMap = {
  'sync-003': {
    id: 'sync-003', name: '学生主档增量同步', tenantName: '江城工程职业学院（演示）',
    source: '学工系统对接', objectLabel: '学生', schedule: '每日 02:30', batchNo: 'SYNC-20260704-0230',
    flow: '外部系统 → 字段映射 → 暂存区 → 校验 → 身份匹配 → 业务表写入 → 日志',
    runs: [
      { time: '2026-07-04 02:30', resultLabel: '部分失败', detail: '成功 6,159 · 失败 41（FIELD_MAPPING_MISS）', tone: 'danger' },
      { time: '2026-07-03 02:30', resultLabel: '成功', detail: '成功 6,148 · 失败 0', tone: 'success' },
      { time: '2026-07-02 02:30', resultLabel: '成功', detail: '成功 6,140 · 失败 0', tone: 'success' }
    ],
    failedRows: [
      { row: 'stu_no=2024****117', field: 'dept_name', message: '「智慧建造学院」未配置映射，暂存区待处理' },
      { row: 'stu_no=2024****233', field: 'dept_name', message: '「智慧建造学院」未配置映射，暂存区待处理' },
      { row: 'stu_no=2025****009', field: 'class', message: '班级编码为空，校验失败' }
    ],
    suggestion: '请在「字段映射」中为 dept_name 新值「智慧建造学院」补充映射后重试；重试仅处理失败行（幂等）。',
    auditTrail: [
      { who: '系统', time: '2026-07-04 02:31', action: '同步部分失败', affected: '41 行进入暂存区，已生成告警' },
      { who: '孟凡 · 实施', time: '2026-07-04 09:15', action: '领取处理', affected: '排查为学校新设学院未同步映射表' }
    ]
  }
}

export const platformOperationLogs = [
  {
    id: 'pol-001', time: '2026-07-04 10:20', who: '孟凡', roleName: '实施人员', module: 'INTEGRATION', moduleLabel: '集成开放',
    action: 'TEST', actionLabel: '测试连接', target: '学工系统对接（江城工院）', result: 'SUCCESS', resultLabel: '成功', ip: '172.16.*.*',
    detail: { summary: '健康检查：警告（字段映射缺失）', before: '', after: '', reason: '' }
  },
  {
    id: 'pol-002', time: '2026-07-01 10:30', who: '苏婉', roleName: '客户成功', module: 'ORDER', moduleLabel: '订单授权',
    action: 'CREATE', actionLabel: '新增', target: '续费订单 ORD-20260701-031', result: 'SUCCESS', resultLabel: '成功', ip: '172.16.*.*',
    detail: { summary: '江城工院续费一年，待款项确认后开通', before: '', after: '', reason: '' }
  },
  {
    id: 'pol-003', time: '2026-06-30 15:00', who: '陈立群', roleName: '平台运营', module: 'INTEGRATION', moduleLabel: '集成开放',
    action: 'CONFIG', actionLabel: '配置变更', target: '学工系统对接（江城工院）', result: 'SUCCESS', resultLabel: '成功', ip: '172.16.*.*',
    detail: { summary: '调整超时时间', before: '3000ms', after: '5000ms', reason: '学校内网高峰期响应慢' }
  },
  {
    id: 'pol-004', time: '2026-06-21 00:05', who: '系统', roleName: '自动任务', module: 'TENANT', moduleLabel: '租户授权',
    action: 'DISABLE', actionLabel: '到期锁写', target: '青阳机电职业技术学院（演示）', result: 'SUCCESS', resultLabel: '成功', ip: '—',
    detail: { summary: '租户到期自动锁写：菜单灰显、新增拦截、历史可读、可导出', before: '正式有效', after: '已到期（锁写）', reason: '合同到期未续费' }
  },
  {
    id: 'pol-005', time: '2026-06-15 16:40', who: '陈立群', roleName: '平台运营', module: 'TENANT', moduleLabel: '租户授权',
    action: 'GRANT', actionLabel: '授权变更', target: '江城工院 · 数据驾驶舱', result: 'SUCCESS', resultLabel: '成功', ip: '172.16.*.*',
    detail: { summary: '关闭模块试用', before: '试用中', after: '不可见', reason: '试用期结束未转正' }
  },
  {
    id: 'pol-006', time: '2026-06-10 11:02', who: '高翔', roleName: '客户成功', module: 'EXPORT', moduleLabel: '导入导出',
    action: 'EXPORT', actionLabel: '导出', target: '租户清单（华南区）', result: 'SUCCESS', resultLabel: '成功', ip: '172.16.*.*',
    detail: { summary: '导出 2 条（联系人已脱敏 · 含水印）', before: '', after: '', reason: '季度复盘' }
  }
]

export const dashboardSummary = {
  stats: [
    { label: '在营租户', value: '7', trend: '正式 5 · 试用 1 · 到期 1', trendQuality: 'neutral' },
    { label: '30 天内到期', value: '1', trend: '江城工院 07-28 到期', trendQuality: 'bad' },
    { label: '本月新增订单', value: '1', trend: '续费 1 · 新购 0', trendQuality: 'neutral' },
    { label: '覆盖学生数', value: '3.9 万', trend: '▲ 6.1% 较上月', trendQuality: 'good' },
    { label: 'API 今日调用', value: '2.8 万', trend: '成功率 99.2%', trendQuality: 'good' },
    { label: '同步失败任务', value: '1', trend: '41 行待人工处理', trendQuality: 'bad' }
  ],
  renewals: [
    { id: 'rn-1', tenantId: 'tenant-02', tenantName: '江城工程职业学院（演示）', packageName: '实践教学组合包', expireAt: '2026-07-28', remainDays: 24, csOwnerName: '苏婉', hasPendingOrder: true },
    { id: 'rn-2', tenantId: 'tenant-04', tenantName: '云岭商贸职业学院（演示）', packageName: '岗位实习单模块包（试用）', expireAt: '2026-08-10', remainDays: 37, csOwnerName: '高翔', hasPendingOrder: false }
  ],
  integrationAlerts: [
    { id: 'ia-1', level: 'HIGH', title: '同步任务部分失败', detail: '江城工院学生同步 41 行字段映射缺失，已入暂存区', time: '今天 02:31' },
    { id: 'ia-2', level: 'MEDIUM', title: 'Webhook 投递失败', detail: '江城工院学生异动订阅 24h 内失败 6 次（HTTP 502）', time: '今天 08:00' },
    { id: 'ia-3', level: 'MEDIUM', title: 'API 限流触发', detail: '省就业监测平台触发限流 1 次，已按策略拦截', time: '今天 10:21' }
  ],
  recentOps: [
    { id: 'po-1', who: '孟凡 · 实施人员', action: '学工系统健康检查（警告：字段映射缺失）', time: '今天 10:20' },
    { id: 'po-2', who: '苏婉 · 客户成功', action: '创建江城工院续费订单（待开通）', time: '07-01 10:30' },
    { id: 'po-3', who: '系统', action: '青阳机电到期自动锁写（历史可读可导出）', time: '06-21 00:05' }
  ]
}

/** 审计留痕（通用追加区，页面动作实时 push） */
export const auditLogs = [
  { id: 'pau-001', who: '陈立群 · 平台运营', time: '2026-07-04 10:00', action: '查看租户详情（江城工院）', affected: '含品牌与授权配置，只读' }
]
