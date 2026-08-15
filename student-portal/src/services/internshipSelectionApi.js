/**
 * E-A03 学生选岗 API facade。
 *
 * A01 已落 StudentInternshipProfile / immutable ApplicationMaterialSnapshot /
 * InternshipVolunteerGroup canonical services，但 student/mobile Catalog/Profile/Volunteer HTTP
 * facade 尚未完整注册。本文件只负责冻结 endpoint，并把 A03 兼容字段收敛到 A01 canonical
 * service payload；禁止回落旧 InternshipApplication 三次写入，也禁止前端自造第二套真值。
 */
import { request } from './request'
import { normalizeCatalogQuery } from '../modules/internshipRecruitment/selectionContract.js'

const enc = (value) => encodeURIComponent(String(value ?? ''))
const hasOwn = (value, key) => Object.prototype.hasOwnProperty.call(value || {}, key)
const latestReads = new Map()

function latestRead(key, task, fallback = null) {
  let exposed
  const raw = Promise.resolve().then(task)
  exposed = raw.then(
    (value) => latestReads.get(key) === exposed ? value : latestReads.get(key),
    (error) => {
      if (latestReads.get(key) !== exposed) return latestReads.get(key)
      if (fallback) return fallback(error)
      throw error
    }
  )
  latestReads.set(key, exposed)
  return exposed
}

function unavailableContext() {
  return {
    campaignStatus: 'UNAVAILABLE',
    phaseLabel: '招聘季信息暂不可用',
    canSelect: false,
    selectionBlockReason: '暂时无法读取学校招聘季信息，请重新加载后再调整志愿。'
  }
}

function normalizeProfileWriteBody(body = {}) {
  const out = {}
  const expected = body.expectedProfileVersion ?? body.expectedVersion
  if (expected !== undefined && expected !== null) out.expectedProfileVersion = expected
  if (hasOwn(body, 'selfIntro') || hasOwn(body, 'selfIntroduction')) out.selfIntro = body.selfIntro ?? body.selfIntroduction ?? ''
  if (hasOwn(body, 'strengths')) out.strengths = body.strengths ?? ''
  if (hasOwn(body, 'skillTags')) out.skillTags = Array.isArray(body.skillTags) ? body.skillTags : []
  if (hasOwn(body, 'availableFrom')) out.availableFrom = body.availableFrom || null
  if (hasOwn(body, 'availableUntil')) out.availableUntil = body.availableUntil || null
  if (hasOwn(body, 'expectedLocations') || hasOwn(body, 'locationPreferences')) {
    out.expectedLocations = body.expectedLocations ?? body.locationPreferences ?? []
  }
  return out
}

function normalizeProfileItemWriteBody(body = {}) {
  const out = {}
  const rawType = body.itemType ?? body.type
  if (rawType !== undefined && rawType !== null) {
    const type = String(rawType).toUpperCase()
    out.itemType = type === 'WORK' ? 'PORTFOLIO' : type
  }
  if (hasOwn(body, 'title')) out.title = body.title
  if (hasOwn(body, 'organization') || hasOwn(body, 'issuedBy')) out.organization = body.organization ?? body.issuedBy ?? ''
  if (hasOwn(body, 'description')) out.description = body.description ?? ''
  if (hasOwn(body, 'startDate') || hasOwn(body, 'occurredAt')) out.startDate = body.startDate ?? body.occurredAt ?? null
  if (hasOwn(body, 'endDate')) out.endDate = body.endDate || null
  if (hasOwn(body, 'level')) out.level = body.level ?? ''
  if (hasOwn(body, 'sortOrder')) out.sortOrder = body.sortOrder
  if (hasOwn(body, 'fileIds')) out.fileIds = Array.isArray(body.fileIds) ? body.fileIds : []
  if (hasOwn(body, 'appendFileIds')) out.appendFileIds = Array.isArray(body.appendFileIds) ? body.appendFileIds : []
  return out
}

export const internshipSelectionApi = {
  context() { return latestRead('context', () => request('/portal/internship/catalog/context'), unavailableContext) },
  positions(query = {}) { return request('/portal/internship/catalog/positions', { params: normalizeCatalogQuery(query) }) },
  position(positionId) { return latestRead('position', () => request(`/portal/internship/catalog/positions/${enc(positionId)}`)) },
  company(companyId) { return latestRead('company', () => request(`/portal/internship/catalog/companies/${enc(companyId)}`)) },

  profile() { return latestRead('profile', () => request('/portal/internship/context/profile')) },
  updateProfile(body) { return request('/portal/internship/context/profile', { method: 'PUT', body: normalizeProfileWriteBody(body) }) },
  profileCompleteness() { return latestRead('profile-completeness', () => request('/portal/internship/profile/completeness')) },
  profileItems() { return latestRead('profile-items', () => request('/portal/internship/profile/items')) },
  createProfileItem(body) { return request('/portal/internship/profile/items', { method: 'POST', body: normalizeProfileItemWriteBody(body) }) },
  updateProfileItem(itemId, body) { return request(`/portal/internship/profile/items/${enc(itemId)}`, { method: 'PUT', body: normalizeProfileItemWriteBody(body) }) },
  deleteProfileItem(itemId) { return request(`/portal/internship/profile/items/${enc(itemId)}`, { method: 'DELETE' }) },
  profilePreview() { return latestRead('profile-preview', () => request('/portal/internship/profile/preview')) },
  profilePdfPreview(body = {}) { return request('/portal/internship/profile/pdf-preview', { method: 'POST', body }) },

  volunteers() { return latestRead('volunteers', () => request('/portal/internship/context/volunteers')) },
  saveVolunteers(body) { return request('/portal/internship/context/volunteers', { method: 'PUT', body }) },
  materialPreview() { return latestRead('material-preview', () => request('/portal/internship/context/volunteers/material-preview')) },
  submitVolunteers(body) { return request('/portal/internship/context/volunteers/submit', { method: 'POST', body }) },
  withdrawVolunteers(body = {}) { return request('/portal/internship/context/volunteers/withdraw', { method: 'POST', body }) },
  requestUnlock(body = {}) { return request('/portal/internship/context/volunteers/unlock-request', { method: 'POST', body }) },
  submissions() { return latestRead('submissions', () => request('/portal/internship/context/volunteers/submissions')) },
  submission(version) { return latestRead('submission', () => request(`/portal/internship/context/volunteers/submissions/${enc(version)}`)) },
  revokeContactConsent(body = {}) { return request('/portal/internship/context/volunteers/contact-consent/revoke', { method: 'POST', body }) }
}

export default internshipSelectionApi
