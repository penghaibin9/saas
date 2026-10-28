/**
 * 岗位实习中心 · 指导记录 / 教师巡访 API（P1-Stage2，生产级只走真实后端）。
 * 端点 /internship/guidances、/internship/visits。
 * owner + 数据范围由后端强校验，前端仅负责交互与提示。
 */
import { request, requestUpload, requestBlob } from '@/services/http/client'
import { normalizeUiError } from '@/utils/presentationSafety'

function ok(data) { return Promise.resolve({ code: 0, data, message: 'ok' }) }
function fail(message, code = 1) { return Promise.resolve({ code, data: null, message }) }
function toErr(e) {
  return { code: e?.code || 503001, data: null,
    message: normalizeUiError(e, { fallback: '操作未完成，请稍后重试' }).userMessage,
    httpStatus: e?.httpStatus, biz: e?.biz, bizCode: e?.bizCode }
}
async function call(fn) {
  try { return ok(await fn()) } catch (e) { return toErr(e) }
}
async function callList(path, params = {}) {
  try {
    const d = await request(path, { params })
    return ok({ list: d.items || [], total: d.total || 0, page: d.page || 1, pageSize: d.pageSize || 20 })
  } catch (e) { return toErr(e) }
}

const B = '/internship'

// 附件：走文件中心真实上传/下载（不伪造）。
export async function uploadAttachment(file) {
  try { return ok(await requestUpload('/files', file)) } catch (e) { return toErr(e) }
}
export async function downloadAttachment(fileId, fileName = '附件', isCurrent = () => true) {
  if (!isCurrent()) return false
  const blob = await requestBlob(`/files/download/${fileId}`)
  if (!isCurrent()) return false
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = fileName; document.body.appendChild(a); a.click()
  a.remove(); URL.revokeObjectURL(url)
  return true
}

export const guidanceVisitApi = {
  uploadAttachment,
  downloadAttachment,
  // 指导记录
  getGuidances(params = {}) { return callList(`${B}/guidances`, params) },
  getGuidanceDetail(id) { return call(() => request(`${B}/guidances/${id}`)) },
  createGuidance(body) { return call(() => request(`${B}/guidances`, { method: 'POST', body })) },
  async createGuidancesBatch(body) {
    const result = await call(() => request(`${B}/guidances/batch`, { method: 'POST', body }))
    if (result.code === 0 && Array.isArray(result.data?.items)) result.data.items = result.data.items.map(row => row.success ? row : {
      ...row, message: normalizeUiError({ code: row.code, message: row.message }, { fallback: '本条未完成，请保留原输入重试' }).userMessage
    })
    return result
  },
  getAttachmentMetadata(id) { return call(() => request(`/files/${id}`)) },
  voidGuidance(id, { reason, expectedVersion, version, batchId } = {}) {
    return call(() => request(`${B}/guidances/${id}/void`, {
      method: 'POST', body: { reason: reason || '', expectedVersion: expectedVersion ?? version, batchId }
    }))
  },
  exportGuidances(params = {}) { return call(() => request(`${B}/guidances/export`, { method: 'POST', params })) },
  getGuidanceStats(threshold = 2, params = {}) {
    return call(() => request(`${B}/guidances/stats`, { params: { threshold, ...params } }))
  },
  getGuidancePlans(params = {}) { return callList(`${B}/guidance-plans`, params) },
  exportGuidancePlans(params = {}) {
    return call(() => request(`${B}/guidance-plans/export`, { method: 'POST', params }))
  },
  // 教师巡访
  getVisits(params = {}) { return callList(`${B}/visits`, params) },
  getVisitDetail(id) { return call(() => request(`${B}/visits/${id}`)) },
  getVisitLocation(id, body) { return call(() => request(`${B}/visits/${id}/location/disclose`, { method: 'POST', body })) },
  createVisit(body) { return call(() => request(`${B}/visits`, { method: 'POST', body })) },
  rectifyVisit(id, { status, note, expectedVersion, version, batchId }) {
    return call(() => request(`${B}/visits/${id}/rectify`, {
      method: 'POST', body: { status, note, batchId, expectedVersion: expectedVersion ?? version }
    }))
  },
  exportVisits(params = {}) { return call(() => request(`${B}/visits/export`, { method: 'POST', params })) },
  getVisitStats(params = {}) { return call(() => request(`${B}/visits/stats`, { params })) },
  // 企业沟通 / 巡访计划（深链真实接线）
  getCommunications(params = {}) { return callList(`${B}/communications`, params) },
  getCommunicationDetail(id) { return call(() => request(`${B}/communications/${id}`)) },
  createCommunication(body) { return call(() => request(`${B}/communications`, { method: 'POST', body })) },
  voidCommunication(id, reason) {
    return call(() => request(`${B}/communications/${id}/void`, { method: 'POST', body: { reason } }))
  },
  getVisitPlans(params = {}) { return callList(`${B}/visit-plans`, params) },
  getVisitPlanDetail(id) { return call(() => request(`${B}/visit-plans/${id}`)) },
  createVisitPlan(body) { return call(() => request(`${B}/visit-plans`, { method: 'POST', body })) },
  transitionVisitPlan(id, action, body = {}) {
    return call(() => request(`${B}/visit-plans/${id}/transition`, {
      method: 'POST', body: { ...(body || {}), action }
    }))
  }
}

export default guidanceVisitApi
