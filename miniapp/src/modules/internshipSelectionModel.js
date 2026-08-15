export const MOBILE_MATCH_LABELS = Object.freeze({
  MATCHED: '专业匹配',
  UNLIMITED: '不限专业',
  UNKNOWN: '匹配待确认',
  POSSIBLE_MISMATCH: '可能不匹配'
})

function first(raw, ...keys) {
  for (const key of keys) {
    if (raw?.[key] !== undefined && raw?.[key] !== null && raw?.[key] !== '') return raw[key]
  }
  return null
}

export function normalizeMobileSelectionContext(raw = {}) {
  const campaign = raw.campaign || raw.recruitmentCampaign || {}
  const stats = raw.stats || raw.summary || {}
  const volunteer = raw.volunteerGroup || raw.volunteer || {}
  const status = String(campaign.status || raw.campaignStatus || '').toUpperCase()
  const groupStatus = String(volunteer.status || raw.volunteerStatus || 'DRAFT').toUpperCase()
  return {
    campaignName: campaign.name || raw.campaignName || '当前招聘季',
    phaseLabel: raw.phaseLabel || ({ OPEN: '选岗进行中', FROZEN: '选岗已冻结', CLOSED: '本季已结束' }[status] || '阶段待确认'),
    selectionDeadline: campaign.studentSelectionEndAt || raw.studentSelectionEndAt || '',
    publishedPositions: Number(stats.publishedPositions ?? raw.publishedPositions ?? 0) || 0,
    partnerCompanies: Number(stats.partnerCompanies ?? raw.partnerCompanies ?? 0) || 0,
    matchedPositions: Number(stats.matchedPositions ?? raw.matchedPositions ?? 0) || 0,
    selectedVolunteers: Number(volunteer.selectedCount ?? raw.selectedVolunteerCount ?? 0) || 0,
    groupStatus,
    canSelect: Boolean(raw.canSelect ?? raw.selectionOpen ?? status === 'OPEN'),
    blockReason: raw.blockReason || raw.selectionBlockReason || ''
  }
}

export function normalizeMobilePosition(raw = {}) {
  const matchStateRaw = String(first(raw, 'matchState', 'majorMatchState') || 'UNKNOWN').toUpperCase()
  const matchState = Object.hasOwn(MOBILE_MATCH_LABELS, matchStateRaw) ? matchStateRaw : 'UNKNOWN'
  const tags = []
  if (matchState) tags.push(MOBILE_MATCH_LABELS[matchState])
  if (raw.accommodationProvided === true) tags.push('提供住宿')
  if (raw.mealProvided === true) tags.push('提供餐食')
  const benefits = Array.isArray(raw.benefitTags) ? raw.benefitTags : []
  benefits.forEach((tag) => { if (tags.length < 3 && tag) tags.push(String(tag)) })
  return {
    id: first(raw, 'id', 'positionId'),
    title: first(raw, 'title', 'positionName') || '岗位名称待完善',
    remuneration: first(raw, 'remunerationDisplay', 'salaryRange', 'remuneration') || '薪酬待确认',
    companyName: first(raw, 'companyName') || raw.company?.name || '企业信息待完善',
    workLocation: first(raw, 'workLocation', 'city') || '地点待定',
    remaining: Number(first(raw, 'remaining', 'remainingQuota', 'remainingCount') || 0),
    matchState,
    tags: tags.slice(0, 3)
  }
}

export function normalizeMobilePage(raw = {}) {
  const items = Array.isArray(raw) ? raw : raw.items || raw.list || []
  return {
    items: items.map(normalizeMobilePosition),
    total: Number(raw.total ?? raw.pagination?.total ?? items.length) || 0,
    page: Math.max(1, Number(raw.page || raw.pagination?.page || 1) || 1),
    pageSize: Math.max(1, Number(raw.pageSize || raw.pagination?.pageSize || 20) || 20)
  }
}

export function formatMobileDeadline(value) {
  if (!value) return '待学校公布'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return `${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}
