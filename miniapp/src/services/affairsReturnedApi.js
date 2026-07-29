import { realRequest } from '@/services/request'

export const affairsReturnedApi = {
  getAid: (applyId) => realRequest(`/mobile/affairs/aid/${applyId}/editable`),
  updateAid: (applyId, data) => realRequest(`/mobile/affairs/aid/${applyId}/returned`, { method: 'PUT', data }),
  resubmitAid: (applyId, version) => realRequest(`/mobile/affairs/aid/${applyId}/resubmit`, { method: 'POST', data: { version } }),
  getFunding: (appId) => realRequest(`/mobile/affairs/funding/${appId}/editable`),
  updateFunding: (appId, data) => realRequest(`/mobile/affairs/funding/${appId}/returned`, { method: 'PUT', data }),
  resubmitFunding: (appId, version) => realRequest(`/mobile/affairs/funding/${appId}/resubmit`, { method: 'POST', data: { version } })
}

export default affairsReturnedApi
