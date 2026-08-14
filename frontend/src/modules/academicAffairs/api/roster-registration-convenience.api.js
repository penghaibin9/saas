import { request } from '@/services/http/client'

const BASE = '/academic-affairs'
const previewTokens = new Map()

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

  async previewBulkRegistration(batchId, studentIds) {
    const key = String(batchId)
    previewTokens.delete(key)
    const result = await call(() => request(`${BASE}/registration-batches/${batchId}/bulk-register-preview`, {
      method: 'POST',
      body: { studentIds: (studentIds || []).map(Number) }
    }))
    if (result.code === 0 && result.data?.previewToken) {
      previewTokens.set(key, result.data.previewToken)
    }
    return result
  },

  async confirmBulkRegistration(batchId) {
    const key = String(batchId)
    const previewToken = previewTokens.get(key)
    if (!previewToken) {
      return { code: 400001, message: '请先重新预览本次批量注册名单', data: null }
    }
    const result = await call(() => request(`${BASE}/registration-batches/${batchId}/bulk-register`, {
      method: 'POST',
      body: { previewToken }
    }))
    // 一次确认尝试后即丢弃浏览器内存 token；失败也必须重新 preview，避免误用旧快照。
    previewTokens.delete(key)
    return result
  }
}