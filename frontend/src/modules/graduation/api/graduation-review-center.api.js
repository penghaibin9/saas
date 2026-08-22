import { request } from '@/services/http/client'
import { withGraduationBatch } from '@/modules/graduation/api/graduation-batch-context'

const CENTER = '/graduation/review-center'
const PROPOSAL = '/graduation/proposals'
const FINAL = '/graduation/finals'
const FORMAL = '/graduation/gd-reviews'

function batchParams(params = {}) {
  return withGraduationBatch(params)
}

function required(value, message) {
  if (value == null || value === '') throw new Error(message)
  return value
}

export const graduationReviewCenterApi = {
  summary(params = {}) {
    return request(`${CENTER}/summary`, { params: batchParams(params) })
  },

  tasks(params = {}) {
    return request(`${CENTER}/tasks`, { params: batchParams(params) })
  },

  detail(caseType, recordId, params = {}) {
    required(caseType, '缺少评阅类型')
    required(recordId, '缺少评阅记录标识')
    return request(`${CENTER}/tasks/${encodeURIComponent(caseType)}/${encodeURIComponent(recordId)}`, {
      params: batchParams(params)
    })
  },

  async writeContext(task = {}) {
    const type = String(task.caseType || '').toUpperCase()
    const recordId = required(task.recordId, '缺少评阅记录标识')
    if (type === 'PROPOSAL') {
      const data = await request(`${PROPOSAL}/${encodeURIComponent(recordId)}`, { params: batchParams() })
      return { kind: 'PROPOSAL', ...data }
    }
    if (type === 'FINAL' || type === 'FINAL_DRAFT') {
      const data = await request(`${FINAL}/${encodeURIComponent(recordId)}`, { params: batchParams() })
      return { kind: type, ...data }
    }
    if (type === 'FORMAL_REVIEW') {
      const data = await request(FORMAL, {
        params: batchParams({ page: 1, pageSize: 200, gdStudentId: task.gdStudentId })
      })
      const rows = Array.isArray(data?.items) ? data.items : []
      const row = rows.find((item) => String(item.id) === String(recordId))
      if (!row) throw new Error('正式评阅任务已变化或不在当前数据范围，请刷新队列')
      return { kind: 'FORMAL_REVIEW', ...row }
    }
    throw new Error(`不支持的评阅类型：${type || 'UNKNOWN'}`)
  },

  reviewProposal(recordId, { action, comment, expectedVersion, fileVersionId } = {}) {
    return request(`${PROPOSAL}/${encodeURIComponent(recordId)}/review`, {
      method: 'POST', params: batchParams(), body: { action, comment, expectedVersion, fileVersionId }
    })
  },

  reviewFinal(recordId, { action, comment, expectedVersion, fileVersionId } = {}) {
    return request(`${FINAL}/${encodeURIComponent(recordId)}/review`, {
      method: 'POST', params: batchParams(), body: { action, comment, expectedVersion, fileVersionId }
    })
  },

  submitFormal(recordId, { score, opinion, expectedVersion, fileVersionId, categories = [], issues = [] } = {}) {
    return request(`${FORMAL}/${encodeURIComponent(recordId)}/submit`, {
      method: 'POST', params: batchParams(),
      body: { score, opinion, expectedVersion, fileVersionId, categories, issues }
    })
  },

  returnFormal(recordId, reason) {
    return request(`${FORMAL}/${encodeURIComponent(recordId)}/return`, {
      method: 'POST', params: batchParams(), body: { reason }
    })
  }
}

export default graduationReviewCenterApi
