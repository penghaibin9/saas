export const INTERNSHIP_SELECTION_ROUTE = '/internship/selection'
export const INTERNSHIP_SELECTION_TITLE = '实习选岗'

export const CATALOG_PAGE_SIZE = 20
export const CATALOG_MAX_PAGE_SIZE = 100

export const CATALOG_SORTS = Object.freeze([
  'RECOMMENDED',
  'LATEST',
  'REMUNERATION',
  'REMAINING'
])

export const POSITION_MATCH_STATES = Object.freeze([
  'MATCHED',
  'UNLIMITED',
  'UNKNOWN',
  'POSSIBLE_MISMATCH'
])

export const CONTACT_SHARING_MODES = Object.freeze([
  'MASKED_ONLY',
  'AFTER_INTERVIEW',
  'AFTER_ACCEPT_INTENT',
  'IMMEDIATE'
])

export const SELECTION_BREAKPOINTS = Object.freeze({
  threeColumn: 1440,
  floatingVolunteer: 1100,
  singleColumn: 900
})

export const POSITION_CARD_LAYOUT = Object.freeze({
  title: { fontSize: 18, color: '#1a1a1a' },
  remuneration: { fontSize: 16, color: '#fa541c' },
  tag: { fontSize: 12, background: '#f0f5ff', radius: 4 },
  primaryAction: '#2f6bff',
  card: { background: '#ffffff', border: '#eef0f3', radius: 10 }
})

function requireNonNegativeVersion(value, label) {
  const parsed = Number(value)
  if (!Number.isInteger(parsed) || parsed < 0) throw new Error(`${label}缺失，请刷新后重试`)
  return parsed
}

export function normalizeCatalogQuery(input = {}) {
  const page = Math.max(1, Number(input.page || 1) || 1)
  const requestedPageSize = Number(input.pageSize || CATALOG_PAGE_SIZE) || CATALOG_PAGE_SIZE
  const pageSize = Math.min(CATALOG_MAX_PAGE_SIZE, Math.max(1, requestedPageSize))
  const sort = CATALOG_SORTS.includes(input.sort) ? input.sort : 'RECOMMENDED'
  const query = { page, pageSize, sort }
  for (const key of [
    'keyword', 'city', 'companyId', 'accommodation', 'meal', 'industry', 'scale',
    'nightShift', 'weeklyHours', 'remaining', 'publishedFrom', 'majorMatched', 'remuneration'
  ]) {
    const value = input[key]
    if (value !== undefined && value !== null && value !== '') query[key] = value
  }
  return query
}

export function buildVolunteerDraftPayload({ batchId, internshipId, items, expectedGroupVersion, expectedRecordVersion, expectedApplicationVersions }) {
  const normalized = (items || [])
    .filter((item) => item && item.positionId)
    .map((item, index) => ({
      volunteerNo: Number(item.volunteerNo || index + 1),
      positionId: Number(item.positionId),
      applicationStatement: String(item.applicationStatement || '').trim()
    }))
    .sort((a, b) => a.volunteerNo - b.volunteerNo)

  if (normalized.length < 1 || normalized.length > 3) throw new Error('岗位志愿必须为 1–3 个')
  if (normalized.some((item) => !Number.isInteger(item.positionId) || item.positionId <= 0)) throw new Error('岗位志愿包含无效岗位')
  if (new Set(normalized.map((item) => item.positionId)).size !== normalized.length) throw new Error('同一岗位不能重复加入志愿')
  if (normalized.some((item, index) => item.volunteerNo !== index + 1)) throw new Error('岗位志愿必须使用连续的第一/第二/第三固定槽位')

  return {
    batchId,
    internshipId,
    items: normalized,
    expectedGroupVersion: requireNonNegativeVersion(expectedGroupVersion, '志愿组版本'),
    expectedRecordVersion,
    expectedApplicationVersions: expectedApplicationVersions || {}
  }
}

export function buildVolunteerSubmitPayload({
  expectedGroupVersion,
  expectedProfileVersion,
  consentPolicyVersion,
  contactSharingMode = 'AFTER_INTERVIEW',
  confirmMaterialPreviewHash
}) {
  if (!CONTACT_SHARING_MODES.includes(contactSharingMode)) throw new Error('联系方式共享策略无效')
  if (!consentPolicyVersion || !confirmMaterialPreviewHash) throw new Error('提交前必须确认企业视角材料预览与隐私授权')
  return {
    expectedGroupVersion: requireNonNegativeVersion(expectedGroupVersion, '志愿组版本'),
    expectedProfileVersion: requireNonNegativeVersion(expectedProfileVersion, '实习档案版本'),
    consentPolicyVersion,
    contactSharingMode,
    confirmMaterialPreviewHash
  }
}
