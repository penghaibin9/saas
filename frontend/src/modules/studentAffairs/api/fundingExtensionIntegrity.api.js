import { request } from '@/services/http/client'

function toResult(error) {
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
    return toResult(error)
  }
}

function pageParams({ status = '', page = 1, pageSize = 50 } = {}) {
  const params = { page, pageSize }
  if (status) params.status = status
  return params
}

export const fundingExtensionIntegrityApi = {
  getWorkStudyRecords(options = {}) {
    return callStrict(() => request('/student-affairs/funding/work-study/records', {
      params: pageParams(options)
    }))
  },

  getLoans(options = {}) {
    return callStrict(() => request('/student-affairs/funding/loans', {
      params: pageParams(options)
    }))
  },

  getFeeReductions(options = {}) {
    return callStrict(() => request('/student-affairs/funding/fee-reductions', {
      params: pageParams(options)
    }))
  }
}
