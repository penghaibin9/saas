import { safeEnumLabel } from '../../../utils/presentationSafety.js'

const PLATFORM_STATUS_LABELS = Object.freeze({
  DRAFT: '草稿', PUBLISHED: '已发布', ACTIVE: '正常', EXPIRED: '已过期', REVOKED: '已撤销',
  OPEN: '待处理', IN_PROGRESS: '处理中', RESOLVED: '已解决', CLOSED: '已关闭',
  PENDING: '待处理', RUNNING: '执行中', SUCCEEDED: '已成功', FAILED: '失败',
  APPROVED: '已批准', ASSESSED: '已评估', IMPLEMENTING: '实施中', SCHEDULED: '已排期',
  VERIFIED: '已验证', ROLLED_BACK: '已回滚', COMPLETED: '已完成', CANCELLED: '已取消',
  CONTACTED: '已联系', COMMITTED: '已承诺', RENEWED: '已续约', AT_RISK: '存在风险', CHURNED: '已流失',
  PASSED: '已通过', DEGRADED: '服务降级', DEPRECATED: '已停用',
  TRIAL: '试用中', ENABLED: '已启用', DISABLED: '已停用', VOID: '已作废',
  REJECTED: '已驳回', TRANSFERRED: '已转办', RETURNED: '已退回',
  SUCCESS: '成功', DENIED: '已拒绝', WARNING: '警告', ERROR: '异常',
  UP: '运行正常', DOWN: '服务异常', OK: '正常', UNKNOWN: '待确认',
  READY: '已就绪', NOT_READY: '未就绪', READONLY: '只读', ARCHIVED: '已归档', BLOCKED: '已阻断',
  ADDED: '新增', REMOVED: '删除', MODIFIED: '修改', UNCHANGED: '未变化',
  WAITING_INPUT: '等待补充信息', COMPENSATING: '回滚处理中', COMPENSATED: '已回滚',
  NEEDS_MANUAL_REVIEW: '需人工复核'
})

const PLATFORM_ENUM_LABELS = Object.freeze({
  PLATFORM: '平台端', TENANT: '学校端',
  HIGH: '高', MEDIUM: '中', LOW: '低', CRITICAL: '严重', NORMAL: '正常',
  PRODUCTION: '生产环境', PROD: '生产环境', DEMO: '演示环境', TEST: '测试环境',
  PLATFORM_SUPER_ADMIN: '平台超级管理员', PLATFORM_OPERATOR: '平台运营人员',
  PLATFORM_SECURITY_AUDITOR: '平台安全审计员', SCHOOL_ADMIN: '学校管理员',
  COLLEGE_ADMIN: '院系管理员', COUNSELOR: '辅导员', GD_MENTOR: '指导教师',
  TEACHER: '教师', STUDENT: '学生',
  LOCAL: '服务器本地存储', COS: '腾讯云对象存储',
  PC: '电脑端', WEB: '网页端', MOBILE: '移动端', MINIAPP: '小程序端',
  FULL: '全量', INCREMENTAL: '增量', MANUAL: '手动', AUTOMATIC: '自动',
  READ: '读取', WRITE: '写入', DELETE: '删除', EXPORT: '导出', IMPORT: '导入'
})

export const PLATFORM_RULE_GROUP_LABELS = Object.freeze({
  student: '学生档案规则', approval: '审批规则', import: '导入规则', export: '导出规则',
  file: '文件规则', risk: '风险预警规则', message: '消息提醒规则', security: '安全规则',
  trial: '试用与到期规则', departure: '离校规则'
})

export const PLATFORM_RULE_LABELS = Object.freeze({
  studentNoRequired: '学号必填',
  idCardRequired: '身份证号必填',
  phoneRequired: '手机号必填',
  allowDuplicatePhone: '允许手机号重复',
  allowDuplicateIdCard: '允许身份证号重复',
  studentArchiveVoidNeedReason: '学生档案作废须填写原因',
  studentVoidReasonMinLength: '学生档案作废原因最少字数',
  studentEditAuditRequired: '学生信息修改须记录审计',
  rejectReasonRequired: '驳回须填写原因',
  rejectReasonMinLength: '驳回原因最少字数',
  transferReasonRequired: '转办须填写原因',
  approvalTimeoutHours: '审批超时时限（小时）',
  autoReminderEnabled: '启用审批自动提醒',
  approvalCanWithdraw: '允许撤回审批',
  approvalCanTransfer: '允许转办审批',
  importMaxRows: '单次导入最大行数',
  importAllowSkipError: '允许跳过错误数据',
  importRequireConfirm: '导入前须再次确认',
  importCheckDuplicateStudentNo: '导入时检查重复学号',
  importCheckDuplicatePhone: '导入时检查重复手机号',
  importCheckDuplicateIdCard: '导入时检查重复身份证号',
  exportNeedPurpose: '导出须填写用途',
  exportPurposeMinLength: '导出用途最少字数',
  exportWatermarkEnabled: '导出文件添加水印',
  exportPhoneMasked: '导出手机号脱敏',
  exportIdCardMasked: '导出身份证号脱敏',
  exportMaxRows: '单次导出最大行数',
  exportRateLimitPerMinute: '每分钟最多导出次数',
  uploadMaxSizeMb: '单个上传文件大小上限（兆字节）',
  allowedFileTypes: '允许上传的文件类型',
  blockedFileTypes: '禁止上传的文件类型',
  fileNameRandomize: '上传后随机重命名文件',
  fileDownloadNeedAudit: '下载文件须记录审计',
  fileRetentionDays: '文件保留天数',
  riskWarningEnabled: '启用风险预警',
  highRiskScoreThreshold: '高风险分数阈值',
  mediumRiskScoreThreshold: '中风险分数阈值',
  absenceDaysThreshold: '连续缺勤预警天数',
  internshipWeeklyReportDelayDays: '实习周报逾期预警天数',
  graduationTaskDelayDays: '毕业设计任务逾期预警天数',
  todoReminderEnabled: '启用待办提醒',
  messageUnreadReminderEnabled: '启用未读消息提醒',
  trialExpireReminderDays: '试用到期提前提醒天数',
  tenantExpireReminderDays: '租户到期提前提醒天数',
  loginFailLockEnabled: '启用登录失败锁定',
  loginFailMaxTimes: '触发锁定的登录失败次数',
  loginFailLockMinutes: '登录锁定时长（分钟）',
  accessTokenExpireMinutes: '访问凭证有效期（分钟）',
  refreshTokenExpireDays: '续期凭证有效期（天）',
  forceStrongPassword: '强制使用高强度密码',
  trialDefaultDays: '默认试用时长（天）',
  trialExpireReadOnly: '试用到期后转为只读',
  trialExpireAllowLogin: '试用到期后允许登录',
  trialExpireShowContactPhone: '试用到期后显示咨询电话',
  disciplineBlocks: '未解除违纪处分阻断离校'
})

export const PLATFORM_FEATURE_LABELS = Object.freeze({
  studentProfile: '学生主档', student360: '学生全景档案', orientation: '数字迎新', campusService: '在校服务',
  approval: '审批中心', todoMessage: '待办与消息', fileUpload: '文件上传', studentImport: '学生导入',
  studentExport: '学生导出', auditLog: '审计日志', graduation: '毕业设计', internship: '岗位实习',
  employment: '就业服务', riskWarning: '风险预警', miniapp: '小程序端', customBrand: '自定义品牌',
  workflowConfig: '流程配置', dataExport: '数据导出', apiAccess: '接口访问',
  studentAffairs: '学生事务', academicAffairs: '教务管理'
})

export const PLATFORM_SERVICE_LABELS = Object.freeze({
  API_GATEWAY: '后端接口服务',
  PC_ADMIN: '电脑管理端',
  STUDENT_PORTAL: '学生门户',
  MINIAPP: '小程序',
  MYSQL: '关系型数据库',
  REDIS: '缓存服务',
  WORKER: '后台任务服务',
  COS: '对象存储服务',
  CLAMAV: '病毒扫描服务',
  SMS_GATEWAY: '短信网关'
})

export function platformStatusLabel(value) {
  const raw = String(value ?? '').trim()
  if (/[\u4e00-\u9fff]/.test(raw)) return raw
  return safeEnumLabel({ value: raw.toUpperCase(), dictionary: PLATFORM_STATUS_LABELS, unknownLabel: '状态待确认' })
}

export function platformEnumLabel(value, unknownLabel = '类型待确认') {
  const raw = String(value ?? '').trim()
  if (/[\u4e00-\u9fff]/.test(raw)) return raw
  return safeEnumLabel({ value: raw.toUpperCase(), dictionary: PLATFORM_ENUM_LABELS, unknownLabel })
}

export function platformRoleLabel(value) {
  return platformEnumLabel(value, '其他业务角色')
}

export function platformServiceLabel(value, fallback = '其他服务') {
  const raw = String(value ?? '').trim()
  if (/[一-鿿]/.test(raw)) return raw
  return PLATFORM_SERVICE_LABELS[raw.toUpperCase()] || fallback
}
