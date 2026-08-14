/**
 * E-A03 学生选岗 API facade。
 *
 * TEMPORARY ADAPTER CONTRACT:
 * A01 当前仍停在 Contract Freeze HEAD；这里先锁定 V3 endpoint / payload / pagination，
 * 不新增后端 Authority，不回落到前端自造 InternshipApplication 真值。
 * A01 API 落地后仅替换适配细节，页面合同保持不变。
 */
import { request } from './request'
import { normalizeCatalogQuery } from '../modules/internshipRecruitment/selectionContract'

const enc = (value) => encodeURIComponent(String(value ?? ''))

export const internshipSelectionApi = {
  context() {
    return request('/portal/internship/catalog/context')
  },
  positions(query = {}) {
    return request('/portal/internship/catalog/positions', { params: normalizeCatalogQuery(query) })
  },
  position(positionId) {
    return request(`/portal/internship/catalog/positions/${enc(positionId)}`)
  },
  company(companyId) {
    return request(`/portal/internship/catalog/companies/${enc(companyId)}`)
  },

  profile() {
    return request('/portal/internship/profile')
  },
  updateProfile(body) {
    return request('/portal/internship/profile', { method: 'PUT', body })
  },
  profileCompleteness() {
    return request('/portal/internship/profile/completeness')
  },
  profileItems() {
    return request('/portal/internship/profile/items')
  },
  createProfileItem(body) {
    return request('/portal/internship/profile/items', { method: 'POST', body })
  },
  updateProfileItem(itemId, body) {
    return request(`/portal/internship/profile/items/${enc(itemId)}`, { method: 'PUT', body })
  },
  deleteProfileItem(itemId) {
    return request(`/portal/internship/profile/items/${enc(itemId)}`, { method: 'DELETE' })
  },
  profilePreview() {
    return request('/portal/internship/profile/preview')
  },
  profilePdfPreview(body = {}) {
    return request('/portal/internship/profile/pdf-preview', { method: 'POST', body })
  },

  volunteers() {
    return request('/portal/internship/context/volunteers')
  },
  saveVolunteers(body) {
    return request('/portal/internship/context/volunteers', { method: 'PUT', body })
  },
  materialPreview() {
    return request('/portal/internship/context/volunteers/material-preview')
  },
  submitVolunteers(body) {
    return request('/portal/internship/context/volunteers/submit', { method: 'POST', body })
  },
  withdrawVolunteers(body = {}) {
    return request('/portal/internship/context/volunteers/withdraw', { method: 'POST', body })
  },
  requestUnlock(body = {}) {
    return request('/portal/internship/context/volunteers/unlock-request', { method: 'POST', body })
  },
  submissions() {
    return request('/portal/internship/context/volunteers/submissions')
  },
  submission(version) {
    return request(`/portal/internship/context/volunteers/submissions/${enc(version)}`)
  },
  revokeContactConsent(body = {}) {
    return request('/portal/internship/context/volunteers/contact-consent/revoke', { method: 'POST', body })
  }
}

export default internshipSelectionApi
