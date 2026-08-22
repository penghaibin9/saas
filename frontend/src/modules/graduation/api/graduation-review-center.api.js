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

function canonicalWrite(path, options) {
  return request(path, options).catch((error) => {
    // Unified HTTP client keeps the stable business code in bizCode and the numeric envelope
    // code in code. W7.4 needs the stable code to refresh canonical facts on optimistic-lock /
    // FileVersion conflicts without weakening the backend fail-closed decision.
    if (error?.bizCode) error.code = error.bizCode
    throw error
  })
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
      // Formal review lock/evidence comes from the same task-scoped Review Center detail.
      // Never widen back to a student-level /gd-reviews list just to recover write fields.
      const data = await request(`${CENTER}/tasks/${encodeURIComponent(type)}/${encodeURIComponent(recordId)}`, {
        params: batchParams()
      })
      const row = data?.case
      if (!row || String(row.recordId) !== String(recordId)) {
        throw new Error('正式评阅任务已变化或不在当前数据范围，请刷新队列')
      }
      if (row.version == null || row.fileVersionId == null) {
        throw new Error('正式评阅任务缺少 W7 冻结版本或乐观锁版本，请刷新或治理历史任务')
      }
      return { kind: 'FORMAL_REVIEW', ...row }
    }
    throw new Error(`不支持的评阅类型：${type || 'UNKNOWN'}`)
  },

  reviewProposal(recordId, { action, comment, expectedVersion, fileVersionId } = {}) {
    return canonicalWrite(`${PROPOSAL}/${encodeURIComponent(recordId)}/review`, {
      method: 'POST', params: batchParams(), body: { action, comment, expectedVersion, fileVersionId }
    })
  },

  reviewFinal(recordId, { action, comment, expectedVersion, fileVersionId } = {}) {
    return canonicalWrite(`${FINAL}/${encodeURIComponent(recordId)}/review`, {
      method: 'POST', params: batchParams(), body: { action, comment, expectedVersion, fileVersionId }
    })
  },

  submitFormal(recordId, { score, opinion, expectedVersion, fileVersionId, categories = [], issues = [] } = {}) {
    return canonicalWrite(`${FORMAL}/${encodeURIComponent(recordId)}/submit`, {
      method: 'POST', params: batchParams(),
      body: { score, opinion, expectedVersion, fileVersionId, categories, issues }
    })
  },

  returnFormal(recordId, reason) {
    return canonicalWrite(`${FORMAL}/${encodeURIComponent(recordId)}/return`, {
      method: 'POST', params: batchParams(), body: { reason }
    })
  }
}

export default graduationReviewCenterApi
