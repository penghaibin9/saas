/**
 * 数字迎新中心 — 前端展示层元数据（字典/列配置，非业务权限或业务数据）。
 * 业务数据一律走真实后端 /api/v1/orientation/*。
 */

export const nowText = () => {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
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
    { key: 'batchAssign', label: '批量分配辅导员', permission: 'orientation.student.batchAssign' }
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
      { key: 'batchNo', label: '迎新批次编号', required: true, example: 'ORI-2026' },
      { key: 'admissionNo', label: '录取编号', required: true, example: 'LQ2026010001' },
      { key: 'candidateNo', label: '候选人编号', required: false, example: 'CAND-0001' },
      { key: 'name', label: '姓名', required: true, example: '示例姓名' },
      { key: 'gender', label: '性别', required: false, example: '男' },
      { key: 'idCard', label: '身份证号', required: false, example: '' },
      { key: 'phone', label: '手机号', required: false, example: '' },
      { key: 'collegeCode', label: '学院代码', required: true, example: 'COL-INFO' },
      { key: 'majorCode', label: '专业代码', required: true, example: 'MAJ-SOFTWARE' },
      { key: 'classCode', label: '班级代码', required: true, example: 'CLS-2601' },
      { key: 'grade', label: '年级', required: false, example: '2026' },
      { key: 'origin', label: '生源地', required: false, example: '湖南长沙' },
      { key: 'admissionType', label: '录取类型', required: false, example: '统招' }
    ]
  }
}

/* ---------------- 导出配置 ---------------- */
export const exportOptions = {
  scopes: [
    { value: 'SCOPE_ALL', label: '当前账号数据范围内全部迎新台账' }
  ],
  fieldGroups: {
    studentList: [
      { key: 'ledger', label: '迎新综合台账', fields: ['迎新批次编号', '姓名', '录取编号', '学院', '专业', '班级', '报到状态', '缴费状态', '宿舍状态', '风险'] }
    ]
  },
  maskDefault: true,
  idCardPlainForbidden: true,
  watermarkNote: '服务端固定按当前账号数据范围导出，并写入学校名、操作人、时间和用途水印。',
  auditNotice: '本次导出行为将被完整记录并可追溯，请确认导出用途合规。'
}
