/**
 * 岗位实习中心 · 实习成绩五项权重 API（P2-D，生产级只走真实后端）。
 * 端点 /internship/scores。权重配置 + 加权核算 + 复核发布状态机，owner + 数据范围后端强校验。
 */
import { getToken, request } from '@/services/http/client'
import { API_BASE_URL, API_PREFIX } from '@/services/http/config'

function ok(data) { return Promise.resolve({ code: 0, data, message: 'ok' }) }
function fail(message, code = 1) { return Promise.resolve({ code, data: null, message }) }
function toErr(e) {
  if (e?.biz) return fail(e.message, e.code || 1)
  return fail(e?.message || '真实接口不可用', 503001)
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

async function uploadEvidence(file) {
  if (!file) throw new Error('请选择需要上传的调分依据')
  const token = getToken()
  const form = new FormData()
  form.append('file', file)
  const response = await fetch(`${API_BASE_URL}${API_PREFIX}/files?bizType=INTERNSHIP_SCORE_ADJUSTMENT`, {
    method: 'POST', headers: token ? { Authorization: `Bearer ${token}` } : {}, body: form
  })
  let payload = null
  try { payload = await response.json() } catch { payload = null }
  if (!response.ok || !payload || payload.code !== 0) throw new Error(payload?.message || '调分依据上传失败')
  return payload.data
}

const B = '/internship/scores'
const A = '/internship/score-appeals'

export const scoreApi = {
  getConfig() { return call(() => request(`${B}/config`)) },
  saveConfig(body) { return call(() => request(`${B}/config`, { method: 'POST', body })) },
  getScores(params = {}) { return callList(B, params) },
  getAppeals(params = {}) { return callList(A, params) },
  approveAppeal(id, body) { return call(() => request(`${A}/${id}/approve`, { method: 'POST', body })) },
  rejectAppeal(id, body) { return call(() => request(`${A}/${id}/reject`, { method: 'POST', body })) },
  getDetail(id) { return call(() => request(`${B}/${id}`)) },
  compute(body) { return call(() => request(`${B}/compute`, { method: 'POST', body })) },
  uploadEvidence(file) { return call(() => uploadEvidence(file)) },
  review(id, { expectedVersion, version } = {}) {
    return call(() => request(`${B}/${id}/review`, {
      method: 'POST', body: { expectedVersion: expectedVersion ?? version }
    }))
  },
  publish(id, { expectedVersion, version } = {}) {
    return call(() => request(`${B}/${id}/publish`, {
      method: 'POST', body: { expectedVersion: expectedVersion ?? version }
    }))
  },
  returnRecalc(id, { reason, expectedVersion, version } = {}) {
    return call(() => request(`${B}/${id}/return`, {
      method: 'POST', body: { reason: reason || '', expectedVersion: expectedVersion ?? version }
    }))
  },
  withdraw(id, { reason, expectedVersion, version }) {
    return call(() => request(`${B}/${id}/withdraw`, {
      method: 'POST', body: { reason, expectedVersion: expectedVersion ?? version }
    }))
  },
  archive(id, { expectedVersion, version } = {}) {
    return call(() => request(`${B}/${id}/archive`, {
      method: 'POST', body: { expectedVersion: expectedVersion ?? version }
    }))
  },
  exportScores(params = {}) { return call(() => request(`${B}/export`, { method: 'POST', params })) }
}
