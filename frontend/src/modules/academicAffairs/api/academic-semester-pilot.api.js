import { request } from '@/services/http/client'

const BASE = '/academic-affairs/semester-pilots'

function ok(data) { return { code: 0, data, message: 'ok' } }
function fail(error) { return { code: error?.code || 1, data: null, message: error?.message || '真实学期验收服务不可用' } }
async function call(fn) {
  try { return ok(await fn()) } catch (error) { return fail(error) }
}

export const academicSemesterPilotApi = {
  create(body) {
    return call(() => request(BASE, { method: 'POST', body }))
  },
  list(params = {}) {
    return call(() => request(BASE, { params }))
  },
  detail(pilotId) {
    return call(() => request(`${BASE}/${pilotId}`))
  },
  check(pilotId) {
    return call(() => request(`${BASE}/${pilotId}/check`, { method: 'POST' }))
  },
  complete(pilotId, confirmText, completionNote) {
    return call(() => request(`${BASE}/${pilotId}/complete`, {
      method: 'POST',
      body: { confirmText, completionNote }
    }))
  },
  cancel(pilotId, reason) {
    return call(() => request(`${BASE}/${pilotId}/cancel`, { method: 'POST', body: { reason } }))
  }
}

export default academicSemesterPilotApi
