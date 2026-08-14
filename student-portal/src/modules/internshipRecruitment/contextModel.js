const PHASE_LABELS = Object.freeze({
  DRAFT: '尚未开放',
  OPEN: '选岗进行中',
  FROZEN: '选岗已冻结',
  CLOSED: '本季已结束',
  ARCHIVED: '历史招聘季'
})

const GROUP_LABELS = Object.freeze({
  DRAFT: '志愿待提交',
  SUBMITTED: '志愿已提交',
  LOCKED: '等待学校最终确认',
  NEEDS_REVISION: '可重新调整',
  APPROVED: '学校已确认',
  CONFIRMED: '学校已确认'
})

function numberOf(value, fallback = 0) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : fallback
}

export function normalizeRecruitmentContext(raw = {}) {
  const campaign = raw.campaign || raw.recruitmentCampaign || {}
  const stats = raw.stats || raw.summary || {}
  const volunteer = raw.volunteerGroup || raw.volunteer || {}
  const status = String(campaign.status || raw.campaignStatus || '').toUpperCase()
  const groupStatus = String(volunteer.status || raw.volunteerStatus || 'DRAFT').toUpperCase()
  const canSelect = raw.canSelect ?? raw.selectionOpen ?? status === 'OPEN'

  return {
    campaignId: campaign.id ?? raw.campaignId ?? null,
    campaignName: campaign.name || raw.campaignName || '当前招聘季',
    status,
    phaseLabel: raw.phaseLabel || PHASE_LABELS[status] || '阶段待确认',
    selectionDeadline: campaign.studentSelectionEndAt || raw.studentSelectionEndAt || raw.selectionDeadline || '',
    schoolConfirmDeadline: volunteer.teacherConfirmDeadline || raw.teacherConfirmDeadline || '',
    publishedPositions: numberOf(stats.publishedPositions ?? stats.positionCount ?? raw.publishedPositions),
    partnerCompanies: numberOf(stats.partnerCompanies ?? stats.companyCount ?? raw.partnerCompanies),
    matchedPositions: numberOf(stats.matchedPositions ?? raw.matchedPositions),
    selectedVolunteers: numberOf(volunteer.selectedCount ?? raw.selectedVolunteerCount),
    groupStatus,
    groupStatusLabel: GROUP_LABELS[groupStatus] || groupStatus,
    lockedCompanyName: volunteer.lockedCompanyName || raw.lockedCompanyName || '',
    canSelect: Boolean(canSelect),
    blockReason: raw.blockReason || raw.selectionBlockReason || ''
  }
}

export function formatDeadline(value) {
  if (!value) return '待学校公布'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false
  }).format(date)
}

export function selectionConclusion(context) {
  if (context.groupStatus === 'LOCKED') {
    return context.lockedCompanyName
      ? `${context.lockedCompanyName} 已拟接收，等待学校最终确认`
      : '企业已拟接收，等待学校最终确认'
  }
  if (context.groupStatus === 'NEEDS_REVISION') return '本轮可重新调整志愿'
  if (['APPROVED', 'CONFIRMED'].includes(context.groupStatus)) return '学校已完成最终确认，正式落岗结果以实习记录为准'
  if (!context.canSelect) return context.blockReason || '当前阶段暂不可新增或调整志愿'
  if (context.selectedVolunteers > 0) return `已选 ${context.selectedVolunteers}/3 个志愿，可继续调整后整组提交`
  return '当前可选岗，请从学校认可岗位中选择 1–3 个志愿'
}
