/**
 * 02 数字迎新中心 — mock 数据源（内存态，可被 api 写操作变更）。
 * 状态机对齐《02-数字迎新中心深化设计 V1.0》§12：
 *  - 报到状态：NOT_REPORTED → PREPARED → CHECKED_IN → COLLEGE_CONFIRMED（异常 DELAYED/NO_SHOW/ABNORMAL）
 *  - 学生阶段：ADMITTED → PRE_STUDENT_VERIFIED → REGISTERED_PENDING_ENROLLMENT → ENROLLED
 *  - 绿色通道：NOT_APPLIED → SUBMITTED → REVIEWING → APPROVED（异常 RETURNED/REJECTED/WITHDRAWN）
 *  - 材料审核：NOT_UPLOADED → UPLOADED → APPROVED（异常 RETURNED/REJECTED）
 * 删除一律逻辑作废；学校名/角色/数据范围由本文件下发，页面禁止硬编码。
 */

export const nowText = () => {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

/* ---------------- 租户品牌 ---------------- */
export const tenantBrandConfig = {
  tenantId: 'tenant-demo-001',
  schoolName: '演示职业技术学院',
  platformDisplayName: '高校学生全生命周期管理平台',
  schoolLogo: '/assets/tenant/demo-logo.svg',
  schoolBadge: '/assets/tenant/demo-badge.svg',
  tenantBrandColor: '#2563EB',
  watermarkText: '演示职业技术学院 · 数字迎新中心'
}

/* ---------------- 角色与数据范围 ---------------- */
export const roles = [
  { roleId: 'COUNSELOR', roleName: '辅导员', dataScope: { code: 'CLASS', name: '软件2601班 / 软件2602班' } },
  { roleId: 'ORI_TEACHER', roleName: '学院迎新老师', dataScope: { code: 'COLLEGE', name: '信息工程学院' } },
  { roleId: 'FINANCE_TEACHER', roleName: '财务老师', dataScope: { code: 'SCHOOL', name: '全校（缴费与绿色通道）' } },
  { roleId: 'DORM_TEACHER', roleName: '宿管老师', dataScope: { code: 'POINT', name: '梧桐苑 1-3 号楼' } },
  { roleId: 'COLLEGE_ADMIN', roleName: '学院管理员', dataScope: { code: 'COLLEGE', name: '信息工程学院' } }
]

export const state = { currentRoleId: 'ORI_TEACHER' }

/* ---------------- 权限动作 ---------------- */
const FULL = {
  'orientation.student.create': true,
  'orientation.student.view': true,
  'orientation.student.edit': true,
  'orientation.student.void': true,
  'orientation.student.import': true,
  'orientation.student.export': true,
  'orientation.student.batchRemind': true,
  'orientation.student.batchAssign': true,
  'orientation.progress.edit': true,
  'orientation.progress.export': true,
  'orientation.progress.manualResolve': true,
  'orientation.payment.view': true,
  'orientation.payment.export': true,
  'orientation.greenchannel.review': true,
  'orientation.material.review': true,
  'orientation.material.export': true,
  'orientation.dorm.edit': true,
  'orientation.dorm.confirm': true,
  'orientation.dorm.export': true,
  'orientation.dorm.markException': true,
  'orientation.exception.handle': true,
  'orientation.exception.escalate': true,
  'orientation.exception.export': true,
  'orientation.followup.create': true,
  'orientation.followup.edit': true,
  'orientation.audit.view': true,
  'orientation.columns.setting': true
}

export const permissionActionsByRole = {
  COUNSELOR: {
    actions: {
      ...FULL,
      'orientation.student.import': false,
      'orientation.student.batchAssign': false,
      'orientation.greenchannel.review': false,
      'orientation.dorm.edit': false,
      'orientation.dorm.confirm': false,
      'orientation.dorm.markException': false
    },
    hidden: [],
    disabledReason: '辅导员仅可维护本班新生的报到与跟进信息'
  },
  ORI_TEACHER: { actions: FULL, disabledReason: '' },
  FINANCE_TEACHER: {
    actions: {
      ...FULL,
      'orientation.student.create': false,
      'orientation.student.edit': false,
      'orientation.student.void': false,
      'orientation.student.import': false,
      'orientation.student.batchAssign': false,
      'orientation.progress.edit': false,
      'orientation.progress.manualResolve': false,
      'orientation.material.review': false,
      'orientation.dorm.edit': false,
      'orientation.dorm.confirm': false,
      'orientation.dorm.markException': false,
      'orientation.exception.handle': false,
      'orientation.exception.escalate': false,
      'orientation.followup.create': false,
      'orientation.followup.edit': false
    },
    hidden: ['orientation.student.import', 'orientation.dorm.export'],
    disabledReason: '财务老师仅负责缴费状态与绿色通道审核'
  },
  DORM_TEACHER: {
    actions: {
      ...FULL,
      'orientation.student.create': false,
      'orientation.student.edit': false,
      'orientation.student.void': false,
      'orientation.student.import': false,
      'orientation.student.export': false,
      'orientation.student.batchRemind': false,
      'orientation.student.batchAssign': false,
      'orientation.progress.edit': false,
      'orientation.progress.export': false,
      'orientation.progress.manualResolve': false,
      'orientation.payment.export': false,
      'orientation.greenchannel.review': false,
      'orientation.material.review': false,
      'orientation.material.export': false,
      'orientation.exception.escalate': false,
      'orientation.followup.create': false,
      'orientation.followup.edit': false
    },
    hidden: ['orientation.student.import', 'orientation.student.export', 'orientation.payment.export', 'orientation.material.export'],
    disabledReason: '宿管老师仅负责宿舍入住确认与异常标记'
  },
  COLLEGE_ADMIN: { actions: FULL, disabledReason: '' }
}

/* ---------------- 字典 ---------------- */
export const statusOptions = {
  stage: [
    { value: 'ADMITTED', label: '已录取' },
    { value: 'PRE_STUDENT_VERIFIED', label: '预报到已核验' },
    { value: 'REGISTERED_PENDING_ENROLLMENT', label: '已报到待注册' },
    { value: 'ENROLLED', label: '已入学' },
    { value: 'DEFERRED', label: '延迟报到' },
    { value: 'NO_SHOW', label: '未到校' },
    { value: 'CANCELLED', label: '取消入学' }
  ],
  reportStatus: [
    { value: 'NOT_REPORTED', label: '未报到' },
    { value: 'PREPARED', label: '预报到完成' },
    { value: 'CHECKED_IN', label: '已现场报到' },
    { value: 'COLLEGE_CONFIRMED', label: '学院已确认' },
    { value: 'DELAYED', label: '延迟报到' },
    { value: 'NO_SHOW', label: '未到校' },
    { value: 'ABNORMAL', label: '报到异常' }
  ],
  paymentStatus: [
    { value: 'PAID', label: '已缴清' },
    { value: 'PARTIAL', label: '部分缴费' },
    { value: 'UNPAID', label: '未缴费' },
    { value: 'DEFERRED', label: '已批准缓缴' },
    { value: 'GREEN_CHANNEL', label: '绿色通道' }
  ],
  greenChannelStatus: [
    { value: 'NOT_APPLIED', label: '未申请' },
    { value: 'SUBMITTED', label: '已提交' },
    { value: 'REVIEWING', label: '审核中' },
    { value: 'APPROVED', label: '已通过' },
    { value: 'RETURNED', label: '已退回' },
    { value: 'REJECTED', label: '已驳回' },
    { value: 'WITHDRAWN', label: '已撤回' }
  ],
  materialStatus: [
    { value: 'NOT_UPLOADED', label: '未上传' },
    { value: 'UPLOADED', label: '待审核' },
    { value: 'APPROVED', label: '已通过' },
    { value: 'RETURNED', label: '已退回' },
    { value: 'REJECTED', label: '已驳回' }
  ],
  materialType: [
    { value: 'ID_CARD', label: '身份证明' },
    { value: 'ADMISSION_LETTER', label: '录取通知书' },
    { value: 'PHOTO', label: '证件照' },
    { value: 'ARCHIVE', label: '纸质档案' },
    { value: 'AID_PROOF', label: '资助证明材料' }
  ],
  dormStatus: [
    { value: 'UNASSIGNED', label: '未分配' },
    { value: 'ASSIGNED', label: '已分配' },
    { value: 'CHECKED_IN', label: '已入住' },
    { value: 'EXCEPTION', label: '入住异常' }
  ],
  exceptionType: [
    { value: 'IDENTITY', label: '身份核验异常' },
    { value: 'PAYMENT', label: '缴费异常' },
    { value: 'MATERIAL', label: '材料异常' },
    { value: 'DORM', label: '宿舍异常' },
    { value: 'NO_SHOW', label: '未到校' }
  ],
  exceptionStatus: [
    { value: 'OPEN', label: '待处理' },
    { value: 'PROCESSING', label: '处理中' },
    { value: 'RESOLVED', label: '已处理' },
    { value: 'ESCALATED', label: '已升级' }
  ],
  recordStatus: [
    { value: 'ACTIVE', label: '有效' },
    { value: 'VOIDED', label: '已作废' }
  ],
  riskLevel: [
    { value: 'LOW', label: '低风险' },
    { value: 'MEDIUM', label: '中风险' },
    { value: 'HIGH', label: '高风险' }
  ],
  followUpWay: [
    { value: 'PHONE', label: '电话联系' },
    { value: 'WECHAT', label: '微信联系' },
    { value: 'PARENT', label: '联系家长' },
    { value: 'ONSITE', label: '现场处理' }
  ]
}

export const filterOptions = {
  colleges: [
    { value: 'C01', label: '信息工程学院' },
    { value: 'C02', label: '智能制造学院' }
  ],
  classes: [
    { value: 'NCL01', label: '软件2601班' },
    { value: 'NCL02', label: '软件2602班' },
    { value: 'NCL03', label: '大数据2601班' },
    { value: 'NCL04', label: '机电2601班' }
  ],
  buildings: [
    { value: 'B01', label: '梧桐苑 1 号楼' },
    { value: 'B02', label: '梧桐苑 2 号楼' },
    { value: 'B03', label: '梧桐苑 3 号楼' }
  ]
}

/* ---------------- 报到环节定义 ---------------- */
export const registrationSteps = [
  { key: 'ACTIVATE', label: '账号激活' },
  { key: 'INFO', label: '信息核对' },
  { key: 'MATERIAL', label: '材料上传' },
  { key: 'PAYMENT', label: '缴费/绿色通道' },
  { key: 'DORM', label: '宿舍确认' },
  { key: 'CHECKIN', label: '现场报到' },
  { key: 'CONFIRM', label: '学院确认' }
]

/* ---------------- 列设置 ---------------- */
export const fieldColumns = {
  studentList: [
    { key: 'name', title: '姓名', locked: true, default: true },
    { key: 'admissionNo', title: '录取编号', default: true },
    { key: 'className', title: '班级', default: true },
    { key: 'stage', title: '学生阶段', default: true },
    { key: 'reportStatus', title: '报到状态', default: true },
    { key: 'paymentStatus', title: '缴费状态', default: true },
    { key: 'materialStatus', title: '材料状态', default: true },
    { key: 'dormStatus', title: '宿舍状态', default: false },
    { key: 'phone', title: '手机号', sensitive: true, default: false },
    { key: 'counselor', title: '辅导员', default: true },
    { key: 'riskLevel', title: '风险', default: true },
    { key: 'updateTime', title: '更新时间', default: false },
    { key: 'actions', title: '操作', locked: true, default: true }
  ],
  progressList: [
    { key: 'name', title: '姓名', locked: true, default: true },
    { key: 'className', title: '班级', default: true },
    { key: 'progress', title: '报到进度', default: true },
    { key: 'blockedStep', title: '当前卡点', default: true },
    { key: 'blockedReason', title: '卡点说明', default: true },
    { key: 'reportStatus', title: '报到状态', default: true },
    { key: 'actions', title: '操作', locked: true, default: true }
  ],
  paymentList: [
    { key: 'name', title: '姓名', locked: true, default: true },
    { key: 'className', title: '班级', default: true },
    { key: 'payableAmount', title: '应缴金额', default: true },
    { key: 'paidAmount', title: '已缴金额', default: true },
    { key: 'paymentStatus', title: '缴费状态', default: true },
    { key: 'greenChannelStatus', title: '绿色通道', default: true },
    { key: 'updateTime', title: '更新时间', default: false },
    { key: 'actions', title: '操作', locked: true, default: true }
  ],
  greenChannelList: [
    { key: 'name', title: '姓名', locked: true, default: true },
    { key: 'className', title: '班级', default: true },
    { key: 'applyType', title: '申请类型', default: true },
    { key: 'applyAmount', title: '涉及金额', default: true },
    { key: 'submitTime', title: '提交时间', default: true },
    { key: 'status', title: '审批状态', default: true },
    { key: 'actions', title: '操作', locked: true, default: true }
  ],
  materialList: [
    { key: 'name', title: '姓名', locked: true, default: true },
    { key: 'className', title: '班级', default: true },
    { key: 'materialType', title: '材料类型', default: true },
    { key: 'fileName', title: '材料文件', default: true },
    { key: 'submitTime', title: '提交时间', default: true },
    { key: 'status', title: '审核状态', default: true },
    { key: 'reviewer', title: '审核人', default: false },
    { key: 'actions', title: '操作', locked: true, default: true }
  ],
  dormList: [
    { key: 'name', title: '姓名', locked: true, default: true },
    { key: 'className', title: '班级', default: true },
    { key: 'building', title: '楼栋', default: true },
    { key: 'room', title: '房间/床位', default: true },
    { key: 'dormStatus', title: '入住状态', default: true },
    { key: 'checkinTime', title: '入住时间', default: true },
    { key: 'exceptionNote', title: '异常说明', default: false },
    { key: 'actions', title: '操作', locked: true, default: true }
  ],
  exceptionList: [
    { key: 'name', title: '姓名', locked: true, default: true },
    { key: 'className', title: '班级', default: true },
    { key: 'exceptionType', title: '异常类型', default: true },
    { key: 'description', title: '异常描述', default: true },
    { key: 'riskLevel', title: '风险', default: true },
    { key: 'status', title: '处理状态', default: true },
    { key: 'handler', title: '负责人', default: true },
    { key: 'lastFollowTime', title: '最近跟进', default: false },
    { key: 'actions', title: '操作', locked: true, default: true }
  ]
}

/* ---------------- 批量操作 ---------------- */
export const batchActions = {
  studentList: [
    { key: 'batchRemind', label: '批量提醒', permission: 'orientation.student.batchRemind' },
    { key: 'batchAssign', label: '批量分配辅导员', permission: 'orientation.student.batchAssign' },
    { key: 'batchExport', label: '导出选中', permission: 'orientation.student.export' }
  ],
  progressList: [{ key: 'batchRemind', label: '批量提醒未完成学生', permission: 'orientation.student.batchRemind' }],
  materialList: [
    { key: 'batchApprove', label: '批量通过', permission: 'orientation.material.review' },
    { key: 'batchReturn', label: '批量退回', permission: 'orientation.material.review' }
  ],
  dormList: [
    { key: 'batchConfirm', label: '批量确认入住', permission: 'orientation.dorm.confirm' },
    { key: 'batchExport', label: '导出住宿名单', permission: 'orientation.dorm.export' }
  ],
  exceptionList: [{ key: 'batchRemind', label: '批量提醒', permission: 'orientation.student.batchRemind' }]
}

/* ---------------- 导入模板 ---------------- */
export const importTemplates = {
  studentList: {
    key: 'studentList',
    name: '新生录取名单导入模板',
    fileName: '新生导入模板.xlsx',
    fields: [
      { key: 'admissionNo', label: '录取编号', required: true, example: 'LQ2026010001' },
      { key: 'name', label: '姓名', required: true, example: '李明' },
      { key: 'idCard', label: '身份证号', required: true, example: '330102200801011234' },
      { key: 'majorName', label: '录取专业', required: true, example: '软件技术' },
      { key: 'phone', label: '联系电话', required: false, example: '13800001111' }
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
    studentList: [
      { key: 'base', label: '基础信息', fields: ['姓名', '录取编号', '班级', '学生阶段'] },
      { key: 'report', label: '报到信息', fields: ['报到状态', '缴费状态', '材料状态', '宿舍状态'] },
      { key: 'sensitive', label: '敏感信息（默认脱敏）', sensitive: true, fields: ['手机号', '身份证号（仅脱敏）'] }
    ],
    progressList: [{ key: 'base', label: '进度报表', fields: ['姓名', '班级', '各环节完成情况', '当前卡点', '卡点说明'] }],
    paymentList: [
      { key: 'base', label: '缴费信息', fields: ['姓名', '班级', '应缴金额', '已缴金额', '缴费状态', '绿色通道状态'] }
    ],
    materialList: [{ key: 'base', label: '审核记录', fields: ['姓名', '材料类型', '提交时间', '审核状态', '审核人', '审核意见'] }],
    dormList: [
      { key: 'base', label: '住宿名单', fields: ['姓名', '班级', '楼栋', '房间/床位', '入住状态', '入住时间'] },
      { key: 'sensitive', label: '敏感信息（默认脱敏）', sensitive: true, fields: ['手机号'] }
    ],
    exceptionList: [{ key: 'base', label: '异常名单', fields: ['姓名', '班级', '异常类型', '异常描述', '风险等级', '处理状态'] }]
  },
  maskDefault: true,
  idCardPlainForbidden: true,
  watermarkNote: '导出文件将自动嵌入水印（学校名 · 操作人 · 时间 · 用途），并写入审计日志。',
  auditNotice: '本次导出行为将被完整记录并可追溯，请确认导出用途合规。'
}

/* ---------------- 新生台账 ---------------- */
const NEW_STU = (id, name, no, classId, className, stage, reportStatus, paymentStatus, greenChannelStatus, materialStatus, dormStatus, riskLevel, extras = {}) => ({
  id,
  studentId: id,
  name,
  admissionNo: no,
  gender: extras.gender || '男',
  collegeId: extras.collegeId || 'C01',
  collegeName: extras.collegeName || '信息工程学院',
  majorName: extras.majorName || '软件技术',
  classId,
  className,
  grade: '2026级',
  phone: extras.phone || '13800002222',
  idCard: extras.idCard || '330102200801011234',
  origin: extras.origin || '浙江杭州',
  stage,
  reportStatus,
  paymentStatus,
  greenChannelStatus,
  materialStatus,
  dormStatus,
  building: extras.building || '',
  room: extras.room || '',
  riskLevel,
  recordStatus: 'ACTIVE',
  voidReason: '',
  counselor: extras.counselor || '李辅导',
  steps: extras.steps || {},
  blockedStep: extras.blockedStep || '',
  blockedReason: extras.blockedReason || '',
  payableAmount: extras.payableAmount ?? 8600,
  paidAmount: extras.paidAmount ?? 0,
  checkinTime: extras.checkinTime || '',
  exceptionNote: extras.exceptionNote || '',
  updateTime: extras.updateTime || '2026-07-02 09:00'
})

/** steps: 每个环节 DONE / DOING / BLOCKED / TODO */
export const orientationStudents = [
  NEW_STU('ori-s-001', '李明泽', 'LQ2026010001', 'NCL01', '软件2601班', 'REGISTERED_PENDING_ENROLLMENT', 'CHECKED_IN', 'PAID', 'NOT_APPLIED', 'APPROVED', 'CHECKED_IN', 'LOW', {
    building: '梧桐苑 1 号楼',
    room: '1-302-2',
    paidAmount: 8600,
    checkinTime: '2026-07-01 10:20',
    steps: { ACTIVATE: 'DONE', INFO: 'DONE', MATERIAL: 'DONE', PAYMENT: 'DONE', DORM: 'DONE', CHECKIN: 'DONE', CONFIRM: 'DOING' }
  }),
  NEW_STU('ori-s-002', '张诗雨', 'LQ2026010002', 'NCL01', '软件2601班', 'PRE_STUDENT_VERIFIED', 'PREPARED', 'PAID', 'NOT_APPLIED', 'APPROVED', 'ASSIGNED', 'LOW', {
    gender: '女',
    building: '梧桐苑 2 号楼',
    room: '2-105-1',
    paidAmount: 8600,
    steps: { ACTIVATE: 'DONE', INFO: 'DONE', MATERIAL: 'DONE', PAYMENT: 'DONE', DORM: 'DONE', CHECKIN: 'TODO', CONFIRM: 'TODO' }
  }),
  NEW_STU('ori-s-003', '王皓宇', 'LQ2026010003', 'NCL01', '软件2601班', 'ADMITTED', 'NOT_REPORTED', 'UNPAID', 'NOT_APPLIED', 'NOT_UPLOADED', 'UNASSIGNED', 'MEDIUM', {
    blockedStep: 'ACTIVATE',
    blockedReason: '账号未激活，短信提醒 2 次未响应',
    steps: { ACTIVATE: 'BLOCKED', INFO: 'TODO', MATERIAL: 'TODO', PAYMENT: 'TODO', DORM: 'TODO', CHECKIN: 'TODO', CONFIRM: 'TODO' }
  }),
  NEW_STU('ori-s-004', '陈可欣', 'LQ2026010004', 'NCL01', '软件2601班', 'PRE_STUDENT_VERIFIED', 'PREPARED', 'GREEN_CHANNEL', 'REVIEWING', 'UPLOADED', 'ASSIGNED', 'MEDIUM', {
    gender: '女',
    building: '梧桐苑 2 号楼',
    room: '2-208-3',
    payableAmount: 8600,
    paidAmount: 0,
    blockedStep: 'PAYMENT',
    blockedReason: '绿色通道申请审核中，学费缓缴待确认',
    steps: { ACTIVATE: 'DONE', INFO: 'DONE', MATERIAL: 'DOING', PAYMENT: 'BLOCKED', DORM: 'DONE', CHECKIN: 'TODO', CONFIRM: 'TODO' }
  }),
  NEW_STU('ori-s-005', '刘子豪', 'LQ2026010005', 'NCL02', '软件2602班', 'PRE_STUDENT_VERIFIED', 'PREPARED', 'PARTIAL', 'NOT_APPLIED', 'RETURNED', 'ASSIGNED', 'MEDIUM', {
    counselor: '周辅导',
    building: '梧桐苑 1 号楼',
    room: '1-406-4',
    paidAmount: 5000,
    blockedStep: 'MATERIAL',
    blockedReason: '证件照被退回：背景不符合要求，需重新上传',
    steps: { ACTIVATE: 'DONE', INFO: 'DONE', MATERIAL: 'BLOCKED', PAYMENT: 'DOING', DORM: 'DONE', CHECKIN: 'TODO', CONFIRM: 'TODO' }
  }),
  NEW_STU('ori-s-006', '赵梦琪', 'LQ2026010006', 'NCL02', '软件2602班', 'REGISTERED_PENDING_ENROLLMENT', 'CHECKED_IN', 'PAID', 'NOT_APPLIED', 'APPROVED', 'EXCEPTION', 'HIGH', {
    gender: '女',
    counselor: '周辅导',
    building: '梧桐苑 2 号楼',
    room: '2-301-2',
    paidAmount: 8600,
    checkinTime: '2026-07-01 14:50',
    exceptionNote: '床位与系统分配不一致，现场调换待确认',
    blockedStep: 'DORM',
    blockedReason: '宿舍床位冲突，待宿管确认调换结果',
    steps: { ACTIVATE: 'DONE', INFO: 'DONE', MATERIAL: 'DONE', PAYMENT: 'DONE', DORM: 'BLOCKED', CHECKIN: 'DONE', CONFIRM: 'TODO' }
  }),
  NEW_STU('ori-s-007', '孙一鸣', 'LQ2026010007', 'NCL02', '软件2602班', 'ADMITTED', 'DELAYED', 'UNPAID', 'NOT_APPLIED', 'NOT_UPLOADED', 'UNASSIGNED', 'HIGH', {
    counselor: '周辅导',
    blockedStep: 'CHECKIN',
    blockedReason: '家长来电：孩子生病住院，申请延迟一周报到',
    steps: { ACTIVATE: 'DONE', INFO: 'DONE', MATERIAL: 'TODO', PAYMENT: 'TODO', DORM: 'TODO', CHECKIN: 'BLOCKED', CONFIRM: 'TODO' }
  }),
  NEW_STU('ori-s-008', '周雨彤', 'LQ2026020008', 'NCL03', '大数据2601班', 'PRE_STUDENT_VERIFIED', 'PREPARED', 'DEFERRED', 'APPROVED', 'APPROVED', 'ASSIGNED', 'LOW', {
    gender: '女',
    majorName: '大数据技术',
    counselor: '钱辅导',
    building: '梧桐苑 3 号楼',
    room: '3-102-1',
    payableAmount: 8600,
    paidAmount: 0,
    steps: { ACTIVATE: 'DONE', INFO: 'DONE', MATERIAL: 'DONE', PAYMENT: 'DONE', DORM: 'DONE', CHECKIN: 'TODO', CONFIRM: 'TODO' }
  }),
  NEW_STU('ori-s-009', '吴俊杰', 'LQ2026020009', 'NCL03', '大数据2601班', 'ADMITTED', 'NOT_REPORTED', 'UNPAID', 'RETURNED', 'UPLOADED', 'UNASSIGNED', 'MEDIUM', {
    majorName: '大数据技术',
    counselor: '钱辅导',
    blockedStep: 'PAYMENT',
    blockedReason: '绿色通道申请被退回：家庭困难证明缺少乡镇盖章',
    steps: { ACTIVATE: 'DONE', INFO: 'DONE', MATERIAL: 'DOING', PAYMENT: 'BLOCKED', DORM: 'TODO', CHECKIN: 'TODO', CONFIRM: 'TODO' }
  }),
  NEW_STU('ori-s-010', '郑晓萌', 'LQ2026020010', 'NCL03', '大数据2601班', 'ADMITTED', 'NO_SHOW', 'UNPAID', 'NOT_APPLIED', 'NOT_UPLOADED', 'UNASSIGNED', 'HIGH', {
    gender: '女',
    majorName: '大数据技术',
    counselor: '钱辅导',
    blockedStep: 'ACTIVATE',
    blockedReason: '报到日未到校，电话/短信均无法联系本人',
    steps: { ACTIVATE: 'BLOCKED', INFO: 'TODO', MATERIAL: 'TODO', PAYMENT: 'TODO', DORM: 'TODO', CHECKIN: 'TODO', CONFIRM: 'TODO' }
  }),
  NEW_STU('ori-s-011', '冯浩然', 'LQ2026030011', 'NCL04', '机电2601班', 'REGISTERED_PENDING_ENROLLMENT', 'COLLEGE_CONFIRMED', 'PAID', 'NOT_APPLIED', 'APPROVED', 'CHECKED_IN', 'LOW', {
    collegeId: 'C02',
    collegeName: '智能制造学院',
    majorName: '机电一体化',
    counselor: '孙辅导',
    building: '梧桐苑 3 号楼',
    room: '3-501-3',
    paidAmount: 8600,
    checkinTime: '2026-07-01 09:05',
    steps: { ACTIVATE: 'DONE', INFO: 'DONE', MATERIAL: 'DONE', PAYMENT: 'DONE', DORM: 'DONE', CHECKIN: 'DONE', CONFIRM: 'DONE' }
  }),
  NEW_STU('ori-s-012', '许安琪', 'LQ2026030012', 'NCL04', '机电2601班', 'PRE_STUDENT_VERIFIED', 'PREPARED', 'PARTIAL', 'SUBMITTED', 'UPLOADED', 'ASSIGNED', 'MEDIUM', {
    gender: '女',
    collegeId: 'C02',
    collegeName: '智能制造学院',
    majorName: '机电一体化',
    counselor: '孙辅导',
    building: '梧桐苑 3 号楼',
    room: '3-203-2',
    paidAmount: 3000,
    blockedStep: 'PAYMENT',
    blockedReason: '绿色通道申请已提交，等待财务初审',
    steps: { ACTIVATE: 'DONE', INFO: 'DONE', MATERIAL: 'DOING', PAYMENT: 'BLOCKED', DORM: 'DONE', CHECKIN: 'TODO', CONFIRM: 'TODO' }
  })
]

/* ---------------- 绿色通道申请 ---------------- */
export const greenChannelApplications = [
  {
    id: 'ori-g-001',
    studentId: 'ori-s-004',
    name: '陈可欣',
    className: '软件2601班',
    applyType: '生源地助学贷款',
    applyAmount: 8600,
    submitTime: '2026-06-25 10:30',
    status: 'REVIEWING',
    reviewer: '财务老师',
    reviewTime: '',
    rejectReason: '',
    attachments: ['助学贷款受理证明.pdf'],
    remark: '贷款回执已上传，待财务确认'
  },
  {
    id: 'ori-g-002',
    studentId: 'ori-s-008',
    name: '周雨彤',
    className: '大数据2601班',
    applyType: '学费缓缴',
    applyAmount: 8600,
    submitTime: '2026-06-20 14:00',
    status: 'APPROVED',
    reviewer: '财务老师',
    reviewTime: '2026-06-22 09:10',
    rejectReason: '',
    attachments: ['家庭经济困难认定表.pdf'],
    remark: '批准缓缴至 2026-09-30'
  },
  {
    id: 'ori-g-003',
    studentId: 'ori-s-009',
    name: '吴俊杰',
    className: '大数据2601班',
    applyType: '学费减免',
    applyAmount: 4300,
    submitTime: '2026-06-26 16:40',
    status: 'RETURNED',
    reviewer: '财务老师',
    reviewTime: '2026-06-27 11:20',
    rejectReason: '家庭困难证明缺少乡镇（街道）盖章，请补盖后重新提交',
    attachments: ['家庭困难证明.jpg'],
    remark: ''
  },
  {
    id: 'ori-g-004',
    studentId: 'ori-s-012',
    name: '许安琪',
    className: '机电2601班',
    applyType: '学费分期',
    applyAmount: 5600,
    submitTime: '2026-07-01 08:50',
    status: 'SUBMITTED',
    reviewer: '',
    reviewTime: '',
    rejectReason: '',
    attachments: ['分期缴费承诺书.pdf'],
    remark: ''
  }
]

/* ---------------- 迎新材料 ---------------- */
export const materialReviewList = [
  {
    id: 'ori-m-001',
    studentId: 'ori-s-004',
    name: '陈可欣',
    className: '软件2601班',
    materialType: 'AID_PROOF',
    fileName: '家庭经济困难认定表-陈可欣.pdf',
    submitTime: '2026-06-25 10:28',
    status: 'UPLOADED',
    reviewer: '',
    reviewTime: '',
    returnReason: ''
  },
  {
    id: 'ori-m-002',
    studentId: 'ori-s-005',
    name: '刘子豪',
    className: '软件2602班',
    materialType: 'PHOTO',
    fileName: '证件照-刘子豪.jpg',
    submitTime: '2026-06-24 09:15',
    status: 'RETURNED',
    reviewer: '学院迎新老师',
    reviewTime: '2026-06-24 15:40',
    returnReason: '照片背景为蓝色，要求白底免冠照，请重新拍摄上传'
  },
  {
    id: 'ori-m-003',
    studentId: 'ori-s-009',
    name: '吴俊杰',
    className: '大数据2601班',
    materialType: 'ID_CARD',
    fileName: '身份证正反面-吴俊杰.pdf',
    submitTime: '2026-06-26 16:35',
    status: 'UPLOADED',
    reviewer: '',
    reviewTime: '',
    returnReason: ''
  },
  {
    id: 'ori-m-004',
    studentId: 'ori-s-001',
    name: '李明泽',
    className: '软件2601班',
    materialType: 'ADMISSION_LETTER',
    fileName: '录取通知书-李明泽.jpg',
    submitTime: '2026-06-18 11:00',
    status: 'APPROVED',
    reviewer: '学院迎新老师',
    reviewTime: '2026-06-18 16:20',
    returnReason: ''
  },
  {
    id: 'ori-m-005',
    studentId: 'ori-s-012',
    name: '许安琪',
    className: '机电2601班',
    materialType: 'AID_PROOF',
    fileName: '分期缴费承诺书-许安琪.pdf',
    submitTime: '2026-07-01 08:52',
    status: 'UPLOADED',
    reviewer: '',
    reviewTime: '',
    returnReason: ''
  }
]

/* ---------------- 迎新异常 ---------------- */
export const exceptionStudents = [
  {
    id: 'ori-e-001',
    studentId: 'ori-s-010',
    name: '郑晓萌',
    className: '大数据2601班',
    exceptionType: 'NO_SHOW',
    description: '报到日未到校，电话/短信均无法联系本人',
    riskLevel: 'HIGH',
    status: 'OPEN',
    handler: '钱辅导',
    lastFollowTime: '',
    followUps: []
  },
  {
    id: 'ori-e-002',
    studentId: 'ori-s-007',
    name: '孙一鸣',
    className: '软件2602班',
    exceptionType: 'NO_SHOW',
    description: '家长申请延迟一周报到（生病住院），需跟踪确认返校时间',
    riskLevel: 'HIGH',
    status: 'PROCESSING',
    handler: '周辅导',
    lastFollowTime: '2026-07-01 16:00',
    followUps: [
      {
        id: 'ori-ef-001',
        followTime: '2026-07-01 16:00',
        way: 'PARENT',
        content: '与家长确认住院情况，约定 7 月 8 日前返校报到',
        operator: '周辅导',
        status: 'ACTIVE',
        voidReason: ''
      }
    ]
  },
  {
    id: 'ori-e-003',
    studentId: 'ori-s-006',
    name: '赵梦琪',
    className: '软件2602班',
    exceptionType: 'DORM',
    description: '床位与系统分配不一致，现场调换待宿管确认',
    riskLevel: 'MEDIUM',
    status: 'PROCESSING',
    handler: '宿管老师',
    lastFollowTime: '2026-07-01 15:30',
    followUps: [
      {
        id: 'ori-ef-002',
        followTime: '2026-07-01 15:30',
        way: 'ONSITE',
        content: '现场核对床位，2-301-2 与 2-301-4 对调，待系统更新',
        operator: '宿管老师',
        status: 'ACTIVE',
        voidReason: ''
      }
    ]
  },
  {
    id: 'ori-e-004',
    studentId: 'ori-s-003',
    name: '王皓宇',
    className: '软件2601班',
    exceptionType: 'IDENTITY',
    description: '账号未激活，无法完成预报到身份核验',
    riskLevel: 'MEDIUM',
    status: 'OPEN',
    handler: '李辅导',
    lastFollowTime: '',
    followUps: []
  },
  {
    id: 'ori-e-005',
    studentId: 'ori-s-009',
    name: '吴俊杰',
    className: '大数据2601班',
    exceptionType: 'PAYMENT',
    description: '绿色通道申请被退回，缴费环节阻塞',
    riskLevel: 'MEDIUM',
    status: 'PROCESSING',
    handler: '钱辅导',
    lastFollowTime: '2026-06-28 10:00',
    followUps: [
      {
        id: 'ori-ef-003',
        followTime: '2026-06-28 10:00',
        way: 'PHONE',
        content: '电话指导补办盖章材料，预计 7 月 5 日前重新提交',
        operator: '钱辅导',
        status: 'ACTIVE',
        voidReason: ''
      }
    ]
  }
]

/* ---------------- 审计日志 ---------------- */
export const auditLogs = [
  {
    id: 'ori-a-001',
    time: '2026-06-27 11:20',
    operator: '财务老师（演示账号）',
    roleName: '财务老师',
    bizType: 'GREEN_CHANNEL',
    bizId: 'ori-g-003',
    action: '退回申请',
    detail: '退回吴俊杰学费减免申请：家庭困难证明缺少乡镇盖章',
    before: 'REVIEWING',
    after: 'RETURNED'
  },
  {
    id: 'ori-a-002',
    time: '2026-06-24 15:40',
    operator: '学院迎新老师（演示账号）',
    roleName: '学院迎新老师',
    bizType: 'MATERIAL',
    bizId: 'ori-m-002',
    action: '退回材料',
    detail: '退回《证件照-刘子豪.jpg》：要求白底免冠照',
    before: 'UPLOADED',
    after: 'RETURNED'
  },
  {
    id: 'ori-a-003',
    time: '2026-06-22 09:10',
    operator: '财务老师（演示账号）',
    roleName: '财务老师',
    bizType: 'GREEN_CHANNEL',
    bizId: 'ori-g-002',
    action: '审核通过',
    detail: '批准周雨彤学费缓缴至 2026-09-30',
    before: 'REVIEWING',
    after: 'APPROVED'
  },
  {
    id: 'ori-a-004',
    time: '2026-07-01 15:30',
    operator: '宿管老师（演示账号）',
    roleName: '宿管老师',
    bizType: 'DORM',
    bizId: 'ori-s-006',
    action: '标记入住异常',
    detail: '赵梦琪床位冲突，现场调换待系统确认',
    before: 'CHECKED_IN',
    after: 'EXCEPTION'
  },
  {
    id: 'ori-a-005',
    time: '2026-06-30 08:40',
    operator: '学院迎新老师（演示账号）',
    roleName: '学院迎新老师',
    bizType: 'EXPORT',
    bizId: 'progressList',
    action: '导出进度报表',
    detail: '导出报到进度报表 12 条（手机号已脱敏，含水印）'
  }
]

/* ---------------- 看板 ---------------- */
export const dashboardSummary = {
  batchName: '2026 级新生迎新批次',
  batchPeriod: '2026-06-15 ~ 2026-07-10 · 现场报到日 7月1日-7月2日',
  updateTime: '2026-07-03 08:30',
  kpis: [
    { key: 'total', label: '新生总数', value: '12', trend: '', trendQuality: 'neutral' },
    { key: 'prepared', label: '预报到完成', value: '9', trend: '75.0%', trendQuality: 'good' },
    { key: 'checkedIn', label: '已现场报到', value: '3', trend: '+3 今日', trendQuality: 'good' },
    { key: 'paidRate', label: '缴费完成率', value: '58.3%', trend: '+8.3% 日环比', trendQuality: 'good' },
    { key: 'greenChannel', label: '绿色通道申请', value: '4', trend: '2 待审', trendQuality: 'neutral' },
    { key: 'exception', label: '迎新异常', value: '5', trend: '+1 今日', trendQuality: 'bad' }
  ],
  flow: [
    { label: '已录取', value: 4 },
    { label: '预报到完成', value: 5, active: true },
    { label: '已现场报到', value: 2 },
    { label: '学院已确认', value: 1 }
  ],
  stepFunnel: [
    { key: 'ACTIVATE', label: '账号激活', done: 10 },
    { key: 'INFO', label: '信息核对', done: 10 },
    { key: 'MATERIAL', label: '材料上传', done: 6 },
    { key: 'PAYMENT', label: '缴费/绿色通道', done: 6 },
    { key: 'DORM', label: '宿舍确认', done: 8 },
    { key: 'CHECKIN', label: '现场报到', done: 3 },
    { key: 'CONFIRM', label: '学院确认', done: 1 }
  ],
  collegeRates: [
    { name: '信息工程学院', total: 10, prepared: 7, rate: 70.0 },
    { name: '智能制造学院', total: 2, prepared: 2, rate: 100.0 }
  ],
  riskAlerts: [
    { id: 'ori-r-001', level: 'HIGH', title: '2 名新生报到日未到校，需当日联系家长核实', link: 'exceptions' },
    { id: 'ori-r-002', level: 'MEDIUM', title: '2 份绿色通道申请超过 48 小时未完成审核', link: 'payment' },
    { id: 'ori-r-003', level: 'MEDIUM', title: '1 名新生宿舍床位冲突待确认', link: 'dorm' }
  ],
  todos: [
    { id: 'ori-t-001', label: '待审核迎新材料', value: 3, link: 'materials' },
    { id: 'ori-t-002', label: '待审批绿色通道', value: 2, link: 'payment' },
    { id: 'ori-t-003', label: '待处理迎新异常', value: 2, link: 'exceptions' },
    { id: 'ori-t-004', label: '未完成预报到学生', value: 3, link: 'progress' }
  ]
}
