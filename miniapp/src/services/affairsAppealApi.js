import { realRequest } from '@/services/request'

function creditAppealBody(body = {}) {
  const value = Number(body.claimValue)
  if (!Number.isFinite(value) || value <= 0) {
    throw new Error('主张数值必填且必须大于0')
  }
  if (Math.round(value * 100) !== value * 100) {
    throw new Error('主张数值最多保留2位小数')
  }
  return { ...body, claimValue: value }
}

export const affairsAppealApi = {
  getPending: (kind) => realRequest(`/mobile/teacher/affairs/appeals/${kind}`),
  review: (kind, appealId, body) => realRequest(`/mobile/teacher/affairs/appeals/${kind}/${appealId}/review`, {
    method: 'POST', data: body
  }),
  getMyCreditAppeals: (page = 1, pageSize = 100) => realRequest('/mobile/affairs/second-class/appeals/my', {
    query: { page, pageSize }
  }),
  submitCreditAppeal: (body) => realRequest('/mobile/affairs/second-class/appeals', {
    method: 'POST', data: creditAppealBody(body)
  })
}

export default affairsAppealApi
