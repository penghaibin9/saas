import { request } from '@/services/http/client'

const BASE = '/academic-affairs'

function toError(error) {
  return {
    code: Number(error?.code || 500000),
    message: error?.message || '请求失败，请稍后重试',
    data: null
  }
}

async function call(fn) {
  try {
    return { code: 0, message: 'ok', data: await fn() }
  } catch (error) {
    return toError(error)
  }
}

export const rosterRegistrationConvenienceApi = {
  getCandidates(batchId, params = {}) {
    return call(async () => {
      const data = await request(`${BASE}/registration-batches/${batchId}/registration-candidates`, { params })
      return {
        list: data.items || [],
        total: Number(data.total || 0),
        page: Number(data.page || params.page || 1),
        pageSize: Number(data.pageSize || params.pageSize || 20)
      }
    })
  },

  previewBulkRegistration(batchId, studentIds) {
    return call(() => request(`${BASE}/registration-batches/${batchId}/bulk-register-preview`, {
      method: 'POST',
      body: { studentIds: (studentIds || []).map(Number) }
    }))
  },

  confirmBulkRegistration(batchId, studentIds) {
    return call(() => request(`${BASE}/registration-batches/${batchId}/bulk-register`, {
      method: 'POST',
      body: { studentIds: (studentIds || []).map(Number) }
    }))
  }
}
