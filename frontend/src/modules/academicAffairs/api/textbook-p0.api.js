import { request } from '@/services/http/client'

const BASE = '/academic-affairs/textbooks'

function ok(data) {
  return { code: 0, data, message: 'ok' }
}

function fail(error) {
  return {
    code: error?.code || 503001,
    data: null,
    message: error?.message || '教材工作台请求失败'
  }
}

async function call(fn) {
  try {
    return ok(await fn())
  } catch (error) {
    return fail(error)
  }
}

export const textbookP0Api = {
  reviewCandidates(termId) {
    return call(() => request(`${BASE}/review-candidates`, { params: { termId } }))
  },
  async listDistributionBatches({ termId, page = 1, pageSize = 50 } = {}) {
    const result = await call(() => request(`${BASE}/distribution-batches`, {
      params: { termId, page, pageSize }
    }))
    if (result.code !== 0) return result
    const data = result.data || {}
    return ok({
      list: data.items || data.list || [],
      total: Number(data.total || 0),
      page: Number(data.page || page),
      pageSize: Number(data.pageSize || pageSize)
    })
  },
  cancelOrder(batchId, reason) {
    return call(() => request(`${BASE}/order-batches/${batchId}/cancel`, {
      method: 'POST', body: { reason }
    }))
  },
  returnDistribution(recordId, reason) {
    return call(() => request(`${BASE}/distribution-records/${recordId}/return`, {
      method: 'POST', body: { reason }
    }))
  }
}
