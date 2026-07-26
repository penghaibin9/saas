import { realRequest } from '@/services/request'

export const affairsAppealApi = {
  getPending: (kind) => realRequest(`/mobile/teacher/affairs/appeals/${kind}`),
  review: (kind, appealId, body) => realRequest(`/mobile/teacher/affairs/appeals/${kind}/${appealId}/review`, {
    method: 'POST', data: body
  }),
  getMyCreditAppeals: () => realRequest('/mobile/affairs/second-class/appeals/my'),
  submitCreditAppeal: (body) => realRequest('/mobile/affairs/second-class/appeals', {
    method: 'POST', data: body
  })
}

export default affairsAppealApi
