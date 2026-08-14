/**
 * E-A03 学生小程序「实习选岗」V3 facade。
 * CONTRACT ADAPTER STATUS (A01 @ 899ce77f): canonical Profile/Snapshot/VolunteerGroup services
 * 已落，但 student/mobile Catalog/Profile/Volunteer HTTP facade 尚未完整注册。这里只冻结移动端
 * endpoint/payload；不创建第二套岗位/志愿 Authority，也不回退旧企业岗位全量接口。
 */
import { realRequest } from './request'

const enc = (value) => encodeURIComponent(String(value ?? ''))

function withQuery(path, params = {}) {
  const entries = Object.entries(params).filter(([, value]) => value !== '' && value !== null && value !== undefined)
  if (!entries.length) return path
  const query = entries.map(([key, value]) => `${enc(key)}=${enc(value)}`).join('&')
  return `${path}${path.includes('?') ? '&' : '?'}${query}`
}

export function normalizeMobileCatalogQuery(input = {}) {
  const page = Math.max(1, Number(input.page || 1) || 1)
  const pageSize = Math.min(100, Math.max(1, Number(input.pageSize || 20) || 20))
  const sort = ['RECOMMENDED', 'LATEST', 'REMUNERATION', 'REMAINING'].includes(input.sort) ? input.sort : 'RECOMMENDED'
  const out = { page, pageSize, sort }
  for (const key of ['keyword', 'city', 'companyId', 'accommodation', 'meal', 'majorMatched', 'remuneration']) {
    if (input[key] !== '' && input[key] !== null && input[key] !== undefined) out[key] = input[key]
  }
  return out
}

export const internshipSelectionApi = {
  context() { return realRequest('/mobile/internship/catalog/context') },
  positions(query = {}) { return realRequest(withQuery('/mobile/internship/catalog/positions', normalizeMobileCatalogQuery(query))) },
  position(positionId) { return realRequest(`/mobile/internship/catalog/positions/${enc(positionId)}`) },
  company(companyId) { return realRequest(`/mobile/internship/catalog/companies/${enc(companyId)}`) },
  profile() { return realRequest('/mobile/internship/profile') },
  profileCompleteness() { return realRequest('/mobile/internship/profile/completeness') },
  volunteers() { return realRequest('/mobile/internship/context/volunteers') },
  saveVolunteers(data) { return realRequest('/mobile/internship/context/volunteers', { method: 'PUT', data: data || {} }) },
  materialPreview() { return realRequest('/mobile/internship/context/volunteers/material-preview') },
  submitVolunteers(data) { return realRequest('/mobile/internship/context/volunteers/submit', { method: 'POST', data: data || {} }) },
  withdrawVolunteers(data) { return realRequest('/mobile/internship/context/volunteers/withdraw', { method: 'POST', data: data || {} }) },
  requestUnlock(data) { return realRequest('/mobile/internship/context/volunteers/unlock-request', { method: 'POST', data: data || {} }) }
}

export default internshipSelectionApi
