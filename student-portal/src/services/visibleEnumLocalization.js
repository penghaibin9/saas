export const VISIBLE_ENUM_LABELS = Object.freeze({
  PENDING_REVIEW: '待审核',
  PENDING_HANDLE: '待处理',
  PENDING: '待处理',
  NOT_SUBMITTED: '未提交',
  SUBMITTED: '已提交',
  REVIEWING: '审核中',
  APPROVED: '已通过',
  REJECTED: '未通过',
  RETURNED: '已退回',
  PROCESSING: '处理中',
  IN_PROGRESS: '进行中',
  DONE: '已完成',
  COMPLETED: '已完成',
  CANCELLED: '已取消',
  CANCELED: '已取消',
  DRAFT: '草稿',
  ACTIVE: '生效中',
  INACTIVE: '已停用',
  PASSED: '已通过',
  FAILED: '未通过',
  VERIFIED: '已核验',
  UNVERIFIED: '待核验',
  NOT_STARTED: '尚未开始',
  CHECKED_IN: '已报到',
  SIGNED: '已签署',
  UNSIGNED: '待签署',
  PUBLISHED: '已发布',
  OPEN: '开放中',
  CLOSED: '已关闭',
  EXPIRED: '已过期',
  NORMAL: '正常',
  WARNING: '预警',
  ONBOARD: '在岗',
  OFFBOARD: '已离岗',
  EMPLOYED: '已就业',
  UNEMPLOYED: '暂未就业',
  JOB_SEEKING: '求职中',
  GRANTED: '已获得',
  ISSUED: '已发放',
  DELIVERED: '已送达',
  RESOLVED: '已处理',
  PENDING_CONFIRMATION: '待确认',

  PERSONAL: '事假',
  SICK: '病假',
  OFFICIAL: '公假',
  HOME: '探亲假',
  HOSPITAL: '住院假',
  GOOUT: '外出',
  OTHER: '其他',

  GENERAL: '一般困难',
  DIFFICULT: '困难',
  SPECIAL: '特别困难',
  CLASS_REVIEW: '班级评议',
  SCHOLARSHIP: '奖学金',
  GRANT: '助学金',
  WORK_STUDY: '勤工助学',
  LOAN: '助学贷款',
  TUITION_REDUCTION: '学费减免',
  TEMPORARY_AID: '临时补助',

  COUNSELOR_REVIEW: '辅导员审核',
  COLLEGE_REVIEW: '学院审核',
  SCHOOL_REVIEW: '学校审核',
  DORM_MANAGER_REVIEW: '宿管审核',
  DORM_REVIEW: '宿舍审核',
  TEACHER_REVIEW: '指导教师审核',
  ENTERPRISE_REVIEW: '企业审核',
  DEPARTMENT_REVIEW: '部门审核',
  FINAL_REVIEW: '终审',
  STUDENT_CONFIRM: '学生确认',
  GUARDIAN_CONFIRM: '监护人确认',

  WRONG: '记错申诉',
  MISSING: '缺记申诉',
  SECOND_CLASS: '第二课堂',
  MORAL: '德育积分',
  VOLUNTEER_HOUR: '志愿时长',

  SELF_ARRANGED: '自主实习',
  SCHOOL_ARRANGED: '学校安排',
  CHANGE_POSITION: '岗位调整',
  CHANGE_COMPANY: '单位调整',
  WITHDRAW: '退岗',
  WEEKLY: '周报',
  MONTHLY: '月报',
  SUMMARY: '总结',
  ON_SITE: '现场',
  REMOTE: '远程',
  OUT_OF_RANGE: '超出打卡范围',

  SIGNED_CONTRACT: '签约就业',
  FLEXIBLE_EMPLOYMENT: '灵活就业',
  FURTHER_EDUCATION: '升学',
  ENTREPRENEURSHIP: '自主创业',

  TOPIC_SELECTED: '已选题',
  PROPOSAL_APPROVED: '开题通过',
  MIDTERM_APPROVED: '中期通过',
  DEFENSE_SCHEDULED: '已安排答辩',
  ARCHIVED: '已归档',
  PENDING_ADVISOR_REVIEW: '待导师审核'
})

export const VISIBLE_ENUM_WHITELIST = new Set([
  'GPA', 'API', 'PC', 'H5', 'UI', 'ID', 'URL', 'HTTP', 'HTTPS',
  'JSON', 'CSV', 'XLS', 'XLSX', 'PDF', 'QR', 'SQL', 'AI', 'V5'
])

const UNDERSCORE_ENUM_RE = /\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b/g
const UPPER_WORD_RE = /\b[A-Z][A-Z0-9]{2,}\b/g

/**
 * 仅本地化一个明确的枚举值。
 * 不扫描、不替换句子中的单词，避免改写学生填写内容、消息正文和业务原始文本。
 */
export function localizeVisibleEnumText(value) {
  const raw = String(value ?? '')
  const key = raw.trim().toUpperCase()
  return VISIBLE_ENUM_LABELS[key] || raw
}

export function findVisibleEnumTokens(value) {
  const text = String(value ?? '')
  const tokens = new Set(text.match(UNDERSCORE_ENUM_RE) || [])
  for (const token of text.match(UPPER_WORD_RE) || []) {
    if (Object.prototype.hasOwnProperty.call(VISIBLE_ENUM_LABELS, token)) tokens.add(token)
  }
  return [...tokens].filter((token) => !VISIBLE_ENUM_WHITELIST.has(token))
}
