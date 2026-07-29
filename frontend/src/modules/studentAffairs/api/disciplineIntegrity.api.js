import { request } from '@/services/http/client'

function toError(error) {
  if (error?.biz) {
    return {
      code: error.code || 1,
      bizCode: error.bizCode || '',
      data: null,
      message: error.message || '操作失败'
    }
  }
  return {
    code: error?.code || 503001,
    bizCode: error?.bizCode || '',
    data: null,
    message: error?.message || '真实接口不可用'
  }
}

async function callStrict(fn) {
  try {
    return { code: 0, data: await fn(), message: 'ok' }
  } catch (error) {
    return toError(error)
  }
}

export const disciplineIntegrityApi = {
  deliverCase(caseId, { method, remark = '', version }) {
    return callStrict(() => request(`/student-affairs/discipline/cases/${caseId}/deliver`, {
      method: 'POST',
      body: { method, remark, version }
    }))
  },

  reviewAppeal(appealId, { result, opinion, version, revisedDiscType = '' }) {
    const body = { result, opinion, version }
    if (result === 'REVISED') body.revisedDiscType = revisedDiscType
    return callStrict(() => request(`/student-affairs/discipline/appeals/${appealId}/review`, {
      method: 'POST',
      body
    }))
  }
}
