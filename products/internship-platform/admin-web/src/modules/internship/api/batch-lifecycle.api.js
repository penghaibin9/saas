import { request } from '@/services/http/client'

function ok(data) {
  return { code: 0, data, message: 'ok' }
}

function fail(e) {
  if (e?.biz) return { code: e.code || 1, data: null, message: e.message || '操作失败' }
  return { code: e?.code || 503001, data: null, message: e?.message || '真实接口不可用' }
}

async function call(fn) {
  try {
    return ok(await fn())
  } catch (e) {
    return fail(e)
  }
}

export const batchLifecycleApi = {
  getReadiness(id) {
    return call(() => request(`/internship/batches/${id}/readiness`))
  },

  close(id, { expectedVersion, force = false, forceReason = '' } = {}) {
    return call(() => request(`/internship/batches/${id}/close`, {
      method: 'POST',
      body: { expectedVersion, force, forceReason }
    }))
  }
}

export default batchLifecycleApi
