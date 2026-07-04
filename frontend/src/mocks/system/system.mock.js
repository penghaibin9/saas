/**
 * 系统管理中心 mock 数据（11 权限与流程中心深化设计 V1.0 口径）。
 * 世界观与 mocks/db.js 一致（演示职业技术学院 / tenant-demo-a）。
 * 页面禁止直接 import 本文件，必须经 modules/system/api/system.api.js 获取。
 * 说明：所有姓名 / 学校 / 手机号 / 账号均为演示数据，运行时由租户配置与登录态注入。
 */

export const tenantBrandConfig = {
  tenantId: 'tenant-demo-a',
  schoolName: '演示职业技术学院',
  platformDisplayName: '高校学生全生命周期管理平台',
  schoolLogo: '',
  schoolBadge: '',
  brandColor: '#2563eb',
  watermarkText: '演示职业技术学院 · 内部数据'
}

/** 当前登录角色（mock：学校系统管理员视角，用于体现权限差异） */
export const currentRole = {
  userId: 'sys-u-001',
  userName: '周文彬',
  roleCode: 'SCHOOL_ADMIN',
  roleName: '学校管理员'
}

export const dataScope = {
  scopeCode: 'SCHOOL',
  scopeName: '本校（全部院系）'
}

/**
 * 权限动作表：allowed=false 且 visible=true → 按钮置灰并提示 reason；
 * visible=false → 按钮不渲染（涉密/平台级入口）。
 */
export const permissionActions = {
  // 用户账号
  createUser: { visible: true, allowed: true, reason: '' },
  editUser: { visible: true, allowed: true, reason: '' },
  disableUser: { visible: true, allowed: true, reason: '' },
  resetPassword: { visible: true, allowed: true, reason: '' },
  assignRole: { visible: true, allowed: true, reason: '' },
  importUsers: { visible: true, allowed: true, reason: '' },
  exportUsers: { visible: true, allowed: true, reason: '' },
  batchDisableUsers: { visible: true, allowed: true, reason: '' },
  viewSensitiveFull: { visible: true, allowed: false, reason: '查看完整敏感字段需「审计人员」授权，操作将被记录' },
  // 角色权限
  createRole: { visible: true, allowed: true, reason: '' },
  editRole: { visible: true, allowed: true, reason: '' },
  copyRole: { visible: true, allowed: true, reason: '' },
  deprecateRole: { visible: true, allowed: true, reason: '' },
  configRolePermission: { visible: true, allowed: true, reason: '' },
  configRoleScope: { visible: true, allowed: true, reason: '' },
  exportRoleConfig: { visible: true, allowed: true, reason: '' },
  // 菜单权限
  createMenu: { visible: true, allowed: false, reason: '菜单结构调整需「系统管理员」角色' },
  editMenu: { visible: true, allowed: false, reason: '菜单结构调整需「系统管理员」角色' },
  disableMenu: { visible: true, allowed: false, reason: '停用菜单需「系统管理员」角色' },
  configMenuButtons: { visible: true, allowed: true, reason: '' },
  previewRoleMenu: { visible: true, allowed: true, reason: '' },
  // 数据范围
  createScopeRule: { visible: true, allowed: true, reason: '' },
  editScopeRule: { visible: true, allowed: true, reason: '' },
  deprecateScopeRule: { visible: true, allowed: true, reason: '' },
  viewScopeAffected: { visible: true, allowed: true, reason: '' },
  exportScopeRules: { visible: true, allowed: true, reason: '' },
  // 组织结构
  createOrg: { visible: true, allowed: true, reason: '' },
  editOrg: { visible: true, allowed: true, reason: '' },
  deprecateOrg: { visible: true, allowed: true, reason: '' },
  importOrg: { visible: true, allowed: true, reason: '' },
  exportOrg: { visible: true, allowed: true, reason: '' },
  // 系统配置 / 品牌配置
  editBrandConfig: { visible: true, allowed: true, reason: '' },
  resetBrandConfig: { visible: true, allowed: false, reason: '恢复默认品牌需「系统管理员」角色并二次确认' },
  exportBrandConfig: { visible: true, allowed: true, reason: '' },
  editSystemConfig: { visible: true, allowed: true, reason: '' },
  restoreConfigDefault: { visible: true, allowed: false, reason: '恢复默认配置需「系统管理员」角色并二次确认' },
  exportSystemConfig: { visible: true, allowed: true, reason: '' },
  // 日志
  viewLoginLogs: { visible: true, allowed: true, reason: '' },
  viewOperationLogs: { visible: true, allowed: true, reason: '' },
  exportLogs: { visible: true, allowed: true, reason: '' },
  deleteAuditLogs: { visible: false, allowed: false, reason: '审计日志不允许删除（平台冻结规则）' },
  // 平台级入口（学校侧不可见）
  managePlatformTenants: { visible: false, allowed: false, reason: '租户管理为平台运营侧能力' }
}

export const statusOptions = {
  userStatus: [
    { value: 'ACTIVE', label: '启用中' },
    { value: 'DISABLED', label: '已停用' },
    { value: 'LOCKED', label: '已锁定' },
    { value: 'PENDING', label: '待激活' }
  ],
  roleStatus: [
    { value: 'ENABLED', label: '启用中' },
    { value: 'DEPRECATED', label: '已作废' }
  ],
  roleType: [
    { value: 'BUILTIN', label: '内置角色' },
    { value: 'CUSTOM', label: '自定义角色' }
  ],
  menuStatus: [
    { value: 'ENABLED', label: '启用' },
    { value: 'DISABLED', label: '停用' }
  ],
  ruleStatus: [
    { value: 'ENABLED', label: '启用中' },
    { value: 'DEPRECATED', label: '已作废' }
  ],
  loginResult: [
    { value: 'SUCCESS', label: '成功' },
    { value: 'FAILED', label: '失败' },
    { value: 'BLOCKED', label: '已拦截' }
  ],
  opResult: [
    { value: 'SUCCESS', label: '成功' },
    { value: 'FAILED', label: '失败' },
    { value: 'DENIED', label: '越权拦截' }
  ],
  scopeTypes: [
    { value: 'SCHOOL', label: '全校' },
    { value: 'COLLEGE', label: '本学院' },
    { value: 'MAJOR', label: '本专业' },
    { value: 'CLASS', label: '本班级' },
    { value: 'SELF', label: '本人' },
    { value: 'GD_STUDENTS', label: '本人指导毕设学生' },
    { value: 'INTERN_STUDENTS', label: '本人指导实习学生' },
    { value: 'ENTERPRISE_AUTH_STUDENTS', label: '企业授权学生' },
    { value: 'TEMP_AUTH', label: '临时授权' }
  ]
}

export const filterOptions = {
  colleges: [
    { value: 'org-c01', label: '信息工程学院' },
    { value: 'org-c02', label: '智能制造学院' },
    { value: 'org-c03', label: '经济管理学院' },
    { value: 'org-dept', label: '职能部门' }
  ],
  roles: [
    { value: 'SYS_ADMIN', label: '系统管理员' },
    { value: 'SCHOOL_ADMIN', label: '学校管理员' },
    { value: 'COLLEGE_ADMIN', label: '学院管理员' },
    { value: 'PLATFORM_OPS', label: '平台运维' },
    { value: 'AUDITOR', label: '审计人员' },
    { value: 'COUNSELOR', label: '辅导员' },
    { value: 'INTERN_ADVISOR', label: '实习指导教师' }
  ],
  logModules: [
    { value: 'SYSTEM', label: '系统管理' },
    { value: 'INTERNSHIP', label: '岗位实习' },
    { value: 'GRADUATION', label: '毕业设计' },
    { value: 'STUDENT', label: '学生主档' },
    { value: 'EXPORT', label: '导入导出' }
  ],
  logActions: [
    { value: 'CREATE', label: '新增' },
    { value: 'UPDATE', label: '编辑' },
    { value: 'DISABLE', label: '停用/作废' },
    { value: 'GRANT', label: '授权变更' },
    { value: 'EXPORT', label: '导出' },
    { value: 'IMPORT', label: '导入' },
    { value: 'CONFIG', label: '配置变更' },
    { value: 'LOGIN', label: '登录' }
  ]
}

/** 表格列设置（列可显隐，locked 列不可隐藏） */
export const fieldColumns = {
  users: [
    { key: 'user', title: '用户', locked: true, defaultVisible: true },
    { key: 'org', title: '所属组织', locked: false, defaultVisible: true },
    { key: 'roles', title: '角色', locked: false, defaultVisible: true },
    { key: 'phone', title: '手机号（脱敏）', locked: false, defaultVisible: true },
    { key: 'status', title: '状态', locked: false, defaultVisible: true },
    { key: 'lastLoginAt', title: '最近登录', locked: false, defaultVisible: true },
    { key: 'source', title: '账号来源', locked: false, defaultVisible: false },
    { key: 'createdAt', title: '创建时间', locked: false, defaultVisible: false },
    { key: 'actions', title: '操作', locked: true, defaultVisible: true }
  ]
}

export const batchActions = {
  users: [
    { key: 'batchAssignRole', label: '批量分配角色', permissionKey: 'assignRole' },
    { key: 'batchDisableUsers', label: '批量停用', permissionKey: 'batchDisableUsers', danger: true },
    { key: 'exportSelected', label: '导出所选', permissionKey: 'exportUsers' }
  ]
}

export const importTemplates = {
  users: {
    key: 'users',
    name: '用户账号导入模板',
    version: 'v3.2',
    fileName: '用户账号导入模板_v3.2.xlsx',
    fields: ['工号/账号', '姓名', '所属组织编码', '角色编码（多个用逗号）', '手机号', '邮箱', '初始数据范围'],
    rules: ['工号在本校内唯一，重复行将被拒绝', '角色编码必须已存在且处于启用状态', '手机号仅用于找回密码，导入后默认脱敏展示', '单次最多 2,000 行']
  },
  org: {
    key: 'org',
    name: '组织结构导入模板',
    version: 'v2.0',
    fileName: '组织结构导入模板_v2.0.xlsx',
    fields: ['组织编码', '组织名称', '组织类型（学院/专业/班级/部门）', '上级组织编码', '排序号'],
    rules: ['组织编码唯一且不可修改', '删除组织请在页面内作废，导入不支持删除']
  }
}

export const exportOptions = {
  users: {
    scopes: [
      { value: 'FILTERED', label: '当前筛选结果' },
      { value: 'SELECTED', label: '仅所选记录' },
      { value: 'ALL', label: '数据范围内全部' }
    ],
    fields: [
      { key: 'userNo', label: '工号/账号', sensitive: true, defaultChecked: true, maskNote: '默认脱敏（保留前 4 位）' },
      { key: 'name', label: '姓名', sensitive: false, defaultChecked: true },
      { key: 'org', label: '所属组织', sensitive: false, defaultChecked: true },
      { key: 'roles', label: '角色', sensitive: false, defaultChecked: true },
      { key: 'phone', label: '手机号', sensitive: true, defaultChecked: false, maskNote: '默认脱敏（138****0000）' },
      { key: 'email', label: '邮箱', sensitive: true, defaultChecked: false, maskNote: '默认脱敏（前 2 位 + 域名）' },
      { key: 'status', label: '状态', sensitive: false, defaultChecked: true },
      { key: 'lastLoginAt', label: '最近登录', sensitive: false, defaultChecked: false }
    ],
    watermark: true,
    note: '导出文件自动附加水印（{{watermarkText}} · 操作人 · 时间），敏感字段默认脱敏；如需明文导出须走导出审批流程。'
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
      { key: 'ip', label: 'IP（脱敏）', sensitive: true, defaultChecked: true, maskNote: '固定脱敏，不支持明文导出' },
      { key: 'detail', label: '详情', sensitive: false, defaultChecked: false }
    ],
    watermark: true,
    note: '审计日志仅支持导出，不支持删除或修改；导出动作本身也会写入审计日志。'
  }
}

export const dashboardSummary = {
  stats: [
    { label: '在册账号', value: '1,842', trend: '本月新增 36', trendQuality: 'neutral' },
    { label: '启用中账号', value: '1,795', trend: '停用 41 · 锁定 6', trendQuality: 'neutral' },
    { label: '今日登录人次', value: '463', trend: '▲ 8.2% 较昨日', trendQuality: 'good' },
    { label: '近 7 日失败登录', value: '29', trend: '含 3 次连续失败锁定', trendQuality: 'bad' },
    { label: '启用角色', value: '12', trend: '内置 7 · 自定义 5', trendQuality: 'neutral' },
    { label: '数据范围规则', value: '9', trend: '本周变更 1 条', trendQuality: 'neutral' }
  ],
  todos: [
    { id: 'st-1', label: '待激活账号', count: 5, tone: 'warning', hint: '新导入教师账号，超 7 天未激活将自动停用', route: '/admin/system/users?status=PENDING' },
    { id: 'st-2', label: '角色权限变更待复核', count: 2, tone: 'danger', hint: '涉及「学院管理员」数据范围调整', route: '/admin/system/roles' },
    { id: 'st-3', label: '异常登录待确认', count: 3, tone: 'warning', hint: '异地 IP 登录 2 次 · 连续失败锁定 1 人', route: '/admin/system/logs?tab=login' }
  ],
  securityAlerts: [
    { id: 'sa-1', level: 'HIGH', title: '账号连续失败锁定', detail: '账号 T20****19（李某）连续 5 次密码错误已锁定，请核实后解锁', time: '今天 09:41' },
    { id: 'sa-2', level: 'MEDIUM', title: '异地登录提醒', detail: '审计账号在非常用地区登录，已触发二次验证', time: '昨天 22:18' },
    { id: 'sa-3', level: 'MEDIUM', title: '导出频次偏高', detail: '某学院管理员当日发起 6 次名单导出，均已留痕', time: '昨天 17:02' }
  ],
  recentOps: [
    { id: 'ro-1', who: '周文彬 · 学校管理员', action: '编辑角色「学院管理员」按钮权限', time: '今天 10:22' },
    { id: 'ro-2', who: '系统', action: '自动停用 30 天未登录账号 2 个', time: '今天 03:00' },
    { id: 'ro-3', who: '赵启明 · 系统管理员', action: '更新登录安全策略（失败锁定阈值 5 次）', time: '昨天 16:40' }
  ]
}

export const userList = [
  {
    id: 'sys-u-001', userNo: 'T2016001', name: '周文彬', orgId: 'org-dept', orgName: '信息中心',
    roles: ['SCHOOL_ADMIN'], roleNames: ['学校管理员'], phone: '13812340101', email: 'zhouwb@demo.edu.cn',
    status: 'ACTIVE', statusLabel: '启用中', source: '本地账号', lastLoginAt: '2026-07-04 08:31', createdAt: '2023-09-01'
  },
  {
    id: 'sys-u-002', userNo: 'T2012008', name: '赵启明', orgId: 'org-dept', orgName: '信息中心',
    roles: ['SYS_ADMIN'], roleNames: ['系统管理员'], phone: '13912340102', email: 'zhaoqm@demo.edu.cn',
    status: 'ACTIVE', statusLabel: '启用中', source: '本地账号', lastLoginAt: '2026-07-03 16:38', createdAt: '2022-03-14'
  },
  {
    id: 'sys-u-003', userNo: 'T2018021', name: '李慧敏', orgId: 'org-c01', orgName: '信息工程学院',
    roles: ['COLLEGE_ADMIN', 'COUNSELOR'], roleNames: ['学院管理员', '辅导员'], phone: '13712340103', email: 'lihm@demo.edu.cn',
    status: 'ACTIVE', statusLabel: '启用中', source: '统一身份认证', lastLoginAt: '2026-07-04 09:02', createdAt: '2023-02-20'
  },
  {
    id: 'sys-u-004', userNo: 'T2019035', name: '刘强', orgId: 'org-c01', orgName: '信息工程学院',
    roles: ['INTERN_ADVISOR'], roleNames: ['实习指导教师'], phone: '13512346867', email: 'liuq@demo.edu.cn',
    status: 'ACTIVE', statusLabel: '启用中', source: '统一身份认证', lastLoginAt: '2026-07-04 07:55', createdAt: '2023-09-01'
  },
  {
    id: 'sys-u-005', userNo: 'T2020019', name: '李敏', orgId: 'org-c01', orgName: '信息工程学院',
    roles: ['COUNSELOR'], roleNames: ['辅导员'], phone: '15012340105', email: 'limin@demo.edu.cn',
    status: 'LOCKED', statusLabel: '已锁定', source: '统一身份认证', lastLoginAt: '2026-07-04 09:41', createdAt: '2023-09-01'
  },
  {
    id: 'sys-u-006', userNo: 'T2015012', name: '王建军', orgId: 'org-c02', orgName: '智能制造学院',
    roles: ['COLLEGE_ADMIN'], roleNames: ['学院管理员'], phone: '13612340106', email: 'wangjj@demo.edu.cn',
    status: 'ACTIVE', statusLabel: '启用中', source: '统一身份认证', lastLoginAt: '2026-07-03 18:20', createdAt: '2021-09-01'
  },
  {
    id: 'sys-u-007', userNo: 'A2024003', name: '孙晓雯', orgId: 'org-dept', orgName: '审计与质量办公室',
    roles: ['AUDITOR'], roleNames: ['审计人员'], phone: '18612340107', email: 'sunxw@demo.edu.cn',
    status: 'ACTIVE', statusLabel: '启用中', source: '本地账号', lastLoginAt: '2026-07-02 14:11', createdAt: '2024-04-08'
  },
  {
    id: 'sys-u-008', userNo: 'P2023001', name: '陈一鸣', orgId: 'org-dept', orgName: '平台运维（驻校）',
    roles: ['PLATFORM_OPS'], roleNames: ['平台运维'], phone: '13312340108', email: 'chenym@ops.example.com',
    status: 'ACTIVE', statusLabel: '启用中', source: '平台派驻', lastLoginAt: '2026-07-01 10:05', createdAt: '2023-11-30'
  },
  {
    id: 'sys-u-009', userNo: 'T2021044', name: '吴倩', orgId: 'org-c03', orgName: '经济管理学院',
    roles: ['COUNSELOR'], roleNames: ['辅导员'], phone: '15912340109', email: 'wuqian@demo.edu.cn',
    status: 'DISABLED', statusLabel: '已停用', source: '统一身份认证', lastLoginAt: '2026-05-12 09:30', createdAt: '2023-09-01'
  },
  {
    id: 'sys-u-010', userNo: 'T2025007', name: '郑立文', orgId: 'org-c02', orgName: '智能制造学院',
    roles: ['INTERN_ADVISOR'], roleNames: ['实习指导教师'], phone: '13112340110', email: 'zhenglw@demo.edu.cn',
    status: 'PENDING', statusLabel: '待激活', source: '批量导入', lastLoginAt: '', createdAt: '2026-06-28'
  }
]

export const userDetailMap = {
  'sys-u-005': {
    id: 'sys-u-005', userNo: 'T2020019', name: '李敏', orgName: '信息工程学院 · 学工办',
    phone: '15012340105', email: 'limin@demo.edu.cn', status: 'LOCKED', statusLabel: '已锁定',
    source: '统一身份认证', createdAt: '2023-09-01', lastLoginAt: '2026-07-04 09:41',
    roles: [
      { code: 'COUNSELOR', name: '辅导员', scopeName: '本班级（软件2301 / 软件2302）' }
    ],
    contexts: ['辅导员（软件2301 / 软件2302）'],
    loginHistory: [
      { time: '2026-07-04 09:41', result: 'BLOCKED', resultLabel: '已拦截', detail: '连续 5 次密码错误，账号锁定 30 分钟', ip: '10.12.*.*', device: 'Windows · Chrome' },
      { time: '2026-07-03 08:12', result: 'SUCCESS', resultLabel: '成功', detail: '', ip: '10.12.*.*', device: 'Windows · Chrome' }
    ],
    auditTrail: [
      { who: '系统', time: '2026-07-04 09:41', action: '账号锁定', affected: '连续失败 5 次触发安全策略 SEC-LOCK-5' },
      { who: '周文彬 · 学校管理员', time: '2026-03-02 10:00', action: '分配角色', affected: '新增「辅导员」，数据范围：本班级' }
    ]
  },
  'sys-u-010': {
    id: 'sys-u-010', userNo: 'T2025007', name: '郑立文', orgName: '智能制造学院',
    phone: '13112340110', email: 'zhenglw@demo.edu.cn', status: 'PENDING', statusLabel: '待激活',
    source: '批量导入（批次 IMP-20260628-01）', createdAt: '2026-06-28', lastLoginAt: '',
    roles: [{ code: 'INTERN_ADVISOR', name: '实习指导教师', scopeName: '本人指导实习学生' }],
    contexts: ['实习指导教师'],
    loginHistory: [],
    auditTrail: [
      { who: '周文彬 · 学校管理员', time: '2026-06-28 15:22', action: '批量导入创建', affected: '导入批次 IMP-20260628-01 · 共 12 行成功' }
    ]
  }
}

export const roleList = [
  {
    id: 'role-01', code: 'SYS_ADMIN', name: '系统管理员', type: 'BUILTIN', typeLabel: '内置角色',
    memberCount: 2, scopeCode: 'SCHOOL', scopeName: '全校', status: 'ENABLED', statusLabel: '启用中',
    description: '学校侧最高配置权限：菜单结构、安全策略、恢复默认', updatedAt: '2026-06-30'
  },
  {
    id: 'role-02', code: 'SCHOOL_ADMIN', name: '学校管理员', type: 'BUILTIN', typeLabel: '内置角色',
    memberCount: 3, scopeCode: 'SCHOOL', scopeName: '全校', status: 'ENABLED', statusLabel: '启用中',
    description: '账号 / 角色 / 组织 / 品牌配置日常管理', updatedAt: '2026-07-01'
  },
  {
    id: 'role-03', code: 'COLLEGE_ADMIN', name: '学院管理员', type: 'BUILTIN', typeLabel: '内置角色',
    memberCount: 8, scopeCode: 'COLLEGE', scopeName: '本学院', status: 'ENABLED', statusLabel: '启用中',
    description: '本学院账号与业务管理，不可跨院查看', updatedAt: '2026-07-02'
  },
  {
    id: 'role-04', code: 'PLATFORM_OPS', name: '平台运维', type: 'BUILTIN', typeLabel: '内置角色',
    memberCount: 1, scopeCode: 'SCHOOL', scopeName: '全校（仅运维项）', status: 'ENABLED', statusLabel: '启用中',
    description: '集成排障与运维工具，默认不可见学生敏感明细', updatedAt: '2026-05-18'
  },
  {
    id: 'role-05', code: 'AUDITOR', name: '审计人员', type: 'BUILTIN', typeLabel: '内置角色',
    memberCount: 1, scopeCode: 'SCHOOL', scopeName: '全校（只读）', status: 'ENABLED', statusLabel: '启用中',
    description: '只读查看审计日志 / 权限变更 / 导出记录，不可修改业务', updatedAt: '2026-04-11'
  },
  {
    id: 'role-06', code: 'COUNSELOR', name: '辅导员', type: 'BUILTIN', typeLabel: '内置角色',
    memberCount: 42, scopeCode: 'CLASS', scopeName: '本班级', status: 'ENABLED', statusLabel: '启用中',
    description: '本班学生服务与风险处理', updatedAt: '2026-06-12'
  },
  {
    id: 'role-07', code: 'INTERN_ADVISOR', name: '实习指导教师', type: 'BUILTIN', typeLabel: '内置角色',
    memberCount: 65, scopeCode: 'INTERN_STUDENTS', scopeName: '本人指导实习学生', status: 'ENABLED', statusLabel: '启用中',
    description: '实习周报批阅 / 打卡异常处理 / 风险跟进', updatedAt: '2026-06-25'
  },
  {
    id: 'role-08', code: 'QA_VIEWER', name: '质量督导（自定义）', type: 'CUSTOM', typeLabel: '自定义角色',
    memberCount: 4, scopeCode: 'SCHOOL', scopeName: '全校（只读报表）', status: 'ENABLED', statusLabel: '启用中',
    description: '教学质量部门只读查看统计报表', updatedAt: '2026-06-20'
  },
  {
    id: 'role-09', code: 'OLD_EXPORTER', name: '临时导出员（已作废）', type: 'CUSTOM', typeLabel: '自定义角色',
    memberCount: 0, scopeCode: 'COLLEGE', scopeName: '本学院', status: 'DEPRECATED', statusLabel: '已作废',
    description: '2025 迎新临时角色，已按期作废', updatedAt: '2025-10-08'
  }
]

export const roleDetailMap = {
  'role-03': {
    id: 'role-03', code: 'COLLEGE_ADMIN', name: '学院管理员', type: 'BUILTIN', typeLabel: '内置角色',
    status: 'ENABLED', statusLabel: '启用中', scopeCode: 'COLLEGE', scopeName: '本学院',
    description: '本学院账号与业务管理，不可跨院查看',
    menuKeys: ['sys-home', 'sys-users', 'int-dashboard', 'int-students', 'int-reports', 'gd-dashboard', 'gd-topics'],
    buttonKeys: ['user:create', 'user:update', 'user:disable', 'intern:weekly-report:review', 'intern:export:desensitized'],
    members: [
      { id: 'sys-u-003', name: '李慧敏', orgName: '信息工程学院' },
      { id: 'sys-u-006', name: '王建军', orgName: '智能制造学院' }
    ],
    auditTrail: [
      { who: '周文彬 · 学校管理员', time: '2026-07-02 10:22', action: '调整按钮权限', affected: '新增 intern:export:desensitized（脱敏导出）' },
      { who: '赵启明 · 系统管理员', time: '2026-05-06 09:15', action: '调整数据范围', affected: 'SCHOOL → COLLEGE，影响 8 个账号' }
    ]
  }
}

/** 权限树：模块 → 菜单 → 按钮（权限编码规范：模块:资源:动作） */
export const permissionTree = [
  {
    key: 'mod-system', label: '系统管理中心', type: 'MODULE',
    children: [
      {
        key: 'sys-home', label: '管理看板', type: 'MENU', children: []
      },
      {
        key: 'sys-users', label: '用户账号管理', type: 'MENU',
        children: [
          { key: 'user:create', label: '新增用户', type: 'BUTTON' },
          { key: 'user:update', label: '编辑用户', type: 'BUTTON' },
          { key: 'user:disable', label: '停用/启用', type: 'BUTTON' },
          { key: 'user:reset-password', label: '重置密码', type: 'BUTTON' },
          { key: 'user:assign-role', label: '分配角色', type: 'BUTTON' },
          { key: 'user:import', label: '批量导入', type: 'BUTTON' },
          { key: 'user:export', label: '批量导出（脱敏）', type: 'BUTTON' }
        ]
      },
      {
        key: 'sys-roles', label: '角色权限管理', type: 'MENU',
        children: [
          { key: 'role:create', label: '新增角色', type: 'BUTTON' },
          { key: 'role:config', label: '配置权限', type: 'BUTTON' },
          { key: 'role:deprecate', label: '作废角色', type: 'BUTTON' }
        ]
      },
      {
        key: 'sys-logs', label: '日志中心', type: 'MENU',
        children: [
          { key: 'log:view', label: '查看日志', type: 'BUTTON' },
          { key: 'log:export', label: '导出日志', type: 'BUTTON' }
        ]
      }
    ]
  },
  {
    key: 'mod-internship', label: '岗位实习中心', type: 'MODULE',
    children: [
      { key: 'int-dashboard', label: '管理看板', type: 'MENU', children: [] },
      {
        key: 'int-students', label: '实习学生', type: 'MENU',
        children: [
          { key: 'intern:student:create', label: '新增实习学生', type: 'BUTTON' },
          { key: 'intern:student:archive', label: '归档', type: 'BUTTON' },
          { key: 'intern:export:desensitized', label: '脱敏导出', type: 'BUTTON' }
        ]
      },
      {
        key: 'int-reports', label: '周报批阅', type: 'MENU',
        children: [{ key: 'intern:weekly-report:review', label: '批阅周报', type: 'BUTTON' }]
      }
    ]
  },
  {
    key: 'mod-graduation', label: '毕业设计中心', type: 'MODULE',
    children: [
      { key: 'gd-dashboard', label: '管理看板', type: 'MENU', children: [] },
      {
        key: 'gd-topics', label: '选题管理', type: 'MENU',
        children: [{ key: 'gd:topic:review', label: '课题审核', type: 'BUTTON' }]
      }
    ]
  }
]

export const menuTree = [
  {
    id: 'menu-sys', code: 'sys', name: '系统管理中心', icon: '⚙', path: '/admin/system', sort: 90,
    status: 'ENABLED', statusLabel: '启用', moduleCode: 'SYSTEM',
    children: [
      { id: 'menu-sys-home', code: 'sys-home', name: '管理看板', path: '/admin/system', sort: 1, status: 'ENABLED', statusLabel: '启用', buttons: [] },
      {
        id: 'menu-sys-users', code: 'sys-users', name: '用户账号管理', path: '/admin/system/users', sort: 2, status: 'ENABLED', statusLabel: '启用',
        buttons: [
          { code: 'user:create', name: '新增用户' }, { code: 'user:import', name: '批量导入' },
          { code: 'user:export', name: '批量导出' }, { code: 'user:reset-password', name: '重置密码' }
        ]
      },
      {
        id: 'menu-sys-roles', code: 'sys-roles', name: '角色权限管理', path: '/admin/system/roles', sort: 3, status: 'ENABLED', statusLabel: '启用',
        buttons: [{ code: 'role:create', name: '新增角色' }, { code: 'role:deprecate', name: '作废角色' }]
      },
      { id: 'menu-sys-menus', code: 'sys-menus', name: '菜单权限管理', path: '/admin/system/menus', sort: 4, status: 'ENABLED', statusLabel: '启用', buttons: [] },
      { id: 'menu-sys-scopes', code: 'sys-scopes', name: '数据范围管理', path: '/admin/system/scopes', sort: 5, status: 'ENABLED', statusLabel: '启用', buttons: [] },
      { id: 'menu-sys-org', code: 'sys-org', name: '组织结构管理', path: '/admin/system/org', sort: 6, status: 'ENABLED', statusLabel: '启用', buttons: [] },
      { id: 'menu-sys-config', code: 'sys-config', name: '系统与品牌配置', path: '/admin/system/config', sort: 7, status: 'ENABLED', statusLabel: '启用', buttons: [] },
      { id: 'menu-sys-logs', code: 'sys-logs', name: '日志中心', path: '/admin/system/logs', sort: 8, status: 'ENABLED', statusLabel: '启用', buttons: [] }
    ]
  },
  {
    id: 'menu-int', code: 'int', name: '岗位实习中心', icon: '🧭', path: '/admin/internship', sort: 20,
    status: 'ENABLED', statusLabel: '启用', moduleCode: 'INTERNSHIP',
    children: [
      { id: 'menu-int-1', code: 'int-dashboard', name: '管理看板', path: '/admin/internship', sort: 1, status: 'ENABLED', statusLabel: '启用', buttons: [] },
      { id: 'menu-int-2', code: 'int-students', name: '实习学生', path: '/admin/internship/students', sort: 2, status: 'ENABLED', statusLabel: '启用', buttons: [{ code: 'intern:export:desensitized', name: '脱敏导出' }] }
    ]
  },
  {
    id: 'menu-legacy', code: 'legacy-report', name: '旧版报表（停用示例）', icon: '▤', path: '/admin/legacy-report', sort: 99,
    status: 'DISABLED', statusLabel: '停用', moduleCode: 'LEGACY', children: []
  }
]

/** 角色 → 可见菜单（菜单权限页「按角色预览」用） */
export const roleMenuPreview = {
  SYS_ADMIN: ['sys-home', 'sys-users', 'sys-roles', 'sys-menus', 'sys-scopes', 'sys-org', 'sys-config', 'sys-logs', 'int-dashboard', 'int-students'],
  SCHOOL_ADMIN: ['sys-home', 'sys-users', 'sys-roles', 'sys-scopes', 'sys-org', 'sys-config', 'sys-logs', 'int-dashboard', 'int-students'],
  COLLEGE_ADMIN: ['sys-home', 'sys-users', 'int-dashboard', 'int-students'],
  PLATFORM_OPS: ['sys-home', 'sys-logs'],
  AUDITOR: ['sys-home', 'sys-logs'],
  COUNSELOR: ['int-dashboard'],
  INTERN_ADVISOR: ['int-dashboard', 'int-students']
}

export const dataScopeRules = [
  {
    id: 'scope-01', name: '全校范围', scopeCode: 'SCHOOL', scopeLabel: '全校',
    appliedRoles: ['系统管理员', '学校管理员', '审计人员'], affectedUsers: 6,
    remark: '含全部院系与职能部门', status: 'ENABLED', statusLabel: '启用中', updatedAt: '2026-05-06'
  },
  {
    id: 'scope-02', name: '本学院范围', scopeCode: 'COLLEGE', scopeLabel: '本学院',
    appliedRoles: ['学院管理员'], affectedUsers: 8,
    remark: '按任职学院自动计算，跨院不可见', status: 'ENABLED', statusLabel: '启用中', updatedAt: '2026-05-06'
  },
  {
    id: 'scope-03', name: '本班级范围', scopeCode: 'CLASS', scopeLabel: '本班级',
    appliedRoles: ['辅导员'], affectedUsers: 42,
    remark: '按带班关系自动计算', status: 'ENABLED', statusLabel: '启用中', updatedAt: '2026-03-01'
  },
  {
    id: 'scope-04', name: '本人指导实习学生', scopeCode: 'INTERN_STUDENTS', scopeLabel: '指导实习学生',
    appliedRoles: ['实习指导教师'], affectedUsers: 65,
    remark: '按实习分配关系自动计算', status: 'ENABLED', statusLabel: '启用中', updatedAt: '2026-03-01'
  },
  {
    id: 'scope-05', name: '本人指导毕设学生', scopeCode: 'GD_STUDENTS', scopeLabel: '指导毕设学生',
    appliedRoles: ['毕设导师'], affectedUsers: 58,
    remark: '按毕设师生关系自动计算', status: 'ENABLED', statusLabel: '启用中', updatedAt: '2026-03-01'
  },
  {
    id: 'scope-06', name: '企业授权学生', scopeCode: 'ENTERPRISE_AUTH_STUDENTS', scopeLabel: '企业授权学生',
    appliedRoles: ['企业导师'], affectedUsers: 23,
    remark: '仅实习相关字段，禁止家庭/心理/处分信息', status: 'ENABLED', statusLabel: '启用中', updatedAt: '2026-04-15'
  },
  {
    id: 'scope-07', name: '2025 迎新临时授权（已作废）', scopeCode: 'TEMP_AUTH', scopeLabel: '临时授权',
    appliedRoles: ['临时导出员（已作废）'], affectedUsers: 0,
    remark: '有效期 2025-08-20 ~ 2025-09-30，到期自动作废', status: 'DEPRECATED', statusLabel: '已作废', updatedAt: '2025-10-08'
  }
]

export const scopeAffectedUsersMap = {
  'scope-02': [
    { id: 'sys-u-003', name: '李慧敏', orgName: '信息工程学院', roleName: '学院管理员' },
    { id: 'sys-u-006', name: '王建军', orgName: '智能制造学院', roleName: '学院管理员' }
  ]
}

export const departmentTree = [
  {
    id: 'org-c01', code: 'C01', name: '信息工程学院', type: 'COLLEGE', typeLabel: '学院', memberCount: 486, status: 'ENABLED',
    children: [
      {
        id: 'org-c01-m1', code: 'C01-RJ', name: '软件技术专业', type: 'MAJOR', typeLabel: '专业', memberCount: 312, status: 'ENABLED',
        children: [
          { id: 'c-2301', code: 'RJ2301', name: '软件2301', type: 'CLASS', typeLabel: '班级', memberCount: 42, status: 'ENABLED', children: [] },
          { id: 'c-2302', code: 'RJ2302', name: '软件2302', type: 'CLASS', typeLabel: '班级', memberCount: 40, status: 'ENABLED', children: [] }
        ]
      },
      {
        id: 'org-c01-m2', code: 'C01-WL', name: '计算机网络专业', type: 'MAJOR', typeLabel: '专业', memberCount: 174, status: 'ENABLED',
        children: [{ id: 'c-2303', code: 'WL2301', name: '网络2301', type: 'CLASS', typeLabel: '班级', memberCount: 44, status: 'ENABLED', children: [] }]
      }
    ]
  },
  {
    id: 'org-c02', code: 'C02', name: '智能制造学院', type: 'COLLEGE', typeLabel: '学院', memberCount: 523, status: 'ENABLED',
    children: [
      {
        id: 'org-c02-m1', code: 'C02-SK', name: '数控技术专业', type: 'MAJOR', typeLabel: '专业', memberCount: 268, status: 'ENABLED',
        children: [{ id: 'c-2201', code: 'SK2201', name: '数控2201', type: 'CLASS', typeLabel: '班级', memberCount: 45, status: 'ENABLED', children: [] }]
      }
    ]
  },
  {
    id: 'org-c03', code: 'C03', name: '经济管理学院', type: 'COLLEGE', typeLabel: '学院', memberCount: 391, status: 'ENABLED', children: []
  },
  {
    id: 'org-dept', code: 'D00', name: '职能部门', type: 'DEPT', typeLabel: '部门', memberCount: 96, status: 'ENABLED',
    children: [
      { id: 'org-dept-1', code: 'D01', name: '信息中心', type: 'DEPT', typeLabel: '部门', memberCount: 12, status: 'ENABLED', children: [] },
      { id: 'org-dept-2', code: 'D02', name: '审计与质量办公室', type: 'DEPT', typeLabel: '部门', memberCount: 5, status: 'ENABLED', children: [] },
      { id: 'org-dept-3', code: 'D03', name: '实习就业处', type: 'DEPT', typeLabel: '部门', memberCount: 9, status: 'ENABLED', children: [] }
    ]
  }
]

export const positionList = [
  { id: 'pos-01', name: '系统管理员岗', orgName: '信息中心', memberCount: 2, remark: '安全策略 / 菜单结构维护', status: 'ENABLED', statusLabel: '启用中' },
  { id: 'pos-02', name: '学工辅导员岗', orgName: '各学院学工办', memberCount: 42, remark: '按班级配置数据范围', status: 'ENABLED', statusLabel: '启用中' },
  { id: 'pos-03', name: '实习指导教师岗', orgName: '各学院', memberCount: 65, remark: '按实习分配关系配置数据范围', status: 'ENABLED', statusLabel: '启用中' },
  { id: 'pos-04', name: '审计专员岗', orgName: '审计与质量办公室', memberCount: 1, remark: '只读审计', status: 'ENABLED', statusLabel: '启用中' }
]

export const loginLogList = [
  { id: 'll-001', userName: '李敏', userNo: 'T2020019', roleName: '辅导员', time: '2026-07-04 09:41', result: 'BLOCKED', resultLabel: '已拦截', reason: '连续 5 次密码错误，账号锁定', ip: '10.12.*.*', location: '校内网', device: 'Windows · Chrome' },
  { id: 'll-002', userName: '李慧敏', userNo: 'T2018021', roleName: '学院管理员', time: '2026-07-04 09:02', result: 'SUCCESS', resultLabel: '成功', reason: '', ip: '10.12.*.*', location: '校内网', device: 'Windows · Edge' },
  { id: 'll-003', userName: '周文彬', userNo: 'T2016001', roleName: '学校管理员', time: '2026-07-04 08:31', result: 'SUCCESS', resultLabel: '成功', reason: '', ip: '10.12.*.*', location: '校内网', device: 'macOS · Safari' },
  { id: 'll-004', userName: '刘强', userNo: 'T2019035', roleName: '实习指导教师', time: '2026-07-04 07:55', result: 'SUCCESS', resultLabel: '成功', reason: '', ip: '112.80.*.*', location: '江苏苏州', device: 'iOS · 小程序' },
  { id: 'll-005', userName: '孙晓雯', userNo: 'A2024003', roleName: '审计人员', time: '2026-07-03 22:18', result: 'SUCCESS', resultLabel: '成功', reason: '异地登录，已通过二次验证', ip: '223.104.*.*', location: '浙江杭州', device: 'Windows · Chrome' },
  { id: 'll-006', userName: '未知账号', userNo: 'admin', roleName: '—', time: '2026-07-03 03:12', result: 'FAILED', resultLabel: '失败', reason: '账号不存在（疑似扫描尝试）', ip: '45.76.*.*', location: '境外', device: '未知' }
]

export const operationLogList = [
  {
    id: 'ol-001', time: '2026-07-04 10:22', who: '周文彬', roleName: '学校管理员', module: 'SYSTEM', moduleLabel: '系统管理',
    action: 'GRANT', actionLabel: '授权变更', target: '角色「学院管理员」', result: 'SUCCESS', resultLabel: '成功', ip: '10.12.*.*',
    detail: { summary: '调整按钮权限', before: '未含 intern:export:desensitized', after: '新增 intern:export:desensitized（脱敏导出）', reason: '学院侧需要脱敏名单用于巡访' }
  },
  {
    id: 'ol-002', time: '2026-07-04 09:58', who: '李慧敏', roleName: '学院管理员', module: 'EXPORT', moduleLabel: '导入导出',
    action: 'EXPORT', actionLabel: '导出', target: '实习学生名单（本学院）', result: 'SUCCESS', resultLabel: '成功', ip: '10.12.*.*',
    detail: { summary: '导出 186 条（脱敏 + 水印）', before: '', after: '文件带水印：演示职业技术学院 · 李慧敏 · 2026-07-04', reason: '巡访安排' }
  },
  {
    id: 'ol-003', time: '2026-07-03 16:40', who: '赵启明', roleName: '系统管理员', module: 'SYSTEM', moduleLabel: '系统管理',
    action: 'CONFIG', actionLabel: '配置变更', target: '安全策略 SEC-LOCK', result: 'SUCCESS', resultLabel: '成功', ip: '10.12.*.*',
    detail: { summary: '登录失败锁定阈值调整', before: '8 次', after: '5 次', reason: '近期扫描尝试增多' }
  },
  {
    id: 'ol-004', time: '2026-07-03 15:02', who: '吴倩', roleName: '辅导员', module: 'STUDENT', moduleLabel: '学生主档',
    action: 'EXPORT', actionLabel: '导出', target: '全校学生名单', result: 'DENIED', resultLabel: '越权拦截', ip: '10.12.*.*',
    detail: { summary: '数据范围不足（CLASS → 请求 SCHOOL）', before: '', after: '', reason: '已提示按数据范围导出' }
  },
  {
    id: 'ol-005', time: '2026-07-02 11:30', who: '周文彬', roleName: '学校管理员', module: 'SYSTEM', moduleLabel: '系统管理',
    action: 'DISABLE', actionLabel: '停用/作废', target: '账号 T2021044（吴倩）', result: 'SUCCESS', resultLabel: '成功', ip: '10.12.*.*',
    detail: { summary: '停用账号（逻辑删除，可恢复）', before: '启用中', after: '已停用', reason: '离职交接，保留历史操作记录' }
  },
  {
    id: 'ol-006', time: '2026-06-28 15:22', who: '周文彬', roleName: '学校管理员', module: 'SYSTEM', moduleLabel: '系统管理',
    action: 'IMPORT', actionLabel: '导入', target: '用户账号（批次 IMP-20260628-01）', result: 'SUCCESS', resultLabel: '成功', ip: '10.12.*.*',
    detail: { summary: '导入 14 行：成功 12 · 失败 2', before: '', after: '失败行已生成错误清单并留存', reason: '新学期教师入职' }
  }
]

export const systemConfigList = [
  { key: 'SEC-PASSWORD', group: '安全策略', name: '密码策略', valueText: '最少 10 位 · 大小写+数字 · 90 天强制更换', sensitive: false, updatedAt: '2026-05-10', updatedBy: '赵启明' },
  { key: 'SEC-LOCK', group: '安全策略', name: '登录失败锁定', valueText: '连续 5 次失败锁定 30 分钟', sensitive: false, updatedAt: '2026-07-03', updatedBy: '赵启明' },
  { key: 'SEC-SESSION', group: '安全策略', name: '会话超时', valueText: 'PC 30 分钟 · 移动端 7 天', sensitive: false, updatedAt: '2026-03-02', updatedBy: '赵启明' },
  { key: 'SEC-MFA', group: '安全策略', name: '异地登录二次验证', valueText: '已开启（短信验证码）', sensitive: false, updatedAt: '2026-04-22', updatedBy: '赵启明' },
  { key: 'EXP-WATERMARK', group: '数据与导出', name: '导出水印', valueText: '强制开启：{{watermarkText}} · 操作人 · 时间', sensitive: false, updatedAt: '2026-02-01', updatedBy: '周文彬' },
  { key: 'EXP-MASK', group: '数据与导出', name: '敏感字段脱敏', valueText: '手机号 / 身份证 / 家庭信息默认脱敏，明文导出需审批', sensitive: true, updatedAt: '2026-02-01', updatedBy: '周文彬' },
  { key: 'EXP-APPROVE', group: '数据与导出', name: '明文导出审批', valueText: '需学校管理员 + 审计人员双确认', sensitive: true, updatedAt: '2026-02-01', updatedBy: '周文彬' },
  { key: 'MSG-CHANNEL', group: '消息通知', name: '通知渠道', valueText: '站内信 + 小程序订阅消息（短信备用）', sensitive: false, updatedAt: '2026-03-15', updatedBy: '周文彬' }
]

/** 品牌配置（学校侧可编辑项，来源：平台租户授权范围内） */
export const brandConfig = {
  schoolName: '演示职业技术学院',
  schoolShortName: '演示职院',
  platformDisplayName: '高校学生全生命周期管理平台',
  schoolLogo: '',
  schoolBadge: '',
  brandColor: '#2563eb',
  loginSlogan: '数字化成长档案，陪伴每一位学生',
  watermarkText: '演示职业技术学院 · 内部数据',
  watermarkDensity: '标准（24 块平铺 · 5% 透明度）',
  footerText: '技术支持：{{platformDisplayName}}',
  editableNote: '学校名称 / 校徽由平台运营侧在租户开通时核定，学校侧仅可修改展示简称、口号、水印与主色。'
}

export const importTemplatesList = [importTemplates.users, importTemplates.org]

/** 审计留痕（通用追加区，页面动作实时 push） */
export const auditLogs = [
  { id: 'au-001', who: '周文彬 · 学校管理员', time: '2026-07-04 10:22', action: '编辑角色「学院管理员」', affected: '按钮权限 +1 · 已通知复核人' },
  { id: 'au-002', who: '系统', time: '2026-07-04 03:00', action: '自动任务', affected: '30 天未登录账号自动停用 2 个（可恢复）' }
]
