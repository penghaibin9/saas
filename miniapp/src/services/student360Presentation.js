// Only machine-valued status fields enter these maps; names and business text stay intact.
const RISK = { NONE: '无', LOW: '低', MEDIUM: '中', HIGH: '高', CRITICAL: '严重', URGENT: '紧急' }
const STAGE = {
  ADMITTED: '录取', PRE_STUDENT_VERIFIED: '预备生', REGISTERED_PENDING_ENROLLMENT: '待注册',
  ENROLLED: '在校', INTERN: '实习', GRADUATING: '毕业年级', GRADUATED: '已毕业', ALUMNI: '校友'
}
const STATUS = { ACTIVE: '在读', ENROLLED: '在籍', SUSPENDED: '休学', INACTIVE: '非在籍', GRADUATED: '已毕业', DROPPED: '已退学', TRANSFERRED: '已转出' }
const key = value => String(value || '').trim().toUpperCase()
export const studentStatusText = value => STATUS[key(value)] || '状态待确认'
export const riskText = value => RISK[key(value)] || '风险待确认'
export const stageText = value => STAGE[key(value)] || '阶段待确认'
export const disciplineStatusText = value => key(value) === 'EFFECTIVE' ? '存在生效处分' : '处分状态待确认'
