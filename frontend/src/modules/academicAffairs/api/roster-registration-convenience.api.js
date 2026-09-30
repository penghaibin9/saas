import { request } from '@/services/http/client'

const BASE = '/academic-affairs'

function toError(error) {
  return {
    code: error?.code || 500000,
    bizCode: error?.bizCode || '',
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

  async previewBulkRegistration(batchId, studentIds) {
    return call(() => request(`${BASE}/registration-batches/${batchId}/bulk-register-preview`, {
      method: 'POST',
      body: { studentIds: (studentIds || []).map(String) }
    }))
  },

  async confirmBulkRegistration(batchId, previewToken) {
    if (typeof previewToken !== 'string' || !previewToken) {
      return { code: 400001, message: '请先重新预览本次批量注册名单', data: null }
    }
    return call(() => request(`${BASE}/registration-batches/${batchId}/bulk-register`, {
      method: 'POST',
      body: { previewToken }
    }))
  }
}
