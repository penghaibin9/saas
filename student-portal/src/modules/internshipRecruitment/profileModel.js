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
  { value: 'WORK', label: '作品' }
])

function first(raw, ...keys) {
  for (const key of keys) {
    if (raw?.[key] !== undefined && raw?.[key] !== null) return raw[key]
  }
  return null
}

export function normalizeInternshipProfile(raw = {}) {
  const school = raw.schoolFacts || raw.student || {}
  return {
    version: Number(first(raw, 'version', 'profileVersion') || 0),
    school: {
      name: first(school, 'name', 'studentName') || first(raw, 'name', 'studentName') || '',
      studentNo: first(school, 'studentNo', 'studentNumber') || first(raw, 'studentNo', 'studentNumber') || '',
      college: first(school, 'college', 'collegeName') || first(raw, 'college', 'collegeName') || '',
      major: first(school, 'major', 'majorName') || first(raw, 'major', 'majorName') || '',
      grade: first(school, 'grade', 'gradeName') || first(raw, 'grade', 'gradeName') || '',
      className: first(school, 'className', 'class') || first(raw, 'className', 'class') || ''
    },
    selfIntroduction: first(raw, 'selfIntroduction', 'introduction') || '',
    strengths: first(raw, 'strengths', 'advantages') || '',
    skillTags: Array.isArray(raw.skillTags) ? raw.skillTags.filter(Boolean).map(String) : [],
    availableFrom: first(raw, 'availableFrom', 'arrivalDate') || '',
    locationPreferences: Array.isArray(raw.locationPreferences)
      ? raw.locationPreferences.filter(Boolean).map(String)
      : String(first(raw, 'locationPreferences', 'preferredLocations') || '').split(/[,，]/).map((v) => v.trim()).filter(Boolean)
  }
}

export function buildInternshipProfileUpdate(profile) {
  const value = normalizeInternshipProfile(profile)
  return {
    expectedVersion: value.version,
    selfIntroduction: value.selfIntroduction.trim(),
    strengths: value.strengths.trim(),
    skillTags: value.skillTags.map((item) => item.trim()).filter(Boolean),
    availableFrom: value.availableFrom || null,
    locationPreferences: value.locationPreferences.map((item) => item.trim()).filter(Boolean)
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
  return items.map((item) => ({
    id: item.id,
    type: String(item.type || item.itemType || '').toUpperCase(),
    title: item.title || item.name || '',
    description: item.description || item.content || '',
    issuedBy: item.issuedBy || item.organization || '',
    occurredAt: item.occurredAt || item.date || '',
    fileName: item.fileName || item.attachmentName || ''
  }))
}
