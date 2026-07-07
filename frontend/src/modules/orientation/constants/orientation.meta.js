/**
 * 数字迎新中心 — 前端展示层元数据（角色/字典/列配置，非业务 mock 数据）。
 * 业务数据一律走真实后端 /api/v1/orientation/*。
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
