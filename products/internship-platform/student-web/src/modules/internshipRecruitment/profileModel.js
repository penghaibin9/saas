export const SCHOOL_VERIFIED_FIELDS = Object.freeze([
  'name', 'studentNo', 'college', 'major', 'grade', 'className'
])

export const STUDENT_EDITABLE_FIELDS = Object.freeze([
  'selfIntroduction', 'strengths', 'skillTags', 'availableFrom', 'locationPreferences'
])

export const PROFILE_ITEM_TYPES = Object.freeze([
  { value: 'PROJECT', label: '项目' },
  { value: 'PRACTICE', label: '实践经历' },
  { value: 'CERTIFICATE', label: '技能证书' },
  { value: 'AWARD', label: '获奖' },
  { value: 'PORTFOLIO', label: '作品' },
  { value: 'SKILL_EVIDENCE', label: '技能证明' }
])

function first(raw, ...keys) {
  for (const key of keys) {
    if (raw?.[key] !== undefined && raw?.[key] !== null) return raw[key]
  }
  return null
}

function stringList(value) {
  if (Array.isArray(value)) return value.filter(Boolean).map(String)
  return String(value || '').split(/[,，]/).map((item) => item.trim()).filter(Boolean)
}

export function normalizeInternshipProfile(raw = {}) {
  const school = raw.schoolFacts || raw.student || {}
  const profile = raw.profile && typeof raw.profile === 'object' ? raw.profile : raw
  const skillTags = first(profile, 'skillTags') ?? first(raw, 'skillTags')
  const locations = first(profile, 'expectedLocations', 'locationPreferences', 'preferredLocations')
    ?? first(raw, 'expectedLocations', 'locationPreferences', 'preferredLocations')
  return {
    version: Number(first(profile, 'profileVersion', 'version') ?? first(raw, 'profileVersion', 'version') ?? 0) || 0,
    school: {
      name: first(school, 'realName', 'name', 'studentName') || first(raw, 'realName', 'name', 'studentName') || '',
      studentNo: first(school, 'studentNo', 'studentNumber') || first(raw, 'studentNo', 'studentNumber') || '',
      college: first(school, 'collegeName', 'college') || first(raw, 'collegeName', 'college') || '',
      major: first(school, 'majorName', 'major') || first(raw, 'majorName', 'major') || '',
      grade: first(school, 'grade', 'gradeName') || first(raw, 'grade', 'gradeName') || '',
      className: first(school, 'className', 'class') || first(raw, 'className', 'class') || ''
    },
    selfIntroduction: String(first(profile, 'selfIntro', 'selfIntroduction', 'introduction') || ''),
    strengths: String(first(profile, 'strengths', 'advantages') || ''),
    skillTags: stringList(skillTags),
    availableFrom: first(profile, 'availableFrom', 'arrivalDate') || '',
    locationPreferences: stringList(locations)
  }
}

export function buildInternshipProfileUpdate(profile) {
  const value = normalizeInternshipProfile(profile)
  return {
    expectedProfileVersion: value.version,
    selfIntro: value.selfIntroduction.trim(),
    strengths: value.strengths.trim(),
    skillTags: value.skillTags.map((item) => item.trim()).filter(Boolean),
    availableFrom: value.availableFrom || null,
    expectedLocations: value.locationPreferences.map((item) => item.trim()).filter(Boolean)
  }
}

export function normalizeProfileCompleteness(raw = {}) {
  const percent = Math.min(100, Math.max(0, Number(raw.percent ?? raw.completeness ?? 0) || 0))
  const blockers = Array.isArray(raw.blockers) ? raw.blockers : []
  const ready = Boolean(raw.readyToSubmit ?? raw.canSubmit ?? (percent === 100 && blockers.length === 0))
  return { percent, blockers, ready }
}

export function normalizeProfileItems(raw = []) {
  const items = Array.isArray(raw) ? raw : raw?.items || raw?.list || []
  return items.map((item) => {
    const rawType = String(item.type || item.itemType || '').toUpperCase()
    const type = rawType === 'WORK' ? 'PORTFOLIO' : rawType
    const fileIds = Array.isArray(item.fileIds) ? item.fileIds : []
    return {
      id: item.id,
      type,
      title: item.title || item.name || '',
      description: item.description || item.content || '',
      issuedBy: item.issuedBy || item.organization || '',
      occurredAt: item.occurredAt || item.date || item.endDate || item.startDate || '',
      fileName: item.fileName || item.attachmentName || (fileIds.length ? `${fileIds.length} 个附件` : '')
    }
  })
}
