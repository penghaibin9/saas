/**
 * 招聘季（企业招募轮次）前端常量。
 * 状态机与阶段名严格对齐后端 app/modules/internship/enterprise_collaboration_contract.py
 * 的 RECRUITMENT_CAMPAIGN_TRANSITIONS / RECRUITMENT_CAMPAIGN_DERIVED_PHASES，
 * 前端只做展示与按钮可用性提示，真正的状态校验由后端负责。
 */

/** 招聘季状态 */
export const CAMPAIGN_STATUS_OPTIONS = [
  { value: 'DRAFT', label: '草稿' },
  { value: 'OPEN', label: '进行中' },
  { value: 'FROZEN', label: '已冻结' },
  { value: 'CLOSED', label: '已关闭' },
  { value: 'ARCHIVED', label: '已归档' }
]

export const CAMPAIGN_STATUS_LABEL = CAMPAIGN_STATUS_OPTIONS.reduce((acc, o) => {
  acc[o.value] = o.label
  return acc
}, {})

export const CAMPAIGN_STATUS_TAG = {
  DRAFT: 'default',
  OPEN: 'success',
  FROZEN: 'warning',
  CLOSED: 'info',
  ARCHIVED: 'default'
}

/**
 * 允许的状态迁移（与后端 RECRUITMENT_CAMPAIGN_TRANSITIONS 一一对应）。
 * 注意：FROZEN 不能回到 OPEN——冻结是不可逆的收敛动作，只能继续关闭。
 */
export const CAMPAIGN_TRANSITIONS = {
  DRAFT: ['OPEN'],
  OPEN: ['FROZEN', 'CLOSED'],
  FROZEN: ['CLOSED'],
  CLOSED: ['ARCHIVED'],
  ARCHIVED: []
}

/** 后端派生阶段（不落库，按当前时间与各时间窗推导） */
export const CAMPAIGN_PHASE_LABEL = {
  PREPARE: '准备中',
  INVITING: '企业邀请中',
  POSITION_SUBMITTING: '岗位报送中',
  STUDENT_SELECTING: '学生选岗中',
  ENTERPRISE_DECIDING: '企业决策中',
  SCHOOL_CONFIRMING: '学校确认中',
  FROZEN: '已冻结',
  CLOSED: '已关闭',
  ARCHIVED: '已归档'
}

/** 企业在招聘季中的参与状态 */
export const PARTICIPATION_STATUS_OPTIONS = [
  { value: 'INVITED', label: '待接受邀请' },
  { value: 'ACCEPTED', label: '已入驻' },
  { value: 'DECLINED', label: '企业已谢绝' },
  { value: 'SUSPENDED', label: '已暂停' },
  { value: 'REVOKED', label: '已撤销' }
]

export const PARTICIPATION_STATUS_LABEL = PARTICIPATION_STATUS_OPTIONS.reduce((acc, o) => {
  acc[o.value] = o.label
  return acc
}, {})

export const PARTICIPATION_STATUS_TAG = {
  INVITED: 'warning',
  ACCEPTED: 'success',
  DECLINED: 'info',
  SUSPENDED: 'warning',
  REVOKED: 'danger'
}

/** 邀请来源 */
export const INVITE_SOURCE_LABEL = {
  MANUAL: '学校手动邀请',
  REUSE: '沿用往期合作',
  PUBLIC_REQUEST: '企业主动申请'
}

/** 企业成员角色（企业侧账号在本企业内的身份） */
export const MEMBER_ROLE_OPTIONS = [
  { value: 'COMPANY_ADMIN', label: '企业管理员（可管岗位与成员）' },
  { value: 'HR', label: 'HR（招聘对接）' },
  { value: 'MENTOR', label: '企业导师（带教学生）' }
]

export function campaignStatusLabel(status) {
  return CAMPAIGN_STATUS_LABEL[status] || status || '—'
}

export function participationStatusLabel(status) {
  return PARTICIPATION_STATUS_LABEL[status] || status || '—'
}

export function canTransition(status, target) {
  return (CAMPAIGN_TRANSITIONS[status] || []).includes(target)
}

/** 日期 → 当日 00:00:00 的无时区 ISO 串（后端按 naive datetime 解析） */
export function toIsoStart(date) {
  const d = String(date || '').slice(0, 10)
  return d ? `${d}T00:00:00` : null
}

/** 日期 → 当日 23:59:59，避免「选到当天却在当天失效」 */
export function toIsoEnd(date) {
  const d = String(date || '').slice(0, 10)
  return d ? `${d}T23:59:59` : null
}
