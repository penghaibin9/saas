/**
 * 03 在校服务中心 — mock 数据源（内存态，可被 api 写操作变更）。
 * 口径来自《03-在校服务中心深化设计 V1.0》：服务工作台 / 服务工单池 / 请假管理 / 困难帮扶（奖助）/
 * 宿舍后勤 / 违纪处分 / 心理关怀（涉密收敛）。
 * 约定：
 *  - 学校名/平台名/Logo/水印/角色/数据范围全部由 tenantBrandConfig 与 roles 提供，页面禁止硬编码。
 *  - 删除一律逻辑作废（recordStatus = VOIDED），保留原因并写审计。
 *  - 家庭经济困难材料、心理记录为敏感数据：默认不展示明细，仅授权角色可见，查看/导出必须留痕并脱敏。
 *  - 页面禁止直接 import 本文件，必须经 modules/campusService/api 获取。
 */

export const nowText = () => {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

/* ---------------- 租户品牌（模拟后端下发） ---------------- */
export const tenantBrandConfig = {
  tenantId: 'tenant-demo-001',
  schoolName: '演示职业技术学院',
  platformDisplayName: '高校学生全生命周期管理平台',
  schoolLogo: '/assets/tenant/demo-logo.svg',
  schoolBadge: '/assets/tenant/demo-badge.svg',
  tenantBrandColor: '#2563EB',
  watermarkText: '演示职业技术学院 · 在校服务中心'
}

/* ---------------- 角色与数据范围（03 §4 使用角色） ---------------- */
export const roles = [
  {
    roleId: 'COUNSELOR',
    roleName: '辅导员',
    userName: '李敏',
    dataScope: { code: 'CLASS', name: '软件2301班 / 软件2302班' }
  },
  {
    roleId: 'COLLEGE_ADMIN',
    roleName: '学院管理员',
    userName: '张文澜',
    dataScope: { code: 'COLLEGE', name: '信息工程学院' }
  },
  {
    roleId: 'STU_AFFAIRS',
    roleName: '学工老师',
    userName: '王学工',
    dataScope: { code: 'SCHOOL', name: '全校（学工口径）' }
  },
  {
    roleId: 'DORM_MANAGER',
    roleName: '宿管老师',
    userName: '赵宿管',
    dataScope: { code: 'DORM', name: '3号宿舍楼 / 5号宿舍楼' }
  },
  {
    roleId: 'AID_TEACHER',
    roleName: '资助老师',
    userName: '陈资助',
    dataScope: { code: 'SCHOOL', name: '全校（资助口径）' }
  },
  {
    roleId: 'PSYCH_TEACHER',
    roleName: '心理老师',
    userName: '周心理',
    dataScope: { code: 'SCHOOL', name: '全校（心理口径 · 涉密）' }
  }
]

export const state = { currentRoleId: 'COUNSELOR' }

/* ---------------- 权限动作（按角色下发） ---------------- */
const FULL = {
  'campus.record.create': true,
  'campus.record.view': true,
  'campus.record.edit': true,
  'campus.record.void': true,
  'campus.record.import': true,
  'campus.record.export': true,
  'campus.record.batchRemind': true,
  'campus.leave.approve': true,
  'campus.leave.return': true,
  'campus.leave.batchApprove': true,
  'campus.leave.export': true,
  'campus.grant.review': true,
  'campus.grant.return': true,
  'campus.grant.batchReview': true,
  'campus.grant.export': true,
  'campus.grant.viewMaterial': true,
  'campus.dorm.create': true,
  'campus.dorm.edit': true,
  'campus.dorm.markException': true,
  'campus.dorm.handle': true,
  'campus.dorm.export': true,
  'campus.discipline.create': true,
  'campus.discipline.edit': true,
  'campus.discipline.void': true,
  'campus.discipline.export': true,
  'campus.mental.view': true,
  'campus.workorder.create': true,
  'campus.workorder.edit': true,
  'campus.workorder.assign': true,
  'campus.workorder.handle': true,
  'campus.workorder.close': true,
  'campus.workorder.export': true,
  'campus.audit.view': true,
  'campus.columns.setting': true
}

/**
 * allowed=false 且 visible=true → 置灰并提示原因；visible=false（hidden）→ 不渲染（涉密收敛）。
 */
export const permissionActionsByRole = {
  COUNSELOR: {
    actions: {
      ...FULL,
      'campus.record.import': false,
      'campus.grant.review': false,
      'campus.grant.return': false,
      'campus.grant.batchReview': false,
      'campus.grant.export': false,
      'campus.discipline.void': false,
      'campus.dorm.create': false,
      'campus.dorm.edit': false
    },
    hidden: ['campus.grant.viewMaterial', 'campus.mental.view'],
    disabledReason: '辅导员负责本班请假审批与服务跟进；资助审核由资助老师负责，宿舍台账由宿管维护'
  },
  COLLEGE_ADMIN: {
    actions: { ...FULL, 'campus.grant.review': false, 'campus.grant.return': false, 'campus.grant.batchReview': false },
    hidden: ['campus.grant.viewMaterial', 'campus.mental.view'],
    disabledReason: '资助审核为资助老师专属职责，学院管理员可查看台账与统计'
  },
  STU_AFFAIRS: {
    actions: FULL,
    hidden: ['campus.grant.viewMaterial', 'campus.mental.view'],
    disabledReason: ''
  },
  DORM_MANAGER: {
    actions: Object.fromEntries(
      Object.keys(FULL).map((k) => [
        k,
        k.startsWith('campus.dorm.') || k === 'campus.workorder.handle' || k === 'campus.columns.setting' || k === 'campus.audit.view'
      ])
    ),
    hidden: [
      'campus.record.import',
      'campus.record.export',
      'campus.record.void',
      'campus.leave.export',
      'campus.grant.export',
      'campus.grant.viewMaterial',
      'campus.discipline.export',
      'campus.mental.view',
      'campus.workorder.export'
    ],
    disabledReason: '宿管老师仅可维护所辖楼栋的住宿与异常记录，并处理分派到楼栋的工单'
  },
  AID_TEACHER: {
    actions: {
      ...FULL,
      'campus.record.create': false,
      'campus.record.edit': false,
      'campus.record.void': false,
      'campus.record.import': false,
      'campus.leave.approve': false,
      'campus.leave.return': false,
      'campus.leave.batchApprove': false,
      'campus.dorm.create': false,
      'campus.dorm.edit': false,
      'campus.dorm.markException': false,
      'campus.dorm.handle': false,
      'campus.discipline.create': false,
      'campus.discipline.edit': false,
      'campus.discipline.void': false,
      'campus.workorder.assign': false,
      'campus.workorder.close': false
    },
    hidden: ['campus.mental.view'],
    disabledReason: '资助老师专注奖助/资助审核与资助台账，其他业务仅可查看'
  },
  PSYCH_TEACHER: {
    actions: Object.fromEntries(
      Object.keys(FULL).map((k) => [
        k,
        k === 'campus.mental.view' || k === 'campus.workorder.handle' || k === 'campus.columns.setting' || k === 'campus.audit.view'
      ])
    ),
    hidden: [
      'campus.record.import',
      'campus.record.export',
      'campus.record.void',
      'campus.leave.export',
      'campus.grant.export',
      'campus.grant.viewMaterial',
      'campus.discipline.export',
      'campus.workorder.export'
    ],
    disabledReason: '心理老师仅可查看心理关怀记录并处理心理类工单，其他业务不可操作'
  }
}

/* ---------------- 字典 ---------------- */
export const statusOptions = {
  leaveType: [
    { value: 'SICK', label: '病假' },
    { value: 'PERSONAL', label: '事假' },
    { value: 'GOOUT', label: '外出报备' }
  ],
  leaveStatus: [
    { value: 'PENDING_REVIEW', label: '待审批' },
    { value: 'APPROVED', label: '已通过' },
    { value: 'RETURNED', label: '已退回' },
    { value: 'CANCELLED', label: '已销假' }
  ],
  grantType: [
    { value: 'NATIONAL_GRANT', label: '国家助学金' },
    { value: 'SCHOLARSHIP', label: '奖学金' },
    { value: 'HARDSHIP', label: '临时困难补助' },
    { value: 'TUITION_WAIVER', label: '学费减免' }
  ],
  grantStatus: [
    { value: 'PENDING_REVIEW', label: '待审核' },
    { value: 'REVIEWING', label: '审核中' },
    { value: 'APPROVED', label: '已通过' },
    { value: 'RETURNED', label: '退回补充' },
    { value: 'REJECTED', label: '不予通过' }
  ],
  dormStatus: [
    { value: 'IN', label: '在住' },
    { value: 'OUT', label: '已退宿' },
    { value: 'CHANGED', label: '已调宿' }
  ],
  dormExceptionType: [
    { value: 'NIGHT_OUT', label: '晚归' },
    { value: 'NO_RETURN', label: '夜不归宿' },
    { value: 'FACILITY', label: '设施报修' },
    { value: 'HYGIENE', label: '卫生不合格' },
    { value: 'DISCIPLINE', label: '宿舍违纪' }
  ],
  dormExceptionStatus: [
    { value: 'PENDING_HANDLE', label: '待处理' },
    { value: 'PROCESSING', label: '跟进中' },
    { value: 'COMPLETED', label: '已办结' }
  ],
  disciplineType: [
    { value: 'WARNING', label: '警告' },
    { value: 'SERIOUS_WARNING', label: '严重警告' },
    { value: 'DEMERIT', label: '记过' },
    { value: 'PROBATION', label: '留校察看' }
  ],
  disciplineStatus: [
    { value: 'EFFECTIVE', label: '生效中' },
    { value: 'REVOKED', label: '已解除' }
  ],
  workOrderType: [
    { value: 'CONSULT', label: '咨询' },
    { value: 'REPAIR', label: '报修' },
    { value: 'COMPLAINT', label: '投诉建议' },
    { value: 'CERT', label: '证明办理' },
    { value: 'CARE', label: '关怀转介' }
  ],
  workOrderStatus: [
    { value: 'PENDING_HANDLE', label: '待处理' },
    { value: 'PROCESSING', label: '处理中' },
    { value: 'COMPLETED', label: '已办结' },
    { value: 'CLOSED', label: '已关闭' }
  ],
  priority: [
    { value: 'HIGH', label: '高' },
    { value: 'MEDIUM', label: '中' },
    { value: 'LOW', label: '低' }
  ],
  careLevel: [
    { value: 'NORMAL', label: '常规' },
    { value: 'FOCUS', label: '重点关注' },
    { value: 'KEY_CARE', label: '重点关怀' }
  ],
  riskLevel: [
    { value: 'LOW', label: '低风险' },
    { value: 'MEDIUM', label: '中风险' },
    { value: 'HIGH', label: '高风险' }
  ],
  recordStatus: [
    { value: 'ACTIVE', label: '有效' },
    { value: 'VOIDED', label: '已作废' }
  ]
}

export const filterOptions = {
  colleges: [
    { value: 'C01', label: '信息工程学院' },
    { value: 'C02', label: '智能制造学院' }
  ],
  classes: [
    { value: 'CL01', label: '软件2301班' },
    { value: 'CL02', label: '软件2302班' },
    { value: 'CL03', label: '大数据2301班' },
    { value: 'CL04', label: '机电2301班' }
  ],
  buildings: [
    { value: 'B3', label: '3号宿舍楼' },
    { value: 'B5', label: '5号宿舍楼' },
    { value: 'B7', label: '7号宿舍楼' }
  ],
  handlers: [
    { value: 'u-limin', label: '李敏（辅导员）' },
    { value: 'u-wangxuegong', label: '王学工（学工老师）' },
    { value: 'u-zhaosuguan', label: '赵宿管（宿管老师）' },
    { value: 'u-zhouxinli', label: '周心理（心理老师）' }
  ]
}

/* ---------------- 列设置 ---------------- */
export const fieldColumns = {
  serviceList: [
    { key: 'name', title: '学生', locked: true, default: true },
    { key: 'className', title: '班级', default: true },
    { key: 'dorm', title: '宿舍', default: true },
    { key: 'leaveSummary', title: '请假', default: true },
    { key: 'grantSummary', title: '奖助', default: true },
    { key: 'disciplineSummary', title: '违纪处分', default: true },
    { key: 'workOrderSummary', title: '服务工单', default: true },
    { key: 'careLevel', title: '关怀级别', default: true },
    { key: 'risk', title: '风险', default: true },
    { key: 'phone', title: '手机号', sensitive: true, default: false },
    { key: 'counselor', title: '辅导员', default: false },
    { key: 'updateTime', title: '更新时间', default: false },
    { key: 'actions', title: '操作', locked: true, default: true }
  ],
  leaveList: [
    { key: 'code', title: '请假编号', locked: true, default: true },
    { key: 'name', title: '学生', default: true },
    { key: 'className', title: '班级', default: true },
    { key: 'type', title: '类型', default: true },
    { key: 'range', title: '起止时间', default: true },
    { key: 'duration', title: '时长', default: true },
    { key: 'reason', title: '事由', default: false },
    { key: 'status', title: '审批状态', default: true },
    { key: 'cancelStatus', title: '销假', default: true },
    { key: 'actions', title: '操作', locked: true, default: true }
  ],
  grantList: [
    { key: 'code', title: '申请编号', locked: true, default: true },
    { key: 'name', title: '学生', default: true },
    { key: 'className', title: '班级', default: true },
    { key: 'type', title: '申请类型', default: true },
    { key: 'amount', title: '金额', sensitive: true, default: true },
    { key: 'materialStatus', title: '材料', default: true },
    { key: 'status', title: '审核状态', default: true },
    { key: 'applyTime', title: '申请时间', default: true },
    { key: 'actions', title: '操作', locked: true, default: true }
  ],
  dormList: [
    { key: 'name', title: '学生', locked: true, default: true },
    { key: 'className', title: '班级', default: true },
    { key: 'building', title: '楼栋', default: true },
    { key: 'room', title: '房间 / 床位', default: true },
    { key: 'checkinDate', title: '入住时间', default: true },
    { key: 'status', title: '状态', default: true },
    { key: 'exceptionCount', title: '近30天异常', default: true },
    { key: 'actions', title: '操作', locked: true, default: true }
  ],
  disciplineList: [
    { key: 'code', title: '处分编号', locked: true, default: true },
    { key: 'name', title: '学生', default: true },
    { key: 'className', title: '班级', default: true },
    { key: 'type', title: '处分类型', default: true },
    { key: 'reason', title: '事由', default: true },
    { key: 'decideDate', title: '决定日期', default: true },
    { key: 'status', title: '状态', default: true },
    { key: 'actions', title: '操作', locked: true, default: true }
  ],
  workOrderList: [
    { key: 'code', title: '工单编号', locked: true, default: true },
    { key: 'title', title: '标题', default: true },
    { key: 'name', title: '学生', default: true },
    { key: 'type', title: '类型', default: true },
    { key: 'priority', title: '优先级', default: true },
    { key: 'handler', title: '处理人', default: true },
    { key: 'status', title: '状态', default: true },
    { key: 'overdue', title: 'SLA', default: true },
    { key: 'createTime', title: '发起时间', default: true },
    { key: 'actions', title: '操作', locked: true, default: true }
  ]
}

/* ---------------- 批量操作 ---------------- */
export const batchActions = {
  serviceList: [
    { key: 'batchRemind', label: '批量提醒', permission: 'campus.record.batchRemind' },
    { key: 'batchExport', label: '导出选中', permission: 'campus.record.export' }
  ],
  leaveList: [
    { key: 'batchApprove', label: '批量通过', permission: 'campus.leave.batchApprove' },
    { key: 'batchExport', label: '导出选中', permission: 'campus.leave.export' }
  ],
  grantList: [
    { key: 'batchApprove', label: '批量审核通过', permission: 'campus.grant.batchReview' },
    { key: 'batchExport', label: '导出选中', permission: 'campus.grant.export' }
  ],
  workOrderList: [
    { key: 'batchAssign', label: '批量分派', permission: 'campus.workorder.assign' },
    { key: 'batchExport', label: '导出选中', permission: 'campus.workorder.export' }
  ]
}

/* ---------------- 导入模板 ---------------- */
export const importTemplates = {
  serviceList: {
    key: 'serviceList',
    name: '在校学生服务台账导入模板',
    fileName: '在校服务学生导入模板.xlsx',
    fields: [
      { key: 'studentNo', label: '学号', required: true, example: '2023010101' },
      { key: 'name', label: '姓名', required: true, example: '张三' },
      { key: 'className', label: '班级', required: true, example: '软件2301班' },
      { key: 'building', label: '宿舍楼栋', required: false, example: '3号宿舍楼' },
      { key: 'room', label: '房间-床位', required: false, example: '312-2' }
    ]
  },
  dormList: {
    key: 'dormList',
    name: '住宿名单导入模板（后勤口径）',
    fileName: '住宿名单导入模板.xlsx',
    fields: [
      { key: 'studentNo', label: '学号', required: true, example: '2023010101' },
      { key: 'building', label: '楼栋', required: true, example: '3号宿舍楼' },
      { key: 'room', label: '房间', required: true, example: '312' },
      { key: 'bed', label: '床位', required: true, example: '2' },
      { key: 'checkinDate', label: '入住日期', required: false, example: '2025-09-01' }
    ]
  }
}

/* ---------------- 导出配置 ---------------- */
export const exportOptions = {
  scopes: [
    { value: 'FILTERED', label: '当前筛选结果' },
    { value: 'SELECTED', label: '仅选中记录' },
    { value: 'SCOPE_ALL', label: '数据范围内全部' }
  ],
  fieldGroups: {
    serviceList: [
      { key: 'base', label: '基础信息', fields: ['姓名', '学号', '班级', '宿舍'] },
      { key: 'service', label: '服务信息', fields: ['请假次数', '奖助状态', '处分记录', '工单数', '关怀级别'] },
      { key: 'sensitive', label: '敏感信息（默认脱敏）', sensitive: true, fields: ['手机号', '身份证号（仅脱敏）'] }
    ],
    leaveList: [
      { key: 'base', label: '请假记录', fields: ['编号', '学生', '班级', '类型', '起止时间', '时长', '审批状态', '销假状态'] }
    ],
    grantList: [
      { key: 'base', label: '资助台账', fields: ['编号', '学生', '班级', '申请类型', '审核状态', '申请时间'] },
      { key: 'sensitive', label: '敏感信息（默认脱敏）', sensitive: true, fields: ['金额（区间化）', '困难等级（仅授权角色）'] }
    ],
    dormList: [{ key: 'base', label: '住宿名单', fields: ['学生', '班级', '楼栋', '房间/床位', '入住时间', '状态'] }],
    disciplineList: [
      { key: 'base', label: '处分记录', fields: ['编号', '学生', '班级', '处分类型', '事由', '决定日期', '状态'] }
    ],
    workOrderList: [
      { key: 'base', label: '工单台账', fields: ['编号', '标题', '学生', '类型', '优先级', '处理人', '状态', '发起/办结时间'] }
    ]
  },
  maskDefault: true,
  idCardPlainForbidden: true,
  watermarkNote: '导出文件将自动嵌入水印（学校名 · 操作人 · 时间 · 用途），并写入审计日志。',
  auditNotice: '本次导出行为将被完整记录并可追溯，请确认导出用途合规。'
}

/* ---------------- 在校学生服务台账 ---------------- */
const STU = (id, name, no, classId, className, extras = {}) => ({
  id,
  studentId: id,
  name,
  studentNo: no,
  gender: extras.gender || '男',
  collegeId: extras.collegeId || 'C01',
  collegeName: extras.collegeName || '信息工程学院',
  majorName: extras.majorName || '软件技术',
  classId,
  className,
  grade: '2023级',
  phone: extras.phone || '13800001234',
  idCard: extras.idCard || '330102200501011234',
  counselor: extras.counselor || '李敏',
  buildingId: extras.buildingId || 'B3',
  building: extras.building || '3号宿舍楼',
  room: extras.room || '312-1',
  leaveCount: extras.leaveCount ?? 0,
  pendingLeave: extras.pendingLeave ?? 0,
  grantSummary: extras.grantSummary || '无申请',
  disciplineCount: extras.disciplineCount ?? 0,
  workOrderCount: extras.workOrderCount ?? 0,
  mentalFlag: extras.mentalFlag ?? false,
  careLevel: extras.careLevel || 'NORMAL',
  riskLevel: extras.riskLevel || 'LOW',
  recordStatus: 'ACTIVE',
  voidReason: '',
  updateTime: extras.updateTime || '2026-06-30 09:40'
})

export const serviceStudents = [
  STU('svc-s-001', '陈晓峰', '2023010101', 'CL01', '软件2301班', { room: '312-1', leaveCount: 1 }),
  STU('svc-s-002', '林嘉怡', '2023010102', 'CL01', '软件2301班', { gender: '女', room: '520-2', building: '5号宿舍楼', buildingId: 'B5', grantSummary: '奖学金 · 已通过' }),
  STU('svc-s-003', '赵子墨', '2023010103', 'CL01', '软件2301班', { room: '312-3', leaveCount: 3, pendingLeave: 1, careLevel: 'FOCUS', riskLevel: 'MEDIUM' }),
  STU('svc-s-004', '王雨桐', '2023010104', 'CL01', '软件2301班', {
    gender: '女', room: '521-1', building: '5号宿舍楼', buildingId: 'B5',
    leaveCount: 2, grantSummary: '国家助学金 · 审核中', mentalFlag: true, careLevel: 'KEY_CARE', riskLevel: 'HIGH',
    workOrderCount: 1, updateTime: '2026-07-01 16:00'
  }),
  STU('svc-s-005', '孙浩然', '2023010205', 'CL02', '软件2302班', { room: '318-2', disciplineCount: 1, careLevel: 'FOCUS', riskLevel: 'MEDIUM' }),
  STU('svc-s-006', '吴思远', '2023010206', 'CL02', '软件2302班', { room: '318-3' }),
  STU('svc-s-007', '郑婉婷', '2023010207', 'CL02', '软件2302班', {
    gender: '女', room: '522-4', building: '5号宿舍楼', buildingId: 'B5', grantSummary: '临时困难补助 · 待审核', careLevel: 'KEY_CARE', riskLevel: 'MEDIUM'
  }),
  STU('svc-s-008', '刘俊熙', '2023010208', 'CL02', '软件2302班', { room: '319-1', workOrderCount: 1, leaveCount: 1 }),
  STU('svc-s-009', '黄一诺', '2023020109', 'CL03', '大数据2301班', {
    gender: '女', majorName: '大数据技术', counselor: '钱辅导', room: '525-2', building: '5号宿舍楼', buildingId: 'B5', grantSummary: '奖学金 · 待审核'
  }),
  STU('svc-s-010', '徐博文', '2023020110', 'CL03', '大数据2301班', { majorName: '大数据技术', counselor: '钱辅导', room: '320-2', workOrderCount: 1 }),
  STU('svc-s-011', '高子轩', '2023030112', 'CL04', '机电2301班', {
    collegeId: 'C02', collegeName: '智能制造学院', majorName: '机电一体化', counselor: '孙辅导', room: '702-1', building: '7号宿舍楼', buildingId: 'B7'
  }),
  STU('svc-s-012', '罗芷晴', '2023030113', 'CL04', '机电2301班', {
    gender: '女', collegeId: 'C02', collegeName: '智能制造学院', majorName: '机电一体化', counselor: '孙辅导',
    room: '705-3', building: '7号宿舍楼', buildingId: 'B7', grantSummary: '学费减免 · 已通过', careLevel: 'FOCUS', riskLevel: 'MEDIUM', leaveCount: 2
  })
]

/* ---------------- 请假申请 ---------------- */
export const leaveApplications = [
  {
    id: 'svc-l-001', code: 'LV-2026-0812', studentId: 'svc-s-003', name: '赵子墨', classId: 'CL01', className: '软件2301班', collegeId: 'C01',
    type: 'SICK', startTime: '2026-07-03 08:00', endTime: '2026-07-04 18:00', duration: '2 天',
    reason: '发烧就医，附医院挂号单', attachments: ['挂号单.jpg'],
    status: 'PENDING_REVIEW', cancelStatus: '—', applyTime: '2026-07-02 21:40',
    reviewer: '', reviewTime: '', returnReason: '', conflictHint: '本学期第 3 次请假 · 近30天累计 4 天（触发频繁请假提示）',
    recordStatus: 'ACTIVE', voidReason: ''
  },
  {
    id: 'svc-l-002', code: 'LV-2026-0813', studentId: 'svc-s-004', name: '王雨桐', classId: 'CL01', className: '软件2301班', collegeId: 'C01',
    type: 'PERSONAL', startTime: '2026-07-05 08:00', endTime: '2026-07-05 18:00', duration: '1 天',
    reason: '家中有事需返家处理', attachments: [],
    status: 'PENDING_REVIEW', cancelStatus: '—', applyTime: '2026-07-02 19:10',
    reviewer: '', reviewTime: '', returnReason: '', conflictHint: '该生为重点关怀学生，请假期间请保持联系',
    recordStatus: 'ACTIVE', voidReason: ''
  },
  {
    id: 'svc-l-003', code: 'LV-2026-0798', studentId: 'svc-s-012', name: '罗芷晴', classId: 'CL04', className: '机电2301班', collegeId: 'C02',
    type: 'SICK', startTime: '2026-06-28 08:00', endTime: '2026-06-30 18:00', duration: '3 天',
    reason: '身体不适回家休养，附诊断证明', attachments: ['诊断证明.pdf'],
    status: 'APPROVED', cancelStatus: '已销假（06-30 19:02）', applyTime: '2026-06-27 20:15',
    reviewer: '孙辅导', reviewTime: '2026-06-27 21:00', returnReason: '', conflictHint: '',
    recordStatus: 'ACTIVE', voidReason: ''
  },
  {
    id: 'svc-l-004', code: 'LV-2026-0801', studentId: 'svc-s-008', name: '刘俊熙', classId: 'CL02', className: '软件2302班', collegeId: 'C01',
    type: 'GOOUT', startTime: '2026-06-29 13:00', endTime: '2026-06-29 17:00', duration: '4 小时',
    reason: '外出参加校外技能竞赛集训', attachments: [],
    status: 'RETURNED', cancelStatus: '—', applyTime: '2026-06-29 08:30',
    reviewer: '李敏', reviewTime: '2026-06-29 09:00', returnReason: '外出报备需附集训通知或带队老师确认，请补充材料后重新提交', conflictHint: '',
    recordStatus: 'ACTIVE', voidReason: ''
  },
  {
    id: 'svc-l-005', code: 'LV-2026-0779', studentId: 'svc-s-001', name: '陈晓峰', classId: 'CL01', className: '软件2301班', collegeId: 'C01',
    type: 'PERSONAL', startTime: '2026-06-20 08:00', endTime: '2026-06-20 18:00', duration: '1 天',
    reason: '办理身份证换领', attachments: [],
    status: 'APPROVED', cancelStatus: '已销假（06-20 19:40）', applyTime: '2026-06-19 17:20',
    reviewer: '李敏', reviewTime: '2026-06-19 18:05', returnReason: '', conflictHint: '',
    recordStatus: 'ACTIVE', voidReason: ''
  }
]

/* ---------------- 奖助 / 资助申请 ---------------- */
export const grantApplications = [
  {
    id: 'svc-g-001', code: 'GR-2026-0231', studentId: 'svc-s-004', name: '王雨桐', classId: 'CL01', className: '软件2301班', collegeId: 'C01',
    type: 'NATIONAL_GRANT', amount: 3300, amountRange: '3000-4000 元',
    applyReason: '家庭经济困难，父亲患病治疗中', materialStatus: '已提交（3 份）', materialSensitive: true,
    status: 'REVIEWING', applyTime: '2026-06-18 10:20', reviewer: '陈资助', reviewTime: '', returnReason: '',
    currentNode: '资助老师审核', recordStatus: 'ACTIVE', voidReason: ''
  },
  {
    id: 'svc-g-002', code: 'GR-2026-0245', studentId: 'svc-s-007', name: '郑婉婷', classId: 'CL02', className: '软件2302班', collegeId: 'C01',
    type: 'HARDSHIP', amount: 1500, amountRange: '1000-2000 元',
    applyReason: '家中突发变故，申请临时困难补助', materialStatus: '已提交（2 份）', materialSensitive: true,
    status: 'PENDING_REVIEW', applyTime: '2026-06-30 15:40', reviewer: '', reviewTime: '', returnReason: '',
    currentNode: '待资助老师领取', recordStatus: 'ACTIVE', voidReason: ''
  },
  {
    id: 'svc-g-003', code: 'GR-2026-0198', studentId: 'svc-s-002', name: '林嘉怡', classId: 'CL01', className: '软件2301班', collegeId: 'C01',
    type: 'SCHOLARSHIP', amount: 2000, amountRange: '2000-3000 元',
    applyReason: '综合测评班级第一，申请校级奖学金', materialStatus: '已提交（1 份）', materialSensitive: false,
    status: 'APPROVED', applyTime: '2026-06-10 09:00', reviewer: '陈资助', reviewTime: '2026-06-15 14:30', returnReason: '',
    currentNode: '已办结', recordStatus: 'ACTIVE', voidReason: ''
  },
  {
    id: 'svc-g-004', code: 'GR-2026-0250', studentId: 'svc-s-009', name: '黄一诺', classId: 'CL03', className: '大数据2301班', collegeId: 'C01',
    type: 'SCHOLARSHIP', amount: 2000, amountRange: '2000-3000 元',
    applyReason: '学业成绩专业第一，申请校级奖学金', materialStatus: '待补充（成绩单缺章）', materialSensitive: false,
    status: 'RETURNED', applyTime: '2026-06-28 11:10', reviewer: '陈资助', reviewTime: '2026-06-29 10:00',
    returnReason: '成绩单缺教务处盖章，请补盖后重新上传', currentNode: '学生补充材料', recordStatus: 'ACTIVE', voidReason: ''
  },
  {
    id: 'svc-g-005', code: 'GR-2026-0187', studentId: 'svc-s-012', name: '罗芷晴', classId: 'CL04', className: '机电2301班', collegeId: 'C02',
    type: 'TUITION_WAIVER', amount: 6000, amountRange: '6000 元（学年）',
    applyReason: '建档立卡家庭，申请学费减免', materialStatus: '已提交（4 份）', materialSensitive: true,
    status: 'APPROVED', applyTime: '2026-05-20 09:30', reviewer: '陈资助', reviewTime: '2026-05-28 16:00', returnReason: '',
    currentNode: '已办结', recordStatus: 'ACTIVE', voidReason: ''
  }
]

/* ---------------- 宿舍住宿与异常 ---------------- */
export const dormitoryRecords = serviceStudents.map((s, i) => ({
  id: `svc-d-${String(i + 1).padStart(3, '0')}`,
  studentId: s.id,
  name: s.name,
  classId: s.classId,
  className: s.className,
  collegeId: s.collegeId,
  buildingId: s.buildingId,
  building: s.building,
  room: s.room.split('-')[0],
  bed: s.room.split('-')[1] || '1',
  checkinDate: '2025-09-01',
  status: 'IN',
  exceptionCount: ['svc-s-003', 'svc-s-005'].includes(s.id) ? 2 : ['svc-s-004'].includes(s.id) ? 1 : 0,
  recordStatus: 'ACTIVE',
  voidReason: '',
  updateTime: '2026-06-30 08:00'
}))

export const dormitoryExceptionRecords = [
  {
    id: 'svc-de-001', code: 'DE-2026-0092', studentId: 'svc-s-003', name: '赵子墨', className: '软件2301班', collegeId: 'C01',
    buildingId: 'B3', building: '3号宿舍楼', room: '312', type: 'NIGHT_OUT', typeLabel: '晚归',
    happenTime: '2026-07-01 23:40', detail: '门禁记录 23:40 入楼（规定 22:30），本月第 2 次',
    status: 'PENDING_HANDLE', handler: '', handleNote: '', handleTime: '',
    recordStatus: 'ACTIVE', voidReason: ''
  },
  {
    id: 'svc-de-002', code: 'DE-2026-0093', studentId: 'svc-s-005', name: '孙浩然', className: '软件2302班', collegeId: 'C01',
    buildingId: 'B3', building: '3号宿舍楼', room: '318', type: 'NO_RETURN', typeLabel: '夜不归宿',
    happenTime: '2026-06-29', detail: '晚点名未到，门禁无入楼记录，已电话确认在校外同学处留宿',
    status: 'PROCESSING', handler: '李敏（辅导员）', handleNote: '已联系学生与家长，明日面谈', handleTime: '2026-06-30 09:10',
    recordStatus: 'ACTIVE', voidReason: ''
  },
  {
    id: 'svc-de-003', code: 'DE-2026-0088', studentId: 'svc-s-004', name: '王雨桐', className: '软件2301班', collegeId: 'C01',
    buildingId: 'B5', building: '5号宿舍楼', room: '521', type: 'FACILITY', typeLabel: '设施报修',
    happenTime: '2026-06-28 20:15', detail: '宿舍空调故障，室温过高影响休息',
    status: 'COMPLETED', handler: '赵宿管（宿管老师）', handleNote: '已联系维修师傅更换电容，验收正常', handleTime: '2026-06-29 15:30',
    recordStatus: 'ACTIVE', voidReason: ''
  },
  {
    id: 'svc-de-004', code: 'DE-2026-0095', studentId: 'svc-s-011', name: '高子轩', className: '机电2301班', collegeId: 'C02',
    buildingId: 'B7', building: '7号宿舍楼', room: '702', type: 'HYGIENE', typeLabel: '卫生不合格',
    happenTime: '2026-06-30 10:00', detail: '周检卫生评分 62 分（合格线 75），垃圾未及时清理',
    status: 'PENDING_HANDLE', handler: '', handleNote: '', handleTime: '',
    recordStatus: 'ACTIVE', voidReason: ''
  }
]

/* ---------------- 违纪 / 处分记录 ---------------- */
export const disciplineRecords = [
  {
    id: 'svc-dis-001', code: 'DIS-2026-0012', studentId: 'svc-s-005', name: '孙浩然', classId: 'CL02', className: '软件2302班', collegeId: 'C01',
    type: 'WARNING', reason: '多次夜不归宿且未报备（宿舍违纪）', decideDate: '2026-06-30', docNo: '学字〔2026〕12 号',
    status: 'EFFECTIVE', revokeDate: '', revokeReason: '',
    recordStatus: 'ACTIVE', voidReason: '', operator: '王学工', updateTime: '2026-06-30 17:20'
  },
  {
    id: 'svc-dis-002', code: 'DIS-2025-0047', studentId: 'svc-s-003', name: '赵子墨', classId: 'CL01', className: '软件2301班', collegeId: 'C01',
    type: 'WARNING', reason: '考试作弊（夹带资料）', decideDate: '2025-12-20', docNo: '学字〔2025〕47 号',
    status: 'REVOKED', revokeDate: '2026-06-20', revokeReason: '察看期内表现良好，按程序解除',
    recordStatus: 'ACTIVE', voidReason: '', operator: '王学工', updateTime: '2026-06-20 10:00'
  }
]

/* ---------------- 心理关怀记录（涉密：仅授权角色可见明细） ---------------- */
export const mentalHealthRecords = [
  {
    id: 'svc-m-001', studentId: 'svc-s-004', name: '王雨桐', className: '软件2301班',
    level: 'FOCUS', levelLabel: '重点关注',
    lastFollowTime: '2026-06-26 16:00', nextFollowTime: '2026-07-06',
    summary: '情绪低落伴学业压力，已安排每两周一次咨询',
    counselorNote: '（涉密内容，仅心理老师可见完整记录）',
    operator: '周心理（心理老师）', status: 'PROCESSING', recordStatus: 'ACTIVE'
  },
  {
    id: 'svc-m-002', studentId: 'svc-s-007', name: '郑婉婷', className: '软件2302班',
    level: 'NORMAL', levelLabel: '常规关注',
    lastFollowTime: '2026-06-15 10:00', nextFollowTime: '—',
    summary: '家庭变故后的适应性访谈，状态平稳',
    counselorNote: '（涉密内容，仅心理老师可见完整记录）',
    operator: '周心理（心理老师）', status: 'COMPLETED', recordStatus: 'ACTIVE'
  }
]

/* ---------------- 服务工单 ---------------- */
export const serviceWorkOrders = [
  {
    id: 'svc-w-001', code: 'WO-2026-1102', title: '申请在读证明（英文版）', studentId: 'svc-s-010', name: '徐博文', classId: 'CL03', className: '大数据2301班', collegeId: 'C01',
    type: 'CERT', priority: 'MEDIUM', handlerId: 'u-wangxuegong', handler: '王学工（学工老师）',
    status: 'PROCESSING', overdue: false, slaHint: '剩余 1 天 6 小时',
    createTime: '2026-07-01 09:20', updateTime: '2026-07-02 10:00', closeTime: '',
    detail: '出国交换项目需要英文在读证明，希望本周内取件。',
    recordStatus: 'ACTIVE', voidReason: ''
  },
  {
    id: 'svc-w-002', code: 'WO-2026-1105', title: '宿舍楼道灯不亮报修', studentId: 'svc-s-008', name: '刘俊熙', classId: 'CL02', className: '软件2302班', collegeId: 'C01',
    type: 'REPAIR', priority: 'HIGH', handlerId: 'u-zhaosuguan', handler: '赵宿管（宿管老师）',
    status: 'PENDING_HANDLE', overdue: true, slaHint: '已逾期 5 小时',
    createTime: '2026-07-01 22:10', updateTime: '2026-07-01 22:10', closeTime: '',
    detail: '3号楼三层楼道灯连续两晚不亮，夜间出入存在安全隐患。',
    recordStatus: 'ACTIVE', voidReason: ''
  },
  {
    id: 'svc-w-003', code: 'WO-2026-1096', title: '咨询学费减免政策', studentId: 'svc-s-012', name: '罗芷晴', classId: 'CL04', className: '机电2301班', collegeId: 'C02',
    type: 'CONSULT', priority: 'LOW', handlerId: 'u-wangxuegong', handler: '王学工（学工老师）',
    status: 'COMPLETED', overdue: false, slaHint: '按时办结',
    createTime: '2026-06-25 14:00', updateTime: '2026-06-26 09:30', closeTime: '2026-06-26 09:30',
    detail: '想了解下学年学费减免的申请条件与材料清单。',
    recordStatus: 'ACTIVE', voidReason: ''
  },
  {
    id: 'svc-w-004', code: 'WO-2026-1108', title: '情绪低落希望预约心理咨询', studentId: 'svc-s-004', name: '王雨桐', classId: 'CL01', className: '软件2301班', collegeId: 'C01',
    type: 'CARE', priority: 'HIGH', handlerId: 'u-zhouxinli', handler: '周心理（心理老师）',
    status: 'PROCESSING', overdue: false, slaHint: '剩余 8 小时',
    createTime: '2026-07-02 20:40', updateTime: '2026-07-03 08:30', closeTime: '',
    detail: '（关怀转介）学生主动预约心理咨询，内容涉密，仅心理老师可见完整描述。',
    recordStatus: 'ACTIVE', voidReason: ''
  }
]

export const workOrderTrails = {
  'svc-w-001': [
    { title: '学生提交工单（小程序服务大厅）', desc: '', time: '2026-07-01 09:20', tone: 'processing' },
    { title: '王学工 · 领取处理', desc: '已登记，证明预计 07-03 可取', time: '2026-07-02 10:00', tone: 'processing' }
  ],
  'svc-w-002': [{ title: '学生提交报修（小程序宿舍维修）', desc: '附楼道照片 2 张', time: '2026-07-01 22:10', tone: 'warning' }],
  'svc-w-003': [
    { title: '学生提交咨询', desc: '', time: '2026-06-25 14:00', tone: 'processing' },
    { title: '王学工 · 回复并办结', desc: '已推送《学费减免申请指引》，学生确认满意', time: '2026-06-26 09:30', tone: 'success' }
  ],
  'svc-w-004': [
    { title: '学生发起关怀预约', desc: '来源：小程序心理服务入口', time: '2026-07-02 20:40', tone: 'warning' },
    { title: '周心理 · 领取并预约面谈', desc: '面谈时间 07-04 15:00（涉密）', time: '2026-07-03 08:30', tone: 'processing' }
  ]
}

/* ---------------- 审计日志 ---------------- */
export const auditLogs = [
  {
    id: 'svc-a-001', time: '2026-06-29 09:00', operator: '李敏', roleName: '辅导员',
    bizType: 'LEAVE', bizId: 'svc-l-004', action: '退回请假申请',
    detail: '退回 LV-2026-0801：外出报备需附集训通知（原因已同步学生端）', before: 'PENDING_REVIEW', after: 'RETURNED'
  },
  {
    id: 'svc-a-002', time: '2026-06-29 10:00', operator: '陈资助', roleName: '资助老师',
    bizType: 'GRANT', bizId: 'svc-g-004', action: '退回资助申请',
    detail: '退回 GR-2026-0250：成绩单缺教务处盖章', before: 'PENDING_REVIEW', after: 'RETURNED'
  },
  {
    id: 'svc-a-003', time: '2026-06-29 15:30', operator: '赵宿管', roleName: '宿管老师',
    bizType: 'DORM_EXCEPTION', bizId: 'svc-de-003', action: '办结宿舍异常',
    detail: '5号楼521空调报修：更换电容并验收（DE-2026-0088）', before: 'PROCESSING', after: 'COMPLETED'
  },
  {
    id: 'svc-a-004', time: '2026-06-30 17:20', operator: '王学工', roleName: '学工老师',
    bizType: 'DISCIPLINE', bizId: 'svc-dis-001', action: '新增处分记录',
    detail: '孙浩然 · 警告（学字〔2026〕12 号），已按流程告知学生并进入学生360', before: '', after: 'EFFECTIVE'
  },
  {
    id: 'svc-a-005', time: '2026-06-26 09:30', operator: '王学工', roleName: '学工老师',
    bizType: 'WORKORDER', bizId: 'svc-w-003', action: '办结工单',
    detail: 'WO-2026-1096 咨询学费减免政策：已回复并办结，学生评价满意', before: 'PROCESSING', after: 'COMPLETED'
  },
  {
    id: 'svc-a-006', time: '2026-06-15 14:30', operator: '陈资助', roleName: '资助老师',
    bizType: 'EXPORT', bizId: 'grantList', action: '导出资助台账',
    detail: '导出资助台账 5 条（金额区间化、材料明细未包含，含水印）', before: '', after: ''
  }
]

/* ---------------- 看板 ---------------- */
export const dashboardSummary = {
  termName: '2025-2026 学年第二学期',
  termRange: '2026-02-23 ~ 2026-07-12',
  updateTime: '2026-07-03 08:30',
  flow: [
    { label: '学生申请', value: 4 },
    { label: '待处理', value: 4, active: true },
    { label: '处理中', value: 3 },
    { label: '已办结', value: 3 },
    { label: '已归档', value: 0 }
  ],
  hotServices: [
    { name: '请假申请', count: 5, trend: '+2 本周' },
    { name: '证明办理', count: 3, trend: '持平' },
    { name: '宿舍报修', count: 2, trend: '+1 本周' },
    { name: '资助咨询', count: 2, trend: '持平' }
  ],
  riskAlerts: [
    { id: 'svc-ra-001', level: 'HIGH', title: '1 个高优先级报修工单已逾期（3号楼楼道灯）', link: 'workorders' },
    { id: 'svc-ra-002', level: 'MEDIUM', title: '1 名重点关怀学生提交请假申请，请假期间需保持联系', link: 'leave' },
    { id: 'svc-ra-003', level: 'MEDIUM', title: '赵子墨 触发频繁请假提示（本学期第 3 次）', link: 'leave' }
  ],
  todos: [
    { id: 'svc-t-001', label: '待审批请假', value: 2, link: 'leave' },
    { id: 'svc-t-002', label: '待审核资助申请', value: 2, link: 'grants' },
    { id: 'svc-t-003', label: '待处理宿舍异常', value: 2, link: 'dorm' },
    { id: 'svc-t-004', label: '待处理服务工单', value: 1, link: 'workorders' }
  ]
}
