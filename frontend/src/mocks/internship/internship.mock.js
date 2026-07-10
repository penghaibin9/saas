/**
 * 岗位实习中心 mock 数据（06 反向建模 V1.0 口径）。
 * 剧本与 mocks/db.js 保持同一世界观（赵一凡 / 刘强 / 李敏 / 华信智能 / 星辰网络）。
 * 页面禁止直接 import 本文件，必须经 modules/internship/api 获取。
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

/** 当前登录角色（mock：实习指导教师视角，体现权限差异） */
export const currentRole = {
  userId: 't-002',
  userName: '刘强',
  roleCode: 'INTERN_ADVISOR',
  roleName: '实习指导教师'
}

export const dataScope = {
  scopeCode: 'INTERN_STUDENTS',
  scopeName: '我指导的实习学生（8 人）'
}

/**
 * 权限动作表：allowed=false 且 visible=true 时按钮置灰并提示 reason；
 * visible=false 时按钮不渲染（涉密入口）。
 */
export const permissionActions = {
  createBatch: { visible: true, allowed: false, reason: '新增实习批次需「学院管理员」角色' },
  importStudents: { visible: true, allowed: false, reason: '批量导入需「学院管理员」角色' },
  exportGroup: { visible: true, allowed: true, reason: '' },
  exportAll: { visible: false, allowed: false, reason: '全院导出仅学院管理员可见' },
  viewAuditLog: { visible: true, allowed: true, reason: '' },
  createStudent: { visible: true, allowed: false, reason: '新增实习学生需「学院管理员」角色' },
  batchAssignAdvisor: { visible: true, allowed: false, reason: '批量分配指导老师需「学院管理员」角色' },
  batchRemind: { visible: true, allowed: true, reason: '' },
  batchArchive: { visible: false, allowed: false, reason: '归档仅学院管理员可见' },
  editStudent: { visible: true, allowed: false, reason: '编辑实习信息需「学院管理员」角色' },
  handleException: { visible: true, allowed: true, reason: '' },
  batchMarkReasonable: { visible: true, allowed: true, reason: '' },
  exportExceptions: { visible: true, allowed: true, reason: '' },
  reviewReport: { visible: true, allowed: true, reason: '' },
  batchApproveReports: { visible: true, allowed: true, reason: '' },
  exportReports: { visible: true, allowed: true, reason: '' },
  manageRisk: { visible: true, allowed: true, reason: '' },
  exportRiskList: { visible: true, allowed: true, reason: '仅限本组学生名单，含水印' },
  createEnterprise: { visible: true, allowed: true, reason: '' },
  editEnterprise: { visible: true, allowed: true, reason: '' },
  reviewEnterprise: { visible: true, allowed: false, reason: '企业资质审核需「实习管理员 / 学院实习负责人」角色' },
  cooperationEnterprise: { visible: true, allowed: true, reason: '' },
  blacklistEnterprise: { visible: true, allowed: false, reason: '拉黑/移出黑名单需「实习管理员」角色' },
  importEnterprises: { visible: true, allowed: true, reason: '' },
  exportEnterprises: { visible: true, allowed: true, reason: '导出字段脱敏、含水印、写审计' },
  manageEnterpriseContact: { visible: true, allowed: true, reason: '' }
}

export const statusOptions = {
  internshipStatus: [
    { value: 'PREPARING', label: '准备中' },
    { value: 'READY', label: '待上岗' },
    { value: 'ONBOARD', label: '在岗中' },
    { value: 'ASSESSING', label: '考核中' },
    { value: 'ARCHIVED', label: '已归档' }
  ],
  riskLevel: [
    { value: 'LOW', label: '低风险' },
    { value: 'MEDIUM', label: '中风险' },
    { value: 'HIGH', label: '高风险' }
  ],
  exceptionType: [
    { value: 'OUT_OF_RANGE', label: '超范围' },
    { value: 'MOCK_LOCATION', label: '模拟定位' },
    { value: 'MISSING', label: '缺卡' }
  ],
  reportStatus: [
    { value: 'PENDING_REVIEW', label: '待批阅' },
    { value: 'APPROVED', label: '已通过' },
    { value: 'RETURNED', label: '已退回' },
    { value: 'OVERDUE', label: '逾期未交' }
  ],
  classes: [
    { value: 'c-2301', label: '软件2301' },
    { value: 'c-2302', label: '软件2302' }
  ],
  enterprises: [
    { value: 'ent-001', label: '华信智能科技有限公司' },
    { value: 'ent-002', label: '星辰网络技术有限公司' }
  ],
  coopStatus: [
    { value: 'PENDING', label: '待审核' },
    { value: 'ACTIVE', label: '合作中' },
    { value: 'REJECTED', label: '已驳回' },
    { value: 'SUSPENDED', label: '已暂停' },
    { value: 'BLACKLIST', label: '黑名单' },
    { value: 'ARCHIVED', label: '已归档' }
  ],
  enterpriseSource: [
    { value: 'SELF_BUILT', label: '自建' },
    { value: 'SCHOOL_ENTERPRISE', label: '校企合作' },
    { value: 'STUDENT_SELF', label: '学生自主' },
    { value: 'RECOMMENDED', label: '推荐' }
  ],
  enterpriseIndustry: [
    { value: '软件', label: '软件' },
    { value: '智能制造', label: '智能制造' },
    { value: '电子商务', label: '电子商务' },
    { value: '现代物流', label: '现代物流' }
  ],
  batchStatus: [
    { value: 'DRAFT', label: '草稿' },
    { value: 'RUNNING', label: '进行中' },
    { value: 'CLOSED', label: '已结束' },
    { value: 'ARCHIVED', label: '已归档' },
    { value: 'VOIDED', label: '已作废' }
  ]
}

/** 默认阶段时间轴 / 规则配置（新建批次未指定时，与后端默认值一致） */
export const defaultBatchStages = [
  { code: 'PREP', name: '岗前准备', startDate: '', endDate: '' },
  { code: 'ONBOARD', name: '在岗实习', startDate: '', endDate: '' },
  { code: 'REVIEW', name: '总结考核', startDate: '', endDate: '' }
]
export const defaultBatchRules = {
  checkin: { requireDaily: true, geofenceRadiusM: 500, allowedExceptionTypes: ['OUT_OF_RANGE', 'MOCK_LOCATION', 'MISSING'] },
  weeklyReport: { frequency: 'WEEKLY', minWordCount: 800, deadlineWeekday: 7 },
  guidance: { minVisitsPerTerm: 2, minCommunicationsPerMonth: 2 },
  evaluation: { enterpriseWeight: 0.4, teacherWeight: 0.4, selfWeight: 0.2 },
  score: { passThreshold: 60, components: [{ name: '企业评价', weight: 0.4 }, { name: '教师评价', weight: 0.4 }, { name: '考核成绩', weight: 0.2 }] }
}

/** 实习批次列表（组织时间轴 + 状态机 DRAFT→RUNNING→CLOSED→ARCHIVED） */
export const internshipBatches = [
  {
    id: 'batch-001', batchName: '2026 届春季岗位实习', batchNo: 'INT-2026S',
    academicYear: '2025-2026', term: '第二学期',
    startDate: '2026-03-02', endDate: '2026-08-28',
    signupStartDate: '2026-02-01', signupEndDate: '2026-02-20',
    plannedCount: 120, actualCount: 8, status: 'RUNNING', statusLabel: '进行中',
    archiveStatus: 'NOT_ARCHIVED', remark: '与专业课教学计划同步', updateTime: '2026-07-01 09:00'
  },
  {
    id: 'batch-002', batchName: '2025 届秋季岗位实习', batchNo: 'INT-2025F',
    academicYear: '2025-2026', term: '第一学期',
    startDate: '2025-09-01', endDate: '2026-01-15',
    signupStartDate: '2025-08-10', signupEndDate: '2025-08-25',
    plannedCount: 110, actualCount: 104, status: 'ARCHIVED', statusLabel: '已归档',
    archiveStatus: 'ARCHIVED', remark: '', updateTime: '2026-01-20 14:30'
  },
  {
    id: 'batch-003', batchName: '2026 届暑期岗位实习（草案）', batchNo: 'INT-2026SUM',
    academicYear: '2025-2026', term: '暑期',
    startDate: '2026-07-15', endDate: '2026-08-31',
    signupStartDate: '', signupEndDate: '',
    plannedCount: 40, actualCount: 0, status: 'DRAFT', statusLabel: '草稿',
    archiveStatus: 'NOT_ARCHIVED', remark: '待学院实习负责人确认规则后启用', updateTime: '2026-07-05 16:12'
  }
]

export const internshipBatchDetailMap = {
  'batch-001': {
    ...internshipBatches[0],
    stages: [
      { code: 'PREP', name: '岗前准备', startDate: '2026-03-02', endDate: '2026-03-08' },
      { code: 'ONBOARD', name: '在岗实习', startDate: '2026-03-09', endDate: '2026-08-15' },
      { code: 'REVIEW', name: '总结考核', startDate: '2026-08-16', endDate: '2026-08-28' }
    ],
    rules: defaultBatchRules,
    previousStatus: 'DRAFT', lastTransitionAt: '2026-02-25 10:00', lastTransitionBy: '刘强',
    transitionReason: '', archivedAt: '', archivedBy: '', archiveBatchNo: '',
    auditTrail: [
      { id: 'at-1', action: 'CREATE', operator: '刘强', time: '2026-02-20 09:00', detail: '{"batchName":"2026 届春季岗位实习"}' },
      { id: 'at-2', action: 'ACTIVATE', operator: '刘强', time: '2026-02-25 10:00', detail: '{"before":"DRAFT","after":"RUNNING"}' }
    ]
  },
  'batch-002': {
    ...internshipBatches[1],
    stages: defaultBatchStages,
    rules: defaultBatchRules,
    previousStatus: 'CLOSED', lastTransitionAt: '2026-01-20 14:30', lastTransitionBy: '刘强',
    transitionReason: '', archivedAt: '2026-01-20 14:30', archivedBy: '刘强', archiveBatchNo: 'INT-2025F',
    auditTrail: [
      { id: 'at-3', action: 'CLOSE', operator: '刘强', time: '2026-01-15 18:00', detail: '{"before":"RUNNING","after":"CLOSED"}' },
      { id: 'at-4', action: 'ARCHIVE', operator: '刘强', time: '2026-01-20 14:30', detail: '{"before":"CLOSED","after":"ARCHIVED"}' }
    ]
  },
  'batch-003': {
    ...internshipBatches[2],
    stages: defaultBatchStages,
    rules: defaultBatchRules,
    previousStatus: '', lastTransitionAt: '', lastTransitionBy: '',
    transitionReason: '', archivedAt: '', archivedBy: '', archiveBatchNo: '',
    auditTrail: [
      { id: 'at-5', action: 'CREATE', operator: '刘强', time: '2026-07-05 16:12', detail: '{"batchName":"2026 届暑期岗位实习（草案）"}' }
    ]
  }
}

export const dashboardSummary = {
  batchName: '2026 届春季实习批次',
  batchRange: '2026-03-02 ~ 2026-08-28',
  batchStatus: '进行中',
  stats: [
    { label: '在岗学生', value: '8', trend: '', trendQuality: 'neutral' },
    { label: '今日打卡率', value: '87.5%', trend: '▲ 较昨日 +12.5%', trendQuality: 'good' },
    { label: '本周周报提交率', value: '75.0%', trend: '▼ 较上周 -12.5%', trendQuality: 'bad' },
    { label: '待处理打卡异常', value: '3', trend: '今日新增 1', trendQuality: 'neutral' },
    { label: '风险学生', value: '2', trend: '高风险 1', trendQuality: 'bad' }
  ],
  flow: [
    { label: '准备中', value: 0 },
    { label: '待上岗', value: 1 },
    { label: '在岗中', value: 6, active: true },
    { label: '考核中', value: 1 },
    { label: '已归档', value: 0 }
  ],
  todos: [
    { id: 'todo-1', label: '待批阅周报', count: 2, tone: 'danger', hint: '最早提交于 2 天前', route: '/admin/internship/reports' },
    { id: 'todo-2', label: '待核实打卡异常', count: 3, tone: 'warning', hint: '含模拟定位命中 1 条', route: '/admin/internship/exceptions' },
    { id: 'todo-3', label: '风险学生待跟进', count: 2, tone: 'warning', hint: '1 人临近处理期限', route: '/admin/internship/risks' }
  ],
  riskAlerts: [
    { id: 'ra-1', code: 'INT-R07', level: 'HIGH', title: '连续 3 天打卡异常', detail: '赵一凡（软件2301）· 已自动生成风险单', time: '今天 08:00' },
    { id: 'ra-2', code: 'INT-R10', level: 'MEDIUM', title: '第 4 周周报未提交', detail: '赵一凡（软件2301）· 已催办 1 次', time: '昨天 18:00' }
  ]
}

/** 实习学生列表（当前数据范围内 8 人） */
export const internshipStudents = [
  {
    id: 'int-001', studentId: 'stu-001', name: '赵一凡', studentNo: 'S2026-000001',
    className: '软件2301', classId: 'c-2301',
    enterpriseId: 'ent-001', enterpriseName: '华信智能科技有限公司', positionName: '前端开发实习生',
    advisorName: '刘强', enterpriseMentor: '周工',
    status: 'ONBOARD', statusLabel: '在岗中',
    checkinSummary: '连续 3 天异常', checkinTone: 'danger',
    reportSummary: '3/4 周', riskLevel: 'HIGH',
    phone: '13512346867'
  },
  {
    id: 'int-002', studentId: 'stu-006', name: '林晓彤', studentNo: 'S2026-000006',
    className: '软件2301', classId: 'c-2301',
    enterpriseId: 'ent-001', enterpriseName: '华信智能科技有限公司', positionName: '测试实习生',
    advisorName: '刘强', enterpriseMentor: '周工',
    status: 'ONBOARD', statusLabel: '在岗中',
    checkinSummary: '正常', checkinTone: 'success',
    reportSummary: '4/4 周', riskLevel: 'NONE',
    phone: '15912348873'
  },
  {
    id: 'int-003', studentId: 'stu-007', name: '陈志远', studentNo: 'S2026-000007',
    className: '软件2302', classId: 'c-2302',
    enterpriseId: 'ent-002', enterpriseName: '星辰网络技术有限公司', positionName: '运维实习生',
    advisorName: '刘强', enterpriseMentor: '吴经理',
    status: 'ONBOARD', statusLabel: '在岗中（请假旁路）',
    checkinSummary: '请假 3 天', checkinTone: 'warning',
    reportSummary: '3/4 周', riskLevel: 'MEDIUM',
    phone: '13712345460'
  },
  {
    id: 'int-004', studentId: 'stu-008', name: '孙一诺', studentNo: 'S2026-000008',
    className: '软件2302', classId: 'c-2302',
    enterpriseId: '', enterpriseName: '', positionName: '',
    advisorName: '刘强', enterpriseMentor: '',
    status: 'READY', statusLabel: '待上岗',
    checkinSummary: '—', checkinTone: 'default',
    reportSummary: '—', riskLevel: 'MEDIUM',
    phone: '18612340031'
  },
  {
    id: 'int-005', studentId: 'stu-009', name: '周雨萌', studentNo: 'S2026-000009',
    className: '软件2301', classId: 'c-2301',
    enterpriseId: 'ent-001', enterpriseName: '华信智能科技有限公司', positionName: '产品助理实习生',
    advisorName: '刘强', enterpriseMentor: '周工',
    status: 'ASSESSING', statusLabel: '考核中',
    checkinSummary: '正常', checkinTone: 'success',
    reportSummary: '4/4 周', riskLevel: 'NONE',
    phone: '15012347788'
  },
  {
    id: 'int-006', studentId: 'stu-010', name: '吴俊杰', studentNo: 'S2026-000010',
    className: '软件2301', classId: 'c-2301',
    enterpriseId: 'ent-001', enterpriseName: '华信智能科技有限公司', positionName: '前端开发实习生',
    advisorName: '刘强', enterpriseMentor: '周工',
    status: 'ONBOARD', statusLabel: '在岗中',
    checkinSummary: '今日超范围 1 次', checkinTone: 'warning',
    reportSummary: '4/4 周', riskLevel: 'NONE',
    phone: '13812349921'
  },
  {
    id: 'int-007', studentId: 'stu-011', name: '郑浩然', studentNo: 'S2026-000011',
    className: '软件2302', classId: 'c-2302',
    enterpriseId: 'ent-002', enterpriseName: '星辰网络技术有限公司', positionName: '网络工程实习生',
    advisorName: '刘强', enterpriseMentor: '吴经理',
    status: 'ONBOARD', statusLabel: '在岗中',
    checkinSummary: '模拟定位命中', checkinTone: 'danger',
    reportSummary: '3/4 周', riskLevel: 'NONE',
    phone: '13312340276'
  },
  {
    id: 'int-008', studentId: 'stu-012', name: '何雨珊', studentNo: 'S2026-000012',
    className: '软件2301', classId: 'c-2301',
    enterpriseId: 'ent-001', enterpriseName: '华信智能科技有限公司', positionName: '测试实习生',
    advisorName: '刘强', enterpriseMentor: '周工',
    status: 'ONBOARD', statusLabel: '在岗中',
    checkinSummary: '正常', checkinTone: 'success',
    reportSummary: '4/4 周', riskLevel: 'NONE',
    phone: '15512340049'
  }
]

/** 学生实习详情（按 id 索引，闭环演示重点做 int-001） */
export const studentDetailMap = {
  'int-001': {
    id: 'int-001', name: '赵一凡', studentNo: 'S2026-000001', className: '软件2301',
    phone: '13512346867', status: 'ONBOARD', statusLabel: '在岗中', riskLevel: 'HIGH',
    enterpriseName: '华信智能科技有限公司', positionName: '前端开发实习生',
    advisorName: '刘强', enterpriseMentor: '周工 · 137****9902',
    internRange: '2026-03-02 ~ 2026-08-28',
    insurance: '实习责任险 · 有效至 2026-08-31',
    agreement: '三方协议已生效',
    stateFlow: [
      { title: '材料核验通过（准备中 → 待上岗）', time: '2026-03-01', tone: 'success' },
      { title: '到岗双确认（学生 + 企业导师）', time: '2026-03-02', tone: 'success' },
      { title: '在岗中（当前）· 旁路态：风险处理中', time: '进行中', tone: 'processing' },
      { title: '考核中 · 已归档', time: '未到达', tone: 'default' }
    ],
    checkins: [
      { id: 'ck-101', date: '07-02 上午', result: '超范围', tone: 'danger', distance: '1.2 km', accuracy: '±12 m', device: '正常', note: '客户现场装机，附照片', handle: '待核实' },
      { id: 'ck-102', date: '07-01 上午', result: '超范围', tone: 'danger', distance: '1.4 km', accuracy: '±8 m', device: '正常', note: '同上，客户现场', handle: '待核实' },
      { id: 'ck-103', date: '06-30 上午', result: '模拟定位', tone: 'danger', distance: '—', accuracy: '—', device: 'is_mock 命中', note: '未提交说明', handle: '已转风险' },
      { id: 'ck-104', date: '06-29 上午', result: '正常', tone: 'success', distance: '86 m', accuracy: '±5 m', device: '正常', note: '', handle: '—' }
    ],
    reports: [
      { id: 'wr-101', week: '第 4 周', status: 'OVERDUE', submitAt: '', version: '—' },
      { id: 'wr-001', week: '第 3 周', status: 'PENDING_REVIEW', submitAt: '07-01 08:02', version: 'v2（重交）' },
      { id: 'wr-102', week: '第 2 周', status: 'APPROVED', submitAt: '06-21 20:15', version: 'v1' }
    ],
    leaves: [
      { id: 'lv-001', type: '病假', range: '06-10 ~ 06-11（2 天）', status: 'APPROVED', reviewer: '刘强' }
    ],
    risks: [
      { id: 'risk-001', code: 'INT-R07', title: '连续 3 天打卡异常', level: 'HIGH', status: '跟进中', owner: '刘强' }
    ],
    auditTrail: [
      { who: '刘强 · 实习指导教师', time: '06-30 16:40', action: '打卡异常转风险跟进', affected: '风险单 risk-001 创建；学生端打卡状态同步「已转风险」' },
      { who: '系统', time: '06-30 08:00', action: '触发 INT-R07 预警', affected: '连续 3 天打卡异常 · 自动生成风险记录' },
      { who: '李敏 · 辅导员', time: '06-28 10:12', action: '发送提醒', affected: '第 3 周周报催交 · 小程序订阅消息' }
    ]
  }
}

/** 打卡异常（学生小程序 P11 提交 → 教师 T18/T19 → PC 处理） */
export const attendanceExceptions = [
  {
    id: 'ex-001', internId: 'int-001', studentName: '赵一凡', className: '软件2301',
    enterpriseName: '华信智能科技有限公司', date: '07-02 上午',
    type: 'OUT_OF_RANGE', typeLabel: '超范围', distance: '1.2 km',
    deviceRisk: '正常', note: '客户现场装机 · 附 2 图', streak: '连续 3 天',
    status: 'PENDING_HANDLE', statusLabel: '待核实'
  },
  {
    id: 'ex-002', internId: 'int-006', studentName: '吴俊杰', className: '软件2301',
    enterpriseName: '华信智能科技有限公司', date: '07-02 上午',
    type: 'OUT_OF_RANGE', typeLabel: '超范围', distance: '0.8 km',
    deviceRisk: '正常', note: '园区停车场排队入厂', streak: '',
    status: 'PENDING_HANDLE', statusLabel: '待核实'
  },
  {
    id: 'ex-003', internId: 'int-007', studentName: '郑浩然', className: '软件2302',
    enterpriseName: '星辰网络技术有限公司', date: '07-01 下午',
    type: 'MOCK_LOCATION', typeLabel: '模拟定位', distance: '—',
    deviceRisk: 'is_mock 命中', note: '未提交说明', streak: '',
    status: 'PENDING_HANDLE', statusLabel: '待核实'
  },
  {
    id: 'ex-004', internId: 'int-008', studentName: '何雨珊', className: '软件2301',
    enterpriseName: '华信智能科技有限公司', date: '06-30 上午',
    type: 'OUT_OF_RANGE', typeLabel: '超范围', distance: '2.1 km',
    deviceRisk: '正常', note: '供应商仓库盘点', streak: '',
    status: 'COMPLETED', statusLabel: '已标记合理'
  }
]

export const attendanceExceptionDetailMap = {
  'ex-001': {
    id: 'ex-001', internId: 'int-001', studentName: '赵一凡', className: '软件2301',
    enterpriseName: '华信智能科技有限公司', positionName: '前端开发实习生',
    date: '07-02 08:47', typeLabel: '超范围 · 连续第 3 天',
    distance: '1.2 km（打卡范围 500 m）', accuracy: '±12 m',
    address: '苏州市吴中区XX产业园', device: 'iPhone 15 · 常用设备',
    deviceId: 'A8F2****D31C', mockDetect: '未命中', systemRisk: '中 · 连续异常（INT-R07）',
    studentNote: '本周被安排到客户现场支持装机调试，地点在吴中产业园，带队的是企业周工，预计周五结束。已附现场照片。',
    noteTime: '07-02 08:49', attachments: ['现场照片 1', '现场照片 2'],
    status: 'PENDING_HANDLE',
    trail: [
      { title: '系统 · 触发 INT-R07 预警', desc: '连续 3 天打卡异常，建议转风险', time: '07-02 08:50', tone: 'warning' },
      { title: '刘强 · 领取处理', desc: '', time: '07-02 09:10', tone: 'processing' }
    ]
  },
  'ex-002': {
    id: 'ex-002', internId: 'int-006', studentName: '吴俊杰', className: '软件2301',
    enterpriseName: '华信智能科技有限公司', positionName: '前端开发实习生',
    date: '07-02 08:31', typeLabel: '超范围',
    distance: '0.8 km（打卡范围 500 m）', accuracy: '±9 m',
    address: '苏州市工业园区XX路', device: 'HarmonyOS · 常用设备',
    deviceId: 'B3C1****77F0', mockDetect: '未命中', systemRisk: '低',
    studentNote: '园区停车场排队入厂，在门口先打卡。',
    noteTime: '07-02 08:32', attachments: [],
    status: 'PENDING_HANDLE',
    trail: [{ title: '学生提交异常说明（小程序 P11）', desc: '', time: '07-02 08:32', tone: 'processing' }]
  },
  'ex-003': {
    id: 'ex-003', internId: 'int-007', studentName: '郑浩然', className: '软件2302',
    enterpriseName: '星辰网络技术有限公司', positionName: '网络工程实习生',
    date: '07-01 14:20', typeLabel: '模拟定位',
    distance: '—', accuracy: '—',
    address: '定位数据不可信', device: 'Android · 新设备',
    deviceId: 'C9D4****02A8', mockDetect: '命中（is_mock=1）', systemRisk: '高 · 建议转风险（INT-R08）',
    studentNote: '未提交说明', noteTime: '', attachments: [],
    status: 'PENDING_HANDLE',
    trail: [{ title: '系统 · 模拟定位检测命中', desc: '按冻结规则：不直接定性作弊，需教师核实', time: '07-01 14:21', tone: 'danger' }]
  }
}

/** 周报（学生 P12 → 教师 T20 → PC 批阅） */
export const weeklyReports = [
  {
    id: 'wr-001', internId: 'int-001', studentName: '赵一凡', className: '软件2301',
    enterpriseName: '华信智能科技有限公司', week: '第 3 周',
    submitAt: '07-01 08:02', version: 'v2', isResubmit: true, wordCount: 1430,
    attachments: 3, riskFlag: 'HIGH', status: 'PENDING_REVIEW', statusLabel: '待批阅'
  },
  {
    id: 'wr-002', internId: 'int-002', studentName: '林晓彤', className: '软件2301',
    enterpriseName: '华信智能科技有限公司', week: '第 4 周',
    submitAt: '07-01 21:14', version: 'v1', isResubmit: false, wordCount: 1120,
    attachments: 2, riskFlag: '', status: 'PENDING_REVIEW', statusLabel: '待批阅'
  },
  {
    id: 'wr-003', internId: 'int-007', studentName: '郑浩然', className: '软件2302',
    enterpriseName: '星辰网络技术有限公司', week: '第 4 周',
    submitAt: '', version: '—', isResubmit: false, wordCount: 0,
    attachments: 0, riskFlag: '', status: 'OVERDUE', statusLabel: '逾期 2 天未交'
  },
  {
    id: 'wr-004', internId: 'int-008', studentName: '何雨珊', className: '软件2301',
    enterpriseName: '华信智能科技有限公司', week: '第 3 周',
    submitAt: '06-28 20:31', version: 'v1', isResubmit: false, wordCount: 620,
    attachments: 0, riskFlag: '', status: 'RETURNED', statusLabel: '已退回'
  },
  {
    id: 'wr-005', internId: 'int-005', studentName: '周雨萌', className: '软件2301',
    enterpriseName: '华信智能科技有限公司', week: '第 4 周',
    submitAt: '07-01 19:40', version: 'v1', isResubmit: false, wordCount: 980,
    attachments: 1, riskFlag: '', status: 'APPROVED', statusLabel: '已通过'
  }
]

export const weeklyReportDetailMap = {
  'wr-001': {
    id: 'wr-001', internId: 'int-001', studentName: '赵一凡', className: '软件2301',
    enterpriseName: '华信智能科技有限公司', positionName: '前端开发实习生',
    week: '第 3 周', submitAt: '07-01 08:02', version: 'v2', isResubmit: true,
    wordCount: 1430, riskFlag: 'HIGH',
    content: {
      work: '本周主要在客户现场配合周工完成 3 个前端页面的联调与上线，学习了灰度发布与回滚流程。',
      harvest: '掌握了接口 Mock 与联调排错方法；问题是对打包配置还不熟练，已向企业导师申请专项讲解。',
      plan: '返回公司参与组件库单元测试补齐，完成第 4 周周报与缺卡说明。'
    },
    attachments: ['联调记录表.xlsx', '现场照片 ×2', '上线清单.pdf'],
    versions: [
      { title: 'v2 · 重新提交（当前批阅版本）', desc: '补充了联调记录与下周计划', time: '07-01 08:02', tone: 'processing' },
      { title: 'v1 · 被退回', desc: '退回原因：仅 300 字，缺少本周工作实质内容与问题反思，请补充联调过程细节。', time: '06-29 10:22 · 刘强', tone: 'danger' },
      { title: 'v1 · 首次提交', desc: '', time: '06-28 22:10', tone: 'default' }
    ],
    status: 'PENDING_REVIEW',
    trail: [
      { who: '刘强', time: '06-29 10:22', action: '退回 v1', affected: '原因已同步学生端（P12 退回提醒条）' },
      { who: '赵一凡（学生端）', time: '07-01 08:02', action: '重交 v2', affected: '来自小程序 P12' }
    ]
  },
  'wr-002': {
    id: 'wr-002', internId: 'int-002', studentName: '林晓彤', className: '软件2301',
    enterpriseName: '华信智能科技有限公司', positionName: '测试实习生',
    week: '第 4 周', submitAt: '07-01 21:14', version: 'v1', isResubmit: false,
    wordCount: 1120, riskFlag: '',
    content: {
      work: '完成登录与订单模块回归测试 86 条用例，提交缺陷 7 个，其中 2 个为阻塞级。',
      harvest: '学会了用例分层设计；对自动化脚本维护还需要练习。',
      plan: '下周开始接口自动化脚本编写，目标覆盖核心链路 30%。'
    },
    attachments: ['测试用例.xlsx', '缺陷清单.xlsx'],
    versions: [{ title: 'v1 · 首次提交', desc: '', time: '07-01 21:14', tone: 'processing' }],
    status: 'PENDING_REVIEW',
    trail: []
  }
}

/** 风险学生（INT-R 编码口径） */
export const riskStudents = [
  {
    id: 'risk-001', internId: 'int-001', studentName: '赵一凡', className: '软件2301',
    source: 'INT-R07 连续打卡异常', sourceDetail: '来源：系统预警 06-30',
    level: 'HIGH', owner: '刘强（指导教师）', deadline: '07-04',
    lastFollow: '07-01 已电话核实客户现场安排', status: 'PROCESSING', statusLabel: '跟进中'
  },
  {
    id: 'risk-002', internId: 'int-003', studentName: '陈志远', className: '软件2302',
    source: 'INT-R16 情绪波动上报', sourceDetail: '来源：企业导师反馈 06-20',
    level: 'MEDIUM', owner: '李敏（辅导员）', deadline: '07-08',
    lastFollow: '06-28 辅导员已联系家长', status: 'PROCESSING', statusLabel: '跟进中'
  },
  {
    id: 'risk-003', internId: 'int-004', studentName: '孙一诺', className: '软件2302',
    source: 'INT-R06 超期未到岗', sourceDetail: '来源：系统预警 06-25',
    level: 'MEDIUM', owner: '刘强（指导教师）', deadline: '07-10',
    lastFollow: '—', status: 'PENDING_HANDLE', statusLabel: '待处理'
  }
]

// ═══════════ 企业库（岗位实习） ═══════════
export const enterpriseList = [
  {
    id: 'ent-001', name: '华信智能科技有限公司', creditCode: '91310000MA1FL0001X',
    industry: '软件', nature: '民营', scale: '中型', region: '上海', city: '上海',
    address: '浦东新区张江高科技园区博云路 2 号', source: 'SCHOOL_ENTERPRISE', sourceLabel: '校企合作',
    cooperationLevel: '战略合作', contactPerson: '王经理', contactPhoneMasked: '138****0011',
    coopStatus: 'ACTIVE', coopStatusLabel: '合作中', coopStatusTone: 'success',
    qualificationStatus: 'PASSED', qualificationLabel: '资质通过',
    blacklist: false, blacklistReason: '', internCount: 12, hiredCount: 8,
    remark: '连续 3 年接收软件专业实习生', reviewBy: '李管理员', reviewAt: '2026-03-01 10:20',
    reviewComment: '营业执照、资质齐全', updatedAt: '2026-06-30 09:12'
  },
  {
    id: 'ent-002', name: '星辰网络技术有限公司', creditCode: '91310000MA1FL0002Y',
    industry: '电子商务', nature: '民营', scale: '小型', region: '上海', city: '上海',
    address: '徐汇区漕河泾开发区宜山路 700 号', source: 'SELF_BUILT', sourceLabel: '自建',
    cooperationLevel: '一般合作', contactPerson: '赵主管', contactPhoneMasked: '139****0022',
    coopStatus: 'PENDING', coopStatusLabel: '待审核', coopStatusTone: 'warning',
    qualificationStatus: 'UNREVIEWED', qualificationLabel: '未核验',
    blacklist: false, blacklistReason: '', internCount: 0, hiredCount: 0,
    remark: '新提交待审核', reviewBy: '', reviewAt: null, reviewComment: '', updatedAt: '2026-06-28 15:40'
  },
  {
    id: 'ent-003', name: '瑞丰物流有限公司', creditCode: '91310000MA1FL0003Z',
    industry: '现代物流', nature: '民营', scale: '中型', region: '江苏', city: '苏州',
    address: '苏州工业园区星湖街 328 号', source: 'RECOMMENDED', sourceLabel: '推荐',
    cooperationLevel: '', contactPerson: '孙经理', contactPhoneMasked: '137****0033',
    coopStatus: 'BLACKLIST', coopStatusLabel: '黑名单', coopStatusTone: 'danger',
    qualificationStatus: 'PASSED', qualificationLabel: '资质通过',
    blacklist: true, blacklistReason: '拖欠 2025 届实习生津贴，学生多次投诉', internCount: 3, hiredCount: 1,
    remark: '', reviewBy: '李管理员', reviewAt: '2025-09-10 14:00', reviewComment: '', updatedAt: '2026-05-20 11:00'
  }
]

export const enterpriseContactsMap = {
  'ent-001': [
    { id: 'ec-1', companyId: 'ent-001', contactType: 'CONTACT', contactTypeLabel: '联系人', name: '王经理', title: 'HR 经理', phoneMasked: '138****0011', email: 'wang@huaxin.com', isPrimary: true, remark: '', status: 'ACTIVE' },
    { id: 'ec-2', companyId: 'ent-001', contactType: 'MENTOR', contactTypeLabel: '企业导师', name: '陈工', title: '技术总监', phoneMasked: '138****0099', email: 'chen@huaxin.com', isPrimary: true, remark: '带教软件实习生', status: 'ACTIVE' }
  ],
  'ent-002': [],
  'ent-003': []
}

// ═══════════ 统计中心 / 归档中心（开发环境后端不可达时的兜底数据）═══════════
export const statsDimensionsMock = {
  colleges: ['信息工程学院'],
  majors: ['软件技术'],
  classes: ['软件2301', '软件2302']
}

export const statsOverviewMock = {
  dimensions: { college: '', major: '', className: '', scopeMode: 'SCOPED' },
  counters: [
    { key: 'totalStudents', label: '实习学生数', value: 8 },
    { key: 'onboardStudents', label: '在岗学生数', value: 6 },
    { key: 'riskStudents', label: '风险学生数', value: 2, warn: true }
  ],
  metrics: [
    { key: 'placementRate', label: '实习落实率', numerator: 7, denominator: 8, rate: 87.5, threshold: 95, warn: true, note: '' },
    { key: 'matchRate', label: '岗位匹配率', numerator: 7, denominator: 8, rate: 87.5, threshold: 90, warn: true, note: '' },
    { key: 'agreementSignRate', label: '协议签署率', numerator: 6, denominator: 8, rate: 75, threshold: 95, warn: true, note: '' },
    { key: 'checkinComplyRate', label: '打卡合规率', numerator: 42, denominator: 48, rate: 87.5, threshold: 85, warn: false, note: '' },
    { key: 'weeklyReviewRate', label: '周报批阅率', numerator: 9, denominator: 12, rate: 75, threshold: 90, warn: true, note: '' },
    { key: 'riskCloseRate', label: '风险闭环率', numerator: 1, denominator: 3, rate: 33.3, threshold: 95, warn: true, note: '' }
  ],
  scoreDistribution: [
    { bucket: '优(90-100)', count: 2 },
    { bucket: '良(80-89)', count: 3 },
    { bucket: '中(70-79)', count: 1 },
    { bucket: '及格(60-69)', count: 0 },
    { bucket: '不及格(<60)', count: 0 }
  ],
  partial: [
    { key: 'employmentRate', label: '就业转化率', reason: '依赖就业模块台账，待就业中心对接' },
    { key: 'helpCoverRate', label: '未就业帮扶覆盖率', reason: '依赖就业帮扶记录，待就业中心对接' },
    { key: 'archiveRate', label: '归档完成率', reason: '依赖实习归档中心聚合' }
  ],
  generatedAt: '2026-07-09 21:00:00'
}

function _archiveMissingForStudent(s) {
  const missing = []
  if (!s.enterpriseId) missing.push('三方协议', '打卡记录', '周报')
  else if (s.riskLevel === 'HIGH') missing.push('周报', '企业评价')
  return missing
}

export const archiveByStudentMock = internshipStudents.map((s) => {
  const missing = _archiveMissingForStudent(s)
  const present = 7 - missing.length
  return {
    id: s.id,
    studentNo: s.studentNo,
    studentName: s.name,
    advisorName: s.advisorName,
    enterpriseName: s.enterpriseName || '—',
    completeness: Math.round(present / 7 * 100),
    missing,
    archived: s.status === 'ARCHIVED'
  }
})

export const archiveByBatchMock = [
  { group: '2026 届春季岗位实习', total: 6, complete: 2, avgCompleteness: 71, archived: 0, archiveRate: 0 },
  { group: '2025 届秋季岗位实习', total: 2, complete: 2, avgCompleteness: 100, archived: 2, archiveRate: 100 }
]

export const archiveByEnterpriseMock = [
  { group: '华信智能科技有限公司', total: 5, complete: 1, avgCompleteness: 68, archived: 0, archiveRate: 0 },
  { group: '星辰网络技术有限公司', total: 1, complete: 1, avgCompleteness: 86, archived: 0, archiveRate: 0 }
]

export const archiveDetailMock = {
  'int-001': {
    studentName: '赵一凡', studentNo: 'S2026-000001', completeness: 57,
    materialLabels: [
      { key: 'agreement', label: '三方协议', present: true },
      { key: 'checkin', label: '打卡记录', present: true },
      { key: 'weekly', label: '周报', present: false },
      { key: 'enterpriseEval', label: '企业评价', present: false },
      { key: 'studentEval', label: '学生自评', present: true },
      { key: 'score', label: '实习成绩', present: false },
      { key: 'guidance', label: '指导记录', present: true }
    ],
    auditTrail: []
  }
}
