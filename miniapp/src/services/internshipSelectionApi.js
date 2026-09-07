import { selectionScope, selectionScopePath, selectionScopeBody } from '../../../shared/internshipSelectionScope.mjs'
/**
 * E-A03 学生小程序「实习选岗」V3 facade。
 * 对接现有 Profile/Snapshot/VolunteerGroup HTTP 服务；原轮次 scope 随请求传递。
 * 读取保持 latest-wins，不创建第二套岗位或志愿记录，也不回退旧企业岗位全量接口。
 */
import { realRequest as baseRequest } from './request'

const enc = (value) => encodeURIComponent(String(value ?? ''))

function mobileProfileProjection(raw = {}) {
  const profile = raw?.profile && typeof raw.profile === 'object' ? raw.profile : raw
  return {
    ...(raw || {}),
    availableFrom: profile?.availableFrom || raw?.availableFrom || ''
  }
}

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

export function createInternshipSelectionApi(input = {}) {
const scope = selectionScope(input)
const latestReads = new Map()

function latestRead(key, task) {
  let exposed
  const raw = Promise.resolve().then(task)
  exposed = raw.then(
    (value) => latestReads.get(key) === exposed ? value : latestReads.get(key),
    (error) => {
      if (latestReads.get(key) !== exposed) return latestReads.get(key)
      throw error
    }
  )
  latestReads.set(key, exposed)
  return exposed
}

function realRequest(path, options = {}) {
  if (path.startsWith('/mobile/internship/catalog/') || path.startsWith('/mobile/internship/context/volunteers') || ['/completeness', '/preview', '/pdf-preview'].some(suffix => path === '/mobile/internship/profile' + suffix)) {
    path = selectionScopePath(path, scope)
    if (options.method && options.method !== 'GET') options = { ...options, data: selectionScopeBody(options.data, scope) }
  }
  return baseRequest(path, options)
}
return {
  forScope: createInternshipSelectionApi,
  volunteerResult(groupId) { return realRequest(`/mobile/internship/volunteer-results/${enc(groupId)}`) },
  context() { return latestRead('context', () => realRequest('/mobile/internship/catalog/context')) },
  positions(query = {}) { return realRequest(withQuery('/mobile/internship/catalog/positions', normalizeMobileCatalogQuery(query))) },
  position(positionId) { return latestRead('position', () => realRequest(`/mobile/internship/catalog/positions/${enc(positionId)}`)) },
  company(companyId) { return latestRead('company', () => realRequest(`/mobile/internship/catalog/companies/${enc(companyId)}`)) },
  profile() { return latestRead('profile', () => realRequest('/mobile/internship/context/profile')).then(mobileProfileProjection) },
  updateProfile(data) { return realRequest('/mobile/internship/context/profile', { method: 'PUT', data }) },
  createProfileItem(data) { return realRequest('/mobile/internship/profile/items', { method: 'POST', data }) },
  updateProfileItem(id, data) { return realRequest(`/mobile/internship/profile/items/${enc(id)}`, { method: 'PUT', data }) },
  deleteProfileItem(id) { return realRequest(`/mobile/internship/profile/items/${enc(id)}`, { method: 'DELETE' }) },
  profilePreview() { return realRequest('/mobile/internship/profile/preview') },
  profileCompleteness() { return latestRead('profile-completeness', () => realRequest('/mobile/internship/profile/completeness')) },
  volunteers() { return latestRead('volunteers', () => realRequest('/mobile/internship/context/volunteers')) },
  saveVolunteers(data) { return realRequest('/mobile/internship/context/volunteers', { method: 'PUT', data: data || {} }) },
  materialPreview() { return latestRead('material-preview', () => realRequest('/mobile/internship/context/volunteers/material-preview')) },
  submitVolunteers(data) { return realRequest('/mobile/internship/context/volunteers/submit', { method: 'POST', data: data || {} }) },
  withdrawVolunteers(data) { return realRequest('/mobile/internship/context/volunteers/withdraw', { method: 'POST', data: data || {} }) },
  requestUnlock(data) { return realRequest('/mobile/internship/context/volunteers/unlock-request', { method: 'POST', data: data || {} }) }
}
}
export const internshipSelectionApi = createInternshipSelectionApi()

export default internshipSelectionApi
