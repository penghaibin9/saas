/**
 * E-A03 学生选岗 API facade。
 *
 * CONTRACT ADAPTER STATUS (A01 @ 899ce77f):
 * A01 已落 StudentInternshipProfile / immutable ApplicationMaterialSnapshot /
 * InternshipVolunteerGroup canonical services，但学生 Catalog/Profile/Volunteer HTTP facade
 * 尚未完整注册。因此此文件继续只冻结 V3 endpoint / payload / pagination；禁止回落旧
 * InternshipApplication 三次写入，也禁止前端自造第二套真值。对应 HTTP 路由进入 A01 后
 * 页面无需改业务模型，只切换为真实 Authority 调用。
 */
import { request } from './request'
import { normalizeCatalogQuery } from '../modules/internshipRecruitment/selectionContract.js'

const enc = (value) => encodeURIComponent(String(value ?? ''))

export const internshipSelectionApi = {
  context() { return request('/portal/internship/catalog/context') },
  positions(query = {}) { return request('/portal/internship/catalog/positions', { params: normalizeCatalogQuery(query) }) },
  position(positionId) { return request(`/portal/internship/catalog/positions/${enc(positionId)}`) },
  company(companyId) { return request(`/portal/internship/catalog/companies/${enc(companyId)}`) },

  profile() { return request('/portal/internship/profile') },
  updateProfile(body) { return request('/portal/internship/profile', { method: 'PUT', body }) },
  profileCompleteness() { return request('/portal/internship/profile/completeness') },
  profileItems() { return request('/portal/internship/profile/items') },
  createProfileItem(body) { return request('/portal/internship/profile/items', { method: 'POST', body }) },
  updateProfileItem(itemId, body) { return request(`/portal/internship/profile/items/${enc(itemId)}`, { method: 'PUT', body }) },
  deleteProfileItem(itemId) { return request(`/portal/internship/profile/items/${enc(itemId)}`, { method: 'DELETE' }) },
  profilePreview() { return request('/portal/internship/profile/preview') },
  profilePdfPreview(body = {}) { return request('/portal/internship/profile/pdf-preview', { method: 'POST', body }) },

  volunteers() { return request('/portal/internship/context/volunteers') },
  saveVolunteers(body) { return request('/portal/internship/context/volunteers', { method: 'PUT', body }) },
  materialPreview() { return request('/portal/internship/context/volunteers/material-preview') },
  submitVolunteers(body) { return request('/portal/internship/context/volunteers/submit', { method: 'POST', body }) },
  withdrawVolunteers(body = {}) { return request('/portal/internship/context/volunteers/withdraw', { method: 'POST', body }) },
  requestUnlock(body = {}) { return request('/portal/internship/context/volunteers/unlock-request', { method: 'POST', body }) },
  submissions() { return request('/portal/internship/context/volunteers/submissions') },
  submission(version) { return request(`/portal/internship/context/volunteers/submissions/${enc(version)}`) },
  revokeContactConsent(body = {}) { return request('/portal/internship/context/volunteers/contact-consent/revoke', { method: 'POST', body }) }
}

export default internshipSelectionApi
