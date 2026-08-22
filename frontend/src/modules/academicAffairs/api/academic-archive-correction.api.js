import { request } from '@/services/http/client'

const BASE = '/academic-affairs/archive'

function ok(data) {
  return { code: 0, data, message: 'ok' }
}

function fail(error) {
  return {
    code: error?.code || 1,
    data: null,
    message: error?.message || '归档后纠错服务不可用'
  }
}

async function call(fn) {
  try {
    return ok(await fn())
  } catch (error) {
    return fail(error)
  }
}

export const academicArchiveCorrectionApi = {
  list(batchId, params = {}) {
    return call(() => request(`${BASE}/batches/${batchId}/corrections`, { params }))
  },

  detail(caseId) {
    return call(() => request(`${BASE}/corrections/${caseId}`))
  },

  create(batchId, body) {
    return call(() => request(`${BASE}/batches/${batchId}/corrections`, {
      method: 'POST',
      body
    }))
  },

  approve(caseId) {
    return call(() => request(`${BASE}/corrections/${caseId}/approve`, {
      method: 'POST'
    }))
  },

  reject(caseId, reason) {
    return call(() => request(`${BASE}/corrections/${caseId}/reject`, {
      method: 'POST',
      body: { reason }
    }))
  },

  verifyManifest(batchId) {
    return call(() => request(`${BASE}/batches/${batchId}/manifest/verify`))
  }
}

export default academicArchiveCorrectionApi
