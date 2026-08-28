import { request } from '@/services/http/client'

function ok(data) { return Promise.resolve({ code: 0, data, message: 'ok' }) }
function fail(message, code = 1, bizCode = '') { return Promise.resolve({ code, bizCode, data: null, message }) }
function toErr(error) {
  if (error?.biz) return fail(error.message, error.code || 1, error.bizCode || error.biz?.bizCode || '')
  return fail(error?.message || '真实接口不可用', 503001)
}
async function call(fn) {
  try { return ok(await fn()) } catch (error) { return toErr(error) }
}

const BASE = '/student-affairs/funding/disbursements'

export const fundingExportApi = {
  create(body) {
    return call(() => request(`${BASE}/export`, { method: 'POST', body }))
  },
  job(jobId) {
    return call(() => request(`${BASE}/export-jobs/${jobId}`))
  },
  ticket(jobId, expectedVersion) {
    return call(() => request(`${BASE}/export-jobs/${jobId}/download-ticket`, {
      method: 'POST', body: { expectedVersion }
    }))
  }
}

export default fundingExportApi
