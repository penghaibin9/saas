import { CONTACT_SHARING_MODES } from './selectionContract.js'

export const CONTACT_SHARING_OPTIONS = Object.freeze([
  { value: 'MASKED_ONLY', label: '仅脱敏联系方式', help: '企业始终只看到脱敏联系方式。' },
  { value: 'AFTER_INTERVIEW', label: '面试后可查看', help: '推荐：企业进入面试阶段后才可查看完整联系方式。' },
  { value: 'AFTER_ACCEPT_INTENT', label: '拟接收后可查看', help: '企业明确拟接收后才可查看完整联系方式。' },
  { value: 'IMMEDIATE', label: '立即允许查看', help: '提交后企业即可查看完整联系方式。' }
])

function list(raw, ...keys) {
  for (const key of keys) {
    if (Array.isArray(raw?.[key])) return raw[key]
  }
  return []
}

function optionalVersion(value) {
  if (value === undefined || value === null || value === '') return null
  const parsed = Number(value)
  return Number.isInteger(parsed) && parsed >= 0 ? parsed : null
}

function normalizeField(item, index) {
  if (typeof item === 'string') return { key: `field-${index}`, label: item, value: '' }
  return {
    key: String(item?.key || item?.code || `field-${index}`),
    label: String(item?.label || item?.name || item?.key || '资料项'),
    value: item?.value ?? item?.displayValue ?? '',
    source: String(item?.source || '').toUpperCase()
  }
}

export function normalizeMaterialPreview(raw = {}) {
  const sharedFields = list(raw, 'sharedFields', 'fields', 'materialFields').map(normalizeField)
  const schoolFields = list(raw, 'schoolFields', 'verifiedFields').map(normalizeField)
  const studentFields = list(raw, 'studentFields', 'selfFilledFields').map(normalizeField)
  return {
    previewHash: String(raw.previewHash || raw.materialPreviewHash || ''),
    consentPolicyVersion: String(raw.consentPolicyVersion || raw.policyVersion || ''),
    profileVersion: optionalVersion(raw.profileVersion),
    groupVersion: optionalVersion(raw.groupVersion ?? raw.volunteerGroupVersion),
    sharedFields,
    schoolFields,
    studentFields,
    maskedContact: String(raw.maskedContact || raw.contactPreview || ''),
    statementCount: Number(raw.statementCount || raw.applicationStatementCount || 0),
    pdfPreviewUrl: String(raw.pdfPreviewUrl || raw.previewUrl || '')
  }
}

export function normalizeContactSharingMode(value) {
  const mode = String(value || 'AFTER_INTERVIEW').toUpperCase()
  return CONTACT_SHARING_MODES.includes(mode) ? mode : 'AFTER_INTERVIEW'
}

export function buildPdfPreviewRequest({ previewHash, contactSharingMode }) {
  if (!previewHash) throw new Error('请先获取企业视角材料预览')
  return {
    materialPreviewHash: previewHash,
    contactSharingMode: normalizeContactSharingMode(contactSharingMode),
    includeVolunteerApplications: false
  }
}
