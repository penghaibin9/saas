/**
 * E-A03 学生小程序「实习选岗」V3 facade。
 * canonical Profile/Snapshot/VolunteerGroup service 已在 A01 建立；student/mobile HTTP facade
 * 尚未完整注册。这里只冻结移动端 endpoint/payload，并保证异步读取 latest-wins；不创建
 * 第二套岗位/志愿 Authority，也不回退旧企业岗位全量接口。
 */
import { realRequest } from './request'

const enc = (value) => encodeURIComponent(String(value ?? ''))
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
    selectionBlockReason: '暂时无法读取学校招聘季信息，请稍后重试。'
  }
}

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

export const internshipSelectionApi = {
  context() { return latestRead('context', () => realRequest('/mobile/internship/catalog/context'), unavailableContext) },
  positions(query = {}) { return realRequest(withQuery('/mobile/internship/catalog/positions', normalizeMobileCatalogQuery(query))) },
  position(positionId) { return latestRead('position', () => realRequest(`/mobile/internship/catalog/positions/${enc(positionId)}`)) },
  company(companyId) { return latestRead('company', () => realRequest(`/mobile/internship/catalog/companies/${enc(companyId)}`)) },
  profile() { return latestRead('profile', () => realRequest('/mobile/internship/context/profile')).then(mobileProfileProjection) },
  profileCompleteness() { return latestRead('profile-completeness', () => realRequest('/mobile/internship/profile/completeness')) },
  volunteers() { return latestRead('volunteers', () => realRequest('/mobile/internship/context/volunteers')) },
  saveVolunteers(data) { return realRequest('/mobile/internship/context/volunteers', { method: 'PUT', data: data || {} }) },
  materialPreview() { return latestRead('material-preview', () => realRequest('/mobile/internship/context/volunteers/material-preview')) },
  submitVolunteers(data) { return realRequest('/mobile/internship/context/volunteers/submit', { method: 'POST', data: data || {} }) },
  withdrawVolunteers(data) { return realRequest('/mobile/internship/context/volunteers/withdraw', { method: 'POST', data: data || {} }) },
  requestUnlock(data) { return realRequest('/mobile/internship/context/volunteers/unlock-request', { method: 'POST', data: data || {} }) }
}

export default internshipSelectionApi
